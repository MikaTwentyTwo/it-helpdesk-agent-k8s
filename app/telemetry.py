import json
import logging
import os
import time
from contextlib import contextmanager

from prometheus_client import Counter, Histogram
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider(
    resource=Resource.create({"service.name": "helpdesk-agent"})
)

if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter())
    )

trace.set_tracer_provider(provider)
tracer = trace.get_tracer("helpdesk")

logger = logging.getLogger("helpdesk.operations")
logger.setLevel(logging.INFO)
logger.propagate = False
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)

operations = Counter(
    "helpdesk_operations_total",
    "Completed operations by layer and status",
    ["layer", "status"],
)

duration = Histogram(
    "helpdesk_operation_seconds",
    "Operation duration in seconds",
    ["layer"],
)

llm_tokens = Counter(
    "helpdesk_llm_tokens_total",
    "Actual token counts reported by Ollama",
    ["kind"],
)


@contextmanager
def operation(layer: str):
    start = time.perf_counter()
    status = "ok"

    with tracer.start_as_current_span(layer) as current_span:
        try:
            yield current_span
        except BaseException:
            status = "error"
            raise
        finally:
            elapsed = time.perf_counter() - start
            operations.labels(layer, status).inc()
            duration.labels(layer).observe(elapsed)

            logger.info(json.dumps({
                "event": "operation_completed",
                "layer": layer,
                "status": status,
                "duration_seconds": round(elapsed, 6),
                "trace_id": format(
                    current_span.get_span_context().trace_id, "032x"
                ),
            }))


def observed(layer: str):
    import inspect
    from functools import wraps

    def decorate(function):
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def async_wrapper(*args, **kwargs):
                with operation(layer):
                    return await function(*args, **kwargs)
            return async_wrapper

        @wraps(function)
        def sync_wrapper(*args, **kwargs):
            with operation(layer):
                return function(*args, **kwargs)
        return sync_wrapper

    return decorate
