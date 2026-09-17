import json
import os
import shlex
import sys

import openai
from mcp import StdioServerParameters
from smolagents import ToolCollection
from smolagents.models import get_tool_json_schema


def build_instructions(app_package: str) -> str:
    parts = [
        "You are an autonomous Android QA engineer. A single Android device is already "
        "connected over adb and the app under test is already installed. Test the app the "
        "way a careful human tester would: exercise its main screens and primary user "
        "flows, and actively look for problems."
    ]
    if app_package:
        parts.append(
            f"The app under test has Android package name '{app_package}'. It is already in "
            "the foreground. Test ONLY this app. If you ever find yourself outside it, come "
            f"back with mobile_launch_app using package '{app_package}'. Never interact with "
            "other apps, the launcher or the home screen, and never press the HOME button."
        )
    parts.append(
        "Reading the screen: call mobile_list_elements_on_screen. It returns the "
        "accessibility tree where every element has a reference such as '@e12'. Use that "
        "reference as the handle for everything. Avoid mobile_take_screenshot unless the "
        "tree is empty or genuinely ambiguous - screenshots are large and slow you down."
    )
    parts.append(
        "Acting: tap elements by their reference (ref='@e12'). Never pass an empty ref. "
        "Only fall back to raw x/y coordinates if an element has no ref, and in that case "
        "pass x and y and omit the ref argument entirely. Type into the focused field with "
        "mobile_type_keys, scroll with mobile_swipe_on_screen, and use mobile_press_button "
        "only for BACK or ENTER."
    )
    parts.append(
        "Work methodically: read the tree, take ONE action, then read the tree again and "
        "confirm the screen changed as expected. If an action errors or has no effect, do "
        "not repeat it blindly - re-read the tree and choose a different element. Look for "
        "crashes, error dialogs, blank or stuck-loading screens, broken layouts and "
        "unexpected behaviour; if the app crashes use mobile_list_crashes and "
        "mobile_get_device_logs."
    )
    parts.append(
        "When you have finished the task, or cannot make further progress, reply with your "
        "final structured report as plain text and DO NOT call any tool. The report must "
        "cover: (1) the task, (2) the key steps you actually performed, (3) what you "
        "observed, (4) a clear verdict on whether the task succeeded, and (5) any bugs, "
        "crashes, errors or unexpected behaviour found (or state that you found none)."
    )
    return " ".join(parts)


def mcp_server_parameters(mcp_command: str) -> StdioServerParameters:
    parts = shlex.split(mcp_command)
    if not parts:
        raise RuntimeError("MCP_COMMAND is empty")
    return StdioServerParameters(command=parts[0], args=parts[1:], env=dict(os.environ))


def content_to_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" or "text" in part:
                    out.append(str(part.get("text", "")))
                else:
                    out.append(f"<{part.get('type', 'non-text')}>")
            else:
                out.append(str(part))
        return "\n".join(out)
    return str(content)


def truncate(text, limit) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + f" ...[+{len(text) - limit} chars]"


def wrap_observation(tool, limit) -> None:
    """Cap a tool's returned observation so huge screen dumps don't blow up the
    context window (every observation is re-sent on every subsequent turn)."""
    original = tool.forward

    def wrapped(*args, **kwargs):
        out = original(*args, **kwargs)
        if isinstance(out, str) and len(out) > limit:
            return (
                out[:limit]
                + f"\n[observation truncated: {len(out)} -> {limit} chars; "
                "re-run this tool if you need the rest]"
            )
        return out

    tool.forward = wrapped


def sanitize_click_tool(tool) -> None:
    """mobile-mcp's tap tool takes EITHER an element ref OR x/y coords. The model
    sometimes sends a ref together with x=0,y=0, and the tool then taps (0,0) and
    nothing happens. Normalise: a real ref wins (drop coords); otherwise drop the
    empty ref so the coords are used."""
    if getattr(tool, "name", "") != "mobile_click_on_screen_at_coordinates":
        return
    original = tool.forward

    def wrapped(*args, **kwargs):
        if kwargs.get("ref"):
            kwargs.pop("x", None)
            kwargs.pop("y", None)
        else:
            kwargs.pop("ref", None)
        return original(*args, **kwargs)

    tool.forward = wrapped


def prune_messages(messages, keep):
    """Collapse all but the last `keep` tool observations to a placeholder so the
    context stops growing with stale screen dumps. The tool_call_id pairing is kept
    intact (only the content is shortened), so the native format stays valid."""
    tool_idx = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    collapse = set(tool_idx[:-keep]) if len(tool_idx) > keep else set()
    out = []
    for i, m in enumerate(messages):
        if i in collapse and isinstance(m.get("content"), str) and len(m["content"]) > 80:
            m2 = dict(m)
            m2["content"] = "[earlier screen omitted to save context]"
            out.append(m2)
        else:
            out.append(m)
    return out


