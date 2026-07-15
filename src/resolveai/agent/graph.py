import datetime
import json
import logging
import time
import uuid
from decimal import Decimal
from typing import Any, Literal, TypedDict
from pydantic import BaseModel, Field
from sqlalchemy import select

from resolveai.core.config import settings
from resolveai.core.llm_provider import get_llm_provider
from resolveai.models.models import (
    AgentDecision,
    AgentRun,
    AgentStep,
    Customer,
    Order,
    Payment,
    Policy,
    PolicyChunk,
    Shipment,
    Ticket,
    TicketMessage,
    ToolCall,
)
from resolveai.agent.tools import (
    get_customer,
    get_order,
    get_payment,
    get_shipment,
    search_policy,
    create_refund_request,
    create_escalation,
)

logger = logging.getLogger(__name__)


# 1. Pydantic schemas for LLM communication
class TicketClassification(BaseModel):
    category: str = Field(description="Category of the ticket: PAYMENT_ISSUE, DELIVERY_DISPUTE, ACCOUNT_ACCESS, SUBSCRIPTION_CHANGE, POLICY_VIOLATION, AMBIGUOUS")
    severity: str = Field(description="Severity level: LOW, MEDIUM, HIGH, CRITICAL")
    intent: str = Field(description="Primary intent, e.g. REPORT_MISSING_DELIVERY, CHARGE_DISPUTE, RESET_PASSWORD, CANCEL_SUBSCRIPTION")
    requires_account_data: bool = Field(description="Whether account data lookup is needed")


class AgentPlan(BaseModel):
    steps: list[str] = Field(description="Sequential plan steps to resolve the issue")


class LLMToolDecision(BaseModel):
    tool_name: Literal["get_customer", "get_order", "get_payment", "get_shipment", "search_policy", "create_refund_request", "create_escalation", "DONE"] = Field(
        description="Name of the tool to execute or 'DONE' if resolution is ready"
    )
    tool_input: dict[str, Any] = Field(
        default={},
        description="Dictionary of inputs for the tool. E.g. {'customer_id': 'CUS-10293'} or {'query': 'refund policy'}"
    )


class LLMResolution(BaseModel):
    resolution: Literal["RESOLVED", "ESCALATE"] = Field(description="Final outcome")
    reason: str = Field(description="Explanation of the final outcome")
    evidence: list[str] = Field(description="Policy and data points supporting this decision")
    actions_taken: list[str] = Field(description="Action summaries performed")


# 2. Define Agent State Schema
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
    input_tokens: int
    output_tokens: int
    estimated_cost: Decimal
    latency_ms: int


# 3. LangGraph Nodes
async def classify_node(state: AgentState, db: Any) -> dict[str, Any]:
    """Classifies the ticket intent, category, and severity."""
    provider = get_llm_provider()
    
    # Compile history
    history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in state["messages"]])
    prompt = f"Analyze the following support ticket and classify it:\n\n{history}"
    
    system_instruction = "You are an expert customer operations classifier. Categorize tickets with high precision."
    
    classification, in_tokens, out_tokens = await provider.generate_structured(
        prompt=prompt,
        response_model=TicketClassification,
        system_instruction=system_instruction,
    )
    
    # Try to extract customer_id if present in message
    customer_id = state["customer_id"]
    if not customer_id:
        for msg in state["messages"]:
            content = msg["content"]
            # Look for CUS-XXXXX pattern
            import re
            match = re.search(r"CUS-\d+", content)
            if match:
                customer_id = match.group(0)
                break

    return {
        "classification": classification,
        "customer_id": customer_id,
        "input_tokens": state["input_tokens"] + in_tokens,
        "output_tokens": state["output_tokens"] + out_tokens,
    }


async def plan_node(state: AgentState, db: Any) -> dict[str, Any]:
    """Generates a sequential resolution plan."""
    if not state["classification"]:
        return {"plan": []}
        
    provider = get_llm_provider()
    history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in state["messages"]])
    classification_str = json.dumps(state["classification"].model_dump())
    
    prompt = (
        f"Support Ticket History:\n{history}\n\n"
        f"Classification:\n{classification_str}\n\n"
        f"Create a step-by-step resolution plan using tools. Focus on correctness and policy adherence."
    )
    
    system_instruction = "You are a customer operations planner. Output a structured JSON plan list."
    
    plan_resp, in_tokens, out_tokens = await provider.generate_structured(
        prompt=prompt,
        response_model=AgentPlan,
        system_instruction=system_instruction,
    )
    
    return {
        "plan": plan_resp.steps,
        "input_tokens": state["input_tokens"] + in_tokens,
        "output_tokens": state["output_tokens"] + out_tokens,
    }


