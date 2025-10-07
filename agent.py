#!/usr/bin/env python3
"""
Minimal Gemini Computer Use + Playwright agent.
- Viewport 1440x900 (recommended) for stability.
- Supported basic actions: open_web_browser, navigate, search, click_at, type_text_at,
  key_combination, scroll_document, scroll_at, hover_at, drag_and_drop, go_back, go_forward, wait_5_seconds.
- HITL: if model marked step as require_confirmation — ask in console.

Usage:
  python agent.py "Find Wikipedia article about Niagara Falls and open History section"

Requires GEMINI_API_KEY environment variable.
"""
import os
import sys
import time
from typing import Any, Dict, List

from termcolor import cprint
from playwright.sync_api import sync_playwright

from google import genai
from google.genai import types
from google.genai.types import Content, Part

# --- Constants and utilities ---
SCREEN_WIDTH = 1440
SCREEN_HEIGHT = 900
MODEL = "gemini-2.5-computer-use-preview-10-2025"  # this specific model is required, otherwise error

def denorm_x(x: int) -> int:
    return int(x / 1000 * SCREEN_WIDTH)

def denorm_y(y: int) -> int:
    return int(y / 1000 * SCREEN_HEIGHT)

def ask_confirmation(safety_decision: Dict[str, Any]) -> bool:
    cprint("\n⚠ Safety check: confirmation required", "red")
    print(safety_decision.get("explanation", ""))
    while True:
        ans = input("Continue? [y/N]: ").strip().lower()
        if ans in ("y", "yes"): return True
        if ans in ("", "n", "no"): return False

def exec_calls(candidate, page) -> List[tuple[str, Dict[str, Any]]]:
    """Execute all function_call from model response. Return list of (name, result_payload)."""
    results: List[tuple[str, Dict[str, Any]]] = []
    function_calls = [p.function_call for p in candidate.content.parts if getattr(p, "function_call", None)]

    for fc in function_calls:
        name = fc.name
        args = dict(fc.args or {})
        extra: Dict[str, Any] = {}

        # HITL: if step is "risky" — ask for confirmation
        if "safety_decision" in args:
            if not ask_confirmation(args["safety_decision"]):
                print("⛔ User denied. Stopping.")
                # Mark stop result with this step
                results.append((name, {"error": "user_denied"}))
                return results
            extra["safety_acknowledgement"] = "true"

        print(f"→ {name} {args}")
        try:
            if name == "open_web_browser":
                pass  # browser already open
            elif name == "wait_5_seconds":
                time.sleep(5)
            elif name == "go_back":
                page.go_back()
            elif name == "go_forward":
                page.go_forward()
            elif name == "search":
                page.goto("https://www.google.com")
            elif name == "navigate":
                page.goto(args["url"])
            elif name == "click_at":
                page.mouse.click(denorm_x(args["x"]), denorm_y(args["y"]))
            elif name == "hover_at":
                page.mouse.move(denorm_x(args["x"]), denorm_y(args["y"]))
            elif name == "type_text_at":
                x, y = denorm_x(args["x"]), denorm_y(args["y"])
                page.mouse.click(x, y)
                if args.get("clear_before_typing", True):
                    # Mac: Meta, Win/Linux: Control — using Meta for demo simplicity
                    page.keyboard.press("Meta+A")
                    page.keyboard.press("Backspace")
                page.keyboard.type(args["text"])
                if args.get("press_enter", True):
                    page.keyboard.press("Enter")
            elif name == "key_combination":
                # expects string like "Control+A" or "Enter"
                page.keyboard.press(args["keys"])
            elif name == "scroll_document":
                direction = args.get("direction", "down").lower()
                if direction == "down":
                    page.keyboard.press("PageDown")
                elif direction == "up":
                    page.keyboard.press("PageUp")
                elif direction == "left":
                    page.evaluate("window.scrollBy(-400, 0)")
                elif direction == "right":
                    page.evaluate("window.scrollBy(400, 0)")
            elif name == "scroll_at":
                # Move cursor and scroll with wheel
                page.mouse.move(denorm_x(args["x"]), denorm_y(args["y"]))
                magnitude = int(args.get("magnitude", 800))
                direction = args.get("direction", "down").lower()
                dy = magnitude if direction == "down" else -magnitude
                page.mouse.wheel(0, dy)
            elif name == "drag_and_drop":
                sx, sy = denorm_x(args["x"]), denorm_y(args["y"])
                dx, dy = denorm_x(args["destination_x"]), denorm_y(args["destination_y"])
                page.mouse.move(sx, sy)
                page.mouse.down()
                page.mouse.move(dx, dy, steps=10)
                page.mouse.up()
            else:
                print(f"⚠ Not implemented: {name}")
                extra["warning"] = "unimplemented_action"

            # wait for rendering/navigation
            try:
                page.wait_for_load_state(timeout=5000)
            except Exception:
                pass
            time.sleep(0.6)

            results.append((name, extra))
        except Exception as e:
            print(f"❌ Error in {name}: {e}")
            results.append((name, {"error": str(e), **extra}))

    return results

def build_function_responses(page, results: List[tuple[str, Dict[str, Any]]]) -> List[types.FunctionResponse]:
    screenshot = page.screenshot(type="png")
    url = page.url
    responses: List[types.FunctionResponse] = []
    for name, payload in results:
        data = {"url": url, **payload}
        responses.append(
            types.FunctionResponse(
                name=name,
                response=data,
                parts=[types.FunctionResponsePart(
                    inline_data=types.FunctionResponseBlob(mime_type="image/png", data=screenshot)
                )],
            )
        )
    return responses

def main():
    if len(sys.argv) < 2:
        print("Usage: python mini_browser_agent.py \"<your goal>\"")
        sys.exit(1)

    goal = sys.argv[1]
    client = genai.Client()  # will get GEMINI_API_KEY from environment
    print("🎯 Goal:", goal)

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=False)
    context = browser.new_context(viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT})
    page = context.new_page()

    try:
        # 0) first page + first screenshot
        page.goto("https://www.google.com")
        initial_png = page.screenshot(type="png")

        # 1) config with Computer Use tool (browser)
        config = types.GenerateContentConfig(
            tools=[types.Tool(
                computer_use=types.ComputerUse(
                    environment=types.Environment.ENVIRONMENT_BROWSER,
                    # example: can disable dangerous/unnecessary actions
                    # excluded_predefined_functions=["drag_and_drop"]
                )
            )],
            thinking_config=types.ThinkingConfig(include_thoughts=True),
        )

        # 2) initial content (goal + screenshot)
        contents: List[Content] = [Content(
            role="user",
            parts=[Part(text=goal),
                   Part.from_bytes(data=initial_png, mime_type="image/png")]
        )]

        # 3) agent loop
        for turn in range(10):
            print(f"\n----- TURN {turn+1} -----")
            resp = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=config,
            )
            cand = resp.candidates[0]
            contents.append(cand.content)

            # if model didn't return function_call — output text and exit
            if not any(getattr(p, "function_call", None) for p in cand.content.parts):
                final_text = " ".join([p.text for p in cand.content.parts if getattr(p, "text", None)])
                print("\n✅ Done:", final_text)
                break

            # otherwise execute actions and return FunctionResponse with new screenshot
            print("▶ Executing actions…")
            results = exec_calls(cand, page)
            frs = build_function_responses(page, results)
            contents.append(Content(role="user", parts=[Part(function_response=fr) for fr in frs]))

        else:
            print("\n⏹ Reached step limit. Stopping.")

    finally:
        print("\nClosing browser…")
        browser.close()
        pw.stop()

if __name__ == "__main__":
    main()
