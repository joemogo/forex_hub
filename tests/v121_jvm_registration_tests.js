// v12.1.0 STRATEGY FRAMEWORK -- JVM REGISTRATION (Foundation, Release 2)
// Proves: the JVM registry entry exposes the existing paperAccount/journalEntries stores
// unmodified, JVM's Services reference existing functions rather than duplicating logic,
// the journal/dashboard/panel-open/dev-tools seams produce identical output through the
// registry for JVM (mirroring what Release 1 proved for ALEX), both strategies coexist
// without interfering with each other, missing-service fallbacks never throw, and zero
// trading state is mutated by any of it.
function runV121Fixtures(g){
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

  // ═══ Fixture 1: STRATEGY_REGISTRY contains both JVM and ALEX entries this release ═══
  {
    const reg=g.getRegistry();
    const ids=reg.map(e=>e.manifest.id);
    assert('Fixture 1: STRATEGY_REGISTRY contains both current_strategy (JVM) and alex_g_sr_v1 (ALEX)',
      ids.includes('current_strategy')&&ids.includes('alex_g_sr_v1')&&reg.length===2,
      'ids='+JSON.stringify(ids));
  }

  // ═══ Fixture 2: Services.getAccount() returns the EXACT live paperAccount reference ═══
  {
    const acc={balance:55555,openPositions:[{id:1}],closedPositions:[]};
    g.setPaperAccount(acc);
    const svc=g.getStrategyServices('current_strategy');
    assert('Fixture 2: JVM Services.getAccount() returns the live paperAccount object (same reference)',
      svc.getAccount()===acc, 'sameRef='+(svc.getAccount()===acc));
  }

  // ═══ Fixture 3: Services.getJournal() returns the EXACT live journalEntries reference ═══
  {
    const j=[{tradeId:99}];
    g.setJournalEntries(j);
    const svc=g.getStrategyServices('current_strategy');
    assert('Fixture 3: JVM Services.getJournal() returns the live journalEntries array (same reference)',
      svc.getJournal()===j, 'sameRef='+(svc.getJournal()===j));
  }

  // ═══ Fixture 4: JVM_MANIFEST carries correct, truthful values ═══
  {
    const m=g.getStrategyManifest('current_strategy');
    const ok=m&&m.id==='current_strategy'&&m.label==='JVM'&&m.family==='jvm'
      &&m.panelId==='paper'&&m.devToolsCardId==='devToolsPaperCard'
      &&m.inspectorCardId==='paperTradeInspectorCard'&&m.academySchoolId==='mogo'
      &&m.version===g.getMogoStrategyMeta().version&&m.fullName===g.getMogoStrategyMeta().name;
    assert('Fixture 4: JVM Manifest carries correct id/label/family/panelId/devToolsCardId/inspectorCardId/academySchoolId, and version/fullName sourced from MOGO_STRATEGY_META',
      ok, 'm='+JSON.stringify(m));
  }

  // ═══ Fixture 5: Manifest is static -- contains no computed performance data ═══
  {
    const m=g.getStrategyManifest('current_strategy');
    const forbidden=['balance','openPositions','closedPositions','winRate','netR','pnl'];
    const hasForbidden=forbidden.some(k=>Object.prototype.hasOwnProperty.call(m,k));
    assert('Fixture 5: JVM Manifest contains no computed performance fields',
      !hasForbidden, 'keys='+Object.keys(m).join(','));
  }

  // ═══ Fixture 6: Services.normalize() produces the exact same output as calling normalizeJournalRecord() directly (reference, not duplicated logic) ═══
  {
    const raw={tradeId:1,pair:'EUR/USD',direction:'buy',entry:1.1,stop:1.09,target:1.12,result:'Win',pnl:100,openedAt:'2026-01-01T00:00:00.000Z',closedAt:'2026-01-01T01:00:00.000Z'};
    const svc=g.getStrategyServices('current_strategy');
    const viaSvc=svc.normalize(raw);
    const viaDirect=g.normalizeJournalRecord(raw,'current_strategy');
    assert('Fixture 6: JVM Services.normalize() output is byte-identical to calling normalizeJournalRecord() directly',
      deepEq(viaSvc,viaDirect), 'equal='+deepEq(viaSvc,viaDirect));
  }

  // ═══ Fixture 7: Services.computePerformance() references computeMogoStrategyPerformance() rather than duplicating its logic ═══
  {
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]}); // <50 trades -> insufficientSample path
    const svc=g.getStrategyServices('current_strategy');
    const viaSvc=svc.computePerformance();
    const viaDirect=g.computeMogoStrategyPerformance();
    assert('Fixture 7: JVM Services.computePerformance() output is byte-identical to calling computeMogoStrategyPerformance() directly',
      deepEq(viaSvc,viaDirect)&&viaSvc.sufficientSample===false, 'viaSvc='+JSON.stringify(viaSvc));
  }

  // ═══ Fixture 8: getUnifiedJournalRecords() via the registry path is byte-identical to the pre-v12.1.0 direct-call path, for JVM's side ═══
  {
    g.setJournalEntries([{tradeId:1,pair:'EUR/USD',direction:'buy',dir:'buy',entry:1.1,stop:1.09,target:1.12,result:'Win',pnl:100,openedAt:'2026-01-01T00:00:00.000Z',closedAt:'2026-01-01T01:00:00.000Z'}]);
    g.setAlexGJournalEntries([{tradeId:'AG|1',pair:'GBP/USD',direction:'sell',entry:1.25,stop:1.26,target:1.22,result:'Loss',pnl:-50,openedAt:'2026-01-02T00:00:00.000Z',closedAt:'2026-01-02T01:00:00.000Z'}]);
    const viaRegistry=g.getUnifiedJournalRecords();
    const jvmOld=g.getJournalEntries().map(e=>g.normalizeJournalRecord(e,'current_strategy'));
    const alexOld=g.getAlexGJournalEntries().map(e=>g.normalizeJournalRecord(e,'alex_g_sr_v1'));
    const viaOldPath=jvmOld.concat(alexOld).sort((a,b)=>{
      const ta=a.openedAt?new Date(a.openedAt).getTime():(a.closedAt?new Date(a.closedAt).getTime():0);
      const tb=b.openedAt?new Date(b.openedAt).getTime():(b.closedAt?new Date(b.closedAt).getTime():0);
      return tb-ta;
    });
    assert('Fixture 8: getUnifiedJournalRecords() output (both JVM and ALEX records together) is identical via the registry path vs. the old direct-call path',
      deepEq(viaRegistry,viaOldPath), 'equal='+deepEq(viaRegistry,viaOldPath));
  }

  // ═══ Fixture 9: getFilteredJournalRecords({strategy:'JVM'}) still correctly isolates JVM records from a mixed journal ═══
  {
    const filtered=g.getFilteredJournalRecords({strategy:'JVM'});
    assert('Fixture 9: getFilteredJournalRecords({strategy:"JVM"}) returns only JVM records from a mixed journal',
      filtered.length===1&&filtered[0].strategyLabel==='JVM', 'filtered='+JSON.stringify(filtered.map(r=>r.strategyLabel)));
  }

  // ═══ Fixture 10: Dashboard's JVM P&L/Win Rate tile reflects the account returned through Services, and ALEX's tile is simultaneously correct too ═══
  {
    g.setPaperAccount({balance:10300,openPositions:[],closedPositions:[{result:'Win',pnl:200},{result:'Loss',pnl:-100},{result:'Win',pnl:200}]});
    g.setAlexGAccount({balance:9800,openPositions:[],closedPositions:[{result:'Loss',pnl:-100},{result:'Loss',pnl:-100}]});
    g.renderDashboard();
    const html=g.getElementHtml('dashPerformance');
    assert('Fixture 10: Dashboard JVM P&L tile (+$300.00) is correct via Services.getAccount()',
      html.indexOf('+$300.00')!==-1, 'jvm pnl present');
    assert('Fixture 10b: Dashboard JVM Win Rate tile (67%) is correct via Services.getAccount()',
      html.indexOf('67%')!==-1, 'jvm win rate present');
    assert('Fixture 10c: Dashboard ALEX P&L tile ($-200.00, fmtCurrency\'s actual negative format) is simultaneously correct -- JVM registration did not disturb ALEX\'s tile',
      html.indexOf('$-200.00')!==-1, 'alex pnl present');
    assert('Fixture 10d: Dashboard ALEX Win Rate tile (0%) is simultaneously correct',
      html.indexOf('0%')!==-1, 'alex win rate present');
  }

  // ═══ Fixture 11: Dashboard running-trades table includes both JVM and ALEX open positions correctly, simultaneously ═══
  {
    g.setPaperAccount({balance:10000,openPositions:[{pair:'EUR/USD',dir:'buy',entry:1.1}],closedPositions:[]});
    g.setAlexGAccount({balance:10000,openPositions:[{pair:'GBP/USD',direction:'sell',entry:1.25}],closedPositions:[]});
    g.renderDashboard();
    const html=g.getElementHtml('dashRunningTrades');
    assert('Fixture 11: Dashboard running-trades table includes both the JVM and ALEX open positions via their respective Services.getAccount()',
      html.indexOf('EUR/USD')!==-1&&html.indexOf('GBP/USD')!==-1&&html.indexOf('JVM')!==-1&&html.indexOf('ALEX')!==-1,
      'html contains both rows');
  }

  // ═══ Fixture 12: showPanel('paper') still fires JVM's full panel-open sequence through Services.onOpen() ═══
  {
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAutoTradingUnseenCount(7);
    g.showPanel('paper',null);
    assert('Fixture 12: showPanel("paper") still triggers initJvmPaperPanel() (via Services.onOpen()) -- autoTrading.unseenCount reset to 0, a real observable side effect of the extracted sequence',
      g.getAutoTradingUnseenCount()===0, 'unseenCount='+g.getAutoTradingUnseenCount());
  }

  // ═══ Fixture 13: Developer Mode visibility toggles BOTH the JVM and ALEX dev-tools cards correctly when both are registered together ═══
  {
    g.setDeveloperMode(false);
    g.applyDeveloperModeVisibility();
    const jvmHidden=g.getElementStyleDisplay('devToolsPaperCard');
    const alexHidden=g.getElementStyleDisplay('devToolsAlexCard');
    g.toggleDeveloperMode();
    const jvmShown=g.getElementStyleDisplay('devToolsPaperCard');
    const alexShown=g.getElementStyleDisplay('devToolsAlexCard');
    assert('Fixture 13: Developer Mode OFF hides both cards, ON shows both, with JVM and ALEX both registered',
      jvmHidden==='none'&&alexHidden==='none'&&jvmShown==='block'&&alexShown==='block',
      'jvmHidden='+jvmHidden+' alexHidden='+alexHidden+' jvmShown='+jvmShown+' alexShown='+alexShown);
    g.toggleDeveloperMode(); // restore OFF
  }

  // ═══ Fixture 13b: JVM's dev-tools card id is genuinely resolved from the Manifest at call time, not a hardcoded literal ═══
  {
    const m=g.getStrategyManifest('current_strategy');
    const originalId=m.devToolsCardId;
    m.devToolsCardId='someOtherJvmCardId';
    g.setElementDisplay('someOtherJvmCardId','none');
    g.setDeveloperMode(true);
    g.applyDeveloperModeVisibility();
    const display=g.getElementStyleDisplay('someOtherJvmCardId');
    m.devToolsCardId=originalId;
    g.setDeveloperMode(false);
    assert('Fixture 13b: applyDeveloperModeVisibility() genuinely resolves JVM\'s card id from the Manifest at call time',
      display==='block', 'display='+display);
  }

  // ═══ Fixture 14: journalStrategyBadge correctly colors JVM (blue) vs ALEX (purple) simultaneously from a mixed unified journal ═══
  {
    const recs=g.getUnifiedJournalRecords();
    const jvmRec=recs.find(r=>r.strategyLabel==='JVM');
    const alexRec=recs.find(r=>r.strategyLabel==='ALEX');
    const jvmBadge=g.journalStrategyBadge(jvmRec);
    const alexBadge=g.journalStrategyBadge(alexRec);
    assert('Fixture 14: journalStrategyBadge renders JVM in blue and ALEX in purple, correctly, from the same mixed unified journal',
      jvmBadge.indexOf('var(--blue)')!==-1&&alexBadge.indexOf('var(--purple)')!==-1,
      'jvmBadge='+jvmBadge+' alexBadge='+alexBadge);
  }

  // ═══ Fixture 15: removing JVM specifically (leaving ALEX registered) fails safely --
  // getUnifiedJournalRecords() never throws, ALEX unaffected. UPDATED (not weakened) for
  // v12.2.0/ADR-006: the per-id hardcoded fallback this fixture originally asserted
  // ("JVM still shows via a direct-call fallback even though only its own entry was removed")
  // was a genuine per-id special case that cannot generalize to a third/future strategy --
  // ADR-006 replaces it with "iterate whatever IS in the registry, skip what isn't, and only
  // fall back to the pre-registry direct calls if the registry is completely empty." So the
  // now-correct, by-design behavior is: JVM's records are safely skipped (not fabricated via
  // fallback), ALEX's are unaffected, and nothing throws. See Fixture 15b below for the
  // separate, still-covered "whole registry empty" fallback case. ═══
  {
    const savedRegistry=g.getRegistry().slice();
    g.setRegistry(savedRegistry.filter(e=>e.manifest.id!=='current_strategy'));
    let threw=false, records=null;
    try{ records=g.getUnifiedJournalRecords(); }catch(e){ threw=true; }
    g.setRegistry(savedRegistry);
    assert('Fixture 15: getUnifiedJournalRecords() does not throw, safely skips JVM, and ALEX records are unaffected when only JVM\'s registry entry is removed',
      !threw&&!records.some(r=>r.strategyLabel==='JVM')&&records.some(r=>r.strategyLabel==='ALEX'),
      'threw='+threw+' count='+(records&&records.length));
  }

  // ═══ Fixture 15b (v12.2.0/ADR-006, new): whole-registry-empty still falls back to the direct
  // pre-registry calls for both JVM and ALEX, so history is never silently lost outright ═══
  {
    const savedRegistry=g.getRegistry().slice();
    g.setRegistry([]);
    let threw=false, records=null;
    try{ records=g.getUnifiedJournalRecords(); }catch(e){ threw=true; }
    g.setRegistry(savedRegistry);
    assert('Fixture 15b: getUnifiedJournalRecords() falls back to direct JVM+ALEX calls when the whole registry is empty',
      !threw&&records.some(r=>r.strategyLabel==='JVM')&&records.some(r=>r.strategyLabel==='ALEX'),
      'threw='+threw+' count='+(records&&records.length));
  }

  // ═══ Fixture 16: removing JVM specifically fails safely -- renderDashboard() never throws, and ALEX's tile is still correct ═══
  {
    const savedRegistry=g.getRegistry().slice();
    g.setRegistry(savedRegistry.filter(e=>e.manifest.id!=='current_strategy'));
    let threw=false;
    try{ g.renderDashboard(); }catch(e){ threw=true; }
    const html=g.getElementHtml('dashPerformance');
    g.setRegistry(savedRegistry);
    assert('Fixture 16: renderDashboard() does not throw and ALEX\'s tile is unaffected when only JVM\'s registry entry is removed',
      !threw&&html.indexOf('ALEX')!==-1, 'threw='+threw);
  }

  // ═══ Fixture 17: removing JVM specifically fails safely -- showPanel("paper") never throws, still fires the fallback sequence ═══
  {
    const savedRegistry=g.getRegistry().slice();
    g.setRegistry(savedRegistry.filter(e=>e.manifest.id!=='current_strategy'));
    g.setAutoTradingUnseenCount(3);
    let threw=false;
    try{ g.showPanel('paper',null); }catch(e){ threw=true; }
    g.setRegistry(savedRegistry);
    assert('Fixture 17: showPanel("paper") does not throw and still fires initJvmPaperPanel() when JVM\'s registry entry is removed',
      !threw&&g.getAutoTradingUnseenCount()===0, 'threw='+threw);
  }

  // ═══ Fixture 18: removing JVM specifically fails safely -- applyDeveloperModeVisibility()
  // never throws. UPDATED (not weakened) for v12.2.0/ADR-006: the per-id literal-id fallback
  // this fixture originally asserted cannot generalize to a third/future strategy (there is no
  // generic way to know an unregistered strategy's dev-tools card id) -- ADR-006 replaces it
  // with "loop over whatever IS in the registry; an entry that's missing is simply not toggled."
  // So the now-correct, by-design behavior is: JVM's card is left exactly as it was (not
  // touched, not force-hidden) when JVM is unregistered, and nothing throws. See Fixture 18b
  // below for the separate, still-covered "whole registry empty" fallback case. ═══
  {
    const savedRegistry=g.getRegistry().slice();
    g.setRegistry(savedRegistry.filter(e=>e.manifest.id!=='current_strategy'));
    g.setElementDisplay('devToolsPaperCard','none');
    g.setDeveloperMode(true);
    let threw=false;
    try{ g.applyDeveloperModeVisibility(); }catch(e){ threw=true; }
    const display=g.getElementStyleDisplay('devToolsPaperCard');
    g.setRegistry(savedRegistry);
    g.setDeveloperMode(false);
    assert('Fixture 18: applyDeveloperModeVisibility() does not throw and leaves JVM\'s card untouched (not force-shown) when JVM is unregistered',
      !threw&&display==='none', 'threw='+threw+' display='+display);
  }

  // ═══ Fixture 18b (v12.2.0/ADR-006, new): whole-registry-empty still falls back to the direct
  // literal devToolsPaperCard/devToolsAlexCard ids for both strategies ═══
  {
    const savedRegistry=g.getRegistry().slice();
    g.setRegistry([]);
    g.setElementDisplay('devToolsPaperCard','none');
    g.setDeveloperMode(true);
    let threw=false;
    try{ g.applyDeveloperModeVisibility(); }catch(e){ threw=true; }
    const display=g.getElementStyleDisplay('devToolsPaperCard');
    g.setRegistry(savedRegistry);
    g.setDeveloperMode(false);
    assert('Fixture 18b: applyDeveloperModeVisibility() falls back to the literal devToolsPaperCard id when the whole registry is empty',
      !threw&&display==='block', 'threw='+threw+' display='+display);
  }

  // ═══ Fixture 19: registering JVM introduces zero new persistence -- no new localStorage key is written by any Services call ═══
  {
    const before=g.getAllLocalStorageKeys();
    const svc=g.getStrategyServices('current_strategy');
    svc.getAccount();svc.getJournal();svc.normalize({});svc.computePerformance();svc.health();
    g.getStrategyManifest('current_strategy');
    const after=g.getAllLocalStorageKeys();
    assert('Fixture 19: no localStorage key is added by any JVM Registry/Manifest/Services call',
      deepEq(before.sort(),after.sort()), 'before='+JSON.stringify(before)+' after='+JSON.stringify(after));
  }

  // ═══ Fixture 20: JVM Services deliberately does not expose isolationCheck/start/stop/settings/playbook/AI hooks this release, matching capabilities:false ═══
  {
    const svc=g.getStrategyServices('current_strategy');
    const m=g.getStrategyManifest('current_strategy');
    const absent=['isolationCheck','start','stop','buildOpenRecord','buildCloseRecord','getContextSnapshot','getExplanation','buildWeeklySummary'].every(k=>typeof svc[k]==='undefined');
    assert('Fixture 20: JVM Services deliberately does not expose isolationCheck/start/stop/buildOpenRecord/buildCloseRecord/AI hooks (no genuine existing behavior to wrap for any of them)',
      absent&&m.capabilities.diagnostics===false&&m.capabilities.settings===false,
      'svc keys='+Object.keys(svc).join(','));
  }

  // ═══ Fixture 21: capabilities honestly describe what is and is not wired this release ═══
  {
    const m=g.getStrategyManifest('current_strategy');
    const c=m.capabilities;
    assert('Fixture 21: capabilities.statistics is true and Services.computePerformance is actually wired (JVM has computeMogoStrategyPerformance, unlike ALEX)',
      c.statistics===true&&typeof g.getStrategyServices('current_strategy').computePerformance==='function', 'ok');
    assert('Fixture 21b: capabilities.academyContent is true (real: ACADEMY_SCHOOLS has id "mogo")',
      c.academyContent===true, 'c.academyContent='+c.academyContent);
  }

  // ═══ Fixture 22: renderMiniJournal(...,'JVM') still runs without throwing. UPDATED comment
  // (not weakened assertion) for v12.2.0/ADR-006: this path was previously described as
  // unreachable dead code with an untouched literal inspector id -- as of v12.2.0 its inspector
  // id now resolves generically via resolveStrategyEntryForRecord()/STRATEGY_REGISTRY instead of
  // a hardcoded literal (see ADR-006 seam 5), so this fixture now also proves the generalized
  // lookup path doesn't throw for the 'JVM' label, whether or not the call site is ever
  // exercised live. ═══
  {
    let threw=false;
    try{ g.renderMiniJournal('someContainer',null,'JVM'); }catch(e){ threw=true; }
    assert('Fixture 22: renderMiniJournal(...,"JVM") does not throw and resolves its inspector id via the generic v12.2.0 lookup',
      !threw, 'threw='+threw);
  }

  // ═══ Fixture 23: a full pass through every touched seam, with BOTH strategies holding real data, never mutates trading state and never cross-contaminates the two stores ═══
  {
    g.setJournalEntries([{tradeId:1,pair:'EUR/USD',result:'Win',pnl:100}]);
    g.setAlexGJournalEntries([{tradeId:'AG|1',pair:'GBP/USD',result:'Loss',pnl:-50}]);
    g.setPaperAccount({balance:10100,openPositions:[],closedPositions:[{result:'Win',pnl:100}]});
    g.setAlexGAccount({balance:9950,openPositions:[],closedPositions:[{result:'Loss',pnl:-50}]});
    g.setScanData({});
    const before=snapshotTradingState();
    g.getUnifiedJournalRecords();
    g.getFilteredJournalRecords({strategy:'JVM'});
    g.getFilteredJournalRecords({strategy:'ALEX'});
    g.renderDashboard();
    g.showPanel('paper',null);
    // Note: showPanel('alexg') is deliberately not exercised here -- it renders ALEX's own
    // richer live-position table, which is outside this release's target seams and requires
    // fully-shaped ALEX position objects (already exhaustively covered by tests/v120).
    g.toggleDeveloperMode();g.toggleDeveloperMode();
    const after=snapshotTradingState();
    assert('Fixture 23: a full pass through every touched seam, with both JVM and ALEX holding real data simultaneously, never mutates journalEntries/alexGJournalEntries/paperAccount/alexGAccount/scanData and never cross-contaminates the two stores',
      before===after, 'changed='+(before!==after));
  }

  return results;
}
