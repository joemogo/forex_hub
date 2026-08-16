// MOGO-021 — MARKET-DATA ACQUISITION, CANDLE COMPLETENESS/CONTINUITY AND MULTI-INSTRUMENT
// OBSERVATION fixtures (v12.39). Written mutation-first: every fixture below was paired with a
// specific behaviour-changing edit to index.html, run against the whole 29-suite gate, and kept
// only after it was observed to FAIL with that edit applied and PASS without it.
//
// WHAT THIS SUITE IS FOR
// The completeness contract (ADR-011) was already covered at the level of "is the verdict right".
// It was NOT covered at the level of "is the SERIES right": nothing in the gate objected when
// fetchCandles stopped filtering out the still-forming candle, so the frozen evaluators would
// have scored a bar that had not closed, with a COMPLETE verdict attached. Nothing objected when
// pagination merged its pages in the wrong direction, when the backward cursor stopped advancing
// correctly, or when a whole instrument silently left the observed set. Those are the gaps here.
//
// RULES OBSERVED
//   * No production function is stubbed, mocked, wrapped or re-implemented. The only seam is
//     globalThis.fetch, answered in OANDA's own response shapes.
//   * Every expected timestamp is a HAND-COMPUTED literal (see the derivations beside each), never
//     re-derived the way production derives it.
//   * Every detector fixture has a partner that proves the detector stays SILENT in the condition
//     it must not fire in, so an edit that simply blesses everything cannot pass both.
//   * No real paper trade is opened or persisted: alexGAutoTrading/autoTrading are left disabled
//     and every storage write lands in the runner's in-memory localStorage stub.
function runMarketDataContinuityFixtures(g){
  const out=[];
  async function t(name,fn){
    try{ const d=await fn(); out.push({name:name,pass:true,detail:d||''}); }
    catch(e){ out.push({name:name,pass:false,detail:(e&&e.message)?e.message:String(e)}); }
  }
  function eq(a,b,m){ if(a!==b) throw new Error((m||'')+' expected '+JSON.stringify(b)+', got '+JSON.stringify(a)); }
  function ok(v,m){ if(!v) throw new Error(m||'expected truthy'); }
  const HOUR=3600000, M15=900000;

  // ── The synthetic market's fixed anchors ───────────────────────────────────────────────────
  // NEWEST is Monday 2026-06-01T00:00:00Z. Every literal below is derived by hand from it:
  //   M15: 219 closed bars back  -> 219*15min = 54h45m  -> 2026-05-29T17:15:00.000Z
  //        1 closed bar back     -> 15min               -> 2026-05-31T23:45:00.000Z
  //   H1 : 299 bars back -> 2026-05-19T13:00:00.000Z   199 bars back -> 2026-05-23T17:00:00.000Z
  //        147 bars back -> 2026-05-25T21:00:00.000Z     1 bar back  -> 2026-05-31T23:00:00.000Z
  const NEWEST=Date.parse('2026-06-01T00:00:00.000Z');

  // An HONEST broker: returns `count` bars, oldest-first, ending at the newest bar that starts
  // strictly before `to` (or at NEWEST when `to` is absent) -- exactly OANDA's documented
  // behaviour. maxPerPage forces the paginated walk to take more than one page.
  function honest(opts){
    opts=opts||{};
    const dur=opts.dur||HOUR, newest=opts.newest===undefined?NEWEST:opts.newest;
    return function(req){
      if(req.kind==='pricing') return g.okPrice();
      if(req.kind!=='candles') return g.errPage(503);
      let end=newest;
      if(req.to){
        const toMs=Date.parse(req.to);
        end=Math.floor((toMs-newest)/dur)*dur+newest;
        if(end>toMs) end-=dur;
      }
      const n=Math.min(req.count,opts.maxPerPage||req.count);
      return g.okPage(g.bars(end,dur,n,!req.to&&!!opts.formingLast));
    };
  }

  return (async function(){

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // A. ACQUISITION — forming vs closed, exact grid, legitimate gaps
  // ══════════════════════════════════════════════════════════════════════════════════════════

  // MUTATION PAIRED: fetchCandles' `.filter(c=>c.complete)` -> `.filter(c=>true)`.
  await t('MDCONT-1 the still-FORMING bar never reaches the returned series, and the closed grid ends exactly one bar earlier',async function(){
    g.route(function(req){ return g.okPage(g.bars(NEWEST,M15,220,true)); });
    const c=await g.fetchCandles('EUR_USD','M15',220);
    ok(Array.isArray(c),'a plain array is still returned');
    eq(c.length,219,'220 raw bars with the newest still forming must yield 219 CLOSED bars');
    eq(c[0].t.toISOString(),'2026-05-29T17:15:00.000Z','oldest closed bar (NEWEST - 219*15min)');
    eq(c[218].t.toISOString(),'2026-05-31T23:45:00.000Z','newest CLOSED bar (NEWEST - 15min)');
    const formingPresent=c.some(function(x){ return x.t.getTime()===NEWEST; });
    ok(!formingPresent,'the forming bar 2026-06-01T00:00:00.000Z must appear nowhere in the series');
    eq(c.rawResponseCount,220,'raw response size is recorded as it arrived');
    eq(c.receivedCount,219,'received count is the CLOSED count');
    eq(c.requestedCount,220,'requested count is what was asked for');
    eq(g.marketDataCompletenessOf(c),'COMPLETE','the RAW size satisfied the request, so this is COMPLETE');
    return '220 raw / 219 closed, forming bar excluded, COMPLETE';
  });

  // MUTATION PAIRED: `out.reverse()`, `out.splice(out.length-1,1)` and
  // `out.push(out[out.length-1])` before the completeness attach. MDCONT-1 pins the ENDPOINTS and the
  // count; this pins every bar BETWEEN them, which endpoint assertions cannot see.
  await t('MDCONT-2 the delivered series is oldest-first on an exact 15-minute grid, with no interior drop, duplicate or reordering',async function(){
    g.route(function(req){ return g.okPage(g.bars(NEWEST,M15,220,true)); });
    const c=await g.fetchCandles('EUR_USD','M15',220);
    const t0=Date.parse('2026-05-29T17:15:00.000Z');
    let bad=-1;
    for(let i=0;i<c.length;i++){ if(c[i].t.getTime()!==t0+i*M15){ bad=i; break; } }
    eq(bad,-1,'bar '+bad+' is not at its hand-computed grid position '+
      (bad>=0?new Date(t0+bad*M15).toISOString()+' (got '+(c[bad]&&c[bad].t.toISOString())+')':''));
    const seen={};let dupes=0;
    c.forEach(function(x){ const k=x.t.getTime(); if(seen[k]) dupes++; seen[k]=1; });
    eq(dupes,0,'no timestamp may appear twice');
    return '219 bars, strictly +15min each, 0 duplicates';
  });

  // BOUNDARY: a weekend hole is legitimate market structure, not incompleteness. ADR-011 forbids a
  // missingCandles reading; this proves production neither condemns the response nor fabricates
  // bars across the hole nor drops the bars either side of it.
  await t('MDCONT-3 a real weekend gap is carried through intact and is NOT treated as incomplete',async function(){
    // 110 hourly bars ending Friday 2026-05-29T21:00Z, then 110 starting Sunday 2026-05-31T22:00Z.
    // 2026-05-29 is a Friday and 2026-05-31 a Sunday: the hole is 49 hours wide, by hand.
    const friClose=Date.parse('2026-05-29T21:00:00.000Z');
    const sunOpen=Date.parse('2026-05-31T22:00:00.000Z');
    const page=g.bars(friClose,HOUR,110,false).concat(g.bars(sunOpen+109*HOUR,HOUR,110,false));
    g.route(function(req){ return g.okPage(page); });
    const c=await g.fetchCandles('EUR_USD','H1',220);
    eq(c.length,220,'every bar either side of the weekend must survive -- none dropped, none invented');
    eq(g.marketDataCompletenessOf(c),'COMPLETE',
      'PARTIAL means the REQUEST was unsatisfied; it must never mean "N candles are missing"');
    eq(c[109].t.toISOString(),'2026-05-29T21:00:00.000Z','last bar before the weekend');
    eq(c[110].t.toISOString(),'2026-05-31T22:00:00.000Z','first bar after it, adjacent in the array');
    eq(c[110].t.getTime()-c[109].t.getTime(),49*HOUR,'the 49-hour hole is preserved, not filled');
    return '220 bars across a 49h weekend hole -> COMPLETE, gap intact';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // B. THE GATE FIRES / DOES NOT FIRE  (positive + negative on the SAME series)
  // ══════════════════════════════════════════════════════════════════════════════════════════

  // NEGATIVE CONTROL, and the precondition that makes MDCONT-5 meaningful: this exact price series
  // DOES produce a non-zero verdict when the gate blesses it. Without this, MDCONT-5's "zero"
  // assertion could pass for the wrong reason -- a series that scores zero either way.
  await t('MDCONT-4 a healthy full response is COMPLETE, is NOT suppressed, and the frozen evaluators genuinely score it',async function(){
    g.setActiveTf('M15'); g.resetPairData(); g.resetFiredAlerts();
    g.route(honest({dur:M15,formingLast:true}));
    await g.scanPair('EUR_USD');
    const pd=g.pairData()['EUR_USD'];
    eq(pd.completenessState,'COMPLETE','a full raw response with one forming bar is COMPLETE');
    eq(pd.evaluationSuppressed,false,'the gate must not fire on healthy data');
    eq(pd.candles.length,219,'219 closed bars were handed to the evaluators');
    ok(pd.conf.total>0,'the frozen confluence engine produced a non-zero score on this series');
    return 'COMPLETE, not suppressed, conf.total='+pd.conf.total+' on 219 bars';
  });

  // POSITIVE CONTROL. One bar short of the requested lookback -- the exact boundary.
  // MUTATION PAIRED: `rawCount>=requestedCount` -> `rawCount>=requestedCount-1`, and separately
  // scanPair's `evaluable = COMPLETE ? candles : null` -> `evaluable = candles`.
  await t('MDCONT-5 ONE bar short of the requested lookback is PARTIAL, and the evaluators are handed nothing at all',async function(){
    g.setActiveTf('M15'); g.resetPairData(); g.resetFiredAlerts();
    g.route(function(req){
      if(req.kind==='pricing') return g.okPrice();
      return g.okPage(g.bars(NEWEST-M15,M15,219,false));   // 219 raw, all closed, against a request for 220
    });
    await g.scanPair('EUR_USD');
    const pd=g.pairData()['EUR_USD'];
    eq(pd.completenessState,'PARTIAL','219 raw against a request for 220 is PARTIAL, not COMPLETE');
    eq(pd.evaluationSuppressed,true,'and evaluation must be suppressed');
    eq(pd.signals.length,0,'the frozen signal detector must have received nothing');
    eq(pd.conf.total,0,'and the frozen confluence engine must have received nothing (MDCONT-4 proves this series scores >0 when blessed)');
    eq(pd.candles.length,219,'yet the full data is still retained for charting and diagnostics');
    eq(pd.receivedCount,219,'the verdict describes the series actually stored');
    return 'PARTIAL at requested-1, evaluators given null, 219 bars still stored';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // C. PAGINATION AND CONTINUITY  (fetchCandlesRange)
  // ══════════════════════════════════════════════════════════════════════════════════════════

  // MUTATION PAIRED: re-introducing the historical defect -- `if(rawCount<count){shortPages++;
  // termination='RAW_COUNT_SHORT'; break;}` plus RAW_COUNT_SHORT counted as satisfied.
  await t('MDCONT-6 a SHORT page does not end the walk -- the next page repairs the shortfall and the request is genuinely satisfied',async function(){
    g.route(function(req){
      if(req.index===0) return g.okPage(g.bars(NEWEST,HOUR,148,true));   // 148 raw, newest forming -> 147 closed
      return honest({dur:HOUR})(req);
    });
    const c=await g.fetchCandlesRange('EUR_USD','H1',150);
    eq(c.length,150,'the walk must continue past the short page and reach the requested count');
    eq(c.paginationTerminationReason,'REACHED_COUNT','the request was reached, not abandoned');
    eq(c.pagesRequested,2,'exactly two pages were needed');
    eq(c.shortPages,1,'the shortfall is still recorded as a diagnostic');
    eq(g.marketDataCompletenessOf(c),'COMPLETE','a repaired window is COMPLETE');
    return '148-of-150 first page repaired by page 2 -> 150 bars, REACHED_COUNT';
  });

  // MUTATION PAIRED: `all=chunk.concat(all)` -> `all=all.concat(chunk)`.
  // The page seam is where a merge silently reverses: page 2 is OLDER than page 1, so appending
  // instead of prepending produces a series that still has the right length and the right bars.
  await t('MDCONT-7 pages merge OLDEST-FIRST across the seam, contiguously, with no duplicate bar',async function(){
    g.route(function(req){
      if(req.index===0) return g.okPage(g.bars(NEWEST,HOUR,148,true));
      return honest({dur:HOUR})(req);
    });
    const c=await g.fetchCandlesRange('EUR_USD','H1',150);
    // page 1 closed bars: NEWEST-147h .. NEWEST-1h. page 2 supplies the 3 immediately older:
    // NEWEST-150h, -149h, -148h  ->  2026-05-25T18:00Z, 19:00Z, 20:00Z
    eq(c[0].t.toISOString(),'2026-05-25T18:00:00.000Z','the OLDEST bar (from page 2) is first');
    eq(c[2].t.toISOString(),'2026-05-25T20:00:00.000Z','page 2 ends where page 1 begins');
    eq(c[3].t.toISOString(),'2026-05-25T21:00:00.000Z','page 1 resumes at the very next hour');
    eq(c[149].t.toISOString(),'2026-05-31T23:00:00.000Z','the NEWEST closed bar is last');
    let bad=-1;
    for(let i=1;i<c.length;i++){ if(c[i].t.getTime()-c[i-1].t.getTime()!==HOUR){ bad=i; break; } }
    eq(bad,-1,'every step across the seam must be exactly one hour (first break at index '+bad+')');
    return 'seam 20:00 -> 21:00 contiguous, 150 bars strictly +1h';
  });

  // NEGATIVE CONTROL for MDCONT-6's detector: a short page that is genuinely the end of history must
  // NOT be condemned. MUTATION PAIRED: dropping `||termination==='EMPTY_PAGE'` from `satisfied`.
  await t('MDCONT-8 a genuinely EXHAUSTED history is COMPLETE even though it is short -- the walk stops on an empty page, not on a hunch',async function(){
    g.route(function(req){
      if(req.index===0) return g.okPage(g.bars(NEWEST,HOUR,148,true));
      return g.emptyPage();
    });
    const c=await g.fetchCandlesRange('EUR_USD','H1',150);
    eq(c.length,147,'only the 147 bars that exist');
    eq(c.paginationTerminationReason,'EMPTY_PAGE','exhaustion is PROVEN by an empty continuation');
    eq(g.marketDataCompletenessOf(c),'COMPLETE',
      'a window pinned at the true start of history cannot move on a later poll, so it is safe to evaluate');
    eq(c[0].t.toISOString(),'2026-05-25T21:00:00.000Z','pinned at the real start of history');
    return '147 bars, EMPTY_PAGE -> COMPLETE';
  });

  // FAILURE ISOLATION at the transport layer.
  // MUTATIONS PAIRED: `satisfied=true`, and `HTTP_ERROR` relabelled `EMPTY_PAGE`.
  await t('MDCONT-9 a mid-walk HTTP failure leaves the request UNSATISFIED -- it is PARTIAL, and it is not laundered into exhaustion',async function(){
    g.route(function(req){
      if(req.index===0) return g.okPage(g.bars(NEWEST,HOUR,148,true));
      return g.errPage(500);
    });
    const c=await g.fetchCandlesRange('EUR_USD','H1',150);
    eq(c.length,147,'the accumulation from page 1 is returned');
    eq(c.paginationTerminationReason,'HTTP_ERROR','a transport failure is its own distinct fact');
    eq(c.httpStatus,500,'and the status is recorded for forensics');
    eq(g.marketDataCompletenessOf(c),'PARTIAL','an unsatisfied request can never be COMPLETE');
    return '147 bars, HTTP_ERROR 500 -> PARTIAL';
  });

  // DELIBERATELY NOT DUPLICATED HERE: a fixture for the CURSOR_NOT_ADVANCING guard would be a
  // strict subset of v130's CURSOR-1, which already asserts the termination reason, PARTIAL, the
  // un-accumulated length, candle distinctness and the two-page stop -- and which was confirmed to
  // kill the guard-removal mutation on its own. Counting it again here would inflate the fixture
  // count without adding one discriminating assertion.

  // MUTATION PAIRED: the backward cursor taken from the NEWEST bar of the page
  // (`chunk[chunk.length-1]`) instead of the OLDEST (`chunk[0]`).
  await t('MDCONT-10 the backward cursor is the OLDEST bar of the page minus one second, so consecutive pages abut exactly',async function(){
    g.route(honest({dur:HOUR,maxPerPage:200}));
    const c=await g.fetchCandlesRange('EUR_USD','H1',300);
    const reqs=g.candleReqs();
    eq(reqs.length,2,'300 bars at 200 per page is exactly two requests');
    eq(reqs[1].to,'2026-05-23T16:59:59.000Z',
      'page 2 must be cursored one second before page 1\'s OLDEST bar (2026-05-23T17:00:00.000Z)');
    eq(c.length,300,'and the two pages must add up rather than overlap');
    eq(c[0].t.toISOString(),'2026-05-19T13:00:00.000Z','oldest bar = NEWEST - 299h');
    eq(c[299].t.toISOString(),'2026-06-01T00:00:00.000Z','newest bar = NEWEST');
    let bad=-1;
    for(let i=1;i<c.length;i++){ if(c[i].t.getTime()-c[i-1].t.getTime()!==HOUR){ bad=i; break; } }
    eq(bad,-1,'the 300-bar window is contiguous end to end (first break at index '+bad+')');
    return 'to=2026-05-23T16:59:59.000Z, 300 contiguous bars';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // D. MULTI-INSTRUMENT OBSERVATION — is every configured instrument actually observed?
  // ══════════════════════════════════════════════════════════════════════════════════════════

  // MUTATION PAIRED: one instrument filtered out of scanAll's dispatch chunks.
  await t('MDCONT-11 one sweep observes EVERY configured instrument -- the coverage ledger names all of them and skips none',async function(){
    g.setActiveTf('M15'); g.resetPairData(); g.resetFiredAlerts(); g.initScan();
    g.setAutoTradingEnabled(false); g.resetObs();
    g.route(honest({dur:M15,formingLast:true}));
    await g.scanAll();
    const o=g.lastObs();
    eq(o.instrumentsAttempted,g.ALL_PAIRS.length,'every configured instrument must be dispatched');
    eq((o.instrumentsEvaluated||[]).length,g.ALL_PAIRS.length,'and every one of them evaluated');
    eq((o.instrumentsSkipped||[]).length,0,'nothing may be skipped when every instrument is healthy');
    const missing=g.ALL_PAIRS.filter(function(p){ return (o.instrumentsEvaluated||[]).indexOf(p)===-1; });
    eq(missing.length,0,'not one instrument may be absent from the evaluated set: missing '+missing.join(','));
    return g.ALL_PAIRS.length+' instruments dispatched, '+g.ALL_PAIRS.length+' evaluated, 0 skipped';
  });

  // FAILURE ISOLATION + the ledger's own negative control.
  // MUTATION PAIRED: `__jvmResults[p]===COMPLETE` -> `true` (every instrument that produced any
  // result counts as evaluated).
  await t('MDCONT-12 one dead instrument and one short instrument are reported as such, and neither blanks nor blesses the other 33',async function(){
    g.setActiveTf('M15'); g.resetPairData(); g.resetFiredAlerts(); g.initScan();
    g.setAutoTradingEnabled(false); g.resetObs();
    const base=honest({dur:M15,formingLast:true});
    g.route(function(req){
      if(req.kind==='candles'&&req.instrument==='GBP_JPY') return g.errPage(500);
      if(req.kind==='candles'&&req.instrument==='AUD_CAD') return g.okPage(g.bars(NEWEST-M15,M15,219,false));
      return base(req);
    });
    await g.scanAll();
    const o=g.lastObs();
    const skipped=o.instrumentsSkipped||[];
    eq(o.instrumentsAttempted,g.ALL_PAIRS.length,'all instruments are still dispatched');
    eq((o.instrumentsEvaluated||[]).length,g.ALL_PAIRS.length-2,'exactly two instruments fall out');
    eq(skipped.length,2,'and exactly two are reported skipped');
    const dead=skipped.filter(function(s){return s.pair==='GBP_JPY';})[0];
    const short=skipped.filter(function(s){return s.pair==='AUD_CAD';})[0];
    ok(dead,'the dead instrument must be named');
    eq(dead.reason,'MARKET_DATA_UNAVAILABLE','no data arrived -- a transport fact');
    ok(short,'the short instrument must be named');
    eq(short.reason,'EVALUATION_SUPPRESSED_INCOMPLETE_DATA','data arrived and failed the contract -- a different fact');
    ok((o.instrumentsEvaluated||[]).indexOf('EUR_USD')!==-1,'a healthy neighbour is still evaluated');
    eq(g.pairData()['EUR_USD'].evaluationSuppressed,false,'and is genuinely scored, not merely listed');
    return '2 skipped ('+dead.reason+' / '+short.reason+'), '+(o.instrumentsEvaluated||[]).length+' evaluated';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // E. MULTI-TIMEFRAME — every required timeframe is checked, independently
  // ══════════════════════════════════════════════════════════════════════════════════════════

  // MUTATION PAIRED: ALEX's required-timeframe list ['W','D','H4','H1'] -> ['H1'].
  await t('MDCONT-13 a short WEEKLY alone suppresses the pair, and is named as the offending timeframe',async function(){
    g.clearDecisionEvents();
    g.route(function(req){
      if(req.kind==='pricing') return g.okPrice();
      if(req.granularity==='W') return g.okPage(g.bars(NEWEST,g.TF_MS.W,72,false));   // 72 of the 73 requested, replayed
      if(req.granularity==='D') return honest({dur:g.TF_MS.D})(req);
      if(req.granularity==='H4') return honest({dur:g.TF_MS.H4})(req);
      if(req.granularity==='H1') return honest({dur:HOUR})(req);
      return g.errPage(503);
    });
    const r=await g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|MDCONT-13');
    eq(r.evaluated,false,'the pair must not be evaluated');
    eq(r.reason,'DATA_TIMEFRAME_INCOMPLETE','data arrived but failed the contract -- not a transport fault');
    eq((r.incompleteTimeframes||[]).join(','),'W','exactly the Weekly, and nothing else, is named');
    return 'W short -> DATA_TIMEFRAME_INCOMPLETE [W]';
  });

  // NEGATIVE CONTROL for MDCONT-13: with all four timeframes satisfied the same path evaluates.
  // Without this, an edit that suppressed every pair unconditionally would pass MDCONT-13.
  await t('MDCONT-14 with all four required timeframes COMPLETE the same pair IS evaluated -- the gate is not a blanket refusal',async function(){
    g.clearDecisionEvents();
    g.route(function(req){
      if(req.kind==='pricing') return g.okPrice();
      if(req.granularity==='W') return honest({dur:g.TF_MS.W})(req);
      if(req.granularity==='D') return honest({dur:g.TF_MS.D})(req);
      if(req.granularity==='H4') return honest({dur:g.TF_MS.H4})(req);
      if(req.granularity==='H1') return honest({dur:HOUR})(req);
      return g.errPage(503);
    });
    const r=await g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|MDCONT-14');
    eq(r.evaluated,true,'a fully satisfied pair must reach the frozen engine');
    ok(!r.reason||r.reason==='EVALUATED','no suppression reason may be recorded: got '+r.reason);
    return 'W/D/H4/H1 all COMPLETE -> evaluated';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // F. FRESHNESS, PERSISTENCE/RESTART, AND END-TO-END
  // ══════════════════════════════════════════════════════════════════════════════════════════

  // MUTATION PAIRED: scanPair keeping the PREVIOUS sweep's candle array under the CURRENT sweep's
  // completeness verdict -- a stale bar served as fresh, with a fresh bill of health attached.
  await t('MDCONT-15 the second sweep stores the SECOND sweep\'s bars -- a stale series is never served under a fresh verdict',async function(){
    g.setActiveTf('M15'); g.resetPairData(); g.resetFiredAlerts();
    g.route(honest({dur:M15,newest:NEWEST,formingLast:true}));
    await g.scanPair('EUR_USD');
    const first=g.pairData()['EUR_USD'].candles;
    eq(first[first.length-1].t.toISOString(),'2026-05-31T23:45:00.000Z','sweep 1 ends at NEWEST-15min');
    // One bar later: the newest forming bar is now 2026-06-01T00:15:00Z, so the newest CLOSED bar
    // must become 2026-06-01T00:00:00.000Z.
    g.route(honest({dur:M15,newest:NEWEST+M15,formingLast:true}));
    await g.scanPair('EUR_USD');
    const pd=g.pairData()['EUR_USD'];
    eq(pd.candles[pd.candles.length-1].t.toISOString(),'2026-06-01T00:00:00.000Z',
      'sweep 2 must store its OWN newest closed bar, not sweep 1\'s');
    eq(pd.candles[0].t.toISOString(),'2026-05-29T17:30:00.000Z','and its own window start, rolled forward by one bar');
    eq(pd.receivedCount,pd.candles.length,'the recorded verdict describes the series actually stored');
    eq(pd.completenessState,'COMPLETE','and the fresh series is the one that was blessed');
    return 'sweep 1 -> 23:45Z, sweep 2 -> 00:00Z (rolled forward one bar)';
  });

  // END-TO-END + FAILURE ISOLATION on the path whose output actually gates real trades:
  // scanData[pair].bucket==='Active watch' is checkAutoTrades' eligibility filter.
  await t('MDCONT-16 an incomplete WEEKLY suppresses that pair\'s tradeable bucket and leaves the other eleven assessed',async function(){
    g.setScanData({}); g.lsClear();
    const bases={W:honest({dur:g.TF_MS.W}),D:honest({dur:g.TF_MS.D}),H4:honest({dur:g.TF_MS.H4})};
    g.route(function(req){
      if(req.kind==='pricing') return g.okPrice();
      if(req.instrument==='GBP_CHF'&&req.granularity==='W')
        return g.okPage(g.bars(NEWEST,g.TF_MS.W,req.count-1,false));   // one weekly bar short
      const b=bases[req.granularity];
      return b?b(req):g.errPage(503);
    });
    await g.runAutoTopDownScan();
    const sd=g.getScanData();
    eq(sd['GBP/CHF'].completenessSuppressed,true,'the short pair is marked as a DATA fault');
    eq(sd['GBP/CHF'].bucket,'—','and is not eligible for a trade this cycle');
    eq(sd['GBP/CHF'].completenessByTimeframe.W,'PARTIAL','the offending timeframe is named');
    eq(sd['GBP/CHF'].completenessByTimeframe.D,'COMPLETE','and the healthy ones are not tarred with it');
    const others=g.SCAN_PAIRS.filter(function(p){ return p!=='GBP/CHF'; });
    const assessed=others.filter(function(p){ return sd[p]&&sd[p].completenessSuppressed===false; });
    eq(assessed.length,others.length,'all eleven other instruments must still be assessed: '+
      others.filter(function(p){return !(sd[p]&&sd[p].completenessSuppressed===false);}).join(','));
    return '1 suppressed (W PARTIAL), '+assessed.length+'/'+others.length+' others assessed';
  });

  // PERSISTENCE / RESTART: the verdicts above are written to localStorage by save() and are what a
  // reload restores. A restart must not launder the suppressed pair into an eligible one.
  await t('MDCONT-17 the per-pair completeness verdict survives a reload unchanged -- a restart cannot bless what the gate refused',async function(){
    const before=JSON.parse(JSON.stringify(g.getScanData()));
    ok(g.lsGet('fxhub_scan')!=null,'the scan state was actually persisted');
    g.setScanData({});                       // the reload boundary: in-memory state is gone
    eq(Object.keys(g.getScanData()).length,0,'in-memory scan state is genuinely empty before the reload');
    g.loadSaved();                           // the real restore path
    const after=g.getScanData();
    eq(after['GBP/CHF'].completenessSuppressed,true,'the suppressed pair is STILL suppressed after the reload');
    eq(after['GBP/CHF'].bucket,'—','and is still not tradeable');
    eq(after['GBP/CHF'].completenessByTimeframe.W,'PARTIAL','with the offending timeframe still named');
    const drifted=g.SCAN_PAIRS.filter(function(p){
      return JSON.stringify(after[p])!==JSON.stringify(before[p]); });
    eq(drifted.length,0,'no pair\'s verdict may change across the reload: drifted '+drifted.join(','));
    return '12 verdicts restored byte-identical; GBP/CHF still suppressed';
  });

  // PERSISTENCE / RESTART, continued: after the reload the acquisition path must re-derive the
  // same correctly-ordered window from the same broker, not a shifted or reversed one.
  await t('MDCONT-18 after a reload the re-fetched series is complete, correctly ordered and identical to the pre-reload window',async function(){
    g.setActiveTf('M15'); g.resetPairData(); g.resetFiredAlerts();
    g.route(honest({dur:M15,formingLast:true}));
    await g.scanPair('EUR_USD');
    const pre=g.pairData()['EUR_USD'].candles.map(function(x){return x.t.getTime();});
    g.resetPairData(); g.loadSaved();        // the reload boundary: pairData is in-memory only
    // loadSaved() is the real restore path. It must NOT resurrect a candle series: a window blessed
    // before the restart says nothing about the market now, and serving it would be the stale-bar
    // defect with a reload in front of it.
    eq(g.pairData()['EUR_USD'],undefined,'loadSaved() must not restore a pre-restart candle series');
    await g.scanPair('EUR_USD');
    const post=g.pairData()['EUR_USD'].candles.map(function(x){return x.t.getTime();});
    eq(post.length,219,'the rebuilt window holds the same 219 closed bars');
    eq(new Date(post[0]).toISOString(),'2026-05-29T17:15:00.000Z','starting at the same hand-computed bar');
    eq(new Date(post[218]).toISOString(),'2026-05-31T23:45:00.000Z','and ending at the same one');
    eq(post.join(','),pre.join(','),'every bar identical, in the same order, across the restart');
    eq(g.pairData()['EUR_USD'].completenessState,'COMPLETE','and the rebuilt window is blessed on its own terms');
    return '219 bars re-derived identically after reload';
  });

  // ══ 🔴 MDSTAMP — the PRODUCER stamped the live activeTf after its own await (§18.24) ═════════
  // v12.28.0 fixed the CONSUMER (loadChart refuses a verdict stamped with another timeframe) and
  // v12.31.0 captured the timeframe there. But scanPair issued its fetch with activeTf and then
  // wrote `timeframe:activeTf` AFTER the await -- so an operator switching timeframes mid-sweep
  // made the stamp itself a lie, the consumer's guard matched, engine authority was granted, and
  // awaitingScanForTimeframe could never fire. Reproduced by an independent verifier end to end:
  // a 220-bar H1 series scored 53 and rendered as "the scanner's own H4 verdict", SHORT 53%.
  await t('MDSTAMP-1 a timeframe switched DURING a sweep cannot mislabel the verdict that sweep produced',async function(){
    g.setActiveTf('H1'); g.resetPairData(); g.resetFiredAlerts();
    g.route(honest({dur:HOUR,formingLast:true}));
    // Started WITHOUT awaiting, then the timeframe is switched -- exactly where an operator's click
    // lands: after the fetch has begun, before the pairData write runs.
    const pending=g.scanPair('EUR_USD');
    g.setActiveTf('H4');
    await pending;
    const pd=g.pairData()['EUR_USD'];
    eq(pd.timeframe,'H1',
      'the verdict must carry the timeframe it was COMPUTED on, not the one the operator switched to');
    return 'stamped H1 despite the mid-sweep switch to H4';
  });

  await t('MDSTAMP-2 (POSITIVE CONTROL) an undisturbed sweep still stamps the timeframe it ran on',async function(){
    // So MDSTAMP-1 is the capture working, not a stamp pinned to a constant.
    g.setActiveTf('H4'); g.resetPairData(); g.resetFiredAlerts();
    g.route(honest({dur:HOUR,formingLast:true}));
    await g.scanPair('EUR_USD');
    eq(g.pairData()['EUR_USD'].timeframe,'H4','an H4 sweep stamps H4');
    return 'stamp follows the sweep';
  });

  // ══ 🔴 MDHIST — runHistoricalDataDiagnostic: a SECOND copy of the pagination arithmetic ══════
  // Independent adversarial verification found this function had ZERO behavioural coverage: three
  // separate behaviour-changing mutations each killed 0 of 2,180 fixtures. It is an entirely
  // separate implementation of the backward walk from fetchCandlesRange, reached from the
  // Diagnostics "Historical Data Diagnostic" button -- so the tool an operator uses to CHECK data
  // continuity could report a reversed, duplicated or truncated window as healthy.
  //
  // Signature is (pair, granularity, totalCount, onProgress); the walk continues until it holds
  // totalCount COMPLETE bars. Page 1 returns 10 raw bars whose newest is still FORMING -- 9
  // complete -- so a second page is required for the 10th. Every timestamp is hand-computed.
  const HIST_H=3600000;
  const HIST_P1_END=Date.parse('2026-06-01T09:00:00.000Z');   // START of the newest (forming) bar
  const HIST_P1_NEWEST_COMPLETE=HIST_P1_END-HIST_H;           // 2026-06-01T08:00Z
  const HIST_P1_OLDEST=HIST_P1_END-9*HIST_H;                  // 2026-06-01T00:00Z
  const HIST_P2_BAR=HIST_P1_OLDEST-HIST_H;                    // 2026-05-31T23:00Z

  await t('MDHIST-1 the diagnostic pages BACKWARDS and merges older pages BEFORE newer ones',async function(){
    let page=0;
    g.route(function(req){
      if(req.kind!=='candles') return g.okPrice();
      page++;
      if(page===1) return g.okPage(g.bars(HIST_P1_END,HIST_H,10,true));
      if(page===2) return g.okPage(g.bars(HIST_P2_BAR,HIST_H,1));
      return g.emptyPage();
    });
    const diag=await g.runHistoricalDataDiagnostic('EUR_USD','H1',10,null);
    const reqs=g.candleReqs();
    eq(diag.earliest,new Date(HIST_P2_BAR).toISOString(),
      'the window must START at the second page\'s bar -- a reversed merge would start later');
    eq(diag.latest,new Date(HIST_P1_NEWEST_COMPLETE).toISOString(),
      'and END at the newest COMPLETE bar of the first page, never the forming one');
    eq(reqs[1].to,new Date(HIST_P1_OLDEST-1000).toISOString(),
      'page 2 must be requested one second before the OLDEST bar of page 1 -- reading the NEWEST end would re-request the window just walked');
    eq(reqs.length,2,
      'a page whose RAW count equals the requested count must NOT end the walk, so exactly two requests are made');
    eq(diag.requestCount,2,'and the diagnostic reports both pages');
    eq(diag.totalUnique,10,'the merged window holds exactly the 10 unique complete bars');
    eq(diag.duplicates,0,'with no duplicate across the page boundary');
    return 'backward walk, merge order, cursor and termination all pinned';
  });

  // §18.26 EQUIVALENT MUTANT, recorded rather than chased: taking requestCount from the loop
  // `guard` instead of `pages.length` cannot be detected, because guard++ runs once per iteration
  // and EVERY path through the body pushes exactly one pages entry before continuing or breaking.
  // The two are equal by construction. An unkillable mutation is not a coverage gap when the
  // substitution is provably behaviour-preserving -- it is reported as equivalent, like AG-21.
  await t('MDHIST-4 the REPORTED coverage figures are the ones the operator reads, and each is pinned',async function(){
    // §18.26: MDHIST-1..3 pinned the WALK -- the cursor, the merge order, the termination test --
    // but every field the diagnostic actually REPORTS was unwatched. An independent sweep changed
    // calendarDays by 7, made tradingDays count weekends, dropped duplicates from totalRaw, took
    // requestCount from the loop guard instead of the page list, and resized every page request:
    // each killed 0 of 2,207. That is the same "second unwatched copy" shape MDHIST-1 closed, one
    // layer out -- the tool an operator uses to CHECK coverage can still misreport its own.
    //
    // Ten DAILY bars, 2026-06-01 (Mon) through 2026-06-10 (Wed), all complete. Every figure below
    // is hand-computed from that window: Mon-Fri gives 8 trading days, the span is 9 calendar days.
    const D=86400000;
    const D_END=Date.parse('2026-06-10T00:00:00.000Z');
    let page=0;
    g.route(function(req){
      if(req.kind!=='candles') return g.okPrice();
      page++;
      if(page===1) return g.okPage(g.bars(D_END,D,10));   // exactly the requested count, all closed
      return g.emptyPage();
    });
    const rep=await g.runHistoricalDataDiagnostic('EUR_USD','D',10,null);
    eq(rep.earliest,'2026-06-01T00:00:00.000Z','the window starts at the Monday');
    eq(rep.latest,'2026-06-10T00:00:00.000Z','and ends at the Wednesday nine days later');
    eq(rep.calendarDays,9,'calendarDays is the SPAN (9), not the bar count (10)');
    eq(rep.tradingDays,8,'tradingDays counts Mon-Fri only -- the Saturday and Sunday in that window are excluded');
    eq(rep.totalUnique,10,'ten unique bars');
    eq(rep.totalRaw,10,'and totalRaw includes every bar seen, duplicates included -- here there are none');
    eq(rep.duplicates,0,'no duplicate across the single page');
    eq(rep.requestCount,1,'one page was needed, and requestCount reports PAGES rather than loop iterations');
    return '9 calendar days, 8 trading days, 10 unique bars, 1 page';
  });

  await t('MDHIST-5 (POSITIVE CONTROL) a window containing MORE weekend days reports fewer trading days',async function(){
    // So MDHIST-4's 8 is the weekday filter working, not a constant that happens to match.
    const D=86400000;
    const D_END=Date.parse('2026-06-08T00:00:00.000Z');   // Mon 2026-06-01 .. Mon 2026-06-08
    let page=0;
    g.route(function(req){
      if(req.kind!=='candles') return g.okPrice();
      page++;
      if(page===1) return g.okPage(g.bars(D_END,D,8));
      return g.emptyPage();
    });
    const rep2=await g.runHistoricalDataDiagnostic('EUR_USD','D',8,null);
    eq(rep2.calendarDays,7,'a seven-day span');
    eq(rep2.tradingDays,6,'containing one Saturday and one Sunday -- six trading days, not eight');
    return '7 calendar days, 6 trading days';
  });

  await t('MDHIST-2 (BOUNDARY) a SHORT page ends the walk immediately',async function(){
    // Paired with MDHIST-1 this pins BOTH sides of the termination test, so neither `<` nor `<=`
    // can be substituted without a fixture dying.
    let page=0;
    g.route(function(req){
      if(req.kind!=='candles') return g.okPrice();
      page++;
      if(page===1) return g.okPage(g.bars(HIST_P1_END,HIST_H,4));   // 4 raw for a request of 10
      return g.okPage(g.bars(HIST_P1_END-20*HIST_H,HIST_H,4));
    });
    const short=await g.runHistoricalDataDiagnostic('EUR_USD','H1',10,null);
    eq(g.candleReqs().length,1,'one request only -- a short page means the history is exhausted');
    eq(short.totalUnique,4,'and the diagnostic reports the 4 bars it genuinely has rather than walking on');
    return 'short page terminates the walk';
  });

  await t('MDHIST-3 (POSITIVE CONTROL) a bar repeated across the page boundary IS counted',async function(){
    // Without this, MDHIST-1's `duplicates === 0` would also be satisfied by a duplicate detector
    // that never fires at all.
    let page=0;
    g.route(function(req){
      if(req.kind!=='candles') return g.okPrice();
      page++;
      if(page===1) return g.okPage(g.bars(HIST_P1_END,HIST_H,10,true));
      if(page===2) return g.okPage(g.bars(HIST_P1_OLDEST,HIST_H,1));   // REPEATS page 1's oldest bar
      return g.emptyPage();
    });
    const dup=await g.runHistoricalDataDiagnostic('EUR_USD','H1',10,null);
    eq(dup.duplicates,1,'the repeated bar must be counted, so MDHIST-1\'s zero is a real zero');
    // §18.26: totalRaw must INCLUDE the duplicate. Asserted here and not in MDHIST-4 because that
    // window has no duplicates, where `all.length + duplicates` and `all.length` are the same
    // number -- the formulas only differ when there is something to lose.
    eq(dup.totalRaw,dup.totalUnique+1,
      'totalRaw counts every bar SEEN including the duplicate, so it exceeds totalUnique by exactly one here');
    return 'duplicate detector genuinely fires, and totalRaw counts it';
  });


    return out;
  })();
}
