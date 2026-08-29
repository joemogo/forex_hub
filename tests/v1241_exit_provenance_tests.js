// G-4 — ALEX exit provenance fails closed on UNKNOWN (MOGO-024).
//
// THE DEFECT. alexGCloseLivePosition built its closed-position record with two fabricating
// fallbacks: `m.exitDetectionSource || 'live_snapshot'` asserted HOW an exit was detected, and
// `m.exitDetectedAt || Date.now()` invented WHEN, whenever a caller supplied neither. Both
// fields are inside the evidence package's contentHash, so an invented value re-derived
// cleanly and was indistinguishable from an observed one.
//
// REACHABILITY, STATED PRECISELY. The developer forced close (generateTestAlexTrade) supplies
// exitDetectionSource:'developer_test' but NO exitDetectedAt, so ONLY the timestamp was
// actively fabricated there. All four call sites already supply a source, so the removed
// `||'live_snapshot'` fallback had no reachable caller -- it was latent defence-in-depth
// against a future caller omitting provenance, not the repair of a live fabrication.
//
// WHAT THESE FIXTURES DRIVE. The real, unmodified production alexGCloseLivePosition -- never a
// reimplementation of its normalization in a test helper. Each case opens a genuine ALEX paper
// position in the harness's isolated state, closes it through the production function, and
// reads the resulting closedPositions[0] record. That is why the `||` -> validated-ternary
// change is what these tests actually detect.
//
// WHY VALIDATION AND NOT `!= null`. Every legitimate caller supplies a NUMBER of epoch
// milliseconds (exit.candleEnd = c.t+candleDurationMs, or Date.now()) and one of exactly three
// source strings. `!= null` would accept NaN, Infinity, 0, negatives, booleans, objects and
// whitespace-only strings as provenance. The invalid-input cases below are what separate the
// two designs, and a `!= null` implementation fails them.
//
// DETERMINISM SCOPE. closedAt is intentionally runtime-generated, so whole-package byte
// identity across executions is NOT asserted -- that would be a false oracle. Determinism is
// asserted only for the normalized provenance transformation under identical inputs.
function runV1241Fixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,detail:detail||''});};

  // Close a position through the REAL production function and return its closed record.
  // exitMetaMode: 'omit' passes no fifth argument at all; otherwise the value is passed as-is.
  function closeWith(exitMetaMode,meta){
    const tradeId=g.seedOpenPosition();
    if(exitMetaMode==='omit') g.closeNoMeta(tradeId);
    else g.closeWithMeta(tradeId,meta);
    return g.lastClosed();
  }
  const INVALID_TS=[
    ['field omitted',{}],['explicit undefined',{exitDetectedAt:undefined}],
    ['null',{exitDetectedAt:null}],['empty string',{exitDetectedAt:''}],
    ['whitespace string',{exitDetectedAt:'   '}],['false',{exitDetectedAt:false}],
    ['NaN',{exitDetectedAt:NaN}],['+Infinity',{exitDetectedAt:Infinity}],
    ['-Infinity',{exitDetectedAt:-Infinity}],['zero',{exitDetectedAt:0}],
    ['negative',{exitDetectedAt:-1}],['object',{exitDetectedAt:{}}],
    ['array',{exitDetectedAt:[]}],['numeric string',{exitDetectedAt:'1787821350692'}]
  ];
  const INVALID_SRC=[
    ['field omitted',{}],['explicit undefined',{exitDetectionSource:undefined}],
    ['null',{exitDetectionSource:null}],['empty string',{exitDetectionSource:''}],
    ['whitespace only',{exitDetectionSource:'   '}],['false',{exitDetectionSource:false}],
    ['number',{exitDetectionSource:12345}],['object',{exitDetectionSource:{}}],
    ['array',{exitDetectionSource:[]}]
  ];

  // ── POSITIVE CONTROLS ────────────────────────────────────────────────────────────────────
  // Without these, every fail-closed assertion below is satisfied by a function that returns
  // null unconditionally -- which would destroy real provenance rather than protect it.
  (function(){
    const TS=1787821350692;                       // the shape Date.now() produces
    const rec=closeWith('meta',{exitTriggerLevel:1.2,exitDetectionSource:'live_snapshot',
                                exitDetectedAt:TS,ambiguous:false,ambiguousMode:null});
    assert('P1 a legitimate live_snapshot numeric exitDetectedAt is preserved EXACTLY',
      rec && rec.exitDetectedAt===TS, String(rec&&rec.exitDetectedAt));
    assert('P2 a legitimate live_snapshot exitDetectionSource is preserved EXACTLY',
      rec && rec.exitDetectionSource==='live_snapshot', String(rec&&rec.exitDetectionSource));
  })();
  (function(){
    const CE=1787821320000;                       // the shape c.t+candleDurationMs produces
    const rec=closeWith('meta',{exitTriggerLevel:1.2,exitDetectionSource:'historical_candle',
                                exitDetectedAt:CE,exitCandleStart:CE-60000,exitCandleEnd:CE,
                                ambiguous:false,ambiguousMode:null});
    assert('P3 a historical candle-boundary exitDetectedAt is preserved EXACTLY',
      rec && rec.exitDetectedAt===CE, String(rec&&rec.exitDetectedAt));
    assert('P4 the historical exitDetectionSource is preserved EXACTLY',
      rec && rec.exitDetectionSource==='historical_candle', String(rec&&rec.exitDetectionSource));
    assert('P4b the sibling candle fields are unaffected by this change',
      rec && rec.exitCandleEnd===CE && rec.exitCandleStart===CE-60000,'');
  })();
  (function(){
    // The third legitimate source string, supplied explicitly.
    const rec=closeWith('meta',{exitTriggerLevel:1.2,exitDetectionSource:'developer_test',
                                exitDetectedAt:1787821350692});
    assert('P5 developer_test is preserved when the caller genuinely supplies it',
      rec && rec.exitDetectionSource==='developer_test',String(rec&&rec.exitDetectionSource));
  })();
  (function(){
    // A close must still SUCCEED with unknown provenance -- fail closed on the VALUE, never by
    // refusing to record the trade. This is the guard against over-correcting into Option B.
    const before=g.closedCount();
    const rec=closeWith('omit');
    assert('P6 closing still SUCCEEDS when provenance is UNKNOWN (no rejection)',
      rec && rec.status==='closed' && g.closedCount()===before+1,
      'closed='+g.closedCount()+' prev='+before);
    assert('P6b and the trade economics are untouched by unknown provenance',
      rec && typeof rec.pnl==='number' && typeof rec.exitPrice==='number' && rec.result!=null,
      JSON.stringify({pnl:rec&&rec.pnl,exit:rec&&rec.exitPrice,result:rec&&rec.result}));
  })();

  // ── FAIL-CLOSED: exitDetectedAt ──────────────────────────────────────────────────────────
  (function(){
    const t0=Date.now();
    INVALID_TS.forEach(function(c){
      const rec=closeWith('meta',c[1]);
      const v=rec?rec.exitDetectedAt:'NO RECORD';
      assert('T-'+c[0]+' -> UNKNOWN (null), never the runtime clock',
        rec && rec.exitDetectedAt===null, String(v));
      // The specific failure this defect had: the field becoming "now".
      assert('T-'+c[0]+' is not a wall-clock value',
        !(typeof v==='number' && v>=t0-5000), String(v));
    });
    // exitMeta itself absent / undefined / null -- the developer forced-close shape.
    [['exitMeta omitted','omit',undefined],['exitMeta undefined','meta',undefined],
     ['exitMeta null','meta',null]].forEach(function(c){
      const rec=closeWith(c[1],c[2]);
      assert('T-'+c[0]+' -> UNKNOWN (null)',
        rec && rec.exitDetectedAt===null, String(rec&&rec.exitDetectedAt));
    });
  })();

  // ── FAIL-CLOSED: exitDetectionSource ─────────────────────────────────────────────────────
  (function(){
    INVALID_SRC.forEach(function(c){
      const rec=closeWith('meta',c[1]);
      assert('S-'+c[0]+' -> UNKNOWN (null), never an invented label',
        rec && rec.exitDetectionSource===null, String(rec&&rec.exitDetectionSource));
      assert('S-'+c[0]+' is specifically NOT "live_snapshot"',
        !rec || rec.exitDetectionSource!=='live_snapshot', String(rec&&rec.exitDetectionSource));
    });
    [['exitMeta omitted','omit',undefined],['exitMeta null','meta',null]].forEach(function(c){
      const rec=closeWith(c[1],c[2]);
      assert('S-'+c[0]+' -> UNKNOWN (null)',
        rec && rec.exitDetectionSource===null, String(rec&&rec.exitDetectionSource));
    });
  })();

  // ── EVIDENCE PACKAGE: UNKNOWN survives into the package, and the hash covers it ───────────
  (function(){
    const unknownRec=closeWith('omit');
    const pkgU=g.buildPackage(unknownRec);
    assert('E1 UNKNOWN provenance reaches the package as JSON null, not a fabricated value',
      pkgU && pkgU.outcome && pkgU.outcome.exitDetectedAt===null
           && pkgU.outcome.exitDetectionSource===null,
      JSON.stringify(pkgU&&pkgU.outcome?{d:pkgU.outcome.exitDetectedAt,s:pkgU.outcome.exitDetectionSource}:null));

    const TS=1787821350692;
    const validRec=closeWith('meta',{exitDetectionSource:'live_snapshot',exitDetectedAt:TS});
    const pkgV=g.buildPackage(validRec);
    assert('E2 VALID provenance reaches the package unchanged',
      pkgV && pkgV.outcome && pkgV.outcome.exitDetectedAt===TS
           && pkgV.outcome.exitDetectionSource==='live_snapshot','');

    // The hash must DEPEND on these fields -- otherwise "the hash covers it" is decoration.
    const cU=g.canonicalize(pkgU), cV=g.canonicalize(pkgV);
    assert('E3 the canonicalization covers exitDetectedAt (UNKNOWN and VALID differ)',
      cU!==cV && cU.indexOf('exitDetectedAt')>-1,'');
    assert('E4 neither canonical form contains an invented source label',
      cU.indexOf('"live_snapshot"')===-1,'UNKNOWN package must not claim live_snapshot');
  })();

  // ── DETERMINISM of the normalization (NOT whole-package byte identity) ───────────────────
  (function(){
    const TS=1787821350692;
    const a=closeWith('meta',{exitDetectionSource:'historical_candle',exitDetectedAt:TS});
    const b=closeWith('meta',{exitDetectionSource:'historical_candle',exitDetectedAt:TS});
    assert('D1 identical inputs normalize identically',
      a.exitDetectedAt===b.exitDetectedAt && a.exitDetectionSource===b.exitDetectionSource,'');
    const u1=closeWith('omit'), u2=closeWith('omit');
    assert('D2 identical UNKNOWN inputs normalize identically',
      u1.exitDetectedAt===null && u2.exitDetectedAt===null
      && u1.exitDetectionSource===null && u2.exitDetectionSource===null,'');
    assert('D3 closedAt IS runtime-generated and is deliberately not asserted for identity',
      typeof a.closedAt==='string' && a.closedAt.length>0,'documents the excluded oracle');
  })();

  // ── REGRESSION CONTROLS ──────────────────────────────────────────────────────────────────
  (function(){
    const TS=1787821350692;
    const rec=closeWith('meta',{exitTriggerLevel:1.23456,exitDetectionSource:'live_snapshot',
                                exitDetectedAt:TS,ambiguous:true,ambiguousMode:'both'});
    assert('R1 exitTriggerLevel still defaults/preserves independently of this change',
      rec.exitTriggerLevel===1.23456,String(rec.exitTriggerLevel));
    assert('R2 ambiguous/ambiguousMode are unchanged by this repair',
      rec.ambiguous===true && rec.ambiguousMode==='both','');
    assert('R3 no new field was added to the closed record',
      Object.prototype.hasOwnProperty.call(rec,'exitDetectedAt')
      && !Object.prototype.hasOwnProperty.call(rec,'exitOccurredAt')
      && !Object.prototype.hasOwnProperty.call(rec,'exitProcessedAt'),
      'Option C concepts must NOT appear in this change');
  })();

  return results;
}

