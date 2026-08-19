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

---

## Session 2026-08-18 (second pass) — MOGO-022 ALEX_G acquisition

Scope: the single gap `GAP|20260817|007` (ALEX_G observed trades), which N-7 above recorded as
untouched and which carries 587 of the 641 blocked hypotheses.

Method: `curl` with a normal browser User-Agent, plus one web search for discovery. No login was
used, no paywall or bot protection was bypassed, no consent banner was accepted, and no
third-party transcript mirror was touched.

Identity established from primary sources this session: the channel is `@fxalexg__`
(channelId `UCgPeeHdxYRal0HTNeAkjqLg`, YouTube-verified, display name "fxalexg"); the person is
**Alex Gonzalez**; the operating entity is **Swing Trading Lab LLC**. Three sibling channels exist
and were checked (below).

### N-8. Does ALEX_G's retrieval ceiling differ from TJR's? — **No. It is identical.**

This was the session's primary question, because a publisher-authored caption track would have
been a materially better evidence source than ASR.

| # | Source | Retrieved | Result | Checked against | Class |
|---|---|---|---|---|---|
| N-8.1 | Caption-track inventory via `ytInitialPlayerResponse` on **17 ALEX_G videos** spanning 2023-10-24 → 2026-06-22 (`DZ9l_dpmbyM`, `XJ6lNP_Ihkg`, `KnZ03FjD-i0`, `7otxB9VIiDs`, `b80QhvUHHoU`, `f-7_8hmb0M0`, `njvjjOgiLKo`, `ILJ5_ZbB5r0`, `iFs8BmHYnks`, `oJvao6Ca4aA`, `JiEJMpdraG4`, `hiad0PbI47o`, `yGkd32dirJ8`, `f0Us3YBL1tg`, `qGNeo8RvV50`, `a03Vmo_d9Tk`, `xAJT6cmJ5gs`, `EEpfmQo2Ars`, `ithXhNOITTA`, `1fGzVHI7rN0`, `M8wDlKjaQRk`, `DsPLtzjTONI`) | 2026-08-18 | HTTP 200 on every watch page. **Every single video carries exactly one caption track: `kind=asr`, `lang=en`, "English (auto-generated)". Zero publisher-authored caption tracks.** | `GAP\|20260817\|007` | — (finding) |
| N-8.2 | `https://www.youtube.com/api/timedtext?v=a03Vmo_d9Tk&…&kind=asr&lang=en` (signed caption URL taken from the live watch page) | 2026-08-18T15:57:02Z | **HTTP 200, 0 bytes** | `GAP\|20260817\|007` | `CONTENT_NOT_RETRIEVABLE` |

Checked **once**, deliberately, not retried. **Conclusion: ALEX_G is structurally identical to TJR
on the caption question.** No route found this session raises the `partially_verified` /
ASR-fidelity ceiling the corpus already records on the nine existing `EVSRC|ALEX_G|*` transcripts.
Spoken content remains the place where per-trade detail lives, and it remains unobtainable.

### N-9. Where ALEX_G **does** differ from TJR — and why it still does not close the gap

This is the one substantive asymmetry found, and it is worth recording precisely so a future
session neither rediscovers it nor overreads it.

**TJR's video descriptions are byte-identical boilerplate with zero chapter markers (N-2.1).
ALEX_G's are not.** The 2024 serial challenge playlist `PL3wdfj84a2fk53i3JdpCB9WEbuXpA3Fbd`
("Turning $100 into a $1,000,000 (2.0)", 13 videos, 2024-07-14 → 2024-10-18) carries, in
**publisher-authored, fully retrievable description text**, a week-by-week account-balance ledger,
and four of the twelve weeks name a currency pair. Several other videos carry publisher-authored
**chapter markers** naming balances and per-trade updates. All are registered as
`CAND|MOGO|20260818|037`–`056`.

What was retrieved, in full, per week (all `SOURCE_STATED` by ALEX_G, none `OBSERVED`):

