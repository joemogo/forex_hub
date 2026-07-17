# Security

MOGO is a single-file, client-only application with no server and no backend (see
[ARCHITECTURE.md](ARCHITECTURE.md)). This document describes what that architecture does and does
not protect against, what data is sensitive, how it is currently handled, and the boundaries this
project has deliberately drawn for itself. It was written for the v12.1.3 Security Baseline
release and should be updated whenever a future release changes any of the below.

## Threat model

MOGO runs entirely in the user's own browser, on the user's own device, from a static file served
by GitHub Pages (or opened locally). There is no multi-user access, no account system, and no
server MOGO controls. The realistic threats this release addresses are:

1. **Script-injection (XSS) via unescaped rendering** of data that could contain attacker-controlled
   text, even though no such live injection path exists today (see below).
2. **Casual shoulder-surfing / device-sharing exposure** of account ID, balances, and credential
   fields while the user has stepped away from an unlocked browser tab — addressed by Manual Lock.
3. **Unintended external network/script dependencies** that expand the app's attack surface for no
   functional reason (the dead Google Fonts import, removed this release).
4. **Accidental destructive or state-changing actions** — a misclick that starts/stops automated
   trading, deletes a journal record, or resets an account — addressed by confirmation dialogs.

MOGO does **not** defend against, and cannot defend against, an attacker who already has control of
the user's device or browser profile (malware, another logged-in local user, browser extensions
with full page access, etc.) — no client-only, backend-less architecture can. Manual Lock is
explicitly labeled as a privacy barrier, not authentication, for this reason.

## Credential handling

**The two credentials in this app have deliberately different persistence behavior — this is not
an inconsistency, and no v12.1.3 claim should ever compress them into one blanket statement:**

- The OANDA API token is never persisted anywhere, in any form.
- The OANDA token is not exposed in diagnostics, exports, alerts, logs, or serialized state.
- The Anthropic key is currently persisted, **by design**, in `localStorage['fxhub_ai_key']` only
  after the user explicitly clicks "Save Key" — it remains persisted until "Clear Key" is clicked.
- The Anthropic key is not exposed in HTML output, URLs, diagnostics, exports, alerts, or logs.
- `clearAiKey()` removes the Anthropic key from both memory (`aiChat.key`) and `localStorage`.
- The existing direct-browser Anthropic integration is frozen and documented as temporary (below).
- No new MOGO AI feature may use this client-side key architecture.
- Future MOGO AI requires a secure backend or serverless endpoint.

### OANDA API key and account ID

`cfg.key` and `cfg.accountId` are **held in memory only** for the lifetime of the browser tab and
are **never written to `localStorage`** anywhere in the codebase (verified by direct code
inspection of every reference, cross-checked independently twice for this release). `disconnect()`
clears both the in-memory `cfg` object and the visible `#apiKey`/`#accountId` input fields (the
latter fixed in v12.1.3 — previously only `#apiKey` was cleared).

The token is sent only via the `Authorization: Bearer` HTTP header on OANDA API calls, never in a
URL or query string. `cfg.accountId` does appear in the request URL path — this is required by
OANDA's own REST API design, not a MOGO choice, and the account ID alone is not a secret credential.

### Anthropic API key — temporary design, disclosed

Unlike the OANDA token, the Anthropic key (`aiChat.key`) **is** persisted to
`localStorage['fxhub_ai_key']`, by explicit user action only (the "Save Key" button) — this has
been disclosed in [STORAGE_KEYS.md](STORAGE_KEYS.md) since it was introduced and remains disclosed
here. Verified for this release:

- Entered via a `type="password"` field, cleared immediately after save.
- Never interpolated into any `innerHTML`, never `JSON.stringify`'d, never logged, never included
  in the Diagnostics self-test message, never referenced by any export function.
- Transmitted only via the `x-api-key` header, never in a URL.
- Sent using Anthropic's own `anthropic-dangerous-direct-browser-access: true` opt-in header —
  the provider's own naming signals that unproxied browser-to-API calls are a discouraged pattern
  outside personal/local use. MOGO's own error handling (`sendAiMessage()`) already anticipates
  CORS failures depending on hosting context, confirming this design is known to be
  context-fragile, not a fully reliable production pattern.

