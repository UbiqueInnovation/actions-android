import http.client
import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit


def report(env, event, timestamp):
    owner, repo = env["GITHUB_REPOSITORY"].split("/", 1)
    base = dict(repoOwner=owner, repoName=repo, runId=env["GITHUB_RUN_ID"],
                runAttempt=env["GITHUB_RUN_ATTEMPT"], ref=env["GITHUB_REF"],
                defaultBranch=event["repository"]["default_branch"], timestamp=timestamp)
    trigger = env["LIMMAT_EVENT"]
    if trigger == "gradle":
        if base["ref"] != "refs/heads/" + base["defaultBranch"]:
            return None
        count = int(env["LIMMAT_COUNT"])
        if count < 0 or not env["LIMMAT_PACKAGE"]:
            raise ValueError("Incomplete Gradle report")
        return "/apis/packages/gradle", dict(base, packageName=env["LIMMAT_PACKAGE"], outdatedDirectDependencies=count)

    outcome = env["LIMMAT_OUTCOME"]
    if trigger == "build_start":
        outcome = "in_progress"
    elif trigger != "build_end" or outcome not in ("success", "failure", "cancelled"):
        raise ValueError("Invalid build event")
    return "/apis/builds/logs", dict(
        base, platform="android", trigger=trigger, outcome=outcome, scheme=env["LIMMAT_SCHEME"],
        workflow=env["GITHUB_WORKFLOW"], actor=env["GITHUB_ACTOR"],
        avatarUrl=(event.get("sender") or {}).get("avatar_url") or "",
        runnerName=env["LIMMAT_RUNNER_NAME"], runnerEnvironment=env["LIMMAT_RUNNER_ENVIRONMENT"],
        scheduled=env.get("GITHUB_EVENT_NAME") == "schedule", errors=[], warningCount=0)


def send(path, payload, token, base_url):
    base = urlsplit(base_url)
    if base.scheme != "https" or not base.hostname or base.username is not None or base.query or base.fragment:
        raise ValueError("Expected an HTTPS base URL without credentials, query or fragment")
    path = base.path.rstrip("/") + path
    body = json.dumps(payload).encode()
    for attempt in range(3):
        conn = http.client.HTTPSConnection(base.hostname, port=base.port, timeout=5)
        try:
            conn.request("POST", path, body, {"Content-Type": "application/json", "api-key": token})
            status = conn.getresponse().status
            if 200 <= status < 300:
                return
            if status != 429 and status < 500:
                raise ValueError(f"Limmat returned HTTP {status}")
            problem = f"HTTP {status}"
        except (OSError, http.client.HTTPException) as error:
            problem = type(error).__name__
        finally:
            conn.close()
        if attempt < 2:
            time.sleep(1 + attempt)
    raise RuntimeError(f"Limmat unavailable ({problem})")


if __name__ == "__main__":
    env = os.environ
    event = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text())
    result = report(env, event, time.time_ns() // 1_000_000)
    if result:
        send(*result, env["LIMMAT_TOKEN"], env["LIMMAT_BASE_URL"])
