"""Local Azure instrumentation and Uvicorn emission, without cloud exporters."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("mode", ["baseline", "sanitized"])
def test_local_activity_telemetry(mode, tmp_path):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), mode],
        cwd=Path(__file__).resolve().parents[1],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
            "PYTHON_DOTENV_DISABLED": "1",
            "DATA_DIR": str(tmp_path),
            "PRAXYS_SYNC_SCHEDULER": "false",
            "OTEL_METRICS_EXPORTER": "none",
            "APPLICATIONINSIGHTS_CONNECTION_STRING":
                "InstrumentationKey=00000000-0000-0000-0000-000000000001;IngestionEndpoint=http://127.0.0.1:1",
        },
        capture_output=True, text=True, timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(result.stdout.strip().splitlines()[-1])
    assert evidence["statuses"] == [200, 401, 404, 405, 500] * 2 + [404] * 6 + [200] * 4
    assert evidence["server_spans"] == 20
    assert evidence["identifier_in_spans"] is (mode == "baseline")
    assert evidence["identifier_in_access_logs"] is (mode == "baseline")
    assert evidence["identifier_in_exported_logs"] is (mode == "baseline")


def capture(mode):
    import io
    import logging
    import socket
    import threading
    import time

    import azure.monitor.opentelemetry as azure_monitor
    from azure.monitor.opentelemetry import _configure
    from opentelemetry import trace
    from opentelemetry._logs import get_logger_provider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter

    trace_exporter = InMemorySpanExporter()
    log_exporter = InMemoryLogRecordExporter()
    _configure.AzureMonitorTraceExporter = lambda **kwargs: trace_exporter
    import azure.monitor.opentelemetry.exporter as exporters
    exporters.AzureMonitorLogExporter = lambda **kwargs: log_exporter
    configure = azure_monitor.configure_azure_monitor

    def local_configure(**kwargs):
        options = {
            library: {"enabled": library == "fastapi"}
            for library in _configure._ALL_SUPPORTED_INSTRUMENTED_LIBRARIES
        }
        options.update(kwargs.pop("instrumentation_options", {}))
        configure(
            **kwargs, instrumentation_options=options,
            enable_live_metrics=False, enable_performance_counters=False,
            disable_offline_storage=True, sampling_ratio=1.0,
        )

    azure_monitor.configure_azure_monitor = local_configure
    if mode == "baseline":
        local_configure()
    else:
        import api.main

    from fastapi import FastAPI, HTTPException, Request
    import httpx
    import uvicorn

    application = FastAPI()

    @application.get("/api/history/{activity_id}/detail")
    async def detail(activity_id: str, request: Request):
        assert activity_id.startswith("synthetic-secret")
        assert request.query_params["marker"] == "synthetic-secret-query"
        await request.body()
        status = int(request.headers["x-test-status"])
        if status == 500:
            raise RuntimeError("synthetic failure")
        if status != 200:
            raise HTTPException(status)
        return {"ok": True}

    captured = io.StringIO()
    handler = logging.StreamHandler(captured)
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.addHandler(handler)
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = True
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(application, log_config=None, lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(.01)
    assert server.started
    statuses = []
    try:
        # The deliberate unhandled 500 closes Uvicorn's connection after sending
        # the response. Fresh connections avoid racing that close on the next
        # request; this test measures telemetry, not connection-pool recovery.
        with httpx.Client(
            base_url=f"http://127.0.0.1:{listener.getsockname()[1]}",
            limits=httpx.Limits(max_keepalive_connections=0),
        ) as client:
            for activity_id in ("synthetic-secret", "synthetic-secret%20encoded"):
                for status in (200, 401, 404, 405, 500):
                    response = client.request(
                        "POST" if status == 405 else "GET",
                        f"/api/history/{activity_id}/detail?marker=synthetic-secret-query#synthetic-secret-fragment",
                        headers={
                            "x-test-status": str(status),
                            "traceparent": "00-1234567890abcdef1234567890abcdef-1234567890abcdef-01",
                        },
                    )
                    statuses.append(response.status_code)
            for path in (
                "synthetic-secret%2Fencoded/detail",
                "synthetic-secret%3Fencoded/detail",
                "synthetic-secret%23encoded/detail",
                "synthetic-secret/detail/synthetic-secret-extra",
                "synthetic-secret",
                "synthetic-secret%2Fdetail%2Fsynthetic-secret/detail",
            ):
                response = client.get(
                    f"/api/history/{path}?marker=synthetic-secret-query#synthetic-secret-fragment",
                    headers={
                        "x-test-status": "404",
                        "traceparent": "00-1234567890abcdef1234567890abcdef-1234567890abcdef-01",
                    },
                )
                statuses.append(response.status_code)
            for prefix in ("/api/%68istory", "/%61pi/history", "/%61pi/%68istory", "/api%2Fhistory"):
                response = client.get(
                    f"{prefix}/synthetic-secret/detail?marker=synthetic-secret-query",
                    headers={
                        "x-test-status": "200",
                        "traceparent": "00-1234567890abcdef1234567890abcdef-1234567890abcdef-01",
                    },
                )
                statuses.append(response.status_code)
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
    trace.get_tracer_provider().force_flush()
    get_logger_provider().force_flush()
    spans = trace_exporter.get_finished_spans()
    server_spans = [span for span in spans if span.kind == trace.SpanKind.SERVER]
    internal_events = {span.attributes.get("asgi.event.type") for span in spans if span.kind == trace.SpanKind.INTERNAL}
    assert {"http.request", "http.response.start", "http.response.body"} <= internal_events
    assert all(span.end_time >= span.start_time for span in server_spans)
    assert all(span.context.trace_id == int("1234567890abcdef1234567890abcdef", 16) for span in server_spans)
    assert sorted(span.attributes["http.status_code"] for span in server_spans) == sorted(statuses)
    span_data = json.dumps([json.loads(span.to_json()) for span in spans])
    logs = log_exporter.get_finished_logs()
    log_data = json.dumps([json.loads(record.to_json()) for record in logs])
    result = {
        "statuses": statuses,
        "server_spans": len(server_spans),
        "identifier_in_spans": "synthetic-secret" in span_data,
        "identifier_in_access_logs": "synthetic-secret" in captured.getvalue(),
        "identifier_in_exported_logs": "synthetic-secret" in log_data,
    }
    if mode == "sanitized":
        assert "/api/history/{activity_id}/detail" in span_data
        assert "/api/history/{activity_id}/detail" in captured.getvalue()
        assert all(f" {status}" in captured.getvalue() for status in statuses)
        assert not any(result[key] for key in result if key.startswith("identifier_")), result
    print(json.dumps(result))


if __name__ == "__main__":
    capture(sys.argv[1])
