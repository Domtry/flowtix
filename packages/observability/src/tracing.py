"""OpenTelemetry tracing setup."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


def setup_tracing(
    service_name: str = "flowtix",
    otlp_endpoint: str | None = None,
) -> Any:
    """Initialize OpenTelemetry tracing with OTLP exporter."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.resources import Resource

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("tracing.otlp", endpoint=otlp_endpoint)

    trace.set_tracer_provider(provider)
    logger.info("tracing.init", service=service_name)
    return provider


def get_tracer(name: str = "flowtix") -> Any:
    from opentelemetry import trace
    return trace.get_tracer(name)
