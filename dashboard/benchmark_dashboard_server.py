#!/usr/bin/env python3
"""Small read-only dashboard server for local benchmark artifacts."""

from __future__ import annotations

import json
import mimetypes
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import median
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
PUBLIC = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8093
LOCK = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def median_or_none(values: list[float]) -> float | None:
    return round(float(median(values)), 3) if values else None


def summarize_artifact(path: Path, artifact: dict, run: dict) -> dict:
    records = artifact.get("records", [])
    measured = [row for row in records if row.get("phase") == "measurement"]
    prompts: dict[str, dict] = {}
    for prompt in sorted({row.get("prompt", "unknown") for row in measured}):
        rows = [row for row in measured if row.get("prompt") == prompt]
        ok = [row for row in rows if not row.get("error")]
        prompts[prompt] = {
            "attempted": len(rows),
            "ok": len(ok),
            "metrics": {
                key: median_or_none([row[key] for row in ok if isinstance(row.get(key), (int, float))])
                for key in ("wall_s", "prompt_tok_s", "decode_tok_s")
            },
        }
    return {
        "source": str(path.relative_to(ROOT)),
        "runtime": artifact.get("runtime", "unknown"),
        "status": artifact.get("status", "unknown"),
        "model_logical_id": artifact.get("model_logical_id", "unknown"),
        "route": artifact.get("route", {"id": "unknown"}),
        "series_key": artifact.get("series_key", "unknown"),
        "comparison_scope": artifact.get("comparison_scope", "unknown"),
        "comparison_valid": bool(run.get("comparison_valid", True)),
        "run_status": run.get("status", "unknown"),
        "validity_reason": run.get("validity_reason"),
        "invalidation": run.get("invalidation"),
        "artifact_identity": artifact.get("artifact_identity", {}),
        "parameters": artifact.get("parameters", {}),
        "attempted_measurements": len(measured),
        "successful_measurements": sum(1 for row in measured if not row.get("error")),
        "warmups": sum(1 for row in records if row.get("phase") == "warmup"),
        "prompts": prompts,
    }


def snapshot() -> dict:
    started = now()
    series: dict[str, dict] = {}
    run_info: list[dict] = []
    errors: list[str] = []
    for run_dir in sorted(RESULTS.glob("qwen36-runtime-ab-*/")):
        run_path = run_dir / "run.json"
        if not run_path.exists():
            continue
        run = read_json(run_path)
        if not run:
            errors.append(str(run_path.relative_to(ROOT)))
            continue
        event_calls = sum(int(event.get("calls", 0)) for event in run.get("events", []))
        generation_calls = run.get("generation_calls_observed", {})
        run_info.append({
            "source": str(run_path.relative_to(ROOT)),
            "status": run.get("status", "unknown"),
            "comparison_valid": bool(run.get("comparison_valid", True)),
            "validity_reason": run.get("validity_reason"),
            "invalidation": run.get("invalidation"),
            "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"),
            "authorized_generations": run.get("authorized_generations", 48),
            "observed_generation_calls": generation_calls.get("total", event_calls),
            "observed_event_calls": event_calls,
            "last_event": (run.get("events") or [{}])[-1],
            "heartbeat": datetime.fromtimestamp(run_path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        for arm in ("ollama", "llama_cpp"):
            artifact_path = run_dir / arm / f"{arm}.json"
            if not artifact_path.exists():
                continue
            artifact = read_json(artifact_path)
            if not artifact:
                errors.append(str(artifact_path.relative_to(ROOT)))
                continue
            item = summarize_artifact(artifact_path, artifact, run)
            key = item["series_key"]
            if key in series:
                # Keep the latest artifact isolated; never pool records.
                if series[key]["source"] != item["source"]:
                    series[key] = item
            else:
                series[key] = item

    series_values = list(series.values())
    return {
        "schema_version": "benchmark-dashboard-snapshot-v1",
        "observer": {
            "status": "healthy" if not errors else "degraded",
            "last_successful_scan": started if not errors else None,
            "collector": "dashboard filesystem observer",
            "note": "dashboard health is separate from benchmark completion",
            "errors": errors,
        },
        "generated_at": started,
        "runs": sorted(run_info, key=lambda item: item.get("started_at") or "", reverse=True),
        "series_count": len(series_values),
        "series_isolation": {
            "mixed_series_rejected": True,
            "pooled_average": None,
            "note": "different series_key values never share a metric or trend",
        },
        "series": series_values,
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/snapshot":
            with LOCK:
                body = json.dumps(snapshot(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        relative = "index.html" if parsed.path in ("", "/") else parsed.path.lstrip("/")
        target = (PUBLIC / relative).resolve()
        if PUBLIC not in target.parents and target != PUBLIC:
            self.send_error(404)
            return
        if not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[dashboard] {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    print(f"benchmark dashboard: http://{HOST}:{PORT}/", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
