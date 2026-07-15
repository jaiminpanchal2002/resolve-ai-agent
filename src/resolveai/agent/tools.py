import json
import logging
from decimal import Decimal
from typing import Any
from sqlalchemy import select

from resolveai.models.models import (
    Customer,
    Escalation,
    Order,
    Payment,
    Policy,
    PolicyChunk,
    Shipment,
    Ticket,
)
from resolveai.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)


# 1. Fetch Customer
async def get_customer(db: Any, customer_id: str) -> dict[str, Any]:
    """Fetch customer profile from database."""
    stmt = select(Customer).where(Customer.id == customer_id)
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()
    
    if not customer:
        return {"error": f"Customer {customer_id} not found"}
        
    return {
        "customer_id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "created_at": customer.created_at.isoformat(),
    }


# 2. Fetch Order
async def get_order(db: Any, order_id: str) -> dict[str, Any]:
    """Fetch order details from database."""
    stmt = select(Order).where(Order.id == order_id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    
    if not order:
        return {"error": f"Order {order_id} not found"}
        
    return {
        "order_id": order.id,
        "customer_id": order.customer_id,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "currency": order.currency,
        "created_at": order.created_at.isoformat(),
    }


# 3. Fetch Payment
async def get_payment(db: Any, payment_id: str) -> dict[str, Any]:
    """Fetch payment status from database."""
    stmt = select(Payment).where(Payment.id == payment_id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        # Fallback: maybe they passed order_id instead of payment_id
        stmt_fallback = select(Payment).where(Payment.order_id == payment_id)
        result_fallback = await db.execute(stmt_fallback)
        payment = result_fallback.scalar_one_or_none()
        
    if not payment:
        return {"error": f"Payment {payment_id} not found"}
        
    return {
        "payment_id": payment.id,
        "order_id": payment.order_id,
        "status": payment.status,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "provider": payment.provider,
        "created_at": payment.created_at.isoformat(),
    }


# 4. Fetch Shipment
async def get_shipment(db: Any, order_id: str) -> dict[str, Any]:
    """Fetch shipment status and tracking details for an order."""
    stmt = select(Shipment).where(Shipment.order_id == order_id)
    result = await db.execute(stmt)
    shipment = result.scalar_one_or_none()
    
    if not shipment:
        return {"error": f"No shipment found for order {order_id}"}
        
    return {
        "shipment_id": shipment.id,
        "order_id": shipment.order_id,
        "status": shipment.status,
        "carrier": shipment.carrier,
        "tracking_number": shipment.tracking_number,
        "proof_of_delivery": shipment.proof_of_delivery_url or "Missing",
        "signature_captured": shipment.signature_captured,
        "created_at": shipment.created_at.isoformat(),
    }


# 5. Search Policy (Hybrid RAG)
async def search_policy(db: Any, query: str, category_filter: str | None = None) -> dict[str, Any]:
    """Search company policy guidelines using hybrid retrieval (RRF + Cross-Encoder)."""
    retrieval_service = RetrievalService(db)
    results = await retrieval_service.retrieve_hybrid_reranked(
        query=query, limit=3, category_filter=category_filter
    )
    
    citations = []
    chunks_data = []
    for chunk, policy, score in results:
        citations.append(policy.id)
        chunks_data.append({
            "policy_id": policy.id,
            "title": policy.title,
            "content": chunk.content,
            "score": score
        })
        
    return {
        "query": query,
        "results": chunks_data,
        "citations": list(set(citations))
    }


# 6. Create Refund Request
async def create_refund_request(db: Any, order_id: str, amount: float, reason: str) -> dict[str, Any]:
    """Initiates a refund request for an order."""
    # First verify if order exists
    stmt = select(Order).where(Order.id == order_id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    
    if not order:
        return {"error": f"Cannot refund: Order {order_id} not found"}
        
    # In a real system we would communicate with Stripe/Razorpay and record refund.
    # We update payments related to this order to "REFUNDED" status.
    stmt_payment = select(Payment).where(Payment.order_id == order_id)
    payment_result = await db.execute(stmt_payment)
    payments = payment_result.scalars().all()
    
    refunded_payment_ids = []
    for pay in payments:
        pay.status = "REFUNDED"
        refunded_payment_ids.append(pay.id)
        
    # We update the order status
    order.status = "REFUNDED"
    
    return {
        "status": "SUCCESS",
        "order_id": order_id,
        "amount": amount,
        "refunded_payments": refunded_payment_ids,
        "message": f"Refund request of {amount} for order {order_id} recorded successfully."
    }


# 7. Create Escalation
async def create_escalation(
    db: Any, ticket_id: str, agent_run_id: str, queue_name: str, reason: str
) -> dict[str, Any]:
    """Escalates a ticket to a specialized human queue."""
    # Ensure unique escalation ID
    import uuid
    esc_id = f"ESC-{uuid.uuid4().hex[:6].upper()}"
    
    escalation = Escalation(
        id=esc_id,
        ticket_id=ticket_id,
        agent_run_id=agent_run_id,
        status="PENDING",
        queue_name=queue_name,
        escalation_reason=reason,
    )
    db.add(escalation)
    
    # Update ticket status to ESCALATED
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    ticket_result = await db.execute(stmt)
    ticket = ticket_result.scalar_one_or_none()
    if ticket and isinstance(ticket, Ticket):
        ticket.status = "ESCALATED"
        
    return {
        "escalation_id": esc_id,
        "ticket_id": ticket_id,
        "queue_name": queue_name,
        "status": "PENDING",
        "reason": reason
    }
