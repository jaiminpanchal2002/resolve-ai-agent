"""Run the offline evaluation suite against the committed dataset.

Usage:
    python scripts/run_evaluation.py            # real LLM (needs API key in .env)
    USE_FAKE_LLM=true python scripts/run_evaluation.py   # deterministic dry run

Loads scripts/eval_cases.json into the evaluation tables (idempotent by
dataset name), executes the agent graph for every case, and stores per-case
and summary metrics in evaluation_runs / evaluation_results. Prints a
markdown table you can paste into docs/evaluation_report.md — the numbers
in the README must come from this script, never be typed by hand.
"""

import asyncio
import datetime
import json
import statistics
import uuid
from pathlib import Path

from sqlalchemy import select

from resolveai.agent.graph import run_agent
from resolveai.db.session import async_session_factory
from resolveai.models.models import (
    Customer,
    EvaluationCase,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    Ticket,
    TicketMessage,
)

DATASET_PATH = Path(__file__).parent / "eval_cases.json"


async def load_dataset(db) -> EvaluationDataset:
    spec = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    existing = (
        await db.execute(
            select(EvaluationDataset).where(EvaluationDataset.name == spec["dataset_name"])
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    dataset = EvaluationDataset(name=spec["dataset_name"], description=spec["description"])
    db.add(dataset)
    await db.flush()
    for case in spec["cases"]:
        db.add(
            EvaluationCase(
                dataset_id=dataset.id,
                category=case["category"],
                ticket_payload_json=json.dumps(case["ticket_payload"]),
                expected_output_json=json.dumps(case["expected_output"]),
            )
        )
    await db.flush()
    return dataset


async def ensure_customer(db, payload: dict) -> str:
    customer_id = payload.get("customer_id", "CUS-TEST")
    existing = (
        await db.execute(select(Customer).where(Customer.id == customer_id))
    ).scalar_one_or_none()
    if not existing:
        db.add(
            Customer(
                id=customer_id,
                name=payload.get("customer_name", "Eval Customer"),
                email=f"eval_{customer_id.lower()}@example.com",
            )
        )
        await db.flush()
    return customer_id


async def evaluate_case(db, case: EvaluationCase) -> dict:
    payload = json.loads(case.ticket_payload_json)
    expected = json.loads(case.expected_output_json)

    customer_id = await ensure_customer(db, payload)
    ticket_id = f"TKT-EVAL-{uuid.uuid4().hex[:8].upper()}"
    db.add(Ticket(id=ticket_id, customer_id=customer_id, status="OPEN"))
    await db.flush()
    for idx, msg in enumerate(payload.get("messages", [])):
        db.add(
            TicketMessage(
                ticket_id=ticket_id,
                sender=msg["role"],
                body=msg["content"],
                created_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=idx),
            )
        )
    await db.flush()

    actual = await run_agent(ticket_id, db)

    classification = actual.get("classification") or {}
    return {
        "case_id": case.id,
        "agent_run_id": actual["run_id"],
        "actual": actual,
        "resolution_correct": actual.get("resolution") == expected.get("resolution"),
        "category_correct": classification.get("category") == expected.get("category"),
        "latency_ms": actual.get("latency_ms", 0),
        "cost": actual.get("cost", 0.0),
    }


async def main() -> None:
    async with async_session_factory() as db:
        dataset = await load_dataset(db)
        cases = (
            (
                await db.execute(
                    select(EvaluationCase).where(EvaluationCase.dataset_id == dataset.id)
                )
            )
            .scalars()
            .all()
        )

        from resolveai.core.llm_provider import get_llm_provider

        eval_run = EvaluationRun(dataset_id=dataset.id, model_name=get_llm_provider().model_name)
        db.add(eval_run)
        await db.flush()

        rows = []
        for case in cases:
            row = await evaluate_case(db, case)
            rows.append(row)
            db.add(
                EvaluationResult(
                    evaluation_run_id=eval_run.id,
                    case_id=row["case_id"],
                    agent_run_id=row["agent_run_id"],
                    actual_output_json=json.dumps(row["actual"]),
                    metrics_json=json.dumps(
                        {
                            "resolution_correct": row["resolution_correct"],
                            "category_correct": row["category_correct"],
                            "latency_ms": row["latency_ms"],
                            "cost": row["cost"],
                        }
                    ),
                )
            )

        n = len(rows)
        summary = {
            "cases": n,
            "resolution_accuracy": sum(r["resolution_correct"] for r in rows) / n,
            "category_accuracy": sum(r["category_correct"] for r in rows) / n,
            "avg_latency_ms": statistics.mean(r["latency_ms"] for r in rows),
            "avg_cost_usd": statistics.mean(r["cost"] for r in rows),
            "model": eval_run.model_name,
        }
        eval_run.summary_metrics_json = json.dumps(summary)
        eval_run.completed_at = datetime.datetime.now(datetime.UTC)
        await db.commit()

        print(f"\nEvaluation run #{eval_run.id} — model: {summary['model']} — {n} cases\n")
        print("| Metric | Value |")
        print("| :--- | :--- |")
        print(f"| Resolution Accuracy | {summary['resolution_accuracy']:.1%} |")
        print(f"| Category Accuracy | {summary['category_accuracy']:.1%} |")
        print(f"| Avg Latency per Ticket | {summary['avg_latency_ms']:.0f} ms |")
        print(f"| Avg LLM Cost per Ticket | ${summary['avg_cost_usd']:.4f} |")


if __name__ == "__main__":
    asyncio.run(main())