| Wk | Candidate | Stated start → end | Instrument named? |
|---|---|---|---|
| 1 | `CAND\|MOGO\|20260818\|038` | $100 → "more than $200" | no |
| 2 | `…\|039` | "$400 to $900" hoped → "$3,000" (title: $3,074) | no |
| 3 | `…\|040` | $3,000 → "$15,000 in a single trade" (title: $6,000) | no |
| 4 | `…\|041` | $15,000 → **$8,949 (loss)** | no |
| 5 | `…\|042` | $8,949 → **no entry taken** | no |
| 6 | `…\|043` | → $22,696 | no |
| 7 | `…\|044` | $22,696 → **$20,380 (loss)** | **GBP/CHF** |
| 8 | `…\|045` | $20,388 → $90,278 (+$70,027) | no |
| 9 | `…\|046` | $90,278 → **$44,262 (−$46,459)** | **NZD/CAD** |
| 10 | `…\|047` | $44,262 → +$882, "broke even" (title: $107,351) | **USD/CAD** |
| 11 | — | **missing from the published series entirely** | — |
| 12 | `…\|048` | $201,940 → $131,550 **(loss)** → $332,588 | **USD/JPY, GBP/CHF** |

**Six independent reasons this does not close `GAP|20260817|007`:**

1. **It is a publisher claim, not an observation.** Same reasoning as N-4.1. Recording any of
   these balances as `OBSERVED` would be the exact promotion of inference into observation this
   corpus exists to prevent.
2. **No `TradeObservation` can be minted from it.** Not one week states an entry price, an exit
   price, a stop, a position size, a direction, or a fill time. Four weeks name an instrument and
   nothing else. Minting a record would require inventing every remaining field.
3. **The stated figures are internally inconsistent.** Week 3's description contradicts its own
   title ($15,000 vs $6,000). Week 10's description ("broke even, +$882") contradicts its own
   title ("$107,351"). Week 7 closes at $20,380 while week 8 opens at $20,388. Week 8's own
   arithmetic is off by $137 ($20,388 + $70,027 = $90,415, not $90,278); week 9's by $443. **An
   equity curve chained from these numbers would be wrong**, and week 11 is missing outright —
   week 10 ends near $45,144 and week 12 opens at $201,940 with no published bridge.
4. **The publisher's own blanket disclaimer declines to affirm the trades were executed.** Every
   ALEX_G description checked this session (n=17) carries: *"CFTC RULE 4.41 - Hypothetical or
   simulated performance results have certain limitations. Unlike an actual performance record,
   simulated results do not represent actual trading. Also, since the trades have not been
   executed…"* This is generic legal boilerplate applied blanket-style and it is **ambiguous**
   whether ALEX_G intends it to cover the trading shown in the videos. That ambiguity is not a
   detail — it means the publisher himself does not assert on the record that these were real
   executions, which is precisely the assertion a `TradeObservation` with `actor: HUMAN` requires.
5. **The publisher states he does not show his broker.** `DZ9l_dpmbyM`
   (`CAND|MOGO|20260818|050`) carries the publisher-authored chapter *"19:12 Why I Don't Show Up
   my Broker?"*. What he says under it is not retrievable, but the chapter title alone is
   **primary** support for treating the absence of a verified ALEX_G account record as a genuine
   absence rather than a failed search.
6. **The first challenge ended in a blown account.** The same video's chapters read *"01:18 I
   Officially Blew Up the Account"* and *"10:20 Thoughts on Blowing Up the Account"*. Escalating
   balance titles elsewhere on the channel are therefore not a sustained record, and publication
   selection bias (N-4.3) applies here too and is unquantified.

### N-10. Rejected / skipped setups — the sub-question the gap most needs

Searched specifically, because `GAP|20260817|007` calls out rejected setups. **Two hits, both
negative on inspection:**

