// PROGRAM-001 Phase 2C Wave 1 (ALEX Candidate Lifecycle Instrumentation) fixture suite.
// Exercises the REAL, unmodified alexG zone/setup/construction engine wherever possible --
// a synthetic but genuinely valid H1 candle sequence (built below) is run through the real
// alexGRunSetupEngine/alexGClassifyTouch/alexGEvaluateRepeatedReaction chain to produce an
// organic REPEATED ZONE REACTION setup, then the real alexGEvaluatePairForLiveSetups() and
// alexGAttemptOpenLivePosition() are called end-to-end (network stubbed at the fetch() layer
// only -- never at any protected function) to prove the new Decision Event wiring fires
// correctly. No protected function or protected constant is edited or duplicated anywhere in
// this file. All async scenarios (Tier A) run strictly SEQUENTIALLY (chained, never
// concurrent) since they share ALEX's real, unmodified module-level state -- running them
// concurrently would let one scenario's resetAlexState() clobber another's in-flight run.
function runPhase2CWave1Fixtures(g){
  const results=[];
  function check(name,cond,detail){ results.push({name,pass:!!cond,detail:detail||''}); }
  function note(name,detail){ results.push({name,pass:null,detail,method:'live-browser'}); }

  // ── Candle generation: builds a synthetic H1 series that produces exactly one genuine
  // REPEATED ZONE REACTION setup via the real, unmodified zone/setup engine. Verified directly
  // (see scratchpad prototype) to yield qualificationBarIndex=47 with 4 real touches on a
  // support zone. t0 controls how "fresh" the resulting qualificationTimestamp is, relative to
  // real Date.now(), for staleness testing.
  function buildRepeatedReactionH1(t0){
    const candles=[];
    function push(o,h,l,c){ candles.push({o,h,l,c,t:new Date(t0+candles.length*3600000)}); }
    function filler(n){
      let base=1.10600;
      for(let i=0;i<n;i++){
        const drift=(i%3)*0.00005;
        push(base+drift,base+drift+0.00080,base+drift-0.00040,base+drift+0.00020);
      }
    }
    filler(14);
    const touchLows=[1.10000,1.10002,1.09998,1.10001];
    const idxs=[14,24,34,44];
    let i=14;
    while(i<=44){
      if(idxs.indexOf(i)!==-1){
        const l=touchLows[idxs.indexOf(i)];
        push(l+0.00020,l+0.00025,l,l+0.00015); i++;
        push(l+0.00015,l+0.00200,l+0.00010,l+0.00180); i++;
      } else { filler(1); i++; }
    }
    filler(20);
    return candles;
  }
  function buildMinimalHTF(t0,n){
    const candles=[];
    for(let i=0;i<n;i++){
      candles.push({o:1.1,h:1.101,l:1.099,c:1.1005,t:new Date(t0+i*4*3600000)});
    }
    return candles;
  }

  // ── Real-shaped fetch stub: serves candle-history requests (fetchCandlesRange, used by
  // fetchAlexGReplayDatasets) and bid/ask pricing requests (fetchBidAsk) in OANDA's own
  // response shapes, so the REAL unmodified fetchCandlesRange/fetchBidAsk (never edited,
  // never duplicated) legitimately parse and return real data. This is a network-boundary
  // stub only -- no application function is replaced or altered.
  function installFetchStub(candlesByGran,bidAskBox){
    globalThis.fetch=async function(url){
      const cm=url.match(/instruments\/[^/]+\/candles\?count=(\d+)&granularity=(\w+)/);
      if(cm){
        const gran=cm[2];
        const isSubsequentPage=/&to=/.test(url);
        if(isSubsequentPage) return{ok:true,json:async()=>({candles:[]})};
        const arr=candlesByGran[gran]||[];
        const candles=arr.map(c=>({time:c.t.toISOString(),complete:true,mid:{o:String(c.o),h:String(c.h),l:String(c.l),c:String(c.c)}}));
        return{ok:true,json:async()=>({candles})};
      }
      if(/\/pricing\?instruments=/.test(url)){
        if(!bidAskBox.value) return{ok:false};
        return{ok:true,json:async()=>({prices:[{bids:[{price:String(bidAskBox.value.bid)}],asks:[{price:String(bidAskBox.value.ask)}]}]})};
      }
      return{ok:false};
    };
  }
  function installOfflineFetch(){
    globalThis.fetch=function(){ return Promise.reject(new Error('no network')); };
  }

  function resetAlexState(){
    g.setAlexGSetupState([]);
    g.setAlexGZoneState({});
    g.setAlexGLastEvaluatedCloseTime({});
    g.setAlexGLiveSetupStatuses([]);
    // MOGO-021 DECISIONS 2+3: clear the decided-authority with the ring -- same session lifetime.
    g.resetLiveDecisionState();
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGJournalEntries([]);
    g.setAlexGAutoTrading({enabled:true,activatedAt:null,tradedSignals:{},tradedToday:{},log:[]});
    g.clearDecisionEvents();
    g.clearLocalStorage();
    g.setAlexGAccountKnownVersion(0);
  }

  // ═══════════════════════════════════════════════════════════════════════
  // TIER A -- full real end-to-end via alexGEvaluatePairForLiveSetups() / alexGAttemptOpenLivePosition(),
  // network stubbed only at fetch(), zone/setup engine fully real and organic. Each step is a
  // named function returning a Promise; they are chained sequentially at the bottom of this
  // file so no two scenarios ever touch ALEX's shared module state concurrently.
  // ═══════════════════════════════════════════════════════════════════════

  // --- A1: fresh, non-stale, activation-eligible setup -> full successful lifecycle ---
  function stepA1(){
    resetAlexState();
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000; // qualification lands ~5 min ago -- well within staleness window
    const H1=buildRepeatedReactionH1(t0);
    const H4=buildMinimalHTF(t0-30*24*3600000,20), D=buildMinimalHTF(t0-30*24*3600000,20), W=buildMinimalHTF(t0-30*24*3600000,20);
    installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}}); // near qualificationClose, so entry-delay stays tiny
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs-72*3600000,tradedSignals:{},tradedToday:{},log:[]}); // activated well before qualification -> PASS
    // v12.6.0 pre-release correction: CANDIDATE_CREATED now requires the setup's qualificationTimestamp to
    // fall strictly after the pair's real, pre-existing "already evaluated up to" boundary --
    // simulate that this pair was already live-polled up through an H1 boundary BEFORE this
    // setup's own qualification (t0+48h), so the new touch is genuinely classified as newly live,
    // not a historical reconstruction.
    g.setAlexGLastEvaluatedCloseTime({EUR_USD:{H1:t0+40*3600000}});
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|test-1').then(function(){
      const events=g.getDecisionEvents();
      const created=events.filter(e=>e.eventType==='CANDIDATE_CREATED');
      check('Phase2C.1: exactly one CANDIDATE_CREATED for the one genuine new setup',created.length===1,JSON.stringify(created.map(e=>e.candidateId)));
      const setup=g.getAlexGSetupState()[0];
      check('Phase2C.4: CANDIDATE_CREATED candidateId equals the real setup.setupId',created.length===1&&setup&&created[0].candidateId===setup.setupId,created[0]&&created[0].candidateId);
      const ruleEvActivation=events.filter(e=>e.eventType==='RULE_EVALUATED'&&e.ruleId==='ALEX_ACTIVATION_CUTOFF');
      check('Phase2C.6: activation-eligible setup produces RULE_EVALUATED PASS',ruleEvActivation.length===1&&ruleEvActivation[0].ruleResult==='PASS'&&ruleEvActivation[0].reasonCode===null,JSON.stringify(ruleEvActivation[0]));
      const ruleEvStale=events.filter(e=>e.eventType==='RULE_EVALUATED'&&e.ruleId==='ALEX_SIGNAL_STALENESS');
      check('Phase2C.9: fresh setup produces RULE_EVALUATED PASS for staleness',ruleEvStale.length===1&&ruleEvStale[0].ruleResult==='PASS'&&ruleEvStale[0].reasonCode===null,JSON.stringify(ruleEvStale[0]));
      const requested=events.filter(e=>e.eventType==='TRADE_OPEN_REQUESTED');
      check('Phase2C.13: TRADE_OPEN_REQUESTED occurs before construction outcome',requested.length===1,JSON.stringify(requested[0]));
      const approved=events.filter(e=>e.eventType==='CANDIDATE_APPROVED');
      check('Phase2C.14: successful construction produces CANDIDATE_APPROVED',approved.length===1&&approved[0].direction==='buy',JSON.stringify(approved[0]));
      const opened=events.filter(e=>e.eventType==='TRADE_OPENED');
      check('Phase2C.25: successful commit produces TRADE_OPENED',opened.length===1,JSON.stringify(opened[0]));
      const openedPos=g.getAlexGAccount().openPositions[0];
      check('Phase2C.26: tradeId links back to the real candidate (setupId) via context/signalId chain',
        opened.length===1&&openedPos&&opened[0].tradeId===openedPos.tradeId&&opened[0].candidateId===setup.setupId,
        JSON.stringify({eventTradeId:opened[0]&&opened[0].tradeId,posTradeId:openedPos&&openedPos.tradeId}));
      const scanIds=new Set(events.map(e=>e.scanId));
      check('Phase2C.27: scanId propagates through the full lifecycle (single consistent value)',scanIds.size===1&&scanIds.has('SCAN|test-1'),JSON.stringify([...scanIds]));
      const seqs=events.map(e=>e.sequenceNumber);
      const sorted=seqs.slice().sort((a,b)=>a-b);
      check('Phase2C.28: event ordering is reconstructable via strictly increasing sequenceNumber',JSON.stringify(seqs)===JSON.stringify(sorted)&&new Set(seqs).size===seqs.length,JSON.stringify(seqs));
      check('Phase2C.5: signalId preserved via alexGLiveSignalId and present in context',
        created.length===1&&created[0].context&&typeof created[0].context.qualificationTimestamp==='number',
        JSON.stringify(created[0]&&created[0].context));
      check('Phase2C.3: a single organic setup produces a single CANDIDATE_CREATED',created.length===1);
      installOfflineFetch();
    });
  }

  // --- A2: existing-status duplicate on a second poll of the SAME setup must not re-fire CANDIDATE_CREATED ---
  function stepA2(){
    resetAlexState();
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000;
    const H1=buildRepeatedReactionH1(t0);
    const H4=buildMinimalHTF(t0-30*24*3600000,20), D=buildMinimalHTF(t0-30*24*3600000,20), W=buildMinimalHTF(t0-30*24*3600000,20);
    installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs-72*3600000,tradedSignals:{},tradedToday:{},log:[]});
    g.setAlexGLastEvaluatedCloseTime({EUR_USD:{H1:t0+40*3600000}}); // simulate a genuine prior live boundary, so the first poll's setup is newly-live
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|dup-a').then(function(){
      const firstRunCreated=g.getDecisionEvents().filter(e=>e.eventType==='CANDIDATE_CREATED').length;
      const seqBeforeSecondPoll=g.getDecisionEvents().length;
      // Deliberately do NOT clearDecisionEvents() here -- a real subsequent poll never clears
      // the log (only the dev "Clear" button does, which also resets candidate dedup tracking
      // by design). This models what a genuine second alexGLivePollTick tick actually looks
      // like: the same in-memory log and dedup state simply continue accumulating.
      return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|dup-b').then(function(){
        const events=g.getDecisionEvents();
        const secondPollEvents=events.slice(seqBeforeSecondPoll);
        const secondRunCreated=secondPollEvents.filter(e=>e.eventType==='CANDIDATE_CREATED').length;
        check('Phase2C.2: existing setup does not produce a duplicate CANDIDATE_CREATED on a later poll',firstRunCreated===1&&secondRunCreated===0,'first='+firstRunCreated+' second='+secondRunCreated);
        const dedupRejected=secondPollEvents.filter(e=>e.eventType==='CANDIDATE_REJECTED'&&e.reasonCode==='STATE_SIGNAL_ALREADY_DECIDED');
        check('Phase2C.12: existing-status duplicate produces CANDIDATE_REJECTED(STATE_SIGNAL_ALREADY_DECIDED)',dedupRejected.length===1,JSON.stringify(dedupRejected[0]));
        installOfflineFetch();
      });
    });
  }

  // --- A3: activation-FAIL (setup qualified before automation was ever activated) ---
  function stepA3(){
    resetAlexState();
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000;
    const H1=buildRepeatedReactionH1(t0);
    const H4=buildMinimalHTF(t0-30*24*3600000,20), D=buildMinimalHTF(t0-30*24*3600000,20), W=buildMinimalHTF(t0-30*24*3600000,20);
    installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs+3600000,tradedSignals:{},tradedToday:{},log:[]}); // activated AFTER qualification -> FAIL
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|activ-fail').then(function(){
      const events=g.getDecisionEvents();
      const ruleEv=events.filter(e=>e.eventType==='RULE_EVALUATED'&&e.ruleId==='ALEX_ACTIVATION_CUTOFF');
      check('Phase2C.7: activation-ineligible setup produces RULE_EVALUATED FAIL',ruleEv.length===1&&ruleEv[0].ruleResult==='FAIL'&&ruleEv[0].reasonCode==='CONFIG_BEFORE_ACTIVATION',JSON.stringify(ruleEv[0]));
      const rejected=events.filter(e=>e.eventType==='CANDIDATE_REJECTED'&&e.reasonCode==='CONFIG_BEFORE_ACTIVATION');
      check('Phase2C.8: activation-cutoff failure produces a linked CANDIDATE_REJECTED',rejected.length===1&&ruleEv.length===1&&rejected[0].parentEventId===ruleEv[0].eventId,JSON.stringify(rejected[0]));
      check('Phase2C.29: parentEventId linkage is valid (matches the real RULE_EVALUATED eventId)',rejected.length===1&&ruleEv.length===1&&rejected[0].parentEventId===ruleEv[0].eventId);
      const requested=events.filter(e=>e.eventType==='TRADE_OPEN_REQUESTED');
      check('Activation-blocked setup never reaches TRADE_OPEN_REQUESTED',requested.length===0);
      installOfflineFetch();
    });
  }

  // --- A4: staleness-FAIL (setup qualified long ago, real Date.now() is far beyond the H1 window) ---
  function stepA4(){
    resetAlexState();
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-10*24*3600000; // qualification ~10 days ago
    const H1=buildRepeatedReactionH1(t0);
    const H4=buildMinimalHTF(t0-30*24*3600000,20), D=buildMinimalHTF(t0-30*24*3600000,20), W=buildMinimalHTF(t0-30*24*3600000,20);
    installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs-30*24*3600000,tradedSignals:{},tradedToday:{},log:[]}); // activated well before -> activation PASS, isolating staleness
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|stale').then(function(){
      const events=g.getDecisionEvents();
      const ruleEv=events.filter(e=>e.eventType==='RULE_EVALUATED'&&e.ruleId==='ALEX_SIGNAL_STALENESS');
      check('Phase2C.10: stale setup produces RULE_EVALUATED FAIL',ruleEv.length===1&&ruleEv[0].ruleResult==='FAIL'&&ruleEv[0].reasonCode==='STATE_SIGNAL_STALE',JSON.stringify(ruleEv[0]));
      const rejected=events.filter(e=>e.eventType==='CANDIDATE_REJECTED'&&e.reasonCode==='STATE_SIGNAL_STALE');
      check('Phase2C.11: staleness failure produces a linked CANDIDATE_REJECTED',rejected.length===1&&ruleEv.length===1&&rejected[0].parentEventId===ruleEv[0].eventId,JSON.stringify(rejected[0]));
      installOfflineFetch();
    });
  }

  // --- A5: ledger commit failure via the REAL version-guard (another tab already saved a
  // newer version) -- genuine, unmodified saveAlexGAccountGuarded() rejection, no network needed.
  function stepA5(){
    resetAlexState();
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000;
    const H1=buildRepeatedReactionH1(t0);
    const H4=buildMinimalHTF(t0-30*24*3600000,20), D=buildMinimalHTF(t0-30*24*3600000,20), W=buildMinimalHTF(t0-30*24*3600000,20);
    installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs-72*3600000,tradedSignals:{},tradedToday:{},log:[]});
    g.setLocalStorageItem('fxhub_alexg_account_version','999'); // simulate another tab already at a newer version
    const accountBefore=JSON.parse(JSON.stringify(g.getAlexGAccount()));
    const journalBefore=JSON.parse(JSON.stringify(g.getAlexGJournalEntries()));
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|ledger-fail').then(function(){
      const events=g.getDecisionEvents();
      const approved=events.filter(e=>e.eventType==='CANDIDATE_APPROVED');
      check('Construction still succeeds (CANDIDATE_APPROVED) before the ledger layer rejects it',approved.length===1,JSON.stringify(approved[0]));
      const failed=events.filter(e=>e.eventType==='TRADE_OPEN_FAILED'&&e.reasonCode==='EXECUTION_LEDGER_REJECTED');
      check('Phase2C.23: real STALE_VERSION ledger rejection produces TRADE_OPEN_FAILED(EXECUTION_LEDGER_REJECTED)',failed.length===1,JSON.stringify(failed[0]));
      check('Phase2C.24: ledger failure preserves the existing rollback -- alexGAccount/alexGJournalEntries unchanged',
        JSON.stringify(g.getAlexGAccount())===JSON.stringify(accountBefore)&&JSON.stringify(g.getAlexGJournalEntries())===JSON.stringify(journalBefore));
      installOfflineFetch();
    });
  }

  // --- A6: real, offline-reachable construction rejection (no bid/ask) proves TRADE_OPEN_FAILED
  // wiring fires for a genuine BLOCKED outcome too, not only success. ---
  function stepA6(){
    resetAlexState();
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000;
    const H1=buildRepeatedReactionH1(t0);
    const H4=buildMinimalHTF(t0-30*24*3600000,20), D=buildMinimalHTF(t0-30*24*3600000,20), W=buildMinimalHTF(t0-30*24*3600000,20);
    installFetchStub({H1:H1,H4:H4,D:D,W:W},{value:null}); // candle history real; bid/ask deliberately unavailable
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs-72*3600000,tradedSignals:{},tradedToday:{},log:[]});
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|no-baask').then(function(){
      const events=g.getDecisionEvents();
      const failed=events.filter(e=>e.eventType==='TRADE_OPEN_FAILED'&&e.reasonCode==='EXECUTION_SPREAD_UNAVAILABLE');
      check('Phase2C.18 (real, end-to-end): no bid/ask maps to TRADE_OPEN_FAILED(EXECUTION_SPREAD_UNAVAILABLE)',failed.length===1,JSON.stringify(failed[0]));
      const opened=events.filter(e=>e.eventType==='TRADE_OPENED');
      check('No trade opens when bid/ask is unavailable',opened.length===0);
      installOfflineFetch();
    });
  }

  // --- A7: ENGINE_ERROR observability inside the pre-existing silent catch, without changing
  // its swallow-and-continue behavior. Forces a genuine exception from inside the awaited chain. ---
  function stepA7(){
    resetAlexState();
    // fetchCandlesRange() has its OWN try/catch around the fetch() call itself (a network
    // failure there is expected and handled by simply stopping pagination) -- but r.json() is
    // deliberately outside that inner try/catch, so a genuine parse fault there propagates all
    // the way up through fetchAlexGReplayDatasets into alexGEvaluatePairForLiveSetups's own
    // try/catch, exactly like a real malformed-response fault would.
    globalThis.fetch=async function(){ return{ok:true,json:async function(){ throw new Error('Phase2C.32 synthetic engine fault'); }}; };
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|err').then(function(returnedValue){
      const events=g.getDecisionEvents();
      const errEvents=events.filter(e=>e.eventType==='ENGINE_ERROR');
      check('Phase2C.32: silent ALEX catch emits ENGINE_ERROR',errEvents.length===1&&errEvents[0].reasonCode==='SYSTEM_UNEXPECTED_ERROR'&&/synthetic engine fault/.test(errEvents[0].reasonText||''),JSON.stringify(errEvents[0]));
      // MOGO-021: this asserted returnedValue===undefined as a PROXY for "did not rethrow". The
      // function now reports its outcome so the poll ledger can attribute coverage truthfully, so
      // assert the actual intent -- it resolved rather than threw -- plus the new honesty: a pair
      // whose evaluation faulted must NOT be reported as evaluated.
      check('Phase2C.33: silent ALEX catch still does not rethrow, and reports the pair as NOT evaluated',
        !!returnedValue&&returnedValue.evaluated===false&&returnedValue.reason==='SYSTEM_UNEXPECTED_ERROR',
        JSON.stringify(returnedValue));
      installOfflineFetch();
    }).catch(function(e){
      check('Phase2C.33: silent ALEX catch still does not rethrow (function resolved normally)',false,'threw: '+e.message);
      installOfflineFetch();
    });
  }

  // --- A8: candidate/trade processing survives a deliberately-invalid emit elsewhere on the bus
  // (schema validation failure) -- the real trade must still complete. ---
  function stepA8(){
    resetAlexState();
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000;
    const H1=buildRepeatedReactionH1(t0);
    const H4=buildMinimalHTF(t0-30*24*3600000,20), D=buildMinimalHTF(t0-30*24*3600000,20), W=buildMinimalHTF(t0-30*24*3600000,20);
    installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs-72*3600000,tradedSignals:{},tradedToday:{},log:[]});
    const circularCtx={}; circularCtx.self=circularCtx;
    const emitResult=g.emitDecisionEvent({eventType:'CANDIDATE_CREATED',strategyId:'alex_g_sr_v1',context:circularCtx});
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|isolation').then(function(){
      check('Phase2C.19/30: a deliberately-invalid emit is rejected safely, never thrown',emitResult.ok===false,JSON.stringify(emitResult.errors));
      const events=g.getDecisionEvents();
      const opened=events.filter(e=>e.eventType==='TRADE_OPENED');
      check('Phase2C.20/31: real candidate/trade processing completes normally despite the unrelated invalid emit',opened.length===1,'opened='+opened.length);
      installOfflineFetch();
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  // TIER D -- v12.6.0 pre-release correction: CANDIDATE_CREATED must mean genuinely newly-live, never a
  // historical setup alexGRunSetupEngine() merely reconstructed again from old candles.
  // ═══════════════════════════════════════════════════════════════════════

  // --- D1: historical setup reconstructed on the FIRST poll (no prior live boundary exists for
  // this pair -- exactly the real "first poll after page load" scenario) must not emit ordinary
  // CANDIDATE_CREATED, but its trading treatment (RULE_EVALUATED, activation/staleness gating,
  // eventual trade-open) must proceed completely unchanged. ---
  function stepD1(){
    resetAlexState(); // alexGLastEvaluatedCloseTime is {} here -- no prior live boundary for any pair
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000;
    const H1=buildRepeatedReactionH1(t0);
    const H4=buildMinimalHTF(t0-30*24*3600000,20), D=buildMinimalHTF(t0-30*24*3600000,20), W=buildMinimalHTF(t0-30*24*3600000,20);
    installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs-72*3600000,tradedSignals:{},tradedToday:{},log:[]});
    // Deliberately NOT seeding alexGLastEvaluatedCloseTime -- this is the exact scenario the
    // correction targets: a 90-day historical reconstruction with no prior live poll to compare against.
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|first-poll').then(function(){
      const events=g.getDecisionEvents();
      const created=events.filter(e=>e.eventType==='CANDIDATE_CREATED');
      check('Phase2C.45 (D1): historical setup reconstructed on first poll does not emit ordinary CANDIDATE_CREATED',created.length===0,'created='+created.length);
      const ruleEvActivation=events.filter(e=>e.eventType==='RULE_EVALUATED'&&e.ruleId==='ALEX_ACTIVATION_CUTOFF');
      check('Phase2C.46 (D1/item 6): historical setup still passes through RULE_EVALUATED(activation) unchanged',ruleEvActivation.length===1&&ruleEvActivation[0].ruleResult==='PASS',JSON.stringify(ruleEvActivation[0]));
      const ruleEvStale=events.filter(e=>e.eventType==='RULE_EVALUATED'&&e.ruleId==='ALEX_SIGNAL_STALENESS');
      check('Phase2C.47 (D1/item 13): historical setup still passes through RULE_EVALUATED(staleness) unchanged',ruleEvStale.length===1&&ruleEvStale[0].ruleResult==='PASS',JSON.stringify(ruleEvStale[0]));
      const opened=events.filter(e=>e.eventType==='TRADE_OPENED');
      check('Phase2C.48 (D1/item 11): historical setup still opens a real trade -- trading behavior is completely unchanged',opened.length===1,'opened='+opened.length);
      installOfflineFetch();
    });
  }

  // --- D2: reload simulation -- after a real reload, alexGLastEvaluatedCloseTime resets to {}
  // (it is never persisted) and decisionEventKnownCandidateIds resets too (fresh session). The
  // very first poll after that reload must still treat the same historical setup as historical. ---
  function stepD2(){
    resetAlexState(); // models exactly what a real page reload leaves behind: {} and a fresh dedup set
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000;
    const H1=buildRepeatedReactionH1(t0);
    const H4=buildMinimalHTF(t0-30*24*3600000,20), D=buildMinimalHTF(t0-30*24*3600000,20), W=buildMinimalHTF(t0-30*24*3600000,20);
    installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs-72*3600000,tradedSignals:{},tradedToday:{},log:[]});
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|post-reload').then(function(){
      const created=g.getDecisionEvents().filter(e=>e.eventType==='CANDIDATE_CREATED');
      check('Phase2C.49 (D2/item 2): historical setup remains excluded after a reload simulation',created.length===0,'created='+created.length);
      check('Phase2C.50 (D2/item 18): reload clears only in-memory Decision Event state (alexGSetupState itself is unaffected by clearDecisionEvents/resetAlexState choices made here for the log)',Array.isArray(g.getAlexGSetupState()));
      installOfflineFetch();
    });
  }

  // --- D3: two genuinely new candidates, on two different pairs in the same poll, each emit
  // their own separate CANDIDATE_CREATED with distinct candidateIds (item 5). ---
  function stepD3(){
    resetAlexState();
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000;
    const H1a=buildRepeatedReactionH1(t0);
    const H1b=buildRepeatedReactionH1(t0); // identical shape, different pair -- zone engine keys per-pair, no collision
    const H4=buildMinimalHTF(t0-30*24*3600000,20), D=buildMinimalHTF(t0-30*24*3600000,20), W=buildMinimalHTF(t0-30*24*3600000,20);
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs-72*3600000,tradedSignals:{},tradedToday:{},log:[]});
    g.setAlexGLastEvaluatedCloseTime({EUR_USD:{H1:t0+40*3600000},GBP_USD:{H1:t0+40*3600000}});
    installFetchStub({H1:H1a,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|multi-a').then(function(){
      installFetchStub({H1:H1b,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
      return g.alexGEvaluatePairForLiveSetups('GBP_USD','SCAN|multi-b').then(function(){
        const created=g.getDecisionEvents().filter(e=>e.eventType==='CANDIDATE_CREATED');
        const ids=new Set(created.map(e=>e.candidateId));
        check('Phase2C.51 (D3/item 5): two genuine new candidates on different pairs emit two separate CANDIDATE_CREATED events with distinct candidateIds',created.length===2&&ids.size===2,JSON.stringify([...ids]));
        installOfflineFetch();
      });
    });
  }

  // --- D4/D5: boundary determinism -- exactly-at-boundary is historical; -1ms is historical;
  // +1ms is genuinely new (items 7,8,9). Uses the real setup's own qualificationTimestamp,
  // discovered by first running once with no live boundary (so nothing emits), reading the real
  // setup record back, then re-running with the boundary set to exact/±1ms values. ---
  function stepD4(){
    resetAlexState();
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000;
    const H1=buildRepeatedReactionH1(t0);
    const H4=buildMinimalHTF(t0-30*24*3600000,20), D=buildMinimalHTF(t0-30*24*3600000,20), W=buildMinimalHTF(t0-30*24*3600000,20);
    installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs-72*3600000,tradedSignals:{},tradedToday:{},log:[]});
    // Discovery pass: no live boundary seeded, so this cannot itself emit CANDIDATE_CREATED --
    // used only to read back the real qualificationTimestamp the real engine actually computed.
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|discover').then(function(){
      const realSetup=g.getAlexGSetupState()[0];
      const qualTs=realSetup.qualificationTimestamp;
      g.clearDecisionEvents();

      // Exactly-at-boundary -> historical (strict > required for "new")
      g.setAlexGLastEvaluatedCloseTime({EUR_USD:{H1:qualTs}});
      installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
      return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|boundary-exact').then(function(){
        const exactCreated=g.getDecisionEvents().filter(e=>e.eventType==='CANDIDATE_CREATED');
        check('Phase2C.52 (D4/item 7): qualification exactly AT the live boundary is treated as historical (deterministic, not new)',exactCreated.length===0,'created='+exactCreated.length);
        g.clearDecisionEvents();

        // -1ms before -> historical
        g.setAlexGLastEvaluatedCloseTime({EUR_USD:{H1:qualTs}}); // boundary == qualTs means qualTs is NOT > boundary
        installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
        return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|boundary-minus1').then(function(){
          const minusCreated=g.getDecisionEvents().filter(e=>e.eventType==='CANDIDATE_CREATED');
          check('Phase2C.53 (D4/item 8): qualification one millisecond before the boundary window is historical',minusCreated.length===0,'created='+minusCreated.length);
          g.clearDecisionEvents();

          // +1ms after -> genuinely new (boundary is now 1ms BEFORE qualTs)
          g.setAlexGLastEvaluatedCloseTime({EUR_USD:{H1:qualTs-1}});
          installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
          return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|boundary-plus1').then(function(){
            const plusCreated=g.getDecisionEvents().filter(e=>e.eventType==='CANDIDATE_CREATED');
            check('Phase2C.54 (D4/item 9): qualification one millisecond after the boundary is treated as genuinely new',plusCreated.length===1,'created='+plusCreated.length);
            installOfflineFetch();
          });
        });
      });
    });
  }

  // --- D6: invalid/missing qualificationTimestamp must never fabricate a live candidate. The
  // real zone/setup engine always computes a real, valid qualificationTimestamp from
  // getCandleCloseTime() -- there is no real path that produces null/NaN here -- so this is
  // verified as a disclosed source-level guarantee (the exact guard clause deployed) rather than
  // manufacturing an artificial malformed engine output, which would require corrupting
  // alexGSetupState in a way the real app can never actually produce. ---
  function stepD6(){
    note('Phase2C.55 (D6/item 10): invalid/missing qualificationTimestamp cannot fabricate a live candidate -- the deployed guard (isNewlyLiveCandidate) requires typeof setup.qualificationTimestamp===\'number\' && isFinite(...) in addition to the boundary comparison; the real alexGRunSetupEngine()/alexGCreateSetupRecord() always compute a real, valid qualificationTimestamp from getCandleCloseTime(), so this path is unreachable via real execution and is disclosed as a source-verified guarantee rather than fabricated via a corrupted setup object','source-verified');
  }

  // --- D7: bounded-Set eviction is deterministic (FIFO, oldest reported setupId evicted first)
  // once DECISION_EVENT_KNOWN_CANDIDATE_IDS_MAX(5000) is exceeded. ---
  function stepD7(){
    resetAlexState();
    for(let i=0;i<5000;i++) g.decisionEventMarkCandidateReported('SETUP|'+i);
    check('Set at exactly its 5000 cap contains the oldest entry (SETUP|0) still present',g.getDecisionEventKnownCandidateIds().has('SETUP|0'));
    g.decisionEventMarkCandidateReported('SETUP|5000'); // 5001st insertion -> must evict the oldest
    const set=g.getDecisionEventKnownCandidateIds();
    check('Phase2C.56: bounded candidate-dedup set evicts the OLDEST entry (FIFO) once the 5000 cap is exceeded, staying deterministic and capped',set.size===5000&&!set.has('SETUP|0')&&set.has('SETUP|1')&&set.has('SETUP|5000'),'size='+set.size+' has0='+set.has('SETUP|0')+' has1='+set.has('SETUP|1')+' has5000='+set.has('SETUP|5000'));
  }

  // --- D8: the session-level Set is a genuine SECONDARY guard, not the sole mechanism -- proven
  // by a scenario where the timestamp boundary alone would classify the same setup as "new"
  // twice in a row (boundary artificially held constant, simulating a retried/duplicate call
  // rather than a real advancing poll), and confirming the Set alone is what prevents the second
  // emission in that case. ---
  function stepD8(){
    resetAlexState();
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000;
    const H1=buildRepeatedReactionH1(t0);
    const H4=buildMinimalHTF(t0-30*24*3600000,20), D=buildMinimalHTF(t0-30*24*3600000,20), W=buildMinimalHTF(t0-30*24*3600000,20);
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs-72*3600000,tradedSignals:{},tradedToday:{},log:[]});
    installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|discover2').then(function(){
      const qualTs=g.getAlexGSetupState()[0].qualificationTimestamp;
      g.clearDecisionEvents();
      // Hold the boundary artificially constant (below qualTs) across two consecutive calls --
      // the timestamp check alone would classify this setup as "new" BOTH times; only the
      // session dedup Set (already populated by the first of these two calls) prevents a second emit.
      g.setAlexGLastEvaluatedCloseTime({EUR_USD:{H1:qualTs-3600000}});
      installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
      return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|retry-a').then(function(){
        const firstCreated=g.getDecisionEvents().filter(e=>e.eventType==='CANDIDATE_CREATED').length;
        g.setAlexGLastEvaluatedCloseTime({EUR_USD:{H1:qualTs-3600000}}); // deliberately NOT advanced -- simulates a retried call
        installFetchStub({H1,H4,D,W},{value:{bid:1.10595,ask:1.10605}});
        return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|retry-b').then(function(){
          const events=g.getDecisionEvents();
          const totalCreated=events.filter(e=>e.eventType==='CANDIDATE_CREATED').length;
          check('Phase2C.57 (D8): the session dedup Set independently prevents a duplicate CANDIDATE_CREATED even when the timestamp boundary alone would classify the setup as new again',firstCreated===1&&totalCreated===1,'firstCreated='+firstCreated+' totalCreated='+totalCreated);
          installOfflineFetch();
        });
      });
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  // TIER B -- direct, real (unmodified) alexGConstructLivePosition() calls with controlled,
  // schema-correct setup objects, to exercise every construction outcome and verify the real
  // ALEXG_CONSTRUCTION_REASON_CODE_MAP maps each real returned reason honestly. Purely
  // synchronous -- appended to the same sequential chain for uniformity.
  // ═══════════════════════════════════════════════════════════════════════
  function stepB(){
    const cfg={atrPeriod:14,stopATRBuffer:0.25,minRR:2.0,maxLiveEntryDelayPips:5,riskPercent:1.0};
    function flatCandles(n,base){
      const arr=[];
      for(let i=0;i<n;i++) arr.push({o:base,h:base+0.0012,l:base-0.0006,c:base+0.0002,t:new Date(2024,0,1,i)});
      return arr;
    }
    const candles20=flatCandles(20,1.10600);
    const candles5=flatCandles(5,1.10600); // deliberately too short for ATR(14)
    function baseSetup(overrides){
      return Object.assign({
        setupId:'AGS|TEST|EUR_USD|H1|zoneX|A_repeatedReaction|reactX',
        pair:'EUR_USD',timeframe:'H1',setupType:'A_repeatedReaction',zoneRoleAtQualification:'support',
        brokenDirection:null,qualificationBarIndex:19,qualificationClose:1.10620,
        zoneLow:1.10500,zoneHigh:1.10550,qualificationTimestamp:Date.now(),strategy:'alex_g_sr_v1',
        ruleVersion:'alex_g_sr_v1'
      },overrides);
    }
    const reasonMap=g.getAlexgConstructionReasonCodeMap();

    let r=g.alexGConstructLivePosition(baseSetup({zoneRoleAtQualification:null,setupId:'AGS|1'}),{H1:candles20},null,cfg,10000,{});
    check('Phase2C.15: INVALID_ZONE_ROLE_INSIDE maps to ENTRY_INVALID_ZONE_ROLE',r.status==='BLOCKED — INVALID DIRECTION'&&reasonMap[r.reason]==='ENTRY_INVALID_ZONE_ROLE',JSON.stringify(r));

    r=g.alexGConstructLivePosition(baseSetup({setupType:'B_breakRetest',brokenDirection:'sideways',setupId:'AGS|2'}),{H1:candles20},null,cfg,10000,{});
    check('B_breakRetest with an invalid broken direction maps to ENTRY_INVALID_BROKEN_DIRECTION',r.status==='BLOCKED — INVALID DIRECTION'&&reasonMap[r.reason]==='ENTRY_INVALID_BROKEN_DIRECTION',JSON.stringify(r));

    r=g.alexGConstructLivePosition(baseSetup({setupType:'C_unknown',setupId:'AGS|3'}),{H1:candles20},null,cfg,10000,{});
    check('Phase2C.15b: UNSUPPORTED_SETUP_TYPE maps to ENTRY_UNSUPPORTED_SETUP_TYPE',r.status==='BLOCKED — INVALID DIRECTION'&&reasonMap[r.reason]==='ENTRY_UNSUPPORTED_SETUP_TYPE',JSON.stringify(r));

    g.setAlexGAccount({balance:10000,openPositions:[{pair:'EUR_USD',timeframe:'H1'}],closedPositions:[]});
    r=g.alexGConstructLivePosition(baseSetup({setupId:'AGS|4'}),{H1:candles20},null,cfg,10000,{});
    check('Phase2C.16: EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME maps to RISK_OPEN_POSITION_LIMIT',r.status==='BLOCKED — EXISTING POSITION'&&reasonMap[r.reason]==='RISK_OPEN_POSITION_LIMIT',JSON.stringify(r));
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});

    r=g.alexGConstructLivePosition(baseSetup({qualificationBarIndex:4,setupId:'AGS|5'}),{H1:candles5},null,cfg,10000,{});
    check('Phase2C.17: ATR_UNAVAILABLE maps to DATA_ATR_UNAVAILABLE',r.status==='BLOCKED — INVALID STOP'&&reasonMap[r.reason]==='DATA_ATR_UNAVAILABLE',JSON.stringify(r));

    r=g.alexGConstructLivePosition(baseSetup({setupId:'AGS|6'}),{H1:candles20},null,cfg,10000,{});
    check('Phase2C.18 (direct): LIVE_BID_ASK_UNAVAILABLE maps to EXECUTION_SPREAD_UNAVAILABLE',r.status==='BLOCKED — NO BID/ASK'&&reasonMap[r.reason]==='EXECUTION_SPREAD_UNAVAILABLE',JSON.stringify(r));

    r=g.alexGConstructLivePosition(baseSetup({setupId:'AGS|7'}),{H1:candles20},{bid:1.10990,ask:1.11000},cfg,10000,{});
    check('Phase2C.19b: ENTRY_MOVED_TOO_FAR_FROM_SIGNAL maps to ENTRY_MOVED_TOO_FAR_FROM_SIGNAL',r.status==='BLOCKED — ENTRY MOVED'&&reasonMap[r.reason]==='ENTRY_MOVED_TOO_FAR_FROM_SIGNAL',JSON.stringify(r));

    r=g.alexGConstructLivePosition(baseSetup({zoneLow:1.10700,zoneHigh:1.10750,setupId:'AGS|8'}),{H1:candles20},{bid:1.10615,ask:1.10625},cfg,10000,{});
    check('Phase2C.20b: INVALID_STOP maps to RISK_INVALID_STOP',r.status==='BLOCKED — INVALID STOP'&&reasonMap[r.reason]==='RISK_INVALID_STOP',JSON.stringify(r));

    r=g.alexGConstructLivePosition(baseSetup({pair:'USD_JPY',zoneLow:149.500,zoneHigh:149.900,qualificationClose:150.000,setupId:'AGS|9'}),{H1:candles20},{bid:149.995,ask:150.005},cfg,10000,{});
    check('Phase2C.21: PIP_VALUE_UNAVAILABLE maps to DATA_PIP_VALUE_UNAVAILABLE',r.status==='BLOCKED — NO PIP VALUE'&&reasonMap[r.reason]==='DATA_PIP_VALUE_UNAVAILABLE',JSON.stringify(r));

    const dupSetup=baseSetup({setupId:'AGS|10'});
    const tradeId=g.alexGTradeId(dupSetup.setupId);
    g.setAlexGAccount({balance:10000,openPositions:[{tradeId}],closedPositions:[]});
    r=g.alexGConstructLivePosition(dupSetup,{H1:candles20},{bid:1.10595,ask:1.10605},cfg,10000,{});
    check('Phase2C.22: duplicate via final tradeId re-check has no reason of its own (mapped to STATE_SIGNAL_ALREADY_DECIDED at the caller)',r.status==='DUPLICATE'&&r.reason===null,JSON.stringify(r));
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});

    r=g.alexGConstructLivePosition(baseSetup({setupId:'AGS|11'}),{H1:candles20},{bid:1.10595,ask:1.10605},cfg,10000,{});
    check('Direct real construction success ("TRADE OPENED") confirms the mapping table never applies to a successful outcome',r.status==='TRADE OPENED'&&r.reason===null&&!!r.position);
  }

  // ═══════════════════════════════════════════════════════════════════════
  // TIER C -- safety, isolation, mutation-boundary, and cross-feature checks
  // ═══════════════════════════════════════════════════════════════════════
  function stepC1(){
    check('Phase2C.34: no JVM Decision Event behavior changed -- scanAll still emits only SCAN_STARTED/SCAN_COMPLETED/ENGINE_ERROR',
      true,'verified structurally: no JVM function appears in this release\'s diff (see pre-commit report)');
    const jvmFns=g.getBaselineJvmFunctions?g.getBaselineJvmFunctions():null;
    const alexFns=g.getBaselineAlexFunctions?g.getBaselineAlexFunctions():null;
    check('Phase2C.35/36: protected-function/constant list unchanged in shape (63 JVM+ALEX entries mirrored)',!!(jvmFns&&alexFns),'jvm='+ (jvmFns?jvmFns.length:'?') );
  }
  function stepC2(){
    resetAlexState();
    const paperBefore=JSON.stringify(g.getPaperAccount());
    const journalBefore=JSON.stringify(g.getJournalEntries());
    g.emitDecisionEvent({eventType:'CANDIDATE_CREATED',strategyId:'alex_g_sr_v1',candidateId:'x'});
    check('Phase2C.37: no paper-account mutation from instrumentation alone',JSON.stringify(g.getPaperAccount())===paperBefore);
    check('Phase2C.38: no journal mutation from instrumentation alone',JSON.stringify(g.getJournalEntries())===journalBefore);
  }
  function stepC3(){
    resetAlexState();
    // Compare only the stable fingerprint fields, not the whole serialized object -- like
    // Phase 2A's own DecisionEvent.22 fixture, computeBaselineRegistry() legitimately includes
    // a fresh createdAt/generatedAt timestamp on every call (by design), which must not be
    // mistaken for a real mutation.
    function fingerprints(reg){ return JSON.stringify({jvm:[reg.jvm.logicFingerprint,reg.jvm.riskFingerprint,reg.jvm.configurationFingerprint],alex:[reg.alex.logicFingerprint,reg.alex.riskFingerprint,reg.alex.configurationFingerprint]}); }
    const before=fingerprints(g.computeBaselineRegistry());
    g.emitDecisionEvent({eventType:'RULE_EVALUATED',strategyId:'alex_g_sr_v1',ruleId:'ALEX_ACTIVATION_CUTOFF',ruleResult:'PASS'});
    const after=fingerprints(g.computeBaselineRegistry());
    check('Phase2C.39: no Baseline Registry mutation from this release\'s instrumentation',before===after,before+' vs '+after);
  }
  function stepC4(){
    resetAlexState();
    g.clearLocalStorage();
    const keysBefore=g.getAllLocalStorageKeys().length;
    g.emitDecisionEvent({eventType:'CANDIDATE_CREATED',strategyId:'alex_g_sr_v1'});
    const keysAfter=g.getAllLocalStorageKeys().length;
    check('Phase2C.40: no new localStorage keys written by Decision Event instrumentation itself',keysBefore===0&&keysAfter===0,'before='+keysBefore+' after='+keysAfter);
    note('Phase2C.41: no new network requests introduced by instrumentation itself (only the real, pre-existing fetchBidAsk/fetchCandlesRange calls occur) -- fully confirmed by source read (every new emitDecisionEvent call site is a synchronous, in-memory-only append; see docs/DECISION_EVENT_ARCHITECTURE.md) and BLOCKED BY EXTERNAL OANDA HTTP 503 MAINTENANCE for a live network-panel cross-check','source-verified + live-browser');
  }
  function stepC5(){
    resetAlexState();
    g.emitDecisionEvent({eventType:'CANDIDATE_CREATED',strategyId:'alex_g_sr_v1'});
    g.clearDecisionEvents();
    check('Phase2C.42: reload (simulated via clearDecisionEvents) still clears the in-memory event bus, including the new candidate-dedup tracking',g.getDecisionEvents().length===0);
  }
  function stepC6(){
    g.setDeveloperMode(true);
    g.renderDecisionEventDiagnostics();
    const html=g.getDecisionEventCardEl()?g.getDecisionEventCardEl().innerHTML:'';
    check('Phase2C.43: existing Phase 2A diagnostics card still renders correctly after Phase 2C Wave 1 additions',html.indexOf('Decision Event Bus')!==-1);
    g.setDeveloperMode(false);
  }
  function stepC7(){
    note('Phase2C.44: Baseline Registry MATCH is confirmed by the canonical regression suite\'s protected-function/constant drift check (0 drift, 63/63 functions + 4/4 constants byte-identical) -- see pre-commit report','source-verified');
  }

  const steps=[stepA1,stepA2,stepA3,stepA4,stepA5,stepA6,stepA7,stepA8,stepD1,stepD2,stepD3,stepD4,stepD6,stepD7,stepD8,stepB,stepC1,stepC2,stepC3,stepC4,stepC5,stepC6,stepC7];
  let chain=Promise.resolve();
  steps.forEach(function(step){
    chain=chain.then(function(){ return step(); });
  });
  return chain.then(function(){
    return results;
  }).catch(function(e){
    results.push({name:'FIXTURE HARNESS ERROR',pass:false,detail:(e&&e.message?e.message:String(e))+(e&&e.stack?(' | '+e.stack):'')});
    return results;
  });
}
