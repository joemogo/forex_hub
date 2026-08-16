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
    g.setAlexGZoneState({});
    g.setAlexGLastEvaluatedCloseTime({});
    g.setAlexGLedgerBlockingError(null);
    g.setAlexGLedgerIntegrityWarning(null);
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
    results.length===64, 'recorded='+results.length+' expected=64 (this fixture is the 65th)');

  return results;
}