| # | Source | Retrieved | What was found | Class |
|---|---|---|---|---|
| N-10.1 | `oJvao6Ca4aA` (`CAND\|MOGO\|20260818\|042`) | 2026-08-18 | The only explicit publisher statement of a non-entry found anywhere: *"this week there was no clear opportunity to enter, so we closed anyway."* **It names no setup, no instrument, and no criterion that failed.** A skipped *week* is not a rejected *setup*, and the reason, if given, is in the spoken content. | `SOURCE_DOES_NOT_STATE` |
| N-10.2 | `KnZ03FjD-i0` (`CAND\|MOGO\|20260818\|051`) | 2026-08-18 | Titled *"Why I haven't taken a trade in 30 Days…"* and chaptered *"02:06 23 Days without taking any trades"*. **A title is not evidence.** The description states the actual cause is non-method: *"I've been victim of a rob in my own house."* Chapters are Las Vegas, Miami and personal events. **Must not be scored as selectivity or discipline.** | `SOURCE_DOES_NOT_STATE` |

**No source found anywhere states a setup ALEX_G evaluated and declined for a rule-based reason.**

### N-11. Other ALEX_G surfaces retrieved

| # | Source | Retrieved | What was found | Checked against | Class |
|---|---|---|---|---|---|
| N-11.1 | `https://swingtradinglab.com/` (`CAND\|MOGO\|20260818\|058`) | 2026-08-18T15:58Z | HTTP 200, public, no login. A paid-course sales funnel. Its only performance content is **student** testimonials ("passing Quant Tekels 3-step evaluation in 43 days", "$3,677.81", "$691.13 and $573.76… from FundedNext"). **These are other people's trades.** No ALEX_G trade, no broker statement, no verified record. Confirms two identity facts only: Alex Gonzalez; Swing Trading Lab LLC. | `GAP\|20260817\|007` | `WRONG_ATTRIBUTION` |
| N-11.2 | `https://www.myfxbook.com/members/fxalexg` | 2026-08-18T15:58Z | **HTTP 403**, body is a Cloudflare interstitial ("Just a moment… Enable JavaScript and cookies to continue"). Bot protection. **Not bypassed.** | `GAP\|20260817\|007` | `ACCESS_BLOCKED` |
| N-11.3 | `https://www.instagram.com/fxalexg/` | 2026-08-18T15:59Z | HTTP 200 but the no-JS body contains the single word "Instagram" — all content is client-rendered behind a login wall. This is also where the six **MOGO-019 `ALEX-IG-2026-CASE-002`** screenshots came from; they remain unobtainable, exactly as that report recorded. Note ALEX_G's own YouTube boilerplate states *"MY only instagram VERIFIED are @ fxalexg and @ swingtradinglab"* — so the handle is publisher-confirmed even though the content is not readable. | `GAP\|20260817\|007` | `ACCESS_BLOCKED` |
| N-11.4 | `https://x.com/FXAlexGI` (`CAND\|MOGO\|20260818\|057`) | 2026-08-18T15:59Z | HTTP 200, public. Unlike TJR's handle (N-2.4) this one **resolves**: "Alex González", Miami FL, links `swingtradinglab.com`, 651 posts, 66K followers. **Only 5 posts of 651 render without login**; systematic reading is login-walled and was not attempted. See N-12 for the two items retrieved and why they are traps. | `GAP\|20260817\|007` | `ACCESS_BLOCKED` (for the timeline) |
| N-11.5 | Sibling channels named on ALEX_G's own "My other channels" shelf: **Swing Trading Lab** (`UCkmdhHHIcTlrZlFtOLz8pbQ`, 36.7K subs) and **Alex G Was Here** (`UCpdBp-4L-vOXUV8uPgvh82w`, 118K subs) | 2026-08-18 | Both enumerated, HTTP 200. Swing Trading Lab is 15 short generic-education videos (candlesticks, order blocks, Fibonacci) — **no trades, no recaps**. Alex G Was Here is 30 pure lifestyle videos (Bugatti, Vegas, Jake Paul) — **no trading content at all**. A third, *Swing Trading Lab Podcast* (`UCsWTXkPbOVvbPNo7EHa35tg`), was identified but not enumerated. | `GAP\|20260817\|007` | `SOURCE_DOES_NOT_STATE` |
| N-11.6 | `@fxalexg__` channel structure: `/videos` (30), `/shorts`, `/playlists` (8), `/streams` | 2026-08-18 | All HTTP 200. **The channel has no Live/Streams tab at all** — `/streams` serves the Home tab. There is therefore **no live-trading stream archive** for ALEX_G, which is the one format that would have carried unnarrated execution footage. The 30 recent videos are dominated by lifestyle and funnel content; the trading-relevant material is the challenge playlists already enumerated. | `GAP\|20260817\|007` | `SOURCE_DOES_NOT_STATE` |

