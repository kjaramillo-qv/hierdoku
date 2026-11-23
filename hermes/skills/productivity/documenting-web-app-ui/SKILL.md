---
name: documenting-web-app-ui
description: Document web or Electron SPA UI from real assets.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [documentation, web, spa, ui, extraction, branding, markdown]
    related_skills: [izydata-knowledge-base]
---

# Documenting a Web or Electron SPA UI from Real Evidence

Write user-facing documentation for web and Electron SPA screens (login, forms,
dashboards, recorders) grounded in what the application ACTUALLY ships or shows —
real labels, button text, validation messages, and corporate colors — never guesses.

## When to Use

- You are asked to document a web-app screen/flow and are given its URL.
- You are asked to document an installed Electron desktop app whose renderer is
  a React/Vue/Vite-style SPA.
- You need the app's real corporate palette, fonts, and copy for a manual.
- Don't use for: documenting a backend/API with no UI, or when the user gives
  you the exact text to document verbatim.

For packaged Electron applications, use
`references/electron-packaged-ui-evidence.md` to recover exact shipped UI copy
from a disposable extraction of `app.asar`. This supplements requirements and
live observation; it never substitutes for verified screenshots.

When browser automation cannot launch inside WSL but Windows Chrome is mounted,
use the validated CDP fallback and production-safe inspection rules in
`references/wsl-windows-chrome-cdp.md`.

When a persistent Chromium profile may already hold authenticated tabs, or the
manual combines live UI, requirements, legacy screenshots, and package/vendor
facts, follow `references/authenticated-cdp-and-cross-source-validation.md`.
It includes exact-page selection, expired-session handling, command validation,
and screenshot acceptance checks.

When updating the organization's real documentation repository in place, follow
`references/safe-in-place-docs-update.md`: back up first, map additions into the
existing functional pages, preserve all prior content, create a new page only
when structurally necessary, and prove the real docs build still succeeds.

## Explain technical controls for end users

When the user asks for more detail, do not merely add jargon or longer lists.
Explain each concept in this order:

1. Plain-language definition and purpose.
2. A familiar analogy when helpful (for example, a selector is an element's
   address, while its display name is the human-readable label).
3. The exact options confirmed by requirements or the live UI.
4. What information each option asks the user to provide.
5. One realistic end-to-end example.
6. How to choose between similar options and what a failure means.

For action catalogs, document each action separately: what it does, when to use
it, required fields, and a short example. Distinguish interaction from
verification (for example, "touch" performs an action; "verify visible" checks
its result). Do not present unconfirmed or merely proposed options as available.

When machine-facing labels must appear (such as locator types), retain the exact
UI/requirements term but immediately explain it in everyday language. Keep the
manual functional and user-facing; implementation details belong only in the
evidence notes, not in the published instructions.

## Core principle

If you can't render the page, extract the truth from the shipped assets. Modern
SPAs (React/Vue + Vite/Tailwind) ship an almost-empty HTML shell; the real
strings and colors live in the compiled JS and CSS bundles. Get them from there
rather than inventing plausible UI text.

## Documenting an authenticated app / finding what's NOT yet documented

