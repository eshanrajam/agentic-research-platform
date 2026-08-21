"""OpenTelemetry tracing setup.

Agent Framework automatically emits spans for agent runs, tool/function
calls, and MCP tool invocations once a global TracerProvider is configured -
this module owns exporter wiring only, it never imports agent_framework.
"""
from __future__ import annotations

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

logger = logging.getLogger(__name__)

_configured = False


def configure_telemetry(service_name: str = "agentic-research-platform") -> None:
    """Idempotently configure tracing. Safe to call multiple times."""
    global _configured
    if _configured:
        return

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))

    conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if conn_str:
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

            provider.add_span_processor(BatchSpanProcessor(AzureMonitorTraceExporter(connection_string=conn_str)))
            logger.info("Azure Monitor tracing enabled.")
        except ImportError:
            logger.warning(
                "APPLICATIONINSIGHTS_CONNECTION_STRING is set but the 'azure-monitor' extra isn't installed "
                "(pip install .[azure-monitor]). Falling back to console tracing."
            )
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _configured = True
