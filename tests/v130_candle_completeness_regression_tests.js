// MOGO-003 — Candle-completeness regression fixture (TEST-FIRST).
//
// PURPOSE
// Prove whether incomplete market-data history can reach signal / AOI / swing-point /
// confluence evaluation without any explicit incomplete-data state.
//
// ⚠️ THIS SUITE IS EXPECTED TO CONTAIN FAILURES AGAINST CURRENT PRODUCTION.
// Fixtures prefixed SAFETY-* encode the required safety contract, NOT current behaviour. They
// fail today, deliberately, and must NOT be weakened, inverted, skipped or deleted to make the
// suite green. Fixtures prefixed BEHAVIOUR-* document what production actually does today and
// are expected to pass; if one of those starts failing, production behaviour has changed.
//
// AUDIT FINDING AS ORIGINALLY STATED vs WHAT THE CODE ACTUALLY DOES
// The audit alleged that fetchCandles() paginates and, on a later-page HTTP 429, returns the
// partially accumulated candles. That is NOT what fetchCandles() does:
//   * fetchCandles() issues exactly ONE request and returns null on any non-OK status (429
//     included). It never paginates and never accumulates. BEHAVIOUR-1 / BEHAVIOUR-2 prove it.
// The underlying RISK is nevertheless real, and arrives through two different doors:
//   * fetchCandles() returns a SHORT-BUT-SUCCESSFUL array whenever OANDA returns fewer complete
//     candles than requested. scanPair() requests 220 and will happily accept 80. (SAFETY-1/2/3)
//   * fetchCandlesRange() DOES paginate and DOES break on a later-page HTTP 429, returning the
//     partial accumulation with no error signal whatsoever. (BEHAVIOUR-3 / SAFETY-4)
//
// DATA-MODEL RULE OBSERVED: this fixture never computes or asserts a "missingCandles" value.
// Session, weekend, holiday and liquidity gaps make requestedCount - receivedCount meaningless
// as a measure of missing market data. Every assertion below rests only on directly observable
// facts: what was requested, what was received, how many pages were requested, and whether any
// incomplete-data state was exposed to the caller.
//
// No production function is modified, re-implemented or stubbed. Only the network boundary
// (globalThis.fetch) is scripted, in OANDA's own response shapes.
function runCandleCompletenessFixtures(g){
  const out=[];
  async function t(name,fn){
    try{ const d=await fn(); out.push({name,pass:true,detail:d||''}); }
    catch(e){ out.push({name,pass:false,detail:(e&&e.message)?e.message:String(e)}); }
  }
  function eq(a,b,m){ if(a!==b) throw new Error((m||'')+' expected '+JSON.stringify(b)+', got '+JSON.stringify(a)); }
  function ok(v,m){ if(!v) throw new Error(m||'expected truthy'); }

  const SCANNER_LOOKBACK=220;   // the count scanPair() actually requests
  const PARTIAL=80;             // a plausible truncated result, well above every length guard

  return (async function(){

    // ── BEHAVIOUR-1 ────────────────────────────────────────────────────────────────────────
    await t('BEHAVIOUR-1 fetchCandles() returns null on HTTP 429 (it does NOT accumulate)',async function(){
      g.setFetchScript([g.RESP_429]);
      const c=await g.fetchCandles('EUR_USD','M15',SCANNER_LOOKBACK);
      eq(c,null,'a 429 must yield null, not a partial array');
      eq(g.fetchCallCount(),1,'fetchCandles must issue exactly one request -- it does not paginate');
      return 'requested '+SCANNER_LOOKBACK+', 1 page, HTTP 429 -> null';
    });

    // ── BEHAVIOUR-2 ────────────────────────────────────────────────────────────────────────
    await t('BEHAVIOUR-2 fetchCandles() classifies a SHORT successful response as PARTIAL',async function(){
      // Before ADR-011 this fixture asserted the DEFECT (a bare array carrying no metadata).
      // It now asserts the contract. The array shape is deliberately unchanged -- completeness
      // is attached non-enumerably so all 12 existing call sites are byte-for-byte unaffected.
      g.setFetchScript([g.okCandles(PARTIAL)]);
      const c=await g.fetchCandles('EUR_USD','M15',SCANNER_LOOKBACK);
      ok(Array.isArray(c),'the return type is still a plain array');
      eq(c.length,PARTIAL,'and still carries exactly the candles that arrived');
      eq(g.completenessStateOf(c),'PARTIAL','a short response must be PARTIAL, never COMPLETE');
      eq(c.requestedCount,SCANNER_LOOKBACK,'observable fact: what was requested');
      eq(c.receivedCount,PARTIAL,'observable fact: what was received');
      ok(!Object.prototype.hasOwnProperty.call(c,'missingCandles'),
        'ADR-011: no missingCandles field may exist -- session/weekend/holiday/liquidity gaps '+
        'make requested-minus-received unsound as a measure of missing market data');
      // Non-enumerable: existing consumers, iteration and serialization must be unaffected.
      eq(Object.keys(c).length,PARTIAL,'completeness fields must not become enumerable array keys');
      return 'requested '+SCANNER_LOOKBACK+', received '+c.length+' -> PARTIAL';
    });

    // ── BEHAVIOUR-2b ───────────────────────────────────────────────────────────────────────
    await t('BEHAVIOUR-2b a full response is COMPLETE and still evaluates normally',async function(){
      // The contract must not suppress healthy scans. The newest candle is usually still
      // forming, so the raw response is compared against the request -- not the filtered length.
      g.setFetchScript([g.okCandlesRaw(SCANNER_LOOKBACK,SCANNER_LOOKBACK-1),g.okPrice()]);
      g.setActiveTf('M15');
      g.resetPairData();
      await g.scanPair('EUR_USD');
      const pd=g.pairData()['EUR_USD'];
      eq(pd.completenessState,'COMPLETE',
        'a full raw response with one still-forming candle must be COMPLETE, not PARTIAL');
      eq(pd.evaluationSuppressed,false,'a healthy scan must not be suppressed');
      ok(pd.signals.length>0||pd.conf.total>0,'and must still evaluate normally');
      return 'raw '+SCANNER_LOOKBACK+', usable '+pd.candles.length+' -> COMPLETE, evaluated';
    });

    // ── BEHAVIOUR-3 ────────────────────────────────────────────────────────────────────────
    await t('BEHAVIOUR-3 fetchCandlesRange() DOES return partial accumulation on page-2 HTTP 429',async function(){
      // Page 1 must return rawCount >= requested count or the loop breaks on RAW_COUNT_SHORT
      // before a second page is ever attempted.
      g.setFetchScript([g.okCandlesRaw(SCANNER_LOOKBACK,PARTIAL),g.RESP_429]);
      const c=await g.fetchCandlesRange('EUR_USD','M15',SCANNER_LOOKBACK);
      ok(Array.isArray(c),'returns an array, not null');
      eq(c.length,PARTIAL,'the partial accumulation from page 1 is returned');
      eq(g.fetchCallCount(),2,'two pages were requested; the second failed');
      return 'requested '+SCANNER_LOOKBACK+', pages 2, received '+c.length+' after HTTP 429';
    });

    // ── SAFETY-4 ───────────────────────────────────────────────────────────────────────────
    await t('SAFETY-4 fetchCandlesRange() must expose an incomplete-data state after HTTP 429',async function(){
      g.setFetchScript([g.okCandlesRaw(SCANNER_LOOKBACK,PARTIAL),g.RESP_429]);
      const c=await g.fetchCandlesRange('EUR_USD','M15',SCANNER_LOOKBACK);
      // MOGO-021 §18.14: THIS WAS PRESENCE-ONLY AND FAR WEAKER THAN ITS TITLE. It asserted
      // `hasCompletenessState(c)`, which accepts ANY of COMPLETE / PARTIAL / UNAVAILABLE -- so a
      // change classifying a 429-terminated walk as COMPLETE passed it. Verified: a mutation
      // forcing `satisfied=true` left this fixture green and only CURSOR-1 fired from this suite.
      // Its first disjunct was also dead code: `c` is always an array here, so
      // `!Array.isArray(c)` is always false, and it would have blanket-passed if the return
      // shape ever changed.
      // The contract (ADR-011) is that consumers depend on completenessState and NOTHING else,
      // so that is the load-bearing assertion; the termination reason is asserted as forensics,
      // which is what ADR-011 says those diagnostic fields are for.
      eq(c.completenessState,'PARTIAL',
        'a walk terminated by HTTP 429 must be PARTIAL -- not COMPLETE, and not merely "some state"');
      eq(c.paginationTerminationReason,'HTTP_ERROR',
        'and the diagnostic must name the HTTP failure rather than an ordinary exhaustion');
      return 'incomplete-data state exposed as PARTIAL/HTTP_ERROR';
    });

    // ── CURSOR-1 (MOGO-021 DECISION 1) ─────────────────────────────────────────────────────
    // The cursor guard had NO fixture anywhere: removing it survived all 24 suites. It only
    // became reachable when the walk started continuing past a short page -- while the loop
    // stopped at the first short page, a broker that ignored `&to=` was never asked twice.
    //
    // The scripted boundary repeats its LAST entry for every further request, which IS a broker
    // that ignores the cursor and replays the same page: no scripting trick is needed to produce
    // the condition, only a request that asks for more than one page holds.
    await t('CURSOR-1 fetchCandlesRange() refuses a broker that ignores the `to` cursor',async function(){
      g.setFetchScript([g.okCandles(PARTIAL)]);
      const c=await g.fetchCandlesRange('EUR_USD','M15',SCANNER_LOOKBACK);
      eq(c.paginationTerminationReason,'CURSOR_NOT_ADVANCING',
        'a replayed page must terminate the walk on the cursor, not be paginated against');
      eq(g.marketDataCompletenessOf(c),'PARTIAL',
        'the request was NOT satisfied, so it must never be classified COMPLETE');
      // The consequence that matters: duplicates could reach totalCount and then be classified
      // COMPLETE, handing the engine a corrupt window that looks fully satisfied.
      eq(c.length,PARTIAL,'exactly one page is kept -- not one duplicate candle is accumulated');
      const times=c.map(function(x){return x.t.getTime();});
      eq(new Set(times).size,times.length,'and every candle in the accumulation is distinct');
      eq(c.receivedCount,PARTIAL,'the recorded receivedCount agrees with the accumulation');
      eq(g.fetchCallCount(),2,
        'the walk stops on the SECOND page -- the guard limit is not what ends it');
      return 'requested '+SCANNER_LOOKBACK+', replayed page of '+PARTIAL+
        ' -> CURSOR_NOT_ADVANCING, PARTIAL, '+c.length+' candles, 0 duplicates, 2 pages';
    });

    // ── SAFETY-1 ───────────────────────────────────────────────────────────────────────────
    await t('SAFETY-1 scanPair() must produce zero signals when history is materially incomplete',async function(){
      // The REQUIRED safety assertion, expressed against the path that can actually deliver a
      // truncated history to scanPair(): a successful response carrying far fewer complete
      // candles than the scanner asked for.
      g.setFetchScript([g.okCandles(PARTIAL),g.okPrice()]);
      g.setActiveTf('M15');
      g.resetPairData();
      await g.scanPair('EUR_USD');
      const pd=g.pairData()['EUR_USD'];
      eq(pd.candles.length,PARTIAL,'precondition: scanPair received a truncated history');
      eq(pd.signals.length,0,
        'scanPair() requested '+SCANNER_LOOKBACK+' candles, received only '+pd.candles.length+
        ', and still produced '+pd.signals.length+' signal(s) from that incomplete history');
      return 'zero signals on incomplete history';
    });

    // ── SAFETY-2 ───────────────────────────────────────────────────────────────────────────
    await t('SAFETY-2 scanPair() must not score confluence on materially incomplete history',async function(){
      g.setFetchScript([g.okCandles(PARTIAL),g.okPrice()]);
      g.setActiveTf('M15');
      g.resetPairData();
      await g.scanPair('EUR_USD');
      const pd=g.pairData()['EUR_USD'];
      eq(pd.conf.total,0,
        'scanPair() scored confluence total='+pd.conf.total+' from only '+pd.candles.length+
        ' of '+SCANNER_LOOKBACK+' requested candles -- a score built on incomplete history is '+
        'indistinguishable from one built on a full lookback');
      return 'zero confluence on incomplete history';
    });

    // ── SAFETY-3 ───────────────────────────────────────────────────────────────────────────
    await t('SAFETY-3 pairData must record an explicit incomplete-data state',async function(){
      g.setFetchScript([g.okCandles(PARTIAL),g.okPrice()]);
      g.setActiveTf('M15');
      g.resetPairData();
      await g.scanPair('EUR_USD');
      const pd=g.pairData()['EUR_USD'];
      ok(g.hasCompletenessState(pd),
        'pairData for EUR_USD carries only ['+Object.keys(pd).join(',')+'] -- there is no '+
        'requestedCount, receivedCount, pagesRequested/pagesReceived, httpStatus or '+
        'paginationTerminationReason, so nothing downstream (rendering, alerting, '+
        'checkAutoTrades) can tell a full lookback from a truncated one');
      return 'incomplete-data state recorded';
    });

    // ── BEHAVIOUR-4 ────────────────────────────────────────────────────────────────────────
    await t('BEHAVIOUR-4 an HTTP 429 through scanPair() IS safe today (null short-circuits the guards)',async function(){
      // Documents the one case the audit worried about that production already handles: a 429
      // yields null, and every downstream guard rejects null. This must keep passing.
      g.setFetchScript([g.RESP_429,g.okPrice()]);
      g.setActiveTf('M15');
      g.resetPairData();
      await g.scanPair('EUR_USD');
      const pd=g.pairData()['EUR_USD'];
      eq(pd.candles,null,'a 429 leaves candles null');
      eq(pd.signals.length,0,'null history must produce zero signals');
      eq(pd.conf.total,0,'null history must produce zero confluence');
      return 'HTTP 429 -> null -> zero signals, zero confluence';
    });

    // ── BEHAVIOUR-5 ────────────────────────────────────────────────────────────────────────
    await t('BEHAVIOUR-5 the length guards are the ONLY protection, and 80 clears them easily',async function(){
      g.setFetchScript([g.okCandles(PARTIAL)]);
      const c=await g.fetchCandles('EUR_USD','M15',SCANNER_LOOKBACK);
      // Real, unmodified protected functions -- called, never re-implemented.
      const sigs=g.detectSignals(c,'EUR_USD');
      const conf=g.bestConfluence(c,'EUR_USD');
      ok(c.length>=10,'80 candles clears the length<10 guard in detectSignals/scoreConfluence');
      ok(sigs.length>0||conf.total>0,
        'incomplete history produced signals='+sigs.length+' confluence='+conf.total+
        ' -- the guards bound the MINIMUM usable length, never the REQUESTED length');
      const swings=g.findSwingPoints(c,5);
      ok(swings.swingHighs.length+swings.swingLows.length>=0,'swing detection also runs on the short array');
      return 'signals='+sigs.length+' confluence='+conf.total+' from '+c.length+'/'+SCANNER_LOOKBACK;
    });

    // ══ CONTRACT-* — ATTACHMENT DURABILITY (ADR-011 §5) ══════════════════════════════════
    // completenessState is attached NON-ENUMERABLY so the 21 existing call sites are unaffected.
    // The unavoidable cost is that it does not survive copying. These fixtures pin that down as
    // a MEASURED FACT rather than an assumption, and prove the current call paths do not rely on
    // preservation. If a future consumer needs completeness after a transform, it must read the
    // durable enumerable copy on pairData (CONTRACT-3) -- never re-derive or assume COMPLETE.
    await t('CONTRACT-1 completenessState does NOT survive copying or transformation',async function(){
      g.setFetchScript([g.okCandles(PARTIAL)]);
      const c=await g.fetchCandles('EUR_USD','M15',SCANNER_LOOKBACK);
      eq(g.completenessStateOf(c),'PARTIAL','precondition: the producer classified it');
      const lost=[['slice()',c.slice()],['map()',c.map(function(x){return x;})],
                  ['filter()',c.filter(function(){return true;})],['concat()',c.concat([])],
                  ['spread',[].concat(c)],['Array.from()',Array.from(c)],
                  ['JSON round-trip',JSON.parse(JSON.stringify(c))]];
      lost.forEach(function(p){
        eq(g.completenessStateOf(p[1]),undefined,p[0]+' must be documented as losing the state');
      });
      // ...and the reader treats an unclassified array as UNAVAILABLE, never optimistically COMPLETE.
      eq(g.marketDataCompletenessOf(c.slice()),'UNAVAILABLE',
        'an unclassified array must never be assumed complete -- fail closed');
      return 'lost by all 7 copy/transform forms; unclassified reads as UNAVAILABLE';
    });

    await t('CONTRACT-2 scanPair() reads the producer value directly, so loss cannot occur',async function(){
      // The only reader in the codebase. It must consume fetchCandles()' return value with no
      // intervening copy, or the state would be silently lost and every scan would fail closed.
      // MOGO-021 §18.14: the two clauses below are STRUCTURAL (source-text) assertions, not
      // behavioural evidence -- they survive every behaviour-changing mutation and die on a
      // rename. They are kept because "must not classify a COPY" is a shape invariant with no
      // directly observable behaviour when the copy would be identical, but they are labelled so
      // they are not mistaken for coverage. The behavioural proof below is what actually holds
      // this contract, and MDCONT-4/-5 in v1239 now drive it end to end.
      const src=String(g.scanPair);
      ok(/marketDataCompletenessOf\(candles\)/.test(src),
        'STRUCTURAL: scanPair must classify the producer value itself, not a derived array');
      ok(!/marketDataCompletenessOf\(\s*candles\s*\.\s*(slice|map|filter|concat)/.test(src),
        'STRUCTURAL: scanPair must not classify a copy');
      // Behavioural proof: a PARTIAL response really does reach the gate as PARTIAL.
      g.setFetchScript([g.okCandles(PARTIAL),g.okPrice()]);
      g.setActiveTf('M15'); g.resetPairData();
      await g.scanPair('EUR_USD');
      eq(g.pairData()['EUR_USD'].completenessState,'PARTIAL','the state survived the producer->consumer hop');
      return 'direct read confirmed in source and behaviour';
    });

    await t('CONTRACT-3 pairData carries a DURABLE, enumerable copy that survives serialization',async function(){
      // The fragile non-enumerable form exists only on the producer->consumer hop. Everything
      // downstream (diagnostics, rendering, any future evidence record) reads this copy instead.
      g.setFetchScript([g.okCandles(PARTIAL),g.okPrice()]);
      g.setActiveTf('M15'); g.resetPairData();
      await g.scanPair('EUR_USD');
      const pd=g.pairData()['EUR_USD'];
      ok(Object.keys(pd).indexOf('completenessState')!==-1,'must be an ENUMERABLE field on pairData');
      const round=JSON.parse(JSON.stringify({completenessState:pd.completenessState,
        evaluationSuppressed:pd.evaluationSuppressed,requestedCount:pd.requestedCount,
        receivedCount:pd.receivedCount}));
      eq(round.completenessState,'PARTIAL','it must survive a JSON round-trip');
      eq(round.evaluationSuppressed,true,'as must the suppression flag');
      eq(round.requestedCount,SCANNER_LOOKBACK);
      eq(round.receivedCount,PARTIAL);
      ok(!Object.prototype.hasOwnProperty.call(pd,'missingCandles'),'ADR-011: still no missingCandles');
      return 'durable enumerable copy survives serialization';
    });

    // ══ VISIBILITY — suppression must never be silent to the operator (ADR-011) ═══════════
    await t('VISIBILITY-1 a suppressed pair is surfaced, and stays silent when nothing is suppressed',async function(){
      // Suppressed: the indicator must name the pair and the observable facts.
      g.setFetchScript([g.okCandles(PARTIAL),g.okPrice()]);
      g.setActiveTf('M15'); g.resetPairData();
      await g.scanPair('EUR_USD');
      g.renderMarketDataCompletenessDiagnostics();
      const shown=g.diagnosticsHtml();
      ok(/not evaluated/i.test(shown),'the indicator must say the pair was not evaluated');
      ok(shown.indexOf('EUR_USD')!==-1,'and name the pair');
      ok(shown.indexOf(String(SCANNER_LOOKBACK))!==-1&&shown.indexOf(String(PARTIAL))!==-1,
        'and show requested vs received');
      ok(/not a claim that market data is missing/i.test(shown),
        'ADR-011: it must not imply market data is missing');
      // Healthy: no indicator at all, or the warning becomes noise and gets ignored.
      g.setFetchScript([g.okCandlesRaw(SCANNER_LOOKBACK,SCANNER_LOOKBACK-1),g.okPrice()]);
      g.resetPairData();
      await g.scanPair('EUR_USD');
      g.renderMarketDataCompletenessDiagnostics();
      eq(g.diagnosticsHtml(),'','a fully-satisfied scan must render no indicator at all');
      return 'shown when suppressed, silent when healthy';
    });

    // ══ MOGO-021 item 3 — OPERATOR REACHABILITY, not merely "innerHTML was written" ═══════
    // VISIBILITY-1 above stubs document.getElementById through a flat map, so it passes identically
    // whether the container is on screen or inside a display:none panel. It was, and that is how a
    // suppressed pair could show a confident recommendation on the chart with nothing to contradict
    // it. These assert the structural fact instead.
    await t('VISIBILITY-2 the suppression indicator is reachable from the SCANNER, not only Diagnostics',async function(){
      const raw=g.rawHtml();
      const scannerStart=raw.indexOf('id="panel-scanner"');
      const diagStart=raw.indexOf('id="panel-diagnostics"');
      ok(scannerStart!==-1&&diagStart!==-1,'both panels must exist');
      // The scanner panel runs until the next panel opens; the original card sits in Diagnostics.
      const scannerBlock=raw.slice(scannerStart,diagStart>scannerStart?diagStart:raw.length);
      ok(scannerBlock.indexOf('id="marketDataCompletenessCardScanner"')!==-1,
        'a suppression container must live inside panel-scanner, where the chart is');
      ok(raw.slice(diagStart).indexOf('id="marketDataCompletenessCard"')!==-1,
        'and the Diagnostics card stays, because ADR-011 places this state there too');
      return 'reachable from the panel the operator is actually looking at';
    });
    await t('VISIBILITY-3 the indicator is rendered to BOTH containers, so neither can silently go stale',async function(){
      g.setFetchScript([g.okCandles(PARTIAL),g.okPrice()]);
      g.setActiveTf('M15'); g.resetPairData();
      await g.scanPair('EUR_USD');
      g.renderMarketDataCompletenessDiagnostics();
      ok(/not evaluated/i.test(g.scannerCardHtml()),'the scanner container must carry the suppression');
      eq(g.scannerCardHtml(),g.diagnosticsHtml(),'both containers must show the identical state');
      g.setFetchScript([g.okCandlesRaw(SCANNER_LOOKBACK,SCANNER_LOOKBACK-1),g.okPrice()]);
      g.resetPairData();
      await g.scanPair('EUR_USD');
      g.renderMarketDataCompletenessDiagnostics();
      eq(g.scannerCardHtml(),'','and both fall silent together when nothing is suppressed');
      return 'both containers, identical content, silent when healthy';
    });

    // ══ MOGO-021 item 3 — THE CHART MUST NOT DECIDE SOMETHING THE ENGINE DID NOT ═════════
    // loadChart used to run detectSignals/bestConfluence on its OWN fetch with no completeness gate
    // and render a "STRATEGY RECOMMENDS BUY" banner from the result -- so a pair the scanner had
    // suppressed showed "-" / 0% in the pair row and a confident recommendation on the chart.
    await t('CHART-1 a suppressed instrument renders an explicit NOT-EVALUATED state',async function(){
      g.renderChartEvaluationState({suppressed:true,completenessState:'PARTIAL',source:'engine',
        requestedCount:SCANNER_LOOKBACK,receivedCount:PARTIAL,timeframe:'M15'});
      const shown=g.chartStateHtml();
      ok(/NOT EVALUATED/i.test(shown),'it must say the instrument was not evaluated');
      ok(/Nothing below is a strategy verdict/i.test(shown),
        'and disclaim the panels beside it, which is the whole point');
      ok(shown.indexOf(String(SCANNER_LOOKBACK))!==-1&&shown.indexOf(String(PARTIAL))!==-1,
        'and show requested vs received');
      return 'suppression is stated on the chart itself';
    });
    await t('CHART-2 a healthy instrument still renders, and says WHOSE verdict it is',async function(){
      g.renderChartEvaluationState({suppressed:false,completenessState:'COMPLETE',source:'engine',timeframe:'H4'});
      const fromEngine=g.chartStateHtml();
      ok(!/NOT EVALUATED/i.test(fromEngine),'a healthy instrument must NOT be marked unevaluated');
      ok(/scanner/i.test(fromEngine)&&fromEngine.indexOf('H4')!==-1,
        'it must attribute the verdict to the scanner and name the timeframe');
      g.renderChartEvaluationState({suppressed:false,completenessState:'COMPLETE',source:'chart',timeframe:'H4'});
      const fromChart=g.chartStateHtml();
      ok(/has not scored/i.test(fromChart),
        'a pre-scan chart-local computation must not be presented as the engine\u2019s verdict');
      ok(fromEngine!==fromChart,'the two must be distinguishable -- only one is what auto-trading acted on');
      return 'engine verdict and chart-local computation are told apart';
    });
    // MOGO-021 §18.17 RELABELLED. This slices ~9,000 characters of loadChart's SOURCE and does
    // indexOf checks on it. It was the ONLY fixture in the repository claiming to protect the
    // §10.1 chart-versus-engine authority property, and it survives every mutation that actually
    // breaks that property -- rendering a re-computed verdict instead of the recorded one, and
    // mislabelling the source -- while it would die on a harmless reformat. loadChart() was never
    // once EXECUTED by the gate before the v1239 chart/AOI campaign. The behavioural coverage now
    // lives in CAF-B1..B6 and CAF-TF.1..7, which run the real loadChart and assert the rendered
    // values. Kept as a code-shape regression pin, retitled so it is not mistaken for coverage.
    await t('CHART-3 (STRUCTURAL, source-text only -- behaviour is covered by CAF-B/CAF-TF in v1239): loadChart still contains its completeness gate and does not score raw candles',async function(){
      const raw=g.rawHtml();
      const start=raw.indexOf('async function loadChart(');
      ok(start!==-1,'loadChart must exist');
      const body=raw.slice(start,start+9000);
      ok(body.indexOf('detectSignals(candles,')===-1&&body.indexOf('bestConfluence(candles,')===-1,
        'loadChart must not score its own raw fetch ungated -- that is the defect');
      ok(body.indexOf('marketDataCompletenessOf(candles)')!==-1,
        'it must consult the completeness contract');
      // §18.24: this matched the literal `pairData[activePair]` and broke the moment loadChart was
      // corrected to capture the pair (`pairData[chartPair]`) -- a CORRECTNESS fix, on a live defect
      // that rendered one pair's verdict on another pair's chart. That is precisely the brittleness
      // this fixture was relabelled STRUCTURAL for: it dies on a rename and survives every
      // behaviour-changing mutation. Matched on the stable part -- that the verdict is read out of
      // pairData at all -- rather than on which variable holds the key.
      ok(/pairData\[(activePair|chartPair)\]/.test(body),
        'and prefer the engine\u2019s own verdict, so the chart and the decision are the same object');
      return 'the chart reads the engine rather than forming a second opinion';
    });

    // ══ MOGO-021 item 5 — AOI FIDELITY ══════════════════════════════════════════════════
    // The purple AOI lines are the Daily/Weekly structure the TRADE path uses. The "AOI touch"
    // badge and confluence item beside them come from the DISPLAYED timeframe's swing clusters --
    // different window, different tolerance. detectSignals/scoreConfluence are PROTECTED and their
    // labels are frozen, so the qualifier is added at the display layer.
    await t('AOI-1 an AOI badge states the timeframe it was computed on',async function(){
      g.setActiveTf('M15');
      g.renderSignalBadges([{type:'aoi',label:'AOI resistance touch',dir:'sell',biasMatch:true}]);
      const m15=g.signalsRowHtml();
      ok(m15.indexOf('AOI resistance touch')!==-1,'the frozen label itself is unchanged');
      ok(m15.indexOf('(M15)')!==-1,'and the displayed timeframe is stated beside it');
      g.setActiveTf('H4');
      g.renderSignalBadges([{type:'aoi',label:'AOI resistance touch',dir:'sell',biasMatch:true}]);
      ok(g.signalsRowHtml().indexOf('(H4)')!==-1,'the qualifier tracks the timeframe, it is not hard-coded');
      return 'AOI badges can no longer be read as the D/W lines they sit under';
    });
    await t('AOI-2 a NON-AOI badge is left exactly as the frozen engine produced it',async function(){
      g.setActiveTf('M15');
      g.renderSignalBadges([{type:'engulf',label:'Bullish engulfing',dir:'buy',biasMatch:true}]);
      ok(g.signalsRowHtml().indexOf('(M15)')===-1,
        'only AOI items are qualified -- this is a targeted clarification, not a blanket relabel');
      return 'non-AOI badges untouched';
    });
    await t('AOI-3 the AOI confluence item carries the same qualifier',async function(){
      g.setActiveTf('M15');
      g.renderConfluencePanel({total:65,direction:'long',
        items:[{label:'AOI zone touch',state:'hit',pts:10},{label:'Bias alignment',state:'hit',pts:25}]});
      const html=g.confItemsHtml();
      ok(/AOI zone touch[\s\S]{0,80}\(M15\)/.test(html),'the AOI item states its timeframe');
      ok(!/Bias alignment[\s\S]{0,40}\(M15\)/.test(html),'and the others are untouched');
      return 'confluence AOI item qualified, others left alone';
    });
    await t('AOI-4 the drawn AOI carries its computation time, because those lines never refresh',async function(){
      const label=g.aoiAgeLabel(Date.UTC(2026,7,14,9,7,0));
      ok(/as of 09:07Z/.test(label),'the stamp must name the instant the AOI was computed');
      eq(g.aoiAgeLabel(null),'','and be absent rather than fabricated when unknown');
      return 'AOI provenance is on the chart';
    });
    await t('AOI-5 concurrent callers share ONE AOI computation, so chart and trade path cannot diverge',async function(){
      g.resetStructuralAOICache();
      // Both D and W requests, for two concurrent callers, would be four fetches without dedup.
      g.setFetchScript([g.okCandles(100),g.okCandles(60),g.okCandles(100),g.okCandles(60)]);
      const before=g.fetchCallCount?g.fetchCallCount():null;
      const [a,b]=await Promise.all([g.getStructuralAOI('EUR_USD'),g.getStructuralAOI('EUR_USD')]);
      ok(a===b,'concurrent callers must receive the SAME object, not two races for it');
      eq(g.structuralAOICacheSize(),1,'and exactly one cache entry results');
      return 'chart and trade path consume one computation';
    });

    // ── INC-006: a check that cannot evaluate must report WHY ────────────────────────────────
    // Production collapsed three materially different failures into one bare `null`, so during a
    // total provider outage (api-fxpractice.oanda.com HTTP 520 on every endpoint) the operator's
    // suppression banner rendered "HTTP —" and read exactly like a quiet market. These fixtures
    // pin the reason surviving, AND pin the return contract that must NOT have changed to get it.
    await t('INC006-1 fetchCandles() STILL returns bare null on a transport failure',async function(){
      // The load-bearing regression guard. Returning [] would be the obvious shape and is exactly
      // wrong: [] is truthy, so every `if(!candles)` guard in the application stops firing.
      g.setFetchScript([g.RESP_520]);
      const c=await g.fetchCandles('EUR_USD','H1',SCANNER_LOOKBACK);
      eq(c,null,'the 21 existing call sites depend on null, not on an empty array');
      return 'return contract unchanged';
    });
    await t('INC006-2 a non-OK status is reported as HTTP_ERROR and keeps the real status code',async function(){
      g.setFetchScript([g.RESP_520]);
      const r=await g.fetchCandlesDiagnosed('EUR_USD','H1',SCANNER_LOOKBACK);
      eq(r.candles,null,'no candles arrived');
      eq(r.diagnostics.transportOutcome,g.MARKET_DATA_TRANSPORT.HTTP_ERROR,'the failure must be named');
      eq(r.diagnostics.httpStatus,520,'the status that names the outage must survive');
      return 'HTTP 520 preserved';
    });
    await t('INC006-3 a 200 carrying no candles field is NOT reported as a network error',async function(){
      g.setFetchScript([g.RESP_NO_CANDLES]);
      const r=await g.fetchCandlesDiagnosed('EUR_USD','H1',SCANNER_LOOKBACK);
      eq(r.candles,null,'an unreadable shape yields no candles');
      eq(r.diagnostics.transportOutcome,g.MARKET_DATA_TRANSPORT.NO_CANDLES_FIELD,'a reachable provider returning a shape MOGO cannot read is its own fact');
      eq(r.diagnostics.httpStatus,200,'and it answered 200, which must not be reported as a failure status');
      return 'shape failure distinguished from transport failure';
    });
    await t('INC006-4 a thrown fetch is reported as NETWORK_ERROR and never leaks the request',async function(){
      g.setFetchScript([g.RESP_NETWORK_ERROR]);
      const r=await g.fetchCandlesDiagnosed('EUR_USD','H1',SCANNER_LOOKBACK);
      eq(r.candles,null,'a rejected fetch yields no candles');
      eq(r.diagnostics.transportOutcome,g.MARKET_DATA_TRANSPORT.NETWORK_ERROR,'never-answered is not the same as answered-badly');
      eq(r.diagnostics.httpStatus,null,'there is no status when nothing answered -- it must not be invented');
      ok(!/Bearer|Authorization/i.test(String(r.diagnostics.errorText||'')),'the bearer token must never reach a diagnostic string');
      return 'network failure named, credential-safe';
    });
    await t('INC006-5 a healthy fetch is reported OK and completeness is untouched',async function(){
      g.setFetchScript([g.okCandles(SCANNER_LOOKBACK)]);
      const r=await g.fetchCandlesDiagnosed('EUR_USD','H1',SCANNER_LOOKBACK);
      ok(Array.isArray(r.candles),'a healthy fetch still returns the array');
      eq(r.diagnostics.transportOutcome,g.MARKET_DATA_TRANSPORT.OK,'a healthy transport must say so');
      eq(g.completenessStateOf(r.candles),'COMPLETE','and ADR-011 classification must be unaffected by this change');
      return 'healthy path unchanged';
    });
    await t('INC006-6 the operator banner NAMES a provider failure instead of implying a quiet market',async function(){
      g.resetPairData();
      g.setActiveTf('H1');
      g.setFetchScript([g.RESP_520]);          // candle fetch fails; price fetch reuses the last step
      await g.scanPair('EUR_USD');
      const d=g.pairData()['EUR_USD'];
      eq(d.evaluationSuppressed,true,'the pair must be suppressed');
      eq(d.httpStatus,520,'the status must reach pairData even though candles was null');
      eq(d.transportOutcome,g.MARKET_DATA_TRANSPORT.HTTP_ERROR,'and so must the transport outcome');
      g.renderMarketDataCompletenessDiagnostics();
      const html=g.diagnosticsHtml();
      ok(/market data could not be retrieved/.test(html),'the headline must not call a dead provider "incomplete candle history"');
      ok(/HTTP 520/.test(html),'the operator must be able to read the actual status');
      ok(/HTTP_ERROR/.test(html),'and the named transport outcome');
      ok(/not a market verdict|cannot see the market/.test(html),'it must say this is not a no-trade signal');
      ok(!/session, weekend, holiday and\s*liquidity gaps are all legitimate/.test(html),
        'the legitimate-gap reassurance must NOT be shown for a total transport failure');
      return 'provider outage is named, not narrated as a quiet market';
    });

    // ── MOGO-023: the tick count that must never become "volume" ─────────────────────────────
    await t('INC006-7 (STRUCTURAL) no code path reads OANDA candle volume',async function(){
      // OANDA's candles DO carry a `volume` field -- "the number of prices created during the
      // time-range represented by the candlestick", i.e. a count of OANDA's OWN price updates from
      // ONE broker. It is not traded volume and FX has no consolidated volume at all.
      //
      // MOGO discards it: all four candle mappers keep only t/o/h/l/c from c.mid. That is correct,
      // and it is one line away from not being correct. Wiring c.volume into a "value area" or a
      // volume-weighted level would be fabrication under MOGO's evidence rules -- and it would look
      // like a trivial enhancement to anyone who noticed the field sitting unused in the response.
      //
      // So the prohibition is ENFORCED here rather than only written in the research thesis.
      //
      // DELIBERATE USE IS STILL POSSIBLE, and must be deliberate: if a future release wants an
      // activity diagnostic, name it for what it is (oanda_tick_count, never "volume"), keep it out
      // of every structure/value/AOI computation, and update this fixture in the same commit. The
      // point is that deleting a guard is a visible act and quietly reading a field is not.
      const html=g.rawHtml();
      const hits=(html.match(/\.volume\b/g)||[]).length;
      eq(hits,0,'index.html now reads a `.volume` property somewhere. If this is OANDA\'s candle '+
        'tick count being used as volume, it is fabrication. If it is a deliberately-named activity '+
        'diagnostic, rename it and update this fixture in the same commit');
      return 'the tick count in every candle response is still discarded, in all 4 mappers';
    });


    // ── Chart audit horizon: the 29 July review that could not happen ────────────────────────
    // The operator could not navigate back to a late-July setup. Root cause: the chart loads ONE
    // fixed window and has no back-history pagination, and at 500 M15 candles that window spans
    // ~7.3 calendar days. M15 is the ENTRY timeframe, so the timeframe an entry must be reviewed
    // on had the shallowest history of all.
    const HORIZON_TOLERANCE=0.98;   // ceil() rounding only; not slack for a short window

    await t('HIST-1 every intraday timeframe reaches the declared audit horizon',async function(){
      const target=g.CHART_AUDIT_HORIZON_DAYS;
      ['M15','H1','H4'].forEach(function(tf){
        const days=g.chartHorizonDaysForCandles(tf,g.getChartCandleCount(tf));
        ok(days>=target*HORIZON_TOLERANCE,
          tf+' spans only '+days.toFixed(1)+' days, short of the '+target+'-day horizon');
      });
      return ['M15','H1','H4'].map(function(tf){
        return tf+' '+g.chartHorizonDaysForCandles(tf,g.getChartCandleCount(tf)).toFixed(1)+'d';
      }).join(', ');
    });

    await t('HIST-2 the change is STRICTLY NON-REDUCING -- no timeframe lost history',async function(){
      // The floor that makes this repair safe to ship without re-verifying every timeframe.
      Object.keys(g.CHART_DISPLAY_CANDLE_COUNTS_LEGACY).forEach(function(tf){
        ok(g.getChartCandleCount(tf)>=g.CHART_DISPLAY_CANDLE_COUNTS_LEGACY[tf],
          tf+' now requests FEWER candles than before: '+g.getChartCandleCount(tf)+
          ' < '+g.CHART_DISPLAY_CANDLE_COUNTS_LEGACY[tf]);
      });
      return 'all timeframes >= their pre-repair counts';
    });

    await t('HIST-3 REGRESSION: 29 July is reachable from 22 August on the entry timeframe',async function(){
      // The incident itself, as a dated fixture. 23 calendar days back on M15.
      const daysBack=(Date.UTC(2026,7,22)-Date.UTC(2026,6,29))/86400000;
      const m15=g.chartHorizonDaysForCandles('M15',g.getChartCandleCount('M15'));
      ok(m15>=daysBack,'M15 reaches only '+m15.toFixed(1)+' days, but 29 July was '+
        daysBack+' days back -- the review would fail again');
      return 'M15 spans '+m15.toFixed(1)+'d vs the '+daysBack+'d needed';
    });

    await t('HIST-4 no request exceeds OANDA’s single-request ceiling',async function(){
      // Beyond this OANDA truncates silently and the horizon would be a claim, not a fact.
      Object.keys(g.CHART_DISPLAY_CANDLE_COUNTS_LEGACY).forEach(function(tf){
        ok(g.getChartCandleCount(tf)<=g.CHART_MAX_SINGLE_REQUEST_CANDLES,
          tf+' requests '+g.getChartCandleCount(tf)+', above the '+
          g.CHART_MAX_SINGLE_REQUEST_CANDLES+' cap -- it would be silently truncated');
      });
      return 'all counts within the single-request cap';
    });

    await t('HIST-5 the horizon helpers are exact inverses',async function(){
      const n=g.chartCandlesForHorizon('M15',45);
      const d=g.chartHorizonDaysForCandles('M15',n);
      ok(Math.abs(d-45)<0.01,'round-trip drifted: 45d -> '+n+' candles -> '+d+'d');
      eq(g.chartCandlesForHorizon('D',45),null,'D is not intraday and must not be derived');
      eq(g.chartHorizonDaysForCandles('M15',0),null,'zero candles has no horizon, not a zero one');
      return 'derivation is invertible and refuses non-intraday timeframes';
    });

    await t('HIST-6 the chart REPORTS the horizon it actually achieved, and flags a short one',async function(){
      // Measured from the candles that arrived, never from the count requested -- a window that
      // came back short is exactly what made the July failure look like an empty market.
      const full=g.chartHistoryHorizonHtml({timeframe:'M15',historyCandleCount:g.getChartCandleCount('M15')});
      ok(/History shown/.test(full),'the achieved horizon must be stated');
      ok(/NOT evidence there was none/.test(full),'it must say an absent setup beyond it proves nothing');
      ok(!/SHORT of/.test(full),'a full window must not be flagged short');
      const short=g.chartHistoryHorizonHtml({timeframe:'M15',historyCandleCount:200});
      ok(/SHORT of/.test(short),'a 200-candle window is ~2.9 days and MUST be flagged');
      eq(g.chartHistoryHorizonHtml({timeframe:'D',historyCandleCount:365}),'',
        'non-intraday timeframes are not qualified');
      return 'achieved horizon reported; short window flagged';
    });

    await t('HIST-7 widening the CHART granted no strategy any extra authority',async function(){
      // The load-bearing isolation check. Every evaluation fetch is independent of the chart's
      // window; if this ever fails, a display change has reached a trading decision.
      const src=g.rawHtml();
      ok(/fetchCandlesDiagnosed\(pair,sweepTf,220\)/.test(src),
        'scanPair no longer requests exactly 220 -- ADR-011’s evaluation window moved');
      ok(/getStructuralAOI/.test(src),'the structural AOI fetch must still exist independently');
      return 'scanPair still requests its own 220; chart window is display-only';
    });


    // ── Integrity: what the count-based contract never inspected ─────────────────────────────
    // Every fixture here sends a FULL-LENGTH response. ADR-011 classifies all of them COMPLETE
    // on count alone, which is exactly why counting is not inspecting.
    const N=SCANNER_LOOKBACK;

    await t('INTEG-1 an impossible bar (high < low) is UNAVAILABLE, not COMPLETE',async function(){
      g.setFetchScript([g.okCandlesMutated(N,function(cs){
        cs[10].mid.h='1.00000'; cs[10].mid.l='1.90000';           // inverted bar
      })]);
      const c=await g.fetchCandles('EUR_USD','H1',N);
      eq(g.completenessStateOf(c),'UNAVAILABLE','a full-length response with an impossible bar was scored');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.INVALID_OHLC,'the reason must be named');
      return 'inverted bar -> UNAVAILABLE';
    });

    await t('INTEG-2 a non-finite price is UNAVAILABLE (NaN would reach stop/target arithmetic)',async function(){
      g.setFetchScript([g.okCandlesMutated(N,function(cs){ cs[5].mid.c=null; })]);
      const c=await g.fetchCandles('EUR_USD','H1',N);
      eq(g.completenessStateOf(c),'UNAVAILABLE','parseFloat(null) is NaN and it was scored');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.INVALID_OHLC);
      return 'null close -> UNAVAILABLE';
    });

    await t('INTEG-3 a REVERSED series is UNAVAILABLE -- the oldest bar must not score as "now"',async function(){
      g.setFetchScript([g.okCandlesMutated(N,function(cs){ cs.reverse(); })]);
      const c=await g.fetchCandles('EUR_USD','H1',N);
      eq(g.completenessStateOf(c),'UNAVAILABLE','a reversed page was scored at full confidence');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.NON_MONOTONIC_TIME);
      return 'reversed series -> UNAVAILABLE';
    });

    await t('INTEG-4 DUPLICATES cannot manufacture a COMPLETE verdict on a short window',async function(){
      // The mechanism: repeats inflate rawCount, and rawCount is the exact quantity
      // marketDataClassify compares against requestedCount.
      g.setFetchScript([g.okCandlesMutated(N,function(cs){
        for(let i=0;i<40;i++) cs[i]=JSON.parse(JSON.stringify(cs[0]));   // 40 copies of one bar
      })]);
      const c=await g.fetchCandles('EUR_USD','H1',N);
      eq(g.completenessStateOf(c),'UNAVAILABLE','duplicates padded a short window into COMPLETE');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.NON_MONOTONIC_TIME,
        'equal timestamps are not strictly ascending');
      return 'padded duplicates -> UNAVAILABLE';
    });

    await t('INTEG-5 a response for the WRONG INSTRUMENT is refused',async function(){
      g.setFetchScript([g.okBody(N,{instrument:'GBP_JPY',granularity:'H1'})]);
      const c=await g.fetchCandles('EUR_USD','H1',N);
      eq(g.completenessStateOf(c),'UNAVAILABLE',
        'a full series for another pair was scored under the requested pair’s name');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.IDENTITY_MISMATCH);
      return 'GBP_JPY body for EUR_USD request -> UNAVAILABLE';
    });

    await t('INTEG-6 a response for the WRONG GRANULARITY is refused',async function(){
      g.setFetchScript([g.okBody(N,{instrument:'EUR_USD',granularity:'M15'})]);
      const c=await g.fetchCandles('EUR_USD','H1',N);
      eq(g.completenessStateOf(c),'UNAVAILABLE','M15 data was scored as H1');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.IDENTITY_MISMATCH);
      return 'M15 body for H1 request -> UNAVAILABLE';
    });

    await t('INTEG-7 a MATCHING identity passes and is recorded as verified',async function(){
      g.setFetchScript([g.okBody(N,{instrument:'EUR_USD',granularity:'H1'})]);
      const c=await g.fetchCandles('EUR_USD','H1',N);
      eq(g.completenessStateOf(c),'COMPLETE','a correct, healthy response must still evaluate');
      eq(c.identityVerified,true,'a verified identity must be recorded as verified');
      return 'matching identity -> COMPLETE, identityVerified true';
    });

    await t('INTEG-8 ABSENT identity is NOT treated as agreement, and does NOT suppress',async function(){
      // Fail-closed on mismatch; honest on absence. Suppressing on a missing field would take
      // the platform down if the provider stopped sending it -- and claiming verification would
      // be the "no exception thrown means healthy" error this milestone exists to end.
      g.setFetchScript([g.okCandles(N)]);                     // body carries no identity fields
      const c=await g.fetchCandles('EUR_USD','H1',N);
      eq(g.completenessStateOf(c),'COMPLETE','absence of a field must not suppress a good response');
      eq(c.identityVerified,false,'"not checked" must never be recorded as "checked and matched"');
      return 'absent identity -> COMPLETE with identityVerified false';
    });

    await t('INTEG-9 a healthy series is untouched -- the guards are not a blanket refusal',async function(){
      // Positive control. Without it every assertion above passes on a check that refuses
      // everything, which is the classic way an integrity gate becomes an outage.
      g.setFetchScript([g.okCandles(N)]);
      const c=await g.fetchCandles('EUR_USD','H1',N);
      eq(g.completenessStateOf(c),'COMPLETE');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.OK);
      eq(g.marketDataCandleIntegrity(c),g.MARKET_DATA_INTEGRITY.OK,'the pure checker agrees');
      return 'healthy series still COMPLETE';
    });

    await t('INTEG-10 a suppressed-by-integrity response reaches the evaluators as NO DATA',async function(){
      // End to end through the real scanPair: the whole point is that the gate already handles it.
      g.resetPairData(); g.setActiveTf('H1');
      g.setFetchScript([g.okCandlesMutated(N,function(cs){ cs[3].mid.h='0.00001'; }),g.okPrice()]);
      await g.scanPair('EUR_USD');
      const pd=g.pairData()['EUR_USD'];
      eq(pd.completenessState,'UNAVAILABLE');
      eq(pd.evaluationSuppressed,true,'an impossible bar must suppress evaluation');
      eq(pd.conf.total,0,'and must not produce a confluence score');
      return 'impossible bar -> suppressed end to end';
    });


    // ── The pair LIST, which is what the operator actually reads ─────────────────────────────
    // During INC-006 all 35 rows showed "— / —", byte-identical to a quiet market, because
    // renderPairList read only price and confluence. The banner told the truth; the list did not.
    await t('ROW-1 a suppressed pair is NOT EVALUATED in the row, not a blank score',async function(){
      const st=g.pairEvaluationDisplayState('EUR_USD',
        {completenessState:'UNAVAILABLE',evaluationSuppressed:true,
         transportOutcome:'HTTP_ERROR',httpStatus:520,requestedCount:220,receivedCount:0});
      eq(st.notEvaluated,true,'a suppressed pair must not read as evaluated');
      eq(st.code,'NOT_EVALUATED');
      ok(/HTTP_ERROR/.test(st.title)&&/520/.test(st.title),'the row must carry the real reason');
      ok(/NOT a statement that there is no setup/.test(st.title),
        'it must say this is a data failure, not a market verdict');
      return 'suppressed -> NOT_EVALUATED with transport reason';
    });

    await t('ROW-2 an evaluated pair with zero confluence is NOT flagged',async function(){
      // The control that stops this becoming a permanent amber badge. A quiet market is a
      // legitimate result and must still read as one.
      const st=g.pairEvaluationDisplayState('EUR_USD',
        {completenessState:'COMPLETE',evaluationSuppressed:false,conf:{total:0,direction:'—'}});
      eq(st.notEvaluated,false,'a genuine no-setup must not be flagged as unevaluated');
      eq(st.code,'EVALUATED');
      return 'evaluated, zero confluence -> EVALUATED';
    });

    await t('ROW-3 a pair never reached this session is distinguishable from both',async function(){
      const st=g.pairEvaluationDisplayState('USD_TRY',{});
      eq(st.notEvaluated,true,'an unscanned pair must not read as evaluated');
      eq(st.code,'NOT_SCANNED','and must be told apart from a suppressed one');
      ok(/not a market verdict/i.test(st.title));
      return 'never scanned -> NOT_SCANNED';
    });

    await t('ROW-4 a suppressed pair showing a LIVE PRICE is still flagged',async function(){
      // The specific trap: fetchPrice() is an independent call that succeeds while the candle
      // fetch fails, so a suppressed pair shows a live price beside a blank score -- which reads
      // as "evaluated, quiet" more strongly than an empty row would.
      const st=g.pairEvaluationDisplayState('EUR_USD',
        {completenessState:'UNAVAILABLE',evaluationSuppressed:true,price:1.0855,
         requestedCount:220,receivedCount:0});
      eq(st.notEvaluated,true,'a live price must not launder a suppressed evaluation');
      ok(/incomplete candle history/.test(st.title),'and the reason must still be named');
      return 'live price + suppressed -> still NOT_EVALUATED';
    });


    await t('INTEG-11 provider NORMALIZATION of the identity echo is not an outage',async function(){
      // Adversarial review found this: OANDA does not guarantee the echo is byte-identical to the
      // request -- published examples show `DE30_EUR` answered with "instrument":"DE30/EUR". A
      // strict !== here would flip every instrument to UNAVAILABLE in one sweep, which is the
      // INC-006 signature this whole repair exists to prevent.
      const forms=[{instrument:'eur_usd',granularity:'h1'},
                   {instrument:'EUR/USD',granularity:'H1'},
                   {instrument:' EUR_USD ',granularity:'H1'}];
      for(const f of forms){
        g.setFetchScript([g.okBody(SCANNER_LOOKBACK,f)]);
        const c=await g.fetchCandles('EUR_USD','H1',SCANNER_LOOKBACK);
        eq(g.completenessStateOf(c),'COMPLETE',
          'normalized echo '+JSON.stringify(f)+' was treated as a mismatch -- that is an outage');
      }
      return 'case, separator and whitespace variants all accepted';
    });

    await t('INTEG-12 tolerance did NOT weaken genuine mismatch detection',async function(){
      // The control for INTEG-11. Normalisation must not make a different pair look equal.
      g.setFetchScript([g.okBody(SCANNER_LOOKBACK,{instrument:'GBP/JPY',granularity:'H1'})]);
      const c=await g.fetchCandles('EUR_USD','H1',SCANNER_LOOKBACK);
      eq(g.completenessStateOf(c),'UNAVAILABLE','a genuinely different pair must still be refused');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.IDENTITY_MISMATCH);
      eq(g.marketDataIdentityOutcome({instrument:'EUR_GBP'},'EUR_USD','H1'),'MISMATCH');
      return 'GBP/JPY still refused for an EUR_USD request';
    });


    await t('INTEG-13 duplicates on INCOMPLETE bars cannot inflate rawCount either',async function(){
      // Adversarial review's finding: the checker saw only the completeness-filtered array while
      // marketDataClassify compares the RAW count. 208 duplicate incomplete bars + 12 real ones
      // scored COMPLETE against a 220 lookback -- a 12-candle window presented as a full one.
      g.setFetchScript([function(){
        const real=candleArrayRef(12);
        const dupe=[];
        for(let i=0;i<208;i++) dupe.push(JSON.parse(JSON.stringify({...real[0],complete:false})));
        return Promise.resolve({ok:true,status:200,
          json:function(){return Promise.resolve({candles:real.concat(dupe)});}});
      }]);
      const c=await g.fetchCandles('EUR_USD','H1',SCANNER_LOOKBACK);
      eq(g.completenessStateOf(c),'UNAVAILABLE',
        'duplicate incomplete bars padded a 12-candle window into COMPLETE');
      return 'incomplete-bar duplicates -> UNAVAILABLE';
    });


    // ══ R1 FAULT INJECTION: the PAGINATED path ══════════════════════════════════════════════
    // fetchCandlesRange feeds ALEX-G replay, the backtester and the optimizer. Until R1 it
    // validated none of what the forward path validates, so replay could accept data that
    // forward evaluation would refuse -- fatal for a system whose comparison method assumes the
    // two are held to one standard. Every fixture below is a FULL-LENGTH accumulation: the point
    // is that the count-based classifier called each of them COMPLETE.
    const RANGE_N=60;   // > MARKET_DATA_MIN_USABLE_CANDLES, small enough to page in one request

    function pageOf(n,startMin,extra){
      const cs=[];
      for(let i=0;i<n;i++){
        const b=1.1000+i*0.0004;
        cs.push({time:new Date(Date.UTC(2026,0,1,0,startMin+i)).toISOString(),complete:true,
          mid:{o:b.toFixed(5),h:(b+0.0012).toFixed(5),l:(b-0.0003).toFixed(5),c:(b+0.0009).toFixed(5)}});
      }
      const body={candles:cs}; Object.assign(body,extra||{});
      return function(){ return Promise.resolve(makeResponse(true,200,body)); };
    }

    await t('RANGE-1 healthy pagination still COMPLETE (positive control)',async function(){
      // Without this, every fixture below passes on a check that refuses everything.
      g.setFetchScript([pageOf(RANGE_N,0)]);
      const c=await g.fetchCandlesRange('EUR_USD','H1',RANGE_N);
      eq(g.completenessStateOf(c),'COMPLETE','a healthy paginated accumulation must still evaluate');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.OK);
      return 'healthy '+c.length+' candles -> COMPLETE';
    });

    await t('RANGE-2 WRONG INSTRUMENT on a page is refused',async function(){
      g.setFetchScript([pageOf(RANGE_N,0,{instrument:'GBP_JPY',granularity:'H1'})]);
      const c=await g.fetchCandlesRange('EUR_USD','H1',RANGE_N);
      eq(g.completenessStateOf(c),'UNAVAILABLE','another pair’s page was accepted into a replay dataset');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.IDENTITY_MISMATCH);
      eq(c.paginationTerminationReason,'IDENTITY_MISMATCH');
      return 'wrong instrument -> UNAVAILABLE';
    });

    await t('RANGE-3 WRONG GRANULARITY on a page is refused',async function(){
      g.setFetchScript([pageOf(RANGE_N,0,{instrument:'EUR_USD',granularity:'M15'})]);
      const c=await g.fetchCandlesRange('EUR_USD','H1',RANGE_N);
      eq(g.completenessStateOf(c),'UNAVAILABLE','M15 data was accepted as H1');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.IDENTITY_MISMATCH);
      return 'wrong granularity -> UNAVAILABLE';
    });

    await t('RANGE-4 identity mismatch arriving on page N (not page 1) is still caught',async function(){
      // The realistic shape: the accumulator looks healthy until the wrong instrument is spliced
      // in. A page-1-only check would pass this.
      g.setFetchScript([pageOf(40,60,{instrument:'EUR_USD',granularity:'H1'}),
                        pageOf(40,0,{instrument:'GBP_JPY',granularity:'H1'})]);
      const c=await g.fetchCandlesRange('EUR_USD','H1',80);
      eq(g.completenessStateOf(c),'UNAVAILABLE','a mid-accumulation instrument switch was accepted');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.IDENTITY_MISMATCH);
      return 'page-2 instrument switch -> UNAVAILABLE';
    });

    await t('RANGE-5 a REVERSED page is refused',async function(){
      g.setFetchScript([function(){
        const cs=[]; for(let i=0;i<RANGE_N;i++){ const b=1.1+i*0.0004;
          cs.push({time:new Date(Date.UTC(2026,0,1,0,i)).toISOString(),complete:true,
            mid:{o:b.toFixed(5),h:(b+0.0012).toFixed(5),l:(b-0.0003).toFixed(5),c:(b+0.0009).toFixed(5)}}); }
        cs.reverse();
        return Promise.resolve(makeResponse(true,200,{candles:cs}));
      }]);
      const c=await g.fetchCandlesRange('EUR_USD','H1',RANGE_N);
      eq(g.completenessStateOf(c),'UNAVAILABLE','a reversed page would score the oldest bar as "now"');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.NON_MONOTONIC_TIME);
      return 'reversed page -> UNAVAILABLE';
    });

    await t('RANGE-6 a MALFORMED candle in a page is refused',async function(){
      g.setFetchScript([function(){
        const cs=[]; for(let i=0;i<RANGE_N;i++){ const b=1.1+i*0.0004;
          cs.push({time:new Date(Date.UTC(2026,0,1,0,i)).toISOString(),complete:true,
            mid:{o:b.toFixed(5),h:(b+0.0012).toFixed(5),l:(b-0.0003).toFixed(5),c:(b+0.0009).toFixed(5)}}); }
        cs[7].mid.h='1.00000'; cs[7].mid.l='1.90000';        // inverted bar
        return Promise.resolve(makeResponse(true,200,{candles:cs}));
      }]);
      const c=await g.fetchCandlesRange('EUR_USD','H1',RANGE_N);
      eq(g.completenessStateOf(c),'UNAVAILABLE','an impossible bar entered a replay dataset');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.INVALID_OHLC);
      return 'inverted bar -> UNAVAILABLE';
    });

    await t('RANGE-7 a DUPLICATE BOUNDARY candle across pages is caught by the COMBINED check',async function(){
      // The seam defect. Each page is internally perfect and every per-page check passes; only
      // the joined series shows the repeat. This is precisely what per-page validation cannot do.
      g.setFetchScript([pageOf(40,60),pageOf(41,20)]);   // page 2 ends where page 1 begins
      const c=await g.fetchCandlesRange('EUR_USD','H1',81);
      eq(g.completenessStateOf(c),'UNAVAILABLE','a duplicated boundary candle survived into the series');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.NON_MONOTONIC_TIME);
      eq(c.paginationTerminationReason,'COMBINED_INTEGRITY','the seam, not a page, must be named');
      return 'duplicate page boundary -> UNAVAILABLE via combined check';
    });

    await t('RANGE-8 OVERLAPPING pages are caught by the COMBINED check',async function(){
      g.setFetchScript([pageOf(40,60),pageOf(40,40)]);   // page 2 overlaps page 1 by 20 bars
      const c=await g.fetchCandlesRange('EUR_USD','H1',80);
      eq(g.completenessStateOf(c),'UNAVAILABLE','overlapping windows were joined into one series');
      return 'overlapping pages -> UNAVAILABLE';
    });

    await t('RANGE-9 a TRUNCATED accumulation is PARTIAL, not COMPLETE',async function(){
      // Not an integrity failure -- a short-but-valid window. It must stay distinguishable from
      // corruption, or the new checks would have collapsed two different facts into one.
      g.setFetchScript([pageOf(30,0),g.RESP_429]);
      const c=await g.fetchCandlesRange('EUR_USD','H1',200);
      eq(g.completenessStateOf(c),'PARTIAL','a short but VALID accumulation must not read as corrupt');
      eq(c.integrityOutcome,g.MARKET_DATA_INTEGRITY.OK,'integrity is fine; only the count is short');
      return 'truncated -> PARTIAL with integrity OK';
    });

    await t('RANGE-10 replay and forward now REFUSE the same body',async function(){
      // The equivalence R1 exists to establish: one standard, both paths.
      const bad={instrument:'GBP_JPY',granularity:'H1'};
      g.setFetchScript([pageOf(RANGE_N,0,bad)]);
      const viaRange=await g.fetchCandlesRange('EUR_USD','H1',RANGE_N);
      g.setFetchScript([g.okBody(SCANNER_LOOKBACK,bad)]);
      const viaForward=await g.fetchCandles('EUR_USD','H1',SCANNER_LOOKBACK);
      eq(g.completenessStateOf(viaRange),'UNAVAILABLE');
      eq(g.completenessStateOf(viaForward),'UNAVAILABLE');
      return 'forward and paginated refuse the same wrong-instrument body';
    });


    // ══ R1 §5: required vs available history ════════════════════════════════════════════════
    // The binding constraint is the DECLARED WINDOW, not any candles.length guard -- every guard
    // in the file sits BELOW the window its own function then addresses, which is exactly why a
    // short window is silent. computeAOI tolerates a shorter supply deliberately (its own comment
    // says so); what was missing is the REPORT.
    await t('HIST-8 a full window is SUFFICIENT',async function(){
      eq(g.historySufficiency(100,100),g.HISTORY_SUFFICIENCY.SUFFICIENT);
      eq(g.historySufficiency(220,100),g.HISTORY_SUFFICIENCY.SUFFICIENT,'surplus is still sufficient');
      return 'full and surplus windows both SUFFICIENT';
    });

    await t('HIST-9 a SHORT window is REDUCED_WINDOW, not silently sufficient',async function(){
      // The live shape: evaluateLiveTrigger fetches M15/60, ~59 usable after the complete filter,
      // against findAOIs' declared 100.
      const r=g.historySufficiencyReport(59,100);
      eq(r.state,g.HISTORY_SUFFICIENCY.REDUCED_WINDOW);
      eq(r.shortfall,41,'the shortfall must be stated, not left to be inferred');
      ok(/weaker evidence/.test(r.qualifies),
        'a reduced window must say an absent AOI is weaker evidence');
      return '59 of 100 -> REDUCED_WINDOW, shortfall 41';
    });

    await t('HIST-10 below the floor is INSUFFICIENT and explicitly NOT "no AOI"',async function(){
      // The R1 rule: insufficient history must never present as a market verdict.
      const r=g.historySufficiencyReport(12,100);
      eq(r.state,g.HISTORY_SUFFICIENCY.INSUFFICIENT);
      ok(/NOT evidence that no AOI exists/.test(r.qualifies),
        'insufficient history must never read as "no AOI exists"');
      return '12 of 100 -> INSUFFICIENT with the disclaimer';
    });

    await t('HIST-11 an unknown supply is UNKNOWN, never assumed sufficient',async function(){
      eq(g.historySufficiency(null,100),g.HISTORY_SUFFICIENCY.UNKNOWN);
      eq(g.historySufficiency(undefined,100),g.HISTORY_SUFFICIENCY.UNKNOWN);
      return 'null/undefined supply -> UNKNOWN';
    });

    await t('HIST-12 the floor matches what computeAOI actually enforces',async function(){
      // If computeAOI's floor ever moves, this classifier would misreport the boundary. Pinned
      // against the real function rather than restating the constant.
      eq(g.AOI_MIN_USABLE_CANDLES,20);
      const mk=function(n){ const a=[]; for(let i=0;i<n;i++){ const b=1.1+i*0.0004;
        a.push({t:new Date(Date.UTC(2026,0,1,0,i)),o:b,h:b+0.0012,l:b-0.0003,c:b+0.0009}); } return a; };
      const below=g.findAOIs(mk(19)), at=g.findAOIs(mk(20));
      eq(below.support,null,'below the floor computeAOI must return a null AOI');
      eq(below.band,0);
      ok(at!==null&&typeof at==='object','at the floor it must attempt a determination');
      return 'floor 20 confirmed against computeAOI itself';
    });

    await t('HIST-13 REDUCED_WINDOW is distinguishable from INSUFFICIENT',async function(){
      // The distinction R1 exists to protect: one produced a real determination on less data,
      // the other produced no determination at all. Collapsing them loses the difference between
      // weak evidence and no evidence.
      ok(g.historySufficiency(59,100)!==g.historySufficiency(12,100),
        'a reduced window and no determination must not share a state');
      return 'the two states are distinct';
    });


    // ══ R1 §29: silent-failure findings ═════════════════════════════════════════════════════

    await t('LEAK-1 disconnect() clears the ALEX exit-monitor timer',async function(){
      // It is the timer that monitors and CLOSES open ALEX paper positions.
      // stopAlexGLivePollingIfDone() cannot retire it: its predicate is
      // `alexGAutoTrading.enabled || openPositions.length > 0`, and disconnect changes neither --
      // so it survived, firing every 60s against credentials cleared on the next line, while the
      // poll ledger kept recording outcome:'OK'.
      const src=g.disconnectSrc;
      ok(/clearInterval\(alexGLiveInterval\)/.test(src),
        'disconnect must clear alexGLiveInterval, or the exit monitor runs credential-less');
      ok(/alexGLiveInterval=null/.test(src),'and null the handle so initAll can restart it');
      ok(/clearInterval\(autoScanTimer\)/.test(src),'the sibling timer must still be cleared too');
      return 'exit-monitor timer retired on disconnect';
    });

    // ── DOCUMENTED DEFECTS, pinned as CURRENT behaviour (BEHAVIOUR-* convention) ─────────────
    // Both live in PROTECTED functions, so repairing them is a governed protected-function change
    // and an operator decision -- not something to do silently. These fixtures pin what production
    // does TODAY so that a future fix FLIPS them, making the change impossible to land unnoticed.

    await t('DEFECT-1 (DOCUMENTED) pipValuePerLot substitutes the WRONG conversion rate',async function(){
      // `(pairData['USD_'+quote].price) || (pairData[pair].price)` -- the second operand is the
      // rate of the pair being SIZED, not USD/quote. Correct only when base==='USD', where the
      // branch is redundant. The `||` fires BEFORE the `return null` guard written to stop exactly
      // this fabrication, so the guard is unreachable whenever the pair itself has a price.
      g.setPairPrice('GBP_CHF',1.11);            // USD_CHF deliberately absent
      const withFallback=g.pipValuePerLot('GBP_CHF');
      g.setPairPrice('USD_CHF',0.88);
      const correct=g.pipValuePerLot('GBP_CHF');
      ok(withFallback!==null,'DOCUMENTED: the fallback fires instead of returning null');
      ok(Math.abs(withFallback-correct)/correct>0.2,
        'DOCUMENTED: the substituted rate differs from the correct one by >20% -- lot size and '+
        'realized P&L are both wrong by that factor. If this assertion ever FAILS, the defect was '+
        'fixed and this fixture must be replaced by the correct-behaviour assertion.');
      return 'substituted '+withFallback.toFixed(4)+' vs correct '+correct.toFixed(4);
    });

    await t('DEFECT-2 (DOCUMENTED) six pairs have NO USD conversion pair at all',async function(){
      // Structural, not transient: ALL_PAIRS contains no USD_GBP / USD_AUD / USD_NZD, so for
      // these the fallback is the ONLY branch that ever executes.
      const missing=['USD_GBP','USD_AUD','USD_NZD'].filter(function(p){ return g.ALL_PAIRS.indexOf(p)===-1; });
      eq(missing.length,3,'DOCUMENTED: none of the three inverse-USD pairs is configured');
      const affected=g.ALL_PAIRS.filter(function(p){
        const q=p.split('_')[1];
        return q!=='USD'&&g.ALL_PAIRS.indexOf('USD_'+q)===-1;
      });
      ok(affected.length>=6,'DOCUMENTED: '+affected.length+' pairs can never resolve a real '+
        'conversion rate: '+affected.join(','));
      return affected.length+' pairs permanently on the fallback: '+affected.join(',');
    });

    await t('DEFECT-3 (DOCUMENTED) the pipD magnitude heuristic misreads five instruments',async function(){
      // `pipD = last.c < 10 ? 0.0001 : 0.01` stands in for pipSize(pair) in three places. It is a
      // proxy for "is this JPY" and fails for every non-JPY instrument trading above 10.
      const highPriced=['USD_MXN','USD_ZAR','USD_TRY','USD_SEK','USD_NOK']
        .filter(function(p){ return g.ALL_PAIRS.indexOf(p)!==-1; });
      ok(highPriced.length>=5,'DOCUMENTED: '+highPriced.length+' configured non-JPY pairs trade above 10');
      highPriced.forEach(function(p){
        eq(g.pipSize(p),0.0001,'canonical pipSize is correct for '+p+
          ' -- the heuristic would return 0.01, a 100x error');
      });
      return highPriced.join(',')+' would each get a 100x pip size from the heuristic';
    });

    return out;
  })();
}
