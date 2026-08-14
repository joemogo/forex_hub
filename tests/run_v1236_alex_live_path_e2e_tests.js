// MOGO-021 — ALEX outermost live path: end-to-end paper execution, restart/recovery, persistence.
//
// WHAT WAS ALREADY COVERED, AND WHAT WAS NOT
// tests/v126_phase2c_wave1_tests.js already proves ALEX's full candidate lifecycle end-to-end and
// opens a REAL paper position -- but it enters at alexGEvaluatePairForLiveSetups(). Nothing drove
// alexGLivePollTick(), the actual production entry point, all the way to an opened position. That
// is where the cursor gate, the 12-instrument loop, position monitoring and the durable
// observation ledger all interact with trade opening, and it was untested as a whole.
//
// Two further MOGO-021 areas had no coverage at all:
//   * RESTART/RECOVERY -- alexGLiveSetupStatuses and alexGLastEvaluatedCloseTime are session-only
//     (cleared by a page reload) while alexGAutoTrading.tradedSignals is persisted. The safety
//     property that matters is that a restart cannot re-open a trade that already happened.
//   * The documented consequence that a restart re-evaluates the historical backlog and records
//     it IGNORED — STALE SIGNAL rather than back-filling trades.
//
// EVIDENCE CLASS: DETERMINISTIC GOVERNED SIMULATION, NOT LIVE-FORWARD EVIDENCE.
// The H1 series is constructed so the FROZEN, unmodified zone/setup engine qualifies a genuine
// REPEATED ZONE REACTION (the same construction tests/v126 already validated -- four real swing-low
// touches). No rule, threshold or weight is altered; the only seam is globalThis.fetch, served in
// OANDA's own response shapes so the real fetchCandlesRange/fetchBidAsk parse real data. The
// candles are constructed; every verdict is the strategy's own.
//
// PROTECTED FUNCTIONS ARE CALLED, NEVER MODIFIED: alexGRunSetupEngine, alexGConstructLivePosition,
// alexGRecordLiveSetupStatus, alexGLiveSignalId, alexGIsSetupSignalStale and the zone engine are
// all invoked as-is.
//
// Run from the project root:
//   osascript -l JavaScript tests/run_v1236_alex_live_path_e2e_tests.js
// or simply:  tests/run_all.sh
ObjC.import('Foundation');
function readFile(path){
  const s=$.NSString.stringWithContentsOfFileEncodingError(path,$.NSUTF8StringEncoding,null);
  const v=ObjC.unwrap(s); return v==null?'':v;
}
function extractScriptBody(html){
  const m=html.match(/<script>([\s\S]*)<\/script>/);
  if(!m) throw new Error('Could not find <script>...</script> body in index.html -- run from project root.');
  return m[1];
}
const appCode=extractScriptBody(readFile('./index.html'));

const elMap={};
function makeClassList(){
  const c=new Set();
  return{add:x=>c.add(x),remove:x=>c.delete(x),contains:x=>c.has(x),
    toggle:(x,f)=>{ if(f===undefined){ c.has(x)?c.delete(x):c.add(x); } else if(f) c.add(x); else c.delete(x); }};
}
function makeStub(){
  return {innerHTML:'',textContent:'',value:'',className:'',style:{},options:[{value:'All'}],
    width:100,height:100,disabled:false,checked:false,classList:makeClassList(),
    getContext:()=>({clearRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillRect(){},save(){},restore(){},setLineDash(){},arc(){},fill(){},closePath(){},fillText(){},measureText:()=>({width:0})}),
    appendChild(){},addEventListener(){},focus(){},setSelectionRange(){},click(){},files:[],
    getBoundingClientRect:()=>({top:0,left:0,width:0,height:0})};
}
const lsStore={};
globalThis.document={
  getElementById:id=>{ if(!elMap[id]) elMap[id]=makeStub(); return elMap[id]; },
  querySelector:()=>null,querySelectorAll:()=>[],createElement:()=>makeStub(),
  addEventListener(){},visibilityState:'visible',
  body:{appendChild(){},removeChild(){}},activeElement:null
};
globalThis.window={devicePixelRatio:1};
globalThis.localStorage={
  getItem:k=>Object.prototype.hasOwnProperty.call(lsStore,k)?lsStore[k]:null,
  setItem:(k,v)=>{lsStore[k]=String(v);},removeItem:k=>{delete lsStore[k];}
};
globalThis.alert=()=>{};globalThis.confirm=()=>true;
globalThis.Blob=function(p,o){return{parts:p,opts:o};};
globalThis.URL={createObjectURL:()=>'blob:stub',revokeObjectURL(){}};
let __t=0;
globalThis.setTimeout=()=>++__t;globalThis.clearTimeout=()=>{};
globalThis.setInterval=()=>++__t;globalThis.clearInterval=()=>{};
globalThis.ResizeObserver=function(){return{observe(){},disconnect(){}};};
globalThis.LightweightCharts={LineStyle:{Solid:0,Dashed:1,Dotted:2},CrosshairMode:{Normal:0}};
globalThis.Notification=undefined;
globalThis.indexedDB=undefined;

// Tuesday 2026-08-11, 14:00 UTC. ALEX's frozen v1.1 entry-day rule allows Mon/Tue/Wed UTC
// (RULES_ALEXG.hubTestStandardizations.entryDaysOfWeekUTC = [1,2,3]). The clock is pinned so the
// suite is deterministic on any day of the week -- the RULE is untouched and still evaluated in
// full; only the simulated "now" is fixed, exactly as the JVM suite does. Running against the real
// clock would make this suite pass or fail depending on the day it happened to run.
let __simNow=Date.UTC(2026,7,11,14,0,0);
const __RealDate=Date;
globalThis.Date=class extends __RealDate{
  constructor(...a){ if(a.length===0) super(__simNow); else super(...a); }
  static now(){ return __simNow; }
};

// ── Candle construction. Same shape tests/v126 validated: a quiet series with four real swing-low
// touches at ~1.1000, which the FROZEN zone/setup engine turns into one genuine REPEATED ZONE
// REACTION. t0 controls how fresh the resulting qualificationTimestamp is.
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
// ── Six-touch variant, used ONLY by the ORGANIC RE-ANCHOR fixtures (DRIFT-12..14). Same
// construction the frozen engine already validates above -- real swing-low touches that become a
// genuine REPEATED ZONE REACTION -- with two deliberate differences.
//   * SIX touches instead of four, so the zone still validates (3 reactions) and still produces a
//     qualifying setup on its last touch AFTER the first touch has been lost.
//   * The FIRST touch is anchored at bar 14, the earliest bar at which the frozen confirmation
//     path can accept a reaction at all: it calls calcATR(candles.slice(0,anchorBarIndex+1),14),
//     which returns null below 15 candles.
// That placement is what makes a candle-window roll ORGANIC. Drop the two oldest H1 candles and
// the first touch's own ATR slice falls two candles short, so the FROZEN engine simply can no
// longer confirm it; the cluster re-anchors on the second touch and the zone is validated at a
// later reaction -- a genuinely different zoneId (and therefore a different setupId/signalId),
// while the last touch's reactionId and qualificationTimestamp are absolute close times and do
// not move at all. No stored record is edited and no guard is touched: this is the same window
// roll fetchAlexGReplayDatasets' fixed 2,220-bar H1 request performs every hour in production.
function buildSixTouchReactionH1(t0){
  const candles=[];
  function push(o,h,l,c){ candles.push({o,h,l,c,t:new Date(t0+candles.length*3600000)}); }
  function filler(n){
    let base=1.10600;
    for(let i=0;i<n;i++){
      const drift=(candles.length%3)*0.00005;
      push(base+drift,base+drift+0.00080,base+drift-0.00040,base+drift+0.00020);
    }
  }
  const touchLows=[1.10000,1.10002,1.09998,1.10001,1.10003,1.09999];
  filler(14);
  for(let n=0;n<touchLows.length;n++){
    const l=touchLows[n];
    push(l+0.00020,l+0.00025,l,l+0.00015);
    push(l+0.00015,l+0.00200,l+0.00010,l+0.00180);
    if(n<touchLows.length-1) filler(8);
  }
  filler(20);
  return candles;
}
// Structureless higher-timeframe filler, and a structureless H1 series for every OTHER pair, so
// only the one instrument under test produces a setup and the other eleven honestly produce none.
function buildFlat(t0,n,stepMs){
  const candles=[];
  for(let i=0;i<n;i++) candles.push({o:1.1,h:1.101,l:1.099,c:1.1005,t:new Date(t0+i*stepMs)});
  return candles;
}

// The higher-timeframe filler each granularity is served by default, factored out so the
// MOGO-021 DECISION 1 fixtures below can hand the broker-page plan the IDENTICAL array the
// healthy control is served. That is what makes those fixtures isolate the completeness
// contract itself: the candles the engine would see are unchanged, and the only difference is
// what the broker does on the &to= continuation.
function __htfDefault(gran){
  if(gran==='H4') return buildFlat(__t0-30*24*3600000,30,4*3600000);
  if(gran==='D') return buildFlat(__t0-30*24*3600000,30,24*3600000);
  return buildFlat(__t0-200*24*3600000,30,7*24*3600000);
}
function __wire(arr){
  return arr.map(c=>({time:c.t.toISOString(),complete:true,
    mid:{o:String(c.o),h:String(c.h),l:String(c.l),c:String(c.c)}}));
}
let __target='EUR_USD', __h1=null, __bidask={bid:1.10595,ask:1.10605}, __t0=0;
// ── BROKER-PAGE PLAN. The default below is unchanged and is what every pre-existing fixture
// runs on: one page for the requested granularity, then an empty &to= continuation -- genuine
// exhaustion, which fetchCandlesRange records as EMPTY_PAGE. MOGO-021 DECISION 1 turns entirely
// on what happens AFTER a short page, so one instrument+granularity at a time can be given an
// explicit page sequence instead: `pages` are served in order to the successive requests of one
// fetchCandlesRange walk, and `then` decides what the broker does once they run out --
//   'EMPTY'          genuine exhaustion            -> EMPTY_PAGE
//   'HTTP_ERROR'     a transport failure mid-walk  -> HTTP_ERROR
//   'NETWORK_ERROR'  the request itself throws     -> NETWORK_ERROR
// The page counter resets on every request WITHOUT &to=, which is precisely the start of a new
// walk, so one plan serves repeated polls identically.
let __plan=null,__planIdx=0;
globalThis.fetch=async function(url){
  const u=String(url);
  const cm=u.match(/instruments\/([^/]+)\/candles\?count=(\d+)&granularity=(\w+)/);
  if(cm){
    const inst=cm[1], gran=cm[3];
    if(__plan&&inst===__plan.inst&&gran===__plan.gran){
      if(!/&to=/.test(u)) __planIdx=0;   // a fresh walk always starts at the plan's first page
      const page=(__plan.pages||[])[__planIdx++];
      if(!page){
        if(__plan.then==='HTTP_ERROR') return {ok:false,status:503,json:async()=>({})};
        if(__plan.then==='NETWORK_ERROR') throw new Error('simulated network failure');
        return {ok:true,status:200,json:async()=>({candles:[]})};
      }
      return {ok:true,status:200,json:async()=>({candles:__wire(page)})};
    }
    if(/&to=/.test(u)) return {ok:true,status:200,json:async()=>({candles:[]})};   // no further pages
    let arr;
    if(gran==='H1') arr=(inst===__target)?__h1:buildFlat(__t0,80,3600000);
    else arr=__htfDefault(gran);
    return {ok:true,status:200,json:async()=>({candles:__wire(arr)})};
  }
  if(/\/pricing\?instruments=/.test(u)){
    if(!__bidask) return {ok:false,status:503,json:async()=>({})};
    return {ok:true,status:200,json:async()=>({prices:[{bids:[{price:String(__bidask.bid)}],asks:[{price:String(__bidask.ask)}]}]})};
  }
  return {ok:false,status:404,json:async()=>({})};
};

