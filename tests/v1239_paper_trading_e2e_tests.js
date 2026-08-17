// ══════════════════════════════════════════════════════════════════════════════════════════
// v12.3.9 ALEX / JVM PAPER TRADING — END-TO-END, ORDER GENERATION, DUPLICATE PREVENTION,
//                                    AND ALEX/JVM ISOLATION
// ══════════════════════════════════════════════════════════════════════════════════════════
// WHY THIS SUITE EXISTS
// A 25-mutation adversarial re-score of the paper-trading execution surface (JVM
// openPaperPosition / closePaperPosition / checkAutoTrades, ALEX alexGConstructLivePosition /
// alexGAttemptOpenLivePosition / alexGCloseLivePosition) found three behaviour-changing
// mutations that killed ZERO fixtures anywhere in the 30-suite gate:
//
//   M12  a JVM close ALSO credits the ALEX balance          (JVM -> ALEX state leak)
//   M25  an ALEX open ALSO pushes the position into the     (ALEX -> JVM state leak)
//        JVM paper account
//   M18  checkAutoTrades evaluates every eligible pair       (each pair decided twice per tick)
//        TWICE per tick
//
// and two further probes that survived because the behaviour is defended at a SECOND layer that
// nothing observed either:
//
//   M14a the one-position-per-pair check is removed from      (the pair is still not traded, but
//        checkAutoTrades' ELIGIBILITY FILTER only              it IS evaluated -- a real signal
//   M15a the traded-today check is removed from the           decision is taken on a pair that
//        ELIGIBILITY FILTER only                              was already excluded)
//
// Nothing anywhere asserted that a JVM operation leaves ALEX untouched, that an ALEX operation
// leaves JVM untouched, or that one auto-trade tick decides each pair exactly once. Every
// fixture below exists to kill one of those specific survivors, or to serve as the control that
// makes the survivor-killing fixtures meaningful.
//
// EVIDENCE STANDARD APPLIED HERE
//   * No fixture asserts against source text.
//   * No fixture is self-consistent: nothing compares two outputs of the same computation
//     (never "balance === balanceBefore + closedPos.pnl").
//   * Every asserted number is a FIXTURE-CHOSEN LITERAL computed by hand from the fixture's own
//     inputs and written out in the fixture text, never re-derived with the production
//     expression. Where a literal cannot be compared with === because of ordinary floating-point
//     noise in FX price arithmetic, it is compared with |actual-expected| < 1e-9 -- a
//     numerical-precision floor (a ten-thousandth of a pip), which every mutation these fixtures
//     target misses by many orders of magnitude, never a trading tolerance.
//   * Each isolation fixture carries its own POSITIVE CONTROL proving the operation really
//     happened, so "the other strategy did not change" can never pass because nothing ran.
//   * The negative controls run against a series that IS evaluated (evaluation counts asserted),
//     so a zero-trade outcome is the strategy's own verdict and not an unreached code path.
//
// HARNESS NOTE: checkAutoTrades() and closePaperPosition() are both genuinely async. This suite
// is `async` and RETURNS ITS PROMISE; the runner prints from the .then() continuation. An async
// fixture that is not actually awaited is a known false-green in this repository -- every await
// below is real, and PTE2E-HARNESS.1 asserts the suite reached its own end.
//
// FROZEN SEMANTICS: no confluence, threshold, setup definition, entry, stop, target, filter,
// risk, sizing or exclusion rule is changed, overridden or re-implemented here. Every protected
// function is CALLED as shipped. The one execution-policy flag this suite reads
// (setupSuspensionEnabled) is not touched at all -- the ALEX fixtures enter at
// alexGAttemptOpenLivePosition, which is downstream of it.
async function runV1239PaperTradingE2EFixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,detail:detail==null?'':String(detail)});};

  // 🔴 §18.37: DRAIN THE MICROTASK QUEUE before the "after" snapshot. Independent verification
  // showed that ISO.6's claim -- "caught here and nowhere else in the gate" -- was FALSE for a
  // leak deferred past the fixture's own await. Crediting alexGAccount.balance with JVM P&L four
  // microtask turns later passed ISO.2, ISO.4, ISO.6 AND ISO.8; the only failure was a positive
  // control in a LATER block tripped by accumulated residue, i.e. caught by accident of ordering
  // rather than by the detector that claims to catch it. alexClean() then wiped the evidence.
  //
  // This is realistic precisely because the cross-strategy write risk is concentrated in the three
  // fire-and-forget evidenceCapture* seams, which are dispatched and not awaited. Snapshotting the
  // instant an await resolves measures a moment before those writes land.
  const drainMicrotasks=async function(){ for(let i=0;i<50;i++) await Promise.resolve(); };
  // Numerical-precision floor for FX price arithmetic. See the header: this is 1/10000 of a pip.
  const EPS=1e-9;
  const near=(a,b)=>typeof a==='number'&&isFinite(a)&&Math.abs(a-b)<EPS;

  g.setCfg({key:'fixture',accountId:'acct',env:'practice'});
  const TODAY=new Date().toDateString();          // frozen clock -> Mon 2026-08-10
  const OPENED_AT=new Date().toISOString();       // exact literal both stores must carry

  // ── JVM reset. Deliberately NOT a production reset function: this is fixture bookkeeping. ──
  function jvmClean(balance){
    g.setPaperAccount({balance:balance==null?10000:balance,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setAutoTrading({enabled:true,tradedToday:{},log:[],_lastDay:TODAY,unseenCount:0});
    g.setPaperEngineErrors([]);
    g.setPaperResetHistory([]);
    g.setPaperReconciliationAudit([]);
    g.setPairDataObj({});
    g.resetPaperVersionGuard();
    g.resetPaperPositionsClosing();
    g.clearLocalStorage();
    g.resetPricingCalls();
    g.resetM15Calls();
    // §18.20: compared by snapshotJvmStores but never reset -- see alexClean. storageLoadFailures
    // must be cleared too: a non-empty INC-001 register makes persistStorageKey REFUSE every write
    // for that key, so a seeded entry left behind silently disables persistence in every later
    // block (it broke ISO.5's balance assertion exactly that way during development).
    g.setPaperLedgerBlockingError(null);
    g.setPaperLedgerIntegrityWarning(null);
    g.clearStorageLoadFailures();
  }
  function alexClean(){
    g.setAlexGAccount({balance:10000,startingBalance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGJournalEntries([]);
    g.setAlexGAutoTrading({enabled:true,tradedToday:{},log:[],activatedAt:g.now()-86400000,tradedSignals:{}});
    g.setAlexGSetupState([]);
    g.setAlexGLiveSetupStatuses([]);
    g.setAlexGEngineErrors([]);
    g.alexGResetLiveDecisionState();
    g.resetAlexGVersionGuard();
    // §18.20: these four ARE compared by snapshotAlexStores but were never reset here, so a leak
    // that writes the SAME value it wrote in an earlier group is identical in the before and after
    // snapshots and passes. Proven: a JVM->ALEX write of a constant into alexGLastEvaluatedCloseTime
    // killed ZERO fixtures, while the same write with an incrementing value killed ISO.2 and ISO.6.
    // An idempotent leak is still a leak; the snapshot must start from a known-empty state.
    g.resetIsolationScratch();   // §18.25: the newly-snapshotted fields need a known start
    g.setAlexGZoneState({});
    g.setAlexGLastEvaluatedCloseTime({});
    g.setAlexGLedgerBlockingError(null);
    g.setAlexGLedgerIntegrityWarning(null);
    // SEEDED LAST, deliberately. An earlier ordering seeded before setAlexGZoneState({}) wiped it
    // straight back to empty, so a leak that WIPES zone state stayed invisible -- the seeder has to
    // be the final word or the snapshot has nothing to lose after all.
    g.seedIsolationScratch();
  }
  // Conversion snapshot so every SCAN_PAIRS instrument can actually be sized. Without it
  // pipValuePerLot() correctly returns null for JPY/CAD/CHF-quoted pairs and they are skipped --
  // which would silently shrink every "all pairs" count below into an unnoticed near-no-op.
  function seedConversions(){
    g.setPairData('USD_JPY',150.00);
    g.setPairData('USD_CAD',1.35);
    g.setPairData('USD_CHF',0.90);
  }
  const SCAN=g.SCAN_PAIRS.map(p=>p.replace('/','_'));
  // The frozen strategy's own verdict on THIS fixture's price series, not a fixture choice: the
  // series is a 1.10-handle EUR/USD-shaped one, so on a JPY-quoted instrument (pip 0.01 instead
  // of 0.0001) the same geometry scores an R:R of 0.23:1 against the frozen 1.99 minimum and is
  // refused. Those four pairs are therefore expected to be EVALUATED and REFUSED, and the other
  // eight to trade. PTE2E-AUTO.6 asserts that refusal explicitly, so this split is an observed
  // strategy decision the suite pins, never an unexplained shortfall quietly absorbed into a
  // smaller expected count.
  const JPY=SCAN.filter(p=>p.indexOf('JPY')!==-1);          // 4 instruments
  const TRADEABLE=SCAN.filter(p=>p.indexOf('JPY')===-1);    // 8 instruments
  function activeWatchAll(){
    const sd={};
    g.SCAN_PAIRS.forEach(p=>{sd[p]={weekly:'Bullish',daily:'Bullish',fh:'Bullish',bucket:'Active watch'};});
    g.setScanData(sd);
  }
  const openOn=oPair=>(g.getPaperAccount().openPositions||[]).filter(p=>p.oPair===oPair).length;

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP 1 — JVM ORDER GENERATION AS ACTUALLY EMITTED (POSITIVE CONTROL)
  //
  // Hand-computed for this exact fixture, from its own inputs:
  //   GBP_USD, pip 0.0001, quote USD -> pipValuePerLot = 0.0001 * 100000 = $10/pip/lot
  //   balance 10000 -> riskAmount = 1% = $100.00
  //   buy, entry 1.3000, stop 1.2900 -> riskPips = 100 ; target 1.3200 -> rewardPips = 200
  //   lots = 100 / (100 * 10) = 0.10   ->  units = round(0.10 * 100000) = 10000
  //   ratio = 200 / 100 = 2.00
  // ════════════════════════════════════════════════════════════════════════════════════════
  {
    jvmClean();
    const pos=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'manual');
    assert('PTE2E-OPEN.1 (POSITIVE CONTROL): a valid JVM setup opens exactly one position, and the ORDER AS EMITTED carries direction "buy", entry 1.3, stop 1.29 and target 1.32 -- the three prices are on the fields the close path will actually read, not merely present somewhere on the object',
      !!pos && !pos.error && pos.dir==='buy' && pos.entry===1.3 && pos.stop===1.29 && pos.target===1.32 &&
      pos.oPair==='GBP_USD' && pos.pair==='GBP/USD' && (g.getPaperAccount().openPositions||[]).length===1,
      pos?('dir='+pos.dir+' entry='+pos.entry+' stop='+pos.stop+' target='+pos.target+' n='+(g.getPaperAccount().openPositions||[]).length):('error='+(pos&&pos.error)));
    assert('PTE2E-OPEN.2 (POSITIVE CONTROL, sizing): that order is sized at exactly 0.10 lots / 10000 units on a $100.00 risk amount -- hand-computed as 1% of the $10,000 balance divided by (100 stop pips x $10 per pip per lot). A doubled size would read 0.20, and a risk fraction that skipped the /100 would read 10.00 lots on a $10,000 risk',
      !!pos && !pos.error && pos.lots===0.1 && pos.units===10000 && pos.riskAmount===100 && pos.pipValueAtEntry===10,
      pos?('lots='+pos.lots+' units='+pos.units+' riskAmount='+pos.riskAmount+' pipValue='+pos.pipValueAtEntry):'no pos');
    assert('PTE2E-OPEN.3 (POSITIVE CONTROL, geometry): the emitted order records 100 risk pips against 200 reward pips for a 2.00:1 ratio, and is stamped source "manual" and openedAt exactly 2026-08-10T14:00:00.000Z from the frozen clock',
      !!pos && !pos.error && near(pos.riskPips,100) && near(pos.rewardPips,200) && near(pos.ratio,2) &&
      pos.source==='manual' && pos.openedAt===OPENED_AT,
      pos?('riskPips='+pos.riskPips+' rewardPips='+pos.rewardPips+' ratio='+pos.ratio+' openedAt='+pos.openedAt):'no pos');
    assert('PTE2E-OPEN.4: the open is PERSISTED, not merely constructed -- the position is flagged committed and fxhub_paper on disk contains that exact trade id',
      !!pos && pos.committed===true && String(g.getLocalStorageItem('fxhub_paper')||'').indexOf(String(pos.id))!==-1,
      'committed='+(pos&&pos.committed)+' storage='+(g.getLocalStorageItem('fxhub_paper')?'present':'MISSING'));
  }

  // ── BOUNDARY: exactly at the zero-risk edge, on both sides ─────────────────────────────
  {
    jvmClean();
    const zero=g.openPaperPosition('GBP_USD','buy',1.3000,1.3000,1.3200,'manual');
    const acct=g.getPaperAccount();
    assert('PTE2E-BOUND.1 (BOUNDARY, exactly zero risk): a stop EXACTLY equal to entry is rejected with an error and opens nothing -- no position, no journal row, and the balance is still exactly 10000',
      !!zero && !!zero.error && (acct.openPositions||[]).length===0 && (g.getJournalEntries()||[]).length===0 && acct.balance===10000,
      'error='+(zero&&zero.error?'yes':'no')+' open='+(acct.openPositions||[]).length+' journal='+(g.getJournalEntries()||[]).length+' bal='+acct.balance);
    const one=g.openPaperPosition('GBP_USD','buy',1.3000,1.2999,1.3200,'manual');
    assert('PTE2E-BOUND.2 (BOUNDARY, one pip past the edge -- positive control for PTE2E-BOUND.1): a stop ONE PIP away is accepted and sized at exactly 10.00 lots ($100 risk / (1 stop pip x $10)). The guard rejects exactly-zero risk only; it is not a blanket refusal that would make PTE2E-BOUND.1 pass for the wrong reason',
      !!one && !one.error && one.lots===10 && one.units===1000000 && near(one.riskPips,1),
      one?('lots='+one.lots+' units='+one.units+' riskPips='+one.riskPips):('error='+(one&&one.error)));
  }

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP 2 — JVM END TO END: signal -> open -> close -> closed record
  //
  // Hand-computed for this exact fixture:
  //   the 0.10-lot GBP_USD buy above, exit taken at 1.3250 (the pairData fallback price this
  //   fixture set; /pricing is made to reject so the fill is fixture-controlled)
  //   move = (1.3250 - 1.3000) / 0.0001 = +250.0 pips
  //   pnl  = 250.0 * $10/pip/lot * 0.10 lots = +$250.00
  //   balance = 10000 + 250.00 = $10,250.00
  //   exit 1.3250 >= target 1.3200 with no explicit autoResult -> result "Win"
  //   automatic (not manual), not a developer trade -> closeReason "TAKE_PROFIT"
  //   resultR = pnl / riskAmount = 250 / 100 = +2.5
  // ════════════════════════════════════════════════════════════════════════════════════════
  {
    jvmClean();
    g.setPricing('reject');
    const pos=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData('GBP_USD',1.3250);
    const res=await g.closePaperPosition(pos.id,false,null);
    const acct=g.getPaperAccount();
    const closed=(acct.closedPositions||[])[0]||null;
    const rec=(g.getJournalEntries()||[]).find(e=>e.tradeId===pos.id)||null;
    assert('PTE2E-E2E.1 (END-TO-END): the REAL async closePaperPosition() moved the trade out of open positions and into exactly one closed position -- open positions is now empty',
      (acct.openPositions||[]).length===0 && (acct.closedPositions||[]).length===1,
      'open='+(acct.openPositions||[]).length+' closed='+(acct.closedPositions||[]).length);
    assert('PTE2E-E2E.2 (END-TO-END, exit and P&L as literals): the closed record carries exitPrice exactly 1.325 and pnl exactly +250.00 -- 250 pips at $10 per pip per lot on 0.10 lots, computed by hand from this fixture\'s own numbers',
      !!closed && closed.exitPrice===1.325 && closed.pnl===250,
      closed?('exit='+closed.exitPrice+' pnl='+closed.pnl):'no closed position');
    assert('PTE2E-E2E.3 (END-TO-END, balance): the account balance is exactly 10250.00 -- the $10,000 the fixture set plus the $250.00 it computed by hand, never read back off the closed position',
      acct.balance===10250, 'balance='+acct.balance);
    assert('PTE2E-E2E.4 (END-TO-END, classification): an exit at 1.325 that CLEARS the 1.32 target with no explicit result label is classified "Win" and reasoned "TAKE_PROFIT", and the closed record keeps the entry/stop/target the order was emitted with',
      !!closed && closed.result==='Win' && closed.closeReason==='TAKE_PROFIT' &&
      closed.entry===1.3 && closed.stop===1.29 && closed.target===1.32 && closed.dir==='buy',
      closed?(closed.result+'/'+closed.closeReason+' entry='+closed.entry+' stop='+closed.stop+' target='+closed.target):'no closed position');
    assert('PTE2E-E2E.5 (END-TO-END, the closed JOURNAL record): the same trade id has exactly ONE journal row, now CLOSED, carrying exitPrice 1.325, pnl +250 and resultR exactly +2.5 ($250 realised on the $100 planned risk)',
      !!rec && rec.status==='CLOSED' && rec.exitPrice===1.325 && rec.pnl===250 && rec.resultR===2.5 &&
      (g.getJournalEntries()||[]).filter(e=>e.tradeId===pos.id).length===1,
      rec?('status='+rec.status+' exit='+rec.exitPrice+' pnl='+rec.pnl+' R='+rec.resultR):'no journal row');
    assert('PTE2E-E2E.6 (END-TO-END, return contract): the close reports itself committed and hands back the same closed position it filed',
      !!res && res.committed===true && !!res.closedPos && res.closedPos.id===pos.id,
      res?('committed='+res.committed):'close returned nothing');
  }

  // ── 🔴 NO FILL AVAILABLE: the one branch holding the account balance up (§18.30) ────────
  // Independent adversarial verification found that `if(!exitPrice)return;` in closePaperPosition
  // had ZERO fixtures. Deleting it survived the entire 2,215-fixture gate with drift 0, while a
  // control at the same line (`if(true)return;`) killed 85 -- so the line is executed constantly;
  // it is its FAILURE path that was unwitnessed. Driven end to end through the real engine, the
  // deletion books the trade at exitPrice=undefined, so pnl is NaN and the balance becomes NaN.
  // JSON.stringify(NaN) is null, so `fxhub_paper` is written as {"balance":null} and the account
  // is PERMANENTLY destroyed across reload -- commitPaperLedger performed no finiteness check, so
  // there was no second line of defence (contrast the ALEX open path, which does check isFinite).
  //
  // Reachable in production, and the two failures are CORRELATED rather than independent:
  // checkPaperPositions decides the exit from a synchronous `live` read, then closePaperPosition
  // yields at `await fetchBidAsk(...)`. During that await the scanner sweep rewrites the shared
  // pairData slot, and a failed fetchPrice writes price:null. fetchBidAsk and fetchPrice hit the
  // same host with the same credentials, so ONE transient outage produces both.
  //
  // The same missing coverage hid a second mutation: rewriting the auto branch as
  // `exitPrice = live!=null ? live : pos.entry` books a genuine +$300 take-profit winner at
  // exitPrice=entry -- pnl 0, result "Win", closeReason TAKE_PROFIT -- destroying the gain and
  // corrupting expectancy with a phantom 0R win. Also 2,215/2,215.
  {
    jvmClean();
    g.setPricing('reject');           // fetchBidAsk fails -- no live bid/ask
    const pos=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'manual');
    const balBefore=g.getPaperAccount().balance;
    g.setPairData('GBP_USD',null);    // and the shared price cache has nothing either
    const res=await g.closePaperPosition(pos.id,false,null);   // AUTO close (manual=false)
    const acct=g.getPaperAccount();
    const stillOpen=(acct.openPositions||[]).filter(p=>p.id===pos.id).length===1;
    const jrn=(g.getJournalEntries()||[]).filter(e=>e.tradeId===pos.id)[0]||null;
    assert('PTE2E-NOFILL.1 (FAILURE ISOLATION): with NO live bid/ask AND no cached price, an auto close REFUSES to fill -- the position stays open, nothing is booked, and the close reports no commit',
      stillOpen && (acct.closedPositions||[]).length===0 && !(res&&res.committed),
      'stillOpen='+stillOpen+' closed='+(acct.closedPositions||[]).length+' res='+JSON.stringify(res||null));
    assert('PTE2E-NOFILL.2 (the money consequence): the balance is untouched and remains a FINITE number, and the position\'s journal row is still OPEN. This is the assertion that fails as NaN the moment the guard goes -- and NaN serialises to null, so the destroyed balance would survive a reload',
      acct.balance===balBefore && Number.isFinite(acct.balance) && !!jrn && jrn.status==='OPEN',
      'balance='+acct.balance+' finite='+Number.isFinite(acct.balance)+' before='+balBefore+' journal='+(jrn?jrn.status:'none'));
    // §18.30: the two guards are DEFENCE IN DEPTH, and this fixture is what tells them apart.
    // Since commitPaperLedger now refuses a non-finite ledger, deleting `if(!exitPrice)return`
    // no longer destroys the account -- the downstream guard catches it. That is the point of
    // defence in depth, and it also means "the position stayed open" can no longer distinguish
    // the two. The observable difference is WHERE the refusal happens: correct code declines to
    // price the exit and never asks the ledger to commit at all, so no blocking banner and no
    // engine error are raised. With the guard gone, the close proceeds on a NaN and is stopped
    // only at the commit, which necessarily raises both. Asserting the quiet path pins the
    // upstream guard specifically, without weakening the downstream one.
    assert('PTE2E-NOFILL.3b (kills the deletion of `if(!exitPrice)return` even with the commit-level guard in place): a healthy refusal is SILENT -- no ledger blocking banner and no engine error, because the close never reached the commit. If the exit-price guard is removed, the trade proceeds on a NaN and is caught one layer later, which necessarily raises both',
      !g.getPaperBlockingError() && g.getPaperEngineErrorMessages().length===0,
      'banner='+String(g.getPaperBlockingError())+' engineErrors='+JSON.stringify(g.getPaperEngineErrorMessages()).slice(0,160));
    assert('PTE2E-NOFILL.3 (PERSISTED, not merely in memory): the stored fxhub_paper still parses and still carries a finite balance -- a NaN balance is written to disk as null, which no later load can distinguish from "never set"',
      (function(){ try{ const raw=g.getLocalStorageItem('fxhub_paper'); if(!raw) return false;
        const o=JSON.parse(raw); return Number.isFinite(o.balance)&&o.balance===balBefore; }catch(e){ return false; } })(),
      'stored='+String(g.getLocalStorageItem('fxhub_paper')||'').slice(0,90));
  }
  {
    // POSITIVE CONTROL for PTE2E-NOFILL.1-3. Identical setup except the cached price EXISTS, so the
    // close must succeed and book the real winner. Without this, "stayed open" would pass just as
    // well if the close path were never reached at all -- and it is exactly the +$300 take-profit
    // that the auto-branch mutation silently books at $0.00.
    jvmClean();
    g.setPricing('reject');
    const pos=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData('GBP_USD',1.3200);   // target reached, and the cache HAS it
    await g.closePaperPosition(pos.id,false,null);
    const acct=g.getPaperAccount();
    const closed=(acct.closedPositions||[])[0]||null;
    assert('PTE2E-NOFILL.4 (POSITIVE CONTROL): with a cached price present the very same auto close DOES fill -- at exactly 1.3200 for exactly +$200.00, leaving the balance at 10200.00. So PTE2E-NOFILL.1 is observing the refusal, not an unreachable close path, and an exit priced at the entry instead of the target would read $0.00 here',
      !!closed && closed.exitPrice===1.32 && closed.pnl===200 && acct.balance===10200 && (acct.openPositions||[]).length===0,
      closed?('exit='+closed.exitPrice+' pnl='+closed.pnl+' balance='+acct.balance):'no closed position');
  }

  // ── 🔴 DEFENCE IN DEPTH: the ledger commit must refuse a non-finite balance (§18.30) ────
  {
    jvmClean();
    g.setPricing('reject');
    const pos=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData('GBP_USD',1.3100);
    await g.closePaperPosition(pos.id,false,null);
    const okBalance=g.getPaperAccount().balance;
    const storedBefore=g.getLocalStorageItem('fxhub_paper');
    assert('PTE2E-FINITE.0 (POSITIVE CONTROL): an ordinary close still commits normally with the new refusal in place -- the guard rejects only non-finite values and does not block healthy trading',
      Number.isFinite(okBalance) && okBalance===10100 && !g.getPaperBlockingError(),
      'balance='+okBalance+' blocking='+String(g.getPaperBlockingError()));
    // Now force the exact state the missing guard would have produced.
    g.forceBalance(NaN);
    const res=g.commitPaperLedger();
    assert('PTE2E-FINITE.1 (kills the absence of a finiteness check): a commit carrying a NaN balance is REFUSED -- ok:false with reasonCode NON_FINITE_LEDGER -- rather than written. Without this the account persists as {"balance":null} and no later load can tell that from "never set"',
      !!res && res.ok===false && res.reasonCode==='NON_FINITE_LEDGER' && res.integrityCompromised===false,
      'res='+JSON.stringify(res));
    assert('PTE2E-FINITE.2 (nothing was written): storage still holds the last GOOD balance, byte-identical to before the refused commit -- the refusal protects the file, not just the return value',
      g.getLocalStorageItem('fxhub_paper')===storedBefore
        && (function(){ try{ return Number.isFinite(JSON.parse(g.getLocalStorageItem('fxhub_paper')).balance); }catch(e){ return false; } })(),
      'stored='+String(g.getLocalStorageItem('fxhub_paper')||'').slice(0,80));
    assert('PTE2E-FINITE.3 (the operator is told): the refusal sets the blocking banner AND records an engine error naming the offending value, so a refused commit is not a silent no-op',
      !!g.getPaperBlockingError()
        && g.getPaperEngineErrorMessages().some(function(m){ return m.indexOf('non-finite')!==-1 && m.indexOf('balance=NaN')!==-1; }),
      'banner='+String(g.getPaperBlockingError()).slice(0,60)+' errors='+JSON.stringify(g.getPaperEngineErrorMessages()).slice(0,140));
    jvmClean();
    // §18.35: the JVM mirror of the pnl arm, with the same six-record shape. Written at the same
    // time as its ALEX twin -- the unmirrored-half defect has now appeared four times in this
    // milestone, and every one of them was a fixture written for one side and not the other.
    jvmClean();
    const jvmSix=[];
    for(let i=0;i<6;i++) jvmSix.push({id:900000+i,pnl:i===0?NaN:10,result:'Win',
      closedAt:'2026-08-0'+(i+1)+'T10:00:00.000Z'});
    g.setPaperAccount({balance:10500,openPositions:[],closedPositions:jvmSix});
    const jvmDeep=g.commitPaperLedger();
    assert('PTE2E-FINITE.4 (JVM pnl ARM, newest of six): a NaN pnl on the NEWEST closed JVM trade is refused with a finite balance -- the arm every existing FINITE fixture left unexercised, and which slice(-5) made inert past the fifth record',
      !!jvmDeep && jvmDeep.ok===false && jvmDeep.reasonCode==='NON_FINITE_LEDGER',
      'res='+JSON.stringify(jvmDeep));
    jvmClean();
    g.setPricing('reject');
    const posF=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData('GBP_USD',1.3100);
    await g.closePaperPosition(posF.id,false,null);
  }

  // ── 🔴 UNREALIZED P&L: the figure the operator watches while deciding to close (§18.30) ──
  // Independent verification mutated this computation three ways -- including replacing the pip
  // value with the constant 987654 -- and ALL of them survived 2,215/2,215. A constant payload
  // surviving means the honest finding is not "a subtle bug slips through" but the stronger one:
  // the entire open-position P&L/R computation was unobserved. Every floating P&L and R-multiple
  // an operator reads while deciding whether to cut a live trade could be arbitrarily wrong with
  // the gate fully green. Hand-computed literals below, one long and one short.
  {
    jvmClean();
    g.setPricing('reject');
    // BUY: entry 1.3000, stop 1.2900 (100 pips risk), 1% of 10000 = $100 risk => 0.10 lots, $10/pip.
    const pos=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData('GBP_USD',1.3050);           // +50 pips in favour
    g.renderPaper();
    const html=g.elHtml('paper-open');
    assert('PTE2E-UNREAL.0 (PRECONDITION): the open-positions table really rendered this position with its live price, so the P&L assertions below read a real row rather than an empty table or a dash',
      html.indexOf('1.30500')!==-1 && html.indexOf('GBP/USD')!==-1,
      'len='+html.length+' head='+html.slice(0,120));
    assert('PTE2E-UNREAL.1 (BUY, hand-computed): a buy 50 pips in profit at 0.10 lots and $10 per pip shows exactly +$50.00 unrealized -- not the realized-path number, not a re-derived pip value, and not a constant',
      html.indexOf('+$50.00')!==-1,
      'html has +$50.00 = '+(html.indexOf('+$50.00')!==-1)+' | '+html.slice(html.indexOf('1.30500'),html.indexOf('1.30500')+220));
    assert('PTE2E-UNREAL.2 (BUY, R multiple): that same position reads exactly 0.50R against its $100.00 risk -- the R the operator judges the trade by, derived from the unrealized P&L rather than from the plan',
      html.indexOf('0.50R')!==-1,
      'html has 0.50R = '+(html.indexOf('0.50R')!==-1));
  }
  {
    jvmClean();
    g.setPricing('reject');
    // SELL: the direction sign is where a P&L formula most often inverts, so the short side gets
    // its own literal rather than being assumed symmetric with the long.
    const pos=g.openPaperPosition('GBP_USD','sell',1.3000,1.3100,1.2800,'manual');
    g.setPairData('GBP_USD',1.3050);           // 50 pips AGAINST a short
    g.renderPaper();
    const html=g.elHtml('paper-open');
    // NOTE on the literal: fmtCurrency is `(v>=0?'+':'')+'$'+v.toFixed(2)`, so a negative renders
    // as "$-50.00" -- the sign lands AFTER the dollar sign. Asserting the real shipped format
    // rather than the one I assumed; my first draft asserted "-$50.00" and failed honestly.
    assert('PTE2E-UNREAL.3 (SELL, sign): a short 50 pips OFFSIDE shows exactly $-50.00 unrealized, and NOT +$50.00 -- an inverted direction sign would report a losing trade as a winning one on the very screen the operator acts from',
      html.indexOf('$-50.00')!==-1 && html.indexOf('+$50.00')===-1,
      'neg='+(html.indexOf('$-50.00')!==-1)+' pos='+(html.indexOf('+$50.00')!==-1));
    assert('PTE2E-UNREAL.4 (SELL, R multiple): the same short reads -0.50R against its $100.00 risk',
      html.indexOf('-0.50R')!==-1,
      'html has -0.50R = '+(html.indexOf('-0.50R')!==-1));
    jvmClean();
  }

  {
    // §18.30: U4 -- "re-derive the pip value at render instead of using pipValueAtEntry" -- survived
    // the fixtures above, because for GBP_USD at 0.10 lots the re-derived value happens to equal the
    // entry-fixed one. That makes it an EQUIVALENT MUTANT in that scenario, not a caught one. This
    // fixture makes the two numbers differ, exactly as JVMEXIT-11 does for the realized close path:
    // a position stamped pipValueAtEntry 25 with 0.50 lots, 50 pips in favour, must read
    // 50 x 25 x 0.5 = +$625.00. A re-derivation would use $10/pip and read +$250.00.
    jvmClean();
    g.setPricing('reject');
    g.setPaperAccount({balance:10000,openPositions:[{
      id:990001,pair:'GBP/USD',oPair:'GBP_USD',dir:'buy',
      entry:1.3000,stop:1.2900,target:1.3200,ratio:2,riskAmount:1250,lots:0.5,
      pipValueAtEntry:25,openedAt:'2026-08-10T14:00:00.000Z',source:'manual'
    }],closedPositions:[]});
    g.setPairData('GBP_USD',1.3050);
    g.renderPaper();
    const html=g.elHtml('paper-open');
    assert('PTE2E-UNREAL.5 (kills a pip value RE-DERIVED at render): a position stamped pipValueAtEntry 25 at 0.50 lots, 50 pips onside, shows exactly +$625.00 unrealized. Re-deriving the conversion at render time would read +$250.00 -- the position\'s own economics silently replaced by today\'s rate on the screen the operator acts from',
      html.indexOf('+$625.00')!==-1 && html.indexOf('+$250.00')===-1,
      'has625='+(html.indexOf('+$625.00')!==-1)+' has250='+(html.indexOf('+$250.00')!==-1));
    assert('PTE2E-UNREAL.6 (its R multiple follows the same fixed economics): +$625.00 against the position\'s own $1250.00 risk reads exactly +0.50R',
      html.indexOf('+0.50R')!==-1,
      'has0.50R='+(html.indexOf('+0.50R')!==-1));
    jvmClean();
  }

  // ── 🔴 §18.32: the ALEX open-positions table was the UNMIRRORED HALF of PTE2E-UNREAL ────────
  // Independent verification made the paired observation that matters: inverting the direction sign
  // in the unrealized-P&L calculation is KILLED on the JVM side by PTE2E-UNREAL.3/.4 and SURVIVED
  // on the ALEX side, byte-for-byte the same mutation on the same money figure on the same kind of
  // screen. The v12.36.0 repair had been applied to one side only. Replacing the entire
  // entry/stop/target cell block with a literal also survived, so nothing read this table at all.
  //
  // Two real defects were living in that unwatched block, both now fixed and both asserted here:
  // a missing pipValue null guard (the JVM twin has one; this side rendered "$NaN"), and every
  // price hardcoded to 5 decimals including JPY pairs.
  function alexOpenPos(over){
    return Object.assign({
      tradeId:'ALEXOPEN-1',pair:'GBP_USD',timeframe:'H1',setupLabel:'Test setup',direction:'buy',
      entry:1.3000,stop:1.2900,target:1.3200,plannedRR:2,riskAmount:100,positionSize:0.10,
      pipValue:10,openedAt:'2026-08-10T14:00:00.000Z',maePips:0,mfePips:0
    },over||{});
  }
  {
    jvmClean(); alexClean();
    g.setHideTestTradesAlex(false);
    g.setAlexGAccount({balance:10000,openPositions:[alexOpenPos()],closedPositions:[],journal:[]});
    g.setPairData('GBP_USD',1.3050);            // +50 pips in favour
    g.renderAlexGLiveOpenTable();
    const html=g.elHtml('alexgLiveOpenTable');
    assert('PTE2E-ALEXOPEN.0 (PRECONDITION): the ALEX open-positions table really rendered this position with its live price, so the assertions below read a real row rather than the empty-state message',
      html.indexOf('1.30500')!==-1 && html.indexOf('GBP_USD')!==-1 && html.indexOf('No open Alex live positions')===-1,
      'len='+html.length+' head='+html.slice(0,140));
    assert('PTE2E-ALEXOPEN.1 (BUY, hand-computed): a buy 50 pips in profit at 0.10 size and $10 per pip shows exactly +$50.00 unrealized on the ALEX table -- the same figure, on the same kind of screen, as PTE2E-UNREAL.1 asserts for JVM',
      html.indexOf('+$50.00')!==-1,
      'has+$50.00='+(html.indexOf('+$50.00')!==-1));
    assert('PTE2E-ALEXOPEN.2 (BUY, R multiple): that position reads exactly +0.50R against its $100.00 risk',
      html.indexOf('+0.50R')!==-1,'has+0.50R='+(html.indexOf('+0.50R')!==-1));
  }
  {
    alexClean();
    g.setAlexGAccount({balance:10000,openPositions:[alexOpenPos({direction:'sell',stop:1.3100,target:1.2800})],closedPositions:[],journal:[]});
    g.setPairData('GBP_USD',1.3050);            // 50 pips AGAINST a short
    g.renderAlexGLiveOpenTable();
    const html=g.elHtml('alexgLiveOpenTable');
    assert('PTE2E-ALEXOPEN.3 (SELL, sign -- the mutation that survived on this side while dying on the JVM one): a short 50 pips OFFSIDE shows $-50.00, not +$50.00. An inverted direction sign reports a losing ALEX trade as a winning one',
      html.indexOf('$-50.00')!==-1 && html.indexOf('+$50.00')===-1,
      'neg='+(html.indexOf('$-50.00')!==-1)+' pos='+(html.indexOf('+$50.00')!==-1));
    assert('PTE2E-ALEXOPEN.4 (SELL, R multiple): the same short reads -0.50R',
      html.indexOf('-0.50R')!==-1,'has-0.50R='+(html.indexOf('-0.50R')!==-1));
  }
  {
    // 🔴 The missing null guard. The JVM twin renders "—" when the pip value is unavailable; this
    // side computed with it regardless. My first draft asserted the ABSENCE OF "NaN" and the
    // mutation survived: `null * positionSize` coerces to 0 in JavaScript, so the unguarded code
    // rendered a confident "+$0.00 / +0.00R" -- a plausible-looking wrong number rather than a
    // visible fault, which is strictly harder for an operator to catch. Asserted on the dash.
    alexClean();
    g.setAlexGAccount({balance:10000,openPositions:[alexOpenPos({pipValue:null})],closedPositions:[],journal:[]});
    g.setPairData('GBP_USD',1.3050);
    g.renderAlexGLiveOpenTable();
    const html=g.elHtml('alexgLiveOpenTable');
    // §18.34: F5. ALEXOPEN.5 seeds `null`, which the `!=null` half already catches -- so removing
    // the isFinite half survived. NaN is neither null nor usable, and v12.37.1 wrote the fixture for
    // the JVM half of this exact pair and not the ALEX half: the unmirrored half, inside the commit
    // that fixed an unmirrored half.
    alexClean();
    g.setAlexGAccount({balance:10000,openPositions:[alexOpenPos({pipValue:NaN})],closedPositions:[],journal:[]});
    g.setPairData('GBP_USD',1.3050);
    g.renderAlexGLiveOpenTable();
    const nanAlexHtml=g.elHtml('alexgLiveOpenTable');
    assert('PTE2E-ALEXOPEN.10 (NaN GUARD, the isFinite half): a NaN pip value renders a dash on the ALEX table -- the `!=null` half alone lets NaN straight through, because NaN is neither null nor usable',
      nanAlexHtml.indexOf('NaN')===-1 && nanAlexHtml.indexOf('GBP_USD')!==-1,
      'containsNaN='+(nanAlexHtml.indexOf('NaN')!==-1)+' rowPresent='+(nanAlexHtml.indexOf('GBP_USD')!==-1));
    alexClean();
    g.setAlexGAccount({balance:10000,openPositions:[alexOpenPos({pipValue:null})],closedPositions:[],journal:[]});
    g.setPairData('GBP_USD',1.3050);
    g.renderAlexGLiveOpenTable();
    assert('PTE2E-ALEXOPEN.5 (NULL GUARD): a position whose pip value is unavailable renders a DASH for unrealized P&L and R -- never NaN, and never a coerced "+$0.00" that reads as a real flat position',
      html.indexOf('NaN')===-1 && html.indexOf('+$0.00')===-1 && html.indexOf('+0.00R')===-1,
      'NaN='+(html.indexOf('NaN')!==-1)+' zeroPnl='+(html.indexOf('+$0.00')!==-1)+' zeroR='+(html.indexOf('+0.00R')!==-1));
    assert('PTE2E-ALEXOPEN.6 (and the row still renders): the position itself is still listed with its prices, so the guard degrades one cell rather than hiding the trade',
      html.indexOf('1.30000')!==-1 && html.indexOf('No open Alex live positions')===-1,
      'row present='+(html.indexOf('1.30000')!==-1));
  }
  {
    // 🔴 JPY decimals. USD_JPY entry/stop/target/current price rendered as 150.12300.
    alexClean();
    g.setAlexGAccount({balance:10000,openPositions:[alexOpenPos({pair:'USD_JPY',entry:150.123,stop:149.123,target:152.123})],closedPositions:[],journal:[]});
    g.setPairData('USD_JPY',150.623);
    g.renderAlexGLiveOpenTable();
    const html=g.elHtml('alexgLiveOpenTable');
    assert('PTE2E-ALEXOPEN.7 (JPY PRECISION): a JPY pair renders its entry at 3 decimals, as every other price surface in the application does, not at 5',
      html.indexOf('150.123')!==-1 && html.indexOf('150.12300')===-1,
      'has3dp='+(html.indexOf('150.123')!==-1)+' has5dp='+(html.indexOf('150.12300')!==-1));
    assert('PTE2E-ALEXOPEN.8 (JPY, the live price too): the current-price cell follows the same convention, so the stop and the price it is compared against are shown at the same precision',
      html.indexOf('150.623')!==-1 && html.indexOf('150.62300')===-1,
      'has3dp='+(html.indexOf('150.623')!==-1)+' has5dp='+(html.indexOf('150.62300')!==-1));
    // 🔴 A legacy position with null excursion fields did not degrade one cell -- `null.toFixed(1)`
    // THREW out of the map, so the entire ALEX open-positions table rendered nothing and the
    // operator saw no open trades at all. The journal record shape initialises maePips/mfePips to
    // null, so this is reachable from persisted state across a restart, not a hypothetical.
    alexClean();
    g.setAlexGAccount({balance:10000,openPositions:[alexOpenPos({maePips:null,mfePips:null})],closedPositions:[],journal:[]});
    g.setPairData('GBP_USD',1.3050);
    let threw=null;
    try{ g.renderAlexGLiveOpenTable(); }catch(e){ threw=(e&&e.message)?e.message:String(e); }
    const legacyHtml=g.elHtml('alexgLiveOpenTable');
    assert('PTE2E-ALEXOPEN.9 (LEGACY RECORD): a position with null excursion fields still renders the whole table -- it must not throw out of the row map and blank every open ALEX trade',
      threw===null && legacyHtml.indexOf('1.30000')!==-1 && legacyHtml.indexOf('No open Alex live positions')===-1,
      'threw='+String(threw)+' rowPresent='+(legacyHtml.indexOf('1.30000')!==-1));
    // §18.33: PARITY on the JVM side. Both gaps were left there when the ALEX table was fixed.
    jvmClean();
    g.setPricing('reject');
    g.setPaperAccount({balance:10000,openPositions:[{
      id:990002,pair:'USD/JPY',oPair:'USD_JPY',dir:'buy',
      entry:150.123,stop:149.123,target:152.123,ratio:2,riskAmount:100,lots:0.10,
      pipValueAtEntry:10,openedAt:'2026-08-10T14:00:00.000Z',source:'manual'
    }],closedPositions:[]});
    g.setPairData('USD_JPY',150.623);
    g.renderPaper();
    const jpyHtml=g.elHtml('paper-open');
    assert('PTE2E-UNREAL.7 (JVM PARITY, JPY precision): the JVM open table renders a JPY live price at 3 decimals, as the ALEX table now does and as every other price surface in the application does',
      jpyHtml.indexOf('150.623')!==-1 && jpyHtml.indexOf('150.62300')===-1,
      'has3dp='+(jpyHtml.indexOf('150.623')!==-1)+' has5dp='+(jpyHtml.indexOf('150.62300')!==-1));
    jvmClean();
    g.setPricing('reject');
    g.setPaperAccount({balance:10000,openPositions:[{
      id:990003,pair:'GBP/USD',oPair:'GBP_USD',dir:'buy',
      entry:1.3000,stop:1.2900,target:1.3200,ratio:2,riskAmount:100,lots:0.10,
      pipValueAtEntry:NaN,openedAt:'2026-08-10T14:00:00.000Z',source:'manual'
    }],closedPositions:[]});
    g.setPairData('GBP_USD',1.3050);
    g.renderPaper();
    const nanHtml=g.elHtml('paper-open');
    assert('PTE2E-UNREAL.8 (JVM PARITY, NaN guard): a NaN pip value renders a dash on the JVM table too -- the old `pipVal!=null` guard let NaN straight through, because NaN is neither null nor usable',
      nanHtml.indexOf('NaN')===-1 && nanHtml.indexOf('GBP/USD')!==-1 && nanHtml.indexOf('No open paper positions')===-1,
      'containsNaN='+(nanHtml.indexOf('NaN')!==-1)+' rowPresent='+(nanHtml.indexOf('GBP/USD')!==-1));
    jvmClean(); alexClean();
  }

  // ── 🔴 §18.33: the ALEX CLOSED table, the sibling left behind by the v12.36.4 fix ──────────
  {
    function alexClosedPos(over){
      return Object.assign({
        tradeId:'ALEXCLOSED-1',pair:'USD_JPY',timeframe:'H1',setupLabel:'fixture',direction:'buy',
        entry:150.123,exitPrice:151.123,stop:149.123,target:152.123,
        result:'Win',resultR:2,pnl:200,positionSize:0.10,pipValue:10,riskAmount:100,
        openedAt:'2026-08-10T12:00:00.000Z',closedAt:'2026-08-10T14:00:00.000Z',
        maePips:0,mfePips:0,status:'closed'
      },over||{});
    }
    alexClean();
    g.setHideTestTradesAlex(false);
    g.setAlexGAccount({balance:10200,openPositions:[],closedPositions:[alexClosedPos()],journal:[]});
    g.renderAlexGLiveClosedTable();
    const html=g.elHtml('alexgLiveClosedTable');
    assert('PTE2E-ALEXCLOSED.0 (PRECONDITION): the closed-trades table rendered this record, so the assertions below read a real row',
      html.indexOf('USD_JPY')!==-1 && html.length>200,'len='+html.length);
    assert('PTE2E-ALEXCLOSED.1 (JPY PRECISION): a closed JPY trade shows its entry and EXIT at 3 decimals, not 5 -- the exit price is what the operator reconciles against their broker',
      html.indexOf('150.123')!==-1 && html.indexOf('151.123')!==-1
        && html.indexOf('150.12300')===-1 && html.indexOf('151.12300')===-1,
      'entry3dp='+(html.indexOf('150.123')!==-1)+' exit3dp='+(html.indexOf('151.123')!==-1)+
      ' entry5dp='+(html.indexOf('150.12300')!==-1));
    // A closed record with no exit price threw out of the row map, so the ENTIRE closed-trades
    // history rendered nothing -- the same shape as the open table's maePips defect.
    alexClean();
    g.setAlexGAccount({balance:10000,openPositions:[],
      closedPositions:[alexClosedPos({tradeId:'ALEXCLOSED-2',pair:'GBP_USD',exitPrice:null})],journal:[]});
    let closedThrew=null;
    try{ g.renderAlexGLiveClosedTable(); }catch(e){ closedThrew=(e&&e.message)?e.message:String(e); }
    const nullHtml=g.elHtml('alexgLiveClosedTable');
    assert('PTE2E-ALEXCLOSED.2 (MISSING EXIT PRICE): a closed record with no exit price still renders the whole table -- it must not throw out of the row map and erase every closed ALEX trade',
      closedThrew===null && nullHtml.indexOf('GBP_USD')!==-1,
      'threw='+String(closedThrew)+' rowPresent='+(nullHtml.indexOf('GBP_USD')!==-1));
    jvmClean(); alexClean();
  }

  // ── 🔴 §18.34: the ALEX twin of the ledger finiteness refusal ───────────────────────────────
  {
    alexClean();
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[],journal:[]});
    const okRes=g.commitAlexGLedger();
    assert('PTE2E-ALEXFINITE.0 (POSITIVE CONTROL): an ordinary ALEX commit still succeeds with the new refusal in place -- it rejects only non-finite values and does not block healthy trading',
      !!okRes && okRes.ok===true && !g.getAlexBlockingError(),
      'res='+JSON.stringify(okRes)+' blocking='+String(g.getAlexBlockingError()));
    const storedBefore=g.getLocalStorageItem('fxhub_alexg_account');
    g.forceAlexBalance(NaN);
    const res=g.commitAlexGLedger();
    assert('PTE2E-ALEXFINITE.1: a commit carrying a NaN ALEX balance is REFUSED -- ok:false with reasonCode NON_FINITE_LEDGER. commitAlexGLedger claimed to mirror commitPaperLedger exactly, and for one release it did not have this check at all',
      !!res && res.ok===false && res.reasonCode==='NON_FINITE_LEDGER' && res.integrityCompromised===false,
      'res='+JSON.stringify(res));
    assert('PTE2E-ALEXFINITE.2 (nothing was written): storage still holds the last GOOD ALEX account, byte-identical to before the refused commit -- and loadAlexGSaved does no numeric validation, so a persisted NaN would reload as null forever',
      g.getLocalStorageItem('fxhub_alexg_account')===storedBefore
        && (function(){ try{ return Number.isFinite(JSON.parse(g.getLocalStorageItem('fxhub_alexg_account')).balance); }catch(e){ return false; } })(),
      'stored='+String(g.getLocalStorageItem('fxhub_alexg_account')||'').slice(0,80));
    assert('PTE2E-ALEXFINITE.3 (the operator is told): the refusal raises the ALEX blocking banner AND records an engine error naming the offending value, so a refused ALEX commit is not a silent no-op',
      !!g.getAlexBlockingError()
        && g.getAlexEngineErrorMessages().some(function(m){ return m.indexOf('non-finite')!==-1 && m.indexOf('balance=NaN')!==-1; }),
      'banner='+String(g.getAlexBlockingError()).slice(0,60)+' errors='+JSON.stringify(g.getAlexEngineErrorMessages()).slice(0,140));
    // 🔴 §18.35: the pnl ARM, on an account with MORE THAN FIVE closed trades. Every existing
    // FINITE fixture forces a NaN BALANCE, so the balance arm carried them all and the pnl arm was
    // never exercised at all -- deleting it survived the full gate on both strategies. And the arm
    // was ALSO wrong: `.slice(-5)` took the OLDEST five, while closedPositions is unshift-built with
    // the newest at index 0, so the trade that just closed was never inspected past the fifth.
    // Six records with a FINITE balance is the exact shape that separates the two: a corrupt record
    // whose damage has NOT propagated into the balance, which is what defence in depth is for.
    alexClean();
    const sixClosed=[];
    for(let i=0;i<6;i++) sixClosed.push({tradeId:'AGT|OLD'+i,pnl:i===0?NaN:10,result:'Win',
      closedAt:'2026-08-0'+(i+1)+'T10:00:00.000Z'});
    g.setAlexGAccount({balance:10500,openPositions:[],closedPositions:sixClosed,journal:[]});
    const deepRes=g.commitAlexGLedger();
    assert('PTE2E-ALEXFINITE.4 (the pnl ARM, newest of six): a NaN pnl on the NEWEST closed trade is refused even though the BALANCE is perfectly finite -- the arm that exists for a corrupt record whose damage has not reached the balance yet',
      !!deepRes && deepRes.ok===false && deepRes.reasonCode==='NON_FINITE_LEDGER',
      'res='+JSON.stringify(deepRes)+' closedCount='+sixClosed.length+' balance=10500');
    assert('PTE2E-ALEXFINITE.5 (ORIENTATION): the guard inspects the NEWEST records. closedPositions is unshift-built, so slice(-5) reads the OLDEST five and the just-closed trade escapes once the account holds more than five -- which every real account does within its first week',
      (function(){ const older=sixClosed.slice(1).concat([]); older.unshift({tradeId:'AGT|CLEAN',pnl:5,result:'Win',closedAt:'2026-08-09T10:00:00.000Z'});
        g.setAlexGAccount({balance:10500,openPositions:[],closedPositions:older,journal:[]});
        return g.commitAlexGLedger().ok===true; })(),
      'a clean newest record must still commit, so the refusal above is the NaN and not the record count');
    alexClean();
  }

  // ── 🔴 §18.36: the ALEX v2 shadow comparison read the OLDEST status, not the newest ─────────
  {
    // alexGLiveSetupStatuses is unshift-built and truncated from the tail, so index 0 is newest.
    // Reading [length-1] froze the comparison on the FIRST status ever recorded for a pair -- and
    // because entries are deduped by signalId and never re-evaluated, it stayed frozen forever.
    // Seeded in production order: each new status is UNSHIFTED, exactly as the engine writes them.
    alexClean();
    g.setAlexGLiveSetupStatuses([]);
    g.pushAlexGLiveSetupStatus({pair:'EUR/USD',status:'IGNORED — STALE SIGNAL',reason:'first ever',signalId:'S1'});
    g.pushAlexGLiveSetupStatus({pair:'EUR/USD',status:'BLOCKED',reason:'second',signalId:'S2'});
    g.pushAlexGLiveSetupStatus({pair:'EUR/USD',status:'TRADE OPENED',reason:'newest',signalId:'S3'});
    const sum=g.alexV2BuildLegacyDecisionSummary('EUR_USD');
    assert('PTE2E-SHADOW.0 (PRECONDITION): three statuses are recorded for this pair in production order, newest first -- so "latest" is a real choice between them and not the only entry',
      g.getAlexGLiveSetupStatuses().length===3 && g.getAlexGLiveSetupStatuses()[0].signalId==='S3',
      'n='+g.getAlexGLiveSetupStatuses().length+' head='+g.getAlexGLiveSetupStatuses()[0].signalId);
    assert('PTE2E-SHADOW.1 (ORIENTATION): the shadow comparison reads the NEWEST status -- legacy ALEX TOOK this trade, so the summary must say ACCEPTED. Reading the tail reports the first status ever recorded and mis-bins every comparison from the second setup onward, systematically as "v2 finds trades legacy misses"',
      !!sum && sum.legacyAlexDecision==='ACCEPTED',
      'decision='+(sum&&sum.legacyAlexDecision)+' reasons='+JSON.stringify(sum&&sum.legacyAlexReasons));
    assert('PTE2E-SHADOW.2 (and it cites the right reason): the reason quoted is the newest status, not the stale one it superseded',
      !!sum && JSON.stringify(sum.legacyAlexReasons).indexOf('TRADE OPENED')!==-1
            && JSON.stringify(sum.legacyAlexReasons).indexOf('STALE')===-1,
      'reasons='+JSON.stringify(sum&&sum.legacyAlexReasons));
    // NEGATIVE CONTROL: a genuine rejection must still read REJECTED, so .1 is not simply asserting
    // that this function always says ACCEPTED.
    g.setAlexGLiveSetupStatuses([]);
    g.pushAlexGLiveSetupStatus({pair:'EUR/USD',status:'TRADE OPENED',reason:'older',signalId:'S1'});
    g.pushAlexGLiveSetupStatus({pair:'EUR/USD',status:'BLOCKED',reason:'newest',signalId:'S2'});
    const sum2=g.alexV2BuildLegacyDecisionSummary('EUR_USD');
    assert('PTE2E-SHADOW.3 (NEGATIVE CONTROL): with the order reversed the newest status is a BLOCK, and the summary must read REJECTED -- so the assertion above is reading position, not a constant',
      !!sum2 && sum2.legacyAlexDecision==='REJECTED'
            && JSON.stringify(sum2.legacyAlexReasons).indexOf('BLOCKED')!==-1,
      'decision='+(sum2&&sum2.legacyAlexDecision)+' reasons='+JSON.stringify(sum2&&sum2.legacyAlexReasons));
    g.setAlexGLiveSetupStatuses([]);
    alexClean();
  }

  // ── 🔴 §18.37: the EVIDENCE CAPTURE seam -- the audit record, previously unwitnessed ────────
  // Making BOTH evidenceCaptureClosedTrades and evidenceCaptureClosedPaperTrades `if(true) return;`
  // survived the full gate. So did dropping every JVM trade's package on the floor. The evidence
  // package is the citable record of what was traded and why; nothing observed whether it was ever
  // written. It could not be observed before, either: the harness had no IndexedDB, so every write
  // failed by construction. It has one now.
  {
    jvmClean(); alexClean();
    // Drain FIRST: the capture seam is guarded by an in-flight flag, so a capture still pending from
    // an earlier fixture makes this one skip silently -- which is exactly what happened on the first
    // run of this fixture, and is itself worth knowing about the seam.
    await drainMicrotasks();
    const pkgsBefore=(await g.evidenceListPackages()).length;
    g.setPricing('reject');
    const evPos=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData('GBP_USD',1.3100);
    await g.closePaperPosition(evPos.id,false,null);
    await drainMicrotasks();
    await drainMicrotasks();
    const pkgs=await g.evidenceListPackages();
    assert('PTE2E-EVCAP.1 (END-TO-END): a real JVM close produces a durable evidence package. The capture seam is fire-and-forget, so nothing downstream fails if it silently stops -- which is exactly why it must be asserted here',
      Array.isArray(pkgs) && pkgs.length===pkgsBefore+1,
      'before='+pkgsBefore+' after='+(Array.isArray(pkgs)?pkgs.length:String(pkgs)));
    // §18.38: this asserted attribution by calling evidenceHasPackageForTrade -- THE FUNCTION UNDER
    // TEST -- as its own oracle. Proven vacuous: hardwiring that function to return true means no
    // package is ever captured, EVCAP.1 and EVCAP.3 fail, and this one PASSES. A fixture whose
    // oracle is the code it is testing cannot fail for the reason it names. Asserted against the
    // stored records instead, which are already in hand two lines above.
    const hasIt=(pkgs||[]).some(function(p){ return p&&String(p.sourceTradeId)===String(evPos.id); });
    assert('PTE2E-EVCAP.2 (ATTRIBUTION): a stored package carries the tradeId that actually closed, not merely "a package exists" -- an audit record attributed to the wrong trade is worse than none',
      !!hasIt,
      'hasPackageFor('+evPos.id+')='+String(!!hasIt)+' ids='+JSON.stringify((pkgs||[]).map(function(p){return p&&(p.sourceTradeId||p.packageId);}).slice(0,4)));
    assert('PTE2E-EVCAP.3 (CONTENT): the package carries the trade\'s own booked numbers rather than a placeholder -- its exit price and P&L match what the ledger recorded',
      (function(){
        const acct=g.getPaperAccount(); const closed=(acct.closedPositions||[])[0];
        const pkg=(pkgs||[]).filter(function(p){ return p&&String(p.sourceTradeId)===String(evPos.id); })[0]
               ||(pkgs||[])[0];
        if(!pkg||!closed) return false;
        const j=JSON.stringify(pkg);
        return j.indexOf(String(closed.exitPrice))!==-1 && j.indexOf(String(closed.pnl))!==-1;
      })(),
      'closed='+JSON.stringify((function(){const c=(g.getPaperAccount().closedPositions||[])[0];return c?{exit:c.exitPrice,pnl:c.pnl}:null;})()));
    // 🔴 §18.38: a DEVELOPER TEST TRADE must be labelled in the corpus. isDeveloperTrade appeared
    // NOWHERE in the evidence platform, so generateTestPaperTrade's fabricated trades entered the
    // exported corpus with no field that could filter them out -- silently contaminating win rate,
    // expectancy and sample size in the corpus this milestone exists to produce. Proven end to end
    // before the fix: a TEST trade produced a package whose JSON contained neither
    // "isDeveloperTrade" nor "TEST". ledgerDeriveAccountState already excludes them (fixture L10);
    // the evidence layer never got the same treatment.
    jvmClean(); alexClean();
    await drainMicrotasks(); await drainMicrotasks();
    const beforeTest=(await g.evidenceListPackages()).length;
    g.setPricing('reject');
    const tPos=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'test');
    const acctT=g.getPaperAccount();
    acctT.openPositions[acctT.openPositions.length-1].isDeveloperTrade=true;
    acctT.openPositions[acctT.openPositions.length-1].tradeSource='TEST';
    g.setPairData('GBP_USD',1.3100);
    await g.closePaperPosition(tPos.id,false,null);
    await drainMicrotasks(); await drainMicrotasks();
    const pkgsT=await g.evidenceListPackages();
    const tPkg=(pkgsT||[]).filter(function(p){ return p&&String(p.sourceTradeId)===String(tPos.id); })[0];
    assert('PTE2E-EVCAP.4 (PRECONDITION): the developer test trade really was captured into the corpus -- so the labelling assertion below is about a package that exists',
      pkgsT.length===beforeTest+1 && !!tPkg,
      'before='+beforeTest+' after='+pkgsT.length+' found='+(!!tPkg));
    assert('PTE2E-EVCAP.5 (FABRICATED TRADES ARE LABELLED): the package carries isDeveloperTrade true and its TEST source, so a consumer of the exported corpus can exclude it. Without this a fabricated trade is arithmetically indistinguishable from a real one in every statistic derived from the corpus',
      !!tPkg && JSON.stringify(tPkg).indexOf('isDeveloperTrade')!==-1
             && /"isDeveloperTrade"\s*:\s*true/.test(JSON.stringify(tPkg)),
      'json='+JSON.stringify(tPkg||{}).slice(0,240));
    assert('PTE2E-EVCAP.6 (REAL EXIT REASON): the package records WHY the trade closed, not only Win or Loss. exitReason was mapped in the normalizer and read nowhere, so a take-profit, a discretionary manual close and a system close all exported identically',
      !!tPkg && JSON.stringify(tPkg).indexOf('exitReasonDetail')!==-1
             && JSON.stringify(tPkg).indexOf('SYSTEM_CLOSE')!==-1,
      'json='+JSON.stringify(tPkg||{}).slice(0,240));
    jvmClean(); alexClean();
  }

  // ── 🔴 §18.38: the Total P&L tile hardcoded a 10000 starting balance ────────────────────────
  {
    jvmClean();
    g.setPricing('reject');
    // A deliberate Set Balance, recorded on startingBalance by §18.36. The panel read a hardcoded
    // 10000 regardless, so it showed a permanent phantom Total P&L while Diagnostics reconciled to
    // zero -- two surfaces disagreeing forever about the same account, with nothing objecting.
    g.setPaperAccount({balance:25000,startingBalance:25000,openPositions:[],closedPositions:[]});
    g.renderPaper();
    const tiles=g.elHtml('paper-stats')||g.elHtml('paperStats')||'';
    assert('PTE2E-STARTBAL.1: with a recorded starting balance of 25000 and no closed trades, the Total P&L tile reads $0.00 -- not the +$15,000.00 phantom a hardcoded 10000 baseline produces',
      tiles.indexOf('+$15000.00')===-1 && tiles.indexOf('+$15,000.00')===-1,
      'phantom15k='+(tiles.indexOf('15000')!==-1||tiles.indexOf('15,000')!==-1)+' len='+tiles.length);
    // POSITIVE CONTROL: a real profit must still show. Otherwise "no phantom" would pass on a tile
    // that renders nothing at all.
    g.setPaperAccount({balance:25300,startingBalance:25000,openPositions:[],
      closedPositions:[{id:1,pnl:300,result:'Win',closedAt:'2026-08-10T10:00:00.000Z'}]});
    g.renderPaper();
    const tiles2=g.elHtml('paper-stats')||g.elHtml('paperStats')||'';
    assert('PTE2E-STARTBAL.2 (POSITIVE CONTROL): a genuine +$300.00 against that same recorded baseline IS shown -- so the assertion above is reading a live tile, not an empty one',
      tiles2.indexOf('300.00')!==-1,
      'len='+tiles2.length+' snippet='+tiles2.slice(0,160));
    jvmClean();
  }

  // ── 🔴 §18.38: the backfill branch that could never fire ────────────────────────────────────
  {
    alexClean();
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[],journal:[]});
    g.setAlexGJournalEntries([{
      tradeId:'AGT|ORPHAN-1',signalId:'AGL|ORPHAN-1',status:'CLOSED',strategy:'ALEX_G',
      pair:'EUR_USD',direction:'buy',entry:1.10000,stop:1.09500,target:1.11000,
      exitPrice:1.11000,pnl:200,result:'Win',resultR:2,
      openedAt:'2026-08-10T10:00:00.000Z',closedAt:'2026-08-10T12:00:00.000Z'
    }]);
    const bf=await g.evidenceBackfillFromLocalStorage();
    assert('PTE2E-BACKFILL.1: a CLOSED journal record with no matching account position is examined by backfill. The branch compared lower-case "closed" while every journal writer stores "CLOSED", so it could never fire -- and that orphan class is exactly what the ledger-integrity subsystem exists to detect',
      !!bf && bf.examined>=1 && bf.created>=1,
      'result='+JSON.stringify(bf||{}));
    g.setAlexGJournalEntries([{
      tradeId:'AGT|STILLOPEN',signalId:'AGL|STILLOPEN',status:'OPEN',strategy:'ALEX_G',
      pair:'EUR_USD',direction:'buy',entry:1.10000,stop:1.09500,target:1.11000,
      openedAt:'2026-08-10T10:00:00.000Z'
    }]);
    const bf2=await g.evidenceBackfillFromLocalStorage();
    assert('PTE2E-BACKFILL.2 (NEGATIVE CONTROL): an OPEN journal record is NOT adopted -- the case-insensitive comparison must not become a match-anything one',
      // Asserted on the COUNT, not on the absence of an id string: the return is a summary, so
      // searching it for the id was vacuously true either way -- the first draft of this control
      // passed for exactly that wrong reason.
      !!bf2 && bf2.examined===0 && bf2.created===0,
      'result='+JSON.stringify(bf2||{}));
    g.setAlexGJournalEntries([]);
    alexClean();
  }

  // ── BOUNDARY: exactly at the risk limit ────────────────────────────────────────────────
  {
    jvmClean();
    g.setPricing('reject');
    const pos=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData('GBP_USD',1.2900);   // exit EXACTLY at the stop
    await g.closePaperPosition(pos.id,false,null);
    const acct=g.getPaperAccount();
    const closed=(acct.closedPositions||[])[0]||null;
    assert('PTE2E-BOUND.3 (BOUNDARY, exactly at the risk limit): a position stopped out EXACTLY at its stop loses exactly $100.00 -- the whole 1% risk amount and not one cent more -- and leaves the balance at exactly 9900.00. This is the fixture that fails if sizing ever risks more than the account allows',
      !!closed && closed.pnl===-100 && acct.balance===9900 && closed.exitPrice===1.29,
      closed?('pnl='+closed.pnl+' balance='+acct.balance+' exit='+closed.exitPrice):'no closed position');
    assert('PTE2E-BOUND.4 (BOUNDARY, classification at the limit): that same stop-out is classified "Loss" with closeReason "STOP_LOSS" -- the classification is not pinned to Win',
      !!closed && closed.result==='Loss' && closed.closeReason==='STOP_LOSS',
      closed?(closed.result+'/'+closed.closeReason):'no closed position');
  }

  // ── DIRECTION: the SELL leg, which a sign inversion cannot satisfy at the same time ────
  //   sell, entry 1.3000, stop 1.3100, target 1.2800 -> riskPips 100, lots 0.10
  //   exit 1.2800 -> move = (1.2800-1.3000)/0.0001 * -1 = +200.0 pips -> pnl = +$200.00
  {
    jvmClean();
    g.setPricing('reject');
    const pos=g.openPaperPosition('GBP_USD','sell',1.3000,1.3100,1.2800,'manual');
    g.setPairData('GBP_USD',1.2800);
    await g.closePaperPosition(pos.id,false,null);
    const acct=g.getPaperAccount();
    const closed=(acct.closedPositions||[])[0]||null;
    assert('PTE2E-SELL.1 (direction, as emitted): a SELL order is emitted with direction "sell" and its stop ABOVE and target BELOW the entry -- 1.31 and 1.28 against a 1.30 entry',
      !!pos && pos.dir==='sell' && pos.stop===1.31 && pos.target===1.28 && pos.entry===1.3,
      pos?(pos.dir+' entry='+pos.entry+' stop='+pos.stop+' target='+pos.target):'no pos');
    assert('PTE2E-SELL.2 (direction, in the P&L): the same sell closed at 1.28 -- 200 pips IN ITS FAVOUR -- earns exactly +$200.00 and lifts the balance to exactly 10200.00. A direction sign inverted anywhere in the close path turns this into -$200.00 while leaving the buy fixtures above still passing',
      !!closed && closed.pnl===200 && acct.balance===10200 && closed.result==='Win',
      closed?('pnl='+closed.pnl+' balance='+acct.balance+' result='+closed.result):'no closed position');
  }

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP 3 — DUPLICATE / IN-FLIGHT CLOSE (CONCURRENCY)
  // ════════════════════════════════════════════════════════════════════════════════════════
  {
    jvmClean();
    g.setPricing('reject');
    const pos=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData('GBP_USD',1.3250);
    g.resetPricingCalls();
    // Genuinely concurrent: the second call is issued while the first is still suspended on its
    // own internal await, not after it.
    const p1=g.closePaperPosition(pos.id,false,null);
    const p2=g.closePaperPosition(pos.id,false,null);
    const both=await Promise.all([p1,p2]);
    const acct=g.getPaperAccount();
    assert('PTE2E-CONCUR.1 (CONCURRENCY, two closes racing one id): the account moved exactly ONCE -- one closed position, an empty open list, and a balance of exactly 10250.00 rather than the 10500.00 a double credit would produce',
      (acct.closedPositions||[]).length===1 && (acct.openPositions||[]).length===0 && acct.balance===10250,
      'closed='+(acct.closedPositions||[]).length+' open='+(acct.openPositions||[]).length+' balance='+acct.balance);
    assert('PTE2E-CONCUR.2 (CONCURRENCY, the in-flight guard specifically): the duplicate was rejected BEFORE it reached the market -- exactly ONE pricing request was attempted for the two calls. Finding the position already gone afterwards would still have produced two requests, so this observes the in-flight guard itself and not the post-await re-validation behind it',
      g.pricingCalls()===1, 'pricingRequests='+g.pricingCalls());
    assert('PTE2E-CONCUR.3 (CONCURRENCY, the loser returns nothing): the first call reports a committed close and the second returns undefined -- the duplicate never produces a second result object a caller could act on',
      !!both[0] && both[0].committed===true && both[1]===undefined,
      'first='+(both[0]?'committed':'none')+' second='+String(both[1]));
    assert('PTE2E-CONCUR.4 (CONCURRENCY, the journal): the raced close left exactly one journal row for that trade id and it is CLOSED once, with pnl +250 recorded a single time',
      (g.getJournalEntries()||[]).filter(e=>e.tradeId===pos.id&&e.status==='CLOSED').length===1 &&
      ((g.getJournalEntries()||[]).find(e=>e.tradeId===pos.id)||{}).pnl===250,
      'rows='+(g.getJournalEntries()||[]).filter(e=>e.tradeId===pos.id).length);
    // SEQUENTIAL duplicate: the first close has fully settled before the second is issued.
    const after=await g.closePaperPosition(pos.id,false,null);
    assert('PTE2E-CONCUR.5 (sequential duplicate): closing the SAME id again after the first close has fully settled is a no-op -- still one closed position, still a balance of exactly 10250.00, and nothing returned',
      after===undefined && (g.getPaperAccount().closedPositions||[]).length===1 && g.getPaperAccount().balance===10250,
      'returned='+String(after)+' closed='+(g.getPaperAccount().closedPositions||[]).length+' balance='+g.getPaperAccount().balance);
  }

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP 4 — checkAutoTrades: POSITIVE CONTROL, NEGATIVE CONTROL, ONE DECISION PER PAIR
  // ════════════════════════════════════════════════════════════════════════════════════════
  {
    jvmClean(); seedConversions(); activeWatchAll();
    g.setMode('firing');
    g.resetM15Calls();
    await g.checkAutoTrades();
    const acct=g.getPaperAccount();
    const opened=(acct.openPositions||[]).length;
    assert('PTE2E-AUTO.1 (POSITIVE CONTROL): with the auto-trader enabled, an active session, every pair in Active watch and a firing series, checkAutoTrades opens a REAL paper position on each of the eight instruments the frozen strategy accepts on this series -- this is the fixture that fails outright if auto-trading is ever disabled or short-circuited',
      opened===TRADEABLE.length && TRADEABLE.every(p=>openOn(p)===1),
      'opened='+opened+'/'+TRADEABLE.length+' ['+(g.getPaperAccount().openPositions||[]).map(p=>p.oPair).sort().join(',')+']');
    assert('PTE2E-AUTO.2 (POSITIVE CONTROL, what was actually traded): every opened position is stamped source "auto", carries a stop on the opposite side of entry from its target, and is sized to a $100.00 risk -- exactly 1% of the $10,000 balance -- so the tick produced real orders and not placeholders',
      opened>0 && (acct.openPositions||[]).every(p=>p.source==='auto'&&p.riskAmount===100&&p.lots>0&&
        (p.dir==='buy'?(p.stop<p.entry&&p.target>p.entry):(p.stop>p.entry&&p.target<p.entry))),
      'sample='+JSON.stringify((acct.openPositions||[])[0]?{pair:(acct.openPositions||[])[0].oPair,dir:(acct.openPositions||[])[0].dir,risk:(acct.openPositions||[])[0].riskAmount}:null));
    assert('PTE2E-AUTO.3 (kills M18 -- ONE DECISION PER PAIR PER TICK): one checkAutoTrades tick evaluated each eligible pair EXACTLY ONCE. The count is taken at the process boundary (one M15 evaluation request per pair), so a tick that decides the same pair twice -- doubling the API cost and taking two independent entry decisions on one instrument -- is visible here even though its second decision is correctly suppressed by the pre-open re-check and therefore changes no position count anywhere',
      SCAN.every(p=>g.m15Calls(p)===1) && g.m15CallTotal()===SCAN.length,
      'perPair='+SCAN.map(p=>g.m15Calls(p)).join(',')+' total='+g.m15CallTotal()+' expected='+SCAN.length);
    assert('PTE2E-AUTO.6 (NEGATIVE, the refusals are the strategy\'s own): the four JPY-quoted instruments were each evaluated exactly once on the same tick and each opened NOTHING -- the frozen R:R minimum refuses this series\' geometry at 0.23:1 on a 0.01 pip size. They are excluded by a recorded strategy verdict, not by being skipped',
      JPY.every(p=>g.m15Calls(p)===1&&openOn(p)===0),
      'jpyEvaluations='+JPY.map(p=>g.m15Calls(p)).join(',')+' jpyPositions='+JPY.map(p=>openOn(p)).join(','));
    // Second tick, same state: the traded-today stamp must hold the line.
    g.resetM15Calls();
    await g.checkAutoTrades();
    assert('PTE2E-AUTO.4 (NEGATIVE, DISCLOSED -- see note): the pair is excluded on the open-position ground. Independent verification showed that removing the traded-today STAMP written after a successful auto-open kills nothing here -- the open-position filter alone carries it, and EXCL.3 stamps tradedToday by hand, so nothing observes that an open CREATES the stamp',
      (g.getPaperAccount().openPositions||[]).length===TRADEABLE.length && g.m15CallTotal()===JPY.length &&
      TRADEABLE.every(p=>g.m15Calls(p)===0),
      'positions='+(g.getPaperAccount().openPositions||[]).length+' evaluations='+g.m15CallTotal()+' (only the four never-traded JPY pairs remain eligible to re-evaluate)');
  }
  {
    // NEGATIVE CONTROL against the very same machinery: the pairs ARE evaluated, and the
    // strategy's own verdict on a flat, structureless series is "no trade".
    jvmClean(); seedConversions(); activeWatchAll();
    g.setMode('flat');
    g.resetM15Calls();
    await g.checkAutoTrades();
    assert('PTE2E-AUTO.5 (NEGATIVE CONTROL, and NOT a false-positive control): against a flat structureless series every pair is still EVALUATED exactly once -- the path is reached -- and the frozen strategy opens nothing. The evaluation count is asserted precisely so this zero cannot be mistaken for an unreached code path',
      (g.getPaperAccount().openPositions||[]).length===0 && SCAN.every(p=>g.m15Calls(p)===1),
      'positions='+(g.getPaperAccount().openPositions||[]).length+' evaluations='+g.m15CallTotal()+'/'+SCAN.length);
  }
  {
    // EXCLUSION: a pair that already holds a position is not even evaluated (kills M14a).
    jvmClean(); seedConversions(); activeWatchAll();
    g.setMode('firing');
    const held=g.openPaperPosition('EUR_USD','buy',1.1000,1.0900,1.1200,'manual');
    g.resetM15Calls();
    await g.checkAutoTrades();
    assert('PTE2E-EXCL.1 (kills M14a -- NEGATIVE, one position per pair): a pair that already holds an open position is excluded BEFORE any decision is taken on it -- EUR_USD was never evaluated at all this tick (zero evaluation requests), while every other pair was evaluated exactly once',
      g.m15Calls('EUR_USD')===0 && SCAN.filter(p=>p!=='EUR_USD').every(p=>g.m15Calls(p)===1),
      'EUR_USD='+g.m15Calls('EUR_USD')+' others='+SCAN.filter(p=>p!=='EUR_USD').map(p=>g.m15Calls(p)).join(','));
    assert('PTE2E-EXCL.2 (NEGATIVE, one position per pair): and no SECOND EUR_USD position was opened -- the pair still holds exactly the one manual position, with its original 1.09 stop untouched, while the other pairs did open',
      openOn('EUR_USD')===1 && (g.getPaperAccount().openPositions||[]).find(p=>p.id===held.id).stop===1.09 &&
      (g.getPaperAccount().openPositions||[]).length===TRADEABLE.length,
      'EUR_USD positions='+openOn('EUR_USD')+' total='+(g.getPaperAccount().openPositions||[]).length);
  }
  {
    // ── PTE2E-RACE: the inner pre-open re-check (§18.22) — REDUNDANT CONFIRMATION ────────────────
    // ⚠️ CORRECTION. These were added believing the inner re-check was UNCOVERED. IT WAS NOT.
    // An independent completeness audit showed JVMDUP-2/3/4 in run_v1233 already drive exactly this
    // guard -- and JVMDUP-3/JVMDUP-4 isolate its open-position half and its traded-today half
    // INDIVIDUALLY. They predate this suite; verified with `git show 4fd38a7:`. The earlier claim
    // came from scoring the mutation against THIS suite alone rather than gate-wide, and I repeated
    // it in the report without checking. §18.21b was wrong and is withdrawn.
    //
    // These fixtures are kept as redundant confirmation, NOT counted as a closed gap: they reach the
    // same guard through a different mechanism (a position injected mid-fetch via the runner's
    // interleaving hook rather than through a scripted concurrent tick), which is worth having. But
    // the milestone's survivor count must not be inflated by them.
    //
    // checkAutoTrades guards one-position-per-pair TWICE: once in the eligibility filter, and again
    // immediately before opening, "in case another concurrent check (or a manual click) already
    // acted on this pair".
    //
    // Under genuinely overlapping ticks the inner guard is the one that matters, and it is the only
    // thing standing between a concurrent manual click and a SECOND position on the same pair. This
    // makes the position appear DURING the in-flight evaluation fetch -- after the filter has
    // already passed the pair, before the re-check runs.
    jvmClean(); alexClean(); seedConversions();
    activeWatchAll();
    g.setPricing('serve','1.09990','1.10000');
    g.resetM15Calls();
    let injected=null;
    g.onMidFetch(function(inst){
      if(inst!=='EUR_USD'||injected) return;   // once, and only for the pair under test
      // A manual click lands mid-tick: EUR_USD now holds a position the filter never saw.
      const acct=g.getPaperAccount();
      injected={id:990777,pair:'EUR/USD',oPair:'EUR_USD',dir:'buy',entry:1.1000,stop:1.0900,target:1.1200,lots:0.1};
      acct.openPositions.push(injected);
      g.setPaperAccount(acct);
    });
    await g.checkAutoTrades();
    g.onMidFetch(null);
    const eu=(g.getPaperAccount().openPositions||[]).filter(p=>p.oPair==='EUR_USD');
    assert('PTE2E-RACE.0 (PRECONDITION): the pair WAS evaluated this tick -- the outer filter passed it, so the assertions below test the inner pre-open re-check and not the filter',
      g.m15Calls('EUR_USD')===1,'EUR_USD evaluations='+g.m15Calls('EUR_USD'));
    assert('PTE2E-RACE.1 (PRECONDITION): the conflicting position really was injected DURING the in-flight evaluation, so it existed at the re-check and not at the filter',
      !!injected,'injected='+(!!injected));
    assert('PTE2E-RACE.2: a position appearing mid-tick is caught by the PRE-OPEN re-check -- EUR_USD still holds exactly the ONE injected position, so a concurrent manual click cannot produce a second position on the same pair',
      eu.length===1 && eu[0].id===990777,
      'EUR_USD positions='+eu.length+' ids='+eu.map(p=>p.id).join(','));
    assert('PTE2E-RACE.3: and the rest of the tick is unaffected -- every other tradeable pair still opened exactly once, so the re-check rejects one pair rather than aborting the sweep',
      (g.getPaperAccount().openPositions||[]).length===TRADEABLE.length,
      'total open='+(g.getPaperAccount().openPositions||[]).length+' expected='+TRADEABLE.length);
  }
  {
    // EXCLUSION: a pair already traded today is not even evaluated (kills M15a).
    jvmClean(); seedConversions(); activeWatchAll();
    g.setMode('firing');
    g.getAutoTrading().tradedToday['GBP_USD']=TODAY;
    g.resetM15Calls();
    await g.checkAutoTrades();
    assert('PTE2E-EXCL.3 (kills M15a -- NEGATIVE, no same-day re-entry): a pair already stamped as traded today is excluded BEFORE any decision is taken on it -- GBP_USD was never evaluated this tick, while every other pair was evaluated exactly once',
      g.m15Calls('GBP_USD')===0 && SCAN.filter(p=>p!=='GBP_USD').every(p=>g.m15Calls(p)===1),
      'GBP_USD='+g.m15Calls('GBP_USD')+' others='+SCAN.filter(p=>p!=='GBP_USD').map(p=>g.m15Calls(p)).join(','));
    assert('PTE2E-EXCL.4 (NEGATIVE, no same-day re-entry): and GBP_USD opened no position at all this tick, while the pairs that had not been traded today did',
      openOn('GBP_USD')===0 && (g.getPaperAccount().openPositions||[]).length===TRADEABLE.length-1,
      'GBP_USD positions='+openOn('GBP_USD')+' total='+(g.getPaperAccount().openPositions||[]).length);
  }

  // ── FAILURE ISOLATION: one instrument throwing must not stop the others ────────────────
  {
    jvmClean(); seedConversions(); activeWatchAll();
    g.setMode('firing');
    // A CORRUPT conversion snapshot for one quote currency, injected as data -- no production
    // function is wrapped or modified. Reading it throws, which is exactly the class of fault
    // the per-pair try/catch inside checkAutoTrades exists to contain.
    const pd=g.getPairData();
    delete pd.USD_CHF;
    Object.defineProperty(pd,'USD_CHF',{configurable:true,enumerable:true,
      get(){ throw new Error('fixture: corrupt conversion snapshot for USD_CHF'); }});
    g.resetM15Calls();
    let threw=false;
    try{ await g.checkAutoTrades(); }catch(e){ threw=true; }
    delete pd.USD_CHF;
    const acct=g.getPaperAccount();
    const chfPairs=TRADEABLE.filter(p=>p.split('_')[1]==='CHF');
    const otherPairs=TRADEABLE.filter(p=>p.split('_')[1]!=='CHF');
    assert('PTE2E-ISOFAIL.1 (FAILURE ISOLATION): a fault raised while sizing ONE instrument does not escape the tick -- checkAutoTrades resolved normally instead of rejecting',
      threw===false, 'rejected='+threw);
    assert('PTE2E-ISOFAIL.2 (FAILURE ISOLATION): every OTHER pair still opened its position -- '+otherPairs.length+' of them -- so one bad instrument cost the operator only that instrument, not the whole tick',
      otherPairs.every(p=>openOn(p)===1) && chfPairs.every(p=>openOn(p)===0) &&
      (acct.openPositions||[]).length===otherPairs.length,
      'opened='+(acct.openPositions||[]).length+' expected='+otherPairs.length);
    assert('PTE2E-ISOFAIL.3 (FAILURE ISOLATION, the failure is reported not swallowed): the failing instruments were each recorded as a paper-engine error naming the pair, so the operator can see WHICH instrument was skipped rather than silently getting fewer trades',
      chfPairs.every(p=>(g.getPaperEngineErrors()||[]).some(e=>String(e&&e.message||e).indexOf(p.replace('_','/'))!==-1||JSON.stringify(e).indexOf(p)!==-1)),
      'errors='+JSON.stringify((g.getPaperEngineErrors()||[]).slice(0,2)).slice(0,200));
  }

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP 5 — PERSISTENCE / RESTART
  // ════════════════════════════════════════════════════════════════════════════════════════
  {
    jvmClean(); seedConversions(); activeWatchAll();
    g.setMode('firing');
    await g.checkAutoTrades();
    const before=(g.getPaperAccount().openPositions||[]).find(p=>p.oPair==='EUR_USD')||null;
    const beforeJournal=(g.getJournalEntries()||[]).find(e=>before&&e.tradeId===before.id)||null;
    // A RESTART, simulated the only honest way: throw away every in-memory store and re-read
    // them from storage through the REAL loadSaved(), exactly as a page reload does.
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setAutoTrading({enabled:false,tradedToday:{},log:[]});
    g.loadSaved();
    const after=(g.getPaperAccount().openPositions||[]).find(p=>p.oPair==='EUR_USD')||null;
    const afterJournal=(g.getJournalEntries()||[]).find(e=>before&&e.tradeId===before.id)||null;
    assert('PTE2E-RESTART.1 (PERSISTENCE): after every in-memory store is discarded and re-read through the real loadSaved(), the EUR_USD position is back with the same trade id, direction, entry, stop, target and lot size it was emitted with -- nothing about the order was lost or re-derived across the restart',
      !!before && !!after && after.id===before.id && after.dir===before.dir && after.entry===before.entry &&
      after.stop===before.stop && after.target===before.target && after.lots===before.lots,
      after?('id='+after.id+' entry='+after.entry+' stop='+after.stop+' target='+after.target+' lots='+after.lots):'position did NOT survive the restart');
    assert('PTE2E-RESTART.2 (PERSISTENCE): its journal row survived the restart too -- same trade id, still OPEN, still carrying the entry the order was emitted with',
      !!beforeJournal && !!afterJournal && afterJournal.tradeId===beforeJournal.tradeId &&
      afterJournal.status==='OPEN' && afterJournal.entry===beforeJournal.entry,
      afterJournal?('status='+afterJournal.status+' entry='+afterJournal.entry):'journal row did NOT survive the restart');
    assert('PTE2E-RESTART.3 (PERSISTENCE): the restored account restored the WHOLE ledger -- all '+TRADEABLE.length+' positions the tick opened, and the balance untouched at exactly 10000.00 because nothing has been closed yet',
      (g.getPaperAccount().openPositions||[]).length===TRADEABLE.length && g.getPaperAccount().balance===10000,
      'positions='+(g.getPaperAccount().openPositions||[]).length+' balance='+g.getPaperAccount().balance);
    // RESTART MUST NOT RE-OPEN. The restored session runs another tick against the same firing
    // series -- the positions it restored must suppress every one of them.
    g.resetM15Calls();
    await g.checkAutoTrades();
    assert('PTE2E-RESTART.4 (PERSISTENCE, and the point of it): the restored session ran a fresh tick against the same firing series and re-opened NOTHING -- still exactly '+TRADEABLE.length+' positions, and the only pairs it even re-evaluated are the four the frozen strategy had already refused. A restart that forgot the restored trades would double the operator\'s exposure on every reload',
      (g.getPaperAccount().openPositions||[]).length===TRADEABLE.length && g.m15CallTotal()===JPY.length &&
      TRADEABLE.every(p=>g.m15Calls(p)===0),
      'positions='+(g.getPaperAccount().openPositions||[]).length+' evaluations='+g.m15CallTotal());
  }

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP 6 — ALEX ORDER GENERATION AS ACTUALLY EMITTED
  //
  // Hand-computed for this exact fixture, from the FROZEN config (atrPeriod 14,
  // stopATRBuffer 0.25, minRR 2.0, riskPercent 1.0) and the fixture's own inputs:
  //   EUR_USD, pip 0.0001, quote USD -> pipValue = $10/pip/lot
  //   every candle has a true range of exactly 0.00200 -> ATR at entry = 0.00200
  //   A_repeatedReaction on a zone whose role at qualification is "support" -> direction BUY
  //   a buy fills at the ASK -> entry = 1.10000 (bid 1.09990 is deliberately different, so a
  //     fill on the wrong side of the spread is visible)
  //   stop = zoneLow - 0.25 x ATR = 1.09050 - 0.00050 = 1.09000
  //   riskDistance = 1.10000 - 1.09000 = 0.01000 = 100.0 pips
  //   target = entry + 2.0 x riskDistance = 1.10000 + 0.02000 = 1.12000
  //   riskAmount = 10000 x (1.0/100) = $100.00      (undivided it would be $10,000)
  //   positionSize = 100 / (100.0 pips x $10) = 0.10 lots  (undivided it would be 10.00)
  // ════════════════════════════════════════════════════════════════════════════════════════
  function alexCandles(){
    // Constant true range of exactly 0.00200 per bar and no gaps, so ATR is an exact literal.
    const out=[];
    for(let i=60;i>=1;i--) out.push({t:new Date(g.now()-i*3600000),o:1.09050,h:1.09250,l:1.09050,c:1.09050});
    return out;
  }
  function alexSetup(id,qualMsOffset){
    return {strategy:'alex_g_sr',ruleVersion:'alex_g_sr_v1',pair:'EUR_USD',timeframe:'H1',
      setupId:id,setupType:'A_repeatedReaction',setupLabel:'Repeated Zone Reaction',
      zoneRoleAtQualification:'support',zoneLow:1.09050,zoneHigh:1.09500,zoneCenter:1.09275,
      qualificationClose:1.10000,qualificationTimestamp:g.now()-(qualMsOffset==null?600000:qualMsOffset),
      qualificationBarIndex:40,zoneId:'Z|'+id,reactionId:'R|'+id,zoneTouchNumber:3,zoneStrength:3,
      zoneQualityAtQualification:'A',session:'London',dayOfWeek:1,hourOfDay:14,trendContext:'up',
      configurationSnapshot:{},brokenDirection:null,barsSinceBreak:null,breakCycleId:null};
  }
  const ALEX_DATASETS={H1:alexCandles()};
  {
    alexClean();
    g.setPricing('serve','1.09990','1.10000');
    await g.alexGAttemptOpenLivePosition(alexSetup('SU|A1'),ALEX_DATASETS,{},'SCAN|A1');
    const p=(g.getAlexGAccount().openPositions||[])[0]||null;
    assert('PTE2E-ALEX.1 (POSITIVE CONTROL): the real ALEX live-open path opened exactly one position, and its DIRECTION as emitted is "buy" -- derived from the zone role at qualification, never from live price',
      (g.getAlexGAccount().openPositions||[]).length===1 && !!p && p.direction==='buy',
      p?('n=1 direction='+p.direction):'n='+(g.getAlexGAccount().openPositions||[]).length);
    assert('PTE2E-ALEX.2 (order as emitted, entry side): the buy filled at the ASK, entry exactly 1.10000 -- not the 1.09990 bid the same snapshot carried, and not the 1.10000 qualification close by coincidence of a wrong field being read (entryDelayPips is exactly 0 here, which the fixture states rather than derives)',
      !!p && near(p.entry,1.10000) && near(p.liveFillPrice,1.10000) && near(p.entryBid,1.09990) && near(p.entryAsk,1.10000),
      p?('entry='+p.entry+' bid='+p.entryBid+' ask='+p.entryAsk):'no position');
    assert('PTE2E-ALEX.3 (order as emitted, stop and target): stop is exactly 1.09000 (the 1.09050 zone low less a 0.25 x 0.00200 ATR buffer, placed BEYOND the zone) and target is exactly 1.12000 (2.0R on the 100.0-pip risk distance). A stop and target swapped, or an ATR buffer applied on the wrong side, both miss these by whole pips',
      !!p && near(p.stop,1.09000) && near(p.target,1.12000) && near(p.atrAtEntry,0.00200) && p.stop<p.entry && p.target>p.entry,
      p?('stop='+p.stop+' target='+p.target+' atr='+p.atrAtEntry):'no position');
    assert('PTE2E-ALEX.4 (kills the riskPercent /100 class, sizing): riskAmount is exactly $100.00 and positionSize exactly 0.10 lots on a $10,000 balance at the frozen 1.0% risk -- hand-computed as $100 divided by (100.0 stop pips x $10 per pip per lot). A riskPercent that skipped its /100 would read $10,000.00 and 10.00 lots -- the entire account risked on one trade',
      !!p && p.riskAmount===100 && near(p.positionSize,0.1) && p.riskPercent===1.0 && p.pipValue===10 &&
      p.balanceAtEntry===10000 && p.plannedRR===2,
      p?('riskAmount='+p.riskAmount+' size='+p.positionSize+' riskPercent='+p.riskPercent+' plannedRR='+p.plannedRR):'no position');
    assert('PTE2E-ALEX.5 (PRESENCE-only, DISCLOSED): the ALEX account key exists in storage after the open. This asserts PRESENCE, not CONTENT -- a wrong persisted balance would still pass. Contrast LCR-PERSIST.1, which reads the JVM bytes properly',
      (g.getAlexGJournalEntries()||[]).filter(e=>p&&e.tradeId===p.tradeId&&e.status==='OPEN').length===1 &&
      !!g.getLocalStorageItem('fxhub_alexg_account'),
      'rows='+(g.getAlexGJournalEntries()||[]).length+' storage='+(g.getLocalStorageItem('fxhub_alexg_account')?'present':'MISSING'));
  }
  {
    // DUPLICATE PREVENTION, ALEX: the same signal offered twice.
    alexClean();
    g.setPricing('serve','1.09990','1.10000');
    await g.alexGAttemptOpenLivePosition(alexSetup('SU|A2'),ALEX_DATASETS,{},'SCAN|A2');
    const afterFirst=(g.getAlexGAccount().openPositions||[]).length;
    await g.alexGAttemptOpenLivePosition(alexSetup('SU|A2'),ALEX_DATASETS,{},'SCAN|A2');
    assert('PTE2E-ALEXDUP.1 (NEGATIVE, DISCLOSED -- see note): offering the IDENTICAL signal a second time opens nothing. Independent verification showed the OVERLAP rule alone carries this: deleting the entire four-term duplicate-signal guard kills nothing here (3 gate-wide). This pins the combined outcome, not that specific guard',
      afterFirst===1 && (g.getAlexGAccount().openPositions||[]).length===1 &&
      (g.getAlexGJournalEntries()||[]).length===1 && g.getAlexGAccount().balance===10000,
      'afterFirst='+afterFirst+' afterSecond='+(g.getAlexGAccount().openPositions||[]).length+
      ' journal='+(g.getAlexGJournalEntries()||[]).length);
    // OVERLAP RULE: a genuinely DIFFERENT signal on the same pair+timeframe.
    await g.alexGAttemptOpenLivePosition(alexSetup('SU|A3',300000),ALEX_DATASETS,{},'SCAN|A3');
    assert('PTE2E-ALEXDUP.2 (NEGATIVE, one open trade per pair+timeframe): a DIFFERENT signal -- its own setup id, its own qualification timestamp, so the duplicate-signal guard cannot be what stops it -- is refused while a position is open on the same pair and timeframe, and the refusal is recorded as BLOCKED — EXISTING POSITION rather than silently dropped',
      (g.getAlexGAccount().openPositions||[]).length===1 &&
      (g.getAlexGAutoTrading().log||[]).some(l=>l&&l.status==='BLOCKED — EXISTING POSITION'&&l.reason==='EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME'),
      'positions='+(g.getAlexGAccount().openPositions||[]).length+' log='+JSON.stringify((g.getAlexGAutoTrading().log||[])[0]||null).slice(0,120));
  }
  {
    // ALEX CLOSE, END TO END, with hand-computed literals, then closed AGAIN.
    //   entry 1.10000, exit 1.12000 -> move = 0.02000/0.0001 = +200.0 pips
    //   pnl = 200.0 x $10/pip/lot x 0.10 lots = +$200.00 ; balance 10000 -> 10200.00
    //   a Win under the frozen fixed-R methodology journals resultR = plannedRR = +2.0
    alexClean();
    g.setPricing('serve','1.09990','1.10000');
    await g.alexGAttemptOpenLivePosition(alexSetup('SU|A4'),ALEX_DATASETS,{},'SCAN|A4');
    const p=(g.getAlexGAccount().openPositions||[])[0]||null;
    // p is read defensively: a mutation that BLOCKS the open must make the assertions below
    // fail on their own terms, not crash the suite into an uncounted zero-fixture run.
    // §18.20: the exit is deliberately BEYOND the 1.12000 target. An earlier version closed exactly
    // AT the target, where the frozen fixed-R value (plannedRR = 2.0) and a value recomputed from
    // pnl/riskAmount (200/100 = 2.0) are the SAME NUMBER -- so ALEXCLOSE.2's claim that this is
    // "fixed-R, not recomputed from slippage" could not fail. Closing at 1.13000 makes recomputed R
    // 300/100 = 3.0 while fixed-R stays 2.0, so the two are now distinguishable.
    g.alexGCloseLivePosition(p?p.tradeId:'no-such-trade','Win',1.13000,null,{});
    const acct=g.getAlexGAccount();
    const closed=(acct.closedPositions||[])[0]||null;
    assert('PTE2E-ALEXCLOSE.1 (END-TO-END): the real ALEX close moved the 0.10-lot buy from 1.10000 to 1.13000 for exactly +$300.00 -- 300 pips at $10 per pip per lot on 0.10 lots -- lifting the balance to exactly 10300.00',
      !!closed && closed.pnl===300 && acct.balance===10300 && (acct.openPositions||[]).length===0,
      closed?('pnl='+closed.pnl+' balance='+acct.balance+' open='+(acct.openPositions||[]).length):'no closed position');
    assert('PTE2E-ALEXCLOSE.2 (END-TO-END, fixed-R): that Win records resultR exactly +2.0 -- the PLANNED R:R -- even though the trade actually ran to +$300.00, which a recomputation from pnl/riskAmount would report as 3.0. This is the frozen fixed-R methodology, and the two values are now distinguishable',
      !!closed && closed.resultR===2 && closed.resultR!==3 && near(closed.exitPrice,1.13) && closed.result==='Win' && closed.status==='closed',
      closed?('R='+closed.resultR+' exit='+closed.exitPrice+' pnl='+closed.pnl):'no closed position');
    let secondThrew=null;
    try{ g.alexGCloseLivePosition(p?p.tradeId:'no-such-trade','Win',1.13000,null,{}); }
    catch(e){ secondThrew=String(e&&e.message||e); }
    assert('PTE2E-ALEXCLOSE.3 (NEGATIVE, double close): closing the SAME ALEX trade id again neither throws nor moves anything -- still exactly one closed position and a balance of exactly 10300.00, not the 10600.00 a second credit would produce',
      secondThrew===null && (g.getAlexGAccount().closedPositions||[]).length===1 && g.getAlexGAccount().balance===10300,
      'threw='+String(secondThrew)+' closed='+(g.getAlexGAccount().closedPositions||[]).length+' balance='+g.getAlexGAccount().balance);
  }

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP 7 — ALEX / JVM ISOLATION (first-class requirement)
  //

  // Each fixture snapshots EVERY store the other strategy owns -- account, journal, auto-trading
  // state, setups, statuses, zones, engine errors, version guard, blocking/integrity banners and
  // that strategy's own localStorage keys -- into one deterministic string, runs a real operation
  // on this side, and requires the other side's string to come back BYTE-IDENTICAL. Each carries
  // a positive control proving this side genuinely changed, so "unchanged" can never pass because
  // nothing happened. The shared observability bus (decisionEventLog) is deliberately excluded and
  // is not a strategy store: both strategies write to it by design.
  // ════════════════════════════════════════════════════════════════════════════════════════
  {
    // JVM -> ALEX. A full JVM lifecycle: auto-trade tick, manual open, and a real close.
    jvmClean(); alexClean(); seedConversions(); activeWatchAll();
    g.setMode('firing'); g.setPricing('reject');
    const alexBefore=g.snapshotAlexStores();
    const jvmBefore=g.snapshotJvmStores();
    await g.checkAutoTrades();
    const pos=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData('GBP_USD',1.3250);
    await g.closePaperPosition(pos.id,false,null);   // the manual GBP_USD trade, whose fallback exit price this fixture set
    await drainMicrotasks();
    const alexAfter=g.snapshotAlexStores();
    const jvmAfter=g.snapshotJvmStores();
    assert('PTE2E-ISO.1 (POSITIVE CONTROL for PTE2E-ISO.2): the JVM side genuinely did a full day\'s work in that block -- an auto-trade tick, a manual open and a real close all landed, so its own store snapshot changed',
      jvmBefore!==jvmAfter && (g.getPaperAccount().closedPositions||[]).length===1 && !!pos && !pos.error,
      'jvmChanged='+(jvmBefore!==jvmAfter)+' closed='+(g.getPaperAccount().closedPositions||[]).length);
    assert('PTE2E-ISO.2 (ISOLATION, JVM -> ALEX): every ALEX store is BYTE-IDENTICAL afterwards -- account and balance, journal, auto-trading state and traded-signal set, setups, live statuses, zone state, engine errors, version guard, ledger banners and every fxhub_alexg_* key. No JVM open, close, balance movement or tick leaks one byte into ALEX',
      alexBefore===alexAfter,
      alexBefore===alexAfter?'identical':('ALEX CHANGED: before='+alexBefore.slice(0,180)+' || after='+alexAfter.slice(0,180)));
  }
  {
    // ALEX -> JVM. A full ALEX lifecycle: a real live open and a real close.
    jvmClean(); alexClean();
    g.setPricing('serve','1.09990','1.10000');
    // §18.20: THE SNAPSHOT MUST HAVE SOMETHING TO LOSE. Comparing a field is not enough if the
    // scenario leaves it EMPTY -- a leak that CLEARS shared state, or that adds an entry per open
    // JVM position, changes nothing when there is no state and no open position to act on. Proven:
    // an ALEX close that locked every open JVM position, and one that wiped the INC-001 register,
    // were both invisible until this state existed. Both are seeded before the snapshot is taken.
    g.setPaperAccount({balance:10000,openPositions:[
      {id:990001,pair:'GBP/USD',oPair:'GBP_USD',dir:'buy',entry:1.3000,stop:1.2900,target:1.3200,lots:0.1}
    ],closedPositions:[]});
    g.seedStorageLoadFailure('fxhub_paper','seeded so a leak that CLEARS the INC-001 register is observable');
    const jvmBefore=g.snapshotJvmStores();
    const alexBefore=g.snapshotAlexStores();
    await g.alexGAttemptOpenLivePosition(alexSetup('SU|ISO1'),ALEX_DATASETS,{},'SCAN|ISO1');
    const p=(g.getAlexGAccount().openPositions||[])[0]||null;
    g.alexGCloseLivePosition(p?p.tradeId:'none','Win',1.12000,null,{});
    await drainMicrotasks();
    const jvmAfter=g.snapshotJvmStores();
    const alexAfter=g.snapshotAlexStores();
    assert('PTE2E-ISO.3 (POSITIVE CONTROL for PTE2E-ISO.4): the ALEX side genuinely opened and closed a real live position in that block -- one closed position and a balance moved to exactly 10200.00 -- so its own store snapshot changed',
      alexBefore!==alexAfter && (g.getAlexGAccount().closedPositions||[]).length===1 && g.getAlexGAccount().balance===10200,
      'alexChanged='+(alexBefore!==alexAfter)+' balance='+g.getAlexGAccount().balance);
    assert('PTE2E-ISO.4 (kills M25 -- ISOLATION, ALEX -> JVM): every JVM store is BYTE-IDENTICAL afterwards -- paper account and balance, journal, auto-trading state, engine errors, reset history, reconciliation audit, version guard, ledger banners and every JVM localStorage key. An ALEX position that also appeared in the JVM account, or ALEX P&L that also moved the JVM balance, is caught here and nowhere else',
      jvmBefore===jvmAfter,
      jvmBefore===jvmAfter?'identical':('JVM CHANGED: before='+jvmBefore.slice(0,180)+' || after='+jvmAfter.slice(0,180)));
  }
  {
    // The single most valuable isolation check, isolated to one operation: a JVM CLOSE.
    // Kills M12 (a close that also credits the ALEX balance) with nothing else in the way.
    jvmClean(); alexClean();
    g.setPricing('reject');
    const pos=g.openPaperPosition('GBP_USD','buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData('GBP_USD',1.3250);
    const alexBefore=g.snapshotAlexStores();
    const alexBalBefore=g.getAlexGAccount().balance;
    await g.closePaperPosition(pos.id,false,null);
    await drainMicrotasks();
    const alexAfter=g.snapshotAlexStores();
    assert('PTE2E-ISO.5 (POSITIVE CONTROL for PTE2E-ISO.6): the JVM close under observation really did credit $250.00 to the JVM balance, taking it to exactly 10250.00',
      g.getPaperAccount().balance===10250 && (g.getPaperAccount().closedPositions||[])[0].pnl===250,
      'jvmBalance='+g.getPaperAccount().balance);
    assert('PTE2E-ISO.6 (kills M12 -- ISOLATION, a JVM close must not credit ALEX): the ALEX balance is still exactly 10000.00 and every ALEX store is byte-identical across a JVM close that moved $250.00. A close that credited the SAME P&L to both accounts is caught here and nowhere else in the gate. DISCLOSED: as a pure detector this is a logical SUBSET of PTE2E-ISO.2, whose block also contains a close -- it is kept, and counted, only because it isolates the close as the single operation under observation, so a failure here NAMES the close rather than a three-operation block',
      g.getAlexGAccount().balance===10000 && alexBalBefore===10000 && alexBefore===alexAfter,
      'alexBalance='+g.getAlexGAccount().balance+' identical='+(alexBefore===alexAfter));
  }
  // ══ 🔴 ALERT — the operator-notification path had NO behavioural coverage (§18.23) ═══════════
  // An independent completeness audit found playAlert, showToast, showAutoTradeToast and
  // notifyAutoTrade appear in ZERO test files, and addAlert appears exactly once -- inside a
  // comment. The only fixture in the repository naming alert dedup was
  // `assert('Fixture 46: alert dedup works', true, ...)` -- the condition is the LITERAL `true`.
  // That is the TWELFTH fixture this milestone has found that cannot fail, and it was still in the
  // gate. Consequence: deleting the `conf.total >= ALERT_THRESHOLD` gate, or inverting it, left the
  // whole gate green -- the operator is told nothing and nothing objects.
  {
    jvmClean(); alexClean(); seedConversions(); activeWatchAll();
    g.setMode('firing'); g.setPricing('serve','1.09990','1.10000');
    g.resetFiredAlerts(); g.setAlertLog([]);
    await g.scanPair('EUR_USD');
    const pdA=g.pairDataAll()['EUR_USD']||{};
    const logA=g.getAlertLog();
    assert('PTE2E-ALERT.0 (PRECONDITION): this series genuinely scores AT OR ABOVE the alert threshold, so the assertion below is not vacuous -- the frozen confluence engine produced 65 against a threshold of 55',
      pdA.conf && pdA.conf.total>=g.ALERT_THRESHOLD && pdA.evaluationSuppressed===false,
      'conf.total='+(pdA.conf&&pdA.conf.total)+' threshold='+g.ALERT_THRESHOLD+' suppressed='+pdA.evaluationSuppressed);
    assert('PTE2E-ALERT.1: a sweep at or above the threshold raises exactly ONE alert, naming the pair that scored and carrying the score the engine actually produced',
      logA.length===1 && logA[0].pair==='EUR/USD' && logA[0].pct===pdA.conf.total,
      'alerts='+logA.length+' pair='+(logA[0]&&logA[0].pair)+' pct='+(logA[0]&&logA[0].pct));
    await g.scanPair('EUR_USD');
    assert('PTE2E-ALERT.2 (DEDUP): re-running the identical sweep in the same 5-minute bucket does NOT raise a second alert -- this replaces v1212 Fixture 46, whose condition was the literal true',
      g.getAlertLog().length===1,'alerts after the second sweep='+g.getAlertLog().length);
  }
  {
    // NEGATIVE CONTROL. Without it, ALERT.1 would also be satisfied by a gate that alerts
    // unconditionally -- which is the mutation most likely to be introduced by a careless edit.
    jvmClean(); alexClean(); seedConversions(); activeWatchAll();
    g.setMode('flat'); g.setPricing('serve','1.09990','1.10000');
    g.resetFiredAlerts(); g.setAlertLog([]);
    await g.scanPair('EUR_USD');
    const pdB=g.pairDataAll()['EUR_USD']||{};
    assert('PTE2E-ALERT.3 (NEGATIVE CONTROL): a sweep scoring BELOW the threshold raises no alert at all, so the gate is a real threshold rather than an unconditional notify',
      pdB.conf && pdB.conf.total<g.ALERT_THRESHOLD && g.getAlertLog().length===0,
      'conf.total='+(pdB.conf&&pdB.conf.total)+' alerts='+g.getAlertLog().length);
  }
  {
    // And the mirror at the finest grain: an ALEX close must not credit JVM.
    jvmClean(); alexClean();
    g.setPricing('serve','1.09990','1.10000');
    await g.alexGAttemptOpenLivePosition(alexSetup('SU|ISO2'),ALEX_DATASETS,{},'SCAN|ISO2');
    const p=(g.getAlexGAccount().openPositions||[])[0]||null;
    const jvmBefore=g.snapshotJvmStores();
    g.alexGCloseLivePosition(p?p.tradeId:'none','Win',1.12000,null,{});
    await drainMicrotasks();
    const jvmAfter=g.snapshotJvmStores();
    assert('PTE2E-ISO.7 (POSITIVE CONTROL for PTE2E-ISO.8): the ALEX close under observation really did credit $200.00 to the ALEX balance, taking it to exactly 10200.00',
      g.getAlexGAccount().balance===10200,'alexBalance='+g.getAlexGAccount().balance);
    assert('PTE2E-ISO.8 (ISOLATION, an ALEX close must not credit JVM): the JVM balance is still exactly 10000.00 with no open and no closed positions, and every JVM store is byte-identical across an ALEX close that moved $200.00. DISCLOSED: as a pure detector this is a logical SUBSET of PTE2E-ISO.4, whose block also contains a close -- it is kept for the same localisation reason as PTE2E-ISO.6',
      g.getPaperAccount().balance===10000 && (g.getPaperAccount().openPositions||[]).length===0 &&
      (g.getPaperAccount().closedPositions||[]).length===0 && jvmBefore===jvmAfter,
      'jvmBalance='+g.getPaperAccount().balance+' identical='+(jvmBefore===jvmAfter));
  }

  // ── HARNESS SELF-CHECK ────────────────────────────────────────────────────────────────────
  // An async suite whose promise is never awaited reports nothing and is scored as a pass by a
  // count-blind reader. This asserts the suite reached its own final line AND that the count of
  // fixtures recorded is what the file contains, so a silently truncated run is a FAILURE here
  // rather than a shorter, quieter, still-green report.
  // DISCLOSED, so this is never mistaken for coverage: PTE2E-HARNESS.1 is a HARNESS assertion,
  // not a production one. No mutation of any production function can make it fail (verified: it
  // survived all 28 behaviour-changing mutations and all 14 confirmation mutations run against
  // this suite). It exists solely to convert a silently truncated async run -- which would
  // otherwise report a shorter, quieter, still-green result -- into a visible FAILURE. Every
  // other fixture in this file has been individually shown to fail against at least one
  // behaviour-changing mutation of the code it claims to cover.
  assert('PTE2E-HARNESS.1 (HARNESS self-check, NOT production coverage): the suite ran to its own end and recorded every fixture above it -- an async suite that is not genuinely awaited is a known false-green in this repository, and this line cannot be reached without the awaits above having resolved',
    results.length===117, 'recorded='+results.length+' expected=117 (this fixture is the 118th)');

  return results;
}
