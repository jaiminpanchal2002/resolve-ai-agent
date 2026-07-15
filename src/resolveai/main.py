import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest, Counter, Histogram
from prometheus_client.multiprocess import MultiProcessCollector

from resolveai.core.config import settings
from resolveai.api.endpoints import router as api_router

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI App
app = FastAPI(
    title="ResolveAI API",
    description="Evaluation-Driven Customer Operations Agent Backend",
    version="0.1.0",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus Metrics Setup
registry = CollectorRegistry()
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP Requests",
    ["method", "endpoint", "http_status"],
    registry=registry,
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP Request Latency",
    ["method", "endpoint"],
    registry=registry,
)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    """Middleware to measure HTTP request counts and durations."""
    start_time = time.perf_counter()
    method = request.method
    endpoint = request.url.path
    
    response = await call_next(request)
    
    duration = time.perf_counter() - start_time
    status_code = response.status_code
    
    # Exclude metrics endpoint from scraping metrics
    if endpoint != "/metrics":
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, http_status=status_code).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
        
    return response


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from fastapi.responses import Response
    data = generate_latest(registry)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


# Mount main API router
app.include_router(api_router, prefix="/api")


# OpenTelemetry Tracing Setup (Optional/Graceful Fallback)
def setup_opentelemetry(app: FastAPI) -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        # Create resource configuration
        resource = Resource.create(attributes={"service.name": "resolveai-backend"})
        
        # Configure Tracer provider and exporter
        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(
            OTLPSpanExporter(endpoint=settings.OPENTELEMETRY_ENDPOINT, insecure=True)
        )
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        
        # Instrument FastAPI app
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry successfully initialized.")
    except Exception as e:
        logger.warning(f"Failed to initialize OpenTelemetry tracing (running without OTEL): {e}")


# Initialize OpenTelemetry
setup_opentelemetry(app)


@app.get("/")
async def root():
    return {
        "name": "ResolveAI",
        "description": "Evaluation-Driven Customer Operations Agent",
        "version": "0.1.0",
        "status": "ONLINE",
    }
