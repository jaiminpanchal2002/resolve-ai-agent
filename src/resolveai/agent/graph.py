"""LangGraph agent orchestration for ResolveAI.

The workflow is a real StateGraph, not a sequential loop:

    classify -> plan -> execute_tools -> guardrails --(violations?)--+
                                             |                       |
                                        [no] v                  [yes] v
                                     generate_response    finalize_escalation
                                             \\                 /
                                              +---> END <-----+

Design decisions worth defending in review:
- Guardrail routing is a *conditional edge*: when deterministic rules fire,
  we skip the final LLM call entirely and build the escalation response in
  code — cheaper, faster, and impossible for the model to talk itself out of.
- Every node execution is audited to Postgres (agent_steps), every tool
  invocation to tool_calls, and the run summary to agent_runs.
- The DB session is passed through LangGraph's configurable rather than
  globals, keeping nodes pure and unit-testable.
"""

import datetime
import json
import logging
import re
import time
import uuid
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy import select
from typing_extensions import TypedDict

from resolveai.agent.guardrails import guardrails_node
from resolveai.agent.tools import (
    create_escalation,
    create_refund_request,
    get_customer,
    get_order,
    get_payment,
    get_shipment,
    search_policy,
)
from resolveai.core.config import settings
from resolveai.core.llm_provider import get_llm_provider
from resolveai.core.pricing import estimate_cost
from resolveai.models.models import (
    AgentDecision,
    AgentRun,
    AgentStep,
    Ticket,
    TicketMessage,
    ToolCall,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# 1. Enumerations and Pydantic schemas for structured LLM communication
# --------------------------------------------------------------------------
class TicketCategory(StrEnum):
    PAYMENT_ISSUE = "PAYMENT_ISSUE"
    DELIVERY_DISPUTE = "DELIVERY_DISPUTE"
    ACCOUNT_ACCESS = "ACCOUNT_ACCESS"
    SUBSCRIPTION_CHANGE = "SUBSCRIPTION_CHANGE"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    AMBIGUOUS = "AMBIGUOUS"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TicketClassification(BaseModel):
    category: TicketCategory = Field(description="Category of the ticket")
    severity: Severity = Field(description="Severity level")
    intent: str = Field(
        description=(
            "Primary intent, e.g. REPORT_MISSING_DELIVERY, CHARGE_DISPUTE, "
            "RESET_PASSWORD, CANCEL_SUBSCRIPTION"
        )
    )
    requires_account_data: bool = Field(description="Whether account data lookup is needed")


class AgentPlan(BaseModel):
    steps: list[str] = Field(description="Sequential plan steps to resolve the issue")


class ToolName(StrEnum):
    GET_CUSTOMER = "get_customer"
    GET_ORDER = "get_order"
    GET_PAYMENT = "get_payment"
    GET_SHIPMENT = "get_shipment"
    SEARCH_POLICY = "search_policy"
    CREATE_REFUND_REQUEST = "create_refund_request"
    CREATE_ESCALATION = "create_escalation"
    DONE = "DONE"


class LLMToolDecision(BaseModel):
    tool_name: ToolName = Field(
        description="Name of the tool to execute or 'DONE' if resolution is ready"
    )
    tool_input: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Dictionary of inputs for the tool. "
            "E.g. {'customer_id': 'CUS-10293'} or {'query': 'refund policy'}"
        ),
    )


class LLMResolution(BaseModel):
    resolution: str = Field(description="Final outcome: RESOLVED or ESCALATE")
    reason: str = Field(description="Explanation of the final outcome")
    evidence: list[str] = Field(description="Policy and data points supporting this decision")
    actions_taken: list[str] = Field(description="Action summaries performed")


# --------------------------------------------------------------------------
# 2. Agent state (LangGraph channels)
# --------------------------------------------------------------------------
def _add_tokens(existing: int, new: int) -> int:
    """Reducer: token counters accumulate across nodes."""
    return existing + new


