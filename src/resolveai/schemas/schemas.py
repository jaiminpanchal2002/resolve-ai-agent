from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# Auth Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "reviewer"  # reviewer, admin, agent


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


# Ticket Message Schemas
class TicketMessageCreate(BaseModel):
    sender: str  # customer, agent, system
    body: str


class TicketMessageResponse(BaseModel):
    id: int
    sender: str
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


# Ticket Schemas
class TicketCreate(BaseModel):
    customer_id: str
    customer_name: str | None = None
    messages: list[TicketMessageCreate]


class TicketResponse(BaseModel):
    id: str
    customer_id: str
    status: str
    category: str | None = None
    severity: str | None = None
    intent: str | None = None
    human_review_status: str | None = None
    human_review_feedback: str | None = None
    human_reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Human Review Request
class HumanReviewRequest(BaseModel):
    status: str = Field(description="APPROVED, REJECTED, EDITED")
    feedback: str | None = None
    edited_resolution: str | None = None  # RESOLVED or ESCALATE (if EDITED)
    edited_reason: str | None = None


# Dashboard Metrics
class DashboardMetricsResponse(BaseModel):
    resolution_rate: float
    escalation_rate: float
    human_approval_rate: float
    policy_citation_accuracy: float
    average_cost_per_ticket: float
    p95_latency_ms: float
    top_failure_categories: list[dict[str, Any]]


# Evaluation Schemas
class EvaluationRunResponse(BaseModel):
    id: int
    dataset_id: int
    model_name: str
    started_at: datetime
    completed_at: datetime | None = None
    summary_metrics: dict[str, Any] | None = None

    class Config:
        from_attributes = True
