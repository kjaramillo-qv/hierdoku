# Live headless browsing + gap-analysis against a knowledge base

Two techniques proven when documenting an authenticated SPA (IzyTesting,
`app.izytesting.com`, Angular) and finding what is NOT yet documented.

## A. Drive browser-harness when `browser_exec` says "chrome-not-running" (WSL/headless)

`browser_exec`'s auto-launched daemon may fail with
`chrome-not-running: no supported browser is running and none could be launched`
in a headless WSL box (no `$DISPLAY`, no system Chrome). Do NOT conclude "browser
tools don't work" and do NOT immediately fall back to asset-only extraction — you
can bring up Chrome yourself and drive it live (live nav + real screenshots).

Recipe:

1. Find a Chromium binary. Playwright ships one:
   `/opt/hermes/.playwright/chromium-*/chrome-linux64/chrome` (check
   `PLAYWRIGHT_BROWSERS_PATH`). Confirm with `--version`.
2. Start a virtual display (background process, tracked by Hermes — never nohup/&):
   `Xvfb :99 -screen 0 1920x1080x24`
3. Launch Chrome with remote debugging (background process). Flags that matter:
   `DISPLAY=:99 <chrome> --remote-debugging-port=9222 --no-sandbox \
     --disable-dev-shm-usage --disable-gpu --no-first-run \
     --no-default-browser-check --user-data-dir=/tmp/chrome-izy-profile about:blank`
   - `--no-sandbox` is REQUIRED (else `FATAL: No usable sandbox!`).
   - `--disable-dev-shm-usage` avoids crashes on small `/dev/shm`.
   Verify: `curl -sS http://127.0.0.1:9222/json/version` returns JSON.
4. Point browser-harness at that Chrome via `BU_CDP_URL` and run it through the
   TERMINAL tool with a heredoc (NOT `browser_exec` — its daemon is a separate
   process that does not inherit your env, so setting `os.environ` inside
   `browser_exec` code does nothing). The harness binary lives at
   `~/.local/share/uv/tools/browser-use/bin/browser-harness`:
   ```
   export DISPLAY=:99
   export BU_CDP_URL="http://127.0.0.1:9222"
   browser-harness --reload   # stop any stale daemon so it re-reads env
   browser-harness <<'PY'
   goto_url("https://app.example.com/"); wait_for_load(); print(page_info())
   PY
   ```
   Helpers pre-imported: `goto_url`, `wait_for_load`, `page_info`, `js`,
   `fill_input`, `click_at_xy`, `capture_screenshot`, `cdp(...)`.
   `browser-harness --doctor` diagnoses connection state.

Operational notes:
- The self-launched Chrome can OOM and die mid-session (`BU_CDP_URL ... unreachable`).
  Detect with the `/json/version` curl; relaunch Chrome, `--reload` the daemon,
  and RE-LOGIN (session cookie is lost on a fresh user-data-dir crash only if the
  dir was wiped — reuse the same `--user-data-dir` to keep the session).
- Login: `fill_input("input[type='email']", ...)`, `fill_input("input[type='password']", ...)`,
  then click via JS `[...document.querySelectorAll('button')].find(x=>/log in/i.test(x.textContent)).click()`.
- Angular/Material click handlers often ignore synthetic `.click()`. For those,
  read the element's bounding box and use a REAL click: `click_at_xy(x,y)`.
- Sidebars rendered off-screen (`x` negative in getBoundingClientRect) can't be
  clicked by coords; navigate by URL instead (see B).
- Screenshots land at `~/.config/browser-harness/tmp/shot.png`; copy elsewhere
  before the next capture overwrites it.

## B. Enumerate every route from the JS bundle, then navigate each

For an authenticated SPA you CAN log into, don't hunt the nav by hand — pull the
route table from the compiled bundle and drive each path:

