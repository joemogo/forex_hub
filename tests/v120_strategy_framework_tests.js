// v12.0.0 STRATEGY FRAMEWORK -- REGISTRY / MANIFEST / SERVICES (Foundation, Release 1)
// Proves: the ALEX registry entry exposes the existing account/journal stores unmodified,
// the journal/dashboard/panel-open/dev-tools/diagnostics seams produce identical output
// through the registry as they did hardcoded, missing-service fallbacks never throw, and
// zero trading state is mutated by any of it.
function runV120Fixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,detail:detail||''});};
  const deepEq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);

  function snapshotTradingState(){
    return JSON.stringify({
      journalEntries:g.getJournalEntries(),
      alexGJournalEntries:g.getAlexGJournalEntries(),
      paperAccount:g.getPaperAccount(),
      alexGAccount:g.getAlexGAccount(),
      scanData:g.getScanData()
    });
  }

  // ═══ Fixture 1: STRATEGY_REGISTRY contains ALEX's registered entry (v12.1.0: JVM was
  // added as a second entry in Release 2 -- this fixture only asserts ALEX is present and
  // correctly registered, not the total registry size, since that's no longer a v120-only
  // concern) ═══
  {
    const reg=g.getRegistry();
    const alexEntry=reg.find(e=>e.manifest.id==='alex_g_sr_v1');
    assert('Fixture 1: STRATEGY_REGISTRY contains ALEX\'s registered entry',
      Array.isArray(reg)&&!!alexEntry,
      'reg='+JSON.stringify(reg.map(e=>e.manifest.id)));
  }

  // ═══ Fixture 2: ALEX Manifest id is read from RULES_ALEXG.ruleVersion, never restated ═══
  {
    const m=g.getStrategyManifest('alex_g_sr_v1');
    assert('Fixture 2: ALEX Manifest id equals RULES_ALEXG.ruleVersion (cannot drift apart)',
      m&&m.id===g.getRulesAlexG().ruleVersion, 'm.id='+(m&&m.id));
  }

  // ═══ Fixture 3: Manifest is static -- contains no computed performance data ═══
  {
    const m=g.getStrategyManifest('alex_g_sr_v1');
    const forbidden=['balance','openPositions','closedPositions','winRate','netR','pnl'];
    const hasForbidden=forbidden.some(k=>Object.prototype.hasOwnProperty.call(m,k));
    assert('Fixture 3: Manifest contains no computed performance fields',
      !hasForbidden, 'keys='+Object.keys(m).join(','));
  }

  // ═══ Fixture 4: getStrategyServices('alex_g_sr_v1').getAccount() returns the EXACT live alexGAccount reference ═══
  {
    const acc={balance:12345,openPositions:[{id:'x'}],closedPositions:[]};
    g.setAlexGAccount(acc);
    const svc=g.getStrategyServices('alex_g_sr_v1');
    const returned=svc.getAccount();
    assert('Fixture 4: Services.getAccount() returns the live alexGAccount object (same reference)',
      returned===acc, 'sameRef='+(returned===acc));
  }

  // ═══ Fixture 5: getStrategyServices('alex_g_sr_v1').getJournal() returns the EXACT live alexGJournalEntries reference ═══
  {
    const j=[{tradeId:'AG|1'}];
    g.setAlexGJournalEntries(j);
    const svc=g.getStrategyServices('alex_g_sr_v1');
    assert('Fixture 5: Services.getJournal() returns the live alexGJournalEntries array (same reference)',
      svc.getJournal()===j, 'sameRef='+(svc.getJournal()===j));
  }

  // ═══ Fixture 6: getUnifiedJournalRecords() via the registry path is byte-identical to the pre-v12.0.0 direct-call path ═══
  {
    g.setJournalEntries([{tradeId:1,pair:'EUR/USD',direction:'buy',dir:'buy',entry:1.1,stop:1.09,target:1.12,result:'Win',pnl:100,openedAt:'2026-01-01T00:00:00.000Z',closedAt:'2026-01-01T01:00:00.000Z'}]);
    g.setAlexGJournalEntries([{tradeId:'AG|1',pair:'GBP/USD',direction:'sell',entry:1.25,stop:1.26,target:1.22,result:'Loss',pnl:-50,openedAt:'2026-01-02T00:00:00.000Z',closedAt:'2026-01-02T01:00:00.000Z'}]);
    const viaRegistry=g.getUnifiedJournalRecords();
    // manually reconstruct exactly what the pre-v12.0.0 hardcoded implementation produced
    const jvmOld=g.getJournalEntries().map(e=>g.normalizeJournalRecord(e,'current_strategy'));
    const alexOld=g.getAlexGJournalEntries().map(e=>g.normalizeJournalRecord(e,'alex_g_sr_v1'));
    const viaOldPath=jvmOld.concat(alexOld).sort((a,b)=>{
      const ta=a.openedAt?new Date(a.openedAt).getTime():(a.closedAt?new Date(a.closedAt).getTime():0);
      const tb=b.openedAt?new Date(b.openedAt).getTime():(b.closedAt?new Date(b.closedAt).getTime():0);
      return tb-ta;
    });
    assert('Fixture 6: getUnifiedJournalRecords() output is identical via the registry path vs. the old direct-call path',
      deepEq(viaRegistry,viaOldPath), 'equal='+deepEq(viaRegistry,viaOldPath));
  }

  // ═══ Fixture 7: getFilteredJournalRecords/renderMiniJournal remain untouched and still work through the new getUnifiedJournalRecords() ═══
  {
    const filtered=g.getFilteredJournalRecords({strategy:'ALEX'});
    assert('Fixture 7: getFilteredJournalRecords({strategy:"ALEX"}) still returns only ALEX records after the registry change',
      filtered.length===1&&filtered[0].strategyLabel==='ALEX', 'filtered='+JSON.stringify(filtered.map(r=>r.strategyLabel)));
  }

  // ═══ Fixture 8: Dashboard's ALEX P&L/Win Rate tile reflects the account returned through Services, byte-identical to raw alexGAccount data ═══
  {
    g.setAlexGAccount({balance:10300,openPositions:[],closedPositions:[{result:'Win',pnl:200},{result:'Loss',pnl:-100},{result:'Win',pnl:200}]});
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.renderDashboard();
    const html=g.getElementHtml('dashPerformance');
    const expectedPnl='+$300.00'; // 10300-10000
    const expectedWinRate='67%'; // 2/3 rounded
    assert('Fixture 8: Dashboard ALEX P&L tile shows the correct value computed via Services.getAccount()',
      html.indexOf(expectedPnl)!==-1, 'html contains expectedPnl='+(html.indexOf(expectedPnl)!==-1));
    assert('Fixture 8b: Dashboard ALEX Win Rate tile shows the correct value computed via Services.getAccount()',
      html.indexOf(expectedWinRate)!==-1, 'html contains expectedWinRate='+(html.indexOf(expectedWinRate)!==-1));
  }

  // ═══ Fixture 9: Dashboard running-trades table still tags ALEX open positions correctly through Services.getAccount() ═══
  {
    g.setAlexGAccount({balance:10000,openPositions:[{pair:'EUR/USD',direction:'buy',entry:1.1}],closedPositions:[]});
    g.renderDashboard();
    const html=g.getElementHtml('dashRunningTrades');
    assert('Fixture 9: Dashboard running-trades table includes the ALEX open position via Services.getAccount()',
      html.indexOf('ALEX')!==-1&&html.indexOf('EUR/USD')!==-1, 'html snippet ok');
  }

  // ═══ Fixture 10: showPanel('alexg') still fires ALEX's panel-open init through Services.onOpen() ═══
  {
    // reset to a render-safe state -- initAlexGPair()/renderAlexGLivePanel() render ALEX's
    // own richer open-positions table (entry/stop/target/etc.), unlike Dashboard's minimal one
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setElementText('alexgHubVersion','');
    g.showPanel('alexg',null);
    const text=g.getElementText('alexgHubVersion');
    assert('Fixture 10: showPanel("alexg") still triggers initAlexGPair() (via Services.onOpen()) -- version label populated',
      text===g.getAppVersion(), 'text='+text+' expected='+g.getAppVersion());
  }

  // ═══ Fixture 11: Developer Mode visibility still toggles the ALEX dev-tools card, now resolved through the Manifest ═══
  {
    g.setDeveloperMode(false);
    g.applyDeveloperModeVisibility();
    const hiddenDisplay=g.getElementStyleDisplay('devToolsAlexCard');
    g.toggleDeveloperMode();
    const shownDisplay=g.getElementStyleDisplay('devToolsAlexCard');
    assert('Fixture 11: Developer Mode OFF hides devToolsAlexCard, ON shows it (resolved via Manifest.devToolsCardId)',
      hiddenDisplay==='none'&&shownDisplay==='block', 'hidden='+hiddenDisplay+' shown='+shownDisplay);
    g.toggleDeveloperMode(); // restore OFF
  }

  // ═══ Fixture 11b: Developer Mode visibility genuinely reads devToolsCardId from the Manifest, not a hardcoded literal ═══
  {
    const m=g.getStrategyManifest('alex_g_sr_v1');
    const originalId=m.devToolsCardId;
    m.devToolsCardId='someOtherCardId';
    g.setElementDisplay('someOtherCardId','none');
    g.setDeveloperMode(true);
    g.applyDeveloperModeVisibility();
    const display=g.getElementStyleDisplay('someOtherCardId');
    m.devToolsCardId=originalId; // restore
    g.setDeveloperMode(false);
    assert('Fixture 11b: applyDeveloperModeVisibility() genuinely resolves the card id from the Manifest at call time',
      display==='block', 'display='+display);
  }

  // ═══ Fixture 12: Diagnostics still performs the exact ALEX isolation check via Services.isolationCheck() ═══
  {
    const svc=g.getStrategyServices('alex_g_sr_v1');
    const before=snapshotTradingState();
    const r=svc.isolationCheck();
    const after=snapshotTradingState();
    assert('Fixture 12: Services.isolationCheck() reports pass:true under normal conditions',
      r&&r.pass===true&&r.name==='Alex G module isolation (Phase 1-3 foundation)', 'r='+JSON.stringify(r));
    assert('Fixture 12b: isolationCheck() itself never leaves current-strategy state mutated',
      before===after, 'changed='+(before!==after));
  }

  // ═══ Fixture 13: alexGIsolationCheck() (the extracted function) is byte-behavior-identical to the pre-v12.0.0 inline block ═══
  {
    // corrupt isolation deliberately to prove the check can still fail correctly, not just always pass
    const savedRuleVersion=g.getRulesAlexG().ruleVersion;
    g.getRulesAlexG().ruleVersion='tampered';
    const r=g.alexGIsolationCheck();
    g.getRulesAlexG().ruleVersion=savedRuleVersion;
    assert('Fixture 13: alexGIsolationCheck() correctly reports pass:false when ruleVersion has been tampered with',
      r.pass===false, 'r='+JSON.stringify(r));
  }

  // ═══ Fixture 14: a missing/unregistered strategy service fails safely -- getUnifiedJournalRecords() never throws, falls back ═══
  {
    const savedRegistry=g.getRegistry().slice();
    g.setRegistry([]);
    let threw=false, records=null;
    try{ records=g.getUnifiedJournalRecords(); }catch(e){ threw=true; }
    g.setRegistry(savedRegistry);
    assert('Fixture 14: getUnifiedJournalRecords() does not throw and still returns ALEX records when the registry is empty (falls back to direct state access)',
      !threw&&Array.isArray(records)&&records.some(r=>r.strategyLabel==='ALEX'), 'threw='+threw+' count='+(records&&records.length));
  }

  // ═══ Fixture 15: a missing/unregistered strategy service fails safely -- renderDashboard() never throws ═══
  {
    const savedRegistry=g.getRegistry().slice();
    g.setRegistry([]);
    let threw=false;
    try{ g.renderDashboard(); }catch(e){ threw=true; }
    g.setRegistry(savedRegistry);
    assert('Fixture 15: renderDashboard() does not throw when the registry is empty (falls back to the raw alexGAccount global)',
      !threw, 'threw='+threw);
  }

  // ═══ Fixture 16: a missing/unregistered strategy service fails safely -- showPanel("alexg") never throws, falls back to the direct call ═══
  {
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    const savedRegistry=g.getRegistry().slice();
    g.setRegistry([]);
    g.setElementText('alexgHubVersion','');
    let threw=false;
    try{ g.showPanel('alexg',null); }catch(e){ threw=true; }
    const text=g.getElementText('alexgHubVersion');
    g.setRegistry(savedRegistry);
    assert('Fixture 16: showPanel("alexg") does not throw and still fires initAlexGPair() when the registry is empty',
      !threw&&text===g.getAppVersion(), 'threw='+threw+' text='+text);
  }

  // ═══ Fixture 17: a missing/unregistered strategy service fails safely -- runDiagnostics' isolation-check branch never throws, reports a clear failure ═══
  {
    const savedRegistry=g.getRegistry().slice();
    g.setRegistry([]);
    let threw=false, pushed=null;
    try{ pushed=g.runIsolationCheckDiagnosticStep(); }catch(e){ threw=true; }
    g.setRegistry(savedRegistry);
    assert('Fixture 17: the Diagnostics isolation-check step does not throw when ALEX is unregistered, and reports a clear failure instead of silently skipping',
      !threw&&pushed&&pushed.pass===false&&pushed.detail==='ALEX strategy is not registered.', 'threw='+threw+' pushed='+JSON.stringify(pushed));
  }

  // ═══ Fixture 18: applyDeveloperModeVisibility() falls back safely when the Manifest is unavailable ═══
  {
    const savedRegistry=g.getRegistry().slice();
    g.setRegistry([]);
    g.setElementDisplay('devToolsAlexCard','none');
    g.setDeveloperMode(true);
    let threw=false;
    try{ g.applyDeveloperModeVisibility(); }catch(e){ threw=true; }
    const display=g.getElementStyleDisplay('devToolsAlexCard');
    g.setRegistry(savedRegistry);
    g.setDeveloperMode(false);
    assert('Fixture 18: applyDeveloperModeVisibility() does not throw and still falls back to the literal devToolsAlexCard id when the Manifest is unavailable',
      !threw&&display==='block', 'threw='+threw+' display='+display);
  }

  // ═══ Fixture 19: renderMiniJournal() falls back safely when the Manifest is unavailable ═══
  {
    const savedRegistry=g.getRegistry().slice();
    g.setRegistry([]);
    let threw=false;
    try{ g.renderMiniJournal('alexMiniJournal','alexMiniJournalSummary','ALEX'); }catch(e){ threw=true; }
    g.setRegistry(savedRegistry);
    assert('Fixture 19: renderMiniJournal() does not throw for strategyLabel=ALEX when the Manifest is unavailable (falls back to the literal inspector card id)',
      !threw, 'threw='+threw);
  }

  // ═══ Fixture 20: runtime health defaults correctly ═══
  {
    const svc=g.getStrategyServices('alex_g_sr_v1');
    assert('Fixture 20: Services.health() defaults to "ready"',
      typeof svc.health==='function'&&svc.health()==='ready', 'health='+(svc.health&&svc.health()));
  }

  // ═══ Fixture 21: capabilities honestly describe what is and is not wired this release ═══
  {
    const m=g.getStrategyManifest('alex_g_sr_v1');
    const c=m.capabilities;
    assert('Fixture 21: capabilities.statistics is honestly false (no dedicated live computePerformance() exists yet)',
      c.statistics===false, 'c.statistics='+c.statistics);
    assert('Fixture 21b: capabilities.diagnostics is true and Services.isolationCheck is actually wired',
      c.diagnostics===true&&typeof g.getStrategyServices('alex_g_sr_v1').isolationCheck==='function', 'ok');
  }

  // ═══ Fixture 22: registering ALEX introduces zero new persistence -- no new localStorage key is written by any Services call ═══
  {
    const before=g.getAllLocalStorageKeys();
    const svc=g.getStrategyServices('alex_g_sr_v1');
    svc.getAccount();svc.getJournal();svc.normalize({});svc.isolationCheck();svc.health();
    g.getStrategyManifest('alex_g_sr_v1');
    const after=g.getAllLocalStorageKeys();
    assert('Fixture 22: no localStorage key is added by any Registry/Manifest/Services call',
      deepEq(before.sort(),after.sort()), 'before='+JSON.stringify(before)+' after='+JSON.stringify(after));
  }

  // ═══ Fixture 23: buildOpenRecord/buildCloseRecord/start/stop/settings/playbook/AI hooks are deliberately absent from Services this release ═══
  {
    const svc=g.getStrategyServices('alex_g_sr_v1');
    const absent=['buildOpenRecord','buildCloseRecord','start','stop','getContextSnapshot','getExplanation','buildWeeklySummary'].every(k=>typeof svc[k]==='undefined');
    assert('Fixture 23: Services deliberately does not expose buildOpenRecord/buildCloseRecord/start/stop/AI hooks this release (not needed by any target seam)',
      absent, 'svc keys='+Object.keys(svc).join(','));
  }

  // ═══ Fixture 24: full pass through every new/changed function never mutates trading state ═══
  {
    g.setJournalEntries([]);g.setAlexGJournalEntries([]);
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setScanData({});
    const before=snapshotTradingState();
    g.getUnifiedJournalRecords();
    g.getFilteredJournalRecords({strategy:'ALEX'});
    g.renderDashboard();
    g.showPanel('alexg',null);
    g.toggleDeveloperMode();g.toggleDeveloperMode();
    g.runIsolationCheckDiagnosticStep();
    g.renderMiniJournal('alexMiniJournal','alexMiniJournalSummary','ALEX');
    const after=snapshotTradingState();
    assert('Fixture 24: a full pass through every touched seam never mutates journalEntries/alexGJournalEntries/paperAccount/alexGAccount/scanData',
      before===after, 'changed='+(before!==after));
  }

  return results;
}
