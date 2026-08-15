// ══════════════════════════════════════════════════════════════════════════════════════════
// v12.3.9 PAPER-POSITION LIFECYCLE, PERSISTENCE, AND LEDGER / ACCOUNT / JOURNAL RECONCILIATION
// ══════════════════════════════════════════════════════════════════════════════════════════
// Closes a MEASURED mutation-coverage gap. A 25-mutation adversarial re-score of the paper
// position state machine (open -> live -> closed -> recorded) and of everything that keeps the
// three stores agreeing -- paperAccount, the journals, and the ledger/commit layer -- found three
// behaviour-changing mutations that killed ZERO of the 1,996 fixtures in the gate:
//
//   * the closed position is never removed from openPositions, so one trade lives in BOTH stores
//     simultaneously (duplicated in every count, and permanently unmatchable);
//   * a REJECTED close rolls the account back but leaves the JOURNAL recording the trade as
//     CLOSED -- a partial rollback, with the two stores permanently disagreeing about whether the
//     trade is open;
//   * savePaperAccountGuarded()'s compensating rollback stops REMOVING the keys it had already
//     written, so a commit that failed part-way leaves a new fxhub_paper / fxhub_paper_version
//     persisted for a save that never completed.
//
// WHY THE FIRST ONE SURVIVED, AND WHY THIS SUITE IS ASYNCHRONOUS. A fixture in the existing paper
// trading audit suite (tests/v_paper_trading_audit_tests.js, "Reconciliation.1") claims that a
// normal open->close cycle produces zero integrity findings, including zero duplicate account ids
// -- which is exactly the assertion that catches a position living in both stores. It never fires,
// because the suite is synchronous and calls g.closePaperPosition(...) WITHOUT awaiting it.
// closePaperPosition is `async` with an internal `await fetchBidAsk(...)`, so the fixture observes
// the account BEFORE the close has done anything at all: one open position, zero closed, balance
// untouched. Against that state every clause it asserts is trivially true. It is a false green,
// and it is reported as one. Every close in THIS suite is awaited; see the runner's header for why
// that is genuinely observable offline.
//
// EVIDENCE STANDARD APPLIED HERE:
//   * No fixture asserts against source text.
//   * No fixture is SELF-CONSISTENT. Nothing below is of the form
//     `balance === balanceBefore + closedPos.pnl` -- that compares two outputs of the SAME
//     computation and is blind to a wrong P&L appearing identically on both sides. This exact
//     anti-pattern was found in this area (run_v1233, JVMCLOSE-1, where it is disclosed). Every
//     money figure below is a hand-computed literal.
//   * THE ARITHMETIC, done by hand ONCE and reused as literals throughout:
//       balance $10,000, risk 1% = $100.  GBP_USD: pip 0.0001, quote is USD, so
//       pipValuePerLot = 0.0001 * 100,000 = $10 per pip per lot.
//       entry 1.3000, stop 1.2900 -> 100 pips of risk -> lots = 100/(100*10) = 0.10 exactly.
//       A buy exited at 1.3050 is +50.0 pips -> 50 * $10 * 0.10 = +$50.00 -> balance $10,050.00.
//       A buy exited at 1.3000 (its own entry) is 0.0 pips -> $0.00 -> balance $10,000.00.
//   * Every detector is exercised BOTH ways: a POSITIVE control proving it fires on the corrupt
//     shape, and a NEGATIVE control proving it stays silent on the clean one. A change that
//     permanently reports a problem dies on the negative half; one that permanently reports CLEAN
//     dies on the positive half.
//   * No fixture reads the LENGTH of paperEngineErrors. That log caps at 50 via unshift+slice, so
//     a length comparison stops discriminating once saturated -- a false-positive control of
//     exactly that shape has already been found in this repository. Message CONTENT is asserted.
//
// ISOLATION: in-memory only, stubbed localStorage, rejecting fetch, no real browser storage and no
// network. No real paper trade can be persisted from this process because this process has no
// access to real storage in the first place.
async function runV1239LifecycleReconciliationFixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,method:'execution',detail:detail||''});};
  const PAIR='GBP_USD';
  const OPEN_MS=Date.parse('2026-05-04T09:00:00.000Z');
  const CLOSE_MS=OPEN_MS+3600000;                       // +60 minutes

  function seedClean(){
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGJournalEntries([]);
    g.setPaperReconciliationAudit([]);
    g.setPaperResetHistory([]);
    g.setStorageLoadFailures({});
    g.setPaperEngineErrors([]);
    g.setPairData(PAIR,null);
    g.clearStorageFailures();
    g.clearLocalStorage();
    g.resetPaperVersionGuard();
    g.resetPaperPositionsClosing();
  }

  // Drives the REAL, PROTECTED openPaperPosition() + closePaperPosition() end to end, awaited.
  async function driveOpenClose(o){
    seedClean();
    g.freezeClock(OPEN_MS);
    const pos=g.openPaperPosition(PAIR,o.dir||'buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData(PAIR,o.exit);
    g.freezeClock(CLOSE_MS);
    const res=await g.closePaperPosition(pos.id,!!o.manual,o.autoResult||null);
    g.restoreClock();
    return{pos,res};
  }
  const jrec=(id)=>(g.getJournalEntries()||[]).filter(e=>e.tradeId===id);
  // Reads a persisted key as JSON, degrading a missing/unparseable key to null instead of throwing.
  // A mutation that stops persisting a key must fail the fixture that asserts the persisted value,
  // not abort the whole suite -- a suite that dies part-way tells you far less than one that names
  // the assertion that broke (and run_all.sh's fixture-count check would flag the short run, but a
  // named failure is the evidence worth having).
  const stored=(k)=>{ try{ const v=g.lsGet(k); return v==null?null:JSON.parse(v); }catch(e){ return null; } };
  const bal=(k)=>{ const o=stored(k); return o&&typeof o.balance==='number'?o.balance:null; };

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 1 — THE STATE MACHINE: open -> live -> closed -> recorded, driven end to end
  // ══════════════════════════════════════════════════════════════════════════════════════
  const e2e=await driveOpenClose({exit:1.3050,autoResult:'Win'});
  {
    assert('LCR-E2E.0 (PRECONDITION): the position every hand-computed dollar figure in this suite assumes -- 0.10 lots at $10/pip on $100 of risk from a $10,000 account, opened and committed',
      !!e2e.pos && !e2e.pos.error && e2e.pos.lots===0.1 && e2e.pos.riskAmount===100 &&
      e2e.pos.pipValueAtEntry===10 && e2e.pos.entry===1.3 && e2e.pos.committed===true,
      e2e.pos?('lots='+e2e.pos.lots+' risk='+e2e.pos.riskAmount+' pipVal='+e2e.pos.pipValueAtEntry+' committed='+e2e.pos.committed):'no position');
    const acct=g.getPaperAccount();
    // THE MUTATION THIS KILLS: delete `paperAccount.openPositions.splice(idx2,1)` from
    // closePaperPosition and the trade sits in BOTH stores. Nothing in the 1,996-fixture gate
    // noticed, because the one fixture that asserts this shape never awaits the close.
    assert('LCR-E2E.1: after the AWAITED real close the trade lives in exactly ONE store -- zero occurrences in openPositions, exactly one in closedPositions',
      acct.openPositions.filter(p=>p.id===e2e.pos.id).length===0 &&
      acct.closedPositions.filter(p=>p.id===e2e.pos.id).length===1 &&
      acct.openPositions.length===0 && acct.closedPositions.length===1,
      'open='+acct.openPositions.length+' closed='+acct.closedPositions.length);
    const integ=g.computePaperLedgerIntegrity();
    assert('LCR-E2E.2: and the integrity report agrees -- the id is counted ONCE across the two account stores, so duplicateAccountIds is empty and no position is reported unjournalled',
      integ.duplicateAccountIds.length===0 && integ.accountPositionsWithNoJournal.length===0,
      'dupIds='+JSON.stringify(integ.duplicateAccountIds)+' unjournalled='+integ.accountPositionsWithNoJournal.length);
    const cp=acct.closedPositions[0]||{};
    assert('LCR-E2E.3: the closed record carries the hand-computed money -- exit exactly 1.305, pnl exactly +50, and the account balance is exactly 10050 (a fixture literal, never balanceBefore+pnl)',
      cp.exitPrice===1.305 && cp.pnl===50 && acct.balance===10050,
      'exit='+cp.exitPrice+' pnl='+cp.pnl+' balance='+acct.balance);
    assert('LCR-E2E.4: derived and actual balance agree exactly -- expectedBalance 10050, actualBalance 10050, difference exactly 0',
      integ.expectedBalance===10050 && integ.actualBalance===10050 && integ.balanceDifference===0,
      'expected='+integ.expectedBalance+' actual='+integ.actualBalance+' diff='+integ.balanceDifference);
    const rows=jrec(e2e.pos.id);
    assert('LCR-E2E.5: the journal holds exactly ONE row for the trade, at status CLOSED with pnl exactly 50 -- the third store agrees with the other two',
      rows.length===1 && rows[0].status==='CLOSED' && rows[0].pnl===50 && rows[0].exitPrice===1.305,
      'rows='+rows.length+' status='+(rows[0]||{}).status+' pnl='+(rows[0]||{}).pnl);
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 2 — PERSISTENCE AND RESTART. Everything above is in-memory; these read the BYTES.
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    const storedAcct=stored('fxhub_paper');
    assert('LCR-PERSIST.1: the PERSISTED account bytes (not the in-memory object) hold balance exactly 10050, zero open positions and exactly one closed position with pnl exactly 50',
      !!storedAcct && storedAcct.balance===10050 && storedAcct.openPositions.length===0 &&
      storedAcct.closedPositions.length===1 && storedAcct.closedPositions[0].pnl===50,
      storedAcct?('balance='+storedAcct.balance+' open='+storedAcct.openPositions.length+' closed='+storedAcct.closedPositions.length):'nothing persisted');
    const storedJournal=stored('fxhub_journal');
    const sr=(storedJournal||[]).filter(e=>e.tradeId===e2e.pos.id);
    assert('LCR-PERSIST.2: the PERSISTED journal bytes hold exactly one CLOSED row for that trade with pnl exactly 50 -- the account and the journal were persisted together, not one without the other',
      sr.length===1 && sr[0].status==='CLOSED' && sr[0].pnl===50,
      'rows='+sr.length+' status='+(sr[0]||{}).status);
    assert('LCR-PERSIST.3: the optimistic-concurrency counter advanced exactly twice from a version-less start -- one commit for the open, one for the close, so fxhub_paper_version is exactly "2"',
      g.lsGet('fxhub_paper_version')==='2' && g.getKnownVersion()===2,
      'stored='+g.lsGet('fxhub_paper_version')+' session='+g.getKnownVersion());
    // RESTART. Discard every in-memory value and rehydrate ONLY from the persisted bytes, the way a
    // reload does. If the close persisted a half-state, this is where it shows.
    g.setPaperAccount({balance:0,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setPaperAccount(stored('fxhub_paper')||{balance:0,openPositions:[],closedPositions:[]});
    g.setJournalEntries(stored('fxhub_journal')||[]);
    const after=g.computePaperLedgerIntegrity();
    assert('LCR-PERSIST.4 (END-TO-END, RESTART): rehydrated from storage alone the books reconcile CLEAN -- balance exactly 10050, expectedBalance exactly 10050, difference exactly 0, and every one of the six finding lists empty',
      g.getPaperAccount().balance===10050 && after.expectedBalance===10050 && after.balanceDifference===0 &&
      after.journalWithNoAccountMatch.length===0 && after.accountPositionsWithNoJournal.length===0 &&
      after.duplicateAccountIds.length===0 && after.duplicateJournalTradeIds.length===0 &&
      after.closedJournalMissingPnl.length===0 && after.closedAccountMissingJournalClosure.length===0,
      'balance='+g.getPaperAccount().balance+' diff='+after.balanceDifference+
      ' findings='+[after.journalWithNoAccountMatch,after.accountPositionsWithNoJournal,after.duplicateAccountIds,
        after.duplicateJournalTradeIds,after.closedJournalMissingPnl,after.closedAccountMissingJournalClosure].map(a=>a.length).join('/'));
    // NEGATIVE CONTROL, stated separately from LCR-PERSIST.4 because it is the half that dies to a
    // detector wired permanently ON: on a genuinely clean book the verdict must be silent.
    assert('LCR-CLEAN.1 (NEGATIVE CONTROL): on that same clean, restarted book nothing is reported at all -- a detector that permanently flags a problem cannot pass here',
      [after.journalWithNoAccountMatch,after.accountPositionsWithNoJournal,after.duplicateAccountIds,
       after.duplicateJournalTradeIds,after.closedJournalMissingPnl,after.closedAccountMissingJournalClosure,
       after.newlyOrphanedAfterReset].every(a=>a.length===0) && after.balanceDifference===0,
      'all seven lists empty, difference 0');
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 3 — POSITIVE CONTROLS. The same detectors, on deliberately corrupted books.
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    // Corrupt ONLY the balance: same one closed trade of +50 against a book that says +125.
    const acct=JSON.parse(JSON.stringify(g.getPaperAccount()));
    acct.balance=10125;
    g.setPaperAccount(acct);
    const bad=g.computePaperLedgerIntegrity();
    assert('LCR-DETECT.1 (POSITIVE CONTROL): a balance 75 dollars above what the closed trades justify is reported as a difference of exactly +75.00 against an expectedBalance still exactly 10050 -- an exact amount, not merely "nonzero"',
      bad.expectedBalance===10050 && bad.actualBalance===10125 && bad.balanceDifference===75,
      'expected='+bad.expectedBalance+' actual='+bad.actualBalance+' diff='+bad.balanceDifference);
    // Corrupt the STORES: put the closed position back into openPositions too -- one trade, two
    // stores. This is the exact shape the surviving mutation produces.
    acct.balance=10050;
    acct.openPositions=acct.closedPositions.length?[JSON.parse(JSON.stringify(acct.closedPositions[0]))]:[];
    g.setPaperAccount(acct);
    const both=g.computePaperLedgerIntegrity();
    assert('LCR-DETECT.2 (POSITIVE CONTROL for LCR-E2E.2): a trade present in BOTH openPositions and closedPositions is reported -- its id appears in duplicateAccountIds, and the second copy is reported as having no journal record of its own',
      both.duplicateAccountIds.length===1 && both.duplicateAccountIds[0]===String(e2e.pos.id) &&
      both.accountPositionsWithNoJournal.length===1,
      'dupIds='+JSON.stringify(both.duplicateAccountIds)+' unjournalled='+both.accountPositionsWithNoJournal.length);
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 4 — CENT-EXACT BALANCE ARITHMETIC (boundary)
  //   33.33 + 33.33 + 33.34 = 100.00 exactly. Chosen so a sum that drops or mis-rounds a cent
  //   is visible, and so "the difference is rounded to whole dollars" cannot hide.
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    seedClean();
    const mk=(id,pnl)=>({id:id,pair:'GBP/USD',oPair:'GBP_USD',dir:'buy',entry:1.3,stop:1.29,target:1.32,
      riskAmount:100,lots:0.1,pnl:pnl,result:pnl>=0?'Win':'Loss',exitPrice:1.305,
      openedAt:'2026-05-04T09:00:00.000Z',closedAt:'2026-05-04T10:00:00.000Z'});
    g.setPaperAccount({balance:10100,openPositions:[],closedPositions:[mk(901,33.33),mk(902,33.33),mk(903,33.34)]});
    g.setJournalEntries([]);
    const c1=g.computePaperLedgerIntegrity();
    assert('LCR-CENT.1: three closed trades of 33.33 / 33.33 / 33.34 give an expectedBalance of exactly 10100.00 and, against an actual balance of 10100.00, a difference of exactly 0',
      c1.expectedBalance===10100 && c1.balanceDifference===0,
      'expected='+c1.expectedBalance+' diff='+c1.balanceDifference);
    const acct=g.getPaperAccount(); acct.balance=10100.01; g.setPaperAccount(acct);
    const c2=g.computePaperLedgerIntegrity();
    assert('LCR-CENT.2 (BOUNDARY): a book one CENT out is reported as a difference of exactly 0.01 -- a single cent is not rounded away',
      c2.balanceDifference===0.01,'diff='+c2.balanceDifference);
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 5 — ZERO-P&L BOUNDARY. A trade that moves the books by nothing must still be
  // recorded, and must move the balance by exactly nothing.
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    const z=await driveOpenClose({exit:1.3000,manual:true});
    const acct=g.getPaperAccount();
    const cp=acct.closedPositions[0]||{};
    assert('LCR-ZERO.1 (BOUNDARY): a manual close at exactly the entry price records pnl exactly 0 and result "Break even", and the balance is exactly 10000.00 -- unchanged to the cent',
      cp.pnl===0 && cp.result==='Break even' && acct.balance===10000 && acct.openPositions.length===0,
      'pnl='+cp.pnl+' result='+cp.result+' balance='+acct.balance);
    const zi=g.computePaperLedgerIntegrity();
    assert('LCR-ZERO.2: and a zero-P&L trade still reconciles -- expectedBalance exactly 10000, difference exactly 0, with the trade genuinely present as one closed position',
      zi.expectedBalance===10000 && zi.balanceDifference===0 && acct.closedPositions.length===1 &&
      jrec(z.pos.id).length===1 && jrec(z.pos.id)[0].status==='CLOSED',
      'expected='+zi.expectedBalance+' diff='+zi.balanceDifference+' closed='+acct.closedPositions.length);
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 6 — REJECTED CLOSE: THE ROLLBACK MUST BE COMPLETE, ACROSS BOTH STORES
  //
  // The close is rejected by the REAL optimistic-concurrency guard (storage holds a version this
  // session has never seen), not by anything stubbed. The mutation these exist to kill rolls the
  // ACCOUNT back and leaves the JOURNAL saying CLOSED -- a partial rollback that permanently
  // disagrees with itself.
  // ══════════════════════════════════════════════════════════════════════════════════════
  let rolled;
  {
    seedClean();
    g.freezeClock(OPEN_MS);
    const pos=g.openPaperPosition(PAIR,'buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData(PAIR,1.3050);
    const acctBytesBefore=g.lsGet('fxhub_paper');
    const journalBytesBefore=g.lsGet('fxhub_journal');
    g.lsSet('fxhub_paper_version','999');               // another tab wrote while this one was open
    g.freezeClock(CLOSE_MS);
    const res=await g.closePaperPosition(pos.id,false,'Win');
    g.restoreClock();
    rolled={pos,res,acctBytesBefore,journalBytesBefore};
    const rows=jrec(pos.id);
    assert('LCR-ROLL.1: a REJECTED close rolls the JOURNAL back too -- the row is at status OPEN again with pnl, closedAt, result and exitPrice all null. The journal never records a close the account refused.',
      rows.length===1 && rows[0].status==='OPEN' && rows[0].pnl===null && rows[0].closedAt===null &&
      rows[0].result===null && rows[0].exitPrice===null,
      'status='+(rows[0]||{}).status+' pnl='+(rows[0]||{}).pnl+' closedAt='+(rows[0]||{}).closedAt);
    const acct=g.getPaperAccount();
    assert('LCR-ROLL.2: and the ACCOUNT is rolled back exactly -- balance exactly 10000.00, the position back in openPositions exactly once, closedPositions empty',
      acct.balance===10000 && acct.openPositions.filter(p=>p.id===pos.id).length===1 &&
      acct.closedPositions.length===0,
      'balance='+acct.balance+' open='+acct.openPositions.length+' closed='+acct.closedPositions.length);
    // The reason travels under `error` here, not `reason` -- closePaperPosition/openPaperPosition
    // return {error, blocked, integrityCompromised} while applyPaperReconciliation returns
    // {reason, blocked}. Asserted against the shape the close path actually returns.
    assert('LCR-ROLL.3: the rejected close reports blocked:true with a non-empty explanation, carries no closedPos, and does not claim committed -- a refused close never reports success',
      !!res && res.blocked===true && typeof res.error==='string' && res.error.length>0 &&
      !res.closedPos && res.committed!==true,
      'blocked='+(res&&res.blocked)+' error='+String(res&&res.error).slice(0,44)+' closedPos='+String(res&&res.closedPos));
    assert('LCR-ROLL.4 (PERSISTENCE): a rolled-back close persists NOTHING -- the account and journal bytes in storage are byte-identical to their pre-close values',
      g.lsGet('fxhub_paper')===acctBytesBefore && g.lsGet('fxhub_journal')===journalBytesBefore,
      'account bytes '+(g.lsGet('fxhub_paper')===acctBytesBefore?'unchanged':'CHANGED')+
      ', journal bytes '+(g.lsGet('fxhub_journal')===journalBytesBefore?'unchanged':'CHANGED'));
    // FAILURE ISOLATION: the rejected attempt must not poison the trade. Once the conflict is
    // resolved (a reload picks up the newer version), the SAME position closes normally.
    g.setKnownVersion(999);
    g.freezeClock(CLOSE_MS);
    const res2=await g.closePaperPosition(pos.id,false,'Win');
    g.restoreClock();
    const acct2=g.getPaperAccount();
    assert('LCR-ROLL.5 (FAILURE ISOLATION): after the conflict is resolved the SAME position closes normally -- exactly one closed record, zero open, balance exactly 10050.00, and the journal row back at CLOSED with pnl exactly 50',
      !!res2 && !res2.blocked && acct2.balance===10050 && acct2.closedPositions.length===1 &&
      acct2.openPositions.length===0 && jrec(pos.id).length===1 && jrec(pos.id)[0].status==='CLOSED' &&
      jrec(pos.id)[0].pnl===50,
      'balance='+acct2.balance+' closed='+acct2.closedPositions.length+' journal='+String((jrec(pos.id)[0]||{}).status));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 7 — THE ATOMIC THREE-KEY COMMIT AND ITS COMPENSATING ROLLBACK
  //
  // savePaperAccountGuarded writes fxhub_paper, fxhub_paper_version and fxhub_journal as one unit
  // and, if any write throws, restores every key it had already written. There is no way to reach
  // that path offline without a storage exception, so the harness's own localStorage STUB is told
  // to throw for one key. No production code is stubbed, wrapped or patched.
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    seedClean();
    g.setPaperAccount({balance:12345.67,openPositions:[],closedPositions:[]});
    g.failSetOn(['fxhub_journal']);                     // the THIRD write of the three fails
    const r=g.savePaperAccountGuarded();
    g.clearStorageFailures();
    assert('LCR-ATOMIC.1: when the third write of the unit throws and the keys were previously ABSENT, the rollback REMOVES the two keys it had already written -- storage afterwards holds neither fxhub_paper nor fxhub_paper_version, so a save that never completed leaves nothing behind',
      g.lsGet('fxhub_paper')===null && g.lsGet('fxhub_paper_version')===null && g.lsGet('fxhub_journal')===null,
      'fxhub_paper='+String(g.lsGet('fxhub_paper')).slice(0,20)+' version='+String(g.lsGet('fxhub_paper_version')));
    assert('LCR-ATOMIC.2: that failure is reported as an ordinary, fully-rolled-back WRITE_FAILED -- ok false, integrityCompromised FALSE -- and the session version counter does not advance',
      r.ok===false && r.reason==='WRITE_FAILED' && r.integrityCompromised===false && g.getKnownVersion()===0,
      'ok='+r.ok+' reason='+r.reason+' compromised='+r.integrityCompromised+' knownVersion='+g.getKnownVersion());
  }
  {
    // POSITIVE CONTROL for LCR-ATOMIC.2's "integrityCompromised === false": the FATAL branch, where
    // the compensating write itself fails, must report true. Without this the `false` above would
    // also pass against a build that can never report the fatal state at all.
    seedClean();
    g.setPaperAccount({balance:12345.67,openPositions:[],closedPositions:[]});
    g.failSetOn(['fxhub_journal']);
    g.failRemoveOn(['fxhub_paper']);                    // ... and the rollback of key 1 fails too
    const r=g.savePaperAccountGuarded();
    g.clearStorageFailures();
    assert('LCR-ATOMIC.3 (POSITIVE CONTROL): when the compensating rollback write ITSELF fails, the result is the distinct FATAL state -- integrityCompromised true, reason ROLLBACK_FAILED, failedCommitStep fxhub_journal, and fxhub_paper named in failedRollbackKeys',
      r.ok===false && r.integrityCompromised===true && r.reason==='ROLLBACK_FAILED' &&
      r.failedCommitStep==='fxhub_journal' && (r.failedRollbackKeys||[]).indexOf('fxhub_paper')!==-1,
      'compromised='+r.integrityCompromised+' reason='+r.reason+' step='+r.failedCommitStep+' keys='+JSON.stringify(r.failedRollbackKeys));
    assert('LCR-ATOMIC.4: and that fatal case is fatal for a REASON -- the key whose rollback failed is genuinely left holding the new, uncommitted bytes, which is exactly the inconsistency the flag exists to declare',
      bal('fxhub_paper')===12345.67 && g.lsGet('fxhub_paper_version')===null,
      'fxhub_paper balance='+String(bal('fxhub_paper'))+' version='+String(g.lsGet('fxhub_paper_version')));
  }
  {
    // The OTHER rollback branch: keys that already held bytes must be RESTORED to exactly those
    // bytes, not removed. Stated as a complementary branch rather than as a second copy of
    // LCR-ATOMIC.1 -- the two exercise the two arms of the same conditional and neither subsumes
    // the other (this one does NOT die to a removeItem defect; that is LCR-ATOMIC.1's job).
    seedClean();
    g.lsSet('fxhub_paper','PRIOR_ACCOUNT_BYTES');
    g.lsSet('fxhub_paper_version','7');
    g.lsSet('fxhub_journal','PRIOR_JOURNAL_BYTES');
    g.setKnownVersion(7);
    g.setPaperAccount({balance:999.99,openPositions:[],closedPositions:[]});
    g.failSetOn(['fxhub_journal']);
    const r=g.savePaperAccountGuarded();
    g.clearStorageFailures();
    assert('LCR-ATOMIC.5: when the same failure happens over keys that ALREADY held data, the rollback restores their exact prior bytes -- fxhub_paper is "PRIOR_ACCOUNT_BYTES" again, the version is "7" again, and the untouched journal key still holds its own prior bytes',
      r.ok===false && g.lsGet('fxhub_paper')==='PRIOR_ACCOUNT_BYTES' &&
      g.lsGet('fxhub_paper_version')==='7' && g.lsGet('fxhub_journal')==='PRIOR_JOURNAL_BYTES',
      'account='+g.lsGet('fxhub_paper')+' version='+g.lsGet('fxhub_paper_version')+' journal='+g.lsGet('fxhub_journal'));
  }
  {
    // The success path of the same unit: all three keys move together, none lags a commit behind.
    seedClean();
    g.setPaperAccount({balance:10777.25,openPositions:[],closedPositions:[]});
    g.setJournalEntries([{journalEntryId:'JVMJ|555',tradeId:555,strategyId:'current_strategy',status:'OPEN'}]);
    const r=g.savePaperAccountGuarded();
    assert('LCR-ATOMIC.6: a SUCCESSFUL commit persists all three keys as one unit -- the account bytes carry balance exactly 10777.25, the journal bytes carry the one row, and the version is exactly "1"',
      r.ok===true && bal('fxhub_paper')===10777.25 &&
      (stored('fxhub_journal')||[]).length===1 && ((stored('fxhub_journal')||[])[0]||{}).tradeId===555 &&
      g.lsGet('fxhub_paper_version')==='1',
      'balance='+String(bal('fxhub_paper'))+' journalRows='+(stored('fxhub_journal')||[]).length+
      ' version='+String(g.lsGet('fxhub_paper_version')));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 8 — THE OPTIMISTIC-CONCURRENCY VERSION GUARD, BOTH HALVES AND BOTH BOUNDARIES
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    seedClean();
    g.setPaperAccount({balance:11111,openPositions:[],closedPositions:[]});
    g.lsSet('fxhub_paper_version','4');
    g.setKnownVersion(4);                               // EXACTLY equal
    const r=g.savePaperAccountGuarded();
    assert('LCR-VER.1 (BOUNDARY, equal): a stored version EXACTLY EQUAL to the one this session knows is not a conflict -- the commit succeeds and storage advances to exactly "5"',
      r.ok===true && g.lsGet('fxhub_paper_version')==='5' && g.getKnownVersion()===5,
      'ok='+r.ok+' stored='+g.lsGet('fxhub_paper_version')+' known='+g.getKnownVersion());
  }
  {
    seedClean();
    g.setPaperAccount({balance:11111,openPositions:[],closedPositions:[]});
    g.lsSet('fxhub_paper','OTHER_TAB_ACCOUNT_BYTES');
    g.lsSet('fxhub_paper_version','5');
    g.setKnownVersion(4);                               // EXACTLY one behind
    g.setPaperEngineErrors([]);
    const r=g.savePaperAccountGuarded();
    assert('LCR-VER.2 (BOUNDARY, one ahead): a stored version exactly ONE ahead is rejected as STALE_VERSION, and this session\'s version counter does not move',
      r.ok===false && r.reason==='STALE_VERSION' && r.integrityCompromised===false && g.getKnownVersion()===4,
      'ok='+r.ok+' reason='+r.reason+' known='+g.getKnownVersion());
    assert('LCR-VER.3 (CONCURRENCY): the other tab\'s newer account bytes survive byte-identical and its version is untouched -- a stale in-memory account can never overwrite a newer stored one',
      g.lsGet('fxhub_paper')==='OTHER_TAB_ACCOUNT_BYTES' && g.lsGet('fxhub_paper_version')==='5',
      'account='+g.lsGet('fxhub_paper')+' version='+g.lsGet('fxhub_paper_version'));
    // MESSAGE CONTENT, never log length -- see this file's header.
    const newest=(g.getPaperEngineErrors()||[])[0]||{};
    const msg=String(newest.message||'');
    assert('LCR-VER.4: the rejection is REPORTED rather than silent -- the newest engine-error names strategy=JVM and both versions (expectedVersion=4, persistedVersion=5). Asserted on message CONTENT, never on the log\'s length, which caps at 50 and stops discriminating.',
      msg.indexOf('strategy=JVM')!==-1 && msg.indexOf('expectedVersion=4')!==-1 && msg.indexOf('persistedVersion=5')!==-1,
      'message='+msg.slice(0,90));
  }
  {
    // The ADVANCE half of the guard. If a successful commit does not move the session's known
    // version, the session immediately becomes stale against its OWN write and the next commit is
    // rejected for a conflict that does not exist.
    seedClean();
    g.setPaperAccount({balance:10500,openPositions:[],closedPositions:[]});
    const r1=g.savePaperAccountGuarded();
    const acct=g.getPaperAccount(); acct.balance=10600; g.setPaperAccount(acct);
    const r2=g.savePaperAccountGuarded();
    assert('LCR-VER.5: two consecutive commits from the SAME session both succeed and land the version at exactly "2" -- the guard advances with this session\'s own writes instead of going stale against itself',
      r1.ok===true && r2.ok===true && g.lsGet('fxhub_paper_version')==='2' && g.getKnownVersion()===2 &&
      bal('fxhub_paper')===10600,
      'r1='+r1.ok+' r2='+r2.ok+' version='+String(g.lsGet('fxhub_paper_version'))+' persistedBalance='+String(bal('fxhub_paper')));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 9 — INC-001: A KEY WE COULD NOT READ IS NEVER A KEY WE MAY OVERWRITE
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    seedClean();
    g.lsSet('fxhub_paper','REAL_STORED_ACCOUNT');
    g.lsSet('fxhub_journal','REAL_STORED_JOURNAL');
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});   // the DEFAULT, not the real data
    g.setStorageLoadFailures({fxhub_journal:{at:'2026-05-04T09:00:00.000Z',message:'JSON parse failed'}});
    const r=g.savePaperAccountGuarded();
    assert('LCR-INC001.1 (POSITIVE CONTROL): with fxhub_journal recorded as present-but-unreadable at load, the commit is REFUSED with reason LOAD_INTEGRITY_BLOCKED and names the blocked key -- an in-memory default is never allowed over real stored data',
      r.ok===false && r.reason==='LOAD_INTEGRITY_BLOCKED' && (r.blockedKeys||[]).indexOf('fxhub_journal')!==-1,
      'ok='+r.ok+' reason='+r.reason+' blocked='+JSON.stringify(r.blockedKeys));
    assert('LCR-INC001.2: and NOTHING is written -- the real stored account and journal bytes are still exactly what they were, and no version key was created',
      g.lsGet('fxhub_paper')==='REAL_STORED_ACCOUNT' && g.lsGet('fxhub_journal')==='REAL_STORED_JOURNAL' &&
      g.lsGet('fxhub_paper_version')===null,
      'account='+g.lsGet('fxhub_paper')+' journal='+g.lsGet('fxhub_journal')+' version='+String(g.lsGet('fxhub_paper_version')));
    // NEGATIVE CONTROL: clearing the register must let the very same commit through, so the block
    // above is genuinely caused by the unreadable key and not by something permanently refusing.
    g.setStorageLoadFailures({});
    const r2=g.savePaperAccountGuarded();
    assert('LCR-INC001.3 (NEGATIVE CONTROL): with no unreadable key recorded the identical commit succeeds and writes the account -- the block is caused by the load failure, not by a permanently closed gate',
      r2.ok===true && bal('fxhub_paper')===10000 && g.lsGet('fxhub_paper_version')==='1',
      'ok='+r2.ok+' persistedBalance='+String(bal('fxhub_paper'))+' version='+String(g.lsGet('fxhub_paper_version')));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 10 — CONCURRENCY: TWO CLOSES RACING ON ONE ID
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    seedClean();
    g.freezeClock(OPEN_MS);
    const pos=g.openPaperPosition(PAIR,'buy',1.3000,1.2900,1.3200,'manual');
    g.setPairData(PAIR,1.3050);
    g.freezeClock(CLOSE_MS);
    const a=g.closePaperPosition(pos.id,false,'Win');
    const b=g.closePaperPosition(pos.id,false,'Win');
    await Promise.all([a,b]);
    g.restoreClock();
    const acct=g.getPaperAccount();
    assert('LCR-CONC.1 (CONCURRENCY): two closes fired for the SAME id, both awaited, produce exactly ONE closed record, zero open positions, and a balance of exactly 10050.00 -- the P&L is applied once. The balance is a hand-computed literal, deliberately not balanceBefore+closedPos.pnl, which is blind to both sides being wrong together.',
      acct.closedPositions.filter(p=>p.id===pos.id).length===1 && acct.closedPositions.length===1 &&
      acct.openPositions.length===0 && acct.balance===10050,
      'closed='+acct.closedPositions.length+' open='+acct.openPositions.length+' balance='+acct.balance);
    const rows=jrec(pos.id);
    assert('LCR-CONC.2: and exactly ONE journal row exists for the trade, at CLOSED with pnl exactly 50 -- one close, one journal closure',
      rows.length===1 && rows[0].status==='CLOSED' && rows[0].pnl===50,
      'rows='+rows.length+' status='+(rows[0]||{}).status+' pnl='+(rows[0]||{}).pnl);
    const ci=g.computePaperLedgerIntegrity();
    assert('LCR-CONC.3: the racing close leaves no duplicate anywhere -- no duplicate account id, no duplicate journal tradeId, and the balance still reconciles to exactly 0 difference',
      ci.duplicateAccountIds.length===0 && ci.duplicateJournalTradeIds.length===0 && ci.balanceDifference===0,
      'dupAcct='+ci.duplicateAccountIds.length+' dupJournal='+ci.duplicateJournalTradeIds.length+' diff='+ci.balanceDifference);
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 11 — FAILURE ISOLATION BETWEEN THE THREE STORES
  // One corrupt store must not switch the other detectors off.
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    // Corrupt JOURNAL, healthy account: the balance arithmetic must still be exactly right.
    const rows=g.getJournalEntries()||[];
    g.setJournalEntries(rows.length?rows.concat([JSON.parse(JSON.stringify(rows[0]))]):rows);
    const iso=g.computePaperLedgerIntegrity();
    assert('LCR-ISO.1 (FAILURE ISOLATION): a duplicated journal row is reported in duplicateJournalTradeIds while the money arithmetic keeps working exactly -- expectedBalance 10050, difference 0. A corrupt journal does not disable the balance check.',
      iso.duplicateJournalTradeIds.length===1 && iso.expectedBalance===10050 && iso.balanceDifference===0,
      'dupJournal='+JSON.stringify(iso.duplicateJournalTradeIds)+' expected='+iso.expectedBalance+' diff='+iso.balanceDifference);
  }
  {
    // Corrupt ACCOUNT balance plus an unrelated orphan: orphan detection must still work.
    const acct=g.getPaperAccount(); acct.balance=10125; g.setPaperAccount(acct);
    g.setJournalEntries([(g.getJournalEntries()||[])[0]||{tradeId:null},
      {journalEntryId:'JVMJ|8888',tradeId:8888,strategy:'current_strategy',strategyId:'current_strategy',
       strategyLabel:'JVM',isDeveloperTrade:false,pair:'GBP/USD',direction:'buy',entry:1.3,stop:1.29,target:1.32,
       riskAmount:100,positionSize:0.1,openedAt:'2026-05-04T09:00:00.000Z',closedAt:'2026-05-04T10:00:00.000Z',
       status:'CLOSED',result:'Win',resultR:0.4,pnl:40,exitPrice:1.304}]);
    const iso=g.computePaperLedgerIntegrity();
    assert('LCR-ISO.2 (FAILURE ISOLATION): with the balance 75 dollars wrong, orphan detection still fires -- the journal row with no account position is reported -- AND the balance difference is still the exact 75.00. Neither check silences the other.',
      iso.journalWithNoAccountMatch.length===1 && String(iso.journalWithNoAccountMatch[0].tradeId)==='8888' &&
      iso.balanceDifference===75 && iso.expectedBalance===10050,
      'orphans='+iso.journalWithNoAccountMatch.length+' diff='+iso.balanceDifference);
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 12 — THE IMMUTABLE LEDGER: DERIVE, THEN RECONCILE AGAINST THE STORED TOTAL
  //
  // Hand-computed equity curve over three closed trades from a $10,000 start:
  //   +200 -> 10,200 (new peak)   -350 -> 9,850 (drawdown 350)   +100 -> 9,950 (drawdown 250)
  // So: derived balance 9,950.00; realized P&L -50.00; MAX drawdown 350.00 -- which is neither 0
  // nor the 50.00 net change, so a drawdown that never grows and a drawdown read off the final
  // balance are both distinguishable from the right answer.
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    const rec=(id,pnl,result,closedAt,dev)=>({id:id,oPair:'GBP_USD',pair:'GBP/USD',dir:'buy',entry:1.3,stop:1.29,
      target:1.32,riskAmount:100,lots:0.1,pnl:pnl,result:result,resultR:pnl/100,exitPrice:1.305,
      openedAt:'2026-05-04T08:00:00.000Z',closedAt:closedAt,isDeveloperTrade:!!dev});
    const three=[rec(701,200,'Win','2026-05-04T10:00:00.000Z'),
                 rec(702,-350,'Loss','2026-05-04T11:00:00.000Z'),
                 rec(703,100,'Win','2026-05-04T12:00:00.000Z')];
    const derived=g.ledgerDeriveAccountState({records:three,strategyId:'current_strategy',startingBalance:10000});
    assert('LCR-LEDG.0 (PRECONDITION): all three fixture trades enter the ledger as verified events -- 3 total, 3 included, 0 quarantined, 0 excluded. Every figure below assumes exactly this.',
      derived.eventCounts.total===3 && derived.eventCounts.included===3 &&
      derived.eventCounts.quarantined===0 && derived.eventCounts.excluded===0,
      JSON.stringify(derived.eventCounts));
    assert('LCR-LEDG.1: the account rebuilt from starting balance + ledger alone lands on exactly 9950.00 with realized P&L of exactly -50.00 -- derived from the events, with no stored total consulted',
      derived.balance===9950 && derived.realizedPnl===-50,
      'balance='+derived.balance+' realized='+derived.realizedPnl);
    assert('LCR-LEDG.2: max drawdown is the peak-to-trough excursion of exactly 350.00 -- not 0 (a drawdown that never grows) and not the 50.00 net change (a drawdown read off the endpoints)',
      derived.maxDrawdownMoney===350,'maxDrawdownMoney='+derived.maxDrawdownMoney);
    assert('LCR-LEDG.3 (NEGATIVE CONTROL): a stored total of exactly 9950.00 reconciles as MATCHES with a delta of exactly 0 -- the reconciler is silent when there is nothing to report',
      (function(){const r=g.ledgerReconcileBalance(9950,derived);return r.status==='MATCHES'&&r.delta===0&&r.unexplainedDelta===0;})(),
      JSON.stringify(g.ledgerReconcileBalance(9950,derived)).slice(0,120));
    assert('LCR-LEDG.4 (POSITIVE CONTROL): a stored total of 10025.00 against the same ledger is UNEXPLAINED_DELTA with delta exactly 75.00 and unexplainedDelta exactly 75.00 -- the stored total moved for a reason the ledger cannot account for',
      (function(){const r=g.ledgerReconcileBalance(10025,derived);return r.status==='UNEXPLAINED_DELTA'&&r.delta===75&&r.unexplainedDelta===75;})(),
      JSON.stringify(g.ledgerReconcileBalance(10025,derived)).slice(0,120));
    // The exclusion arm: an excluded record's P&L must EXPLAIN a divergence rather than be silently
    // folded into the derived balance.
    const withDev=three.concat([rec(704,500,'Win','2026-05-04T13:00:00.000Z',true)]);
    const derived2=g.ledgerDeriveAccountState({records:withDev,strategyId:'current_strategy',startingBalance:10000});
    assert('LCR-LEDG.5: adding a +500 developer trade does NOT move the derived balance -- it stays exactly 9950.00 with the event recorded as excluded and preserved, never deleted',
      derived2.balance===9950 && derived2.eventCounts.excluded===1 && derived2.eventCounts.included===3 &&
      (derived2.excludedEvents||[]).length===1 && derived2.excludedEvents[0].pnl===500,
      'balance='+derived2.balance+' excluded='+derived2.eventCounts.excluded);
    assert('LCR-LEDG.6: and a stored total of 10450.00 -- exactly the derived 9950 plus that excluded 500 -- reconciles as EXPLAINED_BY_EXCLUSIONS with excludedPnl exactly 500.00 and unexplainedDelta exactly 0',
      (function(){const r=g.ledgerReconcileBalance(10450,derived2);
        return r.status==='EXPLAINED_BY_EXCLUSIONS'&&r.delta===500&&r.excludedPnl===500&&r.unexplainedDelta===0;})(),
      JSON.stringify(g.ledgerReconcileBalance(10450,derived2)).slice(0,140));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP 13 — RECONCILIATION APPLY: DURABILITY OF THE RESTORE
  // The preview/apply selection rules, the ambiguity guards and the double-credit defences are
  // already covered by run_v1235_reconciliation_tests.js and are NOT re-asserted here. What that
  // suite never checks is whether a restore actually reaches STORAGE -- it reads only the
  // in-memory account. These two fixtures cover exactly that gap and nothing else.
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    seedClean();
    const orphan={tradeId:'ORPH-1',journalEntryId:'JVMJ|ORPH-1',strategy:'current_strategy',strategyId:'current_strategy',
      strategyLabel:'JVM',isDeveloperTrade:false,pair:'GBP/USD',direction:'buy',entry:1.3,stop:1.29,target:1.32,
      riskAmount:100,positionSize:0.1,openedAt:'2026-05-04T08:00:00.000Z',closedAt:'2026-05-04T10:00:00.000Z',
      status:'CLOSED',result:'Win',resultR:1.25,pnl:125,exitPrice:1.3125};
    g.setJournalEntries([orphan]);
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    const pre=g.computeReconciliationPreview(['ORPH-1']);
    assert('LCR-RECON.0 (PRECONDITION): the fixture record is an unexplained orphan the preview will restore, projecting exactly 10125.00 from 10000.00 plus its stored 125.00',
      pre.items.length===1 && pre.currentBalance===10000 && pre.projectedBalance===10125,
      'items='+pre.items.length+' projected='+pre.projectedBalance);
    const out=g.applyPaperReconciliation(['ORPH-1']);
    const storedAcct=stored('fxhub_paper');
    assert('LCR-RECON.1 (PERSISTENCE): the restore reaches STORAGE, not just memory -- the persisted account bytes carry balance exactly 10125.00 and the restored trade as one closed position with pnl exactly 125',
      out.applied.length===1 && !!storedAcct && storedAcct.balance===10125 &&
      storedAcct.closedPositions.length===1 && storedAcct.closedPositions[0].id==='ORPH-1' &&
      storedAcct.closedPositions[0].pnl===125,
      storedAcct?('persistedBalance='+storedAcct.balance+' closed='+storedAcct.closedPositions.length):'nothing persisted');
    assert('LCR-RECON.2: the restore went through the same guarded ledger commit as a real trade -- the version advanced to exactly "1" and the session counter agrees',
      g.lsGet('fxhub_paper_version')==='1' && g.getKnownVersion()===1,
      'version='+g.lsGet('fxhub_paper_version')+' known='+g.getKnownVersion());
  }

  return results;
}
