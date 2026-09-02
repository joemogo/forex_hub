# Isolated browser observer design — September 2, 2026

Status: selected for isolated synthetic prototyping, NOT approved for production
wiring, installation or activation. Design/testing authority was granted today.

## Decision and evidence

Place the **entire fresh observer session plus emitter and synchronous engine**
inside one dedicated worker per pinned pair/H1 session. The host exchanges plain
data asynchronously; do not make `runLeanSetupEngine` return a Promise. Current
capture explicitly rejects thenables and relies on synchronous state transitions.
Moving only the engine across messages would require rewriting that contract.

Within the worker, each engine attempt creates fresh lexical engine state and
copies its candle input. Keep observer baseline/pending/history state alive across
successful requests; never reuse/reset the running application's scanner state.
This is the smallest selected asynchronous boundary preserving the existing
observer contract, not a claim that browser feasibility is already demonstrated.

The source-only factory and mirrored v135 tests establish a sufficient H1
inventory: 29 phase functions, seven helpers, three constants and three owned
state objects. Build-time generation must preserve declaration text and constant
values and fail on inventory drift. Generated functions/constants belong inside
an attempt factory; do not wrap shared module-level mutable engine state.
Use reviewed source-derived static artifacts, not runtime eval, Function,
index.html extraction, application startup, or loading the app in an iframe.
The existing Node VM factory is a test oracle, not a browser implementation or
security sandbox. Higher timeframes and untested strategy branches are excluded.

## In-memory protocol and ownership

- Explicitly created, disabled by default. No auto-start, timer, feed fetch,
  persistence, UI hook, credential, order, or upload dependency.
- Synthetic initialization pins protocol/build version, session ID, pair, H1,
  supported one-close configuration and maximum endpoint age. Clock and hashing
  are trusted worker dependencies, never callable objects supplied in messages.
- A request carries session ID, monotonically increasing request ID and a plain
  snapshot envelope. Candle timestamps are integer UTC milliseconds. Copy rather
  than transfer caller buffers; no shared memory or live object references.
  Validate wire integers first. The engine adapter must convert each timestamp
  to a fresh Date in its per-attempt candle copy: the selected H1 engine calls
  `t.getTime()` and cannot directly consume numeric wire timestamps. Keep the
  observer's original validated snapshot separate; compare values by epoch time,
  not object identity. Invalid/out-of-Date-range values refuse before the engine.
- Only one request may be outstanding. Host refuses a second request rather than
  queueing an unbounded backlog; worker checks session/version/request order
  before evaluation. No concurrent runs of the session.
- Response is exactly one of `no-export`, `export`, or `refusal`, with matching
  session/request/build IDs. Host accepts only its outstanding response once.
  Late, duplicate and foreign responses cannot become exports.
- Worker clock is sampled when processing, not from snapshot metadata or send
  time. Existing freshness/continuity guards remain unchanged. The synthetic
  prototype uses a controlled clock; real clock/latency policy remains unapproved.
- A synchronous SHA-256 dependency is needed by the current emitter. Selecting
  a reviewed browser implementation and matching canonical byte/hash vectors is
  a prototype prerequisite; do not pass an asynchronous digest Promise through
  the synchronous emitter or substitute a mock hash for compatibility evidence.

## Failure boundary

On an engine exception, discard that attempt's state/candles. Existing pending
observer state stays in the surviving worker; retry intact input only after a
named refusal and verify exactly one eventual export. Tests must distinguish
this recoverable engine failure from an unexpected session/transport failure.

On worker loss, timeout, malformed response or unexpected observer/emitter
failure, stop the host session and refuse further input. Do not automatically
replace a worker or replay an uncertain request: an export might have committed
inside the lost worker before delivery, and its baseline/history is unavailable.
No exactly-once guarantee is claimed across worker loss. Explicit future restart
must declare a new session and re-prime without claiming continuity or novelty
across that boundary. No persistence/recovery protocol is authorized here.

## Bounded prototype acceptance plan

Prototype checkpoint: same-realm lexical attempt generation and mirrored complete
export parity now pass in v135, including wire Date conversion and injected
post-engine mutation/failure recovery. Source text/constant parity is asserted.
This is an in-memory generated program evaluated by Node VM for testing; static
browser packaging and actual worker/message validation are still unimplemented.

1. Build a test-only source-derived attempt factory; compare declaration text,
   constants and both complete mirrored exports with the existing VM oracle.
   Prove two attempts and caller candles remain independent after mutation/fault.
   Include integer-wire-to-Date conversion, invalid Date refusal and a mutation
   control that removes conversion; existing Date-based fixtures alone are not
   evidence that the wire protocol is executable.
2. Exercise a message-boundary simulator with copied data and the whole session
   on its worker side: baseline, pending successor, buy/sell export, duplicate
   suppression, foreign/stale IDs, overlap refusal and worker-loss fail-stop.
   Mutation controls must break state isolation and response correlation tests.
3. Test static packaging and synchronous hashing compatibility without app
   startup. These are Node-based prototype checks, NOT actual Worker, CSP,
   module-loading, Chrome/Mac, or production-performance validation.

Production integration remains prohibited. Real-browser/operator validation needs
separate authority. Static worker URL/module/CSP support under MOGO's actual
launch method, supported-history cost, calendar gaps, feed identity and capture
permissions remain open. Do not fabricate a market calendar or weaken strict H1
continuity. Multi-close semantics remain unresolved and protected rules unchanged.
Paper-trading readiness is not assessed by this design or its future tests.
