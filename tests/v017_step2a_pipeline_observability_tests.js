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
  // §18.33: `m1Exec` serves the EXECUTABLE bid/ask M1 series that alexGFetchExecutableCandles asks
  // for. Its URL shape is `granularity=M1&price=BA&count=5000&from=...` -- a DIFFERENT parameter
  // ORDER from every other candle request in this stub, which is why the existing matcher never saw
  // it and the historical-reconstruction branch could not be driven from here at all. Without this
  // the fetch simply fails and the code falls through to the live-snapshot branch, so a fixture
  // believing it was testing reconstruction was testing the snapshot path a second time.
  function installFetchStub(candlesByGran,bidAskBox,m1Box,m1Exec){
    globalThis.fetch=async function(url){
      const em=url.match(/instruments\/[^/]+\/candles\?granularity=M1&price=BA/);
      if(em){
        if(!m1Exec) return{ok:false};
        return{ok:true,json:async()=>({candles:m1Exec.map(c=>({
          time:new Date(c.t).toISOString(),complete:true,
          bid:{o:String(c.bo),h:String(c.bh),l:String(c.bl),c:String(c.bc)},
          ask:{o:String(c.ao),h:String(c.ah),l:String(c.al),c:String(c.ac)}}))})};
      }
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
    // MOGO-021 DECISIONS 2+3: the decided-authority is session state exactly like the ring, so a
    // scenario that does not clear it inherits the previous scenario's decisions and its setups are
    // correctly refused as already-decided. Cleared through the one primitive that owns both.
    g.resetLiveDecisionState();
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
        // §18.29: the condition was the literal `true` -- the enclosing `if` did all the work, so
        // the record's CONTENT was never checked. A record with the right stage but a null status
        // or a missing tradeId passed. Now the fields are asserted.
        check('2A.19: a rejected ledger commit records REQUEST_FAILED(LEDGER_COMMIT_REJECTED) exactly once, carrying the status and the tradeId of the trade that did not persist',
          commitRejected.length===1
            && commitRejected[0].stage==='REQUEST_FAILED'
            && commitRejected[0].status==='LEDGER_COMMIT_REJECTED'
            && commitRejected[0].tradeId!=null && String(commitRejected[0].tradeId).length>0,
          JSON.stringify({n:commitRejected.length,rec:commitRejected[0]&&{stage:commitRejected[0].stage,status:commitRejected[0].status,tradeId:commitRejected[0].tradeId}}));
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
  // 🔴 ALEXEXIT (§18.33) -- WHAT the ALEX exit actually BOOKS, not merely that it closed
  // ═══════════════════════════════════════════════════════════════════════════════════════
  // Independent adversarial verification found FOURTEEN survivors in one subsystem. Both ALEX exit
  // paths execute during the gate, and the gate observed only THAT a position closed -- never what
  // was booked. Surviving the full 2,280-fixture gate with drift 0: the exit price replaced by the
  // ENTRY or by the constant 1.5 on stop AND on target; the result inverted Loss->Win; the
  // exitTriggerLevel replaced by the target; the exitDetectionSource relabelled; and the SHORT legs
  // of the stop/target comparisons and of the MAE/MFE tracking, in both the snapshot and the
  // historical-reconstruction branch.
  //
  // The controls prove this is a coverage hole and not dead code: deleting both close calls kills 4
  // (2A.29-2A.32), and the JVM twin of the exit-price mutation kills 17. The JVM side is watched;
  // ALEX was not. Every ALEX position is closed by the 60-second poller through one of these two
  // branches, and resultR is plannedRR (+2.0R) for a Win against -1 for a Loss -- so A STOP-OUT
  // RECORDED AS A +2R WINNER SURVIVED THE FULL GATE, moving the balance by an arbitrary amount and
  // corrupting win rate, expectancy and profit factor.
  //
  // Seeded directly rather than opened organically: the point is the arithmetic of the close, and a
  // hand-computed literal is only meaningful against known entry/stop/target/pipValue/size.
  function alexSeedOpen(over){
    const pos=Object.assign({
      tradeId:'ALEXEXIT-1',pair:'EUR_USD',timeframe:'H1',setupLabel:'fixture',direction:'buy',
      entry:1.10000,stop:1.09500,target:1.11000,plannedRR:2,riskAmount:100,positionSize:0.20,
      pipValue:10,openedAt:new Date(Date.now()-3600000).toISOString(),status:'open',
      maePips:0,mfePips:0,maeR:0,mfeR:0
    },over||{});
    g.setAlexGAccount({balance:10000,openPositions:[pos],closedPositions:[],journal:[]});
    return pos;
  }
  // Drives the LIVE-SNAPSHOT branch: the M1 history fetch is made to fail, exactly as P6 does, so
  // the real code falls through to its snapshot check -- a supported branch, not a bypass.
  function alexDriveSnapshotExit(bid,ask){
    const htf=buildMinimalHTF(Date.now()-30*24*3600000,20);
    installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:bid,ask:ask}},{fail:true});
    return g.alexGCheckLivePositions().then(function(){
      installOfflineFetch();
      return g.getAlexGAccount();
    });
  }
  // ── §18.34 F4, DISCLOSED RESIDUAL: the closedPositions half of the ALEX tradeId duplicate
  //    guard is UNWATCHED, and it is NOT redundant. I had assumed it was; independent verification
  //    proved otherwise, and the reason is structural:
  //        tradeId  = AGT|<setupId>
  //        signalId = AGL|<strategy>|<pair>|<tf>|<setupId>|<qualificationTimestamp>
  //    Two signalIds sharing a setupId COLLIDE on tradeId but not on signalId. And the signal-level
  //    closed check is `closedPositions.some(p => p.signalId === signalId)`, which cannot match any
  //    persisted closed position whose signalId is absent or null -- records predating the field,
  //    and normalizers that write `signalId||null`. For those, this half is the ONLY thing stopping
  //    an already-closed trade being re-opened, after which journalNoteCloseAlex -- which finds and
  //    updates BY TRADEID -- overwrites the first trade's journal row.
  //
  //    The production code is CORRECT; only the coverage is missing. A fixture was attempted and
  //    WITHDRAWN rather than shipped green for the wrong reason: driving alexGConstructLivePosition
  //    directly is rejected at an earlier gate ("BLOCKED — INVALID DIRECTION") before the tradeId
  //    guard is reached, and a version asserting only the seeded precondition would have been
  //    asserting my own fixture data back to myself. Reaching this guard needs a fully-qualified
  //    setup with real datasets, direction, AOI and pip value -- which is the work this residual
  //    names. Not papered over.

  function stepAlexExitBuyStop(){
    resetAll();
    alexSeedOpen();
    // BUY stopped out. A buy is closed by SELLING, so the fill is the BID -- never the ask, never
    // the mid. bid 1.09400 is 60 pips below the 1.10000 entry: 60 x $10 x 0.20 = -$120.00.
    return alexDriveSnapshotExit(1.09400,1.09420).then(function(account){
      const c=account.closedPositions[0]||null;
      check('ALEXEXIT.1 (PRECONDITION): the seeded BUY really was closed by the live-snapshot branch',
        !!c && account.openPositions.length===0,
        JSON.stringify({open:account.openPositions.length,closed:account.closedPositions.length}));
      check('ALEXEXIT.2 (FILL SIDE): a BUY is closed at the BID, the executable side -- filling at the ask or the mid overstates every losing exit by the spread',
        !!c && Math.abs(c.exitPrice-1.09400)<1e-9,
        c?('exitPrice='+c.exitPrice+' bid=1.09400 ask=1.09420'):'no closed position');
      check('ALEXEXIT.3 (P&L, hand-computed): 60 pips against a 0.20 position at $10/pip books exactly -$120.00, and the balance moves by exactly that',
        !!c && c.pnl===-120 && account.balance===9880,
        c?('pnl='+c.pnl+' balance='+account.balance):'no closed position');
      check('ALEXEXIT.4 (CLASSIFICATION): the stop-out is recorded as a Loss at exactly -1R -- not as a Win, and not at the planned +2R',
        !!c && c.result==='Loss' && c.resultR===-1,
        c?(c.result+' / '+c.resultR+'R'):'no closed position');
      // The trigger LEVEL is the stop that was breached (1.09500); the FILL is where it actually
      // executed (1.09400). My first draft asserted they were the same and failed honestly -- the
      // code was right. Keeping them distinct is the stronger assertion: collapsing the two would
      // hide slippage entirely, reporting every exit as having filled exactly at its level.
      check('ALEXEXIT.5 (PROVENANCE): the exit is attributed to the live snapshot, and its trigger LEVEL is the stop that was breached -- distinct from the price it actually FILLED at, so slippage stays visible',
        !!c && c.exitDetectionSource==='live_snapshot'
            && Math.abs(c.exitTriggerLevel-1.09500)<1e-9
            && Math.abs(c.exitPrice-1.09400)<1e-9
            && c.exitTriggerLevel!==c.exitPrice,
        c?(c.exitDetectionSource+' level='+c.exitTriggerLevel+' fill='+c.exitPrice):'no closed position');
      // §18.34: FOUR more fields in this same object literal were written and asserted by nothing --
      // balanceAfter, exitBid/exitAsk, exitSpreadPips and exitCandleStart/End all survived the full
      // gate while `pnl`, on the very same line as balanceAfter, kills 15. They are not incidental:
      // evidenceBuildPackageFromTrade copies every one of them into the citable evidence package.
      // balanceAfter is the per-trade equity ledger an operator reconciles against their broker,
      // and exitSpreadPips is the execution-cost figure. Each could be arbitrarily wrong while green.
      check('ALEXEXIT.19 (EVIDENCE FIELDS, equity ledger): the closed record stamps balanceAfter with the account balance AFTER this trade -- 9880.00, not 0 and not the pre-trade balance. This is the per-trade equity trail the evidence package cites',
        !!c && c.balanceAfter===9880 && c.balanceAfter===account.balance,
        c?('balanceAfter='+c.balanceAfter+' accountBalance='+account.balance):'no closed position');
      check('ALEXEXIT.20 (EVIDENCE FIELDS, execution cost): the recorded bid and ask are the snapshot that filled it, and exitSpreadPips is their real distance -- 2.0 pips from 1.09400/1.09420, not 0',
        !!c && Math.abs(c.exitBid-1.09400)<1e-9 && Math.abs(c.exitAsk-1.09420)<1e-9
             && Math.abs(c.exitSpreadPips-2)<1e-6,
        c?('bid='+c.exitBid+' ask='+c.exitAsk+' spreadPips='+c.exitSpreadPips):'no closed position');
      check('ALEXEXIT.21 (EVIDENCE FIELDS, snapshot provenance): a live-snapshot exit carries NO candle window, because no candle detected it -- fabricating one would claim historical evidence that does not exist',
        !!c && c.exitCandleStart===null && c.exitCandleEnd===null && !c.ambiguous,
        c?('candleStart='+c.exitCandleStart+' candleEnd='+c.exitCandleEnd+' ambiguous='+c.ambiguous):'no closed position');
    });
  }
  function stepAlexExitBuyTarget(){
    resetAll();
    alexSeedOpen();
    // BUY target hit. bid 1.11000 is 100 pips above entry: 100 x $10 x 0.20 = +$200.00, and a Win
    // books the FROZEN plannedRR, not a ratio recomputed from the actual fill.
    return alexDriveSnapshotExit(1.11000,1.11020).then(function(account){
      const c=account.closedPositions[0]||null;
      check('ALEXEXIT.6 (BUY target): the winning exit fills at the bid and books exactly +$200.00, leaving the balance at 10200.00',
        !!c && Math.abs(c.exitPrice-1.11000)<1e-9 && c.pnl===200 && account.balance===10200,
        c?('exit='+c.exitPrice+' pnl='+c.pnl+' balance='+account.balance):'no closed position');
      check('ALEXEXIT.7 (BUY target classification): recorded as a Win at the FROZEN planned 2R',
        !!c && c.result==='Win' && c.resultR===2,
        c?(c.result+' / '+c.resultR+'R'):'no closed position');
    });
  }
  function stepAlexExitSellStop(){
    resetAll();
    alexSeedOpen({tradeId:'ALEXEXIT-S',direction:'sell',entry:1.10000,stop:1.10500,target:1.09000});
    // SELL stopped out. A sell is closed by BUYING BACK, so the fill is the ASK. ask 1.10600 is 60
    // pips above the entry, against a short: 60 x $10 x 0.20 = -$120.00.
    // The SHORT legs of the stop/target comparisons were among the survivors, so they get their own
    // fixtures rather than being assumed symmetric with the long side.
    return alexDriveSnapshotExit(1.10580,1.10600).then(function(account){
      const c=account.closedPositions[0]||null;
      check('ALEXEXIT.8 (SELL fill side): a SELL is closed at the ASK, the executable side for buying back',
        !!c && Math.abs(c.exitPrice-1.10600)<1e-9,
        c?('exitPrice='+c.exitPrice+' bid=1.10580 ask=1.10600'):'no closed position');
      check('ALEXEXIT.9 (SELL P&L and classification): 60 pips against the short books exactly -$120.00, a Loss at -1R, balance 9880.00',
        !!c && c.pnl===-120 && c.result==='Loss' && c.resultR===-1 && account.balance===9880,
        c?('pnl='+c.pnl+' '+c.result+' '+c.resultR+'R balance='+account.balance):'no closed position');
    });
  }
  function stepAlexExitSellTarget(){
    resetAll();
    alexSeedOpen({tradeId:'ALEXEXIT-ST',direction:'sell',entry:1.10000,stop:1.10500,target:1.09000});
    // SELL target hit: ask 1.09000 is 100 pips in favour of the short: +$200.00.
    return alexDriveSnapshotExit(1.08980,1.09000).then(function(account){
      const c=account.closedPositions[0]||null;
      check('ALEXEXIT.10 (SELL target): fills at the ask, books exactly +$200.00 and a Win at the frozen 2R, balance 10200.00',
        !!c && Math.abs(c.exitPrice-1.09000)<1e-9 && c.pnl===200 && c.result==='Win' && c.resultR===2 && account.balance===10200,
        c?('exit='+c.exitPrice+' pnl='+c.pnl+' '+c.result+' '+c.resultR+'R balance='+account.balance):'no closed position');
    });
  }
  // ── the HISTORICAL RECONSTRUCTION branch, which nothing could drive until the stub learned the
  //    executable URL shape. This is the branch that exists precisely because a stop touched and
  //    reversed BETWEEN two 60-second polls is invisible to the snapshot check -- so a defect here
  //    means a genuinely stopped-out trade goes on running, or is booked at the wrong level.
  function alexExecBar(tMs,bidLow,bidHigh,askLow,askHigh){
    return{t:tMs,bo:bidLow,bh:bidHigh,bl:bidLow,bc:bidHigh,ao:askLow,ah:askHigh,al:askLow,ac:askHigh};
  }
  function stepAlexExitHistoricalStop(){
    resetAll();
    const pos=alexSeedOpen({tradeId:'ALEXEXIT-H'});
    // The LIVE snapshot is deliberately mid-range -- 1.10200 touches neither level -- so if the
    // historical branch did not run, nothing would close and ALEXEXIT.12 would fail. The M1 history
    // contains one bar whose BID LOW pierces the 1.09500 stop and then recovers.
    const t0=Date.now()-10*60000;
    const bars=[
      alexExecBar(t0,        1.10100,1.10150,1.10120,1.10170),
      alexExecBar(t0+60000,  1.09400,1.10050,1.09420,1.10070),   // pierces the stop, then recovers
      alexExecBar(t0+120000, 1.10000,1.10120,1.10020,1.10140)
    ];
    const htf=buildMinimalHTF(Date.now()-30*24*3600000,20);
    installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:1.10200,ask:1.10220}},null,bars);
    return g.alexGCheckLivePositions().then(function(){
      installOfflineFetch();
      const account=g.getAlexGAccount();
      const c=account.closedPositions[0]||null;
      check('ALEXEXIT.12 (HISTORICAL BRANCH RUNS): a stop touched and REVERSED between two polls is caught from the M1 history -- the live snapshot alone sees only 1.10200, which touches nothing, so nothing would close without this branch',
        !!c && account.openPositions.length===0,
        JSON.stringify({open:account.openPositions.length,closed:account.closedPositions.length}));
      check('ALEXEXIT.13 (HISTORICAL PROVENANCE): the close is attributed to the reconstructed candle, not to the live snapshot -- so an operator reviewing the trade can tell WHICH evidence closed it',
        !!c && c.exitDetectionSource!=='live_snapshot',
        c?('exitDetectionSource='+c.exitDetectionSource):'no closed position');
      check('ALEXEXIT.22 (HISTORICAL EVIDENCE WINDOW): a reconstructed exit records the CANDLE WINDOW that detected it -- the minute bar starting at t0+60000 and ending 60s later. This is the evidence that proves WHEN the stop was touched, and it was written and asserted by nothing',
        !!c && c.exitCandleStart===t0+60000 && c.exitCandleEnd===t0+120000,
        c?('candleStart='+c.exitCandleStart+' expected='+(t0+60000)+' candleEnd='+c.exitCandleEnd+' expected='+(t0+120000)):'no closed position');
      check('ALEXEXIT.14 (HISTORICAL BOOKING): the reconstructed stop books at the STOP LEVEL 1.09500 -- exactly -50 pips, -$100.00 on a 0.20 position at $10/pip -- classified a Loss at -1R, balance 9900.00',
        !!c && Math.abs(c.exitPrice-1.09500)<1e-9 && c.pnl===-100
             && c.result==='Loss' && c.resultR===-1 && account.balance===9900,
        c?('exit='+c.exitPrice+' pnl='+c.pnl+' '+c.result+' '+c.resultR+'R balance='+account.balance):'no closed position');
    });
  }
  function stepAlexExitHistoricalShortStop(){
    resetAll();
    alexSeedOpen({tradeId:'ALEXEXIT-HS',direction:'sell',entry:1.10000,stop:1.10500,target:1.09000});
    // The SHORT leg of the historical stop check. Written because breaking it killed ZERO while
    // breaking the BUY leg killed three -- the same one-quadrant-of-two shape this milestone has
    // now found on the exit boundaries, the stop buffer, the fallback target and the P&L sign.
    // A short is stopped when the ASK rises through the stop, so the piercing bar is an ask HIGH.
    const t0=Date.now()-10*60000;
    const bars=[
      alexExecBar(t0,       1.10100,1.10150,1.10120,1.10170),
      alexExecBar(t0+60000, 1.10050,1.10560,1.10080,1.10600),   // ask high pierces the 1.10500 stop
      alexExecBar(t0+120000,1.10000,1.10120,1.10020,1.10140)
    ];
    const htf=buildMinimalHTF(Date.now()-30*24*3600000,20);
    installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:1.10150,ask:1.10170}},null,bars);
    return g.alexGCheckLivePositions().then(function(){
      installOfflineFetch();
      const account=g.getAlexGAccount();
      const c=account.closedPositions[0]||null;
      check('ALEXEXIT.16 (HISTORICAL, SHORT leg): a SHORT stopped out by a reversing ask spike between polls is caught, booked at the 1.10500 stop for exactly -$100.00, a Loss at -1R, balance 9900.00. Breaking this leg alone killed nothing before',
        !!c && account.openPositions.length===0 && Math.abs(c.exitPrice-1.10500)<1e-9
             && c.pnl===-100 && c.result==='Loss' && c.resultR===-1 && account.balance===9900,
        c?('exit='+c.exitPrice+' pnl='+c.pnl+' '+c.result+' '+c.resultR+'R balance='+account.balance)
         :JSON.stringify({open:account.openPositions.length,closed:account.closedPositions.length}));
    });
  }
  function stepAlexExitHistoricalTargets(){
    // The two historical TARGET legs. Both quadrants of the historical stop check are covered
    // above; these complete the matrix, because breaking the SHORT target leg alone killed nothing.
    resetAll();
    alexSeedOpen({tradeId:'ALEXEXIT-HTB'});
    const t0=Date.now()-10*60000;
    const htf=buildMinimalHTF(Date.now()-30*24*3600000,20);
    // BUY target 1.11000 reached by a bid HIGH, then price falls back so the snapshot sees nothing.
    installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:1.10200,ask:1.10220}},null,[
      alexExecBar(t0,       1.10100,1.10150,1.10120,1.10170),
      alexExecBar(t0+60000, 1.10050,1.11050,1.10070,1.11070),
      alexExecBar(t0+120000,1.10000,1.10120,1.10020,1.10140)
    ]);
    return g.alexGCheckLivePositions().then(function(){
      installOfflineFetch();
      const a1=g.getAlexGAccount(); const c1=a1.closedPositions[0]||null;
      check('ALEXEXIT.17 (HISTORICAL, BUY target): a target touched and reversed between polls books at the 1.11000 target -- +100 pips, +$200.00, a Win at the frozen 2R, balance 10200.00',
        !!c1 && Math.abs(c1.exitPrice-1.11000)<1e-9 && c1.pnl===200 && c1.result==='Win' && c1.resultR===2 && a1.balance===10200,
        c1?('exit='+c1.exitPrice+' pnl='+c1.pnl+' '+c1.result+' '+c1.resultR+'R balance='+a1.balance):'no closed position');
      resetAll();
      alexSeedOpen({tradeId:'ALEXEXIT-HTS',direction:'sell',entry:1.10000,stop:1.10500,target:1.09000});
      // SHORT target 1.09000 reached by an ask LOW.
      installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:1.10150,ask:1.10170}},null,[
        alexExecBar(t0,       1.10100,1.10150,1.10120,1.10170),
        alexExecBar(t0+60000, 1.08940,1.10050,1.08960,1.10070),
        alexExecBar(t0+120000,1.10000,1.10120,1.10020,1.10140)
      ]);
      return g.alexGCheckLivePositions().then(function(){
        installOfflineFetch();
        const a2=g.getAlexGAccount(); const c2=a2.closedPositions[0]||null;
        check('ALEXEXIT.18 (HISTORICAL, SHORT target): the short target leg books at the 1.09000 target -- +100 pips, +$200.00, a Win at the frozen 2R, balance 10200.00. Breaking this leg alone killed nothing before',
          !!c2 && Math.abs(c2.exitPrice-1.09000)<1e-9 && c2.pnl===200 && c2.result==='Win' && c2.resultR===2 && a2.balance===10200,
          c2?('exit='+c2.exitPrice+' pnl='+c2.pnl+' '+c2.result+' '+c2.resultR+'R balance='+a2.balance)
           :JSON.stringify({open:a2.openPositions.length,closed:a2.closedPositions.length}));
      });
    });
  }
  // ── 🔴 §18.36: EXACT-TOUCH boundaries in the HISTORICAL reconstruction, three of four unpinned ──
  // v12.34.0 fixed exactly this class for JVM (JVMEXIT-13/14/15) and F4.11/F4.12 pin it for the
  // ALEX SNAPSHOT path -- but the ALEX HISTORICAL path was never mirrored. Weakening `>=` to `>` on
  // the sell-stop, the buy-target and the sell-target each survived the full gate; only the
  // buy-stop was covered. Reconstruction is the ONLY mechanism that sees a level touched and
  // reversed between two 60-second polls, so a stop touched EXACTLY to the pip during a poll gap
  // (tab throttling, sleep, a dropped connection) does not stop the position out and it runs on
  // with NO BOUND.
  // ── 🔴 §18.38 B1: the ALEX EVIDENCE-CAPTURE seam, previously unwitnessed ────────────────────
  // Making evidenceCaptureClosedTrades `if(true) return;` survived the entire 2,336-fixture gate,
  // while the identical edit to its JVM twin killed three. ALEX is the arm actually running live
  // paper trades, so the audit-capture path this milestone exists to produce could stop emitting
  // packages, silently and for the whole session, with the gate fully green. The most likely
  // production trigger is the in-flight flag latching true on a request that never settles (tab
  // suspension, a versionchange-blocked open) -- there is no watchdog on it.
  //
  // The only thing that DID kill was three source-text fixtures asserting where the seam SITS in
  // the file. That it produces anything was asserted by nothing.
  function stepAlexEvidenceCapture(){
    resetAll();
    alexSeedOpen({tradeId:'ALEXEV-1'});
    const htf=buildMinimalHTF(Date.now()-30*24*3600000,20);
    return g.evidenceListPackages().then(function(before){
      const n0=(before||[]).length;
      // A real ALEX close, driven through the live tick -- which is the ONLY path the seam sits on.
      installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:1.09400,ask:1.09420}},{fail:true});
      return g.alexGCheckLivePositions().then(function(){
        installOfflineFetch();
        // The seam is fire-and-forget, so its write lands after the tick resolves.
        let chain=Promise.resolve();
        for(let i=0;i<200;i++) chain=chain.then(function(){});
        return chain.then(function(){ return g.evidenceListPackages(); }).then(function(after){
          const acct=g.getAlexGAccount();
          const closed=(acct.closedPositions||[])[0]||null;
          check('ALEXEV.0 (PRECONDITION): the ALEX position really closed through the live tick, so the capture assertion below is about a real close',
            !!closed && acct.openPositions.length===0,
            JSON.stringify({open:acct.openPositions.length,closed:acct.closedPositions.length}));
          const mine=(after||[]).filter(function(p){ return p&&String(p.sourceTradeId)===String('ALEXEV-1'); });
          check('ALEXEV.1 (END-TO-END): a real ALEX close produces a durable evidence package filed against its own tradeId. The seam is fire-and-forget, so nothing downstream fails when it stops -- which is precisely why it must be asserted here',
            (after||[]).length===n0+1 && mine.length===1,
            'before='+n0+' after='+((after||[]).length)+' mine='+mine.length+
            ' ids='+JSON.stringify((after||[]).map(function(x){return String(x.sourceTradeId);}).slice(0,5)));
          check('ALEXEV.2 (CONTENT): that package carries the trade\'s own booked exit price and P&L rather than a placeholder',
            mine.length===1 && closed
              && JSON.stringify(mine[0]).indexOf(String(closed.exitPrice))!==-1
              && JSON.stringify(mine[0]).indexOf(String(closed.pnl))!==-1,
            closed?('exit='+closed.exitPrice+' pnl='+closed.pnl):'no closed position');
        });
      });
    });
  }
  function stepAlexExitExactTouch(){
    const t0=Date.now()-10*60000;
    const htf=buildMinimalHTF(Date.now()-30*24*3600000,20);
    // BUY, bid low EXACTLY at the 1.09500 stop.
    resetAll();
    alexSeedOpen({tradeId:'ALEXEXACT-BS'});
    installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:1.10200,ask:1.10220}},null,[
      alexExecBar(t0,1.10100,1.10150,1.10120,1.10170),
      alexExecBar(t0+60000,1.09500,1.10050,1.09520,1.10070),
      alexExecBar(t0+120000,1.10000,1.10120,1.10020,1.10140)
    ]);
    return g.alexGCheckLivePositions().then(function(){
      installOfflineFetch();
      const a=g.getAlexGAccount(), c=a.closedPositions[0]||null;
      check('ALEXEXIT.24 (EXACT TOUCH, buy stop): a bid low EXACTLY at the stop stops the position out. `>=` weakened to `>` leaves it open with no bound',
        !!c && Math.abs(c.exitPrice-1.09500)<1e-9 && c.result==='Loss' && a.openPositions.length===0,
        c?('exit='+c.exitPrice+' '+c.result):JSON.stringify({open:a.openPositions.length}));
      // SELL, ask high EXACTLY at the 1.10500 stop.
      resetAll();
      alexSeedOpen({tradeId:'ALEXEXACT-SS',direction:'sell',entry:1.10000,stop:1.10500,target:1.09000});
      installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:1.10150,ask:1.10170}},null,[
        alexExecBar(t0,1.10100,1.10150,1.10120,1.10170),
        alexExecBar(t0+60000,1.10050,1.10460,1.10080,1.10500),
        alexExecBar(t0+120000,1.10000,1.10120,1.10020,1.10140)
      ]);
      return g.alexGCheckLivePositions().then(function(){
        installOfflineFetch();
        const a2=g.getAlexGAccount(), c2=a2.closedPositions[0]||null;
        check('ALEXEXIT.25 (EXACT TOUCH, sell stop): an ask high EXACTLY at the stop stops the short out',
          !!c2 && Math.abs(c2.exitPrice-1.10500)<1e-9 && c2.result==='Loss' && a2.openPositions.length===0,
          c2?('exit='+c2.exitPrice+' '+c2.result):JSON.stringify({open:a2.openPositions.length}));
        // BUY, bid high EXACTLY at the 1.11000 target.
        resetAll();
        alexSeedOpen({tradeId:'ALEXEXACT-BT'});
        installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:1.10200,ask:1.10220}},null,[
          alexExecBar(t0,1.10100,1.10150,1.10120,1.10170),
          alexExecBar(t0+60000,1.10050,1.11000,1.10070,1.11020),
          alexExecBar(t0+120000,1.10000,1.10120,1.10020,1.10140)
        ]);
        return g.alexGCheckLivePositions().then(function(){
          installOfflineFetch();
          const a3=g.getAlexGAccount(), c3=a3.closedPositions[0]||null;
          check('ALEXEXIT.26 (EXACT TOUCH, buy target): a bid high EXACTLY at the target takes profit -- weakened to `>` the winner is never booked and the trade runs back down',
            !!c3 && Math.abs(c3.exitPrice-1.11000)<1e-9 && c3.result==='Win' && a3.openPositions.length===0,
            c3?('exit='+c3.exitPrice+' '+c3.result):JSON.stringify({open:a3.openPositions.length}));
          // SELL, ask low EXACTLY at the 1.09000 target.
          resetAll();
          alexSeedOpen({tradeId:'ALEXEXACT-ST',direction:'sell',entry:1.10000,stop:1.10500,target:1.09000});
          installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:1.10150,ask:1.10170}},null,[
            alexExecBar(t0,1.10100,1.10150,1.10120,1.10170),
            alexExecBar(t0+60000,1.08980,1.10050,1.09000,1.10070),
            alexExecBar(t0+120000,1.10000,1.10120,1.10020,1.10140)
          ]);
          return g.alexGCheckLivePositions().then(function(){
            installOfflineFetch();
            const a4=g.getAlexGAccount(), c4=a4.closedPositions[0]||null;
            check('ALEXEXIT.27 (EXACT TOUCH, sell target): an ask low EXACTLY at the target takes profit on the short',
              !!c4 && Math.abs(c4.exitPrice-1.09000)<1e-9 && c4.result==='Win' && a4.openPositions.length===0,
              c4?('exit='+c4.exitPrice+' '+c4.result):JSON.stringify({open:a4.openPositions.length}));
          });
        });
      });
    });
  }
  function stepAlexExitShortExcursion(){
    // §18.36: the SHORT-side MAE/MFE in reconstruction was entirely unpinned -- inverting both
    // extremes on the short branch survived, while the same inversion on the long branch kills two.
    // A short that ran to within a pip of its stop would report MAE 0 -- "this trade never went
    // against me" -- the exact opposite of the truth, and grounds for tightening a stop that was in
    // fact nearly hit. These figures reach the closed record, the journal and the evidence package.
    resetAll();
    alexSeedOpen({tradeId:'ALEXEXC-S',direction:'sell',entry:1.10000,stop:1.10500,target:1.09000});
    const t0=Date.now()-10*60000;
    const htf=buildMinimalHTF(Date.now()-30*24*3600000,20);
    installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:1.10150,ask:1.10170}},null,[
      // ask high 1.10400 = 40 pips AGAINST the short; ask low 1.09700 = 30 pips IN FAVOUR.
      alexExecBar(t0+60000,1.09650,1.10380,1.09700,1.10400)
    ]);
    return g.alexGCheckLivePositions().then(function(){
      installOfflineFetch();
      const pos=g.getAlexGAccount().openPositions[0];
      check('ALEXEXIT.28 (SHORT EXCURSION): for a SHORT the adverse extreme is the ask HIGH and the favourable extreme is the ask LOW -- 40 pips MAE and 30 pips MFE here. Inverting them reports a trade that nearly hit its stop as never having gone against you',
        !!pos && Math.abs(pos.maePips-40)<0.001 && Math.abs(pos.mfePips-30)<0.001,
        pos?('maePips='+pos.maePips+' (expect 40) mfePips='+pos.mfePips+' (expect 30)'):'no open position');
      check('ALEXEXIT.29 (SHORT EXCURSION, R multiples): those excursions are expressed against the position\'s own 50-pip risk -- 0.80R adverse and 0.60R favourable',
        !!pos && Math.abs(pos.maeR-0.8)<0.001 && Math.abs(pos.mfeR-0.6)<0.001,
        pos?('maeR='+pos.maeR+' mfeR='+pos.mfeR):'no open position');
    });
  }
  function stepAlexExitHistoricalNoTouch(){
    resetAll();
    alexSeedOpen({tradeId:'ALEXEXIT-HN'});
    // NEGATIVE CONTROL for the historical branch: an M1 history that never reaches either level
    // must close NOTHING, so ALEXEXIT.12-14 cannot pass merely because reconstruction closes
    // whatever it is given.
    const t0=Date.now()-10*60000;
    const bars=[
      alexExecBar(t0,       1.10100,1.10150,1.10120,1.10170),
      alexExecBar(t0+60000, 1.10000,1.10200,1.10020,1.10220)
    ];
    const htf=buildMinimalHTF(Date.now()-30*24*3600000,20);
    installFetchStub({H1:[],H4:htf,D:htf,W:htf},{value:{bid:1.10150,ask:1.10170}},null,bars);
    return g.alexGCheckLivePositions().then(function(){
      installOfflineFetch();
      const account=g.getAlexGAccount();
      check('ALEXEXIT.15 (NEGATIVE CONTROL, historical): an M1 history that never touches the stop or the target closes nothing and books nothing',
        account.openPositions.length===1 && account.closedPositions.length===0 && account.balance===10000,
        JSON.stringify({open:account.openPositions.length,closed:account.closedPositions.length,balance:account.balance}));
      // §18.35: the EXIT CURSOR itself. `pos.lastExitCheckTimestamp = lastProcessedTime` was
      // unwatched -- adding an hour to it survived the full gate, while poisoning the same line
      // with the balance killed 5, so the line demonstrably executes. The cursor never moves
      // backwards, so an hour skipped is an hour NEVER reconstructed: a stop touched and reversed
      // inside it is missed permanently and the position runs past its -1R exit with nothing else
      // to catch it. ALEXEXEC.6 pins the fetcher's forming-bar filter and the pure function pins
      // lastProcessedTime; the CALLER's write of that value into the position was the gap.
      const openPos=account.openPositions[0];
      check('ALEXEXIT.23 (EXIT CURSOR): after a clean reconstruction the position\'s exit cursor advances to the END of the last COMPLETED minute processed -- not beyond it, and never past now. Skipping even one minute leaves a window that is never re-examined',
        !!openPos && openPos.lastExitCheckTimestamp===t0+120000
          && openPos.lastExitCheckTimestamp<=Date.now(),
        openPos?('cursor='+openPos.lastExitCheckTimestamp+' expected='+(t0+120000)+' now='+Date.now()):'no open position');
    });
  }
  function stepAlexExitNoTouch(){
    resetAll();
    alexSeedOpen({tradeId:'ALEXEXIT-N'});
    // NEGATIVE CONTROL. A price strictly between the stop and the target must close nothing --
    // otherwise every assertion above could pass simply because the poller closes unconditionally.
    return alexDriveSnapshotExit(1.10200,1.10220).then(function(account){
      check('ALEXEXIT.11 (NEGATIVE CONTROL): a price between the stop and the target closes NOTHING -- the position stays open, the balance is untouched, and nothing is booked',
        account.openPositions.length===1 && account.closedPositions.length===0 && account.balance===10000,
        JSON.stringify({open:account.openPositions.length,closed:account.closedPositions.length,balance:account.balance}));
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
        // §18.29: this PRECONDITION asserted the literal `true` -- so if no position had ever been
        // opened, 2A.29's "closed" would have passed on an empty account and this line would still
        // have said a real position existed. The position under test is now actually inspected.
        check('2A.28 (PRECONDITION): a real position with a tradeId, a direction and a stop was genuinely opened, so the close assertions below are observing a real close rather than an empty account',
          !!(pos&&pos.tradeId!=null&&(pos.direction==='buy'||pos.direction==='sell')&&typeof pos.stop==='number'),
          JSON.stringify(pos&&{tradeId:pos.tradeId,direction:pos.direction,stop:pos.stop}));
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
    // §18.38: this asserted the HARNESS had no IndexedDB -- a fixture pinning a limitation of the
    // runner rather than a property of the system. That limitation was itself the reason the ALEX
    // evidence-capture seam could not be observed at all, so removing it was the point. The P9
    // header states the real requirement: isolation from genuine forward and research evidence.
    // Asserted the way 2A.44 asserts it for localStorage -- the store is runner-owned and
    // in-memory, so nothing here can reach the operator's real evidence database.
    check('2A.43: the evidence store in this process is a runner-owned in-memory stub, never the operator\'s real IndexedDB -- so no genuine forward or research evidence can be written or read',
      typeof globalThis.indexedDB==='object'&&globalThis.indexedDB!==null
        &&typeof globalThis.indexedDB.__isTestStub==='function'
        &&globalThis.indexedDB.__isTestStub()===true);
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

  // ═══════════════════════════════════════════════════════════════════════════════════════
  // P10 -- MOGO-021: the PIPELINE natural key must identify the INSTRUMENT.
  //
  // The key's identity component is s(sourceTradeId||tradeId||setupId), and not every stage has
  // any of the three. alexGRecordPipelineStage('DATA_INSUFFICIENT',{pair,timeframe,status,reason,
  // occurredAt}) supplies none of them, so the key collapsed to 'PIPE|DATA_INSUFFICIENT||<occurredAt>'
  // -- byte-identical for every instrument. Two pairs failing the H1 history check in the same
  // millisecond therefore produced the same key; the UNIQUE naturalKey index rejected the second,
  // and evidencePutObservation classifies a CONSTRAINT error as {ok:true,duplicate:true}. The
  // observation was dropped silently AND reported as a success.
  //
  // These fixtures are written against evidenceObservationNaturalKey directly rather than through
  // the engine, because the defect is a property of the key function and the collision needs two
  // records sharing an exact millisecond -- which a live-path test could only produce by accident.
  // ═══════════════════════════════════════════════════════════════════════════════════════
  function stepP10(){
    const at='2026-08-14T12:00:00.000Z';
    // The exact shape index.html emits for DATA_INSUFFICIENT: pair + timeframe only, no identity.
    function dataInsufficient(pair){
      return g.evidenceBuildPipelineObservation({stage:'DATA_INSUFFICIENT',pair:pair,timeframe:'H1',
        status:'SKIPPED — INSUFFICIENT MARKET DATA',reason:'DATA_INSUFFICIENT_HISTORY',occurredAt:at});
    }
    const eur=dataInsufficient('EUR_USD'), gbp=dataInsufficient('GBP_USD');
    const kEur=g.evidenceObservationNaturalKey(eur), kGbp=g.evidenceObservationNaturalKey(gbp);

    // THE REGRESSION PROOF. Reverting the pair/timeframe components makes these two keys identical
    // and this fixture fails.
    check('2A.48: two instruments skipped for insufficient history in the SAME millisecond get DISTINCT natural keys',
      kEur!==kGbp,JSON.stringify({kEur:kEur,kGbp:kGbp}));
    check('2A.49: neither key has an empty identity segment -- the instrument is always named',
      kEur.indexOf('EUR_USD')!==-1&&kGbp.indexOf('GBP_USD')!==-1,JSON.stringify({kEur:kEur,kGbp:kGbp}));

    // FALSE-POSITIVE GUARD. Splitting the key must not stop a GENUINE duplicate from collapsing --
    // that is what the unique index is for, and over-splitting would defeat it.
    check('2A.50: a genuine duplicate (same pair, same stage, same instant) still collapses to one key',
      g.evidenceObservationNaturalKey(dataInsufficient('EUR_USD'))===kEur,kEur);

    // The same instrument observed on two timeframes at one instant is two real observations.
    const h1=g.evidenceBuildPipelineObservation({stage:'DATA_INSUFFICIENT',pair:'EUR_USD',timeframe:'H1',occurredAt:at});
    const h4=g.evidenceBuildPipelineObservation({stage:'DATA_INSUFFICIENT',pair:'EUR_USD',timeframe:'H4',occurredAt:at});
    check('2A.51: the same instrument on two timeframes at one instant is two observations, not one',
      g.evidenceObservationNaturalKey(h1)!==g.evidenceObservationNaturalKey(h4),
      JSON.stringify({h1:g.evidenceObservationNaturalKey(h1),h4:g.evidenceObservationNaturalKey(h4)}));

    // The pre-existing identity component must still do its job for stages that DO carry one.
    const a=g.evidenceBuildPipelineObservation({stage:'OPENED',pair:'EUR_USD',timeframe:'H1',tradeId:'AGT|a',occurredAt:at});
    const b=g.evidenceBuildPipelineObservation({stage:'OPENED',pair:'EUR_USD',timeframe:'H1',tradeId:'AGT|b',occurredAt:at});
    check('2A.52: stages that DO carry a trade identity are still separated by it',
      g.evidenceObservationNaturalKey(a)!==g.evidenceObservationNaturalKey(b),
      JSON.stringify({a:g.evidenceObservationNaturalKey(a),b:g.evidenceObservationNaturalKey(b)}));

    // The key is still a PIPELINE key, and the other three kinds are untouched by this change.
    check('2A.53: the key is still a well-formed PIPE| key and the other kinds are unchanged',
      kEur.indexOf('PIPE|')===0
      &&g.evidenceObservationNaturalKey({kind:'POLL',strategyId:'current_strategy',tickId:'T1'})==='POLL|current_strategy|T1'
      &&g.evidenceObservationNaturalKey({kind:'EVALUATION',signalId:'S1',firstLiveEvaluationTimestamp:7})==='EVAL|S1|7'
      &&g.evidenceObservationNaturalKey({kind:'RETENTION',evictedSeqFrom:1,evictedSeqTo:2})==='RETN|1|2',
      kEur);
    return Promise.resolve();
  }

  const steps=[stepP1,stepP2,stepP3,stepP4,stepP5,stepP6,stepP7,stepP8,stepP9,stepP10,
    // §18.33: the ALEX exit-booking group. Placed last so it cannot disturb the ordering the
    // pipeline fixtures above depend on; each step reseeds the account itself.
    stepAlexEvidenceCapture,stepAlexExitBuyStop,stepAlexExitBuyTarget,stepAlexExitSellStop,stepAlexExitSellTarget,
    stepAlexExitNoTouch,stepAlexExitHistoricalStop,stepAlexExitHistoricalShortStop,
    stepAlexExitHistoricalTargets,stepAlexExitExactTouch,stepAlexExitShortExcursion,
    stepAlexExitHistoricalNoTouch];
  let chain=Promise.resolve();
  steps.forEach(function(step){ chain=chain.then(function(){ return step(); }); });
  return chain.then(function(){ return results; }).catch(function(e){
    results.push({name:'FIXTURE HARNESS ERROR',pass:false,
      detail:(e&&e.message?e.message:String(e))+(e&&e.stack?(' | '+e.stack):'')});
    return results;
  });
}
