// ══════════════════════════════════════════════════════════════════════════════════════════
// v12.3.9 — CHART / AOI FIDELITY FIXTURES
//
// THE PROPERTY THIS SUITE PROTECTS: what the chart DRAWS must agree with what the engine
// DECIDED, and the scanner must actually visit every configured instrument and timeframe.
//
// Every fixture below follows one shape:
//     seed isolated in-memory state (or serve OANDA-shaped candles at the fetch boundary)
//     ->  call the REAL chart / render / sweep function
//     ->  read back the exact drawn price levels, series titles, markers or rendered HTML
//     ->  assert a literal computed BY HAND in this file.
//
// THE AOI ARITHMETIC IS DONE ON PAPER, NOT RE-DERIVED. The Daily series built by
// dailyAoiCandles() below is deliberately constructed so every number computeAOI can produce
// is derivable without running it:
//     highest high 1.25000, lowest low 1.15000            -> window range          0.10000
//     range*0.04 = 0.00400 ; currentPrice*0.001 = 0.00120 -> clustering tolerance  0.00400
//     swing lows  : 1.17000 x3, 1.16000 x3, 1.19000 x2, 1.15000 x1
//     swing highs : 1.24000 x3, 1.22000 x2, 1.25000 x1
//     last close  : 1.20000
//   -> the only support cluster with 3+ touches BELOW price and nearest to it is 1.17000
//   -> the only resistance cluster with 3+ touches ABOVE price and nearest to it is 1.24000
//   -> the drawn band half-width is max(band 0.00400, 3 pips 0.00030) = 0.00400
//   -> therefore the support band is drawn at 1.17400 / 1.16600 and the resistance band at
//      1.24400 / 1.23600. Those four numbers are the literals asserted below. Nothing in
//      this file re-runs clusterLevels, findSwingPoints or computeAOI to produce them.
//
// RULES THIS FILE OBEYS:
//   * NO source-text assertions. Nothing here reads index.html or matches a function body.
//     The one pre-existing fixture that claimed to protect the chart-versus-engine property
//     (v13.0 CHART-3) does exactly that, and survives every behavioural mutation below.
//   * NO presence-only assertions. A drawn line is never asserted merely to exist -- an AOI
//     drawn at the wrong price, inverted, or on the wrong side is still a drawn line.
//   * NO self-consistency and NO implementation-mirroring. Expected levels are literals.
//   * NO "covered but wired to nothing". computeAOI/computeAOIWithTouches/the zone engine are
//     never called directly to prove they work -- they are asserted THROUGH loadChart() and
//     the real per-instrument sweep, so deleting the draw call fails the fixture too.
//   * Every fixture is paired with a mutation that makes it FAIL (see the campaign report).
//
// NO REAL PAPER TRADE IS PERSISTED BY THIS SUITE. All state is in-memory; localStorage and
// fetch are stubs; the process has no access to any real saved data.
// ══════════════════════════════════════════════════════════════════════════════════════════
async function runChartAoiFidelityFixtures(g){
  const results=[];
  const assert=(name,desc,cond,detail)=>{results.push({name,desc,pass:!!cond,detail:detail||''});};
  const note=(name,desc,detail)=>{results.push({name,desc,pass:null,detail:detail||''});};
  const near=(a,b)=>a!=null&&b!=null&&Math.abs(a-b)<1e-9;
  // loadChart() deliberately does NOT await the structural-AOI fetch -- the band is drawn from a
  // fire-and-forget promise so a slow D/W response can never hold up the candles. The fixture
  // therefore drains the microtask queue after each load, which is what a real browser tick does.
  const settle=async function(){ for(let i=0;i<200;i++) await Promise.resolve(); };

  // ── candle construction ────────────────────────────────────────────────────────────────
  // Fillers are byte-identical to each other, so a filler can never itself be a swing point
  // (the frozen swing test requires a STRICT extremity against all `lookback` neighbours on
  // both sides). Each special bar differs from its neighbours on exactly one side of the bar.
  const DAY=86400000, HOUR=3600000;
  const T0=Date.UTC(2025,0,1,0,0,0);
  function mk(t,o,h,l,c){ return{t:new Date(t),o:o,h:h,l:l,c:c}; }
  function dailyAoiCandles(spec){
    const out=[];
    const push=(o,h,l,c)=>out.push(mk(T0+out.length*DAY,o,h,l,c));
    const filler=n=>{ for(let i=0;i<n;i++) push(1.20400,1.20800,1.20200,1.20400); };
    const swingLow=l=>push(1.20400,1.20800,l,1.20400);
    const swingHigh=h=>push(1.20400,h,1.20200,1.20400);
    filler(4);
    spec.forEach(s=>{ if(s[0]==='L') swingLow(s[1]); else swingHigh(s[1]); filler(4); });
    while(out.length<99) filler(1);
    push(1.20400,1.20800,1.20200,1.20000); // final close == current price 1.20000
    return out;
  }
  // The reference Daily window described in the header comment.
  const AOI_SPEC_REFERENCE=[
    ['L',1.17000],['L',1.17000],['L',1.17000],
    ['L',1.16000],['L',1.16000],['L',1.16000],
    ['L',1.19000],['L',1.19000],              // exactly 2 touches -- below the frozen minimum
    ['L',1.15000],                            // window low, a single touch
    ['H',1.24000],['H',1.24000],['H',1.24000],
    ['H',1.22000],['H',1.22000],              // exactly 2 touches -- below the frozen minimum
    ['H',1.25000]                             // window high, a single touch
  ];
  // Same window, but the nearer support cluster now has exactly the minimum touch count.
  const AOI_SPEC_MIN_TOUCHES=[
    ['L',1.17000],['L',1.17000],['L',1.17000],
    ['L',1.16000],['L',1.16000],['L',1.16000],
    ['L',1.19000],['L',1.19000],['L',1.19000], // promoted to exactly 3
    ['L',1.15000],
    ['H',1.24000],['H',1.24000],['H',1.24000],
    ['H',1.22000],['H',1.22000],
    ['H',1.25000]
  ];
  // Same window with no resistance cluster that reaches the minimum touch count at all.
  const AOI_SPEC_NO_RESISTANCE=[
    ['L',1.17000],['L',1.17000],['L',1.17000],
    ['L',1.16000],['L',1.16000],['L',1.16000],
    ['L',1.15000],
    ['H',1.24000],['H',1.24000],              // only 2
    ['H',1.22000],['H',1.22000],              // only 2
    ['H',1.25000]
  ];
  function flatWeekly(n){
    const out=[];
    for(let i=0;i<n;i++) out.push(mk(T0+i*7*DAY,1.20000,1.20000,1.20000,1.20000));
    return out;
  }
  // Dull H1 display candles -- deliberately featureless so a chart-local recomputation of
  // signals/confluence lands somewhere OTHER than the recorded engine verdict seeded below.
  function dullH1(n,endMs){
    const out=[];
    for(let i=0;i<n;i++){
      const base=1.20000+((i%5)*0.00002);
      out.push(mk(endMs-(n-1-i)*HOUR,base,base+0.00030,base-0.00030,base+0.00005));
    }
    return out;
  }

  // ── drawn-series read-back (pure inspection of what the app handed the chart library) ──
  function lineSeries(){ return g.chartRec.series.filter(s=>s.kind==='line'); }
  function seriesTitled(prefix){
    return lineSeries().filter(s=>typeof s.opts.title==='string'&&s.opts.title.indexOf(prefix)===0);
  }
  function seriesColored(color){ return lineSeries().filter(s=>s.opts.color===color&&!s.opts.title); }
  // A drawn AOI boundary is a constant line: every point carries the same value.
  function constValue(s){
    if(!s||!s.data||!s.data.length) return null;
    const v=s.data[0].value;
    for(const p of s.data){ if(p.value!==v) return null; }
    return v;
  }
  function anyDrawnAt(v){
    return lineSeries().some(s=>near(constValue(s),v));
  }
  const SUP_PURPLE='rgba(156,111,228,.9)', RES_PURPLE='rgba(156,111,228,.55)';

  function baseReset(){
    g.setCfg();
    g.resetChartRec();
    g.clearFetchLog();
    g.setStructuralAOICache({});
    g.resetPairData();
    g.resetScanData();
    g.setActivePair('EUR_USD');
    g.setActiveTf('H1');
    g.setChartOverlayToggles({overlay:true,zone:true,markers:true,shading:true,maeMfe:true,drawings:true,tjrZones:true});
    g.setFocusedTradeRecord(null);
    g.resetFiredAlerts();
    g.clearLocalStorage();
    g.clearDecisionEvents();
    g.setAutoTradingEnabled(false);
  }
  // Serves the chart's own H1 request, the AOI Daily/Weekly requests, and nothing else --
  // everything the real code asks for beyond that gets an honest HTTP failure.
  function installChartRouter(dailySpec,opts){
    const o=opts||{};
    const chartCandles=o.chartCandles||dullH1(500,T0+400*DAY);
    g.setFetchRouter(function(url,c){
      if(!c) return null;
      if(c.granularity==='H1'&&c.count===500) return g.oandaCandles(chartCandles);
      if(c.granularity==='D'&&c.count===100) return g.oandaCandles(dailyAoiCandles(dailySpec));
      if(c.granularity==='W'&&c.count===60) return g.oandaCandles(flatWeekly(60));
      // §18.26: the WINDOWED shape used by fetchCandlesAroundWindow, which the real overlay draw
      // path depends on. Served from the same H1 series so the overlay lands on real bars.
      if(c.windowed) return g.oandaCandles(chartCandles);
      return null;
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // A. AOI FIDELITY -- the purple Daily/Weekly band the operator measures a stop against
  // ═══════════════════════════════════════════════════════════════════════════════════════
  baseReset();
  installChartRouter(AOI_SPEC_REFERENCE);
  await g.loadChart();
  await settle();

  {
    const titled=seriesTitled('Support AOI (D/W)');
    const untitled=seriesColored(SUP_PURPLE);
    const lower=titled.length===1?constValue(titled[0]):null;
    const upper=untitled.length===1?constValue(untitled[0]):null;
    assert('CAF-A1','the qualified support AOI is drawn as a band at exactly 1.16600 / 1.17400 -- the labelled boundary is the LOWER one, below current price',
      titled.length===1&&untitled.length===1&&near(lower,1.16600)&&near(upper,1.17400)&&lower<1.20000,
      'labelled='+lower+' unlabelled='+upper+' titled='+titled.length+' untitled='+untitled.length);
  }
  {
    const titled=seriesTitled('Resistance AOI (D/W)');
    const untitled=seriesColored(RES_PURPLE);
    const upper=titled.length===1?constValue(titled[0]):null;
    const lower=untitled.length===1?constValue(untitled[0]):null;
    assert('CAF-A2','the qualified resistance AOI is drawn as a band at exactly 1.24400 / 1.23600 -- the labelled boundary is the UPPER one, above current price',
      titled.length===1&&untitled.length===1&&near(upper,1.24400)&&near(lower,1.23600)&&upper>1.20000,
      'labelled='+upper+' unlabelled='+lower);
  }
  {
    const log=g.fetchLog().filter(r=>r.kind==='candles'&&r.instrument==='EUR_USD');
    const grans={};
    log.forEach(r=>{grans[r.granularity]=(grans[r.granularity]||0)+1;});
    assert('CAF-A3','the drawn AOI is sourced from BOTH configured structural timeframes -- one Daily(100) and one Weekly(60) request were actually issued',
      grans.D>=1&&grans.W>=1&&log.some(r=>r.granularity==='D'&&r.count===100)&&log.some(r=>r.granularity==='W'&&r.count===60),
      JSON.stringify(grans));
  }
  {
    assert('CAF-A4','BOUNDARY (below the minimum): a cluster with exactly 2 touches sits NEARER price than the drawn support, and no AOI boundary is drawn at its 1.19400 / 1.18600 band',
      !anyDrawnAt(1.19400)&&!anyDrawnAt(1.18600),
      'lines='+lineSeries().map(s=>constValue(s)).join(','));
  }

  baseReset();
  installChartRouter(AOI_SPEC_MIN_TOUCHES);
  await g.loadChart();
  await settle();
  {
    const titled=seriesTitled('Support AOI (D/W)');
    const untitled=seriesColored(SUP_PURPLE);
    assert('CAF-A5','BOUNDARY (exactly the minimum): promoting that same cluster to exactly 3 touches moves the drawn support band to exactly 1.18600 / 1.19400',
      titled.length===1&&untitled.length===1&&near(constValue(titled[0]),1.18600)&&near(constValue(untitled[0]),1.19400),
      'labelled='+(titled[0]?constValue(titled[0]):null));
  }

  baseReset();
  installChartRouter(AOI_SPEC_NO_RESISTANCE);
  await g.loadChart();
  await settle();
  {
    const resTitled=seriesTitled('Resistance AOI (D/W)');
    const resAny=lineSeries().filter(s=>s.opts.color===RES_PURPLE);
    const supTitled=seriesTitled('Support AOI (D/W)');
    assert('CAF-A6','NEGATIVE: a resistance the engine REJECTED is not drawn at all -- zero resistance series exist, while the qualified support band is still drawn at 1.16600',
      resTitled.length===0&&resAny.length===0&&supTitled.length===1&&near(constValue(supTitled[0]),1.16600),
      'resistanceSeries='+resAny.length+' supportLabelled='+(supTitled[0]?constValue(supTitled[0]):null));
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // B. DECIDED AUTHORITY -- the chart must show the engine's RECORDED decision, never a
  //    recomputation of its own. Proved by making the two DISAGREE.
  // ═══════════════════════════════════════════════════════════════════════════════════════
  const RECORDED_CONF={total:83,direction:'long',
    items:[{label:'Recorded engine confluence item',state:'hit',pts:25},
           {label:'Recorded engine miss item',state:'miss',pts:0}]};
  const RECORDED_SIGNALS=[{type:'engulf',label:'Recorded engine engulf',dir:'buy',biasMatch:true}];
  function seedEngineVerdict(over){
    const v={conf:JSON.parse(JSON.stringify(RECORDED_CONF)),
      signals:JSON.parse(JSON.stringify(RECORDED_SIGNALS)),
      completenessState:'COMPLETE',requestedCount:220,receivedCount:220,
      // v12.28.0 (§18.17): a recorded verdict now carries the TIMEFRAME it was computed on, and
      // loadChart refuses engine authority unless it matches the timeframe being displayed. These
      // fixtures pinned the pre-fix behaviour, where presence of conf+signals was enough.
      timeframe:'H1',
      candles:null,price:1.20000,evaluationSuppressed:false};
    if(over) Object.assign(v,over);
    g.setPairDataEntry('EUR_USD',v);
  }

  baseReset();
  installChartRouter(AOI_SPEC_REFERENCE);
  seedEngineVerdict();
  await g.loadChart();
  await settle();
  const withEngineConf=g.elHtml('confDir'), withEngineItems=g.elHtml('confItems'), withEngineSigs=g.elHtml('signalsRow');
  const withEngineState=g.elHtml('chartEvaluationState');
  {
    assert('CAF-B1','AUTHORITY: the confluence panel shows the engine\'s RECORDED 83% LONG verdict and its recorded item labels, not a figure recomputed from the chart’s own 500-bar fetch',
      withEngineConf.indexOf('▲ LONG — 83%')!==-1&&
      withEngineItems.indexOf('Recorded engine confluence item')!==-1&&
      withEngineItems.indexOf('Recorded engine miss item')!==-1,
      withEngineConf);
    assert('CAF-B2','AUTHORITY: the signal badges are the engine\'s RECORDED signals, not patterns re-detected at draw time',
      withEngineSigs.indexOf('Recorded engine engulf')!==-1&&withEngineSigs.indexOf('No confirmed patterns')===-1,
      withEngineSigs.slice(0,160));
    assert('CAF-B3','AUTHORITY: with a recorded verdict present the chart attributes it to the scanner and names the timeframe',
      withEngineState.indexOf('scanner’s own H1 verdict')!==-1&&withEngineState.indexOf('NOT EVALUATED')===-1,
      withEngineState.slice(0,180));
  }

  // ── 🔴 CAF-TF: THE DEFECT THIS CAMPAIGN FOUND (§18.17, v12.28.0) ─────────────────────────────
  // pairData recorded conf/signals but NO timeframe, and loadChart granted engine authority on the
  // mere PRESENCE of conf+signals -- then labelled the result with `activeTf`, the timeframe the
  // CHART is on. setTf() assigns activeTf and calls loadChart() BEFORE scanAll(), so switching
  // timeframes rendered the OLD timeframe's verdict under the NEW timeframe's wording. The verdict
  // shown and the timeframe named came from different places.
  //
  // The mismatch is created by varying the RECORDED timeframe, not activeTf. An earlier draft of
  // these fixtures moved activeTf to a granularity the chart router does not serve: loadChart then
  // returned early, #chartEvaluationState kept the PREVIOUS fixture's text, and the assertions read
  // STALE DOM -- passing without the code under test having run at all. Every fixture below clears
  // the element first and asserts it was genuinely rewritten this run.
  async function renderStateWithVerdict(verdictTf){
    baseReset();
    installChartRouter(AOI_SPEC_REFERENCE);
    seedEngineVerdict(verdictTf===undefined?{timeframe:undefined}:{timeframe:verdictTf});
    g.setChartEvaluationStateHtml('');            // no stale text can be mistaken for a fresh render
    await g.loadChart();                          // activeTf stays H1, which the router DOES serve
    return String(g.elHtml('chartEvaluationState'));
  }
  {
    const st=await renderStateWithVerdict('M15'); // the engine evaluated M15; the chart shows H1
    assert('CAF-TF.0','PRECONDITION: the state line was actually re-rendered this run, so the assertions below are not reading stale DOM from an earlier fixture',
      st.length>0, 'len='+st.length);
    assert('CAF-TF.1','a verdict computed on a DIFFERENT timeframe is NOT presented as this timeframe\'s scanner verdict -- the chart never claims H1 authority for an M15 evaluation',
      st.indexOf('scanner’s own H1 verdict')===-1, st.slice(0,200));
    // ⚠️ DISCLOSED (§18.26): NOT independent evidence. Under the shipped guard a mismatched verdict
    // never reaches the engine-wording branch at all, so the string this forbids is structurally
    // unproducible -- an independent sweep showed no single behaviour-changing mutation can make it
    // fail; it takes reverting the guard AND changing the wording together. It is a belt-and-braces
    // companion to CAF-TF.1, kept for failure localisation and counted as one piece of evidence
    // with it, not two.
    // 🔴 §18.27: MY OWN §18.26 RELABEL BROKE THIS. Merging the id and the description into one
    // string turned a 4-arg call into a 3-arg one, so `cond` received st.slice(0,200) -- a string
    // CAF-TF.0 guarantees is non-empty -- and the real check landed in the description slot. Proven
    // dead both ways: replacing the check with `false` left the suite 51/51. The FOURTEENTH fixture
    // of this milestone that cannot fail, and the only one CREATED by the commit under review.
    // Restored to the 4-arg form the suite's assert actually takes.
    assert('CAF-TF.2','COMPANION to TF.1, not independent evidence: it does not borrow the recorded timeframe\'s wording either -- an unattributable verdict is simply not attributed',
      st.indexOf('scanner’s own M15 verdict')===-1, st.slice(0,200));
  }
  {
    // POSITIVE CONTROL, one variable away: the SAME verdict on the MATCHING timeframe is still used
    // and still attributed to the scanner -- so CAF-TF.1 is the mismatch, not a chart that has been
    // broken into never attributing anything.
    const st=await renderStateWithVerdict('H1');
    assert('CAF-TF.3','POSITIVE CONTROL: a verdict recorded on the timeframe being displayed IS attributed to the scanner',
      st.indexOf('scanner’s own H1 verdict')!==-1, st.slice(0,200));
  }
  {
    // FAIL CLOSED: a verdict persisted before v12.28.0 carries no timeframe at all. It cannot be
    // honestly attributed, so it must NOT be granted engine authority.
    const st=await renderStateWithVerdict(undefined);
    // §18.21: the `length>0` clause is NOT decoration. Without it this assertion is satisfied by an
    // EMPTY string -- independent verification proved it by blanking the state line only for the
    // legacy no-timeframe case, which killed nothing. CAF-TF.0's precondition guards the M15 run,
    // not this one.
    assert('CAF-TF.4','a legacy verdict with NO recorded timeframe fails CLOSED -- it is not attributed to the scanner rather than being attributed to a guess, and the state line is genuinely rendered rather than left blank',
      st.length>0 && st.indexOf('scanner’s own')===-1, 'len='+st.length+' '+st.slice(0,180));
  }
  {
    // ── 🔴 CAF-TF.8-.10: THE v12.28.0 FIX WAS WORSE THAN THE BUG (§18.21) ───────────────────────
    // setTf() is `activeTf=tf; loadChart(); scanAll();` with neither awaited, so on EVERY timeframe
    // click the recorded verdict stops matching. Before v12.31.0 the chart then computed its OWN
    // signals and confluence -- and for a pair the engine had REFUSED to evaluate on incomplete
    // data it rendered an invented percentage AND a recommendation banner. It traded a labelling
    // error for a fabricated verdict. These pin that the chart now shows NOTHING rather than
    // something it made up.
    baseReset();
    installChartRouter(AOI_SPEC_REFERENCE);
    seedEngineVerdict({timeframe:'M15',completenessState:'PARTIAL',
      requestedCount:220,receivedCount:137,evaluationSuppressed:true});
    // Cleared FIRST. The suppressed path does not rewrite the confluence panel or the banner, so
    // whatever the previous fixture left there would otherwise be read as this run's output -- the
    // stale-DOM trap that already produced one false pass in this suite.
    g.setChartEvaluationStateHtml('');
    g.setElHtml('confDir',''); g.setElHtml('recBanner',''); g.setElHtml('signalsRow','');
    await g.loadChart();
    const st8=String(g.elHtml('chartEvaluationState'));
    const conf8=String(g.elHtml('confDir')||'');
    // 🔴 §18.24: THIS READ AN ELEMENT THE APP NEVER WRITES. renderRecBanner writes #recLabel,
    // #recDetail and #recScore, and sets only recBanner.className -- so `elHtml('recBanner')` was
    // always the empty string and the assertion below could not fail. Worse, one of its two
    // forbidden strings ('TAKE THE TRADE') appears NOWHERE in index.html. Proven: making loadChart
    // render "SETUP FORMING" on EVERY load, including the suppressed path, killed 0 of 2,207 --
    // the banner the §18.21 reproduction showed fabricating that exact string had no fixture
    // anywhere that could see it. The THIRTEENTH unkillable fixture in this milestone, and mine,
    // on the surface my own commit called "the most misleading surface of all".
    const banner8=String(g.elText('recLabel')||'');
    const bannerDetail8=String(g.elText('recDetail')||'');
    assert('CAF-TF.8','a pair the ENGINE suppressed, viewed on a timeframe it has not scanned, renders an explicit not-scanned state naming BOTH timeframes -- not an invented verdict',
      st8.indexOf('has not been scanned yet')!==-1 && st8.indexOf('M15')!==-1,
      st8.slice(0,220));
    assert('CAF-TF.9','and the confluence panel shows NO percentage and NO direction -- the chart does not fill the gap with a figure it computed itself',
      conf8.indexOf('%')===-1 && conf8.indexOf('LONG')===-1 && conf8.indexOf('SHORT')===-1,
      'confDir='+(conf8===''?'(empty -- cleared before the run and never rewritten)':conf8.slice(0,160)));
    assert('CAF-TF.10','and NO recommendation is offered -- the label reads AWAITING DATA rather than a SETUP FORMING or STRATEGY RECOMMENDS verdict, because the banner carries no qualifier of its own and an invented one there is the most misleading surface of all',
      banner8==='AWAITING DATA' &&
      banner8.indexOf('SETUP FORMING')===-1 && banner8.indexOf('STRATEGY RECOMMENDS')===-1,
      'recLabel='+JSON.stringify(banner8)+' recDetail='+JSON.stringify(bannerDetail8.slice(0,80)));
  }
  {
    // ── 🔴 CAF-LEGEND: the THIRD raw-setupType path, AND the wiring gap (§18.21) ────────────────
    // Two findings in one fixture. (1) renderTradeOverlayLegend rendered
    // `rec.setupLabel||rec.setupType`, and normalizeJournalRecord sets setupLabel to null -- so the
    // chart's own legend showed ALEX's internal research id whenever the label was absent. The D2
    // fix missed this path entirely. (2) The CAF-C/CAF-D overlay fixtures all call
    // drawTradeOverlay/drawTjrZoneOverlay DIRECTLY, so deleting the call site inside loadChart
    // killed NOTHING -- both helpers could be permanently disconnected from the real render path at
    // zero cost to the gate. This drives loadChart() and reads the legend the renderer produced.
    baseReset();
    installChartRouter(AOI_SPEC_REFERENCE);
    const REC={
      tradeId:'AGT|LEG1',journalEntryId:'ALEXJ|LEG1',pair:'EUR/USD',timeframe:'H1',
      setupLabel:null,setupType:'A_repeatedReaction',      // exactly what the normalizer produces
      direction:'buy',entry:1.20000,stop:1.19000,target:1.22000,
      openedAt:'2026-05-29T12:00:00.000Z',closedAt:'2026-05-29T18:00:00.000Z',
      status:'CLOSED',result:'Win',exitPrice:1.22000
    };
    g.setElHtml('chartTradeOverlayLegend','');
    await g.loadChart();
    // NOTE: loadChart's destroyChart() clears focusedTradeRecord, so loadChart does NOT draw the
    // overlay -- focusChartOnTradeWindow does, after loadChart resolves. See the disclosure below.
    g.drawTradeOverlay(REC);
    const legend=String(g.elHtml('chartTradeOverlayLegend')||'');
    // 4-arg signature (id, description, condition, detail). An earlier draft passed 3, which
    // silently shifted the boolean into the description slot and the DETAIL STRING into the
    // condition slot -- so the fixture passed on a truthy string regardless of the result.
    assert('CAF-LEGEND.1','the trade-overlay legend renders a Setup row at all, so the assertion below is reading real rendered output rather than an empty element',
      legend.length>0 && legend.indexOf('Setup')!==-1, 'len='+legend.length+' '+legend.slice(0,140));
    assert('CAF-LEGEND.2','it shows the frozen user-facing label, never ALEX\'s internal research id, when the record carries no setupLabel -- the THIRD raw-setupType path, missed by the v12.28.0 D2 fix',
      legend.indexOf('REPEATED ZONE REACTION')!==-1 && legend.indexOf('A_repeatedReaction')===-1,
      legend.slice(0,200));
    // §18.26: the WIRING is now driven for real -- see CAF-WIRE below. These two remain a direct
    // call because they isolate the LABEL; CAF-WIRE proves loadChart's sibling path reaches the
    // renderer at all.
  }
  {
    // ── 🔴 CAF-WIRE: the overlay helpers were reachable-but-unpinned (§18.26) ────────────────────
    // Deleting `drawTradeOverlay(rec)` from focusChartOnTradeWindow, or the drawTjrZoneOverlay call
    // site, killed ZERO fixtures across the whole gate: every overlay fixture called the helper
    // DIRECTLY, so both could be permanently disconnected from the render path at no cost. The
    // blocker was the fixture router, which did not model fetchCandlesAroundWindow's url shape.
    // It does now, so the REAL path runs: focusTradeOnChart -> loadChart -> focusChartOnTradeWindow
    // -> drawTradeOverlay.
    baseReset();
    installChartRouter(AOI_SPEC_REFERENCE);
    const WREC={journalEntryId:'JVMJ|WIRE1',tradeId:'WIRE1',strategyId:'current_strategy',
      pair:'EUR/USD',timeframe:'H1',direction:'buy',status:'CLOSED',result:'Win',
      entry:1.20000,stop:1.19000,target:1.22000,exitPrice:1.22000,
      openedAt:new Date(T0+300*DAY).toISOString(),closedAt:new Date(T0+301*DAY).toISOString()};
    g.setJournalEntries([WREC]);
    g.setElHtml('chartTradeOverlayLegend','');
    g.resetChartRec();
    await g.focusTradeOnChart('JVMJ|WIRE1');
    await settle();
    const lines=(g.chartRec.priceLines||[]).map(function(l){return l.opts||{};});
    const titles=lines.map(function(o){return String(o.title||'');}).join(' | ');
    assert('CAF-WIRE.0','PRECONDITION: the real entry point ran and reached the chart -- price lines exist, so the assertions below are about WIRING and not about an empty chart',
      lines.length>0, 'lines='+lines.length+' titles='+titles.slice(0,140));
    assert('CAF-WIRE.1','WIRING: focusTradeOnChart() reaches drawTradeOverlay through the real path -- the entry, stop and target lines are drawn at the record\'s own recorded prices, so deleting the call site inside focusChartOnTradeWindow now fails',
      lines.some(function(o){return Math.abs(o.price-1.20000)<1e-9;}) &&
      lines.some(function(o){return Math.abs(o.price-1.19000)<1e-9;}) &&
      lines.some(function(o){return Math.abs(o.price-1.22000)<1e-9;}),
      'prices='+lines.map(function(o){return o.price;}).join(','));
  }
  {
    // RE-ENTRANCY (§18.21). loadChart reads its globals across two awaits. An operator clicking a
    // different timeframe mid-load previously let the FETCH use one value while the verdict guard
    // and the state line read another -- H1 candles drawn under an H4 verdict, labelled H4.
    baseReset();
    installChartRouter(AOI_SPEC_REFERENCE);
    seedEngineVerdict({timeframe:'H4'});
    g.setActiveTf('H1');
    g.setChartEvaluationStateHtml('');
    // The interleaving needs no special plumbing: loadChart is async, so starting it WITHOUT
    // awaiting and flipping activeTf before the await puts the change exactly where an operator's
    // mid-load click lands -- after the fetch has begun, before the verdict guard and the label run.
    const pending=g.loadChart();
    g.setActiveTf('H4');
    await pending;
    const st11=String(g.elHtml('chartEvaluationState'));
    assert('CAF-TF.11','a timeframe switched DURING the fetch cannot make the chart label H1 candles with an H4 verdict -- the timeframe is captured once, so the guard and the label read what the fetch actually used',
      st11.length>0 && st11.indexOf('scanner’s own H4 verdict')===-1, st11.slice(0,220));
  }
  {
    // ── 🔴 CAF-PAIR: the PAIR was never captured, only the timeframe (§18.24) ────────────────────
    // v12.31.0 captured chartTf and its comment claimed "exactly as `name` captures the pair
    // above". That was FALSE: `name` is used only for the header text and the live-trigger badge's
    // freshness guard, while the VERDICT block read the live activePair across both awaits. A
    // pair-list click is `activePair=p; renderPairList(); loadChart();` -- unawaited, the same
    // shape as setTf. Reproduced by an independent verifier: EUR/USD's candles and header rendered
    // with GBP/USD's verdict, attributed to the scanner.
    baseReset();
    installChartRouter(AOI_SPEC_REFERENCE);
    g.setActivePair('EUR_USD');
    g.setActiveTf('H1');
    // EUR_USD was SUPPRESSED by the engine; GBP_USD is healthy with a confident verdict.
    seedEngineVerdict({timeframe:'H1',completenessState:'PARTIAL',
      requestedCount:220,receivedCount:137,evaluationSuppressed:true});
    // A DISTINCTIVE value: seedEngineVerdict's own verdict is 83% LONG, so if GBP_USD were also
    // 83% the assertion could not tell whose verdict was rendered. 71% SHORT belongs to GBP_USD
    // and to nothing else in this suite.
    g.setPairDataEntry('GBP_USD',{conf:{total:71,direction:'short',items:[]},signals:[],
      completenessState:'COMPLETE',requestedCount:220,receivedCount:220,timeframe:'H1',
      candles:null,price:1.30000,evaluationSuppressed:false});
    g.setChartEvaluationStateHtml('');
    g.setElHtml('confDir',''); g.setElHtml('recLabel','');
    const pendingPair=g.loadChart();
    g.setActivePair('GBP_USD');          // the operator clicks another pair mid-load
    await pendingPair;
    const stP=String(g.elHtml('chartEvaluationState'));
    const confP=String(g.elHtml('confDir')||'');
    assert('CAF-PAIR.0','PRECONDITION: the state line was re-rendered this run, so the assertions below are not reading stale DOM',
      stP.length>0,'len='+stP.length);
    assert('CAF-PAIR.1','a pair switched DURING the load cannot make the chart show the NEW pair\'s verdict on the OLD pair\'s chart -- GBP_USD\'s distinctive 71% SHORT must not appear on EUR_USD\'s chart',
      confP.indexOf('71%')===-1 && confP.indexOf('SHORT')===-1,'confDir='+confP.slice(0,160));
    assert('CAF-PAIR.2','and the instrument the engine SUPPRESSED still renders its not-evaluated state rather than borrowing a confident verdict from the pair the operator moved to',
      stP.indexOf('NOT EVALUATED')!==-1,stP.slice(0,200));
  }
  {
    // ── CAF-LABEL: the display helper must not drift from the frozen record (§18.17) ───────────
    // alexGCreateSetupRecord is PROTECTED, so the live-setups panel cannot share its mapping and
    // has to duplicate it. This pins the duplicate against the REAL record so they cannot diverge.
    const pairs=[['A_repeatedReaction','REPEATED ZONE REACTION'],['B_breakRetest','BREAK & RETEST']];
    let agree=true, detail=[];
    pairs.forEach(function(pr){
      const shown=g.alexGSetupDisplayLabel(pr[0]);
      detail.push(pr[0]+'->'+shown);
      if(shown!==pr[1]) agree=false;
    });
    // ⚠️ DISCLOSED SCOPE. CAF-LABEL.1 pins the duplication only for the setup type this engine run
    // actually produces (A_repeatedReaction) -- verified: changing THAT branch inside the protected
    // record kills it, while changing the B_breakRetest branch does not, because no real
    // break-retest setup is constructed here. The B half below is still a literal comparison and is
    // counted as such, not as drift protection.
    assert('CAF-LABEL.1b','and it still returns the frozen label for BOTH setup types (LITERAL comparison -- only the A branch above is pinned against a real record)',
      agree, detail.join(' '));
    assert('CAF-LABEL.2','and an unknown setup type is shown verbatim rather than being given an invented label',
      g.alexGSetupDisplayLabel('Z_unknown')==='Z_unknown'&&g.alexGSetupDisplayLabel('')==='' ,
      'Z_unknown->'+g.alexGSetupDisplayLabel('Z_unknown'));
  }

  // The divergence control: the SAME candles, with no recorded verdict, must render something
  // DIFFERENT. Without this, B1/B2 could be passing because the two happen to agree.
  baseReset();
  installChartRouter(AOI_SPEC_REFERENCE);
  await g.loadChart();
  await settle();
  const chartLocalConf=g.elHtml('confDir'), chartLocalSigs=g.elHtml('signalsRow');
  const chartLocalState=g.elHtml('chartEvaluationState');
  {
    assert('CAF-B4','DIVERGENCE CONTROL: the same candles, scored locally with no recorded verdict, produce a DIFFERENT confluence panel and a DIFFERENT badge row -- so B1/B2 are not agreeing by coincidence',
      chartLocalConf!==withEngineConf&&chartLocalSigs!==withEngineSigs&&
      chartLocalConf.indexOf('▲ LONG — 83%')===-1&&
      chartLocalSigs.indexOf('Recorded engine engulf')===-1,
      'local='+chartLocalConf.slice(0,80));
    assert('CAF-B5','AUTHORITY: a chart-local pre-scan computation is labelled as such and is never presented as the engine’s verdict',
      chartLocalState.indexOf('has not scored this pair yet')!==-1&&chartLocalState.indexOf('scanner’s own')===-1,
      chartLocalState.slice(0,180));
  }

  // Suppression authority: the engine recorded an INCOMPLETE evaluation for this pair while
  // the chart's own 500-bar fetch is perfectly complete. The chart must follow the ENGINE.
  baseReset();
  installChartRouter(AOI_SPEC_REFERENCE);
  seedEngineVerdict({completenessState:'PARTIAL',requestedCount:220,receivedCount:137,evaluationSuppressed:true});
  await g.loadChart();
  await settle();
  {
    const st=g.elHtml('chartEvaluationState');
    assert('CAF-B6','AUTHORITY: an instrument the ENGINE suppressed renders NOT EVALUATED even though the chart’s own fetch was complete, and reports the ENGINE’s requested/received in that order',
      st.indexOf('NOT EVALUATED')!==-1&&
      st.indexOf('state PARTIAL')!==-1&&
      st.indexOf('requested 220 · received 137')!==-1&&
      st.indexOf('requested 137')===-1,
      st.slice(0,300));
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // C. TRADE OVERLAY -- entry / stop / target as DRAWN, from the stored journal record
  // ═══════════════════════════════════════════════════════════════════════════════════════
  function priceLineAt(price){
    return g.chartRec.priceLines.filter(l=>near(l.opts.price,price));
  }
  function priceLineTitled(prefix){
    return g.chartRec.priceLines.filter(l=>typeof l.opts.title==='string'&&l.opts.title.indexOf(prefix)===0);
  }
  const TRADE_BUY={strategyLabel:'JVM',pair:'EUR/USD',timeframe:'M15',setupLabel:'Fixture setup',
    direction:'buy',entry:1.10500,stop:1.10200,target:1.11100,plannedRR:2,result:'Win',resultR:2,
    openedAt:'2026-03-02T08:00:00.000Z',closedAt:'2026-03-02T14:00:00.000Z',
    maePips:null,mfePips:null,zoneLow:null,zoneHigh:null,qualificationTimestamp:null,status:'CLOSED'};

  g.resetChartRec();
  g.drawTradeOverlay(TRADE_BUY);
  {
    const entry=priceLineTitled('Entry '), stop=priceLineTitled('Stop '), target=priceLineTitled('Target ');
    assert('CAF-C1','POSITIVE: the trade overlay draws entry, stop and target at exactly the three RECORDED prices, each labelled with its own price -- never one of them at another’s level',
      entry.length===1&&stop.length===1&&target.length===1&&
      near(entry[0].opts.price,1.10500)&&near(stop[0].opts.price,1.10200)&&near(target[0].opts.price,1.11100)&&
      entry[0].opts.title==='Entry 1.10500'&&stop[0].opts.title==='Stop 1.10200'&&target[0].opts.title==='Target 1.11100',
      g.chartRec.priceLines.map(l=>l.opts.title+'@'+l.opts.price).join(' | '));
    const entryMarker=g.chartRec.markers.filter(m=>m.text==='Entry')[0];
    const exitMarker=g.chartRec.markers.filter(m=>m.text==='Win')[0];
    assert('CAF-C2','a BUY’s entry marker is drawn BELOW the bar and its exit marker ABOVE it',
      !!entryMarker&&entryMarker.position==='belowBar'&&entryMarker.shape==='arrowUp'&&
      !!exitMarker&&exitMarker.position==='aboveBar',
      JSON.stringify(g.chartRec.markers.map(m=>m.text+':'+m.position)));
  }
  g.resetChartRec();
  {
    const sell=Object.assign({},TRADE_BUY,{direction:'sell',result:'Loss'});
    g.drawTradeOverlay(sell);
    const entryMarker=g.chartRec.markers.filter(m=>m.text==='Entry')[0];
    const exitMarker=g.chartRec.markers.filter(m=>m.text==='Loss')[0];
    assert('CAF-C3','a SELL’s entry marker is drawn ABOVE the bar and its exit marker BELOW it -- the side tracks the recorded direction',
      !!entryMarker&&entryMarker.position==='aboveBar'&&entryMarker.shape==='arrowDown'&&
      !!exitMarker&&exitMarker.position==='belowBar',
      JSON.stringify(g.chartRec.markers.map(m=>m.text+':'+m.position)));
  }
  g.resetChartRec();
  {
    const noStop=Object.assign({},TRADE_BUY,{stop:null});
    let overlayThrew=null;
    try{ g.drawTradeOverlay(noStop); }catch(e){ overlayThrew=(e&&e.message)?e.message:String(e); }
    assert('CAF-C4','NEGATIVE: a record with no recorded stop draws NO stop line at all -- entry and target only, nothing substituted at the entry price, and the overlay does not fail trying',
      overlayThrew===null&&priceLineTitled('Stop ').length===0&&priceLineAt(1.10500).length===1&&
      priceLineTitled('Entry ').length===1&&priceLineTitled('Target ').length===1,
      'threw='+overlayThrew+' lines='+g.chartRec.priceLines.map(l=>l.opts.title).join(' | '));
  }
  g.resetChartRec();
  g.clearTradeOverlay();

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // D. CHART-LAYER FAILURE ISOLATION -- one malformed zone must not blank the layer
  // ═══════════════════════════════════════════════════════════════════════════════════════
  {
    g.resetChartRec();
    g.setChartOverlayToggles({overlay:true,zone:true,markers:true,shading:true,maeMfe:true,drawings:true,tjrZones:true});
    const result={instrument:'GBP_USD',
      sourceSession:{sessionId:'LONDON',tradingDate:'2026-01-05'},
      highZone:{zoneType:'HIGH',status:'OK',upper:1.35120,lower:1.35080,sourceSessionId:'LONDON',sourceTradingDate:'2026-01-05'},
      lowZone:{zoneType:'LOW',status:'INVALID_SOURCE',upper:null,lower:null}};
    let zoneThrew=null;
    try{ g.drawTjrZoneOverlay(result); }catch(e){ zoneThrew=(e&&e.message)?e.message:String(e); }
    const drawn=g.chartRec.priceLines.map(l=>l.opts.price).sort();
    assert('CAF-D1','FAILURE ISOLATION: one malformed zone is skipped, not fatal -- the overlay does not throw, the healthy zone is still drawn at exactly 1.35120 / 1.35080, and the legend still renders both rows',
      zoneThrew===null&&g.chartRec.priceLines.length===2&&near(drawn[0],1.35080)&&near(drawn[1],1.35120)&&
      g.elHtml('tjrZoneOverlayLegend').indexOf('no valid source data')!==-1,
      'threw='+zoneThrew+' drawn='+JSON.stringify(drawn));
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // E. ALEX -- the zone engine's own rendered output
  // ═══════════════════════════════════════════════════════════════════════════════════════
  // Reuses the same synthetic H1 construction the Phase 2C suite proved yields ONE genuine
  // REPEATED ZONE REACTION on a support zone through the REAL, unmodified zone/setup engine:
  // four real swing-low touches at ~1.10000. Nothing here re-implements or bypasses any
  // protected function -- the network is stubbed at fetch() and the engine runs for real.
  function repeatedReactionH1(t0){
    const c=[];
    const push=(o,h,l,cl)=>c.push(mk(t0+c.length*HOUR,o,h,l,cl));
    const filler=n=>{ let base=1.10600;
      for(let i=0;i<n;i++){ const d=(i%3)*0.00005; push(base+d,base+d+0.00080,base+d-0.00040,base+d+0.00020); } };
    filler(14);
    const lows=[1.10000,1.10002,1.09998,1.10001], idxs=[14,24,34,44];
    let i=14;
    while(i<=44){
      const k=idxs.indexOf(i);
      if(k!==-1){ const l=lows[k];
        push(l+0.00020,l+0.00025,l,l+0.00015); i++;
        push(l+0.00015,l+0.00200,l+0.00010,l+0.00180); i++;
      } else { filler(1); i++; }
    }
    filler(20);
    return c;
  }
  function flatHTF(t0,n,stepMs){
    const out=[];
    for(let j=0;j<n;j++) out.push(mk(t0+j*stepMs,1.10000,1.10100,1.09900,1.10050));
    return out;
  }
  function installAlexRouter(sets,bidAsk){
    g.setFetchRouter(function(url,c){
      if(/pricing\?instruments=/.test(url)) return bidAsk?g.oandaPrice(bidAsk.bid,bidAsk.ask):null;
      if(!c) return null;
      if(c.paged) return g.oandaCandles([]);           // second page: history exhausted
      const arr=sets[c.granularity];
      return arr?g.oandaCandles(arr):g.oandaCandles([]);
    });
  }
  function resetAlex(){
    g.setAlexGSetupState([]);
    g.setAlexGZoneState({});
    g.setAlexGLastEvaluatedCloseTime({});
    g.setAlexGLiveSetupStatuses([]);
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGJournalEntries([]);
    // activatedAt is an epoch-millisecond number: the frozen activation gate compares it
    // directly against setup.qualificationTimestamp, which is also a number. It is set one day
    // in the FUTURE deliberately, so the frozen activation gate always refuses this candidate:
    // the setup still qualifies, is still recorded and is still rendered, but NO paper position
    // is ever constructed and the outcome does not depend on which weekday the gate is run on
    // (the frozen entry-day rule would otherwise make this fixture pass only Monday-Wednesday).
    g.setAlexGAutoTrading({enabled:true,activatedAt:Date.now()+DAY,
      tradedSignals:{},tradedToday:{},log:[]});
    g.clearDecisionEvents();
    g.clearLocalStorage();
  }

  {
    baseReset();
    resetAlex();
    const nowMs=Date.now();
    const t0=nowMs-48*HOUR-5*60000;
    const H1=repeatedReactionH1(t0);
    const htf0=t0-30*DAY;
    installAlexRouter({H1:H1,H4:flatHTF(htf0,20,4*HOUR),D:flatHTF(htf0,20,DAY),W:flatHTF(htf0,20,7*DAY)},
      {bid:1.10595,ask:1.10605});
    const outcome=await g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN-FIXTURE-E');
    g.renderAlexGLiveSetupsPanel();
    const html=g.elHtml('alexgLiveSetupsTable');
    const rows=html.split('<tr>').slice(2); // [0] is the thead prefix, [1] is the header row
    const cellsOf=r=>{ const out=[]; const re=/<td[^>]*>([\s\S]*?)<\/td>/g; let m;
      while((m=re.exec(r))!==null) out.push(m[1]); return out; };
    const first=rows.length?cellsOf(rows[0]):[];
    assert('CAF-E1','ALEX END-TO-END: the live setups panel renders the REAL engine’s recorded qualification -- exactly one row, pair EUR_USD, H1, a repeated-reaction setup on a zone whose id the engine minted',
      rows.length===1&&first[0]==='EUR_USD'&&first[1]==='H1'&&first[2]==='REPEATED ZONE REACTION'&&
      first[5].indexOf('AGZ|AGC|EUR_USD|H1')===0,
      'rows='+rows.length+' cells='+JSON.stringify(first));
    // §18.21: relocated here from the CAF-LABEL block, which runs BEFORE this engine run and
    // therefore had no real setup record to compare against -- the precondition caught that.
    // §18.21: this compared the helper against HAND-WRITTEN LITERALS, so changing the mapping
    // inside the PROTECTED alexGCreateSetupRecord left it green -- it pinned the helper alone, not
    // the DUPLICATION, which is the only thing that can actually drift. It now reads the label off
    // a REAL setup record produced by the real engine run above and requires the helper to agree
    // with THAT. If the protected record's mapping is ever changed, this fails.
    const realSetups=g.getAlexGSetupState()||[];
    const realSetup=realSetups.filter(function(x){return x&&x.setupType&&x.setupLabel;})[0]||null;
    assert('CAF-LABEL.0','PRECONDITION: the real engine run produced a setup record carrying BOTH a setupType and the frozen setupLabel, so the comparison below has a real record to compare against',
      !!realSetup, realSetup?(realSetup.setupType+' -> '+realSetup.setupLabel):'no real setup record');
    assert('CAF-LABEL.1','the display helper agrees with the label a REAL setup record carries -- compared against the record the PROTECTED alexGCreateSetupRecord actually produced, not against a literal, so the duplicated mapping cannot drift',
      !!realSetup && g.alexGSetupDisplayLabel(realSetup.setupType)===realSetup.setupLabel,
      realSetup?('helper='+g.alexGSetupDisplayLabel(realSetup.setupType)+' record='+realSetup.setupLabel):'no real setup record');
    assert('CAF-E2','ALEX END-TO-END: the rendered zone touch number is the engine’s own 4th reaction -- exactly "4", not 3 and not 5',
      first[6]==='4','touchCell='+JSON.stringify(first[6])+' evaluated='+(outcome&&outcome.evaluated));
    assert('CAF-E3','ALEX END-TO-END: the rendered status is the engine’s own recorded verdict for this candidate, and no position was constructed',
      first[7]==='IGNORED — BEFORE ACTIVATION',
      'statusCell='+JSON.stringify(first[7]));
  }
  {
    // Direction is written onto the status record only by the construction path, which the
    // activation gate above deliberately never reaches. It is asserted here at the display
    // layer instead, against a recorded row of exactly the shape that path writes.
    g.setAlexGLiveSetupStatuses([
      {signalId:'S1',setupId:'AGS|1',pair:'EUR_USD',timeframe:'H1',setupType:'A_repeatedReaction',
       direction:'buy',qualificationTimestamp:Date.UTC(2026,2,2,9,0,0),
       zoneId:'AGZ|AGC|EUR_USD|H1|low|1',zoneTouchNumber:4,status:'TRADE OPENED'},
      {signalId:'S2',setupId:'AGS|2',pair:'GBP_JPY',timeframe:'H1',setupType:'B_breakRetest',
       direction:'sell',qualificationTimestamp:Date.UTC(2026,2,2,10,0,0),
       zoneId:'AGZ|AGC|GBP_JPY|H1|high|1',zoneTouchNumber:5,status:'TRADE OPENED'}
    ]);
    g.renderAlexGLiveSetupsPanel();
    const html=g.elHtml('alexgLiveSetupsTable');
    const rows=html.split('<tr>').slice(2);
    const cellsOf=r=>{ const out=[]; const re=/<td[^>]*>([\s\S]*?)<\/td>/g; let m;
      while((m=re.exec(r))!==null) out.push(m[1]); return out; };
    const a=cellsOf(rows[0]||''), b=cellsOf(rows[1]||'');
    assert('CAF-E4','the setups panel renders each recorded direction on its own row -- a BUY reads BUY and a SELL reads SELL, never the opposite',
      rows.length===2&&a[3]==='BUY'&&b[3]==='SELL',
      JSON.stringify([a[3],b[3]]));
    assert('CAF-E5','and each row carries its own recorded touch count -- 4 and 5, not one value applied to both and not off by one',
      a[6]==='4'&&b[6]==='5',JSON.stringify([a[6],b[6]]));
    g.setAlexGLiveSetupStatuses([]);
  }

  {
    // The replay dashboard's own per-timeframe zone tally, produced by a REAL end-to-end run of
    // the frozen zone/setup engine over the same synthetic H1 series. Only the H1 dataset carries
    // repeated reactions; the higher timeframes are deliberately featureless, so the engine can
    // only validate a zone on H1. Both numbers below are stated as literals.
    baseReset();
    resetAlex();
    const t0=Date.now()-48*HOUR-5*60000;
    const htf0=t0-30*DAY;
    installAlexRouter({H1:repeatedReactionH1(t0),H4:flatHTF(htf0,40,4*HOUR),
      D:flatHTF(htf0,40,DAY),W:flatHTF(htf0,40,7*DAY)},{bid:1.10595,ask:1.10605});
    const replay=await g.runAlexGReplay('EUR_USD',90,
      {ambiguousMode:'exclude',alexGSpreadMode:'none',alexGFixedSpreadPips:0,alexGSlippagePips:0,startBalance:10000});
    const counts=g.zoneCountsFor('EUR_USD');
    assert('CAF-E6','the frozen zone engine validates exactly one zone, on H1, from this dataset -- and none on H4, Daily or Weekly',
      !!counts&&counts.H1===1&&counts.H4===0&&counts.D===0&&counts.W===0,
      JSON.stringify(counts)+' replayError='+(replay&&replay.error));
    g.renderAlexGDashboard(replay);
    const line=g.elText('alexgSummaryLine');
    assert('CAF-E7','and the replay dashboard reports that tally per timeframe exactly as the engine produced it -- H1 1, H4 0, D 0, W 0, each in its own slot',
      typeof line==='string'&&line.indexOf('Zones: H1 1 · H4 0 · D 0 · W 0')===0,
      String(line).slice(0,120));
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // F. SCANNER COVERAGE, CADENCE AND FAILURE ISOLATION
  // ═══════════════════════════════════════════════════════════════════════════════════════
  function installSweepRouter(perPairCandles){
    g.setFetchRouter(function(url,c){
      if(/pricing\?instruments=/.test(url)) return g.oandaPrice(1.19995,1.20005);
      if(!c) return null;
      if(c.paged) return g.oandaCandles([]);
      const n=perPairCandles!=null?perPairCandles:c.count;
      const out=[];
      for(let i=0;i<n;i++) out.push(mk(T0+i*HOUR,1.20000,1.20030,1.19970,1.20005));
      return g.oandaCandles(out);
    });
  }
  {
    baseReset();
    installSweepRouter();
    await g.scanAll();
    const configured=g.allPairs();
    const visited={};
    g.fetchLog().filter(r=>r.kind==='candles').forEach(r=>{visited[r.instrument]=true;});
    const missing=configured.filter(p=>!visited[p]);
    assert('CAF-F1','COVERAGE: one JVM sweep issues a market-data request for EVERY configured instrument -- none is silently left out of the sweep',
      configured.length>0&&missing.length===0,
      'configured='+configured.length+' missing='+JSON.stringify(missing));
  }
  {
    // ── CAF-TF.5: THE WIRING HALF OF THE §18.17 FIX ─────────────────────────────────────────────
    // The CAF-TF fixtures above seed pairData directly, so they prove loadChart REFUSES a
    // mismatched verdict but prove nothing about scanPair actually RECORDING the timeframe.
    // Found by mutation: deleting `timeframe:activeTf` from what scanPair writes killed ZERO
    // fixtures -- covered-but-wired-to-nothing, the exact anti-pattern this milestone keeps
    // finding, in the coverage of my own fix. This drives the REAL sweep and reads what the real
    // scanPair actually stored.
    baseReset();
    installSweepRouter();
    g.setActiveTf('H4');
    await g.scanAll();
    const rec=g.pairDataEntry('EUR_USD');
    assert('CAF-TF.5','WIRING: a real sweep RECORDS the timeframe it evaluated on, so the verdict is attributable at all -- without this the loadChart guard has nothing to compare against',
      !!rec&&rec.timeframe==='H4','recorded timeframe='+String(rec&&rec.timeframe));
    // NOT a fixture: switching the sweep timeframe is setup for CAF-TF.7. An earlier draft asserted
    // this step with a callback that returned `true` unconditionally -- a tautology that could never
    // fail, dressed as evidence. Caught before delivery and demoted to the plain statement it is.
    g.setActiveTf('H1');
    await g.scanAll();
    const rec2=g.pairDataEntry('EUR_USD');
    assert('CAF-TF.7','a second sweep on a different timeframe records THAT timeframe -- so the field follows the evaluation and is not a fixed literal',
      !!rec2&&rec2.timeframe==='H1','recorded timeframe='+String(rec2&&rec2.timeframe));
  }
  {
    baseReset();
    installSweepRouter();
    const configured=g.allPairs();
    const victim=configured[configured.length-1]; // the LAST instrument of the LAST chunk
    // A realistic per-instrument fault: the shared pairData slot rejects this instrument's
    // write. This is exactly the "malformed pairData entry" the isolation code names.
    const pd={};
    Object.defineProperty(pd,victim,{configurable:true,
      get:function(){return undefined;},
      set:function(){throw new Error('malformed pairData entry');}});
    g.setPairDataObject(pd);
    let threw=null;
    try{ await g.scanAll(); }catch(e){ threw=(e&&e.message)?e.message:String(e); }
    const visited={};
    g.fetchLog().filter(r=>r.kind==='candles').forEach(r=>{visited[r.instrument]=true;});
    const others=configured.filter(p=>p!==victim);
    const missing=others.filter(p=>!visited[p]);
    const errs=g.getPaperEngineErrors();
    assert('CAF-F2','FAILURE ISOLATION: one instrument throwing does not stop the sweep -- every other configured instrument is still visited, the sweep completes, and the fault is recorded against that instrument by name',
      threw===null&&missing.length===0&&errs.some(e=>String(e.message).indexOf('scanPair('+victim+')')===0),
      'threw='+threw+' missing='+JSON.stringify(missing)+' errs='+JSON.stringify(errs.slice(0,2)));
    g.setPairDataObject({});
  }
  {
    baseReset();
    resetAlex();
    installSweepRouter(30); // deliberately short H1 -- every instrument is DISPATCHED then skipped
    await g.alexGLivePollTick();
    const configured=g.scanPairsList().map(p=>p.replace('/','_'));
    const visited={};
    g.fetchLog().filter(r=>r.kind==='candles').forEach(r=>{visited[r.instrument]=true;});
    const missing=configured.filter(p=>!visited[p]);
    assert('CAF-F3','COVERAGE: one ALEX poll tick reaches EVERY configured instrument -- the sweep is not truncated after the first',
      configured.length>1&&missing.length===0,
      'configured='+configured.length+' missing='+JSON.stringify(missing));
  }
  {
    baseReset();
    resetAlex();
    const t0=Date.now()-48*HOUR-5*60000;
    const H1=repeatedReactionH1(t0);
    const htf0=t0-30*DAY;
    // H1 is COMPLETE; the DAILY response is two candles short of what was requested, so the
    // completeness contract must refuse the whole instrument for this boundary.
    g.setFetchRouter(function(url,c){
      if(/pricing\?instruments=/.test(url)) return g.oandaPrice(1.10595,1.10605);
      if(!c) return null;
      if(c.granularity==='H1') return c.paged?g.oandaCandles([]):g.oandaCandles(H1);
      if(c.paged&&c.granularity!=='D') return g.oandaCandles([]);
      if(c.granularity==='D')  return c.paged?{ok:false,status:429,json:async function(){return{};}}
                                              :g.oandaCandles(flatHTF(htf0,Math.max(1,c.count-2),DAY));
      if(c.granularity==='H4') return g.oandaCandles(flatHTF(htf0,c.count,4*HOUR));
      if(c.granularity==='W')  return g.oandaCandles(flatHTF(htf0,c.count,7*DAY));
      return null;
    });
    const outcome=await g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN-FIXTURE-F4');
    assert('CAF-F4','TIMEFRAME COVERAGE: a Daily response short of the completeness contract suppresses the whole instrument and NAMES the failing timeframe -- H1 alone is never enough',
      !!outcome&&outcome.evaluated===false&&
      Array.isArray(outcome.incompleteTimeframes)&&outcome.incompleteTimeframes.indexOf('D')!==-1,
      JSON.stringify(outcome));
    assert('CAF-F5','TIMEFRAME COVERAGE: and the frozen zone engine is never handed that instrument’s data -- no zone state was built for it',
      g.zoneCountsFor('EUR_USD')===null,
      JSON.stringify(g.zoneCountsFor('EUR_USD')));
  }

  g.setFetchRouter(null);
  return results;
}
