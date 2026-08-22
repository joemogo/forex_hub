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

    return out;
  })();
}
