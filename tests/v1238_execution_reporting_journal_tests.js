// ══════════════════════════════════════════════════════════════════════════════════════════
// v12.3.8 EXECUTION REPORTING — JOURNAL WRITE PATH & RECORD NORMALIZATION
// ══════════════════════════════════════════════════════════════════════════════════════════
// Closes a measured mutation-coverage gap on the paper-trade execution REPORTING surface: a
// re-score of that surface found a block of behaviour-changing mutations in the journal WRITE
// path (applyJournalCloseUpdate / journalNoteCloseJVM / journalNoteCloseAlex), in the close
// paths that REACH it (closePaperPosition / alexGCloseLivePosition), and in the read-side
// normalizer (normalizeJournalRecord) that killed ZERO fixtures. Nothing that journals what a
// closed trade actually was, was observed by any fixture. Every fixture below exists to kill one
// or more of those specific survivors.
//
// EVIDENCE STANDARD APPLIED HERE (deliberately, and worth stating because this repository has
// produced the opposite before):
//   * No fixture asserts against source text. getSource()/substring matching survives every
//     behavioural mutation and is not coverage.
//   * No fixture is self-consistent -- nothing compares two outputs of the same computation
//     (e.g. "balance === balanceBefore + closedPos.pnl"), which is blind to a wrong value
//     appearing identically on both sides.
//   * Every asserted value is a FIXTURE-CHOSEN LITERAL derived by hand from the fixture's own
//     inputs (exit price 1.3050 on a 1.3000 entry at 0.1 lots and $10/pip = exactly +$50, on a
//     $100 risk = exactly +0.50R), never re-derived using the same expression the production
//     code uses.
//   * The reachability fixtures drive the REAL, unmodified, PROTECTED closePaperPosition() /
//     alexGCloseLivePosition() end-to-end and then read the journal store. They never call the
//     journal writer themselves -- that is the whole point: deleting the journalNoteCloseJVM()
//     call site from the close path must make them fail.
//
// HARNESS NOTE: closePaperPosition() is `async` (one internal `await fetchBidAsk`). See the
// header of run_v1238_execution_reporting_journal_tests.js for why that IS observable offline
// (JavaScriptCore drains its microtask queue after the top-level script body finishes) and why
// no production function needed modifying to reach it. This suite therefore returns a Promise.
//
// ISOLATION: in-memory only, stubbed localStorage, stubbed fetch, no real browser storage and no
// network -- identical to every other suite here. No real paper trade can be persisted from this
// process because this process has no access to real storage in the first place.
async function runV1238ExecutionReportingJournalFixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,method:'execution',detail:detail||''});};
  const PAIR='GBP_USD';
  const NOT_RECORDED='Not recorded for this historical trade.'; // fixture-chosen literal, not read back from the app

  function seedClean(){
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGJournalEntries([]);
    g.setPairData(PAIR,null);
    g.resetPaperVersionGuard();
    g.resetPaperPositionsClosing();
    g.resetAlexGVersionGuard();
    g.clearLocalStorage();
  }

  // ── Drives the REAL close path. Deliberately returns the journal record found by tradeId in
  //    the live journalEntries store -- so a close that never journals produces an untouched
  //    OPEN record (or none), and every assertion below it fails. ──
  // §18.12: the clock is FROZEN at a known open instant and advanced to a known close instant
  // exactly 90 minutes later, so closedAt and durationMs are fixture-chosen literals rather than
  // whatever the wall clock happened to produce. Without this the close ran in under a
  // millisecond, durationMs was ~0, and the only assertion available was "is a number and >= 0" --
  // which passes against a mutation that journals 1 for every trade.
  const OPEN_MS=Date.parse('2026-03-01T10:00:00.000Z');
  const CLOSE_MS=OPEN_MS+5400000;                       // +90 minutes
  const EXPECTED_CLOSED_AT=new Date(CLOSE_MS).toISOString();
  async function driveJvmClose(o){
    seedClean();
    g.setPairData(PAIR,o.exitLive);
    g.freezeClock(OPEN_MS);
    const pos=g.openPaperPosition(PAIR,o.dir,o.entry,o.stop,o.target,'manual');
    if(!pos||pos.error){ g.restoreClock(); return{pos:null,res:null,rec:null,openError:(pos&&pos.error)||'no position'}; }
    if(o.developer){ pos.isDeveloperTrade=true; pos.tradeSource='TEST'; }
    g.freezeClock(CLOSE_MS);
    const res=await g.closePaperPosition(pos.id,!!o.manual,o.autoResult||null);
    g.restoreClock();
    const rec=(g.getJournalEntries()||[]).find(e=>e.tradeId===pos.id)||null;
    const closedPos=(g.getPaperAccount().closedPositions||[])[0]||null;
    return{pos,res,rec,closedPos,expectedClosedAt:EXPECTED_CLOSED_AT,openError:null};
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 1 — JVM WINNING CLOSE, DRIVEN THROUGH THE REAL closePaperPosition()
  //
  // Hand-computed expectations for this exact fixture:
  //   balance 10000 -> riskAmount = 1% = $100
  //   GBP_USD buy, entry 1.3000, stop 1.2900 -> riskPips = 100
  //   quote is USD -> pipValuePerLot = 0.0001 * 100000 = $10/pip/lot
  //   lots = 100 / (100 * 10) = 0.10
  //   live/fallback exit 1.3050 -> +50.0 pips -> pnl = 50 * 10 * 0.10 = +$50.00
  //   resultR = pnl / riskAmount = 50 / 100 = +0.50
  //   autoResult 'Win', not manual, not a developer trade -> closeReason TAKE_PROFIT
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    const w=await driveJvmClose({dir:'buy',entry:1.3000,stop:1.2900,target:1.3200,exitLive:1.3050,manual:false,autoResult:'Win'});
    assert('JVM-CLOSE-REACH.1 (kills A5): closing a JVM position through the REAL closePaperPosition() actually produces a CLOSED journal record for that exact tradeId -- the journal write is reached from the production close path, not merely callable',
      !!w.rec && w.rec.status==='CLOSED', 'openError='+w.openError+' rec='+(w.rec?w.rec.status:'MISSING'));
    // LABEL CORRECTED (§18.12). This claimed "(kills A5)" and does not: deleting
    // journalNoteCloseJVM leaves the trade's untouched OPEN row in place, still carrying its
    // entry-time fields and still exactly one row, so this fixture passes. A5 is killed by
    // JVM-CLOSE-REACH.1 and the 17 value assertions. This one pins "no SECOND row is appended",
    // which is a different property and is worth keeping under its true name.
    assert('JVM-CLOSE-REACH.2 (does NOT kill A5 -- see note; it pins no-duplicate-row): the real close path leaves exactly ONE journal row for the trade and it is that trade\'s own OPEN row updated in place (still carrying the entry-time fields 1.3/1.29/1.32), never a second appended row',
      (g.getJournalEntries()||[]).filter(e=>w.pos&&e.tradeId===w.pos.id).length===1 &&
      !!w.rec && w.rec.entry===1.3 && w.rec.stop===1.29 && w.rec.target===1.32,
      w.rec?('entry='+w.rec.entry+' stop='+w.rec.stop+' target='+w.rec.target):'no rec');
    assert('JVM-CLOSE-RESULT.1 (kills B2): a +50-pip winning close journals result exactly "Win"',
      !!w.rec && w.rec.result==='Win', w.rec?String(w.rec.result):'no rec');
    assert('JVM-CLOSE-R.1 (kills B1/B4): a +$50 win on $100 risk journals resultR exactly +0.5 -- not null, and not -0.5',
      !!w.rec && w.rec.resultR===0.5, w.rec?String(w.rec.resultR):'no rec');
    assert('JVM-CLOSE-PNL.1 (kills B3): that same close journals pnl exactly +50',
      !!w.rec && w.rec.pnl===50, w.rec?String(w.rec.pnl):'no rec');
    assert('JVM-CLOSE-EXIT.1 (kills B7): the journalled exitPrice is the actual 1.305 exit, and is NOT the 1.3 entry price',
      !!w.rec && w.rec.exitPrice===1.305 && w.rec.exitPrice!==w.rec.entry, w.rec?String(w.rec.exitPrice):'no rec');
    assert('JVM-CLOSE-REASON.1 (kills B8): an automatic Win close journals closeReason exactly "TAKE_PROFIT"',
      !!w.rec && w.rec.closeReason==='TAKE_PROFIT', w.rec?String(w.rec.closeReason):'no rec');
    assert('JVM-CLOSE-WHY.1 (kills B9): the close narrative is journalled verbatim -- "Closed as a Win at 1.305 (50.0 pips from entry)." -- replacing the open record\'s "Still open."',
      !!w.rec && w.rec.whyClosed==='Closed as a Win at 1.305 (50.0 pips from entry).', w.rec?String(w.rec.whyClosed):'no rec');
    // EXACT LITERALS, not "is a number and >= 0". §18.12: the previous shape passed against a
    // mutation that journalled durationMs as 1 for EVERY trade, and against one that journalled
    // the OPEN time as the close time -- both are wrong values that are still values, and a
    // presence assertion cannot tell the difference. The close is driven from a frozen clock, so
    // both figures are fixture-chosen and hand-computed.
    assert('JVM-CLOSE-DURATION.1 (kills B5): closing writes durationMs of exactly 5400000 (90 minutes, from the frozen open and close times) onto the journal record, which carried null at open',
      !!w.rec && w.rec.durationMs===5400000, w.rec?String(w.rec.durationMs):'no rec');
    assert('JVM-CLOSE-CLOSEDAT.1: the journalled closedAt is exactly the CLOSE time, not the open time echoed back',
      !!w.rec && w.rec.closedAt===w.expectedClosedAt && w.rec.closedAt!==w.rec.openedAt,
      w.rec?('closedAt='+w.rec.closedAt+' openedAt='+w.rec.openedAt+' expected='+w.expectedClosedAt):'no rec');
    // Positive control on the account side: proves the harness genuinely reached the post-await
    // body of the protected closePaperPosition() rather than silently observing nothing.
    assert('JVM-CLOSE-CONTROL.1 (positive control): the same real close moved the account to exactly one closed position at exitPrice 1.305 / pnl +50 and a balance of exactly 10050 -- so a failure above is a journal defect, not an unreached close path',
      !!w.closedPos && w.closedPos.exitPrice===1.305 && w.closedPos.pnl===50 && g.getPaperAccount().balance===10050,
      w.closedPos?('exit='+w.closedPos.exitPrice+' pnl='+w.closedPos.pnl+' bal='+g.getPaperAccount().balance):'no closedPos');
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 2 — JVM LOSING CLOSE (the case a "everything journals as a Win" mutation cannot fake)
  //   live/fallback exit 1.2950 on a 1.3000 buy -> -50.0 pips -> pnl = -$50.00, resultR = -0.50
  //   autoResult 'Loss', not manual -> closeReason STOP_LOSS
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    const l=await driveJvmClose({dir:'buy',entry:1.3000,stop:1.2900,target:1.3200,exitLive:1.2950,manual:false,autoResult:'Loss'});
    assert('JVM-LOSS-RESULT.1 (kills B2): a -50-pip losing close journals result exactly "Loss" -- a closed trade is NOT unconditionally journalled as a Win',
      !!l.rec && l.rec.result==='Loss', l.rec?String(l.rec.result):'no rec');
    assert('JVM-LOSS-R.1 (kills B1/B4): a -$50 loss on $100 risk journals resultR exactly -0.5 -- the sign is preserved, not flipped to +0.5, and not nulled',
      !!l.rec && l.rec.resultR===-0.5, l.rec?String(l.rec.resultR):'no rec');
    assert('JVM-LOSS-PNL.1 (kills B3): that same losing close journals pnl exactly -50',
      !!l.rec && l.rec.pnl===-50, l.rec?String(l.rec.pnl):'no rec');
    assert('JVM-LOSS-EXIT.1 (kills B7): the journalled exitPrice is the actual 1.295 exit, not the 1.3 entry',
      !!l.rec && l.rec.exitPrice===1.295, l.rec?String(l.rec.exitPrice):'no rec');
    assert('JVM-LOSS-REASON.1 (kills B8): an automatic Loss close journals closeReason exactly "STOP_LOSS"',
      !!l.rec && l.rec.closeReason==='STOP_LOSS', l.rec?String(l.rec.closeReason):'no rec');
    assert('JVM-LOSS-WHY.1 (kills B9): the losing close narrative is journalled verbatim -- "Closed as a Loss at 1.295 (-50.0 pips from entry)."',
      !!l.rec && l.rec.whyClosed==='Closed as a Loss at 1.295 (-50.0 pips from entry).', l.rec?String(l.rec.whyClosed):'no rec');
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 3 — MANUAL CLOSE + DEVELOPER/TEST CLOSE LABELLING (A3)
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    const m=await driveJvmClose({dir:'buy',entry:1.3000,stop:1.2900,target:1.3200,exitLive:1.3050,manual:true,autoResult:null});
    assert('JVM-MANUAL-REASON.1 (kills B8/A3): a MANUAL close of the same +50-pip trade journals closeReason exactly "MANUAL_CLOSE" -- the label distinguishes it from the identical automatic close above, which journalled TAKE_PROFIT',
      !!m.rec && m.rec.closeReason==='MANUAL_CLOSE', m.rec?String(m.rec.closeReason):'no rec');
    assert('JVM-MANUAL-R.1 (kills B1/B4): the manual close still journals resultR exactly +0.5 and result "Win"',
      !!m.rec && m.rec.resultR===0.5 && m.rec.result==='Win', m.rec?(m.rec.resultR+'/'+m.rec.result):'no rec');
  }
  {
    const d=await driveJvmClose({dir:'buy',entry:1.3000,stop:1.2900,target:1.3200,exitLive:1.3050,manual:false,autoResult:'Win',developer:true});
    assert('JVM-DEVCLOSE-REASON.1 (kills A3): a developer/self-test trade (isDeveloperTrade) closed through the real close path is labelled closeReason "SYSTEM_CLOSE" on the closed position -- NOT "TAKE_PROFIT", which is what the byte-identical non-developer close produced above',
      !!d.closedPos && d.closedPos.closeReason==='SYSTEM_CLOSE', d.closedPos?String(d.closedPos.closeReason):'no closedPos');
    assert('JVM-DEVCLOSE-REASON.2 (kills A3/A5/B8): that SYSTEM_CLOSE label actually reaches the journal record for the same tradeId, while its Win/Loss label stays "Win" -- the system-close classification is orthogonal to the outcome, and is journalled',
      !!d.rec && d.rec.closeReason==='SYSTEM_CLOSE' && d.rec.result==='Win', d.rec?(d.rec.closeReason+'/'+d.rec.result):'no rec');
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 4 — applyJournalCloseUpdate() DIRECTLY, WITH HAND-CHOSEN CLOSE FIELDS
  // The end-to-end groups above prove the writer is REACHED; this group pins the exact field
  // transfer with values the close path cannot produce by coincidence, including durationMs at
  // an exactly-known 90-minute separation (unavailable end-to-end, where a close happens
  // microseconds after the open).
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    const openRow={journalEntryId:'JVMJ|DUR-1',tradeId:'DUR-1',strategy:'current_strategy',strategyId:'current_strategy',
      strategyLabel:'JVM',status:'OPEN',openedAt:'2026-01-01T00:00:00.000Z',closedAt:null,exitPrice:null,entry:1.3000,
      result:null,resultR:null,pnl:null,maePips:null,mfePips:null,maeR:null,mfeR:null,
      exitDetectionSource:null,closeReason:null,durationMs:null,whyClosed:'Still open.'};
    const store=[openRow];
    const upd=g.applyJournalCloseUpdate(store,'DUR-1',
      {closedAt:'2026-01-01T01:30:00.000Z',exitPrice:1.23456,result:'Loss',resultR:-1.37,pnl:-137.25,
       maePips:12.5,mfePips:4.25,maeR:-0.125,mfeR:0.0425,exitDetectionSource:'historical_candle',closeReason:'STOP_LOSS'},
      'Fixture narrative: closed by the stop at 1.23456.');
    assert('APPLY-CLOSE.STATUS (kills O2-adjacent write side): applyJournalCloseUpdate flips the found OPEN row to status "CLOSED"',
      !!upd && upd.status==='CLOSED', upd?String(upd.status):'null');
    assert('APPLY-CLOSE.RESULT (kills B2): the caller-supplied result "Loss" is journalled as "Loss" -- not rewritten to "Win"',
      !!upd && upd.result==='Loss', upd?String(upd.result):'null');
    assert('APPLY-CLOSE.R (kills B1/B4): the caller-supplied resultR -1.37 is journalled exactly as -1.37 -- neither nulled nor sign-flipped to +1.37',
      !!upd && upd.resultR===-1.37, upd?String(upd.resultR):'null');
    assert('APPLY-CLOSE.PNL (kills B3): the caller-supplied pnl -137.25 is journalled exactly as -137.25, not null',
      !!upd && upd.pnl===-137.25, upd?String(upd.pnl):'null');
    assert('APPLY-CLOSE.EXIT (kills B7): the caller-supplied exitPrice 1.23456 is journalled as 1.23456, not the record\'s 1.3 entry price',
      !!upd && upd.exitPrice===1.23456 && upd.exitPrice!==upd.entry, upd?String(upd.exitPrice):'null');
    assert('APPLY-CLOSE.DURATION (kills B5/O4-adjacent): a 2026-01-01T00:00:00.000Z open closed at 2026-01-01T01:30:00.000Z journals durationMs of exactly 5400000 ms (90 minutes), replacing the OPEN row\'s null',
      !!upd && upd.durationMs===5400000, upd?String(upd.durationMs):'null');
    assert('APPLY-CLOSE.MAE (kills B6): MAE/MFE measured during the trade are carried onto the journal record -- maePips 12.5, mfePips 4.25, maeR -0.125, mfeR 0.0425 -- replacing the OPEN row\'s nulls',
      !!upd && upd.maePips===12.5 && upd.mfePips===4.25 && upd.maeR===-0.125 && upd.mfeR===0.0425,
      upd?(upd.maePips+'/'+upd.mfePips+'/'+upd.maeR+'/'+upd.mfeR):'null');
    assert('APPLY-CLOSE.REASON (kills B8): the caller-supplied closeReason "STOP_LOSS" is journalled, replacing the OPEN row\'s null',
      !!upd && upd.closeReason==='STOP_LOSS', upd?String(upd.closeReason):'null');
    assert('APPLY-CLOSE.WHY (kills B9): the caller-supplied close narrative is journalled verbatim, replacing "Still open."',
      !!upd && upd.whyClosed==='Fixture narrative: closed by the stop at 1.23456.', upd?String(upd.whyClosed):'null');
    assert('APPLY-CLOSE.SOURCE: the caller-supplied exitDetectionSource "historical_candle" is journalled',
      !!upd && upd.exitDetectionSource==='historical_candle', upd?String(upd.exitDetectionSource):'null');
    assert('APPLY-CLOSE.INPLACE: the update mutates the SAME row object already in the store (one row, same identity) rather than appending or replacing it',
      store.length===1 && store[0]===upd, 'len='+store.length);
  }
  {
    // Negative control for the MAE carry: a closer that supplies NO mae/mfe must leave whatever
    // the record already had, never blank it. (Guards against "fix" the mutation the other way.)
    const row={tradeId:'MAE-KEEP',status:'OPEN',openedAt:'2026-01-01T00:00:00.000Z',
      maePips:9.75,mfePips:21.5,maeR:-0.0975,mfeR:0.215,whyClosed:'Still open.',closeReason:'BREAK_EVEN'};
    const upd=g.applyJournalCloseUpdate([row],'MAE-KEEP',
      {closedAt:'2026-01-01T00:45:00.000Z',exitPrice:1.1,result:'Win',resultR:1,pnl:10},null);
    assert('APPLY-CLOSE.MAE-KEEP (negative control for B6): when the closer supplies no MAE/MFE, the values already recorded during the trade (9.75/21.5) survive untouched instead of being blanked, and the pre-existing closeReason "BREAK_EVEN" is likewise preserved rather than overwritten with null',
      !!upd && upd.maePips===9.75 && upd.mfePips===21.5 && upd.closeReason==='BREAK_EVEN',
      upd?(upd.maePips+'/'+upd.mfePips+'/'+upd.closeReason):'null');
    assert('APPLY-CLOSE.WHY-KEEP (negative control for B9): a null narrative leaves the existing whyClosed text alone rather than erasing it',
      !!upd && upd.whyClosed==='Still open.', upd?String(upd.whyClosed):'null');
  }
  {
    const missing=g.applyJournalCloseUpdate([{tradeId:'OTHER',status:'OPEN'}],'NO-SUCH-TRADE',
      {closedAt:'2026-01-01T00:00:00.000Z',exitPrice:1.1,result:'Win',resultR:1,pnl:10},'x');
    assert('APPLY-CLOSE.NOMATCH: closing a tradeId that has no row returns null and creates nothing -- a close never fabricates a row out of thin air here',
      missing===null, String(missing));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 5 — ALEX LIVE CLOSE, DRIVEN THROUGH THE REAL alexGCloseLivePosition()
  //   GBP_USD buy, entry 1.3000, exit 1.3200 -> +200.0 pips
  //   pipValue $10, positionSize 0.10 -> pnl = 200 * 10 * 0.10 = +$200.00
  //   ALEX uses the FROZEN fixed-R methodology: a Win journals resultR = plannedRR = +2.5
  //   MAE/MFE accrued on the position DURING the trade (12.5 / 33.25 pips) must land on the
  //   journal row, which was created at open with nulls.
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    seedClean();
    const pos={tradeId:'ALX-C1',pair:PAIR,timeframe:'H1',setupType:'A_repeatedReaction',setupLabel:'Repeated Zone Reaction',
      direction:'buy',entry:1.3000,stop:1.2900,target:1.3250,plannedRR:2.5,riskPercent:1,riskAmount:100,
      positionSize:0.1,pipValue:10,ruleVersion:'alex_g_sr_v1',openedAt:'2026-03-01T10:00:00.000Z', // == OPEN_MS, so the close below is exactly 90 minutes later
      liveFillPrice:1.3000,entryDelayPips:0.4,qualificationClose:1.2996,atrAtEntry:0.00123,
      zoneRoleAtQualification:'support',zoneTouchNumber:4,
      maePips:null,mfePips:null,maeR:null,mfeR:null,status:'open'};
    g.getAlexGAccount().openPositions.push(pos);
    g.freezeClock(OPEN_MS);   // §18.12: exact timestamps, so the duration below is a literal
    g.journalNoteOpenAlex(pos); // the OPEN row as it really exists at trade-open: MAE/MFE still null
    const openRow=(g.getAlexGJournalEntries()||[]).find(e=>e.tradeId==='ALX-C1')||null;
    assert('ALEX-OPEN-BASELINE.1 (baseline for C1/C2/B6): the journal row created at ALEX trade-open carries status OPEN with resultR, pnl, maePips and mfePips all null -- so every non-null value asserted after the close below was genuinely written BY the close',
      !!openRow && openRow.status==='OPEN' && openRow.resultR===null && openRow.pnl===null && openRow.maePips===null && openRow.mfePips===null,
      openRow?JSON.stringify({s:openRow.status,r:openRow.resultR,p:openRow.pnl,mae:openRow.maePips}):'no open row');
    // MAE/MFE accrue on the live position during the trade, exactly as the live poller updates them.
    pos.maePips=12.5; pos.mfePips=33.25; pos.maeR=-0.125; pos.mfeR=0.3325;
    g.freezeClock(CLOSE_MS);
    // G-4 (MOGO-024): this call passed {} and the two assertions below asserted the INVENTED
    // default -- alexGCloseLivePosition used to fabricate exitDetectionSource:'live_snapshot'
    // when a caller supplied none. That fallback is removed; an unsupplied source is now
    // UNKNOWN (null). These fixtures are about JOURNALLING a source verbatim, not about
    // defaulting one, so the source is supplied explicitly here and both assertions keep
    // their original exact-literal strength. The UNKNOWN contract is pinned by v1241.
    g.alexGCloseLivePosition('ALX-C1','Win',1.3200,null,{exitDetectionSource:'live_snapshot'});
    g.restoreClock();
    const rec=(g.getAlexGJournalEntries()||[]).find(e=>e.tradeId==='ALX-C1')||null;
    const closed=(g.getAlexGAccount().closedPositions||[])[0]||null;
    assert('ALEX-CLOSE-CONTROL.1 (positive control): the real alexGCloseLivePosition() closed the position at 1.32 for exactly +$200.00 and moved the balance to exactly 10200 -- so a journal failure below is a journal defect, not an unreached close',
      !!closed && closed.exitPrice===1.32 && closed.pnl===200 && g.getAlexGAccount().balance===10200,
      closed?('exit='+closed.exitPrice+' pnl='+closed.pnl+' bal='+g.getAlexGAccount().balance):'no closed');
    assert('ALEX-CLOSE-REACH.1: the real ALEX close updates the SAME journal row by tradeId to status CLOSED -- one row, not a second appended one',
      !!rec && rec.status==='CLOSED' && (g.getAlexGJournalEntries()||[]).filter(e=>e.tradeId==='ALX-C1').length===1,
      rec?String(rec.status):'no rec');
    assert('ALEX-CLOSE-R.1 (kills C1): an ALEX Win on a 2.5R plan journals resultR exactly +2.5 (the frozen fixed-R methodology), not null',
      !!rec && rec.resultR===2.5, rec?String(rec.resultR):'no rec');
    assert('ALEX-CLOSE-PNL.1: the same close journals pnl exactly +200 and exitPrice exactly 1.32',
      !!rec && rec.pnl===200 && rec.exitPrice===1.32, rec?(rec.pnl+'/'+rec.exitPrice):'no rec');
    assert('ALEX-CLOSE-MAE.1 (kills C2/B6): the MAE/MFE that accrued on the live position during the trade (12.5 / 33.25 pips, -0.125R / +0.3325R) are carried onto the journal row, which held null for all four at open',
      !!rec && rec.maePips===12.5 && rec.mfePips===33.25 && rec.maeR===-0.125 && rec.mfeR===0.3325,
      rec?(rec.maePips+'/'+rec.mfePips+'/'+rec.maeR+'/'+rec.mfeR):'no rec');
    assert('ALEX-CLOSE-RESULT.1 (kills B2): the ALEX close journals result exactly "Win"',
      !!rec && rec.result==='Win', rec?String(rec.result):'no rec');
    assert('ALEX-CLOSE-SOURCE.1: a caller-supplied exit detection source is journalled verbatim as "live_snapshot" (G-4: it is no longer DEFAULTED when absent)',
      !!rec && rec.exitDetectionSource==='live_snapshot', rec?String(rec.exitDetectionSource):'no rec');
    assert('ALEX-CLOSE-WHY.1 (kills B9): the ALEX close narrative is journalled verbatim -- "Closed as a Win when price reached the target (1.32), detected via the current live bid/ask snapshot." -- replacing the open row\'s "Still open."',
      !!rec && rec.whyClosed==='Closed as a Win when price reached the target (1.32), detected via the current live bid/ask snapshot.',
      rec?String(rec.whyClosed):'no rec');
    // EXACT literal, not "is a number and > 0" (§18.12): the previous shape passed against a
    // mutation journalling durationMs as 1 for every trade -- a wrong value is still a value.
    assert('ALEX-CLOSE-DURATION.1 (kills B5): the ALEX close writes durationMs of exactly 5400000 (90 minutes, from the frozen open and close instants) onto a row that held null at open',
      !!rec && rec.durationMs===5400000, rec?String(rec.durationMs):'no rec');
  }
  {
    // ALEX losing close: fixed-R methodology journals exactly -1R regardless of the plan's R:R,
    // which a sign-flip or a null-R mutation cannot reproduce.
    seedClean();
    const pos={tradeId:'ALX-C2',pair:PAIR,timeframe:'H4',setupType:'B_breakRetest',direction:'sell',
      entry:1.3000,stop:1.3100,target:1.2750,plannedRR:2.5,riskAmount:100,positionSize:0.1,pipValue:10,
      ruleVersion:'alex_g_sr_v1',openedAt:'2026-03-02T00:00:00.000Z',liveFillPrice:1.3000,entryDelayPips:0.2,
      qualificationClose:1.3002,atrAtEntry:0.00111,brokenDirection:'downThroughSupport',zoneTouchNumber:5,
      maePips:null,mfePips:null,maeR:null,mfeR:null,status:'open'};
    g.getAlexGAccount().openPositions.push(pos);
    g.journalNoteOpenAlex(pos);
    g.alexGCloseLivePosition('ALX-C2','Loss',1.3100,null,{exitDetectionSource:'historical_candle',exitTriggerLevel:1.31});
    const rec=(g.getAlexGJournalEntries()||[]).find(e=>e.tradeId==='ALX-C2')||null;
    assert('ALEX-LOSS-R.1 (kills C1/B1/B4): an ALEX Loss journals resultR exactly -1 under the frozen fixed-R methodology -- not null, not +1, and not the 2.5R plan',
      !!rec && rec.resultR===-1, rec?String(rec.resultR):'no rec');
    assert('ALEX-LOSS-PNL.1 (kills B3/B2): the 100-pip adverse move on a 0.1-lot $10/pip short journals pnl exactly -100 and result exactly "Loss"',
      !!rec && rec.pnl===-100 && rec.result==='Loss', rec?(rec.pnl+'/'+rec.result):'no rec');
    assert('ALEX-LOSS-EXIT.1 (kills B7): the journalled exitPrice is the 1.31 stop fill, not the 1.3 entry',
      !!rec && rec.exitPrice===1.31 && rec.exitPrice!==rec.entry, rec?String(rec.exitPrice):'no rec');
    assert('ALEX-LOSS-WHY.1 (kills B9): the historical-candle exit narrative is journalled verbatim -- "Closed as a Loss when price reached the stop (1.31), detected via a reconstructed historical bid/ask candle."',
      !!rec && rec.whyClosed==='Closed as a Loss when price reached the stop (1.31), detected via a reconstructed historical bid/ask candle.',
      rec?String(rec.whyClosed):'no rec');
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 6 — normalizeJournalRecord(), READ END-TO-END THROUGH getUnifiedJournalRecords()
  // Records are placed in the real stores and read back through the real registry-driven
  // reader, so these fixtures cover the normalizer as it is actually REACHED, not in isolation.
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    seedClean();
    g.setJournalEntries([
      // (a) A fully-shaped v5.0+ CLOSED record.
      {journalEntryId:'JVMJ|N1',tradeId:'N1',strategy:'current_strategy',strategyId:'current_strategy',strategyLabel:'JVM',
       tradeSource:'AUTO',isDeveloperTrade:false,pair:'GBP/USD',direction:'buy',entry:1.3,stop:1.29,target:1.32,
       openedAt:'2026-02-01T00:00:00.000Z',closedAt:'2026-02-01T01:30:00.000Z',exitPrice:1.3175,
       result:'Win',resultR:1.75,pnl:175.5,status:'CLOSED',closeReason:'TAKE_PROFIT',
       biasSummary:'Recorded bias text.',whyClosed:'Recorded close text.'},
      // (b) A LEGACY closed record: no status, no closeReason, no durationMs, no explanation
      //     fields, and no strategy id -- exactly what a pre-v12.3.2 close left behind.
      {tradeId:'N2',pair:'EUR/USD',dir:'Sell',result:'Loss',resultR:-1,pnl:-100,
       openedAt:'2026-01-15T08:00:00.000Z',closedAt:'2026-01-15T09:30:00.000Z',exitPrice:1.0850},
      // (c) A developer/self-test record that predates tradeSource being persisted.
      {tradeId:'N3',pair:'GBP/USD',dir:'Buy',isDeveloperTrade:true,result:'Win',resultR:0.5,pnl:50,
       openedAt:'2026-01-20T00:00:00.000Z',closedAt:'2026-01-20T00:30:00.000Z',exitPrice:1.305},
      // (d) A still-OPEN record with no result yet.
      {tradeId:'N4',pair:'USD/JPY',dir:'Buy',openedAt:'2026-02-10T00:00:00.000Z'}
    ]);
    const recs=g.getUnifiedJournalRecords()||[];
    const byId=id=>recs.find(r=>r.tradeId===id)||null;
    const n1=byId('N1'),n2=byId('N2'),n3=byId('N3'),n4=byId('N4');
    assert('NORM-REACH.1: all four seeded JVM journal records survive the real registry-driven getUnifiedJournalRecords() read path',
      recs.length===4 && !!n1 && !!n2 && !!n3 && !!n4, 'count='+recs.length);
    assert('NORM-R.1 (kills O1): a closed record\'s resultR reaches the display model intact -- +1.75 for N1 and -1 for the legacy N2 -- not dropped to null',
      !!n1 && n1.resultR===1.75 && !!n2 && n2.resultR===-1, (n1?n1.resultR:'?')+'/'+(n2?n2.resultR:'?'));
    assert('NORM-R.2 (kills O1): the accompanying pnl values also survive normalization exactly -- +175.5 and -100',
      !!n1 && n1.pnl===175.5 && !!n2 && n2.pnl===-100, (n1?n1.pnl:'?')+'/'+(n2?n2.pnl:'?'));
    assert('NORM-STATUS.1 (kills O2): an explicitly CLOSED record normalizes to status "CLOSED", and a legacy record with a result but no status field is also derived as "CLOSED" -- status is not pinned at OPEN',
      !!n1 && n1.status==='CLOSED' && !!n2 && n2.status==='CLOSED', (n1?n1.status:'?')+'/'+(n2?n2.status:'?'));
    assert('NORM-STATUS.2 (negative control for O2): a record with a tradeId and no result still normalizes to "OPEN" -- status is not pinned at CLOSED either',
      !!n4 && n4.status==='OPEN', n4?String(n4.status):'?');
    assert('NORM-REASON.1 (kills O3): a LEGACY record closed before close-reasons existed normalizes with closeReason null -- a reason is never fabricated for it',
      !!n2 && n2.closeReason===null, n2?String(n2.closeReason):'?');
    assert('NORM-REASON.2 (positive control for O3): a record that genuinely recorded TAKE_PROFIT normalizes to exactly "TAKE_PROFIT", so NORM-REASON.1 is about fabrication and not about the field being ignored',
      !!n1 && n1.closeReason==='TAKE_PROFIT', n1?String(n1.closeReason):'?');
    assert('NORM-DURATION.1 (kills O4): a record with no stored durationMs has it DERIVED from its own timestamps -- 2026-02-01T00:00:00.000Z to 01:30:00.000Z is exactly 5400000 ms',
      !!n1 && n1.durationMs===5400000, n1?String(n1.durationMs):'?');
    assert('NORM-DURATION.2 (kills O4): the legacy 08:00:00 -> 09:30:00 record likewise derives exactly 5400000 ms, and the 30-minute N3 derives exactly 1800000 ms',
      !!n2 && n2.durationMs===5400000 && !!n3 && n3.durationMs===1800000, (n2?n2.durationMs:'?')+'/'+(n3?n3.durationMs:'?'));
    assert('NORM-DURATION.3 (negative control for O4): a still-open record with no closedAt derives durationMs null rather than a fabricated number',
      !!n4 && n4.durationMs===null, n4?String(n4.durationMs):'?');
    assert('NORM-SOURCE.1 (kills O5): a developer/self-test record with no persisted tradeSource normalizes to tradeSource "TEST" -- it is not reported as AUTO',
      !!n3 && n3.tradeSource==='TEST', n3?String(n3.tradeSource):'?');
    assert('NORM-SOURCE.2 (positive control for O5): a genuine non-developer AUTO record still normalizes to "AUTO", so NORM-SOURCE.1 is about misclassification and not about the field being pinned to TEST',
      !!n1 && n1.tradeSource==='AUTO' && n1.isDeveloperTrade===false, n1?(n1.tradeSource+'/'+n1.isDeveloperTrade):'?');
    assert('NORM-BIAS.1 (kills O6): a JVM record that never recorded a bias/AOI/trigger/confluence summary normalizes those four fields to the explicit "Not recorded for this historical trade." disclosure -- never a blank, never null, never a fabricated summary',
      !!n2 && n2.biasSummary===NOT_RECORDED && n2.aoiSummary===NOT_RECORDED && n2.triggerSummary===NOT_RECORDED && n2.confluenceSummary===NOT_RECORDED,
      n2?JSON.stringify(n2.biasSummary):'?');
    assert('NORM-BIAS.2 (positive control for O6): a record that DID record a bias keeps its own text ("Recorded bias text."), so NORM-BIAS.1 is about the unrecorded case and not about the field being overwritten for everyone',
      !!n1 && n1.biasSummary==='Recorded bias text.', n1?String(n1.biasSummary):'?');
    assert('NORM-WHY.1 (kills O6-adjacent): an unrecorded whyClosed normalizes to the same explicit disclosure, while a recorded one keeps its own text',
      !!n2 && n2.whyClosed===NOT_RECORDED && !!n1 && n1.whyClosed==='Recorded close text.',
      (n2?JSON.stringify(n2.whyClosed):'?')+'/'+(n1?JSON.stringify(n1.whyClosed):'?'));
    assert('NORM-EXIT.1: the legacy record\'s exitPrice 1.085 and result "Loss" survive normalization, and its "Sell" dir is lowercased to direction "sell"',
      !!n2 && n2.exitPrice===1.085 && n2.result==='Loss' && n2.direction==='sell',
      n2?(n2.exitPrice+'/'+n2.result+'/'+n2.direction):'?');
  }
  {
    // ALEX-side normalization, read through the same real path.
    seedClean();
    g.setAlexGJournalEntries([
      {journalEntryId:'ALEXJ|A1',tradeId:'A1',strategy:'alex_g_sr_v1',strategyId:'alex_g_sr_v1',strategyLabel:'ALEX',
       tradeSource:'AUTO',pair:'GBP/USD',timeframe:'H1',direction:'buy',entry:1.3,exitPrice:1.325,
       openedAt:'2026-02-05T00:00:00.000Z',closedAt:'2026-02-05T02:00:00.000Z',
       result:'Win',resultR:2.5,pnl:250,status:'CLOSED',closeReason:null,maePips:12.5,mfePips:33.25},
      // legacy pre-v5.0 ALEX row: tradeId but no strategy field at all
      {tradeId:'A2',pair:'EUR/USD',direction:'sell',result:'Loss',resultR:-1,pnl:-100,
       openedAt:'2026-02-06T00:00:00.000Z',closedAt:'2026-02-06T00:45:00.000Z',exitPrice:1.095}
    ]);
    const recs=g.getUnifiedJournalRecords()||[];
    const a1=recs.find(r=>r.tradeId==='A1')||null;
    const a2=recs.find(r=>r.tradeId==='A2')||null;
    assert('NORM-ALEX-R.1 (kills O1): ALEX records keep their resultR through normalization -- +2.5 and -1',
      !!a1 && a1.resultR===2.5 && !!a2 && a2.resultR===-1, (a1?a1.resultR:'?')+'/'+(a2?a2.resultR:'?'));
    assert('NORM-ALEX-STATUS.1 (kills O2): the ALEX closed record normalizes to status "CLOSED", and the legacy ALEX row with a result but no status is derived as "CLOSED" too',
      !!a1 && a1.status==='CLOSED' && !!a2 && a2.status==='CLOSED', (a1?a1.status:'?')+'/'+(a2?a2.status:'?'));
    assert('NORM-ALEX-REASON.1 (kills O3): neither ALEX record fabricates a closeReason -- both normalize to null, because the ALEX close path does not record one',
      !!a1 && a1.closeReason===null && !!a2 && a2.closeReason===null, (a1?String(a1.closeReason):'?')+'/'+(a2?String(a2.closeReason):'?'));
    assert('NORM-ALEX-DURATION.1 (kills O4): the ALEX record\'s 2-hour span derives durationMs of exactly 7200000, and the legacy 45-minute row exactly 2700000',
      !!a1 && a1.durationMs===7200000 && !!a2 && a2.durationMs===2700000, (a1?a1.durationMs:'?')+'/'+(a2?a2.durationMs:'?'));
    assert('NORM-ALEX-MAE.1: ALEX MAE/MFE survive normalization exactly (12.5 / 33.25 pips)',
      !!a1 && a1.maePips===12.5 && a1.mfePips===33.25, a1?(a1.maePips+'/'+a1.mfePips):'?');
    assert('NORM-ALEX-BIAS.1 (negative control for O6): ALEX records that structurally never had bias/AOI/trigger/confluence summaries normalize those to null -- the JVM-only "Not recorded" disclosure is NOT applied to a strategy that never had the concept',
      !!a1 && a1.biasSummary===null && a1.aoiSummary===null && a1.triggerSummary===null && a1.confluenceSummary===null,
      a1?JSON.stringify(a1.biasSummary):'?');
    assert('NORM-ALEX-RULEVERSION.1: a legacy ALEX row with no ruleVersion of its own normalizes to the frozen "alex_g_sr_v1", and is flagged isLegacyAlex',
      !!a2 && a2.ruleVersion==='alex_g_sr_v1' && a2.isLegacyAlex===true, a2?(a2.ruleVersion+'/'+a2.isLegacyAlex):'?');
  }

  // ── ISOLATION.1 REMOVED (§18.12) ─────────────────────────────────────────────────────────
  // It asserted that seedClean() leaves clean in-memory defaults -- but the harness setters and
  // getters are bare assignments (`function(v){paperAccount=v;}` / `function(){return paperAccount;}`)
  // and nothing between the write and the read can reach those variables. The assertion reduced to
  // ({balance:10000}).balance === 10000, with NO PRODUCTION CODE IN ITS PATH, so no mutation of any
  // production function could ever kill it. Proven by an independent verifier: it survived all 27
  // mutations, including one that made openPaperPosition return null and killed 21 fixtures in this
  // same suite. It also did not show what it claimed -- real-storage isolation is a property of the
  // runner's localStorage stub, which the fixture never touched. Deleted rather than reworded: a
  // seventh unkillable fixture is not evidence, and padding a now-pinned count with one is worse.

  return results;
}
