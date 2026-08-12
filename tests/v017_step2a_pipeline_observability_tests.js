// MOGO-017 Step 2A — forward PAPER execution observability fixture suite.
//
// WHAT IS UNDER TEST
//
// MOGO-013 built the PIPELINE observation kind (CANDIDATE | REQUESTED | REQUEST_FAILED | OPENED
// | CLOSED) and then wired nothing to it. Step 2A wires the genuine forward execution path to it.
// These fixtures prove the wiring is correct AND, more importantly, that it cannot lie: OPENED is
// unreachable unless a paper position was genuinely created AND its ledger commit genuinely
// succeeded.
//
// HOW IT IS TESTED
//
// Through the REAL, unmodified engine. A synthetic but genuinely valid H1 candle series is run
// through the real alexGRunSetupEngine / alexGClassifyTouch / alexGEvaluateRepeatedReaction chain
// to produce an organic REPEATED ZONE REACTION setup, then the real alexGEvaluatePairForLiveSetups
// and alexGAttemptOpenLivePosition are driven end to end, calling the real PROTECTED
// alexGConstructLivePosition and the real commitAlexGLedger. The network is stubbed at fetch()
// only -- never at any application function, and never at any protected one. The candle builders
// and fetch stub below are the same ones v126_phase2c_wave1_tests.js already uses to reach
// TRADE OPENED, so this suite exercises a path already proven to reach a real successful open.
//
// ISOLATION -- WHY THIS CANNOT CONTAMINATE ANYTHING
//
// This process has no IndexedDB and no real localStorage; both are stubs created by the runner,
// so no evidence package, no observation and no research artifact can be written even in
// principle. The PIPELINE records asserted here are drained straight out of the in-memory buffer:
// evidencePutObservation is never reached, because only alexGLivePollTick's ledger call reaches
// it and this suite never calls that. Nothing here touches the genuine forward campaign, the real
// alexGAccount, Campaign C1, the legacy corpus or the research corpus.
//
// No protected function or protected constant is edited or duplicated anywhere in this file.
// All async scenarios run strictly SEQUENTIALLY, since they share ALEX's real module state.
function runStep2APipelineObservabilityFixtures(g){
  const results=[];
  function check(name,cond,detail){ results.push({name,pass:!!cond,detail:detail||''}); }

  // ── Candle generation, identical in shape to the v126 suite's proven builders ──────────────
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
    for(let i=0;i<n;i++) candles.push({o:1.1,h:1.101,l:1.099,c:1.1005,t:new Date(t0+i*4*3600000)});
    return candles;
  }
  // Network-boundary stub only. The REAL unmodified fetchCandlesRange / fetchBidAsk parse these.
  function installFetchStub(candlesByGran,bidAskBox,m1Box){
    globalThis.fetch=async function(url){
      const cm=url.match(/instruments\/[^/]+\/candles\?count=(\d+)&granularity=(\w+)/);
      if(cm){
        const gran=cm[2];
        if(/&to=/.test(url)) return{ok:true,json:async()=>({candles:[]})};
        if(gran==='M1'&&m1Box&&m1Box.fail) return{ok:false};
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

  function resetAll(){
    g.setAlexGSetupState([]);
    g.setAlexGZoneState({});
    g.setAlexGLastEvaluatedCloseTime({});
    g.setAlexGLiveSetupStatuses([]);
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGJournalEntries([]);
    g.setAlexGAutoTrading({enabled:true,activatedAt:null,tradedSignals:{},tradedToday:{},log:[]});
    g.clearDecisionEvents();
    g.clearLocalStorage();
    g.setAlexGAccountKnownVersion(0);
    g.drainPipeline();                       // start every scenario with an empty buffer
  }
  function stages(list){ return list.map(function(r){return r.stage;}); }

  // Builds the organic, activation-eligible, non-stale scenario that reaches a real open.
  function organicScenario(bidAsk){
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000;      // qualification ~5 min ago: inside the staleness window
    const H1=buildRepeatedReactionH1(t0);
    const htf=buildMinimalHTF(t0-30*24*3600000,20);
    const box={value:bidAsk||{bid:1.10595,ask:1.10605}};
    installFetchStub({H1,H4:htf,D:htf,W:htf},box);
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs-72*3600000,tradedSignals:{},tradedToday:{},log:[]});
    g.setAlexGLastEvaluatedCloseTime({EUR_USD:{H1:t0+40*3600000}});
    return box;
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // P1 -- the full genuine lifecycle: CANDIDATE -> REQUESTED -> OPENED
  // Requirements 1, 2 and 3.
  // ═══════════════════════════════════════════════════════════════════════════════════════
  function stepP1(){
    resetAll();
    organicScenario();
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|2a-p1').then(function(){
      const pipe=g.drainPipeline();
      const pos=g.getAlexGAccount().openPositions[0];

      check('2A.1: the real end-to-end path produced a genuine paper position',
        !!pos&&!!pos.tradeId,JSON.stringify(pos&&{tradeId:pos.tradeId,entry:pos.entry}));
      check('2A.2: PIPELINE progression is exactly CANDIDATE -> REQUESTED -> OPENED',
        JSON.stringify(stages(pipe))===JSON.stringify(['CANDIDATE','REQUESTED','OPENED']),
        JSON.stringify(stages(pipe)));
      check('2A.3: no REQUEST_FAILED is recorded on a successful open',
        pipe.filter(function(r){return r.stage==='REQUEST_FAILED';}).length===0);

      const opened=pipe.filter(function(r){return r.stage==='OPENED';});
      check('2A.4: OPENED carries the REAL tradeId of the position in the account',
        opened.length===1&&!!pos&&opened[0].tradeId===pos.tradeId,
        JSON.stringify({recorded:opened[0]&&opened[0].tradeId,account:pos&&pos.tradeId}));
      check('2A.5: OPENED occurredAt is the position\'s own openedAt, not "now"',
        opened.length===1&&opened[0].occurredAt===pos.openedAt,
        JSON.stringify({occurredAt:opened[0]&&opened[0].occurredAt,openedAt:pos&&pos.openedAt}));

      // Identity linkage: candidate -> request -> open must be joinable.
      const setup=g.getAlexGSetupState()[0];
      const signalIds=new Set(pipe.map(function(r){return r.signalId;}));
      check('2A.6: every stage carries the SAME signalId, so candidate/request/open join up',
        signalIds.size===1&&[...signalIds][0]===g.alexGLiveSignalId(setup),JSON.stringify([...signalIds]));
      check('2A.7: every stage carries the real setupId, linking back to the evaluation record',
        pipe.every(function(r){return r.setupId===setup.setupId;}),JSON.stringify(pipe.map(function(r){return r.setupId;})));
      check('2A.8: every stage is a well-formed PIPELINE observation with a usable natural key',
        pipe.every(function(r){return r.kind==='PIPELINE'&&r.schemaVersion&&r.provenance==='FORWARD_LIVE_OBSERVATION'
          &&typeof g.evidenceObservationNaturalKey(r)==='string'&&g.evidenceObservationNaturalKey(r).indexOf('PIPE|')===0;}),
        JSON.stringify(pipe.map(function(r){return g.evidenceObservationNaturalKey(r);})));
      check('2A.9: the drain emptied the buffer -- nothing can be written twice',
        g.drainPipeline().length===0);
      installOfflineFetch();
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // P2 -- a setup rejected BEFORE the execution path records nothing at all. Requirement 4.
  // ═══════════════════════════════════════════════════════════════════════════════════════
  function stepP2(){
    resetAll();
    const nowMs=Date.now();
    const t0=nowMs-48*3600000-5*60000;
    const H1=buildRepeatedReactionH1(t0);
    const htf=buildMinimalHTF(t0-30*24*3600000,20);
    installFetchStub({H1,H4:htf,D:htf,W:htf},{value:{bid:1.10595,ask:1.10605}});
    // Activated AFTER the setup qualified -> the frozen activation cutoff must ignore it.
    g.setAlexGAutoTrading({enabled:true,activatedAt:nowMs,tradedSignals:{},tradedToday:{},log:[]});
    g.setAlexGLastEvaluatedCloseTime({EUR_USD:{H1:t0+40*3600000}});
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|2a-p2').then(function(){
      const pipe=g.drainPipeline();
      const statuses=g.getAlexGLiveSetupStatuses();
      check('2A.10: the activation cutoff still ignores a pre-activation setup (behaviour unchanged)',
        statuses.length===1&&/BEFORE ACTIVATION/.test(statuses[0].status),JSON.stringify(statuses[0]&&statuses[0].status));
      check('2A.11: a setup rejected before the execution path records NO pipeline stage at all',
        pipe.length===0,JSON.stringify(stages(pipe)));
      check('2A.12: no OPENED is recorded for a non-qualifying setup',
        pipe.filter(function(r){return r.stage==='OPENED';}).length===0);
      check('2A.13: no paper position was created',g.getAlexGAccount().openPositions.length===0);
      installOfflineFetch();
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // P3 -- construction refuses: CANDIDATE -> REQUESTED -> REQUEST_FAILED, never OPENED.
  // Requirement 5.
  // ═══════════════════════════════════════════════════════════════════════════════════════
  function stepP3(){
    resetAll();
    const box=organicScenario();
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|2a-p3-seed').then(function(){
      const setup=g.getAlexGSetupState()[0];
      // Reset decision state so the same real setup can be attempted again, and make the
      // construction fail for a real, named reason: an unusable zone role.
      g.setAlexGLiveSetupStatuses([]);
      g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
      g.setAlexGAutoTrading({enabled:true,activatedAt:Date.now()-72*3600000,tradedSignals:{},tradedToday:{},log:[]});
      g.drainPipeline();
      const broken=Object.assign({},setup,{zoneRoleAtQualification:null});
      return g.alexGAttemptOpenLivePosition(broken,{H1:[]},{},'SCAN|2a-p3').then(function(){
        const pipe=g.drainPipeline();
        check('2A.14: a refused construction records CANDIDATE -> REQUESTED -> REQUEST_FAILED',
          JSON.stringify(stages(pipe))===JSON.stringify(['CANDIDATE','REQUESTED','REQUEST_FAILED']),
          JSON.stringify(stages(pipe)));
        check('2A.15: a refused construction records NO OPENED',
          pipe.filter(function(r){return r.stage==='OPENED';}).length===0);
        const failed=pipe.filter(function(r){return r.stage==='REQUEST_FAILED';})[0];
        check('2A.16: REQUEST_FAILED carries the protected constructor\'s OWN status, not a re-derived one',
          !!failed&&failed.status==='BLOCKED — INVALID DIRECTION',JSON.stringify(failed&&{status:failed.status,reason:failed.reason}));
        check('2A.17: REQUEST_FAILED carries the constructor\'s own reason',
          !!failed&&typeof failed.reason==='string'&&failed.reason.length>0,JSON.stringify(failed&&failed.reason));
        check('2A.18: no paper position exists after a refused construction',
          g.getAlexGAccount().openPositions.length===0);
        installOfflineFetch();
        void box;
      });
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // P4 -- the position was CONSTRUCTED but the ledger commit was REJECTED. This is the
  // scenario that decides whether OPENED can lie. Requirement 5, and the reason OPENED sits
  // after commitAlexGLedger rather than after construction.
  // ═══════════════════════════════════════════════════════════════════════════════════════
  function stepP4(){
    resetAll();
    organicScenario();
    // A stale known-version makes the real commitAlexGLedger reject the write, exactly as a
    // second browser tab would. No production function is stubbed.
    g.setAlexGAccountKnownVersion(-1);
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|2a-p4').then(function(){
      const pipe=g.drainPipeline();
      const account=g.getAlexGAccount();
      const commitRejected=pipe.filter(function(r){return r.stage==='REQUEST_FAILED'&&r.status==='LEDGER_COMMIT_REJECTED';});
      if(commitRejected.length){
        check('2A.19: a rejected ledger commit records REQUEST_FAILED(LEDGER_COMMIT_REJECTED)',true,
          JSON.stringify(commitRejected[0]&&{status:commitRejected[0].status,tradeId:commitRejected[0].tradeId}));
        check('2A.20: a rejected ledger commit records NO OPENED -- a trade that did not persist is not open',
          pipe.filter(function(r){return r.stage==='OPENED';}).length===0,JSON.stringify(stages(pipe)));
        check('2A.21: the account was rolled back -- no phantom open position',
          account.openPositions.length===0,JSON.stringify(account.openPositions.map(function(p){return p.tradeId;})));
        check('2A.22: the rejected-commit record still carries the constructed tradeId for traceability',
          !!commitRejected[0].tradeId);
      } else {
        // The commit succeeded, so this environment could not exercise the rejection branch.
        // Report that honestly rather than asserting a scenario that did not occur.
        check('2A.19: a rejected ledger commit records REQUEST_FAILED(LEDGER_COMMIT_REJECTED)',false,
          'commit was not rejected in this harness; stages='+JSON.stringify(stages(pipe)));
        check('2A.20: a rejected ledger commit records NO OPENED -- a trade that did not persist is not open',false,'not exercised');
        check('2A.21: the account was rolled back -- no phantom open position',false,'not exercised');
        check('2A.22: the rejected-commit record still carries the constructed tradeId for traceability',false,'not exercised');
      }
      installOfflineFetch();
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // P5 -- duplicate signal. Requirement 6.
  // ═══════════════════════════════════════════════════════════════════════════════════════
  function stepP5(){
    resetAll();
    organicScenario();
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|2a-p5a').then(function(){
      const first=g.drainPipeline();
      const setup=g.getAlexGSetupState()[0];
      check('2A.23: the first attempt opened and recorded OPENED',
        first.filter(function(r){return r.stage==='OPENED';}).length===1,JSON.stringify(stages(first)));
      // Attempt the SAME signal again. The protected constructor's own duplicate guard applies.
      return g.alexGAttemptOpenLivePosition(setup,{H1:[]},{},'SCAN|2a-p5b').then(function(){
        const second=g.drainPipeline();
        check('2A.24: a duplicate signal records CANDIDATE -> REQUESTED -> REQUEST_FAILED',
          JSON.stringify(stages(second))===JSON.stringify(['CANDIDATE','REQUESTED','REQUEST_FAILED']),
          JSON.stringify(stages(second)));
        check('2A.25: a duplicate signal records NO second OPENED',
          second.filter(function(r){return r.stage==='OPENED';}).length===0);
        check('2A.26: the duplicate stage records the constructor\'s DUPLICATE status verbatim',
          second.filter(function(r){return r.stage==='REQUEST_FAILED'&&r.status==='DUPLICATE';}).length===1,
          JSON.stringify(second.map(function(r){return r.status;})));
        check('2A.27: still exactly one open position -- no duplicate paper trade',
          g.getAlexGAccount().openPositions.length===1);
        installOfflineFetch();
      });
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // P6 -- CLOSED, through the real protected alexGCloseLivePosition.
  // ═══════════════════════════════════════════════════════════════════════════════════════
  function stepP6(){
    resetAll();
    const box=organicScenario();
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|2a-p6').then(function(){
      const pos=g.getAlexGAccount().openPositions[0];
      if(!pos){ check('2A.28: a real position was opened to close',false,'no position'); installOfflineFetch(); return; }
      g.drainPipeline();
      // Drive price through the stop. M1 history fetch is made to fail so the real code falls
      // through to its live-snapshot check -- a real, supported branch, not a bypass.
      const htf=buildMinimalHTF(Date.now()-30*24*3600000,20);
      const beyondStop=pos.direction==='buy'?(pos.stop-0.00050):(pos.stop+0.00050);
      installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:beyondStop,ask:beyondStop+0.00010}},{fail:true});
      return g.alexGCheckLivePositions().then(function(){
        const pipe=g.drainPipeline();
        const closedRec=pipe.filter(function(r){return r.stage==='CLOSED';});
        const account=g.getAlexGAccount();
        check('2A.28: a real position was opened to close',true);
        check('2A.29: the real protected close path closed the position',
          account.openPositions.length===0&&account.closedPositions.length===1,
          JSON.stringify({open:account.openPositions.length,closed:account.closedPositions.length}));
        check('2A.30: closing records exactly one CLOSED stage',closedRec.length===1,JSON.stringify(stages(pipe)));
        check('2A.31: CLOSED carries the real tradeId of the closed position',
          closedRec.length===1&&closedRec[0].tradeId===account.closedPositions[0].tradeId,
          JSON.stringify({recorded:closedRec[0]&&closedRec[0].tradeId,account:account.closedPositions[0]&&account.closedPositions[0].tradeId}));
        check('2A.32: CLOSED occurredAt is the position\'s own closedAt, so its natural key is stable',
          closedRec.length===1&&closedRec[0].occurredAt===account.closedPositions[0].closedAt);
        // Idempotence: a second monitoring pass over an already-closed position must add nothing.
        return g.alexGCheckLivePositions().then(function(){
          check('2A.33: a later monitoring pass records no further CLOSED for an already-closed trade',
            g.drainPipeline().filter(function(r){return r.stage==='CLOSED';}).length===0);
          installOfflineFetch();
          void box;
        });
      });
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // P7 -- instrumentation failure cannot alter a trading decision. Requirement 7.
  // ═══════════════════════════════════════════════════════════════════════════════════════
  function stepP7(){
    resetAll();
    // Hostile and malformed inputs must never throw out of the recorder.
    let threw=false;
    try{
      g.alexGRecordPipelineStage('CANDIDATE',null);
      g.alexGRecordPipelineStage(null,undefined);
      g.alexGRecordPipelineStage('OPENED',{pair:{},timeframe:[],setupId:0});
      const circular={}; circular.self=circular;
      g.alexGRecordPipelineStage('REQUESTED',circular);
    }catch(e){ threw=true; }
    check('2A.34: the recorder is total -- malformed, null and circular input never throws',!threw);
    g.drainPipeline();

    // The buffer is capped, and reaching the cap must not disturb trading.
    g.fillPipelineBufferToCap();
    check('2A.35: the buffer is capped so a tick that never drains cannot grow without bound',
      g.pipelineBufferLength()===g.getPipelineBufferMax(),String(g.pipelineBufferLength()));
    organicScenario();
    return g.alexGEvaluatePairForLiveSetups('EUR_USD','SCAN|2a-p7').then(function(){
      const account=g.getAlexGAccount();
      check('2A.36: with the observation buffer full, the REAL trade still opens normally',
        account.openPositions.length===1&&!!account.openPositions[0].tradeId,
        JSON.stringify({open:account.openPositions.length}));
      check('2A.37: a dropped observation is silent to the trading path and never throws',
        g.pipelineBufferLength()===g.getPipelineBufferMax());
      g.drainPipeline();
      check('2A.38: draining restores the buffer to empty',g.pipelineBufferLength()===0);
      installOfflineFetch();
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // P8 -- protected behaviour unchanged, and instrumentation lives outside it. Requirement 8.
  // ═══════════════════════════════════════════════════════════════════════════════════════
  function stepP8(){
    resetAll();
    const cfg={atrPeriod:14,stopATRBuffer:0.25,minRR:2.0,maxLiveEntryDelayPips:5,riskPercent:1.0};
    function flatCandles(n,base){
      const arr=[];
      for(let i=0;i<n;i++) arr.push({o:base,h:base+0.0012,l:base-0.0006,c:base+0.0002,t:new Date(2024,0,1,i)});
      return arr;
    }
    const candles20=flatCandles(20,1.10600);
    const setup={
      setupId:'AGS|2A|EUR_USD|H1|zoneX|A_repeatedReaction|reactX',
      pair:'EUR_USD',timeframe:'H1',setupType:'A_repeatedReaction',zoneRoleAtQualification:'support',
      brokenDirection:null,qualificationBarIndex:19,qualificationClose:1.10620,
      zoneLow:1.10500,zoneHigh:1.10550,qualificationTimestamp:Date.now(),strategy:'alex_g_sr_v1',
      ruleVersion:'alex_g_sr_v1'
    };
    g.drainPipeline();
    const r=g.alexGConstructLivePosition(setup,{H1:candles20},{bid:1.10595,ask:1.10605},cfg,10000,{});
    check('2A.39: the protected constructor still returns TRADE OPENED for a qualifying setup',
      r.status==='TRADE OPENED'&&r.reason===null&&!!r.position,JSON.stringify({status:r.status,reason:r.reason}));
    check('2A.40: calling the PROTECTED constructor directly records NOTHING -- the instrumentation is outside it',
      g.pipelineBufferLength()===0,String(g.pipelineBufferLength()));

    const blocked=g.alexGConstructLivePosition(Object.assign({},setup,{zoneRoleAtQualification:null,setupId:'AGS|2A|b'}),
      {H1:candles20},{bid:1.10595,ask:1.10605},cfg,10000,{});
    check('2A.41: the protected constructor still returns its own named refusals unchanged',
      blocked.status==='BLOCKED — INVALID DIRECTION'&&typeof blocked.reason==='string');
    check('2A.42: a refused protected call also records nothing by itself',g.pipelineBufferLength()===0);
    return Promise.resolve();
  }

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // P9 -- isolation from genuine forward and research evidence. Requirements 9 and 10.
  // ═══════════════════════════════════════════════════════════════════════════════════════
  function stepP9(){
    check('2A.43: this process has no IndexedDB, so no observation or evidence package can be written',
      typeof globalThis.indexedDB==='undefined');
    check('2A.44: localStorage is a runner-owned stub, never the operator\'s real browser storage',
      typeof globalThis.localStorage.__isTestStub==='function'&&globalThis.localStorage.__isTestStub()===true);
    check('2A.45: the durable observation writer was never reached -- records were drained from memory only',
      g.getObservationWriteAttempts()===0,String(g.getObservationWriteAttempts()));
    check('2A.46: PIPELINE remains one of the four declared observation kinds -- no new kind invented',
      JSON.stringify(g.getObservationKinds())===JSON.stringify(['POLL','EVALUATION','PIPELINE','RETENTION']),
      JSON.stringify(g.getObservationKinds()));
    check('2A.47: no new stage vocabulary was invented -- every stage used is one the builder already documented',
      ['CANDIDATE','REQUESTED','REQUEST_FAILED','OPENED','CLOSED'].every(function(s){
        const rec=g.evidenceBuildPipelineObservation({stage:s,setupId:'X'});
        return rec.kind==='PIPELINE'&&rec.stage===s;
      }));
    return Promise.resolve();
  }

  const steps=[stepP1,stepP2,stepP3,stepP4,stepP5,stepP6,stepP7,stepP8,stepP9];
  let chain=Promise.resolve();
  steps.forEach(function(step){ chain=chain.then(function(){ return step(); }); });
  return chain.then(function(){ return results; }).catch(function(e){
    results.push({name:'FIXTURE HARNESS ERROR',pass:false,
      detail:(e&&e.message?e.message:String(e))+(e&&e.stack?(' | '+e.stack):'')});
    return results;
  });
}
