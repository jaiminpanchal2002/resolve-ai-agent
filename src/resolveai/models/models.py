import datetime
from decimal import Decimal
from typing import Any
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from resolveai.core.config import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="reviewer", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g., "CUS-10293"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket", back_populates="customer", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="customer", cascade="all, delete-orphan"
    )


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g., "TKT-29384"
    customer_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("customers.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="OPEN", nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Human Review Fields
    human_review_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "APPROVED", "REJECTED", "EDITED"
    human_review_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_reviewed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="tickets")
    messages: Mapped[list["TicketMessage"]] = relationship(
        "TicketMessage", back_populates="ticket", cascade="all, delete-orphan"
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun", back_populates="ticket", cascade="all, delete-orphan"
    )
    escalations: Mapped[list["Escalation"]] = relationship(
        "Escalation", back_populates="ticket", cascade="all, delete-orphan"
    )


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("tickets.id"), nullable=False
    )
    sender: Mapped[str] = mapped_column(String(50), nullable=False)  # "customer", "agent", "system"
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="messages")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g., "ORD-12345"
    customer_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("customers.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # "DELIVERED", "PROCESSING", "SHIPPED", etc.
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="order", cascade="all, delete-orphan"
    )
    shipments: Mapped[list["Shipment"]] = relationship(
        "Shipment", back_populates="order", cascade="all, delete-orphan"
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g., "PAY-12345"
    order_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("orders.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # "SUCCESS", "FAILED", "REFUNDED", etc.
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "stripe", "razorpay", etc.
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    order: Mapped["Order"] = relationship("Order", back_populates="payments")


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g., "SHP-12345"
    order_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("orders.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # "DELIVERED", "IN_TRANSIT", "PENDING"
    carrier: Mapped[str] = mapped_column(String(100), nullable=False)
    tracking_number: Mapped[str] = mapped_column(String(100), nullable=False)
    proof_of_delivery_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signature_captured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    order: Mapped["Order"] = relationship("Order", back_populates="shipments")


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g., "POL-DELIVERY-04"
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    chunks: Mapped[list["PolicyChunk"]] = relationship(
        "PolicyChunk", back_populates="policy", cascade="all, delete-orphan"
    )


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("policies.id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    policy: Mapped["Policy"] = relationship("Policy", back_populates="chunks")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # UUID
    ticket_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("tickets.id"), nullable=False
    )
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.0"), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="agent_runs")
    steps: Mapped[list["AgentStep"]] = relationship(
        "AgentStep", back_populates="agent_run", cascade="all, delete-orphan"
    )
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        "ToolCall", back_populates="agent_run", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["AgentDecision"]] = relationship(
        "AgentDecision", back_populates="agent_run", cascade="all, delete-orphan"
    )
    escalations: Mapped[list["Escalation"]] = relationship(
        "Escalation", back_populates="agent_run", cascade="all, delete-orphan"
    )


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_run_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("agent_runs.id"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    step_type: Mapped[str] = mapped_column(String(100), nullable=False)  # "CLASSIFY", "PLAN", etc.
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="steps")


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # UUID
    agent_run_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("agent_runs.id"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON dump of arguments
    output_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON dump of outputs
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="tool_calls")


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_run_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("agent_runs.id"), nullable=False
    )
    resolution: Mapped[str] = mapped_column(String(50), nullable=False)  # "RESOLVE" or "ESCALATE"
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list of strings
    actions_taken_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list of strings
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="decisions")


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g., "ESC-12345"
    ticket_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("tickets.id"), nullable=False
    )
    agent_run_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("agent_runs.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)  # "PENDING", "RESOLVED"
    queue_name: Mapped[str] = mapped_column(String(100), nullable=False)
    escalation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="escalations")
    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="escalations")


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    cases: Mapped[list["EvaluationCase"]] = relationship(
        "EvaluationCase", back_populates="dataset", cascade="all, delete-orphan"
    )
    runs: Mapped[list["EvaluationRun"]] = relationship(
        "EvaluationRun", back_populates="dataset", cascade="all, delete-orphan"
    )


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evaluation_datasets.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    ticket_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    dataset: Mapped["EvaluationDataset"] = relationship("EvaluationDataset", back_populates="cases")
    results: Mapped[list["EvaluationResult"]] = relationship(
        "EvaluationResult", back_populates="case", cascade="all, delete-orphan"
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evaluation_datasets.id"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    summary_metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset: Mapped["EvaluationDataset"] = relationship("EvaluationDataset", back_populates="runs")
    results: Mapped[list["EvaluationResult"]] = relationship(
        "EvaluationResult", back_populates="evaluation_run", cascade="all, delete-orphan"
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evaluation_runs.id"), nullable=False
    )
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evaluation_cases.id"), nullable=False
    )
    agent_run_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("agent_runs.id"), nullable=True
    )
    actual_output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    evaluation_run: Mapped["EvaluationRun"] = relationship("EvaluationRun", back_populates="results")
    case: Mapped["EvaluationCase"] = relationship("EvaluationCase", back_populates="results")
    agent_run: Mapped["AgentRun"] = relationship()
