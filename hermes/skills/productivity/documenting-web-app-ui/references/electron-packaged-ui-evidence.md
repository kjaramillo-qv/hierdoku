# Recovering exact UI evidence from a packaged Electron SPA

Use this when the installed desktop application is Electron-based, live desktop automation is unavailable, and user-facing labels or flow details must still be grounded in the shipped application rather than guessed.

## Scope and evidence boundary

This method recovers exact text, controls, states, and bundled version information from the installed application assets. It is valid textual evidence, but it is not a live walkthrough and does not replace real screenshots. In the final documentation, distinguish:

- Observed live behavior: verified by driving the running application.
- Shipped UI evidence: verified in the installed bundle.
- Requirement-only behavior: stated by a requirement but not independently verified.

Never describe bundle-derived content as if it was clicked or observed running.

## Procedure

1. Locate the installed executable.
   - If the user provides a Windows `.lnk`, inspect its UTF-16 strings:
     `strings -el ".../Application.lnk"`
   - Confirm the resolved executable and installation directory before continuing.

2. Find the Electron archive, usually `<install>/resources/app.asar`.

3. Extract to a disposable workspace under the agent's writable cache:
   `npx --yes @electron/asar extract "<install>/resources/app.asar" "<workspace>/app-asar"`

4. Locate the rendered SPA assets, commonly:
   - `dist/index.html`
   - `dist/assets/*.js`
   - `dist/assets/*.css`
   - `dist-electron/main.js` and `preload.js`

5. Make minified bundles searchable. Formatting a disposable extracted copy is safe:
   `npx --yes prettier --write "<workspace>/app-asar/dist/assets/<bundle>.js"`

6. Search for domain labels and read a bounded surrounding range. Useful targets include:
   - page and navigation titles;
   - button labels;
   - field labels and placeholders;
   - status names;
   - success/error messages;
   - onboarding or requirement text;
   - version constants.

7. Build the user-facing flow only from strings and nearby control conditions that are actually present. Cross-check requirements and prior manuals for terminology.

8. Still obtain and verify real screenshots before calling the illustrated documentation complete. If screenshots are blocked, deliver the text as a clearly labeled draft and state what remains unverified.

## Useful packaged-app clues

- `package.json`, executable metadata, or `.lnk` descriptions often confirm that the app is Electron.
- `preload.js` exposes the desktop actions available to the renderer.
- Adjacent conditions around labels can reveal when a button appears (for example, only after recording stops or when captured items exist).
- Export success/error copy is often near the request that sends data to the web platform.

## Pitfalls

- Do not edit the installed `app.asar`; extract and inspect a copy.
- Do not expose tokens, API keys, authorization headers, internal endpoints, or source-code details in end-user documentation.
- Do not let technical bundle names leak into a functional manual.
- A successfully extracted asset proves that the copy ships with the app, not that every path works at runtime.
- Rendering `file://.../index.html` without Electron APIs may show an incomplete or misleading state; treat it as a convenience probe, not authoritative live evidence.
