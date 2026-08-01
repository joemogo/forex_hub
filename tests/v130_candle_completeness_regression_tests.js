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
      // Directly observable facts only -- never an inferred "missingCandles".
      ok(c&&typeof c==='object'&&!Array.isArray(c)||g.hasCompletenessState(c),
        'pagination terminated on HTTP 429 but the caller received a bare array with no '+
        'paginationTerminationReason, no httpStatus and no pagesRequested/pagesReceived -- the '+
        'HTTP 429 is completely invisible to every downstream consumer');
      return 'incomplete-data state exposed';
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
      const src=String(g.scanPair);
      ok(/marketDataCompletenessOf\(candles\)/.test(src),
        'scanPair must classify the producer value itself, not a derived array');
      ok(!/marketDataCompletenessOf\(\s*candles\s*\.\s*(slice|map|filter|concat)/.test(src),
        'scanPair must not classify a copy');
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

    return out;
  })();
}
