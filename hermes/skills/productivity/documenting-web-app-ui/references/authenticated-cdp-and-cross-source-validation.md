# Authenticated CDP reuse and cross-source validation

Use this when updating documentation for an authenticated SPA and a previously
launched Chromium profile may already contain useful logged-in tabs.

## Reuse a live authenticated browser safely

1. Inspect running Chromium command lines for a `--remote-debugging-port` and a
   persistent `--user-data-dir`; do not print cookies, tokens, or storage values.
2. Query `http://127.0.0.1:<port>/json/list` and inspect only page title, URL, and
   type. A loaded internal page can remain usable even when a fresh navigation
   would require login again.
3. Attach with Playwright `chromium.connectOverCDP(...)`; select the page by an
   exact URL fragment, not the first page in the context (contexts may contain
   login, OTP, stale, local-agent, and authenticated tabs together).
4. Read `body.innerText`, visible labels, placeholders, select options, and
   visible controls. Capture the page before changing state.
5. For modal documentation, open the modal but do not submit it. Capture empty
   sensitive fields and close the modal afterward.
6. If a fresh navigation reports an expired token, do not describe cached UI as
   proof that other routes are current. Use already captured evidence, shipped
   assets, requirements, and the authoritative docs repo, and label each source.

## Cross-source validation hierarchy

For each documented claim, classify the evidence:

1. Live UI observation: exact labels, fields, options, validation controls.
2. Authoritative product requirements: new behavior not yet visible in the
   deployed UI.
3. Existing official documentation/screenshots: navigation pattern and visual
   continuity; not proof of newly added fields.
4. Package/vendor documentation: prerequisites, exact environment variable
   names, supported versions, and provider-specific credential locations.
5. User-provided requirements: business rules and desired warnings.

Never merge these categories silently. A legacy screenshot may illustrate where
a step occurs, but the caption must say when its selected type or fields belong
to an older flow. Do not present a Web screenshot as a Mobile result.

## Validate commands before publishing them

When the user supplies a command for end-user documentation:

- Preserve the supplied text in evidence notes.
- Validate package name, minimum runtime, environment variable names, URL syntax,
  and placeholder spelling against authoritative package metadata/README.
- Do not silently publish a malformed command. Explain the discrepancy and put
  the verified working command in the manual.
- Keep placeholders visibly fake and consistent (for example `TU_TOKEN`), and
  warn that the command becomes sensitive after substitution.

## Screenshot acceptance checks

- Empty password/token/access-key fields.
- No real secrets in page text, table cells, browser chrome, or terminal output.
- Image is non-empty, valid PNG/JPEG, and referenced by the Markdown.
- Caption describes exactly the visible action (for example, “open scenario
  selector” versus “save selected scenarios”).
- If names, roles, organizations, or internal integration aliases are visible,
  classify them as internal metadata and anonymize before external publication.
