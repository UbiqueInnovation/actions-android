import os
import shlex
import sys

from mcp import StdioServerParameters
from smolagents import OpenAIModel, ToolCallingAgent, ToolCollection


class AutoToolModel(OpenAIModel):
    """OpenAIModel that forces tool_choice='auto' when tools are present and omits
    it otherwise. smolagents defaults to tool_choice='required', which makes the
    model fail every 'thinking only' turn with a JSON-blob parse error; and a
    forced tool_choice on a no-tool call (final answer / summary) trips
    'tool_choice without tools' API errors."""

    def _prepare_completion_kwargs(self, *args, **kwargs):
        if kwargs.get("tools_to_call_from"):
            kwargs["tool_choice"] = "auto"
        return super()._prepare_completion_kwargs(*args, **kwargs)


def build_model() -> AutoToolModel:
    api_key = os.environ.get("SELFHOSTED_LLM_API_KEY", "")
    base_url = os.environ.get("SELFHOSTED_LLM_BASE_URL", "").strip()
    model_name = os.environ.get("MODEL", "default")

    if not api_key:
        raise RuntimeError("SELFHOSTED_LLM_API_KEY is not set")

    return AutoToolModel(
        model_id=model_name,
        api_base=base_url if base_url else None,
        api_key=api_key,
    )


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
        "You are in a tool-calling loop: EVERY reply must invoke exactly one tool. Keep "
        "any reasoning to a single short sentence before the tool call and never reply "
        "with text only. If you are unsure what to do next, call "
        "mobile_list_elements_on_screen to re-read the screen."
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
        "You MUST finish by calling the final_answer tool with a concise structured report: "
        "(1) the task, (2) the key steps you actually performed, (3) what you observed, "
        "(4) a clear verdict on whether the task succeeded, and (5) any bugs, crashes, "
        "errors or unexpected behaviour found (or state that you found none). Never stop "
        "mid-thought - always end with a final_answer call."
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


def render_trace(agent) -> str:
    lines = []
    n = 0
    for step in agent.memory.steps:
        model_output = getattr(step, "model_output", None)
        tool_calls = getattr(step, "tool_calls", None)
        observations = getattr(step, "observations", None)
        error = getattr(step, "error", None)
        if model_output is None and not tool_calls and error is None:
            continue
        n += 1
        lines.append(f"**Step {n}**")
        reasoning = content_to_text(model_output).strip()
        if reasoning:
            lines.append(f"- Thought: {truncate(reasoning, 1200)}")
        for tc in tool_calls or []:
            args = tc.arguments
            args_s = args if isinstance(args, str) else str(args)
            lines.append(f"- Action: `{tc.name}` {truncate(args_s, 300)}")
        obs = content_to_text(observations).strip()
        if obs:
            lines.append(f"- Observation: {truncate(obs, 600)}")
        if error is not None:
            lines.append(f"- Error: {truncate(str(error), 300)}")
        lines.append("")
    if n == 0:
        lines.append("(no steps recorded)")
    return "\n".join(lines)


def summarize(model, prompt, trace) -> str:
    summary_prompt = (
        "You are summarizing an automated Android QA run that did not reach a clean final "
        "answer. From the trace below write a concise report: what was attempted, what "
        "actually happened, whether the task succeeded, and any bugs or errors observed. "
        "Be explicit about what was left unfinished.\n\n"
        f"ORIGINAL TASK:\n{truncate(prompt, 1500)}\n\n"
        f"TRACE:\n{truncate(trace, 9000)}"
    )
    try:
        msg = model.generate([{"role": "user", "content": summary_prompt}])
        return content_to_text(msg.content).strip()
    except Exception as exc:  # noqa: BLE001
        return f"(could not generate summary: {exc})"


def run_agent(prompt, mcp_command, app_package):
    server_parameters = mcp_server_parameters(mcp_command)
    model = build_model()
    with ToolCollection.from_mcp(
        server_parameters, trust_remote_code=True, structured_output=False
    ) as tools:
        max_obs = int(os.environ.get("MAX_OBS_CHARS", "15000"))
        wrapped = list(tools.tools)
        for t in wrapped:
            wrap_observation(t, max_obs)
        agent = ToolCallingAgent(
            tools=wrapped,
            model=model,
            instructions=build_instructions(app_package),
            max_steps=int(os.environ.get("MAX_TURNS", "50")),
        )
        result = agent.run(prompt, return_full_result=True)
        trace = render_trace(agent)

    state = getattr(result, "state", "success")
    output = content_to_text(getattr(result, "output", "")).strip()
    if state == "success" and output:
        status = "COMPLETED"
        report = output
    else:
        status = "INCOMPLETE"
        report = summarize(model, prompt, trace)
    return status, report, trace, getattr(result, "token_usage", None)


def format_tokens(token_usage) -> str:
    if not token_usage:
        return "n/a"
    try:
        return f"{token_usage.input_tokens:,} in / {token_usage.output_tokens:,} out"
    except Exception:  # noqa: BLE001
        return str(token_usage)


def main() -> None:
    prompt = os.environ.get("PROMPT", "")
    mcp_command = os.environ.get("MCP_COMMAND", "npx -y @mobilenext/mobile-mcp@latest")
    app_package = os.environ.get("APP_PACKAGE", "")

    if not prompt:
        raise RuntimeError("PROMPT is not set")

    print(f"[agent] MCP server: {mcp_command}", flush=True)
    print(f"[agent] target app: {app_package or '(not set)'}", flush=True)

    status, report, trace, token_usage = run_agent(prompt, mcp_command, app_package)

    report_md = (
        f"**Status: {status}**  \n"
        f"**Tokens: {format_tokens(token_usage)}**\n\n"
        f"### Report\n\n{report}\n\n"
        f"<details>\n<summary>Full step-by-step trace</summary>\n\n{trace}\n\n</details>\n"
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