### N-12. Attribution traps — retrieved, informative, and NOT usable

| # | Source | Retrieved | Why it is a trap | Class |
|---|---|---|---|---|
| N-12.1 | The `@FXAlexGI` X **bio**, verbatim: *"I'm a really really really good demo trader"* | 2026-08-18 | Read literally this looks like a decisive publisher admission that ALEX_G's trading is simulated, which would resolve §N-9.4 outright. **It does not, and it must not be used that way.** The register is ambiguous — it reads equally as literal self-description or as self-deprecating irony — and this session did **not** resolve which. Separately, the X account is **not publisher-confirmed**: ALEX_G's own boilerplate names only *Instagram* handles as verified and is silent on X. Two unresolved layers stacked; promoting this to a `SOURCE_STATED` fact about ALEX_G would be a fabrication. | `WRONG_ATTRIBUTION` |
| N-12.2 | The `@FXAlexGI` post of 2025-12-23, verbatim: *"I set and forget a little to hard boys… I let a winning position, turned into a losing position. No new lesson learned here, I know the risk of these decisions and I am responsible for the outcomes. I just decided that I was OK with risking it"* | 2026-08-18 | The closest thing to a first-person ALEX_G trade account found this session, and it names the Set-and-Forget behaviour as the cause. **Still not a trade record**: no instrument, direction, entry, exit, stop, size, or fill date. Same unresolved account-attribution caveat as N-12.1. | `SOURCE_DOES_NOT_STATE` |
| N-12.3 | Web-search returns for an audited ALEX_G track record (trustpilot.com, scampulse.com, coinspot.io, photontradingfx.com, forexinfluencersreviews.com, gumroad.com) | 2026-08-18 | Uniformly **secondary commentary and review-farm content**, asserting that no MyFXBook or audited broker record exists and repeating third-hand allegations about the challenge accounts. **None are primary. None were registered.** Identical trap class to the TJR content farms in N-2. An assertion that appears only in a review farm cannot become a fact about ALEX_G — including the convenient negative one. | `WRONG_ATTRIBUTION` |

**Search terms used for ALEX_G discovery** (so they are not repeated): *Alex Gonzalez fxalexg Swing
Trading Lab verified track record myfxbook broker statement audited proof*.

**No independently verified performance record was found for ALEX_G.** The primary support for
treating this as a genuine absence rather than a failed search is ALEX_G's own chapter title
*"Why I Don't Show Up my Broker?"* (N-9.5) — a publisher-side statement, not a commentator's.

### N-13. Verdict on `GAP|20260817|007`

**Not closable from public ALEX_G material.** The gap decomposes into three distinct failures and
they must not be blurred into one:

- **`CONTENT_NOT_RETRIEVABLE`** — the per-trade detail (entry, exit, stop, size, direction, and the
  reasoning behind any skipped setup) exists only in spoken video content. `en/asr`-only, timedtext
  HTTP 200 / 0 bytes (N-8).
- **`SOURCE_DOES_NOT_STATE`** — everything that *was* retrieved in full (13 challenge descriptions,
  6 chapter-marker sets, the funnel site, two sibling channels) states balances, outcomes and four
  instrument names, and states **no** entry, exit, stop, size, direction or fill time anywhere
  (N-9, N-10, N-11).