```
curl -sS https://app.example.com/main-<hash>.js -o main.js
grep -oE 'path:"[^"]*"' main.js | sed 's/path://; s/"//g' \
  | grep -vE '[0-9]{3}|,-|L-|V-|Z$|column-boundary' | sort -u
```
(The junk filters drop SVG `path` `d=` attributes, which share the `path:` key.)
This gives the real route list (`dashboard`, `dashboardProject`, `milestones`,
`bugs`, `testCasesAuto`, `manageSuscription`, …). Navigate each with
`goto_url` + `wait_for_load`, and dump `cdp("Accessibility.getFullAXTree")`
roles/names (headings, buttons, tabs) plus `document.body.innerText` to a
per-page file for offline analysis. Many project-scoped routes render blank
until a project is selected — select one first, then re-crawl.

## C. Gap analysis: verify module-by-module, never trust one summary query

**FIRST, find the real source of truth.** A vector-KB / n8n webhook is a LOSSY
PROXY, not the documentation itself. Before trusting ANY gap analysis against it,
check whether an authoritative docs repo exists on disk (or ask the user). In one
session the webhook-driven analysis produced a whole folder of "gap" documents —
Tablero del proyecto, Casos automatizados, Plan y facturación, Tokens CI/CD,
Generar informe, Realizar predicción — that were ALL already fully documented in a
`documentacion_referencia/` Docusaurus repo the webhook simply did not surface.
Recon step: `search_files(target="files", pattern="*.md")` under any
`*referencia*` / `*documentation*` dir, and grep it for the module names, BEFORE
writing anything. Only genuinely-absent-from-the-repo items are real gaps.

When you must fall back to the webhook (no repo on disk), a single broad KB query
("summarize all documentation for X") returns an INCOMPLETE inventory — in
practice it listed 8 modules but omitted several (Hitos, Agentes, Escenarios,
Bugs) that DID exist on re-check. Even per-module SI/NO webhook answers can be
wrong (they reported gaps for modules the real repo documented). So:

1. Build the ground-truth feature list from the live app (A + B above).
2. For EACH feature, fire a targeted KB query: "Does a document about <module X>
   exist? Answer only SI/NO and the exact title." (see the
   `knowledge-base-webhook` skill). Treat only these per-item answers as
   authoritative for presence/absence.
3. Document only the confirmed gaps. Clone the org's existing doc style/structure
   (headers, element tables, paso-a-paso, corporate palette) — read one existing
   example doc first.

## D. Updating an existing docs repo (Docusaurus) — match conventions + register in sidebar

When the target is a real docs repo (not a loose folder), do NOT invent your own
format. Read 2-3 sibling `.md` files first and copy their exact conventions:

- Image paths are Docusaurus-absolute: `![alt](/img/file.png)` (served from
  `static/img/`), NOT relative `static/img/...`. Copy your screenshot INTO the
  repo's `static/img/` with a collision-free name before referencing it.
- Body style is usually `##`/`###` headings + descriptive bullet lists +
  admonitions (`:::note`, `:::important`) — NOT the "Elemento | Tipo | Descripción"
  tables a from-scratch doc might use. Some files carry YAML frontmatter
  (`sidebar_position`, `title`, `description`); many do not — match the siblings
  in that same category folder.
- Videos embed with explicit sizes (`<video width="640" height="360" controls>`
  for tutorials, `420x300` inline). This is what "the correct measurements"
  refers to.

CRITICAL — the sidebar is often MANUAL. Check `sidebars.js`/`sidebars.ts`: if it
lists every doc path by hand (`items: ['Módulo X/Page', ...]`) rather than
`type: 'autogenerated'`, a new `.md` file will NOT appear until you add its path
to the correct category (or add a new category block). After editing, validate
with node: `node -e "const s=require('./sidebars.js'); console.log('ok')"` — the
file frequently has pre-existing syntax errors in commented-out blocks, so
confirm the ACTIVE export parses and your new entry is present. Category folders
generally do NOT each need a `_category_.json` (only the docs root had one).

When gap analysis turns out to be a false alarm (repo already complete), say so
plainly and create ONLY the one genuinely-missing page — do not duplicate
existing docs to look productive.
