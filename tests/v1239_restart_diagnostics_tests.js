// ══════════════════════════════════════════════════════════════════════════════════════════
// v12.3.9 RESTART / RECOVERY and DIAGNOSTICS / OBSERVABILITY
// ══════════════════════════════════════════════════════════════════════════════════════════
// Closes a measured mutation-coverage gap. This area was accepted on pre-mutation-era evidence
// and had never been mutation-tested. A 25-mutation sweep scored against the whole 32-suite gate
// found SIX behaviour-changing mutations that killed ZERO fixtures anywhere in the repository:
//
//   R12  the ALEX account key is read and JSON.parse'd by loadAlexGSaved() but never APPLIED --
//        after a restart the operator's real ALEX ledger is silently the empty default.
//   R13  loadSaved() RESURRECTS closed positions into openPositions -- a restart re-opens every
//        trade the engine already closed.
//   D01  recordPaperEngineError() keeps the OLDEST 50 instead of the newest (push vs unshift) --
//        once the log saturates every NEW error is discarded while the LENGTH stays exactly 50,
//        so a length-based fixture is blind in precisely the condition it exists to catch.
//   D02  the same, on the ALEX arm.
//   D03  the cap is off by one at its own boundary (50 -> 49).
//   D15  savePaperAccountGuarded()'s LOAD_INTEGRITY_BLOCKED refusal -- the INC-001 protection --
//        is never recorded to the engine-error channel, so the block happens invisibly.
//
// Every fixture below exists to kill one or more of those survivors, or to supply the control
// that makes the kill mean something.
//
// EVIDENCE STANDARD APPLIED HERE:
//   * Nothing asserts against source text, and nothing is self-consistent -- no assertion
//     compares two outputs of the same computation.
//   * Every expected value is a FIXTURE-CHOSEN LITERAL computed by hand from the fixture's own
//     inputs, never re-derived with the expression production uses.
//   * The restore fixtures drive the REAL loadSaved()/loadAlexGSaved(). None of them calls
//     loadStoredKey() directly: proving the per-key helper works proves nothing about the
//     loader REACHING it, and that exact defect has already been found in this repository.
//   * The engine-error fixtures compare CONTENT, never LENGTH alone. The log caps at 50 via
//     unshift+slice, so at saturation the length stops moving and a length assertion passes
//     against a log that is dropping every real error.
//   * The close in the restart group is genuinely AWAITED. closePaperPosition() is `async`; a
//     fixture that called it without awaiting would assert on pre-close state and pass against
//     an entirely broken close path -- a proven false-green here.
//
// ISOLATION: in-memory only, stubbed localStorage, stubbed fetch, no real browser storage and no
// network. No real paper trade can be persisted from this process.
async function runV1239RestartDiagnosticsFixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,method:'execution',detail:detail||''});};
  const PAIR='GBP_USD';

  function seedClean(){
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGJournalEntries([]);
    g.setAlexGSetupState([]);
    g.setAlexGZoneState({});
    g.setPaperEngineErrors([]);
    g.setAlexGEngineErrors([]);
    g.setPaperLifecycleLog([]);
    g.setPaperReconciliationAudit([]);
    g.setPairData(PAIR,null);
    g.setPaperAccountKnownVersion(0);
    g.setAlexGAccountKnownVersion(0);
    g.resetPaperPositionsClosing();
    g.resetLoadFailures();
    g.setDeveloperMode(false);
    g.clearLocalStorage();
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP A — SIMULATED RESTART, THROUGH THE REAL ENGINE AND THE REAL LOADER
  //
  // Hand-computed expectations for the one trade this group opens and closes:
  //   balance 10000 -> riskAmount = 1% = $100
  //   GBP_USD buy, entry 1.3000, stop 1.2900 -> riskPips = 100
  //   USD quote -> pipValuePerLot = 0.0001 * 100000 = $10 per pip per lot
  //   lots = 100 / (100 * 10) = 0.10
  //   manual close, no live bid/ask (fetch is stubbed to reject) -> fill at the shared mid
  //     price 1.3050 -> +50.0 pips -> pnl = 50 * 10 * 0.10 = +$50.00
  //   balance after the close = 10000 + 50 = $10050.00
  //   realized R = 50 / 100 = +0.50 -> well outside the break-even epsilon -> "Win"
  // Not one of those numbers is read back from the app.
  // ══════════════════════════════════════════════════════════════════════════════════════
  const OPEN_MS=Date.parse('2026-03-01T10:00:00.000Z');
  const CLOSE_MS=OPEN_MS+5400000;            // +90 minutes
  let restart=null;
  {
    seedClean();
    g.setPairData(PAIR,1.3050);
    g.freezeClock(OPEN_MS);
    const pos=g.openPaperPosition(PAIR,'buy',1.3000,1.2900,1.3200,'manual');
    g.freezeClock(CLOSE_MS);
    // AWAITED. Everything asserted below is produced after closePaperPosition()'s one internal
    // `await fetchBidAsk(...)`; without this await the fixture would read pre-close state.
    const closeRes=await g.closePaperPosition(pos&&pos.id,true,null);
    g.restoreClock();
    const persistedAccount=g.getLocalStorageItem('fxhub_paper');
    const persistedJournal=g.getLocalStorageItem('fxhub_journal');
    // ── THE RESTART: every in-memory store is discarded, exactly as a page reload does, and
    //    the state is re-read through the REAL loadSaved() over the REAL persisted bytes. ──
    g.setPaperAccount({balance:0,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setPaperReconciliationAudit([]);
    g.setPaperAccountKnownVersion(0);
    g.resetLoadFailures();
    g.loadSaved();
    const acc=g.getPaperAccount();
    const cp=(acc.closedPositions||[])[0]||null;
    restart={pos,closeRes,acc,cp,persistedAccount,persistedJournal};

    assert('RSTDG-RESTART.1 (PERSISTENCE, POSITIVE): a trade opened and CLOSED through the real engine is recovered EXACTLY by the real loadSaved() after every in-memory store is discarded -- balance $10050.00, exactly one closed position carrying the same trade id, exit 1.3050, P&L +$50.00, result "Win"',
      !!cp && acc.balance===10050 && (acc.closedPositions||[]).length===1 &&
      cp.id===(pos&&pos.id) && cp.exitPrice===1.3050 && Math.abs(cp.pnl-50)<0.000001 && cp.result==='Win',
      JSON.stringify({balance:acc.balance,closed:(acc.closedPositions||[]).length,
        id:cp&&cp.id,exit:cp&&cp.exitPrice,pnl:cp&&cp.pnl,result:cp&&cp.result,closeRes:!!closeRes}));

    // The anti-resurrection claim, stated separately because it is a different property from
    // "the closed record came back correctly": a restart must not re-open a finished trade.
    const openIds=(acc.openPositions||[]).map(p=>p.id);
    assert('RSTDG-RESTART.2 (MUST NOT COME BACK): the restart does NOT resurrect the closed position -- openPositions is empty and the closed trade id appears in NO open row',
      (acc.openPositions||[]).length===0 && openIds.indexOf(pos&&pos.id)===-1,
      'openIds='+JSON.stringify(openIds));

    const jrec=(g.getJournalEntries()||[]).filter(e=>e.tradeId===(pos&&pos.id));
    assert('RSTDG-RESTART.3 (PERSISTENCE): the restart recovers exactly ONE journal record for that trade and it is CLOSED -- not zero, not duplicated, not left OPEN',
      jrec.length===1 && jrec[0].status==='CLOSED',
      'count='+jrec.length+' status='+(jrec[0]&&jrec[0].status));
  }

  {
    // MEMORY-ONLY DIAGNOSTICS STATE MUST NOT SURVIVE A RESTART -- and must never have been
    // written to storage in the first place.
    seedClean();
    const SENTINEL='RSTDG-MEMONLY-SENTINEL-8321';
    g.recordPaperEngineError(SENTINEL);
    // 🔴 §18.21 PRECONDITION. Without this the assertion below is a must-not-contain with NO
    // positive precondition -- the ELEVENTH instance of the pattern this milestone keeps finding,
    // and the second in a security-shaped assertion. Independent verification proved it: making
    // recordPaperEngineError a no-op, so the log is ALWAYS empty, kills 13 fixtures gate-wide and
    // leaves RESTART.4 green. "The sentinel never leaked" means nothing if the sentinel was never
    // recorded in the first place.
    const recordedBefore=g.getPaperEngineErrors().filter(function(e){
      return String(e&&e.message||e).indexOf(SENTINEL)!==-1; }).length;
    g.commitPaperLedger();                       // persists everything that IS persistable
    const leaked=g.storageKeys().filter(k=>String(g.rawStorage()[k]||'').indexOf(SENTINEL)!==-1);
    g.setPaperEngineErrors([]);
    g.setPaperLifecycleLog([]);
    g.setPaperAccount({balance:0,openPositions:[],closedPositions:[]});
    g.resetLoadFailures();
    g.loadSaved();
    assert('RSTDG-RESTART.4a (PRECONDITION): the sentinel error really was recorded before the restart, so the must-not-leak assertion below is applied to a log that actually contained it',
      recordedBefore===1,'recorded='+recordedBefore);
    assert('RSTDG-RESTART.4 (MUST NOT COME BACK): the engine-error log is session-scoped -- a recorded error is never written to any storage key and is not resurrected by loadSaved()',
      leaked.length===0 && g.getPaperEngineErrors().length===0 && g.getPaperLifecycleLog().length===0,
      'recordedBefore='+recordedBefore+' leakedKeys='+JSON.stringify(leaked)+' errors='+g.getPaperEngineErrors().length);
  }

  {
    // ALEX ARM — the store is read and parsed; this proves it is also APPLIED. Driven through
    // the REAL loadAlexGSaved(), never through loadStoredKey().
    seedClean();
    g.setLocalStorageItem('fxhub_alexg_account',JSON.stringify({
      balance:10420.5,startingBalance:10000,
      openPositions:[{tradeId:'AGT|RSTDG-OPEN-1',pair:'EUR_USD',direction:'buy',entry:1.0800}],
      closedPositions:[{tradeId:'AGT|RSTDG-CLOSED-1',pair:'EUR_USD',pnl:420.5,result:'Win'}]}));
    g.setLocalStorageItem('fxhub_alexg_journal',JSON.stringify([
      {journalEntryId:'ALEXJ|RSTDG-1',tradeId:'AGT|RSTDG-OPEN-1',status:'OPEN'},
      {journalEntryId:'ALEXJ|RSTDG-2',tradeId:'AGT|RSTDG-CLOSED-1',status:'CLOSED',pnl:420.5}]));
    // Wipe to a value that could never be mistaken for the stored one.
    g.setAlexGAccount({balance:-1,openPositions:[],closedPositions:[]});
    g.setAlexGJournalEntries([]);
    g.resetLoadFailures();
    g.loadAlexGSaved();
    const a=g.getAlexGAccount();
    assert('RSTDG-ALEXLOAD.1 (PERSISTENCE, POSITIVE): loadAlexGSaved() APPLIES the stored ALEX account, it does not merely read it -- balance $10420.50, one open position AGT|RSTDG-OPEN-1, one closed position AGT|RSTDG-CLOSED-1 with P&L +$420.50',
      a.balance===10420.5 && (a.openPositions||[]).length===1 && (a.closedPositions||[]).length===1 &&
      a.openPositions[0].tradeId==='AGT|RSTDG-OPEN-1' && a.closedPositions[0].tradeId==='AGT|RSTDG-CLOSED-1' &&
      a.closedPositions[0].pnl===420.5,
      JSON.stringify({balance:a.balance,open:(a.openPositions||[]).length,closed:(a.closedPositions||[]).length}));

    const j=g.getAlexGJournalEntries();
    assert('RSTDG-ALEXLOAD.2 (PERSISTENCE, POSITIVE): loadAlexGSaved() APPLIES the stored ALEX journal -- both records come back with their exact journalEntryIds and the closed one keeps status CLOSED',
      j.length===2 && j[0].journalEntryId==='ALEXJ|RSTDG-1' && j[1].journalEntryId==='ALEXJ|RSTDG-2' &&
      j[1].status==='CLOSED',
      'count='+j.length);
  }

  {
    // FAILURE ISOLATION — one unparseable key must not stop the others loading, and must never
    // be overwritten. The corrupt key here is the ACCOUNT and the surviving key is the JOURNAL.
    seedClean();
    const CORRUPT='{CORRUPT BUT REAL ALEX ACCOUNT BYTES';
    g.setLocalStorageItem('fxhub_alexg_account',CORRUPT);
    g.setLocalStorageItem('fxhub_alexg_journal',JSON.stringify([
      {journalEntryId:'ALEXJ|ISO-1',tradeId:'AGT|ISO-1'},
      {journalEntryId:'ALEXJ|ISO-2',tradeId:'AGT|ISO-2'},
      {journalEntryId:'ALEXJ|ISO-3',tradeId:'AGT|ISO-3'}]));
    g.setLocalStorageItem('fxhub_alexg_setups',JSON.stringify([{setupId:'AGS|ISO-1'},{setupId:'AGS|ISO-2'}]));
    g.setAlexGJournalEntries([]);
    g.setAlexGSetupState([]);
    g.resetLoadFailures();
    g.loadAlexGSaved();
    const j=g.getAlexGJournalEntries(),s=g.getAlexGSetupState();
    assert('RSTDG-ISOLATION.1 (FAILURE ISOLATION): an unparseable fxhub_alexg_account does not suppress the keys loaded AFTER it -- all 3 journal records and both setups still load, by id',
      j.length===3 && j[2].journalEntryId==='ALEXJ|ISO-3' && s.length===2 && s[1].setupId==='AGS|ISO-2',
      'journal='+j.length+' setups='+s.length);

    assert('RSTDG-ISOLATION.2 (FAILURE ISOLATION): the unreadable key is recorded and becomes unwritable, while the keys that loaded cleanly stay writable',
      g.storageKeyBlockedFromWrite('fxhub_alexg_account')===true &&
      g.storageKeyBlockedFromWrite('fxhub_alexg_journal')===false &&
      g.storageKeyBlockedFromWrite('fxhub_alexg_setups')===false,
      JSON.stringify(g.storageLoadFailureKeys()));

    // The INC-001 overwrite itself: an in-memory default must never be written over real bytes.
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    const commit=g.saveAlexGAccountGuarded();
    assert('RSTDG-ISOLATION.3 (FAILURE ISOLATION / INC-001): the guarded ALEX commit is REFUSED with LOAD_INTEGRITY_BLOCKED and the corrupt-but-real stored bytes are byte-identical afterwards -- refusing to write is not an integrity compromise',
      commit && commit.ok===false && commit.reason==='LOAD_INTEGRITY_BLOCKED' &&
      commit.integrityCompromised===false && g.rawStorage().fxhub_alexg_account===CORRUPT,
      JSON.stringify({reason:commit&&commit.reason,stored:g.rawStorage().fxhub_alexg_account}));
  }

  {
    // NEGATIVE CONTROL for the whole load-integrity mechanism: an ABSENT key is not a failure.
    // A guard that cannot tell "missing" from "unreadable" bricks every fresh install.
    seedClean();                                  // storage completely empty
    g.loadSaved();
    g.loadAlexGSaved();
    assert('RSTDG-ISOLATION.4 (NEGATIVE CONTROL): with storage entirely EMPTY nothing is recorded as a load failure and no key is blocked -- an absent key is the fresh-install case, not a corruption, and a fresh install must still be able to write',
      g.storageLoadFailureKeys().length===0 &&
      g.storageKeyBlockedFromWrite('fxhub_paper')===false &&
      g.storageKeyBlockedFromWrite('fxhub_alexg_account')===false &&
      g.savePaperAccountGuarded().ok===true,
      JSON.stringify(g.storageLoadFailureKeys()));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP B — SESSION-VERSION SYNC AT LOAD (boundary: exactly equal vs exactly one ahead)
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    seedClean();
    const REAL_ACCOUNT=JSON.stringify({balance:10777,openPositions:[],closedPositions:[]});
    g.setLocalStorageItem('fxhub_paper',REAL_ACCOUNT);
    g.setLocalStorageItem('fxhub_paper_version','4');
    g.setPaperAccountKnownVersion(0);
    g.resetLoadFailures();
    g.loadSaved();
    assert('RSTDG-VERSION.1 (BOUNDARY, EQUAL): loadSaved() syncs this session to the persisted version -- a stored version of 4 leaves the session knowing 4, not 0',
      g.getPaperAccountKnownVersion()===4,'known='+g.getPaperAccountKnownVersion());

    const ok=g.savePaperAccountGuarded();
    assert('RSTDG-VERSION.2 (BOUNDARY, EQUAL — NOT A FREEZE): with the session version exactly EQUAL to the persisted one the next commit is ALLOWED and advances the stored version to exactly 5',
      ok && ok.ok===true && g.getLocalStorageItem('fxhub_paper_version')==='5',
      JSON.stringify({ok:ok&&ok.ok,version:g.getLocalStorageItem('fxhub_paper_version')}));
  }
  {
    seedClean();
    const REAL_ACCOUNT=JSON.stringify({balance:10777,openPositions:[],closedPositions:[]});
    g.setLocalStorageItem('fxhub_paper',REAL_ACCOUNT);
    g.setLocalStorageItem('fxhub_paper_version','4');
    g.setPaperAccountKnownVersion(0);
    g.resetLoadFailures();
    g.loadSaved();
    // Another tab commits exactly ONE version ahead of what this session loaded.
    g.setLocalStorageItem('fxhub_paper_version','5');
    g.setPaperAccount({balance:1,openPositions:[],closedPositions:[]});   // this session's stale copy
    const r=g.savePaperAccountGuarded();
    assert('RSTDG-VERSION.3 (BOUNDARY, ONE AHEAD): a persisted version exactly ONE ahead of the loaded session version is REFUSED as STALE_VERSION and the stored account bytes are untouched -- a session that loaded one version too high would overwrite the other tab here',
      r && r.ok===false && r.reason==='STALE_VERSION' && g.rawStorage().fxhub_paper===REAL_ACCOUNT,
      JSON.stringify({reason:r&&r.reason,stored:g.rawStorage().fxhub_paper===REAL_ACCOUNT}));
  }
  {
    seedClean();
    const REAL_ALEX=JSON.stringify({balance:10555,openPositions:[],closedPositions:[]});
    g.setLocalStorageItem('fxhub_alexg_account',REAL_ALEX);
    g.setLocalStorageItem('fxhub_alexg_account_version','9');
    g.setAlexGAccountKnownVersion(0);
    g.resetLoadFailures();
    g.loadAlexGSaved();
    const synced=g.getAlexGAccountKnownVersion();
    g.setLocalStorageItem('fxhub_alexg_account_version','10');            // another tab, one ahead
    g.setAlexGAccount({balance:1,openPositions:[],closedPositions:[]});
    const r=g.saveAlexGAccountGuarded();
    assert('RSTDG-VERSION.4 (BOUNDARY, ALEX ARM): loadAlexGSaved() syncs the session to 9, and a persisted 10 -- exactly one ahead -- is then refused as STALE_VERSION with the stored ALEX bytes untouched',
      synced===9 && r && r.ok===false && r.reason==='STALE_VERSION' && g.rawStorage().fxhub_alexg_account===REAL_ALEX,
      JSON.stringify({synced,reason:r&&r.reason}));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP C — THE ENGINE-ERROR LOG: CONTENT, NEVER LENGTH
  //
  // recordPaperEngineError()/recordAlexGEngineError() cap at 50 via unshift + slice(0,50).
  // Once saturated the LENGTH stops changing, so a length assertion passes against a log that
  // is silently discarding every new error. Each fixture below names the exact messages it
  // expects to survive and the exact ones it expects to have been evicted.
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    seedClean();
    for(let i=1;i<=50;i++) g.recordPaperEngineError('RSTDG-E-'+i);
    const e=g.getPaperEngineErrors();
    const msgs=e.map(x=>x.message);
    assert('RSTDG-ERRLOG.1 (BOUNDARY, EXACTLY AT THE CAP): exactly 50 recorded errors are all retained -- the log holds 50 entries, the newest ("RSTDG-E-50") is first, and the very first one ("RSTDG-E-1") is still present at the end',
      e.length===50 && msgs[0]==='RSTDG-E-50' && msgs[49]==='RSTDG-E-1' && msgs.indexOf('RSTDG-E-1')===49,
      'len='+e.length+' first='+msgs[0]+' last='+msgs[49]);
  }
  {
    seedClean();
    for(let i=1;i<=60;i++) g.recordPaperEngineError('RSTDG-E-'+i);
    const msgs=g.getPaperEngineErrors().map(x=>x.message);
    assert('RSTDG-ERRLOG.2 (SATURATION, CONTENT NOT LENGTH): after 60 errors the log still holds 50 -- but the 50 it holds are the NEWEST: "RSTDG-E-60" is first, "RSTDG-E-11" is last, and "RSTDG-E-1" through "RSTDG-E-10" have been evicted. The length alone is identical to a log that kept the oldest 50 and threw every new error away',
      msgs.length===50 && msgs[0]==='RSTDG-E-60' && msgs[49]==='RSTDG-E-11' &&
      msgs.indexOf('RSTDG-E-1')===-1 && msgs.indexOf('RSTDG-E-10')===-1,
      'len='+msgs.length+' first='+msgs[0]+' last='+msgs[49]);
  }
  {
    // The operational form of the same claim, on a message no filler shares: at saturation a
    // brand-new failure must still reach the operator.
    seedClean();
    for(let i=1;i<=60;i++) g.recordPaperEngineError('RSTDG-FILLER-'+i);
    g.recordPaperEngineError('RSTDG-CRITICAL-JUST-HAPPENED');
    const msgs=g.getPaperEngineErrors().map(x=>x.message);
    assert('RSTDG-ERRLOG.3 (SATURATION, OPERATOR-VISIBLE): a NEW error recorded against an already-saturated log is present and is the first entry -- a saturated log that silently discards new failures would leave the operator reading only history',
      msgs.indexOf('RSTDG-CRITICAL-JUST-HAPPENED')===0 && msgs.length===50,
      'idx='+msgs.indexOf('RSTDG-CRITICAL-JUST-HAPPENED')+' len='+msgs.length);
  }
  {
    seedClean();
    for(let i=1;i<=60;i++) g.recordAlexGEngineError('RSTDG-A-'+i);
    const msgs=g.getAlexGEngineErrors().map(x=>x.message);
    assert('RSTDG-ERRLOG.4 (ALEX ARM, SATURATION, CONTENT): the ALEX engine-error log caps at the newest 50 exactly as the JVM one does -- "RSTDG-A-60" first, "RSTDG-A-11" last, "RSTDG-A-1" evicted',
      msgs.length===50 && msgs[0]==='RSTDG-A-60' && msgs[49]==='RSTDG-A-11' && msgs.indexOf('RSTDG-A-1')===-1,
      'len='+msgs.length+' first='+msgs[0]+' last='+msgs[49]);
  }
  {
    seedClean();
    for(let i=1;i<=50;i++) g.recordAlexGEngineError('RSTDG-A2-'+i);
    const msgs=g.getAlexGEngineErrors().map(x=>x.message);
    assert('RSTDG-ERRLOG.5 (ALEX ARM, BOUNDARY AT THE CAP): exactly 50 ALEX errors are all retained, newest first, with "RSTDG-A2-1" still present at the end',
      msgs.length===50 && msgs[0]==='RSTDG-A2-50' && msgs[49]==='RSTDG-A2-1',
      'len='+msgs.length+' first='+msgs[0]);
  }
  {
    // SHAPE CONTROL for the whole group: one call produces exactly ONE entry, carrying that
    // exact message AND a non-empty ISO timestamp. Every fixture above reads only .message, so
    // a recorder that dropped the timestamp -- which the Diagnostics card formats with
    // new Date(e.at) -- would sail through all five of them.
    seedClean();
    g.recordPaperEngineError('RSTDG-SHAPE-ONE');
    const one=g.getPaperEngineErrors();
    assert('RSTDG-ERRLOG.6 (SHAPE CONTROL): a single recorded error produces exactly ONE entry, with that exact message and a non-empty ISO-8601 timestamp -- the entry is not duplicated, not truncated, and not left undated for the surface that formats it',
      one.length===1 && one[0].message==='RSTDG-SHAPE-ONE' &&
      typeof one[0].at==='string' && !Number.isNaN(Date.parse(one[0].at)),
      'len='+one.length+' at='+(one[0]&&one[0].at));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP D — THE INC-001 BLOCK MUST BE REPORTED, NOT JUST PERFORMED
  //
  // A refusal the operator cannot see is a frozen ledger with no explanation. END-TO-END: a
  // defect seeded in STORAGE is detected at load, blocks the commit, AND is reported.
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    seedClean();
    const CORRUPT='{CORRUPT BUT REAL JVM LEDGER BYTES';
    g.setLocalStorageItem('fxhub_paper',CORRUPT);
    g.setLocalStorageItem('fxhub_paper_version','3');
    g.setLocalStorageItem('fxhub_journal',JSON.stringify([{journalEntryId:'JVMJ|RSTDG-1',tradeId:'RSTDG-1'}]));
    g.resetLoadFailures();
    g.loadSaved();
    const journalLoaded=(g.getJournalEntries()||[]).length;
    // Isolate: recordStorageLoadFailure() already reported the READ failure. Clearing the log
    // here means the assertions below can only be satisfied by the COMMIT-BLOCK report.
    g.setPaperEngineErrors([]);
    const r=g.savePaperAccountGuarded();
    const msgs=g.getPaperEngineErrors().map(x=>x.message);

    assert('RSTDG-BLOCKREPORT.1 (END-TO-END, POSITIVE): a corrupt fxhub_paper seeded in storage is detected at load (the journal still loads), and the next guarded commit is refused with LOAD_INTEGRITY_BLOCKED naming fxhub_paper',
      journalLoaded===1 && r && r.ok===false && r.reason==='LOAD_INTEGRITY_BLOCKED' &&
      (r.blockedKeys||[]).indexOf('fxhub_paper')!==-1,
      JSON.stringify({journalLoaded,reason:r&&r.reason,blocked:r&&r.blockedKeys}));

    assert('RSTDG-BLOCKREPORT.2 (END-TO-END, REPORTED): the refusal is RECORDED to the engine-error channel with the operator-facing text -- exactly one new error, saying the commit was BLOCKED to prevent data loss, naming fxhub_paper and stating nothing was overwritten',
      msgs.length===1 && msgs[0].indexOf('commit BLOCKED to prevent data loss')!==-1 &&
      msgs[0].indexOf('fxhub_paper')!==-1 && msgs[0].indexOf('Nothing was overwritten')!==-1,
      'count='+msgs.length+' msg='+(msgs[0]||'(none)').slice(0,80));

    g.setDeveloperMode(true);
    g.renderPaperLedgerIntegrity();
    const cardHtml=g.elHtml('paperLedgerIntegrityCard')||'';
    g.setDeveloperMode(false);
    assert('RSTDG-BLOCKREPORT.3 (END-TO-END, RENDERED): that same recorded refusal reaches a surface the operator actually reads -- the Paper Ledger Integrity card renders the blocked-commit text, naming fxhub_paper, under the Engine errors heading',
      cardHtml.indexOf('Engine errors')!==-1 &&
      cardHtml.indexOf('commit BLOCKED to prevent data loss')!==-1 &&
      cardHtml.indexOf('fxhub_paper')!==-1,
      'len='+cardHtml.length);

    // ── 🔴 RSTDG-ALEXSURFACE: PD-1, fixed in v12.29.0 (§18.18) ──────────────────────────────────
    // alexGEngineErrors had THREE sites in the whole application -- declaration, unshift, slice --
    // and NO READ SITE AT ALL, while its own declaration comment claimed "surfaced in Diagnostics,
    // mirrors paperEngineErrors". Every ALEX failure written there was invisible to the operator:
    // commitAlexGLedger's ROLLBACK_FAILED FATAL, STALE_VERSION, LOAD_INTEGRITY_BLOCKED, and the
    // INC-001 storage-load notice whose entire purpose is to tell the operator their data is being
    // PRESERVED. recordStorageLoadFailure deliberately fires BOTH channels for that reason -- and
    // on the ALEX side the message went nowhere. The render block is now mirrored from the JVM one
    // under the same Developer Mode gate.
    {
      g.setAlexGEngineErrors([]);
      g.recordAlexGEngineError('FATAL: strategy=ALEX, operation=commitAlexGLedger, ROLLBACK_FAILED sentinel-9137');
      g.setDeveloperMode(true);
      g.renderPaperLedgerIntegrity();
      const alexCard=g.elHtml('paperLedgerIntegrityCard')||'';
      g.setDeveloperMode(false);
      assert('RSTDG-ALEXSURFACE.1 (END-TO-END, RENDERED): a recorded ALEX engine error reaches a surface the operator actually reads -- the Diagnostics card renders it under its own ALEX heading',
        alexCard.indexOf('ALEX engine errors')!==-1 && alexCard.indexOf('sentinel-9137')!==-1,
        'hasHeading='+(alexCard.indexOf('ALEX engine errors')!==-1)+' hasMsg='+(alexCard.indexOf('sentinel-9137')!==-1));
      // NEGATIVE CONTROL: with no ALEX errors the section must render "none" rather than a stale
      // entry or a fabricated one -- so ALEXSURFACE.1 is the message arriving, not the heading
      // simply always being followed by whatever was there before.
      g.setAlexGEngineErrors([]);
      g.setDeveloperMode(true);
      g.renderPaperLedgerIntegrity();
      const emptyCard=g.elHtml('paperLedgerIntegrityCard')||'';
      g.setDeveloperMode(false);
      assert('RSTDG-ALEXSURFACE.2 (NEGATIVE CONTROL): with the ALEX error log empty the section still renders, and shows none rather than a stale or invented entry',
        emptyCard.indexOf('ALEX engine errors')!==-1 && emptyCard.indexOf('sentinel-9137')===-1,
        'stale='+(emptyCard.indexOf('sentinel-9137')!==-1));
      // 🔴 §18.21: SURFACING IS WORTHLESS IF THE SURFACE IS NOT REPAINTED WHEN IT BECOMES VISIBLE.
      // applyDeveloperModeVisibility() explicitly re-renders five Developer-Mode surfaces on toggle
      // and did NOT re-render this card -- the one holding the ONLY operator-visible view of
      // paperEngineErrors and alexGEngineErrors. Turning Developer Mode ON therefore left the card
      // showing what it had rendered while the flag was OFF, and the operator had to press Refresh
      // or leave and re-enter the tab. Developer Mode is session-only and defaults OFF, so the
      // INC-001 load-time notice was invisible on every fresh session. Driven through the REAL
      // toggle path, not by calling the renderer directly.
      g.setDeveloperMode(false);
      g.renderPaperLedgerIntegrity();                 // the card as it looks with the flag OFF
      g.setAlexGEngineErrors([]);
      g.recordAlexGEngineError('FATAL: strategy=ALEX, operation=commitAlexGLedger, toggle-sentinel-4471');
      g.toggleDeveloperMode(true);                    // the real toggle, nothing rendered by hand
      const toggledCard=g.elHtml('paperLedgerIntegrityCard')||'';
      g.setDeveloperMode(false);
      assert('RSTDG-ALEXSURFACE.3 (END-TO-END, the real toggle): turning Developer Mode ON repaints the card, so a recorded ALEX error is visible WITHOUT the operator pressing Refresh or leaving the tab',
        toggledCard.indexOf('toggle-sentinel-4471')!==-1,
        'visibleAfterToggle='+(toggledCard.indexOf('toggle-sentinel-4471')!==-1));
    }

    assert('RSTDG-BLOCKREPORT.4 (PERSISTENCE): the corrupt-but-real stored bytes and the stored version are byte-identical after the refused commit -- the refusal never degrades into "replace it with a default"',
      g.rawStorage().fxhub_paper===CORRUPT && g.rawStorage().fxhub_paper_version==='3',
      JSON.stringify({paper:g.rawStorage().fxhub_paper===CORRUPT,version:g.rawStorage().fxhub_paper_version}));
  }
  {
    // NEGATIVE CONTROL: on a clean load nothing is blocked and NOTHING is reported. A reporter
    // that always reports, or a guard that always blocks, fails here.
    seedClean();
    g.setLocalStorageItem('fxhub_paper',JSON.stringify({balance:10000,openPositions:[],closedPositions:[]}));
    g.setLocalStorageItem('fxhub_paper_version','3');
    g.setLocalStorageItem('fxhub_journal',JSON.stringify([]));
    g.resetLoadFailures();
    g.loadSaved();
    g.setPaperEngineErrors([]);
    const r=g.savePaperAccountGuarded();
    assert('RSTDG-BLOCKREPORT.5 (NEGATIVE CONTROL): after a CLEAN load the same commit succeeds, advances the version to 4, and records ZERO engine errors -- the block and its report are conditional on a real failure, not unconditional',
      r && r.ok===true && g.getLocalStorageItem('fxhub_paper_version')==='4' &&
      g.getPaperEngineErrors().length===0,
      JSON.stringify({ok:r&&r.ok,version:g.getLocalStorageItem('fxhub_paper_version'),errors:g.getPaperEngineErrors().length}));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP E — THE HEALTH VERDICT MUST BE ABLE TO SAY BOTH THINGS, AND BE SEEN
  // ══════════════════════════════════════════════════════════════════════════════════════
  {
    seedClean();
    const clean=g.computePaperTradingHealthReport();
    assert('RSTDG-VERDICT.1 (NEGATIVE CONTROL): a genuinely clean pair of ledgers produces a CLEAN bottom line and an EMPTY issue list -- a verdict that can only say ISSUES DETECTED fails here',
      clean.combined.reconciliationStatus.indexOf('CLEAN')===0 &&
      clean.combined.reconciliationIssues.length===0,
      clean.combined.reconciliationStatus);
  }
  {
    // Exactly one seeded defect: ALEX's balance does not match its own realized P&L.
    // Hand-computed: no closed ALEX positions -> expected balance $10000.00; actual $10123.45;
    // difference $123.45 -> exactly one issue, and it must be the named one.
    seedClean();
    g.setAlexGAccount({balance:10123.45,openPositions:[],closedPositions:[]});
    const rep=g.computePaperTradingHealthReport();
    assert('RSTDG-VERDICT.2 (POSITIVE): one seeded ALEX balance defect flips the bottom line to ISSUES DETECTED and the issue list is EXACTLY ["ALEX balance difference"] -- expected $10000.00 vs actual $10123.45, difference $123.45',
      rep.combined.reconciliationStatus.indexOf('ISSUES DETECTED')===0 &&
      rep.combined.reconciliationIssues.length===1 &&
      rep.combined.reconciliationIssues[0]==='ALEX balance difference' &&
      rep.alex.expectedBalance===10000 && rep.alex.balanceDifference===123.45,
      JSON.stringify({status:rep.combined.reconciliationStatus,issues:rep.combined.reconciliationIssues,
        diff:rep.alex.balanceDifference}));

    const text=g.buildPaperTradingHealthReportText(rep);
    assert('RSTDG-VERDICT.3 (COPYABLE REPORT): the copyable Health Report text carries that same verdict verbatim on its Reconciliation status line -- the copied bottom line cannot read CLEAN while the computed verdict says otherwise',
      text.indexOf('Reconciliation status: ISSUES DETECTED — ALEX balance difference')!==-1,
      text.split('\n').slice(-1)[0]);

    g.setDeveloperMode(true);
    g.renderPaperTradingHealthCheck();
    const html=g.elHtml('paperTradingHealthCheckCard')||'';
    assert('RSTDG-VERDICT.4 (END-TO-END, RENDERED): the Health Check card the operator actually looks at renders that verdict, names the failing detector, and paints it red -- a defect detected but not shown is a defect not reported',
      html.indexOf('ISSUES DETECTED')!==-1 && html.indexOf('ALEX balance difference')!==-1 &&
      html.indexOf('var(--red)')!==-1,
      'len='+html.length);
    g.setDeveloperMode(false);
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // GROUP F — OUTAGE AND STALE-DATA DETECTION IN THE OBSERVATION SUMMARISER
  //
  // EVIDENCE_POLL_EXPECTED_INTERVAL_MS is 60,000. nowMs is deliberately NOT supplied, so these
  // fixtures measure ONLY the historical between-record arithmetic; the trailing/still-open
  // term is a separate mechanism with its own coverage and is not what is under test here.
  // ══════════════════════════════════════════════════════════════════════════════════════
  const T0='2026-03-01T10:00:00.000Z';
  {
    // BOUNDARY: exactly one expected interval apart -- healthy, and must NOT raise an alarm.
    const sum=g.evidenceSummarizeObservations([
      {kind:'POLL',seq:1,startedAt:T0,outcome:'OK'},
      {kind:'POLL',seq:2,startedAt:'2026-03-01T10:01:00.000Z',outcome:'OK'}]);
    assert('RSTDG-OUTAGE.1 (BOUNDARY, NEGATIVE): two polls exactly ONE expected interval (60s) apart report ZERO missed intervals and a widest gap of exactly 60000ms -- an on-time loop must not be reported as an outage',
      sum.missedIntervals===0 && sum.maxGapMs===60000 && sum.gapsWithFailures.length===0,
      JSON.stringify({missed:sum.missedIntervals,maxGap:sum.maxGapMs}));
  }
  {
    // BOUNDARY: exactly two intervals apart -- exactly ONE interval was missed.
    const sum=g.evidenceSummarizeObservations([
      {kind:'POLL',seq:1,startedAt:T0,outcome:'OK'},
      {kind:'POLL',seq:2,startedAt:'2026-03-01T10:02:00.000Z',outcome:'OK'}]);
    assert('RSTDG-OUTAGE.2 (BOUNDARY, POSITIVE): two polls exactly TWO expected intervals (120s) apart report exactly ONE missed interval, a widest gap of 120000ms, and one recorded gap spanning 10:00:00 to 10:02:00',
      sum.missedIntervals===1 && sum.maxGapMs===120000 && sum.gapsWithFailures.length===1 &&
      sum.gapsWithFailures[0].missedIntervals===1 && sum.gapsWithFailures[0].from===T0,
      JSON.stringify({missed:sum.missedIntervals,maxGap:sum.maxGapMs,gaps:sum.gapsWithFailures.length}));

    const html=g.evidenceContinuityHtml(sum);
    assert('RSTDG-OUTAGE.3 (END-TO-END, RENDERED): the Forward-Observation Continuity card renders that missed interval as 1, in red -- a gap that is counted but displayed as 0 tells the operator the loop is healthy',
      html.indexOf('Missed intervals: <strong style="color:var(--red)">1</strong>')!==-1,
      'len='+html.length);
  }
  {
    // STALENESS: a FAILED poll proves the loop still ran, but must never refresh the
    // "last SUCCESSFUL poll" timestamp -- that is the value that tells the operator how old
    // the newest good data is.
    const sum=g.evidenceSummarizeObservations([
      {kind:'POLL',seq:1,startedAt:T0,outcome:'OK'},
      {kind:'POLL',seq:2,startedAt:'2026-03-01T10:01:00.000Z',outcome:'ERROR'},
      {kind:'POLL',seq:3,startedAt:'2026-03-01T10:02:00.000Z',outcome:'ERROR'}]);
    assert('RSTDG-STALE.1 (POSITIVE): with one OK poll followed by two FAILED ones, the last successful poll stays pinned at 10:00:00 while pollsOk=1 and pollsFailed=2 -- a failed poll must never refresh the freshness timestamp',
      sum.lastSuccessfulPollAt===T0 && sum.pollsOk===1 && sum.pollsFailed===2,
      JSON.stringify({last:sum.lastSuccessfulPollAt,ok:sum.pollsOk,failed:sum.pollsFailed}));
  }
  {
    // NEGATIVE CONTROL for STALE.1: when polls really do succeed, the timestamp really does
    // advance -- so STALE.1 is not passing because the field is simply pinned to the first poll.
    const sum=g.evidenceSummarizeObservations([
      {kind:'POLL',seq:1,startedAt:T0,outcome:'OK'},
      {kind:'POLL',seq:2,startedAt:'2026-03-01T10:01:00.000Z',outcome:'OK'},
      {kind:'POLL',seq:3,startedAt:'2026-03-01T10:02:00.000Z',outcome:'OK'}]);
    assert('RSTDG-STALE.2 (NEGATIVE CONTROL): with three successful polls the last-successful timestamp advances to 10:02:00 -- the field is not simply frozen at the first record',
      sum.lastSuccessfulPollAt==='2026-03-01T10:02:00.000Z' && sum.pollsOk===3 && sum.pollsFailed===0,
      JSON.stringify({last:sum.lastSuccessfulPollAt,ok:sum.pollsOk}));
  }

  return results;
}