async def execute_tools_node(state: AgentState, db: Any) -> dict[str, Any]:
    """Executes a loop of tool calling guided by the LLM."""
    provider = get_llm_provider()
    
    tool_outputs = list(state["tool_outputs"])
    policy_citations = list(state["policy_citations"])
    actions_taken = list(state["actions_taken"])
    
    input_tokens = state["input_tokens"]
    output_tokens = state["output_tokens"]
    
    max_loops = 5
    loop_count = 0
    
    while loop_count < max_loops:
        loop_count += 1
        
        # Compile current environment state
        history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in state["messages"]])
        class_json = json.dumps(state["classification"].model_dump()) if state["classification"] else "{}"
        plan_json = json.dumps(state["plan"])
        outputs_json = json.dumps(tool_outputs)
        
        prompt = (
            f"Ticket History:\n{history}\n\n"
            f"Classification: {class_json}\n"
            f"Plan: {plan_json}\n\n"
            f"Current Executed Tools and Outputs:\n{outputs_json}\n\n"
            f"Identify the next tool to execute. If you have all facts to resolve or escalate, return 'DONE'.\n"
            f"Available customer ID: {state['customer_id']}"
        )
        
        system_instruction = (
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
        
        decision, in_tokens, out_tokens = await provider.generate_structured(
            prompt=prompt,
            response_model=LLMToolDecision,
            system_instruction=system_instruction,
        )
        
        input_tokens += in_tokens
        output_tokens += out_tokens
        
        if decision.tool_name == "DONE":
            break
            
        # Execute tool
        tool_name = decision.tool_name
        args = decision.tool_input
        tool_start = time.perf_counter()
        
        tool_res = None
        status = "SUCCESS"
        
        try:
            if tool_name == "get_customer":
                cid = args.get("customer_id") or state["customer_id"]
                if not cid:
                    tool_res = {"error": "Missing customer_id argument"}
                    status = "FAILED"
                else:
                    tool_res = await get_customer(db, cid)
            elif tool_name == "get_order":
                oid = args.get("order_id")
                if not oid:
                    tool_res = {"error": "Missing order_id"}
                    status = "FAILED"
                else:
                    tool_res = await get_order(db, oid)
            elif tool_name == "get_payment":
                pid = args.get("payment_id") or args.get("order_id")
                if not pid:
                    tool_res = {"error": "Missing payment_id or order_id"}
                    status = "FAILED"
                else:
                    tool_res = await get_payment(db, pid)
            elif tool_name == "get_shipment":
                oid = args.get("order_id")
                if not oid:
                    tool_res = {"error": "Missing order_id"}
                    status = "FAILED"
                else:
                    tool_res = await get_shipment(db, oid)
            elif tool_name == "search_policy":
                q = args.get("query")
                if not q:
                    tool_res = {"error": "Missing query"}
                    status = "FAILED"
                else:
                    tool_res = await search_policy(db, q)
                    if "citations" in tool_res:
                        policy_citations.extend(tool_res["citations"])
            elif tool_name == "create_refund_request":
                oid = args.get("order_id")
                amt = float(args.get("amount", 0.0))
                r = args.get("reason", "Customer request")
                if not oid or amt <= 0.0:
                    tool_res = {"error": "Missing order_id or valid amount"}
                    status = "FAILED"
                else:
                    tool_res = await create_refund_request(db, oid, amt, r)
                    actions_taken.append(f"Created refund request for {oid} (Amount: {amt})")
            elif tool_name == "create_escalation":
                qname = args.get("queue_name", "general")
                r = args.get("reason", "Agent escalation")
                tool_res = await create_escalation(db, state["ticket_id"], state["run_id"], qname, r)
                actions_taken.append(f"Created escalation {tool_res.get('escalation_id')}")
            else:
                tool_res = {"error": "Unknown tool"}
                status = "FAILED"
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            tool_res = {"error": str(e)}
            status = "FAILED"
            
        tool_latency = int((time.perf_counter() - tool_start) * 1000)
        
        # Audit tool call in Postgres
        tool_call_rec = ToolCall(
            id=f"TLC-{uuid.uuid4().hex[:6].upper()}",
            agent_run_id=state["run_id"],
            tool_name=tool_name,
            input_json=json.dumps(args),
            output_json=json.dumps(tool_res),
            status=status,
            latency_ms=tool_latency,
            created_at=datetime.datetime.utcnow(),
        )
        db.add(tool_call_rec)
        
        tool_outputs.append({
            "tool": tool_name,
            "input": args,
            "output": tool_res,
            "status": status
        })
        
    return {
        "tool_outputs": tool_outputs,
        "policy_citations": list(set(policy_citations)),
        "actions_taken": actions_taken,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


async def guardrails_node(state: AgentState, db: Any) -> dict[str, Any]:
    """Applies deterministic compliance rules and logs violations."""
    violations = []
    actions_taken = list(state["actions_taken"])
    
    # 1. Inspect tool outputs for refund actions
    refund_amount = 0.0
    refund_order_id = None
    
    for out in state["tool_outputs"]:
        if out["tool"] == "create_refund_request" and out["status"] == "SUCCESS":
            refund_amount = float(out["input"].get("amount", 0.0))
            refund_order_id = out["input"].get("order_id")
            
    # Rule 1: High value auto-refund ceiling
    if refund_amount > 50000.0:
        violations.append(f"Auto-refund of ₹{refund_amount} exceeds maximum allowed auto-approval limit of ₹50,000.")
        
    # Rule 2: High value delivery dispute with missing proof of delivery
    # Look for shipment details in tools
    is_delivery_dispute = state["classification"] and state["classification"].category == "DELIVERY_DISPUTE"
    if is_delivery_dispute:
        for out in state["tool_outputs"]:
            if out["tool"] == "get_shipment" and out["status"] == "SUCCESS":
                shipment_data = out["output"]
                proof = shipment_data.get("proof_of_delivery", "Missing")
                sig = shipment_data.get("signature_captured", False)
                
                # Fetch order value
                order_val = 0.0
                for out_order in state["tool_outputs"]:
                    if out_order["tool"] == "get_order" and out_order["status"] == "SUCCESS":
                        order_val = float(out_order["output"].get("total_amount", 0.0))
                        
                if order_val > 50000.0 and (proof == "Missing" or not sig):
                    violations.append(
                        f"Order value is ₹{order_val} (> ₹50,000) and proof of delivery is missing or signature was not captured. "
                        "POL-DELIVERY-04 requires manual logistics investigation."
                    )
                    
    # Override actions if violations exist
    if violations:
        logger.warning(f"Guardrail violations triggered: {violations}")
        # If we already created a refund request, we should escalate immediately
        # Find if escalation was already created in tools
        has_escalated = any(out["tool"] == "create_escalation" for out in state["tool_outputs"])
        if not has_escalated:
            # Force escalation
            reason = " | ".join(violations)
            esc_res = await create_escalation(db, state["ticket_id"], state["run_id"], "Logistics Investigation Team", reason)
            actions_taken.append(f"Created escalation {esc_res.get('escalation_id')} due to guardrail violations.")
            
    return {
        "guardrail_violations": violations,
        "actions_taken": actions_taken,
    }


async def generate_response_node(state: AgentState, db: Any) -> dict[str, Any]:
    """Generates the final response and resolution payload."""
    provider = get_llm_provider()
    
    history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in state["messages"]])
    class_json = json.dumps(state["classification"].model_dump()) if state["classification"] else "{}"
    outputs_json = json.dumps(state["tool_outputs"])
    violations_json = json.dumps(state["guardrail_violations"])
    citations_json = json.dumps(state["policy_citations"])
    
    prompt = (
        f"Ticket History:\n{history}\n\n"
        f"Classification: {class_json}\n"
        f"Executed Tools and Outputs:\n{outputs_json}\n\n"
        f"Guardrail Violations: {violations_json}\n"
        f"Retrieved Policy Citations: {citations_json}\n\n"
        f"Determine the final resolution outcome. If a guardrail violation is present, you MUST choose ESCALATE. "
        f"Otherwise, determine if the ticket can be RESOLVED or needs to be ESCALATED based on facts."
    )
    
    system_instruction = "You are a customer operations response generator. Emit final resolution JSON."
    
    decision, in_tokens, out_tokens = await provider.generate_structured(
        prompt=prompt,
        response_model=LLMResolution,
        system_instruction=system_instruction,
    )
    
    # If guardrails triggered, force ESCALATE
    resolution_val = decision.resolution
    reason_val = decision.reason
    evidence_val = list(decision.evidence)
    
    if state["guardrail_violations"]:
        resolution_val = "ESCALATE"
        reason_val = f"Escalated due to business guardrails: {', '.join(state['guardrail_violations'])}"
        evidence_val.extend(state["guardrail_violations"])
        evidence_val.extend(state["policy_citations"])
        
    return {
        "resolution": resolution_val,
        "reason": reason_val,
        "evidence": list(set(evidence_val)),
        "input_tokens": state["input_tokens"] + in_tokens,
        "output_tokens": state["output_tokens"] + out_tokens,
    }


