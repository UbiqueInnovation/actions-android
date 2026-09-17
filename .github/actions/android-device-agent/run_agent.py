import os
import shlex
import sys

from mcp import StdioServerParameters
from smolagents import OpenAIModel, ToolCallingAgent, ToolCollection


def build_model() -> OpenAIModel:
    api_key = os.environ.get("SELFHOSTED_LLM_API_KEY", "")
    base_url = os.environ.get("SELFHOSTED_LLM_BASE_URL", "").strip()
    model_name = os.environ.get("MODEL", "default")

    if not api_key:
        raise RuntimeError("SELFHOSTED_LLM_API_KEY is not set")

    return OpenAIModel(
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
            f"The app under test has Android package name '{app_package}'. It has already "
            "been launched into the foreground. Test ONLY this app. Before your first "
            f"action, confirm it is in the foreground with mobile_get_foreground_app; if "
            f"it is not, bring it back with mobile_launch_app using package "
            f"'{app_package}'. Never open, launch, or interact with any other app, the "
            "launcher, or the home screen, and do NOT press the HOME button (it leaves "
            "the app under test)."
        )
    parts.append(
        "Drive the device with the mobile-mcp tools. Read the screen primarily with "
        "mobile_list_elements_on_screen, which returns the accessibility tree (element "
        "text, resource-id, class and coordinates); use mobile_take_screenshot only when "
        "you need to see something the tree does not capture. To act, tap the "
        "coordinates reported by mobile_list_elements_on_screen using "
        "mobile_click_on_screen_at_coordinates; enter text with mobile_type_keys into the "
        "focused field; scroll with mobile_swipe_on_screen; and use mobile_press_button "
        "for BACK or ENTER (never HOME). Work methodically: read the screen, take one "
        "action, then read the screen again and confirm it changed as expected. If an "
        "action has no effect, do not repeat it blindly - try a different element, "
        "scroll, or press BACK. Look specifically for crashes, error dialogs, blank or "
        "stuck-loading screens, broken layouts, and unexpected behavior; if the app "
        "crashes or freezes, capture the state and, if useful, inspect "
        "mobile_list_crashes and mobile_get_device_logs. Finish with a concise, "
        "structured report: the steps you performed, what you observed on each screen, "
        "and a clear list of any bugs, crashes, errors or unexpected behavior (or state "
        "clearly that you found none)."
    )
    return " ".join(parts)


def mcp_server_parameters(mcp_command: str) -> StdioServerParameters:
    parts = shlex.split(mcp_command)
    if not parts:
        raise RuntimeError("MCP_COMMAND is empty")
    return StdioServerParameters(command=parts[0], args=parts[1:], env=dict(os.environ))


def run_agent(prompt: str, mcp_command: str, app_package: str) -> str:
    server_parameters = mcp_server_parameters(mcp_command)
    with ToolCollection.from_mcp(server_parameters, trust_remote_code=True) as tools:
        agent = ToolCallingAgent(
            tools=[*tools.tools],
            model=build_model(),
            instructions=build_instructions(app_package),
            max_steps=int(os.environ.get("MAX_TURNS", "40")),
        )
        result = agent.run(prompt)
        return result if isinstance(result, str) else str(result)


def main() -> None:
    prompt = os.environ.get("PROMPT", "")
    mcp_command = os.environ.get("MCP_COMMAND", "npx -y @mobilenext/mobile-mcp@latest")
    app_package = os.environ.get("APP_PACKAGE", "")

    if not prompt:
        raise RuntimeError("PROMPT is not set")

    print(f"[agent] MCP server: {mcp_command}", flush=True)
    print(f"[agent] target app: {app_package or '(not set)'}", flush=True)

    output = run_agent(prompt, mcp_command, app_package)
    print("\n=== AGENT FINAL OUTPUT ===\n", flush=True)
    print(output)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"android-device-agent failed: {exc}", file=sys.stderr)
        sys.exit(1)
