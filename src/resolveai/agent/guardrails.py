"""Deterministic policy guardrails.

Guardrails are plain Python rules, NOT prompt instructions: an LLM cannot
be trusted to police itself, so compliance limits are enforced in code
after tool execution and before the final response is generated.
"""

import logging
from typing import Any

from resolveai.agent.tools import create_escalation

logger = logging.getLogger(__name__)

AUTO_REFUND_LIMIT_INR = 50_000.0
HIGH_VALUE_ORDER_LIMIT_INR = 50_000.0


def check_refund_limit(tool_outputs: list[dict[str, Any]]) -> list[str]:
    """Rule 1: refunds above the auto-approval ceiling require a human."""
    violations: list[str] = []
    for out in tool_outputs:
        if out["tool"] == "create_refund_request" and out["status"] == "SUCCESS":
            amount = float(out["input"].get("amount", 0.0))
            if amount > AUTO_REFUND_LIMIT_INR:
                violations.append(
                    f"Auto-refund of ₹{amount} exceeds maximum allowed "
                    f"auto-approval limit of ₹{AUTO_REFUND_LIMIT_INR:,.0f}."
                )
    return violations


def check_delivery_proof(
    tool_outputs: list[dict[str, Any]], is_delivery_dispute: bool
) -> list[str]:
    """Rule 2: high-value delivery disputes need proof of delivery."""
    if not is_delivery_dispute:
        return []

    violations: list[str] = []
    order_val = 0.0
    for out in tool_outputs:
        if out["tool"] == "get_order" and out["status"] == "SUCCESS":
            order_val = float(out["output"].get("total_amount", 0.0))

    for out in tool_outputs:
        if out["tool"] == "get_shipment" and out["status"] == "SUCCESS":
            shipment = out["output"]
            proof = shipment.get("proof_of_delivery", "Missing")
            sig = shipment.get("signature_captured", False)
            if order_val > HIGH_VALUE_ORDER_LIMIT_INR and (proof == "Missing" or not sig):
                violations.append(
                    f"Order value is ₹{order_val} (> ₹{HIGH_VALUE_ORDER_LIMIT_INR:,.0f}) "
                    "and proof of delivery is missing or signature was not captured. "
                    "POL-DELIVERY-04 requires manual logistics investigation."
                )
    return violations


async def guardrails_node(state: dict[str, Any], db: Any) -> dict[str, Any]:
    """Apply all deterministic compliance rules; escalate on violation."""
    actions_taken = list(state["actions_taken"])

    classification = state.get("classification")
    is_delivery_dispute = bool(
        classification and getattr(classification, "category", None) == "DELIVERY_DISPUTE"
    )

    violations = check_refund_limit(state["tool_outputs"])
    violations += check_delivery_proof(state["tool_outputs"], is_delivery_dispute)

    if violations:
        logger.warning("Guardrail violations triggered: %s", violations)
        has_escalated = any(out["tool"] == "create_escalation" for out in state["tool_outputs"])
        if not has_escalated:
            reason = " | ".join(violations)
            esc_res = await create_escalation(
                db,
                state["ticket_id"],
                state["run_id"],
                "Logistics Investigation Team",
                reason,
            )
            actions_taken.append(
                f"Created escalation {esc_res.get('escalation_id')} due to guardrail violations."
            )

    return {"guardrail_violations": violations, "actions_taken": actions_taken}
