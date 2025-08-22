#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple, Optional

import httpx
import typer

BASE_URL = "https://api-cloud.browserstack.com/app-automate/maestro/v2"


class BrowserStackAuth:
    def __init__(self, username: str, access_key: str):
        self.username = username
        self.access_key = access_key

    @classmethod
    def from_env(cls) -> "BrowserStackAuth":
        username = os.getenv("BROWSERSTACK_USERNAME")

        access_key = os.getenv("BROWSERSTACK_ACCESS_KEY")

        if not username or not access_key:
            raise SystemExit(
                "Missing credentials. Set BROWSERSTACK_USERNAME and BROWSERSTACK_ACCESS_KEY in your .env"
            )
        return cls(username, access_key)

    def as_requests_auth(self) -> Tuple[str, str]:
        return self.username, self.access_key


def _print_json(label: str, payload: dict):
    sys.stdout.write(f"\n=== {label} ===\n")
    sys.stdout.write(json.dumps(payload, indent=2))
    sys.stdout.write("\n")


def upload_file(endpoint: str, file_path: str, auth: BrowserStackAuth, field_name: str,
                custom_id: Optional[str] = None) -> dict:
    url = f"{BASE_URL}/{endpoint}"
    if not os.path.isfile(file_path):
        raise SystemExit(f"File not found: {file_path}")
    with open(file_path, "rb") as f:
        files = {field_name: (os.path.basename(file_path), f)}
        data = {}
        if custom_id:
            data["custom_id"] = custom_id
        resp = httpx.post(url, auth=auth.as_requests_auth(), files=files, data=data, timeout=120)
    if resp.status_code >= 300:
        raise SystemExit(f"Upload failed ({resp.status_code}): {resp.text}")
    return resp.json()


def upload_app(apk_path: str, auth: BrowserStackAuth, custom_id: Optional[str] = None) -> str:
    data = upload_file("app", apk_path, auth, field_name="file", custom_id=custom_id)
    app_url = data.get("app_url") or data.get("app")  # be resilient
    if not app_url:
        _print_json("Upload App Response", data)
        raise SystemExit("Could not find app_url in response.")
    print(f"Uploaded app. app_url = {app_url}")
    return app_url


def upload_test_suite(flow_zip_path: str, auth: BrowserStackAuth, custom_id: Optional[str] = None) -> str:
    data = upload_file("test-suite", flow_zip_path, auth, field_name="file", custom_id=custom_id)
    test_suite_url = data.get("test_suite_url") or data.get("testSuite")  # be resilient
    if not test_suite_url:
        _print_json("Upload Test Suite Response", data)
        raise SystemExit("Could not find test_suite_url in response.")
    print(f"Uploaded test suite. test_suite_url = {test_suite_url}")
    return test_suite_url


def start_android_build(app_url: str, test_suite_url: str, devices: List[str], auth: BrowserStackAuth,
                        project: Optional[str] = None, execute: Optional[List[str]] = None,
                        extra_caps: Optional[dict] = None) -> str:
    url = f"{BASE_URL}/android/build"
    payload = {
        "app": app_url,
        "testSuite": test_suite_url,
        "devices": devices,
    }
    if project:
        payload["project"] = project
    if execute:
        payload["execute"] = execute
    if extra_caps:
        payload.update(extra_caps)

    resp = httpx.post(url, auth=auth.as_requests_auth(), json=payload, timeout=60)
    if resp.status_code >= 300:
        raise SystemExit(f"Start build failed ({resp.status_code}): {resp.text}")
    data = resp.json()
    build_id = data.get("build_id") or data.get("id")
    if not build_id:
        _print_json("Start Build Response", data)
        raise SystemExit("Could not find build_id in response.")
    print(f"Started build. build_id = {build_id}")
    return build_id


def get_build_status(build_id: str, auth: BrowserStackAuth) -> dict:
    url = f"{BASE_URL.replace('/v2', '/v2')}/builds/{build_id}"
    resp = httpx.get(url, auth=auth.as_requests_auth(), timeout=60)
    if resp.status_code >= 300:
        raise SystemExit(f"Get build status failed ({resp.status_code}): {resp.text}")
    return resp.json()