- **`ACCESS_BLOCKED`** — MyFXBook (403 Cloudflare), Instagram (login wall, and the origin of the
  still-unobtainable MOGO-019 six screenshots), the X timeline (login wall). None bypassed (N-11).

**What would actually close it**, in descending order of how much each would move the position:

1. **Operator-supplied ALEX_G trade records** — the six MOGO-019 `ALEX-IG-2026-CASE-002`
   screenshots, or any broker/statement artefact. This remains the only route that produces a
   `TradeObservation` with `actor: HUMAN`. `GAP|20260817|007`'s own
   `recommendedNextSourceType` already says so and this session found nothing to displace it.
2. **Owner-pasted transcripts of `CAND|MOGO|20260818|050`, `042`, `052`, `053`, `048`** — in that
   order. 050 is first because its chapter list promises the two facts that most change the
   corpus's posture (the blown account, and why no broker is shown); 042 is the only skipped-week
   candidate; 052/053 carry per-trade chapter timestamps that index exactly where to look. Any
   transcript obtained this way is still `provenanceStatus: partially_verified` with the
   ASR-fidelity caveat, exactly as the nine existing `EVSRC|ALEX_G|*` records are.
3. **An owner ruling on whether the CFTC 4.41 blanket disclaimer (N-9.4) is dispositive.** If it
   is read as covering the challenge videos, then *no* amount of transcript retrieval can ever
   produce an ALEX_G `TradeObservation` from this material, and items 1–2 collapse to item 1
   alone. This is a governance question, not a research one, and it is **the** decision that
   determines whether further ALEX_G acquisition is worth any effort at all.

**What deliberately was NOT done:** no `TradeObservation` was created, no evidence record was
created, no claim was minted, and the week-by-week balance table in N-9 was **not** chained into
an equity curve — it does not chain, and §3 of `MOGO_022_TJR_EVIDENCE_REQUIREMENTS.md` records
the same failure mode for MOGO's own preserved trades.

### N-14. What was NOT searched this session

- The **9 unique 2023-challenge episodes** in `PL3wdfj84a2flucy4Bif28-rrKIuYmWCkQ`
  (`dVCbyu6kDm0`, `M8OcMuD_eEQ`, `okx_3_Uxht0`, `uOtKqV9HQss`, `OyfI83yU0KM`, `7kOPNrRw0jM`,
  `7dcJ2WZYDDQ`, `HmlA-Ro_k9k`, `kb3t0xHbpGQ`) — enumerated and registered as a population handle
  (`CAND|MOGO|20260818|056`), **descriptions not retrieved.** Given N-9.6 (that challenge ended in
  a blown account) they are lower value than the 2024 series, but they are reachable.
- The **Swing Trading Lab Podcast** channel (`UCsWTXkPbOVvbPNo7EHa35tg`) — identified, not enumerated.
- The **Telegram** channel advertised in every description (`go.swingtradinglab.com/*` redirectors,
  which resolve to interstitials rather than to `t.me` from this environment). Not pursued.
- **`GAP|20260817|006`** (TJR) and **`GAP|20260817|008`** (RAYNER_TEO) were out of scope and are
  untouched by this session.

---

## N-15 — External trader discovery sweep, 2026-08-19

~30 candidate hosts probed with real fetches. Recorded so none of this is searched again
without new evidence.

### N-15.1 — GOVERNANCE BLOCK: TradingView asks AI agents not to take the paths we need

`https://www.tradingview.com/robots.txt`, retrieved and **independently re-verified
2026-08-19**, contains a named block listing `ClaudeBot` (alongside Google-Extended,
PerplexityBot, Bytespider and others) whose rules are:

```
Disallow: /ideas/*   /scripts/*   /script/*   /v/*
Disallow: /symbols/*/minds/*   /u/*   /chat/*   /chart/*   /watchlists/*
```

