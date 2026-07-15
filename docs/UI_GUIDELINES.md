# UI Guidelines

This documents the UI conventions actually in use in `index.html`, so new pages/panels stay
visually and structurally consistent with the rest of the app. It describes what exists today —
it is not a new design system being proposed.

## Theme

MOGO uses a single, fixed dark theme defined as CSS custom properties on `:root`. There is no
light-mode variant and no `prefers-color-scheme`/theme-toggle logic — all colors should be
referenced via the existing variables, never hardcoded:

```css
--bg0 / --bg1 / --bg2 / --bg3      /* background layers, darkest to lightest */
--border / --border2               /* hairline borders */
--green / --green2 / --green-dim   /* wins, positive P&L, "on" states */
--red / --red2 / --red-dim         /* losses, negative P&L, danger actions */
--gold / --gold-dim                /* warnings, "SOON" badges, highlights */
--blue / --blue-dim                /* informational accents, EMA20/50 lines */
--purple                           /* ALEX-strategy accent, AOI zones */
--text1 / --text2 / --text3        /* primary / secondary / tertiary text */
```

## Layout primitives

- **Panels**: each top-level page is a `<div class="panel" id="panel-X">`, hidden by default,
  shown via `showPanel()`. See [ARCHITECTURE.md](ARCHITECTURE.md).
- **Cards**: `.card` is the standard content container — `var(--bg1)` background, `1px solid
  var(--border)`, `10px` radius. Most panel content is a vertical stack of `.card`s.
- **Section labels**: `.section-label` (small, uppercase-weight, `var(--text2)`) introduces a
  card's content — used instead of a heading tag.
- **Stat rows**: `.stats-row` is a 4-column grid of `.stat-card` tiles (value + label), used for
  account/summary metrics (balance, P&L, open count, win rate, etc.) at the top of a page.
- **Empty states**: `.empty-state` (centered, `var(--text2)`, generous padding) is used any time
  a list/table has nothing to show — never leave a blank space where an empty-state message
  belongs, and never fabricate placeholder rows instead.

## Buttons

- Default `button` — outlined, transparent background.
- `button.primary` — filled, `var(--green)` — the single confirming/primary action on a card.
- `button.danger` — outlined in `var(--red)` — destructive or high-consequence actions (Reset
  Account, Clear Test Trades, etc.). Always pair a `.danger` action with a `confirm()` dialog
  that states exactly what will and won't be affected — see the 3-option reset modal
  (`openPaperResetModal()`) as the reference example.

## Status and direction indicators

- `.tag-long` / `.tag-short` — green/red pills for BUY/SELL direction, used consistently across
  the Journal, Paper Trading, and ALEX tables.
- `.badge` — small pill for short status labels (`AUTO`, `TEST`, `SOON`, strategy tags). Compose
  its color from the existing `--*-dim` background + matching solid text color pair, don't invent
  a new color for a new badge.
- Win/loss/positive/negative values are colored `var(--green)`/`var(--red)` directly on the
  number itself (balance, P&L, result), not via a separate icon.

## "Coming Soon" pattern

Any nav item or feature area that isn't built yet uses the shared `comingSoonOpen(title, desc)`
panel rather than a broken link, an empty page, or silently routing to an unrelated existing
page. The description should always say what's planned **and** name the closest already-working
functionality, exactly as the six current Coming Soon nav items do — see
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the current list and their exact wording.

## Toasts and notifications

`.toast` (fixed top-right, slide-in) is used for transient, dismissible confirmations — e.g. an
auto-trade firing. Pair a toast with a desktop `Notification` call where the action can happen
while the tab isn't focused (auto trading, ALEX live setups); never rely on a toast alone for
something the user needs to know about if they've navigated away.

## Blocking/error banners

A persistent (not auto-dismissing) red banner at the top of the relevant panel — not a toast — is
the pattern for a condition that actually blocked an action and needs the user to do something
about it (see the Paper Ledger blocking banner introduced in v11.0.1, `#paperLedgerBlockingBanner`
/ `renderPaperLedgerBlockingBanner()`). This is deliberately **not** gated behind Developer Mode:
if an action didn't happen, every user needs to see why, not just developers.

## Accessibility & fabrication discipline

- Never render a computed statistic, chart marker, or journal field from data that wasn't
  actually stored/computed — an honest "Not Evaluated" / empty-state / "insufficient sample"
  message is always correct where real data doesn't exist. See
  [ADR-004](adr/ADR-004-read-only-analytics-principle.md).
- Escape all user- or API-derived text inserted via `innerHTML` (`escapeHtml()`) — this app had a
  real stored-XSS defect in v2.6 from unescaped AI/journal/scan text; do not reintroduce that
  class of bug in a new feature.