def render_trace(trace) -> str:
    lines = []
    for e in trace:
        lines.append(f"**Step {e['step']}**")
        if e.get("reasoning"):
            lines.append(f"- Thought: {truncate(e['reasoning'], 1200)}")
        if e.get("action"):
            lines.append(f"- Action: {e['action']}")
        if e.get("observation"):
            lines.append(f"- Observation: {truncate(e['observation'], 600)}")
        if e.get("error"):
            lines.append(f"- Error: {truncate(e['error'], 300)}")
        lines.append("")
    return "\n".join(lines) if lines else "(no steps recorded)"


def summarize(client, model_id, prompt, trace_md) -> str:
    sp = (
        "You are summarizing an automated Android QA run that hit its step limit "
        "without a final report. From the trace below write a concise report: what was "
        "attempted, what actually happened, whether the task succeeded, and any bugs or "
        "errors observed. Be explicit about what was left unfinished.\n\n"
        f"ORIGINAL TASK:\n{truncate(prompt, 1500)}\n\n"
        f"TRACE:\n{truncate(trace_md, 9000)}"
    )
    try:
        r = client.chat.completions.create(model=model_id, messages=[{"role": "user", "content": sp}])
        return (r.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        return f"(could not generate summary: {exc})"


def run_agent(prompt, mcp_command, app_package):
    server_parameters = mcp_server_parameters(mcp_command)
    api_key = os.environ.get("SELFHOSTED_LLM_API_KEY", "")
    if not api_key:
        raise RuntimeError("SELFHOSTED_LLM_API_KEY is not set")
    base_url = os.environ.get("SELFHOSTED_LLM_BASE_URL", "").strip() or None
    model_id = os.environ.get("MODEL", "default")
    max_steps = int(os.environ.get("MAX_TURNS", "80"))
    max_obs = int(os.environ.get("MAX_OBS_CHARS", "15000"))
    keep = int(os.environ.get("KEEP_FULL_SCREENS", "2"))

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    with ToolCollection.from_mcp(
        server_parameters, trust_remote_code=True, structured_output=False
    ) as toolset:
        tools = list(toolset.tools)
        for t in tools:
            wrap_observation(t, max_obs)
            sanitize_click_tool(t)
        by_name = {t.name: t for t in tools}
        schemas = [get_tool_json_schema(t) for t in tools]

        messages = [
            {"role": "system", "content": build_instructions(app_package)},
            {"role": "user", "content": prompt},
        ]
        trace = []
        in_tok = 0
        out_tok = 0
        final = None

        for step in range(1, max_steps + 1):
            resp = client.chat.completions.create(
                model=model_id,
                messages=prune_messages(messages, keep),
                tools=schemas,
                tool_choice="auto",
            )
            if resp.usage:
                in_tok += resp.usage.prompt_tokens
                out_tok += resp.usage.completion_tokens
            msg = resp.choices[0].message
            reasoning = msg.content or ""
            tcs = msg.tool_calls or []
            print(
                f"[raw] step={step} tool_calls={len(tcs)} content={reasoning[:160]!r}",
                flush=True,
            )

            asst = {"role": "assistant", "content": reasoning if reasoning else None}
            if tcs:
                asst["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tcs
                ]
            messages.append(asst)

            if not tcs:
                final = reasoning
                trace.append({"step": step, "reasoning": reasoning})
                break

            for tc in tcs:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:  # noqa: BLE001
                    args = {}
                tool = by_name.get(name)
                if tool is None:
                    obs = f"Unknown tool: {name}"
                else:
                    try:
                        obs = content_to_text(tool(**args))
                    except Exception as exc:  # noqa: BLE001
                        obs = f"Tool error: {exc}"
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": obs})
                trace.append(
                    {
                        "step": step,
                        "reasoning": reasoning,
                        "action": f"`{name}` {truncate(str(args), 200)}",
                        "observation": obs,
                    }
                )

        status = "COMPLETED" if final else "INCOMPLETE"
        report = final if final else summarize(client, model_id, prompt, render_trace(trace))
    return status, report, trace, (in_tok, out_tok)


def main() -> None:
    prompt = os.environ.get("PROMPT", "")
    mcp_command = os.environ.get("MCP_COMMAND", "npx -y @mobilenext/mobile-mcp@latest")
    app_package = os.environ.get("APP_PACKAGE", "")

    if not prompt:
        raise RuntimeError("PROMPT is not set")

    print(f"[agent] MCP server: {mcp_command}", flush=True)
    print(f"[agent] target app: {app_package or '(not set)'}", flush=True)

    status, report, trace, (in_tok, out_tok) = run_agent(prompt, mcp_command, app_package)

    report_md = (
        f"**Status: {status}**  \n"
        f"**Tokens: {in_tok:,} in / {out_tok:,} out**\n\n"
        f"### Report\n\n{report}\n\n"
        f"<details>\n<summary>Full step-by-step trace</summary>\n\n{render_trace(trace)}\n\n</details>\n"
    )
    with open("agent-report.md", "w") as f:
        f.write(report_md)
    with open("agent-status.txt", "w") as f:
        f.write(status)
    print("\n=== AGENT FINAL OUTPUT ===\n", flush=True)
    print(report_md)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"android-device-agent failed: {exc}", file=sys.stderr)
        sys.exit(1)