// ══════════════════════════════════════════════════════════════════════════════════════════
// THE ACTUAL PRODUCTION DEVELOPER PATH (added after a post-commit audit found the gap).
//
// Everything above drives alexGCloseLivePosition directly. That proves the normalization but
// NOT the call site, so it would have passed even if generateTestAlexTrade's exitMeta had
// changed shape. Constructing an "AGT|TEST|..." string by hand is not the same as producing
// one, and the audit was right to reject it. This block invokes the REAL production function.
//
// The reachable G-4 fabrication lived exactly here: this call site supplies
// exitDetectionSource:'developer_test' but NO exitDetectedAt, so before the repair
// `m.exitDetectedAt||Date.now()` stamped the record with the runtime clock. The source was
// never fabricated on this path -- all four callers already supply one -- which is why the
// removed `||'live_snapshot'` fallback was latent defence-in-depth, not an active defect.
function runV1241DeveloperPathFixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,detail:detail||''});};

  g.resetAlexAccount();
  const oPair=g.primeDevPrice();
  assert('DEV.0 precondition: pipValuePerLot resolves for the developer pair without a cross rate',
    g.pipValueFor(oPair)!=null, oPair+' -> '+g.pipValueFor(oPair));

  // Developer mode is a HARD gate on the production function -- prove it blocks first, so the
  // success below cannot be mistaken for the gate being absent.
  g.setDeveloperMode(false);
  const beforeBlocked=g.closedCount();
  g.runGenerateTestAlexTrade('buy','Win');
  assert('DEV.1 developerModeEnabled is a real gate: OFF produces no trade at all',
    g.closedCount()===beforeBlocked && g.openCount()===0,
    'closed='+g.closedCount()+' open='+g.openCount());

  g.setDeveloperMode(true);
  assert('DEV.2 developer mode is ON for the run below', g.isDeveloperMode()===true,'');

  const before=g.closedCount();
  const t0=Date.now();
  g.runGenerateTestAlexTrade('buy','Win');          // the REAL production entry point
  const t1=Date.now();
  const rec=g.lastClosed();

  assert('DEV.3 the real generateTestAlexTrade forced-close produced exactly one closed trade',
    g.closedCount()===before+1 && !!rec, 'closed='+g.closedCount());
  assert('DEV.4 the trade id was PRODUCED by production logic in the AGT|TEST| identity form',
    !!rec && typeof rec.tradeId==='string' && rec.tradeId.indexOf('AGT|TEST|')===0,
    rec?String(rec.tradeId):'no rec');
  assert('DEV.5 the production call site supplied exitDetectionSource and it is preserved EXACTLY',
    !!rec && rec.exitDetectionSource==='developer_test', rec?String(rec.exitDetectionSource):'no rec');
  assert('DEV.6 the production call site supplies NO exitDetectedAt, so it is UNKNOWN (null)',
    !!rec && rec.exitDetectedAt===null, rec?String(rec.exitDetectedAt):'no rec');
  // The precise regression G-4 removed: the field becoming the runtime clock.
  assert('DEV.7 exitDetectedAt is not the diagnostic runtime, nor near it',
    !!rec && !(typeof rec.exitDetectedAt==='number' && rec.exitDetectedAt>=t0-1000 && rec.exitDetectedAt<=t1+1000),
    'window '+t0+'..'+t1+' value '+(rec?String(rec.exitDetectedAt):'?'));
  assert('DEV.8 the developer markers the import policy reads are present on the record',
    !!rec && rec.isDeveloperTrade===true && rec.tradeSource==='TEST',
    rec?(String(rec.isDeveloperTrade)+'/'+String(rec.tradeSource)):'no rec');

  // ── The evidence package, built through the real package path ────────────────────────────
  const w=g.buildPackage(rec);
  const out=w.outcome;
  assert('DEV.9 the package carries exitDetectionSource exactly "developer_test"',
    !!out && out.exitDetectionSource==='developer_test', out?String(out.exitDetectionSource):'no outcome');
  assert('DEV.10 the package carries exitDetectedAt exactly null -- no fabricated timestamp',
    !!out && out.exitDetectedAt===null, out?String(out.exitDetectedAt):'no outcome');
  assert('DEV.11 the package remains content-hash verifiable (canonicalizes and covers the field)',
    g.canonicalize(w).indexOf('exitDetectedAt')>-1 && g.canonicalize(w).indexOf('"live_snapshot"')===-1,'');
  // is_developer_test_package (the Python import gate) reads exactly these three markers.
  assert('DEV.12 the package is classifiable as a developer-test package by the shipped predicate inputs',
    !!w.pkg && typeof w.pkg.sourceTradeId==='string' && w.pkg.sourceTradeId.indexOf('AGT|TEST|')===0,
    w.pkg?String(w.pkg.sourceTradeId).slice(0,24):'no pkg');

  // ── A losing forced close takes the other branch of the same call site ───────────────────
  const beforeL=g.closedCount();
  g.runGenerateTestAlexTrade('sell','Loss');
  const recL=g.lastClosed();
  assert('DEV.13 the Loss branch of the same call site behaves identically',
    g.closedCount()===beforeL+1 && !!recL && recL.exitDetectionSource==='developer_test'
    && recL.exitDetectedAt===null, recL?(recL.exitDetectionSource+'/'+recL.exitDetectedAt):'no rec');

  g.setDeveloperMode(false);
  return results;
}
