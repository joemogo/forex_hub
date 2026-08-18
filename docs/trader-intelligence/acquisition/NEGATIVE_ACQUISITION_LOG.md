# Negative Acquisition Log

**Purpose.** A durable record of sources that were checked and did **not** close the gap they
were checked against, so a future session does not repeat the search. A negative result here is
a finding, not a failure.

**Status: append-only. Adjudicates nothing, promotes nothing, authorises no trade.**
Nothing in this file is evidence about a trader's method. Every row records what was
retrieved and why it does not close a gap.

**Rules for appending.**
- One row per source *actually retrieved*, with the retrieval date and the HTTP result.
- State the gap/question it was checked against, by id.
- State the failure class exactly. The four classes are distinct and must not be blurred:
  - `SOURCE_DOES_NOT_STATE` — retrieved successfully; the content simply does not contain the fact.
  - `CONTENT_NOT_RETRIEVABLE` — the source plausibly states the fact, but its content cannot be obtained.
  - `ACCESS_BLOCKED` — login, paywall, rate limit or bot protection stands between us and the page. Not bypassed.
  - `WRONG_ATTRIBUTION` — retrieved and informative, but not attributable to the trader in question.
- Never upgrade a row to a positive result by reasoning about it. Only new retrieval does that.

---

## Session 2026-08-18 — MOGO-022 research acquisition

Scope: the three binding gaps `GAP|20260817|006` (TJR observed trades), `GAP|20260817|007`
(ALEX_G observed trades), `GAP|20260817|008` (RAYNER_TEO observed trades), and the TJR
stated-rule blockers `GAP|20260727|002` (entry_trigger), `GAP|20260727|003` (risk_percentage),
`GAP|20260817|001` (stop_placement).

Method: `curl` with a normal browser User-Agent, plus web search for discovery. No login was
used, no paywall or bot protection was bypassed, and no consent banner was accepted.

### N-1. The binding retrieval blocker

| # | Source | Retrieved | Result | Checked against | Class |
|---|---|---|---|---|---|
| N-1.1 | `https://www.youtube.com/api/timedtext?v=8PYgFVB0GHE&…&kind=asr&lang=en` (signed caption URL taken from the live watch page) | 2026-08-18T15:12Z | **HTTP 200, 0 bytes** | all TJR stated-rule gaps | `CONTENT_NOT_RETRIEVABLE` |

This re-confirms the constraint established in an earlier session, on a freshly-signed URL, and
it was checked **once**, deliberately, not retried. Everything else in the TJR column of this
log follows from it.

What *does* work from this environment, confirmed the same day: channel pages, `/videos`,
`/streams`, `/playlists`, `playlist?list=…`, and `watch?v=…` all return HTTP 200 with full
`ytInitialData` / `ytInitialPlayerResponse`. So **titles, durations, publish dates, playlist
membership and full video descriptions are obtainable; spoken content is not.**

Caption-track inventory, checked on 16 priority TJR videos spanning 2023-06-07 to 2026-06-05:
**every one carries `en/asr` only.** There is no publisher-authored caption track anywhere in
the sampled set. Consequence: even if the caption endpoint were opened, or a transcript were
obtained through the operator's own browser, the text would be **machine-generated** and would
carry unverified fidelity to the spoken audio — the same `provenanceStatus: partially_verified`
ceiling the corpus already records on `EVSRC|TJR|20260727|002`. No route found in this session
raises that ceiling.

### N-2. TJR — sources retrieved that do not state entry, stop or risk