When you CAN log in and the task is a gap analysis ("document everything not
already in the knowledge base"), prefer live crawling over asset scraping:
enumerate every route from the JS bundle, navigate each authenticated page,
then verify presence module-by-module. CRITICAL: a vector-KB / webhook is a
LOSSY PROXY — first hunt for the REAL docs repo on disk (`search_files` for
`*referencia*`/`*.md`); a webhook "gap" is often already fully documented in a
repo the webhook never surfaced. A single broad "summarize all docs" query is
especially unreliable and omits real modules. When updating an existing docs
repo (e.g. Docusaurus), match its conventions and register new pages in the
manual `sidebars.js`. Full recipe — headless-Chrome bring-up, route extraction,
source-of-truth recon, per-module verification, and Docusaurus-repo updates — in
`references/headless-browser-and-gap-analysis.md`.

## Procedure

1. Fetch the page HTML. It will likely be a shell with `<div id="root">` and
   `<script src="/assets/index-*.js">` + `<link href="/assets/index-*.css">`.
   - Completion: you have the asset filenames referenced by the shell.
2. Download the compiled CSS and JS bundles (the hashed `/assets/*.css` and
   `/assets/*.js`).
3. Extract real UI copy from the JS bundle — grep for quoted strings matching
   the domain words (login page example, Spanish):
   `grep -oiE '"[^"]{0,50}(sesi[oó]n|ingres|olvid|contrase|usuario|correo|email|password)[^"]{0,50}"' app.js | sort -u`
   This yields titles, placeholders, button labels, validation messages, and
   route paths (`/forgot-password`, `/reset-password`).
4. Extract the corporate palette from the CSS. Tailwind emits CSS variables;
   the brand colors are the NON-default ones, usually named explicitly:
   `grep -oE -- '--color-brand-[0-9]+:#[0-9a-fA-F]{6,8}' app.css`
   Also grab `--font-sans` for the typeface. Ignore the standard Tailwind
   `--color-red-*`, `--color-blue-*` etc. — those are framework defaults, not
   branding. The lowest-index `brand-500`-style token is typically the primary.
5. Write the doc in the format the org uses (often Markdown `.md`, paso-a-paso:
   Introducción → Requisitos previos → Descripción → Paso a paso → Resultado
   esperado → Mensajes del sistema → Colores corporativos → Notas).
6. If the manual contains installation commands, validate package name, runtime
   requirement, environment-variable names, URL syntax, and placeholders against
   authoritative package/vendor documentation. Do not silently copy a malformed
   user-supplied command; explain the discrepancy and publish the verified form.
7. Validate every screenshot against its caption: opening a selector, choosing
   items, confirming a selection, and viewing a result are different steps and
   should not be described interchangeably.
8. State your evidence source honestly. If you documented from HTML/CSS/JS,
   requirements, or older official screenshots because you couldn't capture the
   current live page, SAY so. Never present inferred or legacy content as a live
   observation.

## Pitfalls

- Do NOT deliver a parallel “new updates” manual when the user asked to update
  the real documentation. Integrate each addition into the existing functional
  page; create a new page only for a genuinely new feature with no coherent
  home. When the user requires preservation, back up first and verify that no
  original page or prior content was removed.
- Do NOT invent labels, button text, or error messages. If a string isn't in
  the bundle, don't document it.
- A Tailwind CSS dump contains hundreds of default colors; the brand palette is
  the handful under `--color-brand-*` / `--color-<name>-*` custom names, not
  the framework's `red/blue/slate/gray` scales.
- SPA HTML is a shell — extracting only the HTML gives you nothing. You MUST
  pull the JS/CSS bundles.
- Raw-IP + plain-HTTP URLs will trigger a security-scan approval prompt on the
  terminal tool; that's expected, proceed once approved.
- If a headless browser (Chrome) isn't running you can't screenshot. Before
  falling back to asset-only extraction, try bringing Chrome up yourself: in a
  WSL/headless box, `browser_exec` may report `chrome-not-running`, but you can
  launch Xvfb + Chromium with `--remote-debugging-port` and drive browser-harness
  via `BU_CDP_URL` from the TERMINAL tool — that restores live navigation AND real
  screenshots. Full recipe in
  `references/headless-browser-and-gap-analysis.md`. Only fall back to asset
  extraction if that fails, and note the missing screenshots.
- When a corporate knowledge base has no formal branding/style guide, the
  extracted app palette IS the authoritative source of the real colors.

## Time-sensitive authentication (2FA / OTP)

For authenticated UI documentation, establish and verify the live browser
session before asking the user for a one-time code:

1. Start or reconnect the browser and load the login page.
2. Submit the username and password, then confirm that the OTP screen is
   actually visible and ready for input.
3. Only then ask for the current code and enter it immediately.
4. Do not restart the login flow after the code is issued: many applications
   generate a new code on every login attempt and invalidate the previous one.
5. Verify successful navigation to the authenticated area before claiming that
   access was completed.

If the normal browser harness cannot attach but a real Chromium executable is
available, a validated fallback is to start Chromium with a remote debugging
port and use Playwright's `chromium.connectOverCDP(...)` against that live
session. Keep credentials and OTPs in process environment variables rather
than writing them into scripts or documentation. Treat this as a live-browser
fallback, not a reason to replace real UI evidence with asset guesses.

## Config-driven documentation workflows

Some deployments define the documentation process in
`agent.personalities` inside the profile `config.yaml` (for example, a
"Documentador Funcional Oficial" flow). That personality/config GOVERNS the
task and OUTRANKS any narrower skill's framing (such as an "answer only from
the vector KB" skill). Read the personality, follow its question sequence and
save-path rules, and treat a knowledge base only as a style/context reference
when the config says the source of truth is the live app or a user-provided
link. Keep the output user-facing and functional: explain what the user sees
and does, without exposing implementation details.