const results=[];
const g={record:(id,desc,pass,detail)=>results.push({id,desc,pass,detail:detail||''})};
g.setH1=c=>{__h1=c;};
g.setT0=t=>{__t0=t;};
g.setBidAsk=v=>{__bidask=v;};
g.build=t0=>buildRepeatedReactionH1(t0);
g.build6=t0=>buildSixTouchReactionH1(t0);
g.now=()=>Date.now();
g.setPlan=p=>{__plan=p;__planIdx=0;};              // null restores the default one-page-then-exhausted broker
g.htf=gran=>__htfDefault(gran);                    // the exact array the healthy control is served
g.flat=(t0,n,step)=>buildFlat(t0,n,step);

const wrapped=new Function('g', appCode + '\n' + 'return (async function(){\n' +
  '  cfg.key="fixture"; cfg.accountId="acct"; cfg.env="practice";\n' +
  // Capture what the poll hands the durable ledger, built through the REAL builder (not the raw
  // seam input), so a coverage claim here is a claim about the durable record.
  '  var __lastObs=null; const __origRecObs=evidenceRecordForwardObservations;\n' +
  '  evidenceRecordForwardObservations=function(input){ __lastObs=evidenceBuildPollObservation((input&&input.poll)||{}); return __origRecObs.apply(this,arguments); };\n' +
  '  g.lastObs=function(){ return __lastObs||{}; };\n' +
  '  var __lastPipeline=[]; const __origDrain=alexGDrainPipelineObservations;\n' +
  '  alexGDrainPipelineObservations=function(){ const r=__origDrain.apply(this,arguments); __lastPipeline=r||[]; return r; };\n' +
  '  g.lastPipeline=function(){ return __lastPipeline; };\n' +
  '  const nowMs=Date.now();\n' +
  '  const t0=nowMs-48*3600000-5*60000;\n' +   // the qualifying touch lands ~5 min ago
  '  g.setT0(t0); g.setH1(g.build(t0));\n' +
  '  function freshSession(){\n' +
  '    alexGSetupState=[]; alexGZoneState={}; alexGLastEvaluatedCloseTime={}; alexGResetLiveDecisionState();\n' +
  '    decisionEventLog=[]; decisionEventSequenceCounter=0; decisionEventKnownCandidateIds=new Set();\n' +
  '  }\n' +
  '  function fullReset(){\n' +
  '    freshSession();\n' +
  '    alexGAccount={balance:10000,openPositions:[],closedPositions:[]};\n' +
  '    alexGJournalEntries=[];\n' +
  '    alexGAutoTrading={enabled:true,activatedAt:nowMs-72*3600000,tradedSignals:{},tradedToday:{},log:[]};\n' +
  '    alexGAccountKnownVersion=0;\n' +
  // The persisted ledger version must be cleared too. Without this, the optimistic-concurrency
  // guard refuses every commit after the first, so a scenario looks like "no duplicate opened"
  // when the real cause is a blocked write -- which is exactly why an earlier E2E-11 survived
  // removal of all four duplicate guards.
  '    ["fxhub_alexg_account","fxhub_alexg_account_version","fxhub_alexg_auto",\n' +
  '     "fxhub_alexg_journal","fxhub_alexg_setups","fxhub_alexg_zones"].forEach(function(k){\n' +
  '       try{ localStorage.removeItem(k); }catch(e){} });\n' +
  '  }\n' +
  '  function closeOpenPosition(){ const q=alexGAccount.openPositions.shift(); if(!q) return null;\n' +
  '    q.status="closed"; q.exitPrice=q.target; q.closedAt=new Date().toISOString();\n' +
  '    q.result="Win"; q.resultR=2; q.pnl=200; q.exitBid=q.target; q.exitAsk=q.target;\n' +
  '    q.exitSpreadPips=0; q.exitDetectionSource="fixture_close";\n' +
  '    alexGAccount.closedPositions.push(q); return q; }\n' +
  '  fullReset();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  // ══ PART 1 -- under the REAL production policy, unmodified ══
  '  const chain=decisionEventLog.map(function(e){return e.eventType+"/"+(e.reasonCode||"-");});\n' +
  '  const rules=decisionEventLog.filter(function(e){return e.eventType==="RULE_EVALUATED";})\n' +
  '    .map(function(e){return e.ruleId+":"+e.ruleResult;});\n' +
  '  g.record("E2E-1","the OUTERMOST live path drives a real setup through EVERY frozen gate in order",\n' +
  '    rules.join(",")==="ALEX_ACTIVATION_CUTOFF:PASS,ALEX_SIGNAL_STALENESS:PASS,ALEX_V11_ENTRY_DAY:PASS,ALEX_V11_SETUP_EXECUTION_POLICY:FAIL",\n' +
  '    rules.join(" -> "));\n' +
  '  g.record("E2E-2","PRODUCTION POLICY: the trade is withheld because A_repeatedReaction is suspended for research",\n' +
  '    alexGAccount.openPositions.length===0&&\n' +
  '    chain.indexOf("CANDIDATE_REJECTED/SETUP_SUSPENDED_FOR_RESEARCH")!==-1&&\n' +
  '    RULES_ALEXG_V11.v11Config.setupSuspensionEnabled===true,\n' +
  '    "open="+alexGAccount.openPositions.length+", withheld by the live suspension policy");\n' +
  '  g.record("E2E-3","the withheld candidate is RECORDED, not silently dropped",\n' +
  '    (alexGLiveSetupStatuses[0]||{}).reason==="SETUP_SUSPENDED_FOR_RESEARCH"&&\n' +
  '    /SUSPENDED/.test(String((alexGLiveSetupStatuses[0]||{}).status)),\n' +
  '    String((alexGLiveSetupStatuses[0]||{}).status));\n' +
  '  g.record("E2E-4","every configured instrument is still covered on that tick",\n' +
  '    (g.lastObs().instrumentsEvaluated||[]).length===SCAN_PAIRS.length,\n' +
  '    "instrumentsEvaluated="+((g.lastObs().instrumentsEvaluated)||[]).length+"/"+SCAN_PAIRS.length);\n' +
  '  g.record("E2E-5","the other eleven instruments honestly produced no setup of their own",\n' +
  '    alexGSetupState.filter(function(s){return s.pair!=="EUR_USD";}).length===0,\n' +
  '    "non-target setups="+alexGSetupState.filter(function(s){return s.pair!=="EUR_USD";}).length);\n' +
  // ══ PART 2 -- execution mechanics, with the suspension flag explicitly lifted ══
  // DISCLOSED, exactly as tests/v126 does: the operational suspension is an execution-policy flag,
  // not a strategy rule. It is lifted ONLY to exercise the open/persist/restart machinery that
  // production policy currently withholds, and restored and re-asserted at the end (E2E-14).
  // Everything else -- thresholds, zone engine, gates -- remains frozen and untouched.
  '  const __suspendWas=RULES_ALEXG_V11.v11Config.setupSuspensionEnabled;\n' +
  '  RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=false;\n' +
  '  fullReset();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("E2E-6","with the policy lifted, the SAME setup opens a REAL ALEX paper position end-to-end",\n' +
  '    alexGAccount.openPositions.length===1,"openPositions="+alexGAccount.openPositions.length);\n' +
  '  const pos=alexGAccount.openPositions[0]||{};\n' +
  '  g.record("E2E-7","the position is coherent -- pair, timeframe, direction, and stop below entry",\n' +
  '    pos.pair==="EUR_USD"&&pos.timeframe==="H1"&&typeof pos.entry==="number"&&\n' +
  '    typeof pos.stop==="number"&&typeof pos.target==="number"&&pos.stop<pos.entry&&pos.target>pos.entry,\n' +
  '    JSON.stringify({pair:pos.pair,tf:pos.timeframe,dir:pos.direction||pos.dir,entry:pos.entry,stop:pos.stop,target:pos.target}));\n' +
  '  g.record("E2E-8","LIFECYCLE PERSISTENCE: journalled once and the signal marked traded",\n' +
  '    alexGJournalEntries.length===1&&Object.keys(alexGAutoTrading.tradedSignals).length===1&&\n' +
  '    alexGAutoTrading.tradedSignals[pos.signalId]===true,\n' +
  '    "journal="+alexGJournalEntries.length+" tradedSignals="+Object.keys(alexGAutoTrading.tradedSignals).length);\n' +
  '  const opened=decisionEventLog.filter(function(e){return e.eventType==="TRADE_OPENED";});\n' +
  '  g.record("E2E-9","TRADE_OPENED carries the tradeId of the position that actually exists",\n' +
  '    opened.length===1&&opened[0].tradeId===pos.tradeId,\n' +
  '    "eventTradeId="+(opened[0]||{}).tradeId+" posTradeId="+pos.tradeId);\n' +
  '  const balAfter=alexGAccount.balance;\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("E2E-10","a second poll in the same session opens nothing further",\n' +
  '    alexGAccount.openPositions.length===1&&alexGAccount.balance===balAfter,\n' +
  '    "open="+alexGAccount.openPositions.length+" balance unchanged="+(alexGAccount.balance===balAfter));\n' +
  // ══ RESTART / RECOVERY -- the property that actually matters ══
  // The position must be CLOSED before the restart. With it still open, the pair+timeframe overlap
  // rule (index.html:4314) blocks any re-open and the persistence guards are never reached -- an
  // earlier version of these two fixtures passed even with the tradedSignals guard disabled.
  // Production's only real trade closed the same day, so this is the case that actually matters.
  '  closeOpenPosition();\n' +
  '  freshSession();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  // NOTE ON STRENGTH: this fixture is a scenario check, not a guard proof. Mutation-tested -- it
  // survives removal of all four duplicate guards, because other persisted state still prevents a
  // second open in this configuration. E2E-12 below is the discriminating one: it isolates
  // tradedSignals and does die when that guard is disabled. Kept because it exercises the
  // realistic restart-after-close sequence end-to-end, which E2E-12's stripped ledger does not.
  '  g.record("E2E-11","RESTART SCENARIO: with the trade closed and the session cleared, the ledger is unchanged",\n' +
  '    alexGAccount.openPositions.length===0&&alexGAccount.closedPositions.length===1&&alexGJournalEntries.length===1,\n' +
  '    "open="+alexGAccount.openPositions.length+" closed="+alexGAccount.closedPositions.length+" journal="+alexGJournalEntries.length+" (scenario check; E2E-12 carries the discrimination)");\n' +
  // Isolate the persisted guards one at a time. The status ring is gone, so whatever blocks the
  // re-open must be persisted state -- and each of these is individually load-bearing.
  '  alexGAccount.closedPositions=[]; alexGJournalEntries=[];\n' +
  '  freshSession();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  // The setup must be re-derived (proving the duplicate check was actually reached) while nothing
  // opens. Note the DUPLICATE path returns before recording a status, so the ring stays empty --
  // asserting on ring length here would be asserting on the wrong observable.
  '  g.record("E2E-12","with closed-positions and journal ALSO cleared, persisted tradedSignals ALONE still blocks it",\n' +
  '    alexGAccount.openPositions.length===0&&alexGAccount.closedPositions.length===0&&\n' +
  '    alexGJournalEntries.length===0&&Object.keys(alexGAutoTrading.tradedSignals).length===1&&\n' +
  '    alexGSetupState.filter(function(x){return x.pair==="EUR_USD";}).length===1,\n' +
  '    "setup re-derived and reached the duplicate check; open=0 with tradedSignals as the only surviving guard");\n' +
  // stale backlog after a restart -- never back-filled
  '  fullReset();\n' +
  '  const tOld=nowMs-48*3600000-8*3600000;\n' +
  '  g.setT0(tOld); g.setH1(g.build(tOld));\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:tOld+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const staleEv=decisionEventLog.filter(function(e){return e.reasonCode==="STATE_SIGNAL_STALE";});\n' +
  '  g.record("E2E-13","RESTART BACKLOG: a post-activation but OLD setup is rejected STALE, never back-filled",\n' +
  '    alexGAccount.openPositions.length===0&&staleEv.length>0&&\n' +
  '    staleEv.some(function(e){return e.context&&e.context.maxAgeMinutes===60&&e.context.ageMinutes>60;}),\n' +
  '    JSON.stringify((staleEv.find(function(e){return e.context;})||{}).context));\n' +
  '  g.record("E2E-14","the stale-backlog rejection is the strategy\u2019s own, measured against its own limit",\n' +
  '    staleEv.some(function(e){ return e.context&&e.context.maxAgeMinutes===60; }),\n' +
  '    "maxAgeMinutes=60 as configured for H1");\n' +
  // ══ failure isolation ══
  // The suspension must be LIFTED here, or the setup is withheld at the policy gate and
  // alexGAttemptOpenLivePosition -- and therefore fetchBidAsk -- is never reached at all. An
  // earlier version restored the flag first, so this fixture passed for an unrelated reason and
  // never exercised the pricing seam. TRADE_OPEN_REQUESTED below proves the seam is reached.
  '  RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=false;\n' +
  '  fullReset();\n' +
  '  g.setT0(t0); g.setH1(g.build(t0)); g.setBidAsk(null);\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("E2E-15","FAILURE ISOLATION: the pricing seam IS reached and returns nothing, and no throw escapes",\n' +
  '    decisionEventLog.filter(function(e){return e.eventType==="TRADE_OPEN_REQUESTED";}).length===1&&\n' +
  '    alexGAccount.openPositions.length===0&&alexGJournalEntries.length===0&&\n' +
  '    decisionEventLog.some(function(e){return e.eventType==="SCAN_COMPLETED";}),\n' +
  '    "TRADE_OPEN_REQUESTED="+decisionEventLog.filter(function(e){return e.eventType==="TRADE_OPEN_REQUESTED";}).length+\n' +
  '    ", open=0, journal=0, scan still completed");\n' +
  '  g.record("E2E-16","and coverage is still recorded for every instrument on the failing tick",\n' +
  '    (g.lastObs().instrumentsEvaluated||[]).length===SCAN_PAIRS.length,\n' +
  '    "instrumentsEvaluated="+((g.lastObs().instrumentsEvaluated)||[]).length+"/"+SCAN_PAIRS.length);\n' +
  // ══ SIGNAL-IDENTITY DRIFT DETECTOR ══
  // Reproduces the production condition from report section 2.16: a setup already traded is
  // re-derived later under a DIFFERENT signalId because its zone re-anchored, at which point every
  // duplicate guard misses. The detector is observation-only; these fixtures prove it fires on the
  // real condition, stays silent otherwise, and changes no trading decision.
  '  const __susp3=RULES_ALEXG_V11.v11Config.setupSuspensionEnabled;\n' +
  '  RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=false;\n' +
  '  g.setBidAsk({bid:1.10595,ask:1.10605});\n' +
  '  fullReset();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const traded=alexGAccount.openPositions[0];\n' +
  // The likeliest way the journal scan could go wrong: firing on a setup's OWN journal entry every
  // time it is re-evaluated. Re-arm the cursor so the setup really is re-evaluated, then demand
  // silence -- this is the fixture that would catch a tradeId derivation mismatch.
  // The latch MUST be cleared here, or this fixture is vacuous. Every scenario above runs on the
  // same t0, so it produces the same (stableId|signalId) latch key -- and a false positive raised
  // in an EARLIER fixture latches that key and then silently suppresses the very condition this
  // fixture exists to catch. Verified: without this line, removing j.tradeId!==currentTradeId from
  // the journal scan left DRIFT-1b PASSING, and so did removing p.signalId!==signalId.
  '  alexGIdentityDriftReported=new Set();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}}; alexGResetLiveDecisionState();\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("DRIFT-1b","NO false positive: re-evaluating a normally-traded setup reports no drift",\n' +
  '    decisionEventLog.filter(function(e){return e.reasonCode==="STATE_SIGNAL_IDENTITY_DRIFTED";}).length===0&&\n' +
  '    (g.lastObs().instrumentsEvaluated||[]).length===SCAN_PAIRS.length&&alexGJournalEntries.length===1,\n' +
  '    "0 drift events across "+((g.lastObs().instrumentsEvaluated)||[]).length+"/12 re-evaluated instruments, journal present");\n' +
  '  g.record("DRIFT-1","precondition: a real position exists to drift away from",!!traded,"tradeId="+(traded||{}).tradeId);\n' +
  // Close it, then re-anchor its stored identity exactly as a candle-window roll does: the zone
  // components change while pair/timeframe/setupType/reactionId/qualificationTimestamp do not.
  '  if(traded) closeOpenPosition();\n' +
  // Every PERSISTED record must carry the OLD identity while the freshly-derived setup carries the
  // NEW one -- that is what a zone re-anchor actually produces. Drifting only the stored position
  // while leaving tradedSignals keyed on the original identity would leave a guard that still
  // matches, and the scenario would prove nothing.
  '  alexGAccount.closedPositions[0].signalId="AGL|DRIFTED|"+alexGAccount.closedPositions[0].signalId;\n' +
  '  alexGAccount.closedPositions[0].tradeId="AGT|DRIFTED|"+alexGAccount.closedPositions[0].tradeId;\n' +
  '  alexGAutoTrading.tradedSignals={};\n' +
  '  alexGAutoTrading.tradedSignals[alexGAccount.closedPositions[0].signalId]=true;\n' +
  '  alexGJournalEntries.forEach(function(j){ if(j.signalId) j.signalId="AGL|DRIFTED|"+j.signalId; });\n' +
  '  freshSession();\n' +
  // Clear the persisted ledger version too, or the optimistic-concurrency guard refuses the second
  // commit and the scenario would look safe for a reason that has nothing to do with the defect.
  '  ["fxhub_alexg_account","fxhub_alexg_account_version"].forEach(function(k){ try{ localStorage.removeItem(k); }catch(e){} });\n' +
  '  alexGAccountKnownVersion=0;\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const drift=decisionEventLog.filter(function(e){return e.reasonCode==="STATE_SIGNAL_IDENTITY_DRIFTED";});\n' +
  '  g.record("DRIFT-2","the detector FIRES when an already-traded setup returns under a new identity",\n' +
  '    drift.length===1,"events="+drift.length);\n' +
  '  const dctx=(drift[0]||{}).context||{};\n' +
  '  g.record("DRIFT-3","and it names both identities plus the stable key that links them",\n' +
  '    typeof dctx.stableId==="string"&&typeof dctx.currentSignalId==="string"&&\n' +
  '    typeof dctx.priorSignalId==="string"&&dctx.currentSignalId!==dctx.priorSignalId,\n' +
  '    "stableId="+String(dctx.stableId).slice(0,60));\n' +
  '  const dpipe=(g.lastPipeline()||[]).filter(function(r){return r&&r.reason==="STATE_SIGNAL_IDENTITY_DRIFTED";});\n' +
  '  g.record("DRIFT-4","the drift survives the DURABLE builder with stage and source trade intact",\n' +
  '    dpipe.length===1&&dpipe[0].stage==="IDENTITY_DRIFT"&&\n' +
  '    dpipe[0].sourceTradeId===alexGAccount.closedPositions[0].tradeId,\n' +
  '    "stage="+String(dpipe[0]&&dpipe[0].stage)+" sourceTradeId set="+!!(dpipe[0]&&dpipe[0].sourceTradeId));\n' +
  // The cursor and status ring must be re-armed, or the second poll skips all 12 pairs at the
  // cadence gate and the detector never runs -- which made an earlier version of this fixture pass
  // even with the latch permanently disabled.
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}}; alexGResetLiveDecisionState();\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("DRIFT-5","it is reported ONCE per drifted identity, even though the setup is re-evaluated",\n' +
  '    (g.lastObs().instrumentsEvaluated||[]).length===SCAN_PAIRS.length&&\n' +
  '    decisionEventLog.filter(function(e){return e.reasonCode==="STATE_SIGNAL_IDENTITY_DRIFTED";}).length===1,\n' +
  '    "re-evaluated "+((g.lastObs().instrumentsEvaluated)||[]).length+"/12 instruments, still 1 drift event");\n' +
  // INVERTED BY MOGO-021 DECISIONS 2+3, exactly as this fixture always said it would be. It
  // previously asserted the guard MISS -- a second position on one economic setup, report section
  // 2.16 -- and was documented as "expected to invert when the governed fix lands, at which point
  // it becomes the proof the fix works." The scenario construction below is unchanged to the
  // character; only the asserted outcome moved. The decided-authority now matches the drifted
  // setup through the DURABLE records it left behind, so the duplicate is refused.
  '  const decided6=decisionEventLog.filter(function(e){return e.eventType==="CANDIDATE_REJECTED"&&\n' +
  '    e.reasonCode==="STATE_SIGNAL_ALREADY_DECIDED";});\n' +
  '  g.record("DRIFT-6","THE GUARD MISS IS CLOSED: the drifted setup is REFUSED, not opened a second time",\n' +
  '    alexGAccount.openPositions.length===0&&alexGAccount.closedPositions.length===1&&\n' +
  '    alexGJournalEntries.length===1&&Object.keys(alexGAutoTrading.tradedSignals).length===1&&\n' +
  '    decided6.length>0&&decided6.every(function(e){return (e.context||{}).identityDrifted===true;}),\n' +
  '    "open="+alexGAccount.openPositions.length+" closed="+alexGAccount.closedPositions.length+\n' +
  '    " journal="+alexGJournalEntries.length+" -- one economic setup, ONE position, refused as "+\n' +
  '    "already decided on each of the "+decided6.length+" re-evaluations "+\n' +
  '    "(matchedBy="+String((decided6[0]||{}).context&&decided6[0].context.matchedBy)+")");\n' +
  '  g.record("DRIFT-6b","OBSERVATION ONLY: the detector records it and rejects nothing -- repair is a governed change",\n' +
  '    decisionEventLog.filter(function(e){return e.eventType==="CANDIDATE_REJECTED"&&e.reasonCode==="STATE_SIGNAL_IDENTITY_DRIFTED";}).length===0&&\n' +
  '    decisionEventLog.filter(function(e){return e.reasonCode==="STATE_SIGNAL_IDENTITY_DRIFTED";}).every(function(e){return e.eventType==="ENGINE_ERROR";}),\n' +
  '    "no rejection attributable to the detector; it only reports");\n' +
  '  clearDecisionEvents();\n' +
  '  g.record("DRIFT-7","clearing the bus re-arms the detector, so a dev-only button cannot hide an ongoing drift",\n' +
  '    alexGIdentityDriftReported.size===0,"latch cleared alongside the events it referred to");\n' +
  // An UNRELATED closed position must be present, or the detector has nothing to false-positive
  // against and the fixture cannot catch a degenerate identity. Verified: with
  // alexGStableSetupIdentity returning a constant, an empty-account version of this stayed green.
  '  fullReset();\n' +
  '  alexGAccount.closedPositions.push({pair:"USD_CHF",timeframe:"H4",setupType:"B_breakRetest",\n' +
  '    reactionId:"AGR|USD_CHF|H4|high|1700000000000",qualificationTimestamp:1700000000000,\n' +
  '    signalId:"AGL|UNRELATED",tradeId:"AGT|UNRELATED",status:"closed",exitPrice:1,closedAt:new Date().toISOString(),\n' +
  '    result:"Win",resultR:2,pnl:200});\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("DRIFT-8","it stays SILENT against an UNRELATED prior trade -- the identity discriminates",\n' +
  '    decisionEventLog.filter(function(e){return e.reasonCode==="STATE_SIGNAL_IDENTITY_DRIFTED";}).length===0&&\n' +
  '    alexGAccount.closedPositions.length===1,\n' +
  '    "0 drift events despite a prior closed position on a different setup");\n' +
  // The blind spot the detector now covers: positions gone, journal surviving (INC-001 per-key load).
  '  fullReset();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const jTraded=alexGAccount.openPositions[0];\n' +
  '  if(jTraded) closeOpenPosition();\n' +
  // EVERY recorded identity must be re-anchored, tradedSignals included -- rewriting only the
  // journal tradeId leaves tradedSignals matching, so no second position opens and the fixture
  // would prove detection without proving the guards actually miss in this state.
  '  alexGJournalEntries.forEach(function(j){ if(j.tradeId) j.tradeId="AGT|DRIFTED|"+j.tradeId; });\n' +
  '  alexGAutoTrading.tradedSignals={}; alexGAutoTrading.tradedSignals["AGL|DRIFTED|orphan"]=true;\n' +
  '  alexGAccount={balance:10000,openPositions:[],closedPositions:[]};\n' +   // account key unreadable; journal + auto survive
  '  freshSession();\n' +
  '  ["fxhub_alexg_account","fxhub_alexg_account_version"].forEach(function(k){ try{ localStorage.removeItem(k); }catch(e){} });\n' +
  '  alexGAccountKnownVersion=0;\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const jDrift=decisionEventLog.filter(function(e){return e.reasonCode==="STATE_SIGNAL_IDENTITY_DRIFTED";});\n' +
  '  g.record("DRIFT-9","BLIND SPOT CLOSED: drift is detected when ONLY the journal survives",\n' +
  '    jDrift.length===1&&(jDrift[0].context||{}).priorRecord==="journal",\n' +
  '    "detected from the journal alone, positions empty (the INC-001 per-key load state)");\n' +
  // INVERTED BY MOGO-021 DECISIONS 2+3. This is the INC-001 blind spot -- positions gone, journal
  // surviving -- and it was the state in which every identity-keyed guard missed. The
  // decided-authority derives "already traded" from the durable records that DO survive, so the
  // journal alone is now enough to refuse the duplicate. Scenario construction unchanged.
  '  const decided9=decisionEventLog.filter(function(e){return e.eventType==="CANDIDATE_REJECTED"&&\n' +
  '    e.reasonCode==="STATE_SIGNAL_ALREADY_DECIDED";});\n' +
  '  g.record("DRIFT-9b","and in that state the guards now HOLD -- the journal alone refuses the second position",\n' +
  '    alexGAccount.openPositions.length===0&&alexGJournalEntries.length===1&&\n' +
  '    decided9.length===1&&(decided9[0].context||{}).identityDrifted===true,\n' +
  '    "open="+alexGAccount.openPositions.length+" with every recorded identity re-anchored; refused via "+\n' +
  '    String((decided9[0]||{}).context&&decided9[0].context.matchSource));\n' +
  // ── the latch fix itself, which had NO repository coverage ──
  // The first attempt at this fix reordered the mark to after the emit and was a no-op, because
  // emitDecisionEvent never throws -- it returns {ok:false}. Reverting the real fix (marking
  // unconditionally) previously killed nothing in the suite. These two fixtures close that.
  '  fullReset(); g.setBidAsk({bid:1.10595,ask:1.10605});\n' +
  '  alexGIdentityDriftReported=new Set();\n' +   // fullReset does not clear the latch; earlier scenarios latched
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  if(alexGAccount.openPositions.length) closeOpenPosition();\n' +
  '  alexGAccount.closedPositions[0].signalId="AGL|DRIFTED|"+alexGAccount.closedPositions[0].signalId;\n' +
  '  alexGAccount.closedPositions[0].tradeId="AGT|DRIFTED|"+alexGAccount.closedPositions[0].tradeId;\n' +
  '  const __origValidate=validateDecisionEvent;\n' +
  '  validateDecisionEvent=function(ev){ if(ev&&ev.reasonCode==="STATE_SIGNAL_IDENTITY_DRIFTED") return{valid:false,errors:["forced reject"]}; return __origValidate.apply(this,arguments); };\n' +
  '  freshSession();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  validateDecisionEvent=__origValidate;\n' +
  '  g.record("DRIFT-10","a REJECTED drift event does NOT latch -- the condition is not silently suppressed",\n' +
  '    alexGIdentityDriftReported.size===0&&\n' +
  '    (g.lastPipeline()||[]).filter(function(r){return r&&r.reason==="STATE_SIGNAL_IDENTITY_DRIFTED";}).length===1,\n' +
  '    "latchSize="+alexGIdentityDriftReported.size+" (unlatched, so it keeps reporting) with the durable row still written");\n' +
  // Asserts the key the DETECTOR actually built. Calling the mark helper with literal keys tests
  // the Set, not the composition -- and left the "keyed on stableId only" mutation surviving.
  '  alexGIdentityDriftReported=new Set(); freshSession();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const latchKeys=Array.from(alexGIdentityDriftReported);\n' +
  '  const curSig=alexGSetupState.filter(function(x){return x.pair==="EUR_USD";}).map(alexGLiveSignalId)[0];\n' +
  '  const curSetup=alexGSetupState.filter(function(x){return x.pair==="EUR_USD";})[0];\n' +
  '  const expectKey=curSetup?(alexGStableSetupIdentity(curSetup)+"|"+curSig):null;\n' +
  '  g.record("DRIFT-11","the latch key the detector builds is (stableId|signalId), so a second re-anchor still reports",\n' +
  '    latchKeys.length===1&&!!expectKey&&latchKeys[0]===expectKey,\n' +
  '    "key="+String(latchKeys[0]).slice(-40)+" (stable id alone would suppress a later re-anchor)");\n' +
  // ══ ORGANIC ZONE RE-ANCHOR -- the drift condition produced by the ENGINE, not by the fixture ══
  // Every drift fixture above fakes the re-anchor by string-prefixing a stored identifier while
  // leaving the stored zoneId untouched. A real re-anchor changes the zoneId itself, and the
  // difference is not cosmetic: appending ,x.zoneId to alexGStableSetupIdentity -- which destroys
  // the detector's entire reason to exist, since the "stable" identity would then drift with the
  // zone -- killed 0 of the 38 fixtures that existed before this block, while against a real
  // re-anchor it produces zero drift events at the exact moment a second position opens.
  //
  // Here NOTHING is hand-edited. The real, unmodified engine opens a position on poll 1; the
  // position is closed (as production's own only real trade was, the same day); and the ONLY
  // change before poll 2 is that the two oldest H1 candles fall out of the fetch window. The
  // re-anchor, the new zoneId, the new signalId and the guard miss are all the engine's own.
  '  RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=false;\n' +
  '  fullReset(); alexGIdentityDriftReported=new Set(); g.setBidAsk({bid:1.10595,ask:1.10605});\n' +
  '  const tOrg=nowMs-68*3600000-5*60000;\n' +   // the sixth touch qualifies ~5 min ago
  '  const h1Full=g.build6(tOrg);\n' +
  '  g.setT0(tOrg); g.setH1(h1Full);\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:tOrg+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const orgPos=alexGAccount.openPositions[0]||null;\n' +
  '  g.record("DRIFT-12a","ORGANIC precondition: the unmodified engine opens ONE real position on the full window",\n' +
  '    alexGAccount.openPositions.length===1&&!!orgPos&&!!orgPos.zoneId&&!!orgPos.reactionId,\n' +
  '    "open="+alexGAccount.openPositions.length+" zoneId="+String(orgPos&&orgPos.zoneId).slice(-30));\n' +
  '  if(orgPos) closeOpenPosition();\n' +
  // The ONLY intervention: roll the candle-fetch window forward by two H1 bars. No stored record
  // is rewritten, tradedSignals still carries poll 1's real signalId, and no guard is disabled.
  '  g.setH1(h1Full.slice(2));\n' +
  '  freshSession();\n' +
  '  ["fxhub_alexg_account","fxhub_alexg_account_version"].forEach(function(k){ try{ localStorage.removeItem(k); }catch(e){} });\n' +
  '  alexGAccountKnownVersion=0;\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:tOrg+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const orgSetup=alexGSetupState.filter(function(x){return x.pair==="EUR_USD";})[0]||null;\n' +
  '  const orgDrift=decisionEventLog.filter(function(e){return e.reasonCode==="STATE_SIGNAL_IDENTITY_DRIFTED";});\n' +
  '  const octx=(orgDrift[0]||{}).context||{};\n' +
  '  g.record("DRIFT-12","ORGANIC RE-ANCHOR: the detector fires on drift the ENGINE produced, with nothing hand-edited",\n' +
  '    orgDrift.length===1&&!!orgPos&&octx.priorSignalId===orgPos.signalId&&\n' +
  '    octx.currentSignalId!==octx.priorSignalId&&octx.priorZoneId!==octx.currentZoneId,\n' +
  '    "events="+orgDrift.length+" priorZoneId!=currentZoneId="+(octx.priorZoneId!==octx.currentZoneId));\n' +
  // INVERTED BY MOGO-021 DECISIONS 2+3, and this is the strongest of the three: the re-anchor here
  // is the ENGINE's own -- a real candle-window roll, no stored record edited -- so what is refused
  // is a duplicate the fixture did not have to manufacture. alexGStableSetupIdentity alone would
  // still match here; DRIFT-14 pins that. Scenario construction unchanged.
  '  const decided12=decisionEventLog.filter(function(e){return e.eventType==="CANDIDATE_REJECTED"&&\n' +
  '    e.reasonCode==="STATE_SIGNAL_ALREADY_DECIDED";});\n' +
  '  g.record("DRIFT-12b","and in that organic state the guards now HOLD -- one economic setup, ONE position",\n' +
  '    alexGAccount.openPositions.length===0&&alexGAccount.closedPositions.length===1&&\n' +
  '    decided12.length===1&&(decided12[0].context||{}).identityDrifted===true&&\n' +
  '    (decided12[0].context||{}).priorSignalId===orgPos.signalId,\n' +
  '    "open="+alexGAccount.openPositions.length+" closed="+alexGAccount.closedPositions.length+\n' +
  '    " -- the duplicate the engine itself produced is refused, matched back to the traded signalId");\n' +
  '  g.record("DRIFT-13","the re-anchor is REAL: same reactionId and qualificationTimestamp, DIFFERENT zoneId",\n' +
  '    !!orgSetup&&!!orgPos&&orgSetup.reactionId===orgPos.reactionId&&\n' +
  '    orgSetup.qualificationTimestamp===orgPos.qualificationTimestamp&&orgSetup.zoneId!==orgPos.zoneId&&\n' +
  '    alexGLiveSignalId(orgSetup)!==orgPos.signalId,\n' +
  '    "zoneId "+String(orgPos&&orgPos.zoneId).slice(-24)+" -> "+String(orgSetup&&orgSetup.zoneId).slice(-24));\n' +
  // The property the whole detector rests on, asserted against a re-anchor the engine really did.
  '  g.record("DRIFT-14","IDENTITY INVARIANCE: the stable identity survives a real re-anchor unchanged",\n' +
  '    !!orgSetup&&!!orgPos&&alexGStableSetupIdentity(orgSetup)===alexGStableSetupIdentity(orgPos)&&\n' +
  '    orgSetup.zoneId!==orgPos.zoneId,\n' +
  '    "stable identity identical across two different zoneIds");\n' +
  // ── COMPOSITION. The five components ARE the detector's correctness, and nothing pinned them:
  // dropping reactionId, or dropping qualificationTimestamp, each killed 0 of the original 38.
  '  const __compBase={pair:"EUR_USD",timeframe:"H1",setupType:"A_repeatedReaction",\n' +
  '    reactionId:"AGR|EUR_USD|H1|low|1700000000000",qualificationTimestamp:1700003600000,\n' +
  '    zoneId:"AGZ|AGC|EUR_USD|H1|low|1699000000000|v1699500000000",\n' +
  '    signalId:"AGL|IGNORED",tradeId:"AGT|IGNORED",setupId:"AGS|IGNORED"};\n' +
  '  function __comp(over){ return Object.assign({},__compBase,over); }\n' +
  '  g.record("DRIFT-15","COMPOSITION: the identity is EXACTLY the five anchor-free components, in order",\n' +
  '    alexGStableSetupIdentity(__compBase)===\n' +
  '      "EUR_USD|H1|A_repeatedReaction|AGR|EUR_USD|H1|low|1700000000000|1700003600000",\n' +
  '    alexGStableSetupIdentity(__compBase));\n' +
  '  g.record("DRIFT-16","two setups differing ONLY in reactionId get DIFFERENT identities",\n' +
  '    alexGStableSetupIdentity(__comp({reactionId:"AGR|EUR_USD|H1|low|1700007200000"}))!==\n' +
  '      alexGStableSetupIdentity(__compBase),\n' +
  '    "reactionId is load-bearing -- two touches of one zone are not one setup");\n' +
  '  g.record("DRIFT-17","two setups differing ONLY in qualificationTimestamp get DIFFERENT identities",\n' +
  '    alexGStableSetupIdentity(__comp({qualificationTimestamp:1700007200000}))!==\n' +
  '      alexGStableSetupIdentity(__compBase),\n' +
  '    "qualificationTimestamp is load-bearing -- one reaction qualifying twice is not one setup");\n' +
  // Restore the four-touch series every fixture below this point is built on.
  '  g.setT0(t0); g.setH1(g.build(t0));\n' +
  '  alexGIdentityDriftReported=new Set();\n' +
  '  RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=__susp3;\n' +
  '  g.setBidAsk({bid:1.10595,ask:1.10605});\n' +
  // ══ CONCURRENT POLL TICKS ══
  // Production evidence (durable ledger) shows 9 hours containing two advancing polls ~25s apart
  // with disjoint, non-contiguous pair sets -- the signature of one tick overlapping the next
  // interval firing. startAlexGLivePollingIfNeeded is guarded against a second interval, and
  // alexGLivePollTick has NO re-entrancy guard, so rather than assume the risk, exercise it.
  '  RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=false;\n' +
  '  fullReset();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  const __p1=alexGLivePollTick(); const __p2=alexGLivePollTick();\n' +
  '  await Promise.all([__p1,__p2]);\n' +
  '  g.record("RE-1","two CONCURRENT poll ticks both genuinely run -- the hazard is exercised, not avoided",\n' +
  '    decisionEventLog.filter(function(e){return e.eventType==="SCAN_STARTED";}).length===2,\n' +
  '    "SCAN_STARTED="+decisionEventLog.filter(function(e){return e.eventType==="SCAN_STARTED";}).length);\n' +
  // ATTRIBUTION, established by mutation rather than assumed: with ALL FIVE identity-keyed guards
  // disabled (the four at index.html:4302 plus the tradeId guard at 4361) these still pass. The
  // guard that actually holds under concurrency is the pair+timeframe OVERLAP rule at
  // index.html:4314. Removing that makes RE-2 and RE-4 fail with two positions open.
  '  g.record("RE-2","and they open exactly ONE position between them -- no duplicate trade",\n' +
  '    alexGAccount.openPositions.length===1,"openPositions="+alexGAccount.openPositions.length);\n' +
  '  g.record("RE-3","one journal entry and one traded-signal mark, not two",\n' +
  '    alexGJournalEntries.length===1&&Object.keys(alexGAutoTrading.tradedSignals).length===1,\n' +
  '    "journal="+alexGJournalEntries.length+" tradedSignals="+Object.keys(alexGAutoTrading.tradedSignals).length);\n' +
  '  g.record("RE-4","exactly one TRADE_OPENED across both ticks",\n' +
  '    decisionEventLog.filter(function(e){return e.eventType==="TRADE_OPENED";}).length===1,\n' +
  '    "TRADE_OPENED="+decisionEventLog.filter(function(e){return e.eventType==="TRADE_OPENED";}).length);\n' +
  '  g.record("RE-5","concurrent rebuild of the SAME pair does not duplicate its setup state",\n' +
  '    alexGSetupState.filter(function(x){return x.pair==="EUR_USD";}).length===1,\n' +
  '    "EUR_USD setups after concurrent rebuild="+alexGSetupState.filter(function(x){return x.pair==="EUR_USD";}).length);\n' +
  // Names the operative guard, so the attribution is asserted rather than left to a comment.
  '  g.record("RE-6","the guard holding under concurrency is the pair+timeframe OVERLAP rule, not signal identity",\n' +
  '    alexGAccount.openPositions.filter(function(p){return p.pair==="EUR_USD"&&p.timeframe==="H1";}).length===1,\n' +
  '    "one open EUR_USD/H1 position -- index.html:4314 is what prevents the second");\n' +
  // SCOPE LIMIT, stated so this suite is not read as covering the identity-drift defect.
  '  g.record("RE-7","SCOPE: these ticks share one identity, so they do NOT exercise the signal-drift defect",\n' +
  '    alexGSetupState.filter(function(x){return x.pair==="EUR_USD";}).map(alexGLiveSignalId)\n' +
  '      .every(function(id){ return alexGAutoTrading.tradedSignals[id]===true; }),\n' +
  '    "identity is stable within a session; drift needs a candle-window shift (see report 2.16)");\n' +
  // ══ MARKET-DATA COMPLETENESS GATE (MOGO-021 DECISION 1) ═══════════════════════════════════════
  // THE DEFECT. fetchAlexGReplayDatasets(oPair,90) fetches by fixed COUNT -- 2220 H1, 600 H4, 150 D,
  // 73 W -- and fetchCandlesRange used to `break` on the first short page and then classify that
  // short accumulation COMPLETE, reasoning that a short page means the broker has no more history.
  // A broker that returns 148 daily candles when asked for 150 is indistinguishable at that point
  // from one that has genuinely run out, and because the fetch is by COUNT, stopping two candles
  // early moves the window START off a bar boundary. That re-anchors ALEX's zone identity in the
  // middle of the staleness window -- where a whole-bar roll can never land -- and every
  // duplicate-trade guard misses. Reproduced: 148-of-150 opened a SECOND real paper position where
  // a full-count control blocked the same setup as DUPLICATE.
  //
  // THE REPAIR HAS TWO HALVES AND BOTH ARE PROVEN HERE, NOT JUST THE SUPPRESSION HALF:
  //   1. fetchCandlesRange CONTINUES past a short page, so a shortfall more history can satisfy is
  //      REPAIRED rather than merely detected (MDC-15, MDC-18), and only REACHED_COUNT or a
  //      genuinely empty continuation now satisfy the request (MDC-16).
  //   2. alexGEvaluatePairForLiveSetups gates on marketDataCompletenessOf()===COMPLETE for ALL FOUR
  //      required timeframes and otherwise suppresses THAT PAIR ONLY (MDC-4..MDC-14, MDC-17).
  //
  // THE ONLY SEAM IS THE BROKER'S PAGING. For every suppression fixture the plan serves the
  // IDENTICAL candle array the healthy control is served (g.htf(...)), changing only what the
  // broker does on the &to= continuation -- so the data the frozen engine would see is unchanged
  // and the fixture isolates the completeness contract itself, not a different market.
  '  RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=false;\n' +
  // Every suppression this gate can produce, read off the decision bus by SOURCE rather than by
  // reason code alone -- DATA_CANDLES_UNAVAILABLE is also emitted by an unrelated JVM mapping.
  '  function suppressions(){ return decisionEventLog.filter(function(e){\n' +
  '    return e.eventType==="ENGINE_ERROR"&&e.source==="alexGEvaluatePairForLiveSetups"&&\n' +
  '      (e.reasonCode==="DATA_TIMEFRAME_INCOMPLETE"||e.reasonCode==="DATA_CANDLES_UNAVAILABLE"); }); }\n' +
  // ── HEALTHY CONTROL. Nothing planned: one page per granularity, then an exhausted continuation.
  '  g.setPlan(null); g.setT0(t0); g.setH1(g.build(t0)); g.setBidAsk({bid:1.10595,ask:1.10605});\n' +
  '  fullReset(); alexGIdentityDriftReported=new Set();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("MDC-1","COMPLETE W/D/H4/H1 permits normal evaluation -- a real paper position opens end-to-end",\n' +
  '    alexGAccount.openPositions.length===1&&alexGJournalEntries.length===1,\n' +
  '    "open="+alexGAccount.openPositions.length+" journal="+alexGJournalEntries.length);\n' +
  // The anti-over-blocking control, and it matters as much as the suppression fixtures: a gate that
  // blocks healthy data is a trading defect in the other direction.
  '  g.record("MDC-2","ANTI-OVER-BLOCKING: healthy data suppresses NOTHING, on any of the twelve instruments",\n' +
  '    suppressions().length===0&&(g.lastObs().instrumentsEvaluated||[]).length===SCAN_PAIRS.length&&\n' +
  '    alexGSetupState.filter(function(x){return x.pair==="EUR_USD";}).length===1,\n' +
  '    "0 suppressions across "+((g.lastObs().instrumentsEvaluated)||[]).length+"/12 instruments, setup still derived");\n' +
  // ── A HEALTHY FULL-COUNT FETCH. 73 is fetchAlexGReplayDatasets' own W count for days=90, so this
  // is the real request being fully satisfied -- REACHED_COUNT rather than exhaustion -- reached
  // only BECAUSE the walk continued past a short first page.
  '  const w73=g.flat(t0-73*7*24*3600000,73,7*24*3600000);\n' +
  '  g.setPlan({inst:"EUR_USD",gran:"W",pages:[w73.slice(2),w73.slice(0,2)],then:"EMPTY"});\n' +
  '  fullReset();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("MDC-3","a FULL-COUNT walk (73 of 73 W, reached only by walking past a short page) still trades",\n' +
  '    alexGAccount.openPositions.length===1&&suppressions().length===0,\n' +
  '    "open="+alexGAccount.openPositions.length+", 0 suppressions on a request that was fully satisfied");\n' +
  // ── PER-TIMEFRAME SUPPRESSION. Same candles as the healthy control; the continuation fails, so
  // the shortfall is not satisfiable and the dataset is PARTIAL rather than COMPLETE.
  '  g.setPlan({inst:"EUR_USD",gran:"H4",pages:[g.htf("H4")],then:"HTTP_ERROR"});\n' +
  '  fullReset();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const h4Sup=suppressions();\n' +
  '  g.record("MDC-4","INCOMPLETE H4 suppresses evaluation of that pair -- and no position opens",\n' +
  '    h4Sup.length===1&&h4Sup[0].pair==="EUR_USD"&&\n' +
  '    (h4Sup[0].context||{}).incompleteTimeframes.join(",")==="H4"&&\n' +
  '    alexGAccount.openPositions.length===0,\n' +
  '    "incompleteTimeframes="+JSON.stringify((h4Sup[0]||{}).context&&h4Sup[0].context.incompleteTimeframes)+" open="+alexGAccount.openPositions.length);\n' +
  '  g.setPlan({inst:"EUR_USD",gran:"D",pages:[g.htf("D")],then:"HTTP_ERROR"});\n' +
  '  fullReset();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const dSup=suppressions(); const dPipe=(g.lastPipeline()||[]).filter(function(r){return r&&r.stage==="DATA_INCOMPLETE";});\n' +
  '  g.record("MDC-5","INCOMPLETE D suppresses evaluation of that pair -- and no position opens",\n' +
  '    dSup.length===1&&dSup[0].pair==="EUR_USD"&&\n' +
  '    (dSup[0].context||{}).incompleteTimeframes.join(",")==="D"&&\n' +
  '    alexGAccount.openPositions.length===0,\n' +
  '    "incompleteTimeframes="+JSON.stringify((dSup[0]||{}).context&&dSup[0].context.incompleteTimeframes)+" open="+alexGAccount.openPositions.length);\n' +
  // The engine is never handed the data at all -- MDC-2 proves the same tick derives a setup when
  // the data IS complete, so an empty setup list here is suppression, not an absent opportunity.
  '  g.record("MDC-6","the suppressed pair is never handed to the FROZEN engine -- no setup is derived from it",\n' +
  '    alexGSetupState.filter(function(x){return x.pair==="EUR_USD";}).length===0&&\n' +
  '    alexGJournalEntries.length===0,\n' +
  '    "EUR_USD setups=0 where the identical healthy tick (MDC-2) derives 1");\n' +
  '  g.setPlan({inst:"EUR_USD",gran:"W",pages:[g.htf("W")],then:"HTTP_ERROR"});\n' +
  '  fullReset();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const wSup=suppressions();\n' +
  '  g.record("MDC-7","INCOMPLETE W suppresses evaluation of that pair -- and no position opens",\n' +
  '    wSup.length===1&&wSup[0].pair==="EUR_USD"&&\n' +
  '    (wSup[0].context||{}).incompleteTimeframes.join(",")==="W"&&\n' +
  '    alexGAccount.openPositions.length===0,\n' +
  '    "incompleteTimeframes="+JSON.stringify((wSup[0]||{}).context&&wSup[0].context.incompleteTimeframes)+" open="+alexGAccount.openPositions.length);\n' +
  // ── TRANSPORT vs CONTRACT. The same timeframe, the same gate, two materially different facts:
  // above, the data ARRIVED and did not satisfy the contract (PARTIAL); here it never arrived at
  // all (UNAVAILABLE). An operator who cannot tell those apart cannot act on either.
  '  g.setPlan({inst:"EUR_USD",gran:"D",pages:[],then:"HTTP_ERROR"});\n' +
  '  fullReset();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const xSup=suppressions(); const xctx=(xSup[0]||{}).context||{};\n' +
  '  g.record("MDC-8","TRANSPORT FAILURE reads as UNAVAILABLE and reports DATA_CANDLES_UNAVAILABLE",\n' +
  '    xSup.length===1&&xSup[0].reasonCode==="DATA_CANDLES_UNAVAILABLE"&&\n' +
  '    (xctx.completenessByTimeframe||{}).D==="UNAVAILABLE"&&alexGAccount.openPositions.length===0,\n' +
  '    "reasonCode="+(xSup[0]||{}).reasonCode+" D="+((xctx.completenessByTimeframe||{}).D));\n' +
  '  g.record("MDC-9","the two facts DO NOT share a code -- a merely-short dataset reports DATA_TIMEFRAME_INCOMPLETE",\n' +
  '    (dSup[0]||{}).reasonCode==="DATA_TIMEFRAME_INCOMPLETE"&&\n' +
  '    (xSup[0]||{}).reasonCode==="DATA_CANDLES_UNAVAILABLE"&&\n' +
  '    (dSup[0]||{}).reasonCode!==(xSup[0]||{}).reasonCode&&\n' +
  '    !!REASON_CODE_REGISTRY.DATA_TIMEFRAME_INCOMPLETE,\n' +
  '    "PARTIAL -> "+(dSup[0]||{}).reasonCode+" vs UNAVAILABLE -> "+(xSup[0]||{}).reasonCode);\n' +
  // ── DECISION EVIDENCE. What was suppressed, why, and on which timeframes -- asserted on the
  // event the gate actually emitted and on the row the REAL durable builder actually produced.
  '  const dctx2=(dSup[0]||{}).context||{};\n' +
  '  g.record("MDC-10","the suppression is RECORDED as an ENGINE_ERROR at the market-data stage, not silently dropped",\n' +
  '    (dSup[0]||{}).eventType==="ENGINE_ERROR"&&(dSup[0]||{}).stage==="MARKET_DATA_FETCH"&&\n' +
  '    (dSup[0]||{}).severity==="ERROR"&&/did not satisfy the completeness contract/.test(String((dSup[0]||{}).reasonText)),\n' +
  '    "stage="+(dSup[0]||{}).stage+" severity="+(dSup[0]||{}).severity);\n' +
  '  g.record("MDC-11","the evidence NAMES the failing timeframe and reports the state of ALL FOUR",\n' +
  '    JSON.stringify(dctx2.incompleteTimeframes)===JSON.stringify(["D"])&&\n' +
  '    (dctx2.completenessByTimeframe||{}).D==="PARTIAL"&&\n' +
  '    (dctx2.completenessByTimeframe||{}).W==="COMPLETE"&&\n' +
  '    (dctx2.completenessByTimeframe||{}).H4==="COMPLETE"&&\n' +
  '    (dctx2.completenessByTimeframe||{}).H1==="COMPLETE",\n' +
  '    JSON.stringify(dctx2.completenessByTimeframe));\n' +
  '  g.record("MDC-12","and it survives the DURABLE pipeline builder as a DATA_INCOMPLETE stage",\n' +
  '    dPipe.length===1&&dPipe[0].pair==="EUR_USD"&&dPipe[0].timeframe==="D"&&\n' +
  '    dPipe[0].reason==="DATA_TIMEFRAME_INCOMPLETE"&&/INCOMPLETE MARKET DATA/.test(String(dPipe[0].status)),\n' +
  '    "stage=DATA_INCOMPLETE pair="+(dPipe[0]||{}).pair+" tf="+(dPipe[0]||{}).timeframe+" reason="+(dPipe[0]||{}).reason);\n' +
  // ── SCOPE. Suppression is per-pair. Planned on GBP_USD, so the instrument under test is a
  // DIFFERENT one from the instrument that must still trade in the very same tick.
  '  g.setPlan({inst:"GBP_USD",gran:"D",pages:[g.htf("D")],then:"HTTP_ERROR"});\n' +
  '  fullReset();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const iSup=suppressions();\n' +
  '  g.record("MDC-13","SCOPE: one incomplete instrument does not suppress the others -- EUR_USD still trades on that tick",\n' +
  '    iSup.length===1&&iSup[0].pair==="GBP_USD"&&alexGAccount.openPositions.length===1&&\n' +
  '    alexGAccount.openPositions[0].pair==="EUR_USD"&&\n' +
  // MOGO-021: this asserted 12/12 EVALUATED while one instrument was suppressed -- which was only
  // ever true because the poll ledger counted an ATTEMPT as an evaluation. The ledger is now honest,
  // so the correct assertion is 11 evaluated + the suppressed one named in instrumentsSkipped, and
  // every configured instrument still accounted for. Scope is what this fixture is about, and scope
  // is still proved: the other eleven were unaffected and EUR_USD traded on the same tick.
  '    (g.lastObs().instrumentsEvaluated||[]).length===SCAN_PAIRS.length-1&&\n' +
  '    (g.lastObs().instrumentsEvaluated||[]).indexOf("GBP_USD")===-1&&\n' +
  '    (g.lastObs().instrumentsSkipped||[]).some(function(x){return x.pair==="GBP_USD";})&&\n' +
  '    (g.lastObs().instrumentsEvaluated||[]).length+(g.lastObs().instrumentsSkipped||[]).length===SCAN_PAIRS.length,\n' +
  '    "suppressed="+(iSup[0]||{}).pair+" while EUR_USD opened a position; "+\n' +
  '    ((g.lastObs().instrumentsEvaluated)||[]).length+" evaluated + "+\n' +
  '    ((g.lastObs().instrumentsSkipped)||[]).length+" skipped = "+SCAN_PAIRS.length+" configured");\n' +
  // instrumentsAttempted is the DISPATCH list. It used to be derived from instrumentsEvaluated, so
  // the two were identical by construction and neither could ever reveal a suppressed instrument.
  '  g.record("MDC-13b","instrumentsAttempted counts the DISPATCH, so a suppressed instrument is visible rather than absorbed",\n' +
  '    g.lastObs().instrumentsAttempted===SCAN_PAIRS.length&&\n' +
  '    g.lastObs().instrumentsAttempted>(g.lastObs().instrumentsEvaluated||[]).length,\n' +
  '    "attempted="+g.lastObs().instrumentsAttempted+" evaluated="+((g.lastObs().instrumentsEvaluated)||[]).length+\n' +
  '    " (a count derived from the evaluated list would have reported "+((g.lastObs().instrumentsEvaluated)||[]).length+")");\n' +
  // ── RESTART / RECOVERY under the gate. The trade is closed first, for the same reason E2E-11
  // states: with it open the pair+timeframe overlap rule blocks any re-open and the real guards are
  // never reached. What this adds is that the gate must not change the answer in either direction --
  // the setup must still be RE-DERIVED (so it genuinely reached the duplicate check) and must not
  // be traded again.
  '  g.setPlan(null);\n' +
  '  fullReset();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const rstPos=alexGAccount.openPositions[0]||null;\n' +
  '  if(rstPos) closeOpenPosition();\n' +
  '  freshSession();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("MDC-14","RESTART/RECOVERY: after a cleared session the setup is re-derived, NOT suppressed, and NOT re-traded",\n' +
  '    !!rstPos&&suppressions().length===0&&\n' +
  '    alexGSetupState.filter(function(x){return x.pair==="EUR_USD";}).length===1&&\n' +
  '    alexGAccount.openPositions.length===0&&alexGAccount.closedPositions.length===1&&\n' +
  '    alexGJournalEntries.length===1,\n' +
  '    "setup re-derived and passed the gate; open=0 closed=1 journal=1, 0 suppressions");\n' +
  // ── THE WALK ITSELF, at fetchCandlesRange level, where the count and the termination reason are
  // directly observable. 73 is the real W request for days=90.
  '  g.setPlan({inst:"EUR_USD",gran:"W",pages:[w73.slice(2),w73.slice(0,2)],then:"EMPTY"});\n' +
  '  const r15=await fetchCandlesRange("EUR_USD","W",73);\n' +
  '  const m15=r15||{};\n' +
  // The head of the accumulation is the assertion that matters: the two candles the short page
  // omitted are the OLDEST ones, so recovering them is precisely what keeps the window START where
  // it was. A walk that stopped at the short page would start two bars later -- the re-anchor.
  '  g.record("MDC-15","REPAIR: a short page followed by AVAILABLE history is walked past and the COUNT IS REACHED",\n' +
  '    marketDataCompletenessOf(r15)===MARKET_DATA_COMPLETENESS.COMPLETE&&r15.length===73&&\n' +
  '    m15.paginationTerminationReason==="REACHED_COUNT"&&m15.shortPages===1&&m15.pagesReceived===2&&\n' +
  '    r15[0].t.getTime()===w73[0].t.getTime(),\n' +
  '    "received="+r15.length+"/73 termination="+m15.paginationTerminationReason+" shortPages="+m15.shortPages+\n' +
  '    " -- window START unmoved, so the identity cannot re-anchor");\n' +
  '  g.setPlan({inst:"EUR_USD",gran:"W",pages:[w73.slice(2)],then:"EMPTY"});\n' +
  '  const r16=await fetchCandlesRange("EUR_USD","W",73);\n' +
  '  const m16=r16||{};\n' +
  '  g.record("MDC-16","EXHAUSTION: a short page followed by an EMPTY continuation is COMPLETE though short",\n' +
  '    marketDataCompletenessOf(r16)===MARKET_DATA_COMPLETENESS.COMPLETE&&r16.length===71&&\n' +
  '    m16.paginationTerminationReason==="EMPTY_PAGE"&&m16.shortPages===1,\n' +
  '    "received="+r16.length+"/73 termination="+m16.paginationTerminationReason+\n' +
  '    " -- a window pinned at the true start of history cannot move, so it is safe to evaluate");\n' +
  // ══ THE HEADLINE: A SHORT BROKER PAGE CANNOT CREATE A DUPLICATE OPPORTUNITY ═══════════════════
  // Reconstructed on the same organic machinery DRIFT-12 uses, and it is the same window shift:
  // the six-touch series minus its two oldest H1 bars re-anchors the zone, because the first
  // touch's own ATR slice falls two candles short and the frozen confirmation path can no longer
  // accept it. Here that two-bar shift arrives the way PRODUCTION produced it -- as a SHORT BROKER
  // PAGE -- rather than by slicing the fixture's own series. Nothing is hand-edited: the trade, the
  // close and the second poll are all real.
  //
  // WHAT THIS FIXTURE CAN AND CANNOT DISCRIMINATE, stated plainly rather than implied. Since
  // Decisions 2+3 landed, "no second position" is OVER-DETERMINED: the decided-authority refuses
  // the duplicate as well. Mutation-established, not assumed -- with the gate reverted ALONE the
  // second position still does not open, so open===0 alone would be a vacuous assertion here. The
  // observable that belongs to DECISION 1 is that the truncated window never reaches the FROZEN
  // ENGINE AT ALL: no setup is derived and the suppression is recorded. Both of those die under a
  // reverted gate and under a restored short-page break. And the scenario is a genuine
  // duplicate-generator: with BOTH the gate and the decided-authority removed, this same short page
  // opens a SECOND real position -- which is the defect exactly as it was reproduced.
  '  g.setPlan(null); fullReset(); alexGIdentityDriftReported=new Set();\n' +
  '  const tShort=nowMs-68*3600000-5*60000;\n' +   // the sixth touch qualifies ~5 min ago
  '  const h1Short=g.build6(tShort);\n' +
  '  g.setT0(tShort); g.setH1(h1Short);\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:tShort+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const shortPos=alexGAccount.openPositions[0]||null;\n' +
  '  g.record("MDC-17a","precondition: the unmodified engine opens ONE real position on the full window",\n' +
  '    alexGAccount.openPositions.length===1&&!!shortPos&&!!shortPos.zoneId,\n' +
  '    "open="+alexGAccount.openPositions.length+" signalId="+String(shortPos&&shortPos.signalId).slice(-24));\n' +
  '  if(shortPos) closeOpenPosition();\n' +
  // The broker now returns a page two candles short of what it holds and then FAILS the
  // continuation, so the shortfall cannot be repaired: the walk ends HTTP_ERROR and the dataset is
  // PARTIAL. Every stored record still carries poll 1's identity and no guard is disabled.
  '  g.setPlan({inst:"EUR_USD",gran:"H1",pages:[h1Short.slice(2)],then:"HTTP_ERROR"});\n' +
  '  freshSession();\n' +
  '  ["fxhub_alexg_account","fxhub_alexg_account_version"].forEach(function(k){ try{ localStorage.removeItem(k); }catch(e){} });\n' +
  '  alexGAccountKnownVersion=0;\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:tShort+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const sSup=suppressions();\n' +
  '  g.record("MDC-17","HEADLINE: a SHORT BROKER PAGE cannot create a duplicate opportunity -- the pair is suppressed",\n' +
  '    alexGAccount.openPositions.length===0&&alexGAccount.closedPositions.length===1&&\n' +
  '    sSup.length===1&&sSup[0].pair==="EUR_USD"&&sSup[0].reasonCode==="DATA_TIMEFRAME_INCOMPLETE"&&\n' +
  '    (sSup[0].context||{}).incompleteTimeframes.join(",")==="H1"&&\n' +
  '    alexGSetupState.filter(function(x){return x.pair==="EUR_USD";}).length===0,\n' +
  '    "open="+alexGAccount.openPositions.length+" closed="+alexGAccount.closedPositions.length+\n' +
  '    " -- the two-bar-short window never reaches the frozen engine: 0 setups derived, suppression recorded");\n' +
  // And the half that makes this a fix rather than a mute button: give the SAME short page a real
  // continuation and the walk recovers the two missing bars, so the window never moves, the engine
  // derives the SAME identity it traded, and the ordinary duplicate guard does its job.
  '  g.setPlan({inst:"EUR_USD",gran:"H1",pages:[h1Short.slice(2),h1Short.slice(0,2)],then:"EMPTY"});\n' +
  '  freshSession();\n' +
  '  ["fxhub_alexg_account","fxhub_alexg_account_version"].forEach(function(k){ try{ localStorage.removeItem(k); }catch(e){} });\n' +
  '  alexGAccountKnownVersion=0;\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:tShort+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  // The six-touch series qualifies several setups; the one that matters is the one that was
  // TRADED. If the window had moved, that identity would simply not be among the setups the engine
  // re-derives -- which is exactly what DRIFT-13 shows a two-bar roll does to it.
  '  const rSetups=alexGSetupState.filter(function(x){return x.pair==="EUR_USD";});\n' +
  '  const rMatch=rSetups.filter(function(x){return alexGLiveSignalId(x)===(shortPos||{}).signalId;});\n' +
  '  const rDecided=decisionEventLog.filter(function(e){return e.eventType==="CANDIDATE_REJECTED"&&\n' +
  '    e.reasonCode==="STATE_SIGNAL_ALREADY_DECIDED";});\n' +
  '  g.record("MDC-18","REPAIRED, NOT MUTED: the same short page with history behind it is walked past, the identity\\u2019s unchanged, and the duplicate guard holds",\n' +
  '    alexGAccount.openPositions.length===0&&alexGAccount.closedPositions.length===1&&\n' +
  '    suppressions().length===0&&!!shortPos&&rMatch.length===1&&\n' +
  '    rMatch[0].zoneId===shortPos.zoneId&&rDecided.length===1&&\n' +
  '    (rDecided[0].context||{}).identityDrifted===false,\n' +
  '    "0 suppressions; the TRADED identity is re-derived unchanged (zoneId and signalId both), and "+\n' +
  '    "the refusal reports identityDrifted=false -- the window never moved, so nothing had to be blocked");\n' +
  // ══ RELOAD + WEEKEND CLOSE-TIME RE-ESTIMATION: the DURABLE ECONOMIC term, end to end ══════
  // alexGFindPriorDecision's durable half has two OR-terms. The stableId term is exercised by
  // DRIFT-6/9b/12b, where a zone re-anchor leaves reactionId and qualificationTimestamp untouched.
  // The economicId term exists for the ONE case that term cannot cover: getCandleCloseTime returns
  // an ESTIMATE while a bar is still the newest, so every artifact anchored on the last bar of a
  // trading week has its close time move by ~48h when the market reopens -- moving reactionId AND
  // qualificationTimestamp together, two of the five components of the stable identity. Removing
  // the term survived the entire gate.
  //
  // Nothing about the trading path is disabled here. The reload is simulated the way this suite
  // already simulates one (freshSession clears the session maps), the persisted signal/trade marks
  // are cleared because a re-derivation under a shifted identity would not match them anyway, and
  // the surviving durable record is shifted BACK by one market gap so the setup the engine
  // re-derives really does differ from it in both fields. The stable term therefore cannot match,
  // and neither can the tradeId or signalId guards -- the economic term is the only thing left.
  '  RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=false;\n' +
  '  g.setPlan(null); g.setT0(t0); g.setH1(g.build(t0)); g.setBidAsk({bid:1.10595,ask:1.10605});\n' +
  '  fullReset(); alexGIdentityDriftReported=new Set();\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const wkPos=alexGAccount.openPositions[0]||null;\n' +
  '  g.record("RELOAD-1","precondition: a real position exists, carrying the economic fields the durable term reads",\n' +
  '    alexGAccount.openPositions.length===1&&!!wkPos&&typeof wkPos.qualificationClose==="number"&&\n' +
  '    typeof wkPos.reactionId==="string"&&typeof wkPos.qualificationTimestamp==="number",\n' +
  '    "qualificationClose="+String(wkPos&&wkPos.qualificationClose)+" on the stored position");\n' +
  '  if(wkPos) closeOpenPosition();\n' +
  // Shift the surviving record back by one market gap: the trailing anchor time inside reactionId
  // AND qualificationTimestamp, exactly the pair of fields the close-time re-estimation moves.
  // qualificationClose is a PRICE and is deliberately untouched -- that is what the economic
  // identity is built from.
  '  const wkStored=alexGAccount.closedPositions[0];\n' +
  '  const wkParts=String(wkStored.reactionId).split("|");\n' +
  '  wkParts[4]=String(Number(wkParts[4])-48*3600000);\n' +
  '  wkStored.reactionId=wkParts.join("|");\n' +
  '  wkStored.qualificationTimestamp=wkStored.qualificationTimestamp-48*3600000;\n' +
  '  wkStored.signalId="AGL|PREWEEKEND|"+wkStored.signalId;\n' +
  '  wkStored.tradeId="AGT|PREWEEKEND|"+wkStored.tradeId;\n' +
  '  alexGJournalEntries=[];\n' +
  '  alexGAutoTrading.tradedSignals={};\n' +
  '  freshSession();\n' +
  '  ["fxhub_alexg_account","fxhub_alexg_account_version"].forEach(function(k){ try{ localStorage.removeItem(k); }catch(e){} });\n' +
  '  alexGAccountKnownVersion=0;\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  const wkSetup=alexGSetupState.filter(function(x){return x.pair==="EUR_USD";})[0]||null;\n' +
  '  const wkDecided=decisionEventLog.filter(function(e){return e.eventType==="CANDIDATE_REJECTED"&&\n' +
  '    e.reasonCode==="STATE_SIGNAL_ALREADY_DECIDED";});\n' +
  '  g.record("RELOAD-2","the re-derivation differs in BOTH drifting components, so ONLY the economic identity can match",\n' +
  '    !!wkSetup&&wkSetup.reactionId!==wkStored.reactionId&&\n' +
  '    wkSetup.qualificationTimestamp!==wkStored.qualificationTimestamp&&\n' +
  '    alexGStableSetupIdentity(wkSetup)!==alexGStableSetupIdentity(wkStored)&&\n' +
  '    alexGEconomicSetupIdentity(wkSetup)===alexGEconomicSetupIdentity(wkStored)&&\n' +
  '    alexGLiveSignalId(wkSetup)!==wkStored.signalId,\n' +
  '    "stable identities differ, economic identity holds ("+alexGEconomicSetupIdentity(wkSetup)+")");\n' +
  '  g.record("RELOAD-3","AFTER A RELOAD the weekend-shifted setup is still REFUSED -- from the durable record alone",\n' +
  '    alexGAccount.openPositions.length===0&&alexGAccount.closedPositions.length===1&&\n' +
  '    Object.keys(alexGAutoTrading.tradedSignals).length===0&&alexGJournalEntries.length===0&&\n' +
  '    wkDecided.length===1&&(wkDecided[0].context||{}).matchSource==="durable"&&\n' +
  '    (wkDecided[0].context||{}).matchedBy==="economicId"&&\n' +
  '    (wkDecided[0].context||{}).identityDrifted===true,\n' +
  '    "open="+alexGAccount.openPositions.length+" with the session maps empty, no tradedSignals and no "+\n' +
  '    "journal -- refused via matchedBy="+String((wkDecided[0]||{}).context&&wkDecided[0].context.matchedBy)+\n' +
  '    " from source="+String((wkDecided[0]||{}).context&&wkDecided[0].context.matchSource));\n' +
  // ══ A THROW AFTER THE FROZEN ENGINE RAN MUST NOT REPORT THE PAIR AS SKIPPED ═══════════════
  // __engineRan is set immediately after alexGRunSetupEngine, and the catch returns
  // {evaluated:__engineRan}. Reverting it to {evaluated:false} survived the entire gate -- yet that
  // is the case where the ledger would claim an instrument was NOT evaluated while a real paper
  // position for it is durably recorded. A coverage row contradicting a trade record is not a safe
  // under-report, it is a wrong one.
  //
  // The fault is injected at showAlexGLiveToast, a UI call that runs AFTER the ledger commit, the
  // tradedSignals mark and saveAlexG -- so the position genuinely exists when the throw happens.
  // No trading function is stubbed, reordered or weakened; a rendering call is made to fail.
  '  g.setPlan(null); g.setT0(t0); g.setH1(g.build(t0)); g.setBidAsk({bid:1.10595,ask:1.10605});\n' +
  '  fullReset(); alexGIdentityDriftReported=new Set();\n' +
  '  const __origToast=showAlexGLiveToast;\n' +
  '  showAlexGLiveToast=function(){ throw new Error("fixture fault downstream of the frozen engine"); };\n' +
  '  alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}};\n' +
  '  await alexGLivePollTick();\n' +
  '  showAlexGLiveToast=__origToast;\n' +
  '  const thrObs=g.lastObs();\n' +
  '  const thrErr=decisionEventLog.filter(function(e){return e.eventType==="ENGINE_ERROR"&&\n' +
  '    e.source==="alexGEvaluatePairForLiveSetups"&&e.reasonCode==="SYSTEM_UNEXPECTED_ERROR"&&e.pair==="EUR_USD";});\n' +
  '  g.record("THROW-1","precondition: the throw really happened AND a real position was durably opened first",\n' +
  '    thrErr.length===1&&alexGAccount.openPositions.length===1&&alexGJournalEntries.length===1&&\n' +
  '    Object.keys(alexGAutoTrading.tradedSignals).length===1,\n' +
  '    "1 SYSTEM_UNEXPECTED_ERROR for EUR_USD, with open=1 journal=1 tradedSignals=1 already committed");\n' +
  '  g.record("THROW-2","the ledger reports that pair as EVALUATED, not skipped -- coverage must not contradict a trade record",\n' +
  '    (thrObs.instrumentsEvaluated||[]).indexOf("EUR_USD")!==-1&&\n' +
  '    !(thrObs.instrumentsSkipped||[]).some(function(x){return x.pair==="EUR_USD";})&&\n' +
  '    (thrObs.instrumentsEvaluated||[]).length===SCAN_PAIRS.length,\n' +
  '    "instrumentsEvaluated="+((thrObs.instrumentsEvaluated)||[]).length+"/"+SCAN_PAIRS.length+\n' +
  '    ", EUR_USD present and absent from instrumentsSkipped despite the throw");\n' +
  '  g.record("THROW-3","and the scan itself is unaffected: the other eleven are still covered on that tick",\n' +
  '    (thrObs.instrumentsSkipped||[]).length===0&&thrObs.instrumentsAttempted===SCAN_PAIRS.length&&\n' +
  '    decisionEventLog.some(function(e){return e.eventType==="SCAN_COMPLETED";}),\n' +
  '    "attempted="+thrObs.instrumentsAttempted+" skipped="+((thrObs.instrumentsSkipped)||[]).length+\n' +
  '    " -- the swallow-and-continue behaviour is unchanged, only the attribution is honest");\n' +
  '  g.setPlan(null); g.setT0(t0); g.setH1(g.build(t0));\n' +
  '  RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=__suspendWas;\n' +
  '  g.record("E2E-17","the suspension flag is RESTORED -- this suite leaves production policy as it found it",\n' +
  '    RULES_ALEXG_V11.v11Config.setupSuspensionEnabled===true,\n' +
  '    "setupSuspensionEnabled="+RULES_ALEXG_V11.v11Config.setupSuspensionEnabled);\n' +
  // ══ MOGO-021 -- OVERLAPPING TICKS MUST NOT RE-ROLL A PERMANENT REJECTION ══
  // alexGLivePollTick has no re-entrancy guard and is driven by setInterval, and the duplicate gate
  // is consulted BEFORE the trade attempt while the decision is recorded only AFTER it -- with an
  // `await fetchBidAsk` in between. Two in-flight ticks therefore both passed the gate for the same
  // signalId: tick 1 was blocked by the price-dependent entry-delay gate and recorded a PERMANENT
  // rejection, while tick 2 -- already past the gate -- re-evaluated the SAME setup against a FRESH
  // bid/ask and opened a real position the sequential path refuses.
  //
  // No existing guard could catch it: every duplicate check looks for an EXISTING position, and tick
  // 1 never opened one. It is not a duplicate trade, it is an EXTRA trade past a permanent rejection.
  //
  // The bid/ask is the ONLY seam: the first call returns a price far from qualificationClose (so the
  // frozen entry-delay rule blocks of its own accord) and every later call a good one. No rule,
  // threshold or protected function is touched -- the candles and the price are constructed, every
  // verdict is the strategy's own.
  '  RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=false;\n' +
  '  const __origFBA2=fetchBidAsk; let __ban2=0;\n' +
  '  fetchBidAsk=async function(p){ __ban2++; return __ban2===1?{bid:1.20000,ask:1.20010}:{bid:1.10595,ask:1.10605}; };\n' +
  '  fullReset(); alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}}; __ban2=0;\n' +
  '  await alexGLivePollTick();\n' +
  '  const seqAfter1=alexGAccount.openPositions.length;\n' +
  '  const seqChain=decisionEventLog.map(function(e){return e.eventType+"/"+(e.reasonCode||"-");}).join(",");\n' +
  '  await alexGLivePollTick();\n' +
  '  const seqOpen=alexGAccount.openPositions.length;\n' +
  '  g.record("CONCUR-1","CONTROL (sequential): a price far from the signal blocks the open on poll 1",\n' +
  '    seqAfter1===0&&/ENTRY_MOVED/.test(seqChain),\n' +
  '    "open after poll 1="+seqAfter1+" entryMovedRecorded="+/ENTRY_MOVED/.test(seqChain));\n' +
  '  g.record("CONCUR-2","CONTROL (sequential): poll 2 with a GOOD price still opens nothing -- the block was PERMANENT",\n' +
  '    seqOpen===0,"openPositions after a second poll="+seqOpen);\n' +
  '  fullReset(); alexGLastEvaluatedCloseTime={EUR_USD:{H1:t0+40*3600000}}; __ban2=0;\n' +
  '  const pA=alexGLivePollTick(); const pB=alexGLivePollTick();\n' +
  '  await Promise.all([pA,pB]);\n' +
  '  const ovOpen=alexGAccount.openPositions.length;\n' +
  '  const ovPos=alexGAccount.openPositions[0]||null;\n' +
  '  g.record("CONCUR-3","OVERLAPPING ticks must NOT open a position the sequential path refused",\n' +
  '    ovOpen===0,\n' +
  '    "sequential opened 0; overlapping opened "+ovOpen+\n' +
  '    (ovPos?(" -- entry="+ovPos.entry+" stop="+ovPos.stop+" target="+ovPos.target+" risk=$"+ovPos.riskAmount):""));\n' +
  '  const cBlocked=decisionEventLog.filter(function(e){return e.reasonCode==="ENTRY_MOVED_TOO_FAR_FROM_SIGNAL";}).length;\n' +
  '  const cOpened=decisionEventLog.filter(function(e){return e.eventType==="TRADE_OPENED";}).length;\n' +
  '  g.record("CONCUR-4","the SAME setup is never both BLOCKED and OPENED within one H1 boundary",\n' +
  '    cBlocked===0||cOpened===0,\n' +
  '    "ENTRY_MOVED rejections="+cBlocked+" TRADE_OPENED="+cOpened+" (both non-zero means the gate was re-rolled)");\n' +
  '  const claimed=decisionEventLog.filter(function(e){ return e.reasonCode==="STATE_SIGNAL_ALREADY_DECIDED"\n' +
  '    &&e.context&&e.context.matchedBy==="inFlight"; }).length;\n' +
  '  g.record("CONCUR-5","and the second tick is refused by the IN-FLIGHT claim, recorded as such for audit",\n' +
  '    claimed>0,"STATE_SIGNAL_ALREADY_DECIDED events attributed to matchedBy=inFlight: "+claimed);\n' +
  '  fetchBidAsk=__origFBA2;\n' +
  '  RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=true;\n' +
  '  g.record("CONCUR-6","and this block leaves production policy exactly as it found it",\n' +
  '    RULES_ALEXG_V11.v11Config.setupSuspensionEnabled===true&&fetchBidAsk===__origFBA2,\n' +
  '    "suspension restored and the bid/ask seam removed");\n' +
  '  return g;\n})();'
);

// Capture the durable observation the poll hands to the ledger, built through the REAL builder.
wrapped.__hook=true;
wrapped(g).then(function(){
  let pass=0,fail=0;
  results.forEach(function(r){
    if(r.pass){pass++;console.log('PASS -- '+r.id+': '+r.desc+(r.detail?'  ['+r.detail+']':''));}
    else{fail++;console.log('FAIL -- '+r.id+': '+r.desc+(r.detail?'  ['+r.detail+']':''));}
  });
  console.log('---');
  console.log(results.length+' fixtures, '+pass+' PASS, '+fail+' FAIL');
}).catch(function(e){
  console.log('EXECUTION ERROR: '+(e&&e.message?e.message:String(e)));
  console.log('---');
  console.log(results.length+' fixtures, 0 PASS, '+(results.length||1)+' FAIL');
});
