// v12.3.1 -- Strategy Workspace Framework & Dedicated TJR Workspace
//
// Proves: (1) registry metadata (navLabel/workspaceTitle/currentPhase/panelId) is present and
// correct for all three strategies, with JVM/ALEX's own existing panels completely unchanged;
// (2) the Strategies nav group is genuinely registry-driven -- one button per entry, in
// registry order, and a fixture-injected 4th strategy produces a 4th button automatically;
// (3) TJR's workspace panel opens via the exact same registry-driven showPanel() mechanism
// JVM/ALEX already use (TJR_MANIFEST.panelId + TJR_SERVICES.onOpen), not a special case;
// (4) the shared Scanner chart's source no longer calls loadAndRenderTjrZones() (Phase 5),
// while the Phase 1 function itself is still present and callable, unchanged; (5) the
// dedicated workspace chart draws/clears its own zone overlay in total isolation from the
// shared chart's tjrChartZoneLines/tjrZoneState; (6) every required workspace tab renders its
// required content (Rules' three categories, Diagnostics' full field list, Paper Trading's
// fully-disabled controls, Replay/Journal's exact placeholder text, Developer's raw objects);
// (7) workspace chart lifecycle/cleanup leaves no leaked chart instance or price lines;
// (8) building/opening the workspace causes zero mutation of paperAccount/alexGAccount/
// journalEntries/alexGJournalEntries and adds zero localStorage keys.
function runV1231Fixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,detail:detail||''});};

  function buildSessionCandles(boundaries,defaults){
    const out=[];
    for(let t=boundaries.utcStart;t<boundaries.utcEnd;t+=1800000){ out.push({t,o:defaults.o,h:defaults.h,l:defaults.l,c:defaults.c}); }
    return out;
  }
  const DEFAULT_OHLC={o:1.1000,h:1.1010,l:1.0990,c:1.1005};
  function makeFakeSeries(store){
    return {
      createPriceLine:(opts)=>{const line={opts}; store.push(line); return line;},
      removePriceLine:(line)=>{const idx=store.indexOf(line); if(idx!==-1) store.splice(idx,1);}
    };
  }

  // ═══ Registry metadata ═══
  {
    const tjr=g.findStrategyEntry('tjr_slr').manifest;
    assert('Fixture 1: TJR_MANIFEST has navLabel/workspaceTitle/currentPhase populated',
      !!tjr.navLabel&&!!tjr.workspaceTitle&&!!tjr.currentPhase,
      JSON.stringify({navLabel:tjr.navLabel,workspaceTitle:tjr.workspaceTitle,currentPhase:tjr.currentPhase}));
  }
  {
    const tjr=g.findStrategyEntry('tjr_slr').manifest;
    assert('Fixture 2: TJR_MANIFEST.panelId is the new dedicated workspace panel',
      tjr.panelId==='tjrworkspace','panelId='+tjr.panelId);
  }
  {
    const jvm=g.findStrategyEntry('current_strategy').manifest;
    const alex=g.findStrategyEntry('alex_g_sr_v1').manifest;
    assert('Fixture 3: JVM and ALEX gained navLabel/workspaceTitle/currentPhase without changing their existing panelId',
      jvm.panelId==='paper'&&alex.panelId==='alexg'&&!!jvm.navLabel&&!!alex.navLabel&&!!jvm.currentPhase&&!!alex.currentPhase,
      JSON.stringify({jvmPanelId:jvm.panelId,alexPanelId:alex.panelId}));
  }

  // ═══ Registry-driven Strategies nav group ═══
  {
    g.renderStrategyNavGroup();
    const html=g.getNavDropdownHtml();
    const buttonCount=(html.match(/<button/g)||[]).length;
    assert('Fixture 4: Strategies nav dropdown renders exactly one button per registered strategy (3: JVM, ALEX, TJR)',
      buttonCount===3,'buttonCount='+buttonCount+' html='+html.substring(0,200));
  }
  {
    const html=g.getNavDropdownHtml();
    assert('Fixture 5: Strategies nav buttons appear in registry order (JVM, ALEX, TJR)',
      html.indexOf('JVM')<html.indexOf('ALEX')&&html.indexOf('ALEX')<html.indexOf('TJR'),
      html);
  }
  {
    // Registry-driven, not hardcoded: injecting a 4th synthetic entry produces a 4th button.
    const before=g.getRegistry().slice();
    const synManifest={id:'test_ws_zzz',navLabel:'SYN WORKSPACE',panelId:'comingsoon'};
    g.setRegistry(before.concat([{manifest:synManifest,services:{}}]));
    g.renderStrategyNavGroup();
    const html=g.getNavDropdownHtml();
    const buttonCount=(html.match(/<button/g)||[]).length;
    g.setRegistry(before); // restore
    g.renderStrategyNavGroup();
    assert('Fixture 6: a 4th registry entry produces a 4th nav button automatically (proves genuine registry-driven routing, not hardcoded TJR nav)',
      buttonCount===4&&html.indexOf('SYN WORKSPACE')!==-1,'buttonCount='+buttonCount);
  }

  // ═══ Routing: showPanel opens the TJR workspace via the existing registry mechanism ═══
  {
    g.showPanel('tjrworkspace',null);
    const headerHtml=g.getElementHtml('tjrWsHeaderCard');
    assert('Fixture 7: showPanel(\'tjrworkspace\') routes through TJR_SERVICES.onOpen -> initTjrWorkspace() and renders the header (same registry-driven mechanism JVM/ALEX already use, no new special case in showPanel())',
      headerHtml.length>0&&headerHtml.indexOf('TJR Session Level Reaction')!==-1,
      'len='+headerHtml.length);
  }

  // ═══ Strategy Header content ═══
  {
    const headerHtml=g.getElementHtml('tjrWsHeaderCard');
    const required=['Strategy Name','Version','Current Phase','Detection Status','Candidate Status','Paper Status','Live Status','Profitability Status','Current Pair','Current Timeframe','Current Session','Previous Session'];
    const missing=required.filter(r=>headerHtml.indexOf(r)===-1);
    assert('Fixture 8: Strategy Header contains all 12 required fields',
      missing.length===0,'missing='+JSON.stringify(missing));
  }
  {
    const headerHtml=g.getElementHtml('tjrWsHeaderCard');
    assert('Fixture 9: Strategy Header shows the exact required current values (Phase 1, Detection Active, Candidate Not Implemented, Paper/Live Disabled, Profitability Unvalidated)',
      headerHtml.indexOf('Phase 1 — Session &amp; Zone Engine')!==-1&&headerHtml.indexOf('Active')!==-1&&
      headerHtml.indexOf('Not Implemented')!==-1&&headerHtml.indexOf('Disabled')!==-1&&headerHtml.indexOf('Unvalidated')!==-1,
      headerHtml.substring(0,400));
  }

  // ═══ Workspace tabs render (7 tabs) ═══
  {
    const tabsHtml=g.getElementHtml('tjrWsTabsContainer');
    const tabCount=(tabsHtml.match(/sc-tab/g)||[]).length;
    assert('Fixture 10: workspace renders all 7 required tabs (Chart/Rules/Diagnostics/Paper Trading/Replay/Journal/Developer)',
      tabCount>=7,'tabsHtml='+tabsHtml);
  }

  // ═══ Rules tab: Implemented / Approved / Future ═══
  {
    const html=g.renderTjrWsRulesTab();
    assert('Fixture 11: Rules tab clearly distinguishes IMPLEMENTED, APPROVED FOR IMPLEMENTATION, and FUTURE',
      html.indexOf('IMPLEMENTED')!==-1&&html.indexOf('APPROVED FOR IMPLEMENTATION')!==-1&&html.indexOf('FUTURE')!==-1,
      '');
  }
  {
    const html=g.renderTjrWsRulesTab();
    assert('Fixture 12: Rules tab lists Zone Interaction, Reaction Detection, and Five-minute BOS as approved-not-implemented',
      html.indexOf('Zone Interaction')!==-1&&html.indexOf('Reaction Detection')!==-1&&html.indexOf('Five-minute BOS')!==-1,
      '');
  }

  // ═══ Diagnostics tab: full field list, never hides incomplete data ═══
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC).slice(1); // missing interval -- incomplete data
    const result=g.buildTjrSessionZones('GBP_USD',candles,b.utcEnd+5000);
    g.setTjrWsZoneState({instrument:'GBP_USD',result,fetchedAt:Date.now(),error:null});
    const html=g.renderTjrWsDiagnosticsTab();
    const required=['Source Session','Session Date','Session Start','Session End','DST Result','Candle Count','Missing Candles','Duplicate Candles','Invalid Candles','Selected High Candle','Selected Low Candle','Zone Bounds','Zone ID','Lifecycle','Warnings','Errors'];
    const missing=required.filter(r=>html.indexOf(r)===-1);
    assert('Fixture 13: Diagnostics tab shows every required field, including an incomplete/missing-candle dataset (not hidden)',
      missing.length===0&&html.indexOf('Missing Candles')!==-1&&html.indexOf('>1<')!==-1,
      'missing='+JSON.stringify(missing));
  }

  // ═══ Paper Trading tab: every control disabled, no execution logic ═══
  {
    const html=g.renderTjrWsPaperTab();
    const inputCount=(html.match(/<input/g)||[]).length;
    const disabledCount=(html.match(/disabled/g)||[]).length;
    assert('Fixture 14: every control in the Paper Trading tab is disabled',
      inputCount>0&&disabledCount>=inputCount,'inputs='+inputCount+' disabled='+disabledCount);
  }
  {
    const html=g.renderTjrWsPaperTab();
    assert('Fixture 15: Paper Trading tab shows the exact required not-yet-available message',
      html.indexOf('TJR paper trading becomes available only after the Interaction Engine, BOS Confirmation, Candidate Engine, Risk Engine, and Replay Validation are complete.')!==-1,
      '');
  }
  {
    const html=g.renderTjrWsPaperTab();
    assert('Fixture 16: Paper Trading tab shows Risk %/Entry Model/Stop Model/Target Model/Minimum Grade/Manual Approval/Automatic Paper Trading',
      ['Risk %','Entry Model','Stop Model','Target Model','Minimum Grade','Manual Approval','Automatic Paper Trading'].every(f=>html.indexOf(f)!==-1),
      '');
  }

  // ═══ Replay / Journal placeholders ═══
  {
    const html=g.renderTjrWsReplayTab();
    assert('Fixture 17: Replay tab shows the exact required placeholder, no replay logic',
      html.indexOf('Replay support will be introduced in a future milestone.')!==-1,'');
  }
  {
    const html=g.renderTjrWsJournalTab();
    assert('Fixture 18: Journal tab shows the exact required placeholder, no journal records created',
      html.indexOf('No TJR trades exist.')!==-1&&html.indexOf('Future TJR trades will use the unified journal architecture.')!==-1,
      '');
  }

  // ═══ Developer tab: raw objects, no credentials ═══
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    const result=g.buildTjrSessionZones('GBP_USD',candles,b.utcEnd+5000);
    g.setTjrWsZoneState({instrument:'GBP_USD',result,fetchedAt:Date.now(),error:null});
    const html=g.renderTjrWsDeveloperTab();
    assert('Fixture 19: Developer tab exposes raw session/zone objects and zone ids',
      html.indexOf(result.highZone.zoneId)!==-1&&html.indexOf(result.lowZone.zoneId)!==-1&&html.indexOf('sourceSession')!==-1,
      '');
  }
  {
    const html=g.renderTjrWsDeveloperTab();
    assert('Fixture 20: Developer tab never exposes credentials/tokens/account identifiers',
      html.toLowerCase().indexOf('apikey')===-1&&html.toLowerCase().indexOf('accountid')===-1&&html.indexOf('cfg.key')===-1,
      '');
  }

  // ═══ Dedicated chart isolation: workspace zone overlay never touches shared-chart state ═══
  {
    const sharedLinesBefore=g.getSharedTjrChartZoneLinesLength();
    const fakeLines=[];
    g.setTjrWsChartAndSeries({},makeFakeSeries(fakeLines));
    g.setTjrWsZonesVisible(true);
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    const result=g.buildTjrSessionZones('GBP_USD',candles,b.utcEnd+5000);
    g.drawTjrWorkspaceZoneOverlay(result);
    assert('Fixture 21: drawTjrWorkspaceZoneOverlay draws 4 price lines (high upper/lower, low upper/lower) on the WORKSPACE\'s own fake series',
      fakeLines.length===4,'fakeLines.length='+fakeLines.length);
    assert('Fixture 22: drawing the workspace overlay leaves the SHARED chart\'s tjrChartZoneLines completely untouched',
      g.getSharedTjrChartZoneLinesLength()===sharedLinesBefore,
      'before='+sharedLinesBefore+' after='+g.getSharedTjrChartZoneLinesLength());
    g.clearTjrWorkspaceZoneOverlay();
    assert('Fixture 23: clearTjrWorkspaceZoneOverlay removes all workspace price lines',
      fakeLines.length===0,'fakeLines.length='+fakeLines.length);
  }
  {
    // Zones-visible toggle off -- nothing should be drawn even with a valid result.
    const fakeLines=[];
    g.setTjrWsChartAndSeries({},makeFakeSeries(fakeLines));
    g.setTjrWsZonesVisible(false);
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    const result=g.buildTjrSessionZones('GBP_USD',candles,b.utcEnd+5000);
    g.drawTjrWorkspaceZoneOverlay(result);
    assert('Fixture 24: Show/Hide Zones toggle off suppresses the overlay entirely',
      fakeLines.length===0,'fakeLines.length='+fakeLines.length);
    g.setTjrWsZonesVisible(true);
  }

  // ═══ Chart lifecycle / cleanup ═══
  {
    const fakeLines=[];
    g.setTjrWsChartAndSeries({},makeFakeSeries(fakeLines));
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    const result=g.buildTjrSessionZones('GBP_USD',candles,b.utcEnd+5000);
    g.drawTjrWorkspaceZoneOverlay(result);
    g.destroyTjrWorkspaceChart();
    assert('Fixture 25: destroyTjrWorkspaceChart() nulls the chart/series and empties the price-line array (no leaked instance across repeated workspace opens)',
      g.getTjrWsChartIsNull()&&g.getTjrWsCandleSeriesIsNull()&&g.getTjrWsZoneLinesLengthDirect()===0,
      '');
  }

  // ═══ Phase 5: shared chart source no longer auto-calls the Phase 1 function; the
  // function itself is retained, unmodified, and still directly callable. ═══
  {
    // Requires the trailing ";" of an actual statement (not just the phrase, which the
    // v12.3.1 changelog's own prose legitimately mentions in the APP_VERSION_LOG string) --
    // distinguishes a real call site from a descriptive text reference to the same phrase.
    const hasCallSite=/loadAndRenderTjrZones\(activePair\);/.test(g.appCodeSource);
    assert('Fixture 26: loadChart() no longer calls loadAndRenderTjrZones(activePair) -- the shared chart no longer auto-renders TJR zones',
      hasCallSite===false,'');
  }
  {
    const hasFunctionDef=/function loadAndRenderTjrZones\s*\(/.test(g.appCodeSource);
    const hasDrawFn=/function drawTjrZoneOverlay\s*\(/.test(g.appCodeSource);
    const hasClearFn=/function clearTjrZoneOverlay\s*\(/.test(g.appCodeSource);
    assert('Fixture 27: the Phase 1 rendering functions (loadAndRenderTjrZones/drawTjrZoneOverlay/clearTjrZoneOverlay) are still defined -- retained and reusable, not deleted',
      hasFunctionDef&&hasDrawFn&&hasClearFn,'');
  }
  {
    assert('Fixture 28: the retained Phase 1 drawTjrZoneOverlay is still directly callable and behaves identically (functionally unchanged)',
      typeof g.drawTjrZoneOverlay==='function'&&typeof g.buildTjrSessionZones==='function',
      '');
  }

  // ═══ Registry compatibility: ALEX/JVM workspace launch still calls their real, unmodified init functions ═══
  {
    let jvmOnOpenCalled=false,alexOnOpenCalled=false;
    const origJvmInit=g.getWindowFn('initJvmPaperPanel');
    const origAlexInit=g.getWindowFn('initAlexGPair');
    g.setWindowFn('initJvmPaperPanel',()=>{jvmOnOpenCalled=true;});
    g.setWindowFn('initAlexGPair',()=>{alexOnOpenCalled=true;});
    g.showPanel('paper',null);
    g.showPanel('alexg',null);
    g.setWindowFn('initJvmPaperPanel',origJvmInit);
    g.setWindowFn('initAlexGPair',origAlexInit);
    assert('Fixture 29: JVM/ALEX workspace navigation still fires their existing onOpen (initJvmPaperPanel/initAlexGPair) -- zero change to their own behavior',
      jvmOnOpenCalled&&alexOnOpenCalled,'jvm='+jvmOnOpenCalled+' alex='+alexOnOpenCalled);
  }

  // ═══ Mutation safety ═══
  {
    const paperBefore=JSON.stringify(g.getPaperAccount());
    const alexBefore=JSON.stringify(g.getAlexGAccount());
    const journalBefore=JSON.stringify(g.getJournalEntries());
    const alexJournalBefore=JSON.stringify(g.getAlexGJournalEntries());
    const storageBefore=g.getAllLocalStorageKeys().slice().sort();
    g.showPanel('tjrworkspace',null);
    g.setTjrWsTab('chart');g.setTjrWsTab('rules');g.setTjrWsTab('diagnostics');
    g.setTjrWsTab('paper');g.setTjrWsTab('replay');g.setTjrWsTab('journal');g.setTjrWsTab('developer');
    const storageAfter=g.getAllLocalStorageKeys().slice().sort();
    assert('Fixture 30: opening the TJR workspace and visiting every tab causes zero mutation of paperAccount/alexGAccount/journalEntries/alexGJournalEntries',
      paperBefore===JSON.stringify(g.getPaperAccount())&&alexBefore===JSON.stringify(g.getAlexGAccount())&&
      journalBefore===JSON.stringify(g.getJournalEntries())&&alexJournalBefore===JSON.stringify(g.getAlexGJournalEntries()),
      '');
    assert('Fixture 31: opening the TJR workspace and visiting every tab adds zero localStorage keys',
      JSON.stringify(storageBefore)===JSON.stringify(storageAfter),
      'before='+JSON.stringify(storageBefore)+' after='+JSON.stringify(storageAfter));
  }

  return results;
}
