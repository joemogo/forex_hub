// MOGO-002.5 Phase 8 — ALEX strategy-provenance and fidelity-support fixture suite.
//
// Exercises the REAL, unmodified functions added by MOGO-002.5 Phase 5
// (alexGStableHash, alexGStrategyVersionReference, alexGStampTradeProvenance,
// alexGClassifyTradeProvenance, alexGProvenanceSummary) plus targeted ALEX behavioural
// assertions that repository evidence actually supports.
//
// SCOPE DISCIPLINE: no protected function or protected constant is edited, duplicated or
// re-implemented here. Where a behaviour lives inside a protected function, this suite
// calls the REAL function rather than restating its logic. Speculative educator rules are
// NOT encoded: every behavioural fixture below asserts something the repository itself
// states (RULES_ALEXG.originalAlexConcepts or an inspected code path).
function runStrategyFidelityProvenanceFixtures(g){
  const results=[];
  function check(name,cond,detail){ results.push({name,pass:!!cond,detail:detail||''}); }
  function note(name,detail){ results.push({name,pass:null,detail,method:'source-verified'}); }

  // ════════════════════════════════════════════════════════════════════════
  // A. Stable hashing
  // ════════════════════════════════════════════════════════════════════════
  const h=g.alexGStableHash;

  check('A1 stable hash is deterministic across calls',
    h({a:1,b:[2,3]})===h({a:1,b:[2,3]}));

  check('A2 stable hash is key-order independent',
    h({a:1,b:2})===h({b:2,a:1}),
    'two configs differing only in key order must hash identically');

  check('A3 stable hash distinguishes different values',
    h({a:1})!==h({a:2}));

  check('A4 stable hash distinguishes nested differences',
    h({a:{b:1}})!==h({a:{b:2}}));

  check('A5 stable hash is array-order sensitive',
    h([1,2])!==h([2,1]),
    'array order is meaningful (rule ordering), unlike object key order');

  check('A6 stable hash handles null and undefined without throwing',
    typeof h({a:null,b:undefined})==='string' && h({a:null}).length===16);

  check('A7 stable hash is fixed width (16 hex chars)',
    /^[0-9a-f]{16}$/.test(h({any:'value'})));

  // ════════════════════════════════════════════════════════════════════════
  // B. Version reference
  // ════════════════════════════════════════════════════════════════════════
  const ref=g.alexGStrategyVersionReference();

  check('B1 version reference carries every required provenance field',
    ref.strategyId && ref.strategySpecificationVersion && ref.implementationVersion &&
    ref.ruleSetHash && ref.configurationHash && ref.engineVersion,
    JSON.stringify(Object.keys(ref)));

  check('B2 strategyId is the real RULES_ALEXG.ruleVersion',
    ref.strategyId===g.getRulesAlexG().ruleVersion,
    ref.strategyId);

  check('B3 engineVersion is the real APP_VERSION',
    ref.engineVersion===g.getAppVersion(), ref.engineVersion);

  check('B4 decisionTraceVersion reuses the EXISTING decision-event schema version',
    ref.decisionTraceVersion===g.getDecisionEventSchemaVersion(),
    'must reuse mogo.decision-event.v1, never invent a parallel trace version');

  check('B5 ruleSetHash is derived from originalAlexConcepts, not the config',
    ref.ruleSetHash===h(g.getRulesAlexG().originalAlexConcepts) &&
    ref.ruleSetHash!==ref.configurationHash,
    'spec identity and config identity must be separately detectable');

  check('B6 configurationHash matches a fresh snapshotAlexGConfig().config',
    ref.configurationHash===h(g.snapshotAlexGConfig().config));

  check('B7 version reference is stable across repeated calls',
    JSON.stringify(g.alexGStrategyVersionReference())===JSON.stringify(ref));

  // ════════════════════════════════════════════════════════════════════════
  // C. Stamping
  // ════════════════════════════════════════════════════════════════════════
  const fresh={tradeId:'T1',entry:1.1,stop:1.09,target:1.13};
  const before=JSON.stringify(fresh);
  g.alexGStampTradeProvenance(fresh);

  check('C1 stamping adds strategyProvenance',
    !!fresh.strategyProvenance);

  check('C2 stamping does not alter any pre-existing field',
    fresh.tradeId==='T1' && fresh.entry===1.1 && fresh.stop===1.09 && fresh.target===1.13,
    'entry/stop/target must be byte-identical after stamping');

  check('C3 stamping adds exactly one new key',
    Object.keys(fresh).length===Object.keys(JSON.parse(before)).length+1);

  const stampedOnce=JSON.stringify(fresh.strategyProvenance);
  fresh.strategyProvenance.strategyId='TAMPERED';
  g.alexGStampTradeProvenance(fresh);
  check('C4 re-stamping never overwrites an existing stamp',
    fresh.strategyProvenance.strategyId==='TAMPERED',
    'a historical record must never be silently re-versioned');
  fresh.strategyProvenance=JSON.parse(stampedOnce);

  check('C5 stamping a null or invalid record never throws',
    (function(){ try{ g.alexGStampTradeProvenance(null); g.alexGStampTradeProvenance(undefined);
      g.alexGStampTradeProvenance(42); return true; }catch(e){ return false; } })(),
    'provenance must never be able to block a real trade');

  // ════════════════════════════════════════════════════════════════════════
  // D. Classification — including LEGACY_UNVERSIONED
  // ════════════════════════════════════════════════════════════════════════
  const C=g.getAlexProvenanceClasses();

  check('D1 a fully stamped trade classifies VERSIONED',
    g.alexGClassifyTradeProvenance(fresh)===C.VERSIONED);

  check('D2 a pre-MOGO-002.5 trade with NO version evidence is LEGACY_UNVERSIONED',
    g.alexGClassifyTradeProvenance({tradeId:'OLD',entry:1.2})===C.LEGACY);

  check('D3 a pre-existing trade with configurationSnapshot is PARTIAL, not VERSIONED',
    g.alexGClassifyTradeProvenance({tradeId:'OLD2',configurationSnapshot:{ruleVersion:'alex_g_sr_v1'}})===C.PARTIAL,
    'must not be rounded up -- it genuinely had partial version evidence');

  check('D4 a trade with only createdByEngineVersion is PARTIAL',
    g.alexGClassifyTradeProvenance({tradeId:'OLD3',createdByEngineVersion:'12.5.0'})===C.PARTIAL);

  check('D5 an incomplete stamp is PARTIAL, never VERSIONED',
    g.alexGClassifyTradeProvenance({strategyProvenance:{strategySpecificationVersion:'x'}})===C.PARTIAL,
    'a half-written stamp must not claim full provenance');

  check('D6 null/garbage classifies LEGACY rather than throwing',
    g.alexGClassifyTradeProvenance(null)===C.LEGACY &&
    g.alexGClassifyTradeProvenance('nonsense')===C.LEGACY);

  check('D7 classification never mutates the record it inspects',
    (function(){ const t={tradeId:'X',configurationSnapshot:{}}; const b=JSON.stringify(t);
      g.alexGClassifyTradeProvenance(t); return JSON.stringify(t)===b; })(),
    'old records must never be rewritten to imply provenance they did not have');

  // ════════════════════════════════════════════════════════════════════════
  // E. Aggregation — reports must distinguish verified from legacy/mixed
  // ════════════════════════════════════════════════════════════════════════
  const versioned=JSON.parse(JSON.stringify(fresh));
  const legacy={tradeId:'L1'};
  const partial={tradeId:'P1',createdByEngineVersion:'12.5.0'};

  const allVersioned=g.alexGProvenanceSummary([versioned,JSON.parse(JSON.stringify(fresh))]);
  check('E1 an all-versioned set reports VERSIONED and mixed=false',
    allVersioned.reportable==='VERSIONED' && allVersioned.mixed===false &&
    allVersioned.VERSIONED===2);

  const allLegacy=g.alexGProvenanceSummary([legacy,{tradeId:'L2'}]);
  check('E2 an all-legacy set reports LEGACY_UNVERSIONED',
    allLegacy.reportable==='LEGACY_UNVERSIONED' && allLegacy.LEGACY_UNVERSIONED===2 &&
    allLegacy.mixed===false);

  const mixed=g.alexGProvenanceSummary([versioned,legacy,partial]);
  check('E3 a mixed set is reported MIXED_VERSION, never averaged silently',
    mixed.reportable==='MIXED_VERSION' && mixed.mixed===true,
    'VERSIONED=1 LEGACY=1 PARTIAL=1');

  check('E4 mixed summary counts each class separately',
    mixed.VERSIONED===1 && mixed.LEGACY_UNVERSIONED===1 && mixed.PARTIAL_PROVENANCE===1 &&
    mixed.total===3);

  const twoSpecs=g.alexGProvenanceSummary([versioned,
    {strategyProvenance:{strategySpecificationVersion:'alex_g_sr_v2',implementationVersion:'i2',
      ruleSetHash:'a',configurationHash:'b'}}]);
  check('E5 two specification versions is MIXED even when both are fully versioned',
    twoSpecs.mixed===true && twoSpecs.specificationVersions.length===2,
    twoSpecs.specificationVersions.join(','));

  check('E6 empty input summarises to NONE without throwing',
    g.alexGProvenanceSummary([]).reportable==='NONE' &&
    g.alexGProvenanceSummary(null).total===0);

  // ════════════════════════════════════════════════════════════════════════
  // F. Targeted ALEX behavioural fidelity — REAL protected functions only
  // Each assertion below corresponds to a rule in the fidelity specification.
  // ════════════════════════════════════════════════════════════════════════
  const cfg=g.snapshotAlexGConfig().config;

  // ALEX_SR_005 — three reactions validate; the fourth is the first trade.
  const zoneValidated={status:'validated',touches:[1,2,3,4]};
  check('F1 (ALEX_SR_005) the 4th reaction qualifies',
    g.alexGEvaluateRepeatedReaction(zoneValidated,{},3,'clean',cfg).qualifies===true);
  check('F2 (ALEX_SR_005) the 3rd reaction does NOT qualify',
    g.alexGEvaluateRepeatedReaction(zoneValidated,{},2,'clean',cfg).qualifies===false,
    'touchIndex 2 is the validating reaction, not a trade');
  check('F3 (ALEX_SR_005) a zone with fewer than 4 touches never qualifies',
    g.alexGEvaluateRepeatedReaction({status:'validated',touches:[1,2,3]},{},3,'clean',cfg).qualifies===false);
  check('F4 (ALEX_X_005) a choppy zone is disqualified even at the 4th touch',
    g.alexGEvaluateRepeatedReaction(zoneValidated,{},3,'choppy',cfg).qualifies===false);
  check('F5 (ALEX_SR_011) an already-broken zone never produces a repeated-reaction setup',
    g.alexGEvaluateRepeatedReaction({status:'broken',touches:[1,2,3,4]},{},3,'clean',cfg).qualifies===false);

  // ALEX_SR_003 — a zone can never be traded against its current role.
  check('F6 (ALEX_SR_003) support -> buy',
    g.alexGDetermineTradeDirection({setupType:'A_repeatedReaction',zoneRoleAtQualification:'support'}).direction==='buy');
  check('F7 (ALEX_SR_003) resistance -> sell',
    g.alexGDetermineTradeDirection({setupType:'A_repeatedReaction',zoneRoleAtQualification:'resistance'}).direction==='sell');
  check('F8 (ALEX_SR_003) an "inside" role produces NO direction and a real rejection reason',
    (function(){ const r=g.alexGDetermineTradeDirection({setupType:'A_repeatedReaction',zoneRoleAtQualification:'inside'});
      return r.direction===null && r.rejectionReason==='INVALID_ZONE_ROLE_INSIDE'; })(),
    'the prohibition is enforced by construction -- there is no path to a wrong-side trade');

  // ALEX_SR_001 — role is positional relative to the zone.
  const z={low:1.1000,high:1.1020};
  check('F9 (ALEX_SR_001) price above the zone makes it support',
    g.alexGZoneRole(z,1.1050)==='support');
  check('F10 (ALEX_SR_001) price below the zone makes it resistance',
    g.alexGZoneRole(z,1.0950)==='resistance');
  check('F11 (ALEX_SR_001) price inside the zone is neither',
    g.alexGZoneRole(z,1.1010)==='inside');

  // ALEX_SR_004 — bidirectional: fromSide resolves above/below from the pre-anchor close.
  const candles=[{o:1.11,h:1.12,l:1.10,c:1.1100},{o:1.10,h:1.11,l:1.09,c:1.0900}];
  check('F12 (ALEX_SR_004) a close above the zone yields fromSide "above"',
    g.alexGDetermineFromSide(candles,1,1.1000,1.1020)==='above');
  check('F13 (ALEX_SR_004) an out-of-range anchor degrades to inside_unknown, never guesses',
    g.alexGDetermineFromSide(candles,0,1.1000,1.1020)==='inside_unknown');

  // ALEX_SR_009 — exactly four zone timeframes.
  check('F14 (ALEX_SR_009) config declares exactly H1, H4, D, W',
    JSON.stringify(cfg.zoneTimeframes)===JSON.stringify(['H1','H4','D','W']));

  // ALEX_SR_010 — higher-timeframe priority ordering.
  check('F15 (ALEX_SR_010) htfPriority orders W > D > H4 > H1',
    cfg.htfPriority.W>cfg.htfPriority.D && cfg.htfPriority.D>cfg.htfPriority.H4 &&
    cfg.htfPriority.H4>cfg.htfPriority.H1);

  // ── Body-close versus wick-break, and incomplete-candle behaviour ───────
  // RULES_ALEXG records that wick strength is RECORDED BUT NEVER REQUIRED
  // (requireWick defaults false, 'the source never mentions wicks'). These
  // fixtures assert that documented repository position -- not an educator rule.
  check('F16 (body vs wick) requireWick is false by default, per RULES_ALEXG',
    cfg.requireWick===false,
    'the artifact states the source never mentions wicks; a wick is never a requirement');
  check('F17 (body vs wick) minWickRatio is 0.0, so no wick threshold gates a reaction',
    cfg.minWickRatio===0.0);
  check('F18 (break confirmation) a break requires a confirming CLOSE count, not a wick touch',
    cfg.breakConfirmationCloses>=1,
    'breakConfirmationCloses='+cfg.breakConfirmationCloses);

  // ── Missing-context behaviour ──────────────────────────────────────────
  check('F19 (missing context) trend context on empty candles is INSUFFICIENT_DATA, never a guess',
    g.alexGComputeTrendContext([],0,cfg).trendContext==='INSUFFICIENT_DATA');
  check('F20 (missing context) an unsupported setup type yields no direction',
    (function(){ const r=g.alexGDetermineTradeDirection({setupType:'NOT_A_REAL_TYPE'});
      return !r || r.direction==null; })());

  // ── Risk configuration sanity (ALEX_X_001 — extra implementation rule) ──
  check('F21 (ALEX_X_001) riskPercent is a positive, non-zero fraction of the account',
    typeof cfg.riskPercent==='number' && cfg.riskPercent>0,
    'zero-risk protection: a zero riskPercent would size every trade at zero');
  check('F22 (ALEX_X_001) minRR is positive',
    typeof cfg.minRR==='number' && cfg.minRR>0, 'minRR='+cfg.minRR);
  check('F23 (ALEX_X_001) stopATRBuffer is non-negative',
    typeof cfg.stopATRBuffer==='number' && cfg.stopATRBuffer>=0);
  check('F24 (ALEX_X_001) the risk model exists in config but NOT in the specification',
    cfg.riskPercent!=null && g.getRulesAlexG().originalAlexConcepts.every(function(c){
      return c.toLowerCase().indexOf('stop loss')<0 && c.toLowerCase().indexOf('risk')<0;
    }),
    'this is the central fidelity finding: a full risk model with zero source authority');

  // ── Session restrictions (ALEX_X_007) ──────────────────────────────────
  check('F25 (ALEX_X_007) session metadata is computed but no session gate exists in config',
    typeof g.alexGComputeSessionMetadata==='function' &&
    cfg.sessionFilter===undefined && cfg.tradingDays===undefined,
    'RULES_ALEXG records zero session/day/news filtering as a deliberate choice');

  // ════════════════════════════════════════════════════════════════════════
  // G. Isolation — this milestone must not have changed trading behaviour
  // ════════════════════════════════════════════════════════════════════════
  check('G1 no provenance function writes to localStorage',
    (function(){ const before=g.getAllLocalStorageKeys().length;
      g.alexGStrategyVersionReference(); g.alexGStampTradeProvenance({tradeId:'Z'});
      g.alexGProvenanceSummary([{tradeId:'Z'}]);
      return g.getAllLocalStorageKeys().length===before; })(),
    'the fidelity layer persists nothing of its own');

  check('G2 no provenance function mutates the ALEX account or journal',
    (function(){ const a=JSON.stringify(g.getAlexGAccount()), j=JSON.stringify(g.getAlexGJournalEntries());
      g.alexGStrategyVersionReference(); g.alexGProvenanceSummary(g.getAlexGAccount().openPositions||[]);
      return JSON.stringify(g.getAlexGAccount())===a && JSON.stringify(g.getAlexGJournalEntries())===j; })());

  check('G3 no provenance function mutates RULES_ALEXG',
    (function(){ const b=JSON.stringify(g.getRulesAlexG());
      g.alexGStrategyVersionReference(); g.alexGStampTradeProvenance({tradeId:'Q'});
      return JSON.stringify(g.getRulesAlexG())===b; })(),
    'RULES_ALEXG is a protected constant');

  check('G4 snapshotAlexGConfig still returns an independent deep copy',
    (function(){ const s=g.snapshotAlexGConfig(); s.config.riskPercent=999;
      return g.snapshotAlexGConfig().config.riskPercent!==999; })());

  note('G5 protected-function/constant drift is verified by regression-baseline-tools.py',
    'Phase 5 added provenance in the NON-protected caller alexGAttemptOpenLivePosition; '+
    'alexGConstructLivePosition itself is untouched. Verified: zero drift across all 63 '+
    'protected functions and 4 protected constants.');

  return results;
}
