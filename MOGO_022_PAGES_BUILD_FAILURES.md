# MOGO-022 — Repeated GitHub Pages build failures: root cause

**Verdict: EXTERNAL / TRANSIENT. Severity P3. No repair warranted, and no repository
change would have prevented it.**
**Forward PAPER operation unaffected. Evidence preservation unaffected. Site currently live and current.**

---

## 1. The exact failing step

Not a Jekyll error, and not a repository-content error. All five failures die in the
**`build` job, step 1 "Set up job"**, during `Prepare all required actions` — *before*
`actions/checkout` runs, so no repository file is ever fetched, let alone built.

```
Download action repository 'actions/jekyll-build-pages@v1'
  (SHA:44a6e6beabd48582f863aeeb6cb2151cc1716697)
##[warning]Failed to download action
  'https://codeload.github.com/actions/jekyll-build-pages/tar.gz/44a6e6be…'
  Error: Response status code does not indicate success: 429 (Too Many Requests).
##[warning]Back off 26.159 seconds before retry.
…
##[error]Failed to download archive '…' after 3 attempts.
```

The root cause is `codeload.github.com` — GitHub's own artifact CDN — returning
**429 / 502 / 503** for the SHA-pinned action tarball. Every code is server-side.

## 2. All five failures share one cause

| Run | Commit | HTTP responses observed |
|---|---|---|
| #303 | `c3f7f96` | 429 → 503 → 503 |
| #305 | `dafeada` | 503 → 429 → 429 |
| #306 | `2f679f4` | 503 → 429 |
| #308 | `4e486bf` | 429 → 429 |
| #310 | `3d4db38` | 429 → 429 → 502 |

Same URL, same pinned SHA, same step, same failure mode. The two runs named by the
operator (#303, #310) are the same defect as the other three.

## 3. Timeline

- **Most recent SUCCESS: #313 (`8cd9207`)** — the current HEAD, built `2026-08-17T16:32:17Z`.
- **Earliest failure in this pattern: #303**, `2026-08-17T15:00:38Z`.
- **No Pages failure in the preceding 55 runs.**
- Failures and successes **interleave**: #303 ✗, #307 ✓, #308 ✗, #309 ✓, #310 ✗, #311 ✓, #313 ✓.

Interleaving is itself decisive. A defect in repository content would fail
*deterministically* on every subsequent run; these alternate, and the newest run
succeeded on the newest commit.

## 4. Did MOGO-022 work cause this?

**No — but it plausibly increased exposure, and that distinction matters.**

The failure is a download of a third-party action from a CDN. Nothing in this
repository is read at the point of failure, so no commit can be the *cause*.

However, `429 Too Many Requests` is a rate-limit response, and MOGO-022 pushed
**10 commits in roughly 90 minutes**, each triggering a Pages build. That cadence is
a plausible contributor to hitting a per-account or per-runner-pool limit on
`codeload.github.com`. That is a contributing *condition* arising from working
rhythm, not a defect in any commit — and the correct response is operational
(batch pushes when convenient), not a code change.

Stated plainly: temporal correlation with MOGO-022 commits is real, causal
responsibility is not.

## 5. What is actually affected

| Component | Affected? |
|---|---|
| Pages deployment pipeline | Transiently, yes — build failed, deploy skipped |
| Deployed site content | **No.** `deploy` was SKIPPED, so the previous good deployment stayed live. A failed build never publishes a broken site. |
| Forward PAPER runtime | **No.** MOGO runs in an already-loaded browser tab; a build failure cannot touch a running page. |
| Forward evidence preservation | **No.** Evidence lives in browser IndexedDB/localStorage and in the tracked corpus. Neither depends on Pages. |
| Research infrastructure | **No.** |

**Verified live, not assumed:** `https://joemogo.github.io/forex_hub/` returns HTTP 200
and is **byte-identical to local `index.html`** (SHA-256
`d42dae66ffac209298b4b39491a0c742a6a0a3a0442374158370d59b9d669012`), serving
`APP_VERSION='12.39.2'` including the MOGO-022 exit-monitor fix. The Pages API
reports `status: built`, `sha: 8cd92075` — current HEAD, `error: None`.

The site is fully up to date. The five failures left no residue.

## 6. Why no repository change would help

Worth stating, because the tempting fixes do not work:

- **`.nojekyll` would not help.** It controls whether Jekyll *processes* files. The
  failure occurs while downloading the `jekyll-build-pages` action, before any build
  begins. The action is still fetched regardless.
- **A `_config.yml` would not help**, for the same reason.
- **Replacing the built-in `pages-build-deployment` with a custom workflow** that
  avoids `jekyll-build-pages` *could* sidestep this specific action download — but it
  would replace a working deployment path for the live trading UI in order to route
  around a transient CDN condition that already self-resolves. That trades a real
  risk for a cosmetic one, and is against both "existing architecture > replacement"
  and "do not disable a meaningful build check to make GitHub green."

There is no check to fix here, and nothing was suppressed: the build check is valid,
it correctly reported that it could not obtain its dependency, and it correctly
skipped deployment rather than publishing an unbuilt site. **That is the system
behaving properly under an external fault.**

## 7. Classification

**P3 — external infrastructure, transient, self-resolving, no residual defect.**

Not P2: there is no outstanding work item. The failure mode requires no mitigation,
has no impact on forward operation or evidence, and has already resolved on its own.

**Action taken: none, deliberately.** Failed-run references preserved above.

## 8. Reproducing / re-checking

```
gh run list --repo joemogo/forex_hub --workflow pages-build-deployment --limit 25 \
  --json number,conclusion,headSha,createdAt
gh api repos/joemogo/forex_hub/actions/runs/<id>/logs > logs.zip   # step "Set up job"
gh api repos/joemogo/forex_hub/pages/builds/latest
curl -s https://joemogo.github.io/forex_hub/ | grep -o "APP_VERSION='[0-9.]*'"
```

If this recurs and a build failure is ever followed by *no* successful run, the live
site simply remains at the last good deployment — which is the safe outcome, not an
outage.