**This design is temporary and is not being expanded.** Future AI Security Boundary rule, in force
starting this release:

- Future MOGO AI features must go through a secure backend or serverless endpoint.
- No paid AI-provider key may be embedded in source, committed to Git, or stored in `localStorage`.
- The browser must never receive the permanent provider credential.
- The current direct-browser Anthropic implementation is frozen as-is (AI Assistant chat only) and
  must not be expanded with additional AI features until this boundary is built.

## Manual Lock (v12.1.3)

A local, client-side privacy barrier, added to the top-right of the topnav ("🔒 Lock" /
"Unlock"). **This is not authentication** — it has no password, does not protect `localStorage`
contents from anyone with device access, and is disclosed as such directly in its own UI.

While locked:
- A full-screen overlay conceals the entire app (account ID, credential fields, balances, and
  every other on-screen detail) beneath it.
- Credential changes (`connect`/`disconnect`/AI key save/clear), automation toggles, destructive
  actions (journal delete, paper/ALEX resets, test-trade clearing, reconciliation, balance
  override, chat-history clear), and Manual Review approval are all blocked with a message to
  unlock first.
- Scanner polling, chart updates, paper-position monitoring, and any automation already running
  are **untouched** — none of these are paused, since locking is a pure presentation/interaction
  gate, not a pause on the app's own background operation.
- Toast alert popups (rendered above the lock overlay) continue to appear, using their existing
  non-sensitive text (pair, direction, confidence %, time) — no account-sensitive data.
- Locking/unlocking itself never creates, closes, or alters any trade.

The locked/unlocked state is stored as a plain boolean flag (`fxhub_lock`, `'1'` or absent) so a
page reload doesn't silently unlock the app — this flag carries no sensitive data. Unlocking is a
single deliberate click, with no additional verification, consistent with the "not authentication"
disclosure above.

## XSS / rendering safety

`escapeHtml(str)` (5-character HTML-entity escaper: `& < > " '`) is the app's one centralized
escaping helper. As of v12.1.3, every known interpolation site that renders potentially
user-influenced text into `innerHTML` uses it, including two gaps closed this release:

- `renderAlertLog()` — previously interpolated `pair`/`sigs`/`direction`/`time`/`pct` unescaped.
  No live free-text path was found feeding these fields (they come from a fixed pair list and
  hardcoded label strings), but the render function itself provided no defense-in-depth escaping.
- `inspectorRows()` — previously interpolated its `val` argument unescaped. Its current callers
  all pass either plain computed text/numbers or (for the two rows that render HTML badges,
  Strategy and Direction) pre-built trusted markup — those two rows were pulled out of the
  generic escaping path so the badges continue to render correctly rather than being
  double-escaped into visible tag text.
- Six `fmtDash(r.pair)` sinks — `fmtDash()` itself only substitutes a dash for a missing value,
  it never escapes. A dedicated security fixture (`tests/v1213_security_baseline_tests.js`)
  caught one of these live: `renderTradeInspectorContent()`'s own header line rendered
  `fmtDash(r.pair)` unescaped even after its `inspectorRows()`-based overview section (a few
  lines above, in the same function) was already fixed to escape the identical field — an
  inconsistency worth closing on its own. The same audit found five more identical sinks
  (two mini-journal row renders, the same Trade Inspector header, the Strategy Center hero
  name, and one more mini-journal-style row) — all six now wrapped in `escapeHtml()`. As with
  the two sinks above, no live free-text path was found feeding `r.pair` (it is always either
  dropdown-selected or scanner/pair-list-derived), but leaving any of them unescaped after
  finding the others would have been an inconsistent, avoidable residual gap.

Everywhere else audited this release (journal notes, Trade Inspector notes, AI Assistant messages,
chart drawing labels/text, scanner pair notes, Academy homework/lesson notes) was already
consistently escaped at every render site.

## Content Security Policy — built, tested, not yet in production

A CSP was built and tested this release but is **not** in the production `index.html`, pending
your explicit approval (per your instruction: an enforcing `<meta http-equiv="Content-Security-Policy">`
can only be verified in a scratch/dev copy, and `Content-Security-Policy-Report-Only` cannot be
set via `<meta>` at all — it is HTTP-header-only, which GitHub Pages does not let this repository
control).

