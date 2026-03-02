from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from urllib import error as urlerror
from urllib import request as urlrequest


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str


def http_json(base_url: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict | list]:
    url = f"{base_url.rstrip('/')}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(url, method=method.upper(), headers=headers, data=data)
    with urlrequest.urlopen(req, timeout=10) as resp:
        status = int(getattr(resp, "status", 200) or 200)
        raw = resp.read().decode("utf-8")
        payload = json.loads(raw) if raw else {}
        return status, payload


def run_step(name: str, fn) -> StepResult:
    try:
        detail = fn()
        return StepResult(name=name, ok=True, detail=detail)
    except urlerror.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            code = payload.get("error_code") or "-"
            req_id = payload.get("request_id") or "-"
            msg = payload.get("error") or str(exc)
            return StepResult(name=name, ok=False, detail=f"HTTP {exc.code} | error_code={code} | request_id={req_id} | {msg}")
        except Exception:
            return StepResult(name=name, ok=False, detail=f"HTTP {exc.code} | {exc.reason}")
    except Exception as exc:
        return StepResult(name=name, ok=False, detail=str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description="Web-shell E2E smoke check (collect -> label -> writer -> publish).")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="web-shell base URL")
    parser.add_argument("--verify-save", action="store_true", help="also POST settings with current values")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    results: list[StepResult] = []

    collect_settings: dict = {}
    label_settings: dict = {}
    writer_settings: dict = {}
    publish_settings: dict = {}

    results.append(run_step("menu", lambda: f"default_node={http_json(base, 'GET', '/api/v2/menu')[1].get('default_node_id', '-')}"))

    def load_collect() -> str:
        nonlocal collect_settings
        _, payload = http_json(base, "GET", "/api/v2/settings/collect")
        collect_settings = payload if isinstance(payload, dict) else {}
        return f"scope={collect_settings.get('keyword_scope', '-')}"

    def load_label() -> str:
        nonlocal label_settings
        _, payload = http_json(base, "GET", "/api/v2/settings/label")
        label_settings = payload if isinstance(payload, dict) else {}
        return f"method={label_settings.get('method', '-')}"

    def load_writer() -> str:
        nonlocal writer_settings
        _, payload = http_json(base, "GET", "/api/v2/settings/writer")
        writer_settings = payload if isinstance(payload, dict) else {}
        return f"priority={writer_settings.get('ai_provider_priority', '-')}"

    def load_publish() -> str:
        nonlocal publish_settings
        _, payload = http_json(base, "GET", "/api/v2/settings/publish")
        publish_settings = payload if isinstance(payload, dict) else {}
        return f"mode={publish_settings.get('channel_mode', '-')}"

    results.append(run_step("collect.settings.load", load_collect))
    results.append(run_step("collect.keywords", lambda: f"keywords={len(http_json(base, 'GET', '/api/collect/keywords')[1])}"))
    results.append(run_step("label.settings.load", load_label))
    results.append(run_step("label.stats", lambda: f"keys={len((http_json(base, 'GET', '/api/labeling/stats')[1] or {}).keys())}"))
    results.append(run_step("writer.settings.load", load_writer))
    results.append(run_step("writer.summary", lambda: f"channels={len((http_json(base, 'GET', '/api/writer/run-summary')[1] or {}).get('channels', []))}"))
    results.append(run_step("publish.settings.load", load_publish))
    results.append(run_step("publish.auto.status", lambda: f"enabled={bool((http_json(base, 'GET', '/api/publish/auto/status')[1] or {}).get('enabled', False))}"))
    results.append(run_step("publish.jobs", lambda: f"jobs={len(http_json(base, 'GET', '/api/publisher/jobs')[1])}"))
    results.append(run_step("monitor.events", lambda: f"rows={len((http_json(base, 'GET', '/api/v2/monitor/events?limit=50')[1] or {}).get('items', []))}"))

    if args.verify_save:
        if collect_settings:
            results.append(run_step("collect.settings.save", lambda: f"status={http_json(base, 'POST', '/api/v2/settings/collect', collect_settings)[0]}"))
        if label_settings:
            results.append(run_step("label.settings.save", lambda: f"status={http_json(base, 'POST', '/api/v2/settings/label', label_settings)[0]}"))
        if writer_settings:
            results.append(run_step("writer.settings.save", lambda: f"status={http_json(base, 'POST', '/api/v2/settings/writer', writer_settings)[0]}"))
        if publish_settings:
            results.append(run_step("publish.settings.save", lambda: f"status={http_json(base, 'POST', '/api/v2/settings/publish', publish_settings)[0]}"))

    fail_count = 0
    for row in results:
        mark = "OK" if row.ok else "FAIL"
        if not row.ok:
            fail_count += 1
        print(f"[{mark}] {row.name}: {row.detail}")

    print(f"\nsummary: total={len(results)} fail={fail_count}")
    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