`User-agent: *` permits these paths; the AI-agent block does not. **Every candidate in the
shortlist below depends on `/ideas/*` and `/u/*`.**

**Status: NOT PURSUED — publisher AI-agent exclusion. DECIDED by the owner 2026-08-19,
`DECISION|MOGO|20260819|007`.** The ruling: the ClaudeBot exclusion is **dispositive for
autonomous acquisition**. No bypass, evasion, masquerade, or User-Agent substitution.
Continuing under a browser User-Agent in order to sidestep a rule that names ClaudeBot is
masquerade, which the operating charter forbids outright. Recorded rather than routed around.

The same ruling directs that TradingView **not** be discarded scientifically. It is classified
**HIGH-VALUE / ACCESS_BLOCKED**: the measured findings in N-15.2 stand as results, and the
reconstructability advantage recorded there is why this source stays on the books rather than
being struck. What is blocked is the *acquisition path*, not the *scientific interest*.

**Reconsideration is possible only through a legitimate path** — operator-supplied artifacts,
an authorized API, a permitted access mechanism, or an explicitly permitted export/download.
Nothing that circumvents the publisher's restriction qualifies, however it is dressed up. The
specific artifacts that would unlock this source are enumerated in
`HUMAN_ASSISTED_ACQUISITION_QUEUE.md` (HAQ-1); **no operator action is requested now.**

**Disclosure:** during discovery, before robots.txt was read, roughly 90 tag-feed pages and
82 idea pages were fetched under a normal browser UA. Crawling stopped immediately once the
file was read. Nothing was registered, acquired into the corpus, or committed.

### N-15.2 — What was lost to that block, so the cost of the decision is legible

TradingView published ideas are, on the evidence gathered, **the only publicly retrievable
source class found anywhere that is genuinely mechanically reconstructable**. A server-side
JSON blob carries `created_at` stamped to the microsecond (publisher-stamped, not an author
claim), `symbol.pro_symbol`, `interval`, `direction`, the description carrying entry/stop/
target, and `updates[]` with typed outcomes (`close_position` → `target_reached` /
`stop_reached`).

Why that matters more than the levels themselves: because instrument, direction, levels and a
**pre-trade** timestamp are all present, the outcome does not have to come from the author at
all — it can be derived from price history. That defeats hindsight bias and self-reporting
bias together, which are the two failure modes that blocked TJR and ALEX_G. Ideas whose entry
never filled would also form an observable population of **skipped setups** — the thing
`GAP|20260817|007` asks for and no video source can supply.

Measured base rates (not estimates): **110–135 of 1,572** forex ideas carry entry + stop +
target (~7–9%). Of 82 idea pages sampled, **22 carried a structured outcome: 17
`target_reached`, 5 `stop_reached`** — a 3.4:1 skew in *self-marked* outcomes, which is itself
a quantified reporting-bias figure and an argument for deriving outcomes mechanically.

Shortlist held pending the governance decision, NOT registered: `FXCM`, `VantageMarkets`,
`EliteTradingSignals`, `YenSensei`, `UnitedSignals`.

Two findings worth keeping even if the answer is no:
- **`EliteTradingSignals` and `UnitedSignals` state position sizing** (`Suggested risk: 1%`,
  `Our Risk - 1%`) in structured form — the exact fact class `GAP|20260727|003` is blocked on.