class AgentState(TypedDict):
    ticket_id: str
    run_id: str
    customer_id: str | None
    messages: list[dict[str, str]]
    classification: TicketClassification | None
    plan: list[str] | None
    tool_outputs: list[dict[str, Any]]
    policy_citations: list[str]
    guardrail_violations: list[str]
    resolution: str | None
    reason: str | None
    evidence: list[str]
    actions_taken: list[str]
    input_tokens: Annotated[int, _add_tokens]
    output_tokens: Annotated[int, _add_tokens]
    estimated_cost: Decimal
    latency_ms: int


def _history(state: AgentState) -> str:
    return "\n".join(f"{m['role']}: {m['content']}" for m in state["messages"])


def _classification_json(state: AgentState) -> str:
    if not state["classification"]:
        return "{}"
    return json.dumps(state["classification"].model_dump())


# --------------------------------------------------------------------------
# 3. Node implementations (pure: state + db in, partial state out)
# --------------------------------------------------------------------------
async def classify_node(state: AgentState, db: Any) -> dict[str, Any]:
    """Classify the ticket intent, category, and severity."""
    provider = get_llm_provider()
    prompt = f"Analyze the following support ticket and classify it:\n\n{_history(state)}"
    system_instruction = (
        "You are an expert customer operations classifier. Categorize tickets with high precision."
    )

    classification, in_tokens, out_tokens = await provider.generate_structured(
        prompt=prompt,
        response_model=TicketClassification,
        system_instruction=system_instruction,
    )

    # Extract customer_id from the conversation if the ticket lacks one.
    customer_id = state["customer_id"]
    if not customer_id:
        for msg in state["messages"]:
            match = re.search(r"CUS-\d+", msg["content"])
            if match:
                customer_id = match.group(0)
                break

    return {
        "classification": classification,
        "customer_id": customer_id,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
    }


async def plan_node(state: AgentState, db: Any) -> dict[str, Any]:
    """Generate a sequential resolution plan."""
    if not state["classification"]:
        return {"plan": []}

    provider = get_llm_provider()
    prompt = (
        f"Support Ticket History:\n{_history(state)}\n\n"
        f"Classification:\n{json.dumps(state['classification'].model_dump())}\n\n"
        "Create a step-by-step resolution plan using tools. "
        "Focus on correctness and policy adherence."
    )
    plan_resp, in_tokens, out_tokens = await provider.generate_structured(
        prompt=prompt,
        response_model=AgentPlan,
        system_instruction=(
            "You are a customer operations planner. Output a structured JSON plan list."
        ),
    )
    return {
        "plan": plan_resp.steps,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
    }


_TOOL_SYSTEM_INSTRUCTION = (
    "You are a customer support tool calling agent. Use the correct tool names and arguments.\n"
    "Tools available:\n"
    "- get_customer(customer_id)\n"
    "- get_order(order_id)\n"
    "- get_payment(payment_id)\n"
    "- get_shipment(order_id)\n"
    "- search_policy(query)\n"
    "- create_refund_request(order_id, amount, reason)\n"
    "- create_escalation(queue_name, reason)\n"
)

MAX_TOOL_LOOPS = 5