Proposed policy:

```
default-src 'self';
script-src 'self' 'unsafe-inline' https://unpkg.com;
style-src 'self' 'unsafe-inline';
img-src 'self' data:;
font-src 'self';
connect-src 'self' https://api-fxpractice.oanda.com https://api-fxtrade.oanda.com https://api.anthropic.com;
object-src 'none';
base-uri 'self';
form-action 'self';
frame-ancestors 'none';
```

`'unsafe-inline'` is required for both `script-src` (hundreds of inline `onclick=` handlers) and
`style-src` (the single inline `<style>` block plus per-element `style=""` attributes) because the
whole app is one inline-script, inline-style file with no build step — converting every inline
handler/style to an external, nonce/hash-based equivalent would be a large, high-regression-risk
rewrite explicitly out of scope for this release. **Honest limitation**: this means the CSP cannot
block a newly-injected inline `<script>` tag if some future/undiscovered escaping gap were ever
exploited — its real value here is closing off unexpected external script/connect/frame
destinations (a second layer against supply-chain/typosquatting-style risks), not inline-script
XSS specifically. A stronger, nonce-based CSP requires a real backend/build step capable of
generating a per-load nonce and setting real HTTP headers — tracked as future work, not this
release's scope.

**Verification performed** (scratch copy served over local HTTP, not the production file):
- Confirmed a genuine CSP block (`securitypolicyviolation` event, `connect-src` directive) against
  a deliberately non-allow-listed host, proving the policy actively enforces rather than silently
  passing everything.
- Confirmed no CSP violation against any of the three allow-listed `connect-src` hosts (both OANDA
  hosts, Anthropic).
- Confirmed the `unpkg.com` chart library still loads (`window.LightweightCharts` defined) and the
  setup screen renders fully styled with working inline `onclick` handlers.
- Not exercised: an authenticated live OANDA `connect()` call end-to-end (no real OANDA credentials
  available in this environment — the same disclosed limitation noted throughout this project's
  history for anything requiring live broker credentials).

If approved, the same `<meta>` tag will be added to production `index.html` in a follow-up change,
verified live in-browser (Charts, Scanner, Replay, exports, Anthropic connectivity), and disclosed
in the release notes. Until then, this is documented as a **pending limitation**: MOGO ships v12.1.3
without a CSP.

## Dependency / external-resource inventory

| Resource | Purpose | Notes |
|---|---|---|
| `https://unpkg.com/lightweight-charts@4.1.3/...` | Charting library (`<script src>`) | Only external script in the app. |
| `https://api-fxpractice.oanda.com`, `https://api-fxtrade.oanda.com` | OANDA REST API | Token via `Authorization: Bearer` header only. |
| `https://api.anthropic.com` | AI Assistant chat | Key via `x-api-key` header only; see Anthropic section above. |
| ~~`https://fonts.googleapis.com`~~ | ~~Google Fonts (`Dancing Script`)~~ | **Removed in v12.1.3.** Loaded a font for `.jvm-signature`, a CSS class applied to zero elements anywhere in the app (a dead v7.0 rebrand leftover). Deleting it removes an entire external CDN dependency with no functional loss. |

No images, no analytics/tracking scripts, no other stylesheets, and no other external hosts exist
anywhere in the app.

## GitHub and repository safety

- No secrets exist in tracked files or git history — verified this release by a two-pass scan
  (current tracked files, and separately `git log --all -p`) for common secret patterns
  (`sk-ant-`, generic `sk-`, `AIza`, `AKIA`, PEM private-key headers, generic password/api-key
  assignment, Bearer tokens). The only match in either pass was the harmless UI placeholder string
  `placeholder="sk-ant-..."` in `index.html` and the frozen `index-v2.9-KNOWN-GOOD.html` reference.
- `.gitignore` documents that MOGO never stores API keys server-side — this remains accurate for
  the OANDA token (memory-only) and is now cross-referenced against the Anthropic key's actual,
  disclosed, client-side-persisted design above, so the two statements don't read as contradictory.
