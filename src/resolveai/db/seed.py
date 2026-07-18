import datetime
import json
import logging
from decimal import Decimal

from sqlalchemy import select

from resolveai.core.auth import get_password_hash
from resolveai.core.llm_provider import get_llm_provider
from resolveai.db.session import sync_session_factory
from resolveai.models.models import (
    Customer,
    EvaluationCase,
    EvaluationDataset,
    Order,
    Payment,
    Policy,
    PolicyChunk,
    Shipment,
    User,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.db.seed")


def seed_db():
    db = sync_session_factory()
    provider = get_llm_provider()

    try:
        logger.info("Starting database seed...")

        # 1. Seed Users
        stmt = select(User).where(User.email == "admin@resolveai.com")
        if not db.scalar(stmt):
            admin = User(
                email="admin@resolveai.com",
                hashed_password=get_password_hash("admin123"),
                role="admin",
            )
            db.add(admin)
            logger.info("Admin user seeded.")

        # 2. Seed Policies & Policy Chunks
        policies_data = [
            {
                "id": "POL-DELIVERY-04",
                "title": "High-Value Delivery Disputes Policy",
                "category": "logistics",
                "chunks": [
                    "Orders with a value exceeding ₹50,000 (Fifty Thousand Rupees) are categorized as high-value orders.",
                    "If a customer disputes the delivery of a high-value order (e.g. claiming they never received it, despite tracking showing delivered), you MUST inspect the shipment's proof of delivery.",
                    "If the proof of delivery is unavailable OR if the recipient's signature was not captured at the time of delivery, the case MUST be escalated to the logistics investigation team. Do not issue an auto-refund under any circumstances.",
                ],
            },
            {
                "id": "POL-REFUND-01",
                "title": "General Order Refund Guidelines",
                "category": "refunds",
                "chunks": [
                    "Customers can request a refund for eligible orders within 14 days of delivery.",
                    "Auto-refunds can be processed for orders under ₹50,000 if the item was returned in original condition or if shipping was delayed by more than 10 days.",
                    "Refund requests exceeding ₹50,000 are subject to manual compliance reviews and MUST be escalated to the financial operations manager. Auto-refunds for high-value orders are strictly forbidden.",
                ],
            },
            {
                "id": "POL-PAYMENT-02",
                "title": "Duplicate Charge Escalation Policy",
                "category": "payments",
                "chunks": [
                    "When a customer reports being charged twice for a single order, inspect the payments system.",
                    "If two successful transactions exist for the same order ID, flag the second transaction and issue a refund for the duplicate amount immediately.",
                    "If only one successful payment exists and the other is failed/pending, instruct the customer that the deduction is a temporary hold that will clear within 3-5 business days.",
                ],
            },
            {
                "id": "POL-ACCOUNT-05",
                "title": "Account Access Lockout Policy",
                "category": "account",
                "chunks": [
                    "Accounts are locked automatically after 5 failed login attempts for security.",
                    "To unlock an account, the support agent must verify the customer's email address and identity via secondary verification.",
                    "Do not unlock accounts that show suspicious login attempts from multiple geographic locations; escalate these to the security operations center (SOC).",
                ],
            },
        ]

        # Sync code block for embedding generation (blocking since seed script runs offline)
        import asyncio

        loop = asyncio.get_event_loop()

        for p_data in policies_data:
            p_stmt = select(Policy).where(Policy.id == p_data["id"])
            policy = db.scalar(p_stmt)
            if not policy:
                policy = Policy(
                    id=p_data["id"],
                    title=p_data["title"],
                    category=p_data["category"],
                    created_at=datetime.datetime.now(datetime.UTC),
                )
                db.add(policy)
                db.flush()

                for idx, chunk_text in enumerate(p_data["chunks"]):
                    # Generate embedding (runs async helper in sync code)
                    embedding = loop.run_until_complete(provider.get_embedding(chunk_text))

                    chunk = PolicyChunk(
                        policy_id=policy.id,
                        content=chunk_text,
                        embedding=embedding,
                        chunk_index=idx,
                    )
                    db.add(chunk)
                logger.info(f"Seeded policy {policy.id}")

        # 3. Seed Customers, Orders, Payments, Shipments
        customers_data = []
        for i in range(1, 21):
            cid = f"CUS-10{i:03d}"
            cust_stmt = select(Customer).where(Customer.id == cid)
            if not db.scalar(cust_stmt):
                c = Customer(
                    id=cid,
                    name=f"Customer {i}",
                    email=f"customer_{i}@example.com",
                    created_at=datetime.datetime.now(datetime.UTC),
                )
                db.add(c)
                customers_data.append(c)
                db.flush()

                # Seed a default order, payment, and shipment for this customer
                oid = f"ORD-20{i:03d}"
                pid = f"PAY-30{i:03d}"
                shpid = f"SHP-40{i:03d}"

                # Set a high value for order 1 (to test ₹82,000 scenario!)
                is_high_value = i == 1
                amount = Decimal("82000.00") if is_high_value else Decimal("12500.00")

                o = Order(
                    id=oid,
                    customer_id=cid,
                    status="DELIVERED" if i % 2 == 1 else "PROCESSING",
                    total_amount=amount,
                    currency="INR",
                    created_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=5),
                )
                db.add(o)
                db.flush()

                p = Payment(
                    id=pid,
                    order_id=oid,
                    status="SUCCESS",
                    amount=amount,
                    currency="INR",
                    provider="stripe",
                    created_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=5),
                )
                db.add(p)

                s = Shipment(
                    id=shpid,
                    order_id=oid,
                    status="DELIVERED" if i % 2 == 1 else "PENDING",
                    carrier="Delhivery",
                    tracking_number=f"TRK{100000 + i}",
                    proof_of_delivery_url=None
                    if is_high_value
                    else f"https://tracking.carrier.com/proof_{shpid}.jpg",
                    signature_captured=not is_high_value,
                    created_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=5),
                )
                db.add(s)

        # Seed an additional duplicate payment case for customer 2
        # Order 2 has a duplicate payment record
        dup_pid = "PAY-DUP-30002"
        dup_stmt = select(Payment).where(Payment.id == dup_pid)
        if not db.scalar(dup_stmt):
            p_dup = Payment(
                id=dup_pid,
                order_id="ORD-20002",
                status="SUCCESS",
                amount=Decimal("12500.00"),
                currency="INR",
                provider="razorpay",
                created_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=4),
            )
            db.add(p_dup)
            logger.info("Duplicate payment seeded for customer 2.")

        # 4. Seed Evaluation Dataset & 100 Cases
        dataset_stmt = select(EvaluationDataset).where(
            EvaluationDataset.name == "Standard Support Suite"
        )
        dataset = db.scalar(dataset_stmt)
        if not dataset:
            dataset = EvaluationDataset(
                name="Standard Support Suite",
                description="100 synthetic cases testing payments, deliveries, subscription, security, and policies.",
                created_at=datetime.datetime.now(datetime.UTC),
            )
            db.add(dataset)
            db.flush()

            # Generate 100 synthetic cases (10 categories x 10 cases)
            categories = [
                "payment failed",
                "duplicate payment",
                "refund pending",
                "order delayed",
                "delivered but missing",
                "account locked",
                "subscription cancellation",
                "invoice request",
                "policy violation",
                "ambiguous query",
            ]

            # Sample case builder
            case_index = 1
            for cat in categories:
                for k in range(1, 11):
                    # Category-specific details
                    cid = f"CUS-10{k:03d}"
                    oid = f"ORD-20{k:03d}"

                    if cat == "delivered but missing" and k == 1:
                        # Case 1 matches the prompt: high-value missing delivery ₹82,000
                        msg_body = "I ordered a laptop five days ago. The order says delivered, but I never received it."
                        expected = {
                            "intent": "REPORT_MISSING_DELIVERY",
                            "expected_tools": [
                                "get_customer",
                                "get_order",
                                "get_shipment",
                                "search_policy",
                            ],
                            "expected_args": [
                                {"tool": "get_customer", "params": {"customer_id": cid}},
                                {"tool": "get_order", "params": {"order_id": oid}},
                            ],
                            "expected_policies": ["POL-DELIVERY-04"],
                            "resolution": "ESCALATE",
                        }
                    elif cat == "duplicate payment" and k == 2:
                        msg_body = "I was charged twice for order ORD-20002. Both charges went through on my card."
                        expected = {
                            "intent": "REPORT_DUPLICATE_CHARGE",
                            "expected_tools": [
                                "get_payment",
                                "search_policy",
                                "create_refund_request",
                            ],
                            "expected_args": [
                                {"tool": "get_payment", "params": {"payment_id": "ORD-20002"}}
                            ],
                            "expected_policies": ["POL-PAYMENT-02"],
                            "resolution": "RESOLVED",
                        }
                    else:
                        msg_body = f"Query {case_index} regarding {cat} of customer {cid}."
                        expected = {
                            "intent": f"RESOLVE_{cat.replace(' ', '_').upper()}",
                            "expected_tools": ["search_policy"],
                            "expected_args": [],
                            "expected_policies": [],
                            "resolution": "RESOLVED" if k % 2 == 1 else "ESCALATE",
                        }

                    payload = {
                        "customer_id": cid,
                        "customer_name": f"Customer {k}",
                        "messages": [{"role": "customer", "content": msg_body}],
                    }

                    case = EvaluationCase(
                        dataset_id=dataset.id,
                        category=cat,
                        ticket_payload_json=json.dumps(payload),
                        expected_output_json=json.dumps(expected),
                        created_at=datetime.datetime.now(datetime.UTC),
                    )
                    db.add(case)
                    case_index += 1

            logger.info("Seeded 100 evaluation cases.")

        db.commit()
        logger.info("Database seeding completed successfully!")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_db()