async def _dispatch_tool(
    state: AgentState, db: Any, tool_name: str, args: dict[str, Any]
) -> tuple[dict[str, Any], str, list[str], list[str]]:
    """Execute one tool. Returns (result, status, new_citations, new_actions)."""
    citations: list[str] = []
    actions: list[str] = []

    if tool_name == "get_customer":
        cid = args.get("customer_id") or state["customer_id"]
        if not cid:
            return {"error": "Missing customer_id argument"}, "FAILED", citations, actions
        return await get_customer(db, cid), "SUCCESS", citations, actions

    if tool_name == "get_order":
        oid = args.get("order_id")
        if not oid:
            return {"error": "Missing order_id"}, "FAILED", citations, actions
        return await get_order(db, oid), "SUCCESS", citations, actions

    if tool_name == "get_payment":
        pid = args.get("payment_id") or args.get("order_id")
        if not pid:
            return {"error": "Missing payment_id or order_id"}, "FAILED", citations, actions
        return await get_payment(db, pid), "SUCCESS", citations, actions

    if tool_name == "get_shipment":
        oid = args.get("order_id")
        if not oid:
            return {"error": "Missing order_id"}, "FAILED", citations, actions
        return await get_shipment(db, oid), "SUCCESS", citations, actions

    if tool_name == "search_policy":
        query = args.get("query")
        if not query:
            return {"error": "Missing query"}, "FAILED", citations, actions
        result = await search_policy(db, query)
        citations = list(result.get("citations", []))
        return result, "SUCCESS", citations, actions

    if tool_name == "create_refund_request":
        oid = args.get("order_id")
        amount = float(args.get("amount", 0.0))
        reason = args.get("reason", "Customer request")
        if not oid or amount <= 0.0:
            return {"error": "Missing order_id or valid amount"}, "FAILED", citations, actions
        result = await create_refund_request(db, oid, amount, reason)
        actions.append(f"Created refund request for {oid} (Amount: {amount})")
        return result, "SUCCESS", citations, actions

    if tool_name == "create_escalation":
        queue = args.get("queue_name", "general")
        reason = args.get("reason", "Agent escalation")
        result = await create_escalation(db, state["ticket_id"], state["run_id"], queue, reason)
        actions.append(f"Created escalation {result.get('escalation_id')}")
        return result, "SUCCESS", citations, actions

    return {"error": "Unknown tool"}, "FAILED", citations, actions