- **`YenSensei` states a setup evaluated and DECLINED with the rule-based reason**
  (*"Selling without confirmation is not considered, as the technical trend remains
  bullish"*). N-10 records that no such statement exists anywhere in ALEX_G's material.

**UNRESOLVED, and it must not be assumed away:** FXCM and VantageMarkets publish in a
near-identical analytical lexicon with byte-similar boilerplate but name *different* providers
(TFA Global Pte Ltd vs Everest Fortune Group). Whether they are one analyst under two brands is
**UNKNOWN**. Treating them as independent would double-count the same calls.

### N-15.3 — Other publisher AI-agent exclusions

| Host | Directive | Verified |
|---|---|---|
| `elitetrader.com` | `ClaudeBot → Disallow: /`, plus `Content-Signal: ai-train=no` | yes, re-verified |
| `forexlive.com` | reported as `ClaudeBot`/`anthropic-ai`/`Claude-Web → Disallow: /` | **NOT reproduced** — robots.txt returned empty on re-check. Treat as UNCONFIRMED and re-verify before relying on it either way. |

### N-15.4 — NETWORK EGRESS, a class distinct from ACCESS_BLOCKED

DNS resolves but TCP times out (curl exit 28) from this environment for: `t.me`,
`www.fxblue.com`, `www.fxstat.com`, `www.tradervue.com`, `www.actionforex.com`,
`tapi.fxbrokersignals.com`, `fxsignals.fxleaders.de`.

**This is an environment constraint, not a publisher refusal**, and is logged separately
because a different network might succeed. Two of these are high value and deserve one
re-check rather than being written off:

- **`fxleaders.com`** — robots fully permissive, no AI directive. Its page template exposes
  exactly the wanted schema (`signal.pair`, `.action`, `.status`, `.entryPrice`, `.stopLoss`,
  `.takeProfit`, `.analyst`), free-tier signals showing all three levels. Killed only because
  both of its API hosts time out.
- **`t.me/s/{channel}`** — public Telegram previews carry full timestamped history without
  login. Untestable here.

### N-15.5 — Rejected on content: the source does not state trades

| Source | Evidence | Class |
|---|---|---|
| `fxstreet.com/analysis` | Retrieved in full. `stop loss` 0, `take profit` 0, `entry` 0; `target` 6, `support` 99. States bias + invalidation + target only. **Retained as a weaker bias/level source, rejected as a trade source** — the distinction must not be blurred. Entry would have to be INFERRED as price-at-publication and marked as such. Robots clean, no AI directive (re-verified). | `SOURCE_DOES_NOT_STATE` |
| `fxempire.com/forecasts` | Same shape as FXStreet, plus a paywalled premium tier. Strictly dominated. | `SOURCE_DOES_NOT_STATE` |
| `darwinex.com` | Publishes DARWIN quote series and risk metrics, **not trades**. Zero occurrences of open/close price, stop loss, take profit. | `SOURCE_DOES_NOT_STATE` |
| `etoro.com` portfolios | Portfolio composition and aggregate stats, not per-trade levels. | `SOURCE_DOES_NOT_STATE` |
| TradingView author pages `/u/{name}/` | Entirely client-rendered: 0 chart URLs, 0 `created_at`, no item JSON. **No server-rendered author-scoped feed exists**, so per-author totals are only ever lower bounds from tag feeds. A cost finding. | `SOURCE_DOES_NOT_STATE` |

### N-15.6 — Rejected on access

`mql5.com/en/signals` is the strongest evidence quality found anywhere — **broker-monitored
rather than self-reported**, with public per-symbol trade counts, win rate, Sharpe and
drawdown. The `Trading history` tab is replaced by *"To see trades in realtime, please log in
or register"*. Per-trade levels are behind login. **Not bypassed.**

Also `ACCESS_BLOCKED`, all 2026-08-19: `zulutrade.com` (API 401), `babypips.com` (403
Cloudflare, robots.txt itself blocked), `reddit.com` (403), `investing.com`,
`dailyforex.com`, `signalstart.com`, `collective2.com`, `forexfactory.com` (403/404),
`public.api.bsky.app` (403). `championship.mql5.com` archive redirects to marketing — gone.

### N-15.7 — A constraint on ANY published-idea source, if one is ever authorised

A published idea is **a stated plan, not an executed trade**. No broker statement or verified
record exists for any author found — the same genuine absence as TJR and ALEX_G. Any
observation minted from one must record that it is not an execution claim, and **survivorship
is unbounded**: authors may silently delete losing ideas, which is invisible from outside and
would corrupt any win rate computed from marked outcomes.
