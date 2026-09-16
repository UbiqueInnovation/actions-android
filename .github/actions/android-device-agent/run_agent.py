import asyncio
import os
import sys

from agents import Agent, Runner
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI


INSTRUCTIONS = (
    "You are an autonomous Android QA tester. An Android device is connected "
    "and the app under test is already installed. Use the available "
    "mobile-mcp tools to interact with the device (list devices, launch and "
    "terminate apps, tap, long-press, swipe, type, press hardware buttons, "
    "take screenshots, and read device logs). Start by listing the available "
    "devices to confirm the connection. Follow the task below, verify the "
    "outcome on screen, and finish with a concise written report of what you "
    "did and what you observed, including any errors or unexpected behavior."
)


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


async def run_agent(prompt: str, mcp_package: str) -> str:
    async with MCPServerStdio(
        name="android-mcp",
        params={"command": "npx", "args": ["-y", mcp_package]},
    ) as server:
        agent = Agent(
            name="android-tester",
            instructions=INSTRUCTIONS,
            model=build_model(),
            mcp_servers=[server],
        )
        result = await Runner.run(agent, prompt, max_turns=80)
        return result.final_output


def main() -> None:
    prompt = os.environ.get("PROMPT", "")
    mcp_package = os.environ.get("MCP_PACKAGE", "@mobilenext/mobile-mcp@latest")

    if not prompt:
        raise RuntimeError("PROMPT is not set")

    output = asyncio.run(run_agent(prompt, mcp_package))
    print(output)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"android-device-agent failed: {exc}", file=sys.stderr)
        sys.exit(1)