async def execute_tools_node(state: AgentState, db: Any) -> dict[str, Any]:
    """LLM-guided tool-calling loop with per-call Postgres auditing."""
    provider = get_llm_provider()

    tool_outputs = list(state["tool_outputs"])
    policy_citations = list(state["policy_citations"])
    actions_taken = list(state["actions_taken"])
    input_tokens = 0
    output_tokens = 0

    for _ in range(MAX_TOOL_LOOPS):
        prompt = (
            f"Ticket History:\n{_history(state)}\n\n"
            f"Classification: {_classification_json(state)}\n"
            f"Plan: {json.dumps(state['plan'])}\n\n"
            f"Current Executed Tools and Outputs:\n{json.dumps(tool_outputs)}\n\n"
            "Identify the next tool to execute. If you have all facts to resolve or escalate, "
            "return 'DONE'.\n"
            f"Available customer ID: {state['customer_id']}"
        )
        decision, in_tok, out_tok = await provider.generate_structured(
            prompt=prompt,
            response_model=LLMToolDecision,
            system_instruction=_TOOL_SYSTEM_INSTRUCTION,
        )
        input_tokens += in_tok
        output_tokens += out_tok

        if decision.tool_name == ToolName.DONE:
            break

        tool_name = decision.tool_name.value
        args = decision.tool_input
        tool_start = time.perf_counter()

        try:
            tool_res, status, new_citations, new_actions = await _dispatch_tool(
                state, db, tool_name, args
            )
            policy_citations.extend(new_citations)
            actions_taken.extend(new_actions)
        except Exception as exc:  # noqa: BLE001 - tool errors become auditable FAILED records
            logger.error("Error executing tool %s: %s", tool_name, exc)
            tool_res, status = {"error": str(exc)}, "FAILED"

        tool_latency = int((time.perf_counter() - tool_start) * 1000)

        db.add(
            ToolCall(
                id=f"TLC-{uuid.uuid4().hex[:6].upper()}",
                agent_run_id=state["run_id"],
                tool_name=tool_name,
                input_json=json.dumps(args),
                output_json=json.dumps(tool_res),
                status=status,
                latency_ms=tool_latency,
                created_at=datetime.datetime.now(datetime.UTC),
            )
        )
        tool_outputs.append(
            {"tool": tool_name, "input": args, "output": tool_res, "status": status}
        )

    return {
        "tool_outputs": tool_outputs,
        "policy_citations": sorted(set(policy_citations)),
        "actions_taken": actions_taken,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


async def finalize_escalation_node(state: AgentState, db: Any) -> dict[str, Any]:
    """Deterministic terminal node when guardrails fire.

    No LLM call: the escalation response is built entirely in code so the
    model can never argue its way past a compliance rule. Also saves one
    LLM round-trip on every guardrail hit.
    """
    violations = state["guardrail_violations"]
    evidence = list(state["evidence"]) + violations + state["policy_citations"]
    return {
        "resolution": "ESCALATE",
        "reason": f"Escalated due to business guardrails: {', '.join(violations)}",
        "evidence": sorted(set(evidence)),
    }


async def generate_response_node(state: AgentState, db: Any) -> dict[str, Any]:
    """Generate the final resolution payload with the LLM (no violations path)."""
    provider = get_llm_provider()
    prompt = (
        f"Ticket History:\n{_history(state)}\n\n"
        f"Classification: {_classification_json(state)}\n"
        f"Executed Tools and Outputs:\n{json.dumps(state['tool_outputs'])}\n\n"
        f"Retrieved Policy Citations: {json.dumps(state['policy_citations'])}\n\n"
        "Determine the final resolution outcome: RESOLVED if the facts support "
        "resolving the ticket, otherwise ESCALATE."
    )
    decision, in_tokens, out_tokens = await provider.generate_structured(
        prompt=prompt,
        response_model=LLMResolution,
        system_instruction=(
            "You are a customer operations response generator. Emit final resolution JSON."
        ),
    )
    resolution = (
        decision.resolution if decision.resolution in ("RESOLVED", "ESCALATE") else "ESCALATE"
    )
    return {
        "resolution": resolution,
        "reason": decision.reason,
        "evidence": sorted(set(decision.evidence)),
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
    }


# --------------------------------------------------------------------------
# 4. Graph construction
# --------------------------------------------------------------------------
def route_after_guardrails(state: AgentState) -> str:
    """Conditional edge: violations bypass the LLM and escalate deterministically."""
    return "finalize_escalation" if state["guardrail_violations"] else "generate_response"


def _audited(node_fn: Any, step_name: str, step_type: str) -> Any:
    """Wrap a node so each execution is recorded as an agent_steps row."""

    async def wrapper(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        db = config["configurable"]["db"]
        step_rec = AgentStep(
            agent_run_id=state["run_id"],
            step_name=step_name,
            step_type=step_type,
            status="RUNNING",
            started_at=datetime.datetime.now(datetime.UTC),
        )
        db.add(step_rec)
        await db.flush()
        try:
            result = await node_fn(state, db)
            step_rec.status = "COMPLETED"
            return result
        except Exception:
            step_rec.status = "FAILED"
            raise
        finally:
            step_rec.completed_at = datetime.datetime.now(datetime.UTC)

    return wrapper


def build_agent_graph() -> Any:
    """Compile the ResolveAI LangGraph StateGraph with an in-memory checkpointer."""
    graph = StateGraph(AgentState)

    graph.add_node("classify", _audited(classify_node, "classify", "CLASSIFY"))
    graph.add_node("plan", _audited(plan_node, "plan", "PLAN"))
    graph.add_node("execute_tools", _audited(execute_tools_node, "execute_tools", "TOOL_EXEC"))
    graph.add_node("guardrails", _audited(guardrails_node, "guardrails", "GUARDRAIL"))
    graph.add_node(
        "generate_response",
        _audited(generate_response_node, "generate_response", "RESPONSE"),
    )
    graph.add_node(
        "finalize_escalation",
        _audited(finalize_escalation_node, "finalize_escalation", "FORCED_ESCALATION"),
    )

    graph.set_entry_point("classify")
    graph.add_edge("classify", "plan")
    graph.add_edge("plan", "execute_tools")
    graph.add_edge("execute_tools", "guardrails")
    graph.add_conditional_edges(
        "guardrails",
        route_after_guardrails,
        {"finalize_escalation": "finalize_escalation", "generate_response": "generate_response"},
    )
    graph.add_edge("generate_response", END)
    graph.add_edge("finalize_escalation", END)

    return graph.compile(checkpointer=MemorySaver())


_compiled_graph: Any = None


def get_agent_graph() -> Any:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_agent_graph()
    return _compiled_graph


# --------------------------------------------------------------------------
# 5. Runner: fetch ticket, invoke graph, persist run summary
# --------------------------------------------------------------------------
async def run_agent(ticket_id: str, db: Any) -> dict[str, Any]:
    """Execute the agent graph for a ticket, logging runs/steps/tools/decisions."""
    start_time = time.perf_counter()
    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"

    ticket = (await db.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one_or_none()
    if not ticket:
        raise ValueError(f"Ticket {ticket_id} not found.")

    msgs = (
        (
            await db.execute(
                select(TicketMessage)
                .where(TicketMessage.ticket_id == ticket_id)
                .order_by(TicketMessage.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    provider = get_llm_provider()
    agent_run = AgentRun(
        id=run_id,
        ticket_id=ticket_id,
        model_provider="fake" if settings.USE_FAKE_LLM else settings.DEFAULT_PROVIDER,
        model_name=provider.model_name,
        prompt_version="v1.0",
        status="PENDING",
        started_at=datetime.datetime.now(datetime.UTC),
        input_tokens=0,
        output_tokens=0,
        estimated_cost=Decimal("0.0"),
        latency_ms=0,
    )
    db.add(agent_run)
    await db.flush()

    initial_state: AgentState = {
        "ticket_id": ticket_id,
        "run_id": run_id,
        "customer_id": ticket.customer_id,
        "messages": [{"role": m.sender, "content": m.body} for m in msgs],
        "classification": None,
        "plan": None,
        "tool_outputs": [],
        "policy_citations": [],
        "guardrail_violations": [],
        "resolution": None,
        "reason": None,
        "evidence": [],
        "actions_taken": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost": Decimal("0.0"),
        "latency_ms": 0,
    }

    graph = get_agent_graph()
    try:
        final_state: AgentState = await graph.ainvoke(
            initial_state,
            config={"configurable": {"db": db, "thread_id": run_id}},
        )
        agent_run.status = "COMPLETED"
    except Exception:
        agent_run.status = "FAILED"
        agent_run.completed_at = datetime.datetime.now(datetime.UTC)
        await db.flush()
        raise

    cost = estimate_cost(
        provider.model_name, final_state["input_tokens"], final_state["output_tokens"]
    )
    latency = int((time.perf_counter() - start_time) * 1000)

    agent_run.completed_at = datetime.datetime.now(datetime.UTC)
    agent_run.input_tokens = final_state["input_tokens"]
    agent_run.output_tokens = final_state["output_tokens"]
    agent_run.estimated_cost = cost
    agent_run.latency_ms = latency

    if final_state["classification"]:
        ticket.category = final_state["classification"].category.value
        ticket.severity = final_state["classification"].severity.value
        ticket.intent = final_state["classification"].intent
    ticket.status = final_state["resolution"] or "OPEN"

    db.add(
        AgentDecision(
            agent_run_id=run_id,
            resolution=final_state["resolution"] or "ESCALATE",
            reason=final_state["reason"] or "Escalation requested",
            evidence_json=json.dumps(final_state["evidence"]),
            actions_taken_json=json.dumps(final_state["actions_taken"]),
            created_at=datetime.datetime.now(datetime.UTC),
        )
    )
    await db.flush()

    return {
        "run_id": run_id,
        "ticket_id": ticket_id,
        "classification": (
            final_state["classification"].model_dump() if final_state["classification"] else None
        ),
        "resolution": final_state["resolution"],
        "reason": final_state["reason"],
        "evidence": final_state["evidence"],
        "actions_taken": final_state["actions_taken"],
        "cost": float(cost),
        "latency_ms": latency,
    }
