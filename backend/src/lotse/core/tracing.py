"""OpenTelemetry setup. One provider per app; spans are exported only when an endpoint is set."""

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from lotse.settings import Settings

ATTR_REQUEST_ID = "lotse.request_id"
ATTR_TENANT_ID = "lotse.tenant_id"


def instrument(app: FastAPI, settings: Settings) -> TracerProvider:
    provider = TracerProvider(
        resource=Resource.create(
            {"service.name": "lotse-api", "deployment.environment": settings.env}
        )
    )
    if settings.otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider, excluded_urls="healthz,readyz"
    )
    return provider


def current_trace_id() -> str | None:
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None
