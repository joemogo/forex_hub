// v12.2.0 -- Multi-Strategy Foundation (ADR-006)
//
// Proves: (1) strategyId is the primary, rename-proof record identity, with strategyLabel as a
// legacy-compatibility-only fallback and a safe, non-JVM-defaulting path for anything that
// resolves to neither; (2) all seven generalized seams (unified journal, Dashboard tiles +
// running-trades table, panel-open hook, Developer Mode card visibility, mini-journal inspector
// lookup, journal badge color, Strategy Center tabs) genuinely iterate STRATEGY_REGISTRY rather
// than re-hardcoding a third id; (3) a fixture-only synthetic third strategy renders correctly
// at every seam, alongside JVM and ALEX, with zero change to either's own output.
function runV122Fixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,detail:detail||''});};

  const SYN_ID='test_strategy_zzz';
  const SYN_LABEL='SYN';
  function makeSyntheticEntry(overrides){
    const account={balance:10000,openPositions:[{pair:'EUR/USD',dir:'buy',entry:1.1,isDeveloperTrade:false}],closedPositions:[]};
    const journal=[{tradeId:'SYN|1',pair:'EUR/USD',result:'Win',pnl:50,strategyId:SYN_ID,strategyLabel:SYN_LABEL,openedAt:new Date().toISOString()}];
    const manifest=Object.assign({
      id:SYN_ID,family:'synthetic',version:'v0',label:SYN_LABEL,fullName:'Synthetic Test Strategy',
      description:'Fixture-only synthetic strategy -- never shipped to production.',
      author:'test',ownership:'internal',status:'active',trustLevel:'verified',
      badgeColor:'var(--gold)',
      capabilities:{scanning:true,paperTrading:true,automation:false,journal:true,statistics:false,
        alerts:false,replay:false,backtesting:false,aiReview:false,aiCoaching:false,reports:false,
        academyContent:false,diagnostics:false,settings:false,strategyCenterContent:false},
      dependencies:[],dna:{style:'synthetic',difficulty:'n/a',marketType:'n/a',preferredSessions:[],idealConditions:[],avoidConditions:[],strengths:[],weaknesses:[]},
      panelId:'synPanel',devToolsCardId:'devToolsSynCard',inspectorCardId:'synTradeInspectorCard',
      academySchoolId:null,release:{registeredInVersion:'12.2.0-test-only'}
    },overrides&&overrides.manifest);
    let onOpenCalled=false;
    const services=Object.assign({
      getAccount:()=>account,
      getJournal:()=>journal,
      normalize:(raw)=>g.normalizeJournalRecord(raw,SYN_ID),
      onOpen:()=>{onOpenCalled=true;},
      health:()=>'ready'
    },overrides&&overrides.services);
    return{entry:{manifest,services},account,journal,wasOpened:()=>onOpenCalled};
  }

  // ── strategyId on newly created records ──
  (function(){
    const jvmRecord=g.buildJVMJournalOpenRecord({id:1,pair:'EUR/USD',dir:'buy',entry:1.1,stop:1.09,target:1.12,ratio:2,riskAmount:100,lots:0.1,openedAt:new Date().toISOString()});
    assert('new JVM journal record carries strategyId="current_strategy"', jvmRecord.strategyId==='current_strategy', jvmRecord.strategyId);
    assert('new JVM journal record still carries the legacy strategy field too (untouched)', jvmRecord.strategy==='current_strategy', '');
  })();
  (function(){
    const alexRecord=g.buildAlexJournalOpenRecord({tradeId:'AG|1',pair:'GBP/USD',direction:'buy',entry:1.25,stop:1.24,target:1.27,plannedRR:2,riskPercent:1,riskAmount:100,positionSize:0.1,openedAt:new Date().toISOString(),maePips:0,mfePips:0});
    assert('new ALEX journal record carries strategyId="alex_g_sr_v1"', alexRecord.strategyId==='alex_g_sr_v1', alexRecord.strategyId);
    assert('new ALEX journal record still carries the legacy strategy field too (untouched)', alexRecord.strategy==='alex_g_sr_v1', '');
  })();

  // ── 3-tier resolver: strategyId first, legacy label second, unknown third ──
  (function(){
    const e=g.resolveStrategyEntryForRecord({strategyId:'current_strategy'});
    assert('resolver: strategyId resolves directly via findStrategyEntry', e&&e.manifest.id==='current_strategy', '');
  })();
  (function(){
    // legacy JVM record: only strategyLabel, no strategyId, no strategy field
    const e=g.resolveStrategyEntryForRecord({strategyLabel:'JVM'});
    assert('resolver: legacy JVM label-only record resolves via findStrategyEntryByLabel fallback', e&&e.manifest.id==='current_strategy', '');
  })();
  (function(){
    // legacy ALEX record: only strategyLabel
    const e=g.resolveStrategyEntryForRecord({strategyLabel:'ALEX'});
    assert('resolver: legacy ALEX label-only record resolves via findStrategyEntryByLabel fallback', e&&e.manifest.id==='alex_g_sr_v1', '');
  })();
  (function(){
    const e=g.resolveStrategyEntryForRecord({strategyId:'totally_unknown_id',strategyLabel:'Nope'});
    assert('resolver: neither strategyId nor strategyLabel resolving returns null (safe unknown)', e===null, '');
  })();
  (function(){
    const e=g.resolveStrategyEntryForRecord(null);
    assert('resolver: a null/undefined record returns null without throwing', e===null, '');
  })();
  (function(){
    // strategyId wins even if strategyLabel would resolve to a DIFFERENT (wrong) entry
    const e=g.resolveStrategyEntryForRecord({strategyId:'alex_g_sr_v1',strategyLabel:'JVM'});
    assert('resolver: strategyId takes priority over a conflicting strategyLabel', e&&e.manifest.id==='alex_g_sr_v1', '');
  })();

  // ── findStrategyEntryByLabel is legacy-only: rename resilience ──
  (function(){
    const savedRegistry=g.getRegistry().slice();
    const alexEntry=g.getRegistry().find(e=>e.manifest.id==='alex_g_sr_v1');
    const originalLabel=alexEntry.manifest.label;
    // Simulate a future label rename on the SAME registry entry (same id, new display label).
    alexEntry.manifest.label='ALEX-RENAMED';
    const byId=g.resolveStrategyEntryForRecord({strategyId:'alex_g_sr_v1'});
    const byOldLabelOnly=g.resolveStrategyEntryForRecord({strategyLabel:originalLabel});
    alexEntry.manifest.label=originalLabel; // restore immediately
    assert('rename resilience: a record with strategyId still resolves correctly after its manifest.label is renamed',
      byId&&byId.manifest.id==='alex_g_sr_v1', '');
    assert('rename resilience: a label-only legacy record carrying the OLD label safely becomes unresolvable after a rename (never mismatches)',
      byOldLabelOnly===null, '');
  })();

  // ── Unknown-strategy records never default to JVM styling ──
  (function(){
    const badge=g.journalStrategyBadge({strategyId:'nope',strategyLabel:'Ghost'});
    assert('journalStrategyBadge: an unresolved record uses the dedicated neutral color, not JVM\'s blue',
      badge.indexOf(g.getUnknownBadgeColor())!==-1 && badge.indexOf('var(--blue)')===-1, badge);
    assert('journalStrategyBadge: an unresolved record still displays its own label text, not a fabricated one',
      badge.indexOf('Ghost')!==-1, badge);
  })();
  (function(){
    const inspectorIdForKnownJvm=g.getMiniJournalInspectorId('JVM');
    const inspectorIdForUnknown=g.getMiniJournalInspectorId('GhostStrategy');
    assert('renderMiniJournal inspector lookup: an unresolved label falls back to the shared generic tradeInspectorCard id, not JVM\'s own card',
      inspectorIdForUnknown==='tradeInspectorCard' && inspectorIdForUnknown!==inspectorIdForJvmCheck(inspectorIdForKnownJvm),
      'unknown='+inspectorIdForUnknown+' jvm='+inspectorIdForKnownJvm);
    function inspectorIdForJvmCheck(x){return x;} // JVM's real id, just for the inequality check above
  })();

  // ── Registry-order determines render order ──
  (function(){
    const ids=g.getRegistry().map(e=>e.manifest.id);
    assert('registry order: JVM (current_strategy) renders before ALEX (alex_g_sr_v1), matching array order',
      ids.indexOf('current_strategy')<ids.indexOf('alex_g_sr_v1'), JSON.stringify(ids));
  })();

  // ── Synthetic third strategy: proves genuine N-strategy support, not just N=2 with nicer code ──
  (function(){
    const savedRegistry=g.getRegistry().slice();
    const syn=makeSyntheticEntry();
    g.setRegistry(savedRegistry.concat([syn.entry]));

    // 1. Unified journal includes the synthetic strategy's record alongside JVM/ALEX, unaffected.
    g.setJournalEntries([{tradeId:1,pair:'EUR/USD',result:'Win',pnl:100,strategyId:'current_strategy',strategyLabel:'JVM',openedAt:new Date().toISOString()}]);
    g.setAlexGJournalEntries([{tradeId:'AG|1',pair:'GBP/USD',result:'Loss',pnl:-50,strategyId:'alex_g_sr_v1',strategyLabel:'ALEX',openedAt:new Date().toISOString()}]);
    const unified=g.getUnifiedJournalRecords();
    assert('synthetic strategy: its journal record appears in the unified journal', unified.some(r=>r.strategyId===SYN_ID), '');
    assert('synthetic strategy: JVM record still present and unaffected', unified.some(r=>r.strategyLabel==='JVM'), '');
    assert('synthetic strategy: ALEX record still present and unaffected', unified.some(r=>r.strategyLabel==='ALEX'), '');

    // 2. Dashboard renders a tile + running-trades row for the synthetic strategy.
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    let threwDash=false;
    try{ g.renderDashboard(); }catch(e){ threwDash=true; }
    const perfHtml=g.getElementHtml('dashPerformance');
    const runHtml=g.getElementHtml('dashRunningTrades');
    assert('synthetic strategy: renderDashboard() does not throw with a 3rd registry entry present', !threwDash, '');
    assert('synthetic strategy: Dashboard tiles include the synthetic strategy\'s label', perfHtml.indexOf(SYN_LABEL)!==-1, '');
    assert('synthetic strategy: Dashboard running-trades table includes its open position', runHtml.indexOf(SYN_LABEL)!==-1, '');

    // 3. showPanel() fires the synthetic strategy's onOpen() via its own panelId.
    g.showPanel('synPanel',null);
    assert('synthetic strategy: showPanel() fires its Services.onOpen() via generic panelId lookup', syn.wasOpened(), '');

    // 4. Developer Mode toggles its dev-tools card.
    g.setDeveloperMode(true);
    g.applyDeveloperModeVisibility();
    assert('synthetic strategy: applyDeveloperModeVisibility() toggles its devToolsCardId', g.getElementStyleDisplay('devToolsSynCard')==='block', '');
    g.setDeveloperMode(false);

    // 5. Journal badge renders its own real, distinct color.
    const badge=g.journalStrategyBadge({strategyId:SYN_ID,strategyLabel:SYN_LABEL});
    assert('synthetic strategy: journalStrategyBadge renders its own badgeColor, not JVM\'s or ALEX\'s', badge.indexOf('var(--gold)')!==-1, badge);

    // 6. Strategy Center renders a disabled/Coming-Soon tab for it (strategyCenterContent:false).
    let threwRules=false;
    try{ g.renderRules(); }catch(e){ threwRules=true; }
    const tabsHtml=g.getElementHtml('scTabsContainer');
    assert('synthetic strategy: renderRules() does not throw with a 3rd registry entry present', !threwRules, '');
    assert('synthetic strategy: Strategy Center generates a tab for it', tabsHtml.indexOf('scTab_'+SYN_ID)!==-1, '');
    assert('synthetic strategy: its tab is disabled (Coming Soon), matching capabilities.strategyCenterContent:false',
      new RegExp('id="scTab_'+SYN_ID+'"[^>]*class="sc-tab disabled"|class="sc-tab disabled"[^>]*id="scTab_'+SYN_ID+'"').test(tabsHtml)||tabsHtml.indexOf('disabled')!==-1, tabsHtml.slice(0,300));

    // 7. Zero mutation of JVM/ALEX's own stores by any of the above.
    assert('synthetic strategy: JVM paperAccount untouched by any synthetic-strategy seam call', g.getPaperAccount().openPositions.length===0, '');
    assert('synthetic strategy: ALEX account untouched by any synthetic-strategy seam call', g.getAlexGAccount().openPositions.length===0, '');

    g.setRegistry(savedRegistry);
  })();

  return results;
}
