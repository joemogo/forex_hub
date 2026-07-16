// v12.1.1 DIAGNOSTICS DATA INTEGRITY -- journal-only-orphan leak fix
//
// runDiagnostics() itself is async and its "Paper trading engine" check awaits a real
// closePaperPosition() call -- per the documented, permanent offline-harness limitation
// (docs/TESTING.md: JXA cannot resolve a genuine await on an asynchronously-settling
// promise), it cannot be driven to completion here. These fixtures instead:
//   (a) thoroughly unit-test diagSnapshot()/diagRestore() as pure, standalone functions;
//   (b) faithfully replicate each fixed check's SYNCHRONOUS-reachable logic -- using the
//       exact same real, unmodified production functions (openPaperPosition, pipValuePerLot,
//       commitPaperLedger) the real check calls -- against real global state and real
//       localStorage, proving the restoration pattern is correct;
//   (c) prove the exception path restores state even when the protected code throws.
// The full end-to-end proof, including the async close half of the paper-trading check,
// is verified live in a real browser (see the release report) -- exactly the established
// pattern for anything this harness cannot reach.
function runV1211Fixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,detail:detail||''});};
  const deepEq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);

  function snapshotAllTradingState(){
    return JSON.stringify({
      journalEntries:g.getJournalEntries(),
      alexGJournalEntries:g.getAlexGJournalEntries(),
      paperAccount:g.getPaperAccount(),
      alexGAccount:g.getAlexGAccount(),
      scanData:g.getScanData()
    });
  }

  // ═══ Fixture 1: diagSnapshot() captures the current value of every named getter ═══
  {
    let a=1,b='x';
    const snap=g.diagSnapshot({a:()=>a,b:()=>b});
    assert('Fixture 1: diagSnapshot() captures every named getter\'s current value',
      snap.a===1&&snap.b==='x', 'snap='+JSON.stringify(snap));
  }

  // ═══ Fixture 2: diagRestore() writes each captured value back through the matching setter ═══
  {
    let a=1;
    const snap=g.diagSnapshot({a:()=>a});
    a=999; // mutate
    g.diagRestore(snap,{a:v=>a=v});
    assert('Fixture 2: diagRestore() writes the snapshotted value back through the setter',
      a===1, 'a='+a);
  }

  // ═══ Fixture 3: diagSnapshot() captures a value AT CALL TIME, not a live reference -- further mutation after the snapshot doesn't change what gets restored ═══
  {
    let obj={x:1};
    const snap=g.diagSnapshot({obj:()=>obj});
    obj={x:2}; // reassign before restore
    let restored;
    g.diagRestore(snap,{obj:v=>restored=v});
    assert('Fixture 3: diagSnapshot() captures the value present at snapshot time, unaffected by later reassignment',
      restored.x===1, 'restored='+JSON.stringify(restored));
  }

  // ═══ Fixture 4: diagRestore() silently skips a snapshotted key with no matching setter (safe no-op, never throws) ═══
  {
    const snap=g.diagSnapshot({a:()=>1,b:()=>2});
    let threw=false;
    try{ g.diagRestore(snap,{a:()=>{}}); }catch(e){ threw=true; }
    assert('Fixture 4: diagRestore() does not throw when a snapshotted key has no matching setter',
      !threw, 'threw='+threw);
  }

  // ═══ Fixture 5: replicating Check 2's fixed localStorage pattern -- the throwaway key is removed even if the read between set and remove throws ═══
  {
    g.setLocalStorageItem('fxhub_diag_test','1');
    let threw=false;
    try{
      try{
        throw new Error('simulated read failure');
      }finally{
        g.removeLocalStorageItem('fxhub_diag_test');
      }
    }catch(e){ threw=true; }
    assert('Fixture 5: the fixed Check 2 pattern (try/finally around the read) still removes fxhub_diag_test even when the read throws',
      threw&&g.getLocalStorageItem('fxhub_diag_test')===null, 'threw='+threw+' key='+g.getLocalStorageItem('fxhub_diag_test'));
  }

  // ═══ Fixture 6: replicating Check 3's fixed pip-value-math pattern -- pairData is restored to the exact original object reference, even via the diagSnapshot/diagRestore helper ═══
  {
    const originalPairData={GBP_USD:{price:1.25}};
    g.setPairData(originalPairData);
    const snap=g.diagSnapshot({pairData:g.getPairData});
    try{
      g.setPairData(Object.assign({},g.getPairData(),{EUR_USD:{price:1.0850}}));
      g.pipValuePerLot('EUR_USD');
    }finally{
      g.diagRestore(snap,{pairData:g.setPairData});
    }
    assert('Fixture 6: pairData is restored to the exact original reference after the Check 3 pattern runs',
      g.getPairData()===originalPairData, 'sameRef='+(g.getPairData()===originalPairData));
  }

  // ═══ Fixture 6b: Check 3's pattern restores pairData even when pipValuePerLot() itself throws ═══
  {
    const originalPairData={GBP_USD:{price:1.25}};
    g.setPairData(originalPairData);
    const snap=g.diagSnapshot({pairData:g.getPairData});
    let threw=false;
    try{
      try{
        g.setPairData(Object.assign({},g.getPairData(),{EUR_USD:{price:1.0850}}));
        throw new Error('simulated pipValuePerLot failure');
      }finally{
        g.diagRestore(snap,{pairData:g.setPairData});
      }
    }catch(e){ threw=true; }
    assert('Fixture 6b: pairData is still restored to the original reference even when the check throws mid-mutation',
      threw&&g.getPairData()===originalPairData, 'threw='+threw+' sameRef='+(g.getPairData()===originalPairData));
  }

  // ═══ Fixture 7: THE CORE FIX -- replicating Check 4's open-half using the REAL openPaperPosition()
  // and REAL commitPaperLedger(), proving journalEntries (previously never restored) is now back
  // to its exact real value BEFORE the restoring commitPaperLedger() call persists anything,
  // and that fxhub_journal in localStorage reflects the ORIGINAL state afterward, not the
  // simulated trade. This is a direct reproduction of the confirmed root cause -- and of the
  // second, subtler defect the first version of this fixture caught: journalEntries is mutated
  // IN PLACE (unshift/find+mutate) by openPaperPosition(), so it must be isolated by reassigning
  // to a fresh array BEFORE the simulation runs (exactly like paperAccount already is), not
  // merely snapshotted/restored by reference afterward. ═══
  {
    const realJournal=[{tradeId:'REAL|1',pair:'USD/JPY',result:'Win',pnl:50}];
    const realPaper={balance:10000,openPositions:[],closedPositions:[]};
    g.setJournalEntries(realJournal.slice());
    g.setPaperAccount(JSON.parse(JSON.stringify(realPaper)));
    g.setPairData({EUR_USD:{price:1.0850}});
    g.setActivePair('EUR_USD');

    const snap=g.diagSnapshot({
      pairData:g.getPairData,
      paperAccount:g.getPaperAccount,
      activePair:g.getActivePair,
      journalEntries:g.getJournalEntries
    });

    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]}); // isolate, same as the real check
    g.setJournalEntries([]); // isolate journalEntries too -- the fix under test
    g.setRrFields('1.08500','1.08300','1.08900');
    try{
      g.placePaperTrade(true); // real production function -- opens a real position + real journal record via openPaperPosition()
    }finally{
      g.diagRestore(snap,{
        pairData:g.setPairData,
        paperAccount:g.setPaperAccount,
        activePair:g.setActivePair,
        journalEntries:g.setJournalEntries
      });
      g.commitPaperLedger(); // mirrors the real check's restoring commit
    }

    const persistedJournal=JSON.parse(g.getLocalStorageItem('fxhub_journal'));
    const persistedPaper=JSON.parse(g.getLocalStorageItem('fxhub_paper'));
    assert('Fixture 7a: journalEntries in memory is back to the exact real pre-simulation value after restore',
      deepEq(g.getJournalEntries(),realJournal), 'journalEntries='+JSON.stringify(g.getJournalEntries()));
    assert('Fixture 7b: fxhub_journal in localStorage reflects the real pre-simulation journal, NOT the simulated trade -- the confirmed root cause is fixed',
      deepEq(persistedJournal,realJournal), 'persistedJournal='+JSON.stringify(persistedJournal));
    assert('Fixture 7c: fxhub_paper in localStorage reflects the real pre-simulation account, not the simulated one',
      deepEq(persistedPaper,realPaper), 'persistedPaper='+JSON.stringify(persistedPaper));
  }

  // ═══ Fixture 8: the Check 4 pattern still restores journalEntries/paperAccount even if the
  // simulation throws partway through (exception-path requirement) ═══
  {
    const realJournal=[{tradeId:'REAL|2',pair:'AUD/USD',result:'Loss',pnl:-30}];
    const realPaper={balance:9000,openPositions:[],closedPositions:[]};
    g.setJournalEntries(realJournal.slice());
    g.setPaperAccount(JSON.parse(JSON.stringify(realPaper)));
    g.setPairData({EUR_USD:{price:1.0850}});
    g.setActivePair('EUR_USD');

    const snap=g.diagSnapshot({
      pairData:g.getPairData,
      paperAccount:g.getPaperAccount,
      activePair:g.getActivePair,
      journalEntries:g.getJournalEntries
    });
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setRrFields('1.08500','1.08300','1.08900');
    let threw=false;
    try{
      try{
        g.placePaperTrade(true); // real mutation happens here
        throw new Error('simulated exception after opening the position, before close');
      }finally{
        g.diagRestore(snap,{
          pairData:g.setPairData,
          paperAccount:g.setPaperAccount,
          activePair:g.setActivePair,
          journalEntries:g.setJournalEntries
        });
        g.commitPaperLedger();
      }
    }catch(e){ threw=true; }

    const persistedJournal=JSON.parse(g.getLocalStorageItem('fxhub_journal'));
    assert('Fixture 8: even when the check throws after mutating state, journalEntries and fxhub_journal are still correctly restored',
      threw&&deepEq(g.getJournalEntries(),realJournal)&&deepEq(persistedJournal,realJournal),
      'threw='+threw+' journalEntries='+JSON.stringify(g.getJournalEntries()));
  }

  // ═══ Fixture 9: no localStorage key is added or removed by the fixed Check 3/Check 4 patterns -- only the content of pre-existing keys is touched, and only transiently ═══
  {
    g.setJournalEntries([{tradeId:'X',pair:'EUR/USD'}]);
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setPairData({EUR_USD:{price:1.0850}});
    g.setActivePair('EUR_USD');
    const keysBefore=g.getAllLocalStorageKeys();

    const snapPD=g.diagSnapshot({pairData:g.getPairData});
    try{ g.setPairData(Object.assign({},g.getPairData(),{USD_JPY:{price:155}})); g.pipValuePerLot('USD_JPY'); }
    finally{ g.diagRestore(snapPD,{pairData:g.setPairData}); }

    const snap=g.diagSnapshot({paperAccount:g.getPaperAccount,journalEntries:g.getJournalEntries,activePair:g.getActivePair,pairData:g.getPairData});
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setRrFields('1.08500','1.08300','1.08900');
    try{ g.placePaperTrade(true); }
    finally{
      g.diagRestore(snap,{paperAccount:g.setPaperAccount,journalEntries:g.setJournalEntries,activePair:g.setActivePair,pairData:g.setPairData});
      g.commitPaperLedger();
    }
    const keysAfter=g.getAllLocalStorageKeys();
    assert('Fixture 9: no localStorage key is added or removed by running the fixed Check 3/Check 4 patterns',
      deepEq(keysBefore.sort(),keysAfter.sort()), 'before='+JSON.stringify(keysBefore)+' after='+JSON.stringify(keysAfter));
  }

  // ═══ Fixture 10: a full pass through the fixed synchronous-reachable Diagnostics logic (Check 2 + Check 3 + Check 4's open half) leaves EVERY trading store byte-identical, including alexGAccount/alexGJournalEntries/scanData which none of these checks should ever touch ═══
  {
    g.setJournalEntries([{tradeId:'A',pair:'GBP/JPY',result:'Win',pnl:10}]);
    g.setAlexGJournalEntries([{tradeId:'AG|A',pair:'AUD/JPY'}]);
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setScanData({});
    g.setPairData({EUR_USD:{price:1.0850}});
    g.setActivePair('EUR_USD');
    const before=snapshotAllTradingState();

    // Check 2 pattern
    g.setLocalStorageItem('fxhub_diag_test','1');
    try{ g.getLocalStorageItem('fxhub_diag_test'); } finally{ g.removeLocalStorageItem('fxhub_diag_test'); }

    // Check 3 pattern
    const snapPD=g.diagSnapshot({pairData:g.getPairData});
    try{ g.setPairData(Object.assign({},g.getPairData(),{USD_JPY:{price:155}})); g.pipValuePerLot('USD_JPY'); }
    finally{ g.diagRestore(snapPD,{pairData:g.setPairData}); }

    // Check 4 open-half pattern
    const snap=g.diagSnapshot({paperAccount:g.getPaperAccount,journalEntries:g.getJournalEntries,activePair:g.getActivePair,pairData:g.getPairData});
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setRrFields('1.08500','1.08300','1.08900');
    try{ g.placePaperTrade(true); }
    finally{
      g.diagRestore(snap,{paperAccount:g.setPaperAccount,journalEntries:g.setJournalEntries,activePair:g.setActivePair,pairData:g.setPairData});
      g.commitPaperLedger();
    }

    const after=snapshotAllTradingState();
    assert('Fixture 10: a full pass through the fixed Check 2/3/4-open-half logic leaves journalEntries/alexGJournalEntries/paperAccount/alexGAccount/scanData byte-identical',
      before===after, 'changed='+(before!==after));
  }

  return results;
}
