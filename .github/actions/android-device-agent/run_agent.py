import asyncio
import os
import sys

from agents import Agent, Runner, RunHooks
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI


def build_model() -> OpenAIChatCompletionsModel:
    api_key = os.environ.get("SELFHOSTED_LLM_API_KEY", "")
    base_url = os.environ.get("SELFHOSTED_LLM_BASE_URL", "").strip()
    model_name = os.environ.get("MODEL", "default")

    if not api_key:
        raise RuntimeError("SELFHOSTED_LLM_API_KEY is not set")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url if base_url else None,
    )
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


def build_instructions(app_package: str) -> str:
    parts = [
        "You are an autonomous Android QA tester. A single Android device is connected "
        "over adb and the app under test is already installed."
    ]
    if app_package:
        parts.append(
            f"The app under test has Android package name '{app_package}'. It has already "
            "been launched and should be in the foreground. Interact ONLY with this app. "
            f"If it is not in the foreground, bring it back (relaunch it by package name "
            f"'{app_package}'). Do NOT open, launch, or interact with any other app."
        )
    parts.append(
        "Use the available mobile-mcp tools to drive the device (list devices, launch app, "
        "tap, long-press, swipe, type text, press hardware buttons, take screenshots, and "
        "read device logs). Work methodically: before you act, take a screenshot to see the "
        "current screen; after each action, take another screenshot to verify what changed. "
        "If an action produces no visible change, do NOT repeat the same tap - press Back, "
        "tap a different element, or relaunch the target app. If the app shows a crash, a "
        "blank screen, or a stuck loading screen, note it and stop guessing. Finish with a "
        "concise written report of exactly what you did, what you observed on screen, and "
        "any crashes, errors, or unexpected behavior."
    )
    return " ".join(parts)


class LoggingHooks(RunHooks):
    """Print each turn and tool call so a stuck/looping run is diagnosable."""

    def __init__(self) -> None:
        self._turn = 0

    def _log(self, msg: str) -> None:
        try:
            print(msg, flush=True)
        except Exception:  # noqa: BLE001 - logging must never break the run
            pass

    def on_llm_start(self, context, agent, system_prompt, input_items) -> None:
        self._turn += 1
        self._log(f"[agent] turn {self._turn}: calling model")

    def on_llm_end(self, context, agent, response) -> None:
        try:
            for item in getattr(response, "output", []) or []:
                t = getattr(item, "type", None)
                if t in (
                    "function_call",
                    "computer_call",
                    "mcp_call",
                    "custom_tool_call",
                    "tool_search_call",
                ):
                    name = getattr(item, "name", "?")
                    args = getattr(item, "arguments", "") or getattr(item, "input", "")
                    self._log(f"[agent]   tool_call: {name} {str(args)[:500]}")
                elif t == "message":
                    text = "".join(
                        getattr(p, "text", "") for p in getattr(item, "content", []) or []
                    )
                    if text.strip():
                        self._log(f"[agent]   assistant: {text.strip()[:500]}")
        except Exception:  # noqa: BLE001
            pass

    def on_tool_start(self, context, agent, tool) -> None:
        self._log(f"[agent]   -> tool start: {getattr(tool, 'name', tool)}")

    def on_tool_end(self, context, agent, tool, result) -> None:
        self._log(
            f"[agent]   <- tool end: {getattr(tool, 'name', tool)} "
            f"result={str(result)[:300]}"
        )


async def run_agent(prompt: str, mcp_package: str, app_package: str) -> str:
    async with MCPServerStdio(
        name="android-mcp",
        params={"command": "npx", "args": ["-y", mcp_package]},
    ) as server:
        agent = Agent(
            name="android-tester",
            instructions=build_instructions(app_package),
            model=build_model(),
            mcp_servers=[server],
        )
        max_turns = int(os.environ.get("MAX_TURNS", "40"))
        result = await Runner.run(
            agent, prompt, max_turns=max_turns, hooks=LoggingHooks()
        )
        return result.final_output


def main() -> None:
    prompt = os.environ.get("PROMPT", "")
    mcp_package = os.environ.get("MCP_PACKAGE", "@mobilenext/mobile-mcp@latest")
    app_package = os.environ.get("APP_PACKAGE", "")

    if not prompt:
        raise RuntimeError("PROMPT is not set")

    output = asyncio.run(run_agent(prompt, mcp_package, app_package))
    print("\n=== AGENT FINAL OUTPUT ===\n", flush=True)
    print(output)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"android-device-agent failed: {exc}", file=sys.stderr)
        sys.exit(1)
