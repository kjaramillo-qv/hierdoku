# WSL fallback: inspect a Windows Chrome session over CDP

Use this only when normal browser automation cannot launch a browser inside WSL, but a Windows Chrome executable is mounted and the task requires real authenticated UI evidence.

## Validated approach

1. Launch Windows Chrome headlessly from WSL with a dedicated disposable profile and remote debugging enabled:

```bash
'/mnt/c/Program Files/Google/Chrome/Application/chrome.exe' \
  --headless=new \
  --remote-debugging-port=9222 \
  --remote-debugging-address=0.0.0.0 \
  --user-data-dir='C:\Users\<user>\AppData\Local\Temp\chrome-docs' \
  --no-first-run --no-default-browser-check about:blank
```

Adapt `/mnt/c` to the actual host mount. Verify `http://127.0.0.1:9222/json/version` before continuing.

2. If Playwright/Selenium is unavailable, use a small Python CDP client with `websocket-client`:

```bash
uv run --with websocket-client python cdp_probe.py
```

Read the page target from `/json/list`, connect to its `webSocketDebuggerUrl`, then use:

- `Page.navigate` for navigation.
- `Runtime.evaluate` for DOM text and selectors.
- `Input.dispatchMouseEvent` for real clicks.
- `Page.captureScreenshot` for evidence.
- `Emulation.setDeviceMetricsOverride` for a stable viewport.

3. For Angular/Material controls, synthetic `element.click()` may not open menus. Use this sequence instead:

- Call `scrollIntoView({block: 'center'})`.
- Read `getBoundingClientRect()`.
- Dispatch `mouseMoved`, `mousePressed`, and `mouseReleased` at the center point.

Collapsed sidebars may place controls at negative x coordinates. Expand the sidebar first using its visible burger/logo control. If responsive CSS still moves it off-screen, temporarily expose the sidebar only for inspection by overriding its transform/left styles; do not treat that temporary presentation as product behavior.

## Safe production inspection

Production documentation must be read-only unless the user explicitly approves a change.

- Open navigation menus, tabs, and creation dialogs to record labels and validation rules.
- Do not submit create, generate, delete, execute, or save actions merely to discover the next screen.
- If a button opens a modal before committing, inspect the modal and cancel it.
- Hidden modal DOM may reveal labels and validation copy, but document only options actually rendered by the shipped UI; do not claim a successful workflow step that was never executed.
- Capture both the list/empty state and the open form when each explains a different part of the flow.
- After inspection, verify that no record or credential was created and say so in the completion report.

## Credential handling

Prompt interactively or pass credentials through process input/environment. Never write passwords or generated keys into scripts, screenshots, documentation, skills, or logs intended for users.

## Screenshot verification

Copy each capture into the documentation image directory before taking the next screenshot if the CDP script reuses one output filename. Verify every referenced image exists, is non-empty, and visually matches the documented state.