# 4. Main Run Agent Runner
async def run_agent(ticket_id: str, db: Any) -> dict[str, Any]:
    """Fetches a ticket, executes the LangGraph workflow, logs all runs, steps, and decisions to DB."""
    start_time = time.perf_counter()
    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    
    # 1. Fetch ticket and messages
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise ValueError(f"Ticket {ticket_id} not found.")
        
    stmt_msgs = select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at.asc())
    msg_result = await db.execute(stmt_msgs)
    msgs = msg_result.scalars().all()
    
    messages_payload = [{"role": msg.sender, "content": msg.body} for msg in msgs]
    
    # Initialize run record in DB
    agent_run = AgentRun(
        id=run_id,
        ticket_id=ticket_id,
        model_provider=settings.DEFAULT_PROVIDER,
        model_name=settings.OPENAI_MODEL_NAME if settings.DEFAULT_PROVIDER == "openai" else settings.GEMINI_MODEL_NAME,
        prompt_version="v1.0",
        status="PENDING",
        started_at=datetime.datetime.utcnow(),
        input_tokens=0,
        output_tokens=0,
        estimated_cost=Decimal("0.0"),
        latency_ms=0,
    )
    db.add(agent_run)
    await db.flush() # Send to DB to retrieve relations and link FKs
    
    # Initialize State
    state = AgentState(
        ticket_id=ticket_id,
        run_id=run_id,
        customer_id=ticket.customer_id,
        messages=messages_payload,
        classification=None,
        plan=None,
        tool_outputs=[],
        policy_citations=[],
        guardrail_violations=[],
        resolution=None,
        reason=None,
        evidence=[],
        actions_taken=[],
        input_tokens=0,
        output_tokens=0,
        estimated_cost=Decimal("0.0"),
        latency_ms=0,
    )
    
    # List of steps to run sequentially (mirroring the graph structure)
    steps = [
        ("classify", "CLASSIFY", classify_node),
        ("plan", "PLAN", plan_node),
        ("execute_tools", "TOOL_EXEC", execute_tools_node),
        ("guardrails", "GUARDRAIL", guardrails_node),
        ("generate_response", "RESPONSE", generate_response_node)
    ]
    
    # Run steps sequentially
    for step_name, step_type, node_fn in steps:
        step_start = time.perf_counter()
        
        step_rec = AgentStep(
            agent_run_id=run_id,
            step_name=step_name,
            step_type=step_type,
            status="RUNNING",
            started_at=datetime.datetime.utcnow(),
        )
        db.add(step_rec)
        await db.flush()
        
        try:
            node_output = await node_fn(state, db)
            state.update(node_output) # type: ignore
            step_rec.status = "COMPLETED"
        except Exception as e:
            logger.error(f"Step {step_name} failed: {e}")
            step_rec.status = "FAILED"
            raise e
        finally:
            step_rec.completed_at = datetime.datetime.utcnow()
            
    # Calculate costs (rough estimation based on GPT-4o-mini rates)
    # $0.150 / 1M input tokens, $0.600 / 1M output tokens
    cost = Decimal(state["input_tokens"]) * Decimal("0.00000015") + Decimal(state["output_tokens"]) * Decimal("0.00000060")
    
    latency = int((time.perf_counter() - start_time) * 1000)
    
    # Update Run Record
    agent_run.status = "COMPLETED"
    agent_run.completed_at = datetime.datetime.utcnow()
    agent_run.input_tokens = state["input_tokens"]
    agent_run.output_tokens = state["output_tokens"]
    agent_run.estimated_cost = cost
    agent_run.latency_ms = latency
    
    # Update Ticket Category & Severity in DB
    if state["classification"]:
        ticket.category = state["classification"].category
        ticket.severity = state["classification"].severity
        ticket.intent = state["classification"].intent
        
    ticket.status = state["resolution"] or "OPEN"
    
    # Insert Decision Record
    decision_rec = AgentDecision(
        agent_run_id=run_id,
        resolution=state["resolution"] or "ESCALATE",
        reason=state["reason"] or "Escalation requested",
        evidence_json=json.dumps(state["evidence"]),
        actions_taken_json=json.dumps(state["actions_taken"]),
        created_at=datetime.datetime.utcnow(),
    )
    db.add(decision_rec)
    
    await db.flush()
    
    return {
        "run_id": run_id,
        "ticket_id": ticket_id,
        "classification": state["classification"].model_dump() if state["classification"] else None,
        "resolution": state["resolution"],
        "reason": state["reason"],
        "evidence": state["evidence"],
        "actions_taken": state["actions_taken"],
        "cost": float(cost),
        "latency_ms": latency,
    }
