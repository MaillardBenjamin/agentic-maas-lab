import os
from opentelemetry import propagate, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


def configure(service_name):
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)


def service_headers():
    headers = {"X-Service-Token": os.environ.get("SERVICE_TOKEN", "local-services-only-0123456789")}
    propagate.inject(headers)
    return headers