def poll_build(build_id: str, auth: BrowserStackAuth, interval: int = 20, timeout: int = 60 * 60) -> dict:
    """Poll build until it leaves queued/running or until timeout seconds elapse."""
    start = time.time()
    terminal_statuses = {"passed", "failed", "error", "timedout", "stopped", "completed", "unknown"}
    while True:
        status_json = get_build_status(build_id, auth)
        status = status_json.get("status") or status_json.get("build_status") or ""
        print(f"[{time.strftime('%H:%M:%S')}] build {build_id} status: {status or 'unknown'}")
        if status and status.lower() in terminal_statuses:
            _print_json("Final build status", status_json)
            return status_json
        if time.time() - start > timeout:
            print("Polling timed out.")
            _print_json("Last known status", status_json)
            return status_json
        time.sleep(interval)


def get_screenshots(build_id: str, session_id: str, auth: BrowserStackAuth, local_path: Optional[Path] = None):
    if local_path is None:
        local_path = Path(f"./screenshots/{build_id}/{session_id}")

    url = f"{BASE_URL}/builds/{build_id}/sessions/{session_id}"
    resp = httpx.get(url, auth=auth.as_requests_auth(), timeout=60)

    if resp.status_code >= 300:
        raise SystemExit(f"Session detail load failed ({resp.status_code}): {resp.text}")
    data = resp.json()

    for d in data["testcases"]["data"]:
        for test in d["testcases"]:
            if test["status"] == "passed":
                screenshot_url = test["screenshots"]
                content = httpx.get(screenshot_url, auth=auth.as_requests_auth(), timeout=60).content
                local_path.mkdir(parents=True, exist_ok=True)
                with open(local_path / "screenshots.zip", "wb") as f:
                    f.write(content)


def parse_devices(devices_str: Optional[str]) -> List[str]:
    if not devices_str:
        # A sensible default device; users should override for real runs.
        return ["Google Pixel 3-9.0"]
    return [d.strip() for d in devices_str.split(",") if d.strip()]


def parse_execute(execute_str: Optional[str]) -> Optional[List[str]]:
    if not execute_str:
        return None
    # allow comma-separated paths
    return [p.strip() for p in execute_str.split(",") if p.strip()]


app = typer.Typer(help="Run Maestro tests on BrowserStack via REST API")


@app.command()
def run(
        apk: str = typer.Option(..., help="Path to the Android APK to upload", metavar="PATH"),
        flow: str = typer.Option(..., help="Path to the Maestro Flows ZIP to upload", metavar="PATH"),
        devices: Optional[str] = typer.Option(
            None,
            help="Comma-separated device names (e.g. 'Samsung Galaxy S20-10.0,Google Pixel 3-9.0')",
        ),
        project: Optional[str] = typer.Option(None, help="Optional project name to group builds"),
        execute: Optional[str] = typer.Option(
            None,
            help="Optional comma-separated paths within the flow ZIP to run (files or folders)",
        ),
        app_id: Optional[str] = typer.Option(None, help="Optional custom_id for the uploaded app"),
        suite_id: Optional[str] = typer.Option(None, help="Optional custom_id for the uploaded test suite"),
        poll: bool = typer.Option(False, help="Poll build status until completion"),
        interval: int = typer.Option(20, help="Polling interval seconds"),
        timeout: int = typer.Option(3600, help="Polling timeout seconds"),
):
    auth = BrowserStackAuth.from_env()

    app_url = upload_app(apk, auth, custom_id=app_id)
    suite_url = upload_test_suite(flow, auth, custom_id=suite_id)

    device_list = parse_devices(devices)
    execute_list = parse_execute(execute)

    build_id = start_android_build(
        app_url=app_url,
        test_suite_url=suite_url,
        devices=device_list,
        project=project,
        execute=execute_list,
        auth=auth,
    )

    typer.echo(f"\nBuild started. ID: {build_id}")
    typer.echo("View details in App Automate dashboard (Builds > Maestro).")

    if poll:
        status = poll_build(build_id, auth, interval=interval, timeout=timeout)
        final = (status.get("status") or "").lower()
        if final in {"failed", "error", "timedout"}:
            raise typer.Exit(code=2)
        else:
            for device in status["devices"]:
                for session in device.get("sessions", []):
                    get_screenshots(build_id, session_id=session["id"], auth=auth)


@app.command()
def screenshots(
        build_id: str = typer.Option(..., help="The build ID to load screenshots from", metavar="ID"),
        session_id: str = typer.Option(..., help="The session ID to load screenshots from", metavar="ID"),
        output: Path = typer.Option(..., help="Local directory to save screenshots to", metavar="PATH"),
):
    auth = BrowserStackAuth.from_env()
    get_screenshots(build_id, session_id, auth, output)
    typer.echo(f"Screenshots saved to {output.resolve()}")


if __name__ == "__main__":
    app()
