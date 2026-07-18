# ResolveAI — Offline Evaluation Report

**Status: pending a full run against a real LLM provider.**

Every number published here must be produced by `python scripts/run_evaluation.py`
against the committed dataset (`scripts/eval_cases.json`, 15 hand-written cases).
No metric in this project is ever typed by hand.

## How to reproduce

```bash
# 1. Start infrastructure and apply migrations
docker compose up -d postgres redis
alembic upgrade head
make seed

# 2. Run the evaluation (requires OPENAI_API_KEY or GEMINI_API_KEY in .env)
make eval

# Deterministic dry run without any API key:
USE_FAKE_LLM=true make eval
```

## Metrics measured

1. **Resolution Accuracy** — agent's final RESOLVED/ESCALATE decision vs ground truth.
2. **Category Accuracy** — intent classification vs ground truth label.
3. **Guardrail Compliance** — guardrail-trigger cases (refunds > ₹50,000, missing
   proof of delivery on high-value orders) must end in ESCALATE, enforced by
   deterministic code rather than the model.
4. **Latency / Cost** — per-ticket wall-clock latency and token cost estimated
   from the per-model pricing table in `resolveai/core/pricing.py`.

## Retrieval strategies compared

`evaluate_retrieval_performance` in `resolveai/services/retrieval.py` measures
Recall@5, MRR, and latency for three configurations: pure pgvector cosine
similarity, hybrid RRF (semantic + Postgres FTS), and hybrid + cross-encoder
reranking (`ms-marco-MiniLM-L-6-v2`). Results will be published here from a
real run.