| # | Source | Retrieved | What was found | Checked against | Class |
|---|---|---|---|---|---|
| N-2.1 | YouTube video descriptions, all 6 fetched in full (`8PYgFVB0GHE`, `Vulini8xbB0`, `_zzxRMbyE44`, `vGYKloNLKAw`, `akkPDEAm1jw`, `EMSTUOAtCo0`) | 2026-08-18 | Byte-for-byte the same boilerplate block on every video: an affiliate link to `go.tjrtrades.com/blueprint-*`, an indicator link, a funded-account raffle form, four broker/prop-firm referral links, and an income disclaimer. **Zero methodology text. No chapter markers on any of them.** | `GAP|20260727|002`, `GAP|20260727|003`, `GAP|20260817|001` | `SOURCE_DOES_NOT_STATE` |
| N-2.2 | `https://go.tjrtrades.com/blueprint-km5bykx` → redirects to `https://learn.tjrtrades.com/blueprint` | 2026-08-18 | HTTP 200, public, no login required. A paid-mentorship application funnel. Page text is a headline, a testimonial disclaimer and ~2,500 words of legal disclaimers. **No strategy content whatsoever.** | TJR stated-rule gaps | `SOURCE_DOES_NOT_STATE` |
| N-2.3 | `https://www.tjrtrades.com/` | 2026-08-18 | HTTP 200, redirects to the same `learn.tjrtrades.com` funnel. Not a content site. | TJR stated-rule gaps | `SOURCE_DOES_NOT_STATE` |
| N-2.4 | `https://x.com/tjr_trades` | 2026-08-18 | **HTTP 404.** Handle does not resolve. No verified TJR account handle was established in this session; X is in any case login-walled for systematic reading and was not pursued further. | `GAP|20260817|006` | `ACCESS_BLOCKED` |
| N-2.5 | `https://whop.com/tjr-trades/` | 2026-08-18 | HTTP 200 but redirects to `whop.com/joined/tjr-trades/` — a paid community storefront. Course content sits behind purchase. **Not pursued: acquiring it would require a paid login.** | TJR stated-rule gaps | `ACCESS_BLOCKED` |

**Search terms used for TJR discovery** (so they are not repeated): *TJR Trades exact entry
model stop loss placement risk per trade*; *"TJR" trader strategy written guide entry trigger
stop loss risk management*; *TJR Trades verified track record myfxbook prop firm payout proof
audited*. Search returns for these are dominated by SEO/affiliate content farms
(`forex.in.rs`, `writofinance.com`, `44leverage.com`, `phidiaspropfirm.com`,
`snappchart.app`, `beststockstrategy.com`, `scribd.com`, `coconote.app`, `studocu.com`,
TradingView community scripts). **None of these are primary.** Each paraphrases TJR without
quotation, citation, timestamp or source video. None were registered as trader-attributed
candidates and none should be: a number that appears only in a content farm's paraphrase
cannot become a `SOURCE_STATED` claim about TJR.

### N-3. Attribution traps — retrieved, informative, and NOT usable

| # | Source | Retrieved | Why it is a trap | Class |
|---|---|---|---|---|
| N-3.1 | `https://www.jointjrtrades.com/philosophy` (registered as `CAND\|MOGO\|20260818\|035`) | 2026-08-18 | Presents "Never risk more than 1-2% per trade", "Is the risk/reward at least 2:1?" and "Use maximum 2-3 indicators" as TJR's own principles. Taken at face value this appears to close `GAP\|20260727\|003`. **It does not.** The page's own footer reads: *"Affiliate Disclosure: This website (tjrtrades.com) is an affiliate of TJR LLC through Whop.com … all opinions are our own."* It is a third-party marketer's paraphrase with no quotation or source attached to any figure. | `WRONG_ATTRIBUTION` |
| N-3.2 | `https://www.tradingwithrayner.com/best-stop-loss-strategy/` (registered as `CAND\|MOGO\|20260818\|036`) | 2026-08-18 | Hosted on Rayner Teo's own domain and returned by search as a Rayner stop-loss source, but the byline is **"By Jet Toyco"**, a staff writer. Rules stated in it are not attributable to `RAYNER_TEO`. **Only "By Rayner Teo" bylines on that domain may carry RAYNER_TEO attribution.** | `WRONG_ATTRIBUTION` |

Both were registered as candidates **without** a `claimedTraderId`, on purpose, so that the
trap itself is durable and a future session re-encountering these pages finds the reason
already recorded.

### N-4. Observed-trade evidence — what exists and why it still does not close the gap

