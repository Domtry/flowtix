"""Application metrics — counters and histograms for RPA operations."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


def setup_metrics(service_name: str = "flowtix", otlp_endpoint: str | None = None) -> Any:
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource

    resource = Resource.create({"service.name": service_name})
    provider = MeterProvider(resource=resource)

    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=otlp_endpoint))
        provider = MeterProvider(resource=resource, metric_readers=[reader])

    metrics.set_meter_provider(provider)
    logger.info("metrics.init", service=service_name)
    return provider


def get_meter(name: str = "flowtix") -> Any:
    from opentelemetry import metrics
    return metrics.get_meter(name)


class RpaMetrics:
    """Pre-defined RPA metrics."""

    def __init__(self, meter: Any | None = None) -> None:
        m = meter or get_meter()
        self.executions_started = m.create_counter("rpa.executions.started", description="Total executions started")
        self.executions_completed = m.create_counter("rpa.executions.completed", description="Total executions completed")
        self.executions_failed = m.create_counter("rpa.executions.failed", description="Total executions failed")
        self.step_duration = m.create_histogram("rpa.step.duration_ms", description="Step execution duration in ms", unit="ms")
        self.robots_active = m.create_up_down_counter("rpa.robots.active", description="Currently active robots")
        self.ai_requests = m.create_counter("rpa.ai.requests", description="AI service requests")
        self.data_rows_processed = m.create_counter("rpa.data.rows_processed", description="Data rows processed")
