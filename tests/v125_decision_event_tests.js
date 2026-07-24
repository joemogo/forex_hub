// PROGRAM-001 Phase 2A -- Decision Event Schema & Observability Foundation.
//
// Exercises the REAL, unmodified functions createDecisionEvent/emitDecisionEvent/
// getDecisionEvents/clearDecisionEvents/validateDecisionEvent/generateDecisionEventId/
// renderDecisionEventDiagnostics against isolated, in-memory state only -- the same offline
// JXA-harness pattern every other suite in this repository uses. This is purely additive,
// memory-only, Diagnostics-only infrastructure: nothing under test places, modifies, or closes
// a trade, changes risk/thresholds/execution, or writes to localStorage.
//
// One deliberate, disclosed exception, consistent with this repository's established pattern
// (see docs/TESTING.md): scanAll() and alexGLivePollTick() are both genuinely `async` with real
// internal `await`s (fetchBidAsk/candle fetches) gating the remainder of their bodies, and this
// offline JXA harness cannot resolve a real await. SCAN_STARTED is emitted as the literal FIRST
// statement in each function, before either function's first await point, so calling them
// WITHOUT awaiting still executes that emit call synchronously -- proven directly, below, for
// both engines. SCAN_COMPLETED and ENGINE_ERROR from those two specific call sites require a
// real live browser pass to observe (see docs/PAPER_TRADING_AUDIT.md's established pattern for
// this exact limitation), and are disclosed as `requires-live-browser` notes rather than faked.
function runDecisionEventFixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,method:'execution',detail:detail||''});};
  const note=(name,method,detail)=>{results.push({name,pass:null,method,detail:detail||''});};

  function seedClean(){
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGJournalEntries([]);
    g.clearLocalStorage();
    g.clearDecisionEvents();
    g.setDeveloperMode(false);
  }

  // ── Schema ──
  {
    seedClean();
    assert('DecisionEvent.1: schema version constant is the versioned mogo.decision-event.v1 identifier',
      g.getDecisionEventSchemaVersion()==='mogo.decision-event.v1','got '+g.getDecisionEventSchemaVersion());
    const types=g.getDecisionEventTypes();
    const requiredTypes=['SCAN_STARTED','SCAN_COMPLETED','SETUP_OBSERVED','CANDIDATE_CREATED','RULE_EVALUATED','CANDIDATE_REJECTED','CANDIDATE_APPROVED','TRADE_OPEN_REQUESTED','TRADE_OPENED','TRADE_OPEN_FAILED','TRADE_CLOSED','DATA_UNAVAILABLE','ENGINE_ERROR'];
    assert('DecisionEvent.1b: the schema supports every required event type, even though not all are emitted yet',
      requiredTypes.every(t=>types[t]===t),'missing='+JSON.stringify(requiredTypes.filter(t=>types[t]!==t)));
  }

  // ── Valid event creation + required fields, never fabricated ──
  {
    seedClean();
    const event=g.createDecisionEvent({eventType:'SCAN_STARTED',strategyId:'current_strategy'});
    const requiredKeys=['eventId','schemaVersion','eventType','occurredAt','recordedAt','strategyId','strategyVersion','baselineId','applicationVersion','scanId','candidateId','tradeId','pair','direction','timeframe','session','source','engineMode','stage','decision','reasonCode','reasonText','ruleId','ruleVersion','ruleResult','severity','marketTimestamp','marketDataReference','context','metrics','diagnostics','parentEventId','correlationId','sequenceNumber','evidenceCompleteness','unknownFields'];
    assert('DecisionEvent.2: createDecisionEvent() produces every required schema field',
      requiredKeys.every(k=>Object.prototype.hasOwnProperty.call(event,k)),'missing='+JSON.stringify(requiredKeys.filter(k=>!Object.prototype.hasOwnProperty.call(event,k))));
    assert('DecisionEvent.2b: an omitted field is explicitly null, never fabricated as 0/empty-string/undefined',
      event.candidateId===null&&event.tradeId===null&&event.pair===null&&event.reasonCode===null&&event.metrics===null,JSON.stringify({candidateId:event.candidateId,tradeId:event.tradeId,pair:event.pair}));
    assert('DecisionEvent.2c: evidenceCompleteness defaults to the honest UNKNOWN enum value, never fabricated as COMPLETE',
      event.evidenceCompleteness==='UNKNOWN','got '+event.evidenceCompleteness);
    assert('DecisionEvent.2d: unknownFields defaults to an empty array, and is preserved verbatim when explicitly provided',
      Array.isArray(event.unknownFields)&&event.unknownFields.length===0&&JSON.stringify(g.createDecisionEvent({eventType:'SCAN_STARTED',unknownFields:['x','y']}).unknownFields)==='["x","y"]','');
  }

  // ── emitDecisionEvent: valid event succeeds and is retrievable ──
  {
    seedClean();
    const result=g.emitDecisionEvent({eventType:'SCAN_STARTED',strategyId:'current_strategy',evidenceCompleteness:'COMPLETE'});
    assert('DecisionEvent.3: emitting a valid SCAN_STARTED event succeeds and is retrievable via getDecisionEvents()',
      result.ok===true&&g.getDecisionEvents().length===1&&g.getDecisionEvents()[0].eventType==='SCAN_STARTED',JSON.stringify(result));
  }

  // ── Invalid events rejected safely, never crash ──
  {
    seedClean();
    const missingType=g.emitDecisionEvent({strategyId:'current_strategy'});
    assert('DecisionEvent.4: an event with a missing eventType is rejected (ok:false) and never enters the log',
      missingType.ok===false&&g.getDecisionEvents().length===0,JSON.stringify(missingType));
    const badType=g.emitDecisionEvent({eventType:'NOT_A_REAL_EVENT_TYPE'});
    assert('DecisionEvent.5: an event with an invalid eventType is rejected and never enters the log',
      badType.ok===false&&g.getDecisionEvents().length===0,JSON.stringify(badType));
    assert('DecisionEvent.5b: every rejected event is recorded in the validation-failures log for diagnosis, never silently dropped',
      g.getDecisionEventValidationFailures().length===2,'count='+g.getDecisionEventValidationFailures().length);
  }

  // ── Reason code validation: centralized registry is the source of truth ──
  {
    seedClean();
    const badReason=g.emitDecisionEvent({eventType:'ENGINE_ERROR',reasonCode:'MADE_UP_CODE_NOT_IN_REGISTRY'});
    assert('DecisionEvent.6: an unregistered reasonCode is rejected -- codes are validated against the centralized registry, not a loose prefix guess',
      badReason.ok===false,JSON.stringify(badReason));
    const goodReason=g.emitDecisionEvent({eventType:'ENGINE_ERROR',reasonCode:'SYSTEM_UNEXPECTED_ERROR',reasonText:'anything the caller wants to say'});
    assert('DecisionEvent.7: a real registered reasonCode is accepted, and reasonText is independent free-form wording never itself validated against a fixed list',
      goodReason.ok===true,JSON.stringify(goodReason));
    const categories=g.getReasonCodeCategories();
    const requiredCategories=['DATA','SESSION','STRUCTURE','BIAS','AOI','CONFLUENCE','ENTRY','RISK','SPREAD','EXECUTION','STATE','CONFIG','SYSTEM','UNKNOWN'];
    assert('DecisionEvent.7b: the reason-code category list covers every required category',
      requiredCategories.every(c=>categories.indexOf(c)!==-1),'missing='+JSON.stringify(requiredCategories.filter(c=>categories.indexOf(c)===-1)));
    const registry=g.getReasonCodeRegistry();
    const allCodesHaveValidCategory=Object.keys(registry).every(code=>categories.indexOf(registry[code].category)!==-1);
    assert('DecisionEvent.7c: every registered reason code belongs to one of the required categories',
      allCodesHaveValidCategory,'');
  }

  // ── Evidence completeness validation ──
  {
    seedClean();
    const badEvidence=g.emitDecisionEvent({eventType:'SCAN_STARTED',evidenceCompleteness:'SUPER_DUPER_SURE'});
    assert('DecisionEvent.8: an invalid evidenceCompleteness value is rejected',
      badEvidence.ok===false,JSON.stringify(badEvidence));
    const levels=g.getEvidenceCompletenessLevels();
    assert('DecisionEvent.8b: all four required evidence-completeness levels are supported',
      ['COMPLETE','PARTIAL','MINIMAL','UNKNOWN'].every(l=>levels.indexOf(l)!==-1),JSON.stringify(levels));
    const provenance=g.getEvidenceFieldProvenance();
    assert('DecisionEvent.8c: the field-provenance taxonomy distinguishes Observed/Derived/Unavailable/Unsafe-to-reconstruct/Future-work',
      ['OBSERVED','DERIVED','UNAVAILABLE','UNSAFE_TO_RECONSTRUCT','FUTURE_WORK'].every(p=>provenance.indexOf(p)!==-1),JSON.stringify(provenance));
  }

  // ── Unique identifiers: scan/candidate/trade lifecycle, never collide ──
  {
    seedClean();
    const ids=new Set();
    for(let i=0;i<200;i++) ids.add(g.generateDecisionEventId('SCAN'));
    assert('DecisionEvent.9: generateDecisionEventId() never collides even across 200 rapid-fire calls in the same tick',
      ids.size===200,'unique='+ids.size+'/200');
    const e1=g.emitDecisionEvent({eventType:'SCAN_STARTED'});
    const e2=g.emitDecisionEvent({eventType:'SCAN_STARTED'});
    assert('DecisionEvent.10: two events emitted back-to-back get distinct eventIds',
      e1.event.eventId!==e2.event.eventId,'');
  }

  // ── Correlation and parent linkage ──
  {
    seedClean();
    const scanId=g.generateDecisionEventId('SCAN');
    const started=g.emitDecisionEvent({eventType:'SCAN_STARTED',scanId,correlationId:scanId});
    const completed=g.emitDecisionEvent({eventType:'SCAN_COMPLETED',scanId,correlationId:scanId,parentEventId:started.event.eventId});
    assert('DecisionEvent.11: correlationId links two events of the same scan tick together, and parentEventId threads a causal chain',
      completed.event.correlationId===started.event.correlationId&&completed.event.parentEventId===started.event.eventId,'');
  }

  // ── Sequence ordering: strictly increasing, rejected events never consume a slot ──
  {
    seedClean();
    const first=g.emitDecisionEvent({eventType:'SCAN_STARTED'});
    const rejected=g.emitDecisionEvent({eventType:'NOT_REAL'});
    const second=g.emitDecisionEvent({eventType:'SCAN_COMPLETED'});
    assert('DecisionEvent.12: sequenceNumber increases by exactly 1 across two valid emits, even with a rejected emit attempted in between (a rejected event never consumes a sequence number)',
      rejected.ok===false&&second.event.sequenceNumber===first.event.sequenceNumber+1,JSON.stringify({first:first.event.sequenceNumber,second:second.event.sequenceNumber}));
    const events=g.getDecisionEvents();
    const sequenceIsMonotonic=events.every((e,i)=>i===0||e.sequenceNumber>events[i-1].sequenceNumber);
    assert('DecisionEvent.12b: events are reconstructable in true emission order via sequenceNumber',
      sequenceIsMonotonic,JSON.stringify(events.map(e=>e.sequenceNumber)));
  }

  // ── Immutability: append-only, never rewritten ──
  {
    seedClean();
    g.emitDecisionEvent({eventType:'SCAN_STARTED',strategyId:'current_strategy'});
    const eventRef=g.getDecisionEvents()[0];
    const originalStrategyId=eventRef.strategyId;
    try{ eventRef.strategyId='TAMPERED'; }catch(e){/* strict-mode engines may throw on a frozen-object write -- that is also a correct outcome */}
    const rereadEvent=g.getDecisionEvents()[0];
    assert('DecisionEvent.13: an already-emitted event cannot be rewritten later -- attempting to mutate a field on a retrieved event never changes the stored event',
      rereadEvent.strategyId===originalStrategyId,'original='+originalStrategyId+' afterAttemptedMutation='+rereadEvent.strategyId);
    const arrRef=g.getDecisionEvents();
    arrRef.push({fake:true});
    assert('DecisionEvent.14: getDecisionEvents() returns a defensive copy of the array -- pushing to it never affects the real in-memory log',
      g.getDecisionEvents().length===1,'realLogLength='+g.getDecisionEvents().length);
  }

  // ── Payload limits and serialization ──
  {
    seedClean();
    const hugeContext={blob:'x'.repeat(g.getDecisionEventMaxPayloadChars()+1000)};
    const tooLarge=g.emitDecisionEvent({eventType:'SCAN_STARTED',context:hugeContext});
    assert('DecisionEvent.17: an event whose serialized payload exceeds the configured max size is rejected rather than silently truncated or accepted',
      tooLarge.ok===false,JSON.stringify(tooLarge).slice(0,200));
    const normal=g.emitDecisionEvent({eventType:'SCAN_STARTED',context:{small:'fine'}});
    assert('DecisionEvent.18: a normally-sized event is JSON-serializable and round-trips preserving its eventId',
      normal.ok===true&&JSON.parse(JSON.stringify(normal.event)).eventId===normal.event.eventId,'');
  }

  // ── Failure isolation: the event bus itself can never throw into its caller ──
  {
    seedClean();
    const circular={};
    circular.self=circular;
    let threw=false,circularResult;
    try{ circularResult=g.emitDecisionEvent({eventType:'SCAN_STARTED',context:circular}); }catch(e){ threw=true; }
    assert('DecisionEvent.19: emitDecisionEvent() never throws even when given a genuinely unserializable (circular) payload -- it fails safely with {ok:false}',
      !threw&&circularResult&&circularResult.ok===false,JSON.stringify({threw,circularResult}));
  }

  // ── No mutation of any real trading/journal/account/baseline state ──
  {
    seedClean();
    g.setPaperAccount({balance:12345.67,openPositions:[{id:1,pair:'EUR/USD'}],closedPositions:[]});
    g.setJournalEntries([{tradeId:1,status:'OPEN'}]);
    g.setAlexGAccount({balance:9999.99,openPositions:[{tradeId:'A1'}],closedPositions:[]});
    g.setAlexGJournalEntries([{tradeId:'A1',status:'OPEN'}]);
    const scanBefore=JSON.stringify(g.getScanData());
    const autoBefore=JSON.stringify(g.getAutoTrading());
    const alexAutoBefore=JSON.stringify(g.getAlexGAutoTrading());
    const paperBefore=JSON.stringify(g.getPaperAccount());
    const journalBefore=JSON.stringify(g.getJournalEntries());
    const alexAcctBefore=JSON.stringify(g.getAlexGAccount());
    const alexJournalBefore=JSON.stringify(g.getAlexGJournalEntries());
    // computeBaselineRegistry() legitimately stamps a fresh createdAt/generatedAt timestamp on
    // every call by design (Phase 1) -- so the STABLE part to compare is the fingerprints
    // themselves, not full-object JSON equality (which would always differ on timestamp alone).
    const baselineFingerprintsBefore=(function(r){return JSON.stringify({jvm:[r.jvm.logicFingerprint,r.jvm.riskFingerprint,r.jvm.configurationFingerprint],alex:[r.alex.logicFingerprint,r.alex.riskFingerprint,r.alex.configurationFingerprint]});})(g.computeBaselineRegistry());

    for(let i=0;i<20;i++) g.emitDecisionEvent({eventType:'SCAN_STARTED',strategyId:i%2===0?'current_strategy':'alex_g_sr_v1'});
    g.setDeveloperMode(true);
    g.renderDecisionEventDiagnostics();
    g.clearDecisionEvents();

    assert('DecisionEvent.20: no journal mutation -- journalEntries/alexGJournalEntries are byte-identical before and after a batch of Decision Event operations',
      JSON.stringify(g.getJournalEntries())===journalBefore&&JSON.stringify(g.getAlexGJournalEntries())===alexJournalBefore,'');
    assert('DecisionEvent.21: no paper-account mutation -- paperAccount/alexGAccount are byte-identical before and after a batch of Decision Event operations',
      JSON.stringify(g.getPaperAccount())===paperBefore&&JSON.stringify(g.getAlexGAccount())===alexAcctBefore,'');
    assert('DecisionEvent.21b: scanData/autoTrading/alexGAutoTrading are also completely untouched',
      JSON.stringify(g.getScanData())===scanBefore&&JSON.stringify(g.getAutoTrading())===autoBefore&&JSON.stringify(g.getAlexGAutoTrading())===alexAutoBefore,'');
    const baselineFingerprintsAfter=(function(r){return JSON.stringify({jvm:[r.jvm.logicFingerprint,r.jvm.riskFingerprint,r.jvm.configurationFingerprint],alex:[r.alex.logicFingerprint,r.alex.riskFingerprint,r.alex.configurationFingerprint]});})(g.computeBaselineRegistry());
    assert('DecisionEvent.22: no Baseline Registry mutation -- computeBaselineRegistry() produces byte-identical fingerprints (logic/risk/configuration) before and after Decision Event operations (cross-feature isolation; createdAt/generatedAt timestamps are expected to differ by design and are deliberately excluded from this comparison)',
      baselineFingerprintsAfter===baselineFingerprintsBefore,'before='+baselineFingerprintsBefore+' after='+baselineFingerprintsAfter);
  }

  // ── Storage isolation: memory-only, zero persistence ──
  {
    seedClean();
    const keysBefore=g.getAllLocalStorageKeys().slice();
    for(let i=0;i<10;i++) g.emitDecisionEvent({eventType:'SCAN_STARTED'});
    g.setDeveloperMode(true);
    g.renderDecisionEventDiagnostics();
    const keysAfter=g.getAllLocalStorageKeys().slice();
    assert('DecisionEvent.24: Decision Event operations write ZERO localStorage keys -- this layer is memory-only by explicit Phase 2A mandate, unlike the Baseline Registry',
      JSON.stringify(keysBefore)===JSON.stringify(keysAfter),'before='+JSON.stringify(keysBefore)+' after='+JSON.stringify(keysAfter));
    assert('DecisionEvent.24b: clearDecisionEvents() (simulating what a real reload would do, since nothing is persisted) empties the log completely',
      (g.clearDecisionEvents(),g.getDecisionEvents().length===0),'');
  }

  // ── Developer Mode preview ──
  {
    seedClean();
    g.emitDecisionEvent({eventType:'SCAN_STARTED',strategyId:'current_strategy'});
    g.setDeveloperMode(true);
    g.renderDecisionEventDiagnostics();
    const htmlOn=g.getDecisionEventCardEl().innerHTML;
    assert('DecisionEvent.23: with Developer Mode ON, the diagnostics card shows Schema Version, Event Bus Status, Events in Memory, Last Event, Validation Failures, and Persistence Status',
      htmlOn.indexOf('Decision Event Bus')!==-1&&htmlOn.indexOf('Schema Version')!==-1&&htmlOn.indexOf('Event Bus Status')!==-1&&htmlOn.indexOf('Events in Memory')!==-1&&htmlOn.indexOf('Last Event')!==-1&&htmlOn.indexOf('Validation Failures')!==-1&&htmlOn.indexOf('Persistence Status')!==-1,'');
    g.setDeveloperMode(false);
    g.renderDecisionEventDiagnostics();
    assert('DecisionEvent.23b: with Developer Mode OFF, the diagnostics card is cleared',
      g.getDecisionEventCardEl().innerHTML==='','');
  }

  // ── Protected-function / instrumentation-boundary check ──
  {
    assert('DecisionEvent.25: scanAll() (the JVM instrumentation point) is confirmed NOT a protected function, cross-checked directly against Phase 1\'s already-verified BASELINE_JVM_FUNCTIONS mirror of PROTECTED_FUNCTIONS',
      g.getBaselineJvmFunctions().indexOf('scanAll')===-1,'');
    assert('DecisionEvent.25b: alexGLivePollTick() (the ALEX instrumentation point) is confirmed NOT a protected function, cross-checked directly against Phase 1\'s already-verified BASELINE_ALEX_FUNCTIONS mirror of PROTECTED_FUNCTIONS',
      g.getBaselineAlexFunctions().indexOf('alexGLivePollTick')===-1,'');
  }

  // ── Real emission from the actual instrumented scan-boundary functions ──
  // scanAll()/alexGLivePollTick() are async with a real internal await; SCAN_STARTED is their
  // literal first statement, executed synchronously before either function suspends at its
  // first await -- so calling them WITHOUT awaiting still lets us observe SCAN_STARTED for
  // real, in this offline harness, even though the rest of each function cannot complete here.
  {
    seedClean();
    g.scanAll(); // deliberately not awaited -- runs synchronously up to its first await
    const jvmEvents=g.getDecisionEvents().filter(e=>e.eventType==='SCAN_STARTED'&&e.source==='scanAll');
    assert('DecisionEvent.27: calling the real scanAll() emits a genuine SCAN_STARTED event for JVM (strategyId current_strategy) as its first synchronous action',
      jvmEvents.length===1&&jvmEvents[0].strategyId==='current_strategy'&&jvmEvents[0].scanId===jvmEvents[0].correlationId&&jvmEvents[0].scanId!=null,JSON.stringify(jvmEvents));
  }
  {
    seedClean();
    g.alexGLivePollTick(); // deliberately not awaited -- runs synchronously up to its first await
    const alexEvents=g.getDecisionEvents().filter(e=>e.eventType==='SCAN_STARTED'&&e.source==='alexGLivePollTick');
    assert('DecisionEvent.28: calling the real alexGLivePollTick() emits a genuine SCAN_STARTED event for ALEX (strategyId alex_g_sr_v1) as its first synchronous action',
      alexEvents.length===1&&alexEvents[0].strategyId==='alex_g_sr_v1'&&alexEvents[0].scanId===alexEvents[0].correlationId&&alexEvents[0].scanId!=null,JSON.stringify(alexEvents));
  }
  note('DecisionEvent.29: SCAN_COMPLETED (both engines) and ENGINE_ERROR (both engines) fire only after each function\'s real internal await resolves (fetchBidAsk/candle fetches) -- this offline JXA harness cannot resolve a genuine await (documented, permanent limitation, same as closePaperPosition()/alexGCloseLivePosition() elsewhere in this suite family). Verified live in a real browser instead.',
    'requires-live-browser','');

  // ── Reload behavior ──
  {
    seedClean();
    g.emitDecisionEvent({eventType:'SCAN_STARTED'});
    assert('DecisionEvent.reload: since nothing is ever persisted, a simulated reload (clearDecisionEvents(), the same effect a real page reload has on this memory-only log) leaves the bus empty but fully functional afterward',
      g.getDecisionEvents().length===1&&(g.clearDecisionEvents(),g.getDecisionEvents().length===0)&&g.emitDecisionEvent({eventType:'SCAN_STARTED'}).ok===true,'');
  }

  return results;
}