The TJR **Trade Recaps** playlist (`PLKE_22Jx497vfICwVYk-gDnBHJEw76-7n`) was enumerated in
full: **100 videos**, dated from 2024-02-20, each a per-session recap published by TJR himself.
Wins and losses are both present, and the P&L figure is stated in the title.

This is the closest thing found to observed-trade evidence for any of the three human traders,
and it is **still not sufficient** for `GAP|20260817|006`, for three independent reasons:

1. **The figure is a publisher claim, not an observation.** A title reading
   "Live Day Trading Losing $33,814" is `SOURCE_STATED` by TJR. We did not observe the
   execution. Recording it as `OBSERVED` would be exactly the promotion of inference into
   observation this corpus exists to prevent.
2. **A title is not a trade.** Titles carry no instrument (with two exceptions — SPX and
   GBPJPY — both in Boot Camp recaps), no direction, no entry, no exit, no stop, no size, no
   time. A `TradeObservation` cannot be minted from one without inventing the missing fields.
   The per-trade detail is in the spoken video content, which is blocked (N-1.1).
3. **Publication selection bias is unquantified.** The set is what TJR chose to upload. Any
   win rate computed on it is the win rate of *published* days. Nothing in the corpus bounds
   the gap between that and his actual trading.

**No independently verified performance record was found for TJR.** No Myfxbook, no
third-party-verified account, no broker statement. Two things support treating this as a
genuine absence rather than a failed search: search specifically for an audited/verified TJR
track record returned only commentary asserting no such record exists (secondary, not
citable as fact), **and** TJR LLC's own boilerplate — retrieved directly from the publisher on
six separate videos and on the blueprint landing page — states: *"We do not measure earnings
or financial performance."* That is a **primary, publisher-stated** admission, and it is the
strongest evidence available on this point.

### N-5. Routes considered and deliberately NOT taken

| Route | Why not |
|---|---|
| Third-party YouTube transcript mirror sites | They are proxies for the very endpoint the platform is refusing this environment, and their output fidelity is unverifiable against the audio. Using one would inject text of unknown provenance into the corpus while *appearing* to be TJR's words — the single highest-risk way to manufacture evidence here. |
| Driving the operator's own browser to read YouTube's transcript panel | This is a legitimate normal-user path and **is the recommended route** (see below), but it requires the operator to select and confirm their own browser. It was not executed in this session. |
| Whop / paid course purchase | Requires payment and login. Out of bounds. |
| X/Twitter systematic reading | Login-walled. Out of bounds. |

### N-6. Recommended sanctioned route for the operator

The corpus's existing TJR and ALEX_G transcripts were **owner-pasted**, and that remains the
only route that works. YouTube's own "Show transcript" panel is available to a logged-in
person in a normal browser for every video in section N-2/N-4. The 27 TJR candidates registered
this session (`CAND|MOGO|20260818|001`–`027` — 17 rule-stating targets, then the Trade Recaps
playlist and 9 named recaps) are selected so that the operator's paste effort goes to the
videos most likely to state the three blocking facts, rather than to the corpus at large. Any transcript obtained this way must still be registered as
`provenanceStatus: partially_verified` with `titleVerification.stillUnverified` carrying the
ASR-fidelity caveat, exactly as `EVSRC|TJR|20260727|002` does.

### N-7. What was NOT searched this session

Recorded so the boundary is honest, not so it looks complete:

- **ALEX_G** was surveyed only at the channel level (30 recent videos enumerated,
  `youtube.com/@fxalexg__/videos`, HTTP 200). No ALEX_G-specific acquisition was attempted;
  `GAP|20260817|007` is untouched by this session. ALEX_G carries 587 of the 641 blocked
  hypotheses and is the largest remaining acquisition target.
- **RAYNER_TEO observed trades** (`GAP|20260817|008`) were not pursued. Rayner Teo's written
  corpus states rules; nothing found in it records executions.
- The TJR **Boot Camp** (56 videos) and **Boot Camp 2.0** (14 videos) playlists were
  enumerated in full but only 9 episodes were registered as candidates. The remainder are
  known and reachable; they were left unregistered to keep the queue signal-bearing.
