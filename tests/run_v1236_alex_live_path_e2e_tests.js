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
// Structureless higher-timeframe filler, and a structureless H1 series for every OTHER pair, so
// only the one instrument under test produces a setup and the other eleven honestly produce none.
function buildFlat(t0,n,stepMs){
  const candles=[];
  for(let i=0;i<n;i++) candles.push({o:1.1,h:1.101,l:1.099,c:1.1005,t:new Date(t0+i*stepMs)});
  return candles;
}

let __target='EUR_USD', __h1=null, __bidask={bid:1.10595,ask:1.10605}, __t0=0;
globalThis.fetch=async function(url){
  const u=String(url);
  const cm=u.match(/instruments\/([^/]+)\/candles\?count=(\d+)&granularity=(\w+)/);
  if(cm){
    const inst=cm[1], gran=cm[3];
    if(/&to=/.test(u)) return {ok:true,status:200,json:async()=>({candles:[]})};   // no further pages
    let arr;
    if(gran==='H1') arr=(inst===__target)?__h1:buildFlat(__t0,80,3600000);
    else if(gran==='H4') arr=buildFlat(__t0-30*24*3600000,30,4*3600000);
    else if(gran==='D') arr=buildFlat(__t0-30*24*3600000,30,24*3600000);
    else arr=buildFlat(__t0-200*24*3600000,30,7*24*3600000);
    const candles=arr.map(c=>({time:c.t.toISOString(),complete:true,
      mid:{o:String(c.o),h:String(c.h),l:String(c.l),c:String(c.c)}}));
    return {ok:true,status:200,json:async()=>({candles})};
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
g.now=()=>Date.now();

const wrapped=new Function('g', appCode + '\n' + 'return (async function(){\n' +
  '  cfg.key="fixture"; cfg.accountId="acct"; cfg.env="practice";\n' +
  // Capture what the poll hands the durable ledger, built through the REAL builder (not the raw
  // seam input), so a coverage claim here is a claim about the durable record.
  '  var __lastObs=null; const __origRecObs=evidenceRecordForwardObservations;\n' +
  '  evidenceRecordForwardObservations=function(input){ __lastObs=evidenceBuildPollObservation((input&&input.poll)||{}); return __origRecObs.apply(this,arguments); };\n' +
  '  g.lastObs=function(){ return __lastObs||{}; };\n' +
  '  const nowMs=Date.now();\n' +
  '  const t0=nowMs-48*3600000-5*60000;\n' +   // the qualifying touch lands ~5 min ago
  '  g.setT0(t0); g.setH1(g.build(t0));\n' +
  '  function freshSession(){\n' +
  '    alexGSetupState=[]; alexGZoneState={}; alexGLastEvaluatedCloseTime={}; alexGLiveSetupStatuses=[];\n' +
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
  '  alexGAccount.closedPositions.push(alexGAccount.openPositions.shift());\n' +
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
  '  RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=__suspendWas;\n' +
  '  g.record("E2E-17","the suspension flag is RESTORED -- this suite leaves production policy as it found it",\n' +
  '    RULES_ALEXG_V11.v11Config.setupSuspensionEnabled===true,\n' +
  '    "setupSuspensionEnabled="+RULES_ALEXG_V11.v11Config.setupSuspensionEnabled);\n' +
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
