// Forward-coverage observability fixture.
//
// PURPOSE
// This suite was written against a MOGO-020 premise that has since been RETRACTED. The original
// claim -- "EUR_USD produced zero poll appearances and zero evaluations, while GBP_USD was
// attempted ~once per H1 boundary" -- is FALSE, and the asymmetry it asserted never existed.
// Read directly from the durable ledger across 67 advancing polls, instrumentsEvaluated shows
// GBP_USD 61 and EUR_USD 61: identical, and in line with every peer. EUR_USD was never starved
// and was never missing from the poll. See MOGO_021_FORWARD_TRADING_RELIABILITY.md section 2.10.
//
// What was really happening is the STATUS-RING TRUNCATION BIAS proved by BIAS-1..5 at the end of
// this file: alexGLiveSetupStatuses is a 300-entry ring that cannot hold one scan cycle, so the
// pairs earliest in SCAN_PAIRS order never survive into the durable `statuses` array. A coverage
// claim read off that array under-reports them; a coverage claim read off instrumentsEvaluated
// does not, and instrumentsEvaluated was already present in the running build all along.
//
// The two silent paths below are nevertheless REAL and their fixtures remain valid -- they were
// simply not what happened to EUR_USD:
//
//   1. alexGEvaluatePairForLiveSetups() returned early on a short H1 dataset, recording nothing.
//   2. alexGLivePollTick() skipped a pair whose evaluation cursor had not fallen behind the
//      current H1 boundary, recording nothing.
//
// These fixtures prove both paths are now auditable. They assert ONLY observability: every
// strategy decision, threshold, rule and return value is unchanged, and the drift gate proves it
// (no protected function or constant is touched by the change these fixtures cover).
//
// Run from the project root:
//   osascript -l JavaScript tests/run_v1232_forward_coverage_observability_tests.js
// or simply:
//   tests/run_all.sh
//
// This runner opens NO browser, touches NO Chrome profile, performs NO real network I/O and
// writes NOTHING to disk. The only seam is globalThis.fetch, scripted in OANDA's own response
// shapes -- no application function is stubbed, mocked or re-implemented.
ObjC.import('Foundation');
function readFile(path){
  const s=$.NSString.stringWithContentsOfFileEncodingError(path,$.NSUTF8StringEncoding,null);
  const v=ObjC.unwrap(s);
  return v==null?'':v;
}
function extractScriptBody(html){
  const m=html.match(/<script>([\s\S]*)<\/script>/);
  if(!m) throw new Error('Could not find <script>...</script> body in index.html -- run this from the project root.');
  return m[1];
}
const html=readFile('./index.html');
const appCode=extractScriptBody(html);

const elMap={};
function makeClassList(){
  const classes=new Set();
  return{add:function(c){classes.add(c);},remove:function(c){classes.delete(c);},
    toggle:function(c,force){ if(force===undefined){ if(classes.has(c)) classes.delete(c); else classes.add(c); } else if(force) classes.add(c); else classes.delete(c); },
    contains:function(c){return classes.has(c);}};
}
function makeStub(){
  return {innerHTML:'',textContent:'',value:'',className:'',style:{},options:[{value:'All'}],width:100,height:100,disabled:false,checked:false,
    classList:makeClassList(),
    getContext:function(){return{clearRect:function(){},beginPath:function(){},moveTo:function(){},lineTo:function(){},stroke:function(){},fillRect:function(){},save:function(){},restore:function(){},setLineDash:function(){},arc:function(){},fill:function(){},closePath:function(){},fillText:function(){},measureText:function(){return{width:0};}};},
    appendChild:function(){},addEventListener:function(){},focus:function(){},setSelectionRange:function(){},click:function(){},files:[],
    getBoundingClientRect:function(){return{top:0,left:0,width:0,height:0};}};
}
const lsStore={};
globalThis.document={
  getElementById:function(id){ if(!elMap[id]) elMap[id]=makeStub(); return elMap[id]; },
  querySelector:function(){return null;},querySelectorAll:function(){return [];},
  createElement:function(){return makeStub();},addEventListener:function(){},
  visibilityState:'visible',body:{appendChild:function(){},removeChild:function(){}},activeElement:null
};
globalThis.window={devicePixelRatio:1};
globalThis.localStorage={
  getItem:function(k){return Object.prototype.hasOwnProperty.call(lsStore,k)?lsStore[k]:null;},
  setItem:function(k,v){lsStore[k]=String(v);},
  removeItem:function(k){delete lsStore[k];}
};
globalThis.alert=function(){};
globalThis.confirm=function(){return true;};
globalThis.Blob=function(parts,opts){return{parts,opts};};
globalThis.URL={createObjectURL:function(){return 'blob:stub';},revokeObjectURL:function(){}};
let __fakeTimerId=0;
globalThis.setTimeout=function(){return ++__fakeTimerId;};globalThis.clearTimeout=function(){};
globalThis.setInterval=function(){return ++__fakeTimerId;};globalThis.clearInterval=function(){};
globalThis.ResizeObserver=function(){return{observe:function(){},disconnect:function(){}};};
globalThis.LightweightCharts={LineStyle:{Solid:0,Dashed:1,Dotted:2},CrosshairMode:{Normal:0}};
globalThis.Notification=undefined;
// Controllable clock so an H1 boundary can be crossed deterministically. Installed BEFORE the app
// is evaluated so every Date.now() inside it observes the fixture's simulated time.
let __simNow=Date.UTC(2026,7,13,12,5,0);
const __RealDate=Date;
globalThis.Date=class extends __RealDate{
  constructor(...a){ if(a.length===0) super(__simNow); else super(...a); }
  static now(){ return __simNow; }
};
globalThis.indexedDB=undefined;   // durable ledger unavailable in-fixture; writer must stay non-throwing

let fetchScript=[],fetchIdx=0,fetchUrls=[];
let __badPair=null;
globalThis.fetch=function(url){
  fetchUrls.push(url);
  const step=fetchScript[fetchIdx]||fetchScript[fetchScript.length-1];
  fetchIdx++;
  if(!step) return Promise.reject(new Error('no scripted response'));
  return step();
};
function makeResponse(ok,status,body){
  return{ok:ok,status:status,json:function(){return Promise.resolve(body);},text:function(){return Promise.resolve('');}};
}
function candleArray(rawCount){
  const out=[];
  for(let i=0;i<rawCount;i++){
    const base=1.1000+i*0.0004;
    out.push({time:new Date(Date.UTC(2026,0,1,0,i)).toISOString(),complete:true,
      mid:{o:base.toFixed(5),h:(base+0.0012).toFixed(5),l:(base-0.0003).toFixed(5),c:(base+0.0009).toFixed(5)}});
  }
  return out;
}

// Realistic per-pair responses: hourly candles whose last COMPLETE candle closed on the most
// recent H1 boundary, exactly as OANDA returns them. Every pair gets identical, healthy data --
// so if any pair is still starved, the defect is in the loop, not the data.
function hourlyCandles(n,granMs){
  const out=[];
  const lastClose=Math.floor(__simNow/3600000)*3600000;   // most recent H1 boundary
  for(let i=n;i>=1;i--){
    const start=lastClose-i*granMs;
    const base=1.1000+(n-i)*0.0004;
    out.push({time:new Date(start).toISOString(),complete:true,
      mid:{o:base.toFixed(5),h:(base+0.0012).toFixed(5),l:(base-0.0003).toFixed(5),c:(base+0.0009).toFixed(5)}});
  }
  return out;
}
globalThis.fetch=function(url){
  fetchUrls.push(url);
  // MOGO-021: a continuation request (`&to=`) asks for history OLDER than what we already hold.
  // This stub previously ignored the cursor and replayed the same page, which was harmless only
  // because fetchCandlesRange used to stop at the first short page. Now that a short page is walked
  // past rather than treated as proof of exhaustion, ignoring `to` would hand the engine the same
  // candles over and over until the guard limit. A real broker returns nothing before the start of
  // its history, and that is what the v1236 harness already models -- so do the same here. This
  // makes the stub MORE faithful, not more permissive: an empty continuation is exactly the
  // EMPTY_PAGE signal that legitimately ends a walk.
  if(/&to=/.test(String(url))) return Promise.resolve(makeResponse(true,200,{candles:[]}));
  // An explicit script wins when one is installed (used by the short-dataset fixtures); otherwise
  // every pair gets healthy per-granularity data.
  if(__badPair && url.indexOf('/instruments/'+__badPair+'/')!==-1){
    return Promise.resolve(makeResponse(true,200,{candles:hourlyCandles(20,3600000)}));  // short: <60
  }
  if(fetchScript.length){ const st=fetchScript[fetchIdx]||fetchScript[fetchScript.length-1]; fetchIdx++; return st(); }
  const m=/granularity=([A-Z0-9]+)/.exec(url);
  const gran=m?m[1]:'H1';
  const ms={W:604800000,D:86400000,H4:14400000,H1:3600000}[gran]||3600000;
  const n={W:70,D:150,H4:400,H1:2300}[gran]||300;
  return Promise.resolve(makeResponse(true,200,{candles:hourlyCandles(n,ms)}));
};
const g={};
g.okCandles=function(n){ return function(){ return Promise.resolve(makeResponse(true,200,{candles:candleArray(n)})); }; };
g.setFetchScript=function(steps){ fetchScript=steps; fetchIdx=0; fetchUrls=[]; };
g.fetchUrls=function(){ return fetchUrls.slice(); };

g.advanceHour=function(){ __simNow+=3600000; };
g.setBadPair=function(p){ __badPair=p; };
g.now=function(){ return __simNow; };
const results=[];
function record(id,desc,pass,detail){ results.push({id,desc,pass,detail:detail||''}); }
g.record=record;

const wrapped = new Function('g',
  appCode + '\n' +
  'g.alexGEvaluatePairForLiveSetups=alexGEvaluatePairForLiveSetups;' +
  'g.emitDecisionEvent=emitDecisionEvent;' +
  'g.decisionEventLog=function(){return decisionEventLog;};' +
  'g.SCAN_PAIRS=SCAN_PAIRS;' +
  'g.setCursor=function(p,v){ if(!alexGLastEvaluatedCloseTime[p]) alexGLastEvaluatedCloseTime[p]={}; alexGLastEvaluatedCloseTime[p].H1=v; };' +
  'g.clearCursors=function(){ alexGLastEvaluatedCloseTime={}; };' +
  'g.buildPoll=function(o){ return evidenceBuildPollObservation(o); };' +
  'g.RULES_ALEXG=RULES_ALEXG;' +
  'return (async function(){\n' +
  // ── FIXTURE 1: short H1 dataset must now emit an auditable ENGINE_ERROR ──\n' +
  '  g.setFetchScript([g.okCandles(20)]);\n' +
  '  const before=decisionEventLog.length;\n' +
  '  await alexGEvaluatePairForLiveSetups("EUR_USD","SCAN|fixture|1");\n' +
  '  const added=decisionEventLog.slice(0,Math.max(0,decisionEventLog.length-before));\n' +
  '  const all=decisionEventLog.slice();\n' +
  '  const err=all.filter(function(e){ return e&&e.reasonCode==="DATA_INSUFFICIENT_HISTORY"; });\n' +
  '  g.record("COVERAGE-1","short H1 dataset emits DATA_INSUFFICIENT_HISTORY (was silent)",err.length>0,"events="+err.length);\n' +
  '  const e0=err[0]||{};\n' +
  '  g.record("COVERAGE-2","the event names the affected instrument",e0.pair==="EUR_USD","pair="+String(e0.pair));\n' +
  '  const ctx=e0.context||{};\n' +
  '  g.record("COVERAGE-3","the event carries the received candle count",typeof ctx.receivedH1==="number","receivedH1="+String(ctx.receivedH1));\n' +
  '  g.record("COVERAGE-4","the event carries the required minimum",ctx.requiredMinCandles===60,"requiredMinCandles="+String(ctx.requiredMinCandles));\n' +
  '  g.record("COVERAGE-5","the event carries the pagination termination reason field",Object.prototype.hasOwnProperty.call(ctx,"paginationTerminationReason"),"present");\n' +
  // ── FIXTURE 2: the poll observation must expose configured-vs-skipped ──\n' +
  '  const rec=evidenceBuildPollObservation({tickId:"t",startedAt:new Date().toISOString(),\n' +
  '    finishedAt:new Date().toISOString(),outcome:"OK",tradingEnabled:true,evaluationAdvanced:true,\n' +
  '    instrumentsAttempted:10,instrumentsEvaluated:["USD_JPY"],instrumentsConfigured:12,\n' +
  '    instrumentsSkipped:[{pair:"EUR_USD",lastEvaluatedH1:99,currentH1Boundary:1}]});\n' +
  '  g.record("COVERAGE-6","poll observation persists instrumentsConfigured",rec.instrumentsConfigured===12,"value="+String(rec.instrumentsConfigured));\n' +
  '  g.record("COVERAGE-7","poll observation persists instrumentsSkipped",Array.isArray(rec.instrumentsSkipped)&&rec.instrumentsSkipped.length===1,"len="+String((rec.instrumentsSkipped||[]).length));\n' +
  '  g.record("COVERAGE-8","skipped entry identifies the starved pair",(rec.instrumentsSkipped[0]||{}).pair==="EUR_USD","pair="+String((rec.instrumentsSkipped[0]||{}).pair));\n' +
  '  g.record("COVERAGE-9","a starved pair is now detectable: configured>evaluated",rec.instrumentsConfigured>rec.instrumentsEvaluated.length,"12>1");\n' +
  // ── FIXTURE 3: strategy semantics untouched ──\n' +
  '  const cfg=RULES_ALEXG.config.maxLiveSignalAgeMinutes;\n' +
  '  g.record("COVERAGE-10","staleness thresholds unchanged by this fix",\n' +
  '    cfg.H1===60&&cfg.H4===240&&cfg.D===1440&&cfg.W===10080,JSON.stringify(cfg));\n' +
  '  g.record("COVERAGE-11","all 12 instruments still configured",SCAN_PAIRS.length===12,"len="+SCAN_PAIRS.length);\n' +
  '  g.setFetchScript([]);\n' +
  '  cfg.key="fixture"; cfg.accountId="acct"; cfg.env="practice";\n' +
  '  alexGAutoTrading.enabled=true; alexGAutoTrading.activatedAt=g.now()-86400000;\n' +
  '  alexGLastEvaluatedCloseTime={}; alexGZoneState={}; alexGSetupState=[]; alexGResetLiveDecisionState(); alexGLiveSetupStatuses=[];\n' +
  '  await alexGLivePollTick();\n' +
  '  const covered=SCAN_PAIRS.map(function(p){return p.replace("/","_");})\n' +
  '    .filter(function(op){ return alexGLastEvaluatedCloseTime[op]&&alexGLastEvaluatedCloseTime[op].H1!=null; });\n' +
  '  g.record("LOOP-1","one tick evaluates ALL 12 configured instruments",covered.length===12,"covered="+covered.length+"/12 missing="+SCAN_PAIRS.map(function(p){return p.replace("/","_");}).filter(function(op){return covered.indexOf(op)<0;}).join(","));\n' +
  '  const bnd=Math.floor(g.now()/3600000)*3600000;\n' +
  '  const ahead=covered.filter(function(op){ return alexGLastEvaluatedCloseTime[op].H1>bnd; });\n' +
  '  g.record("LOOP-2","no instrument cursor lands AHEAD of the current H1 boundary (starvation condition)",ahead.length===0,"ahead="+ahead.join(","));\n' +
  '  const atBnd=covered.filter(function(op){ return alexGLastEvaluatedCloseTime[op].H1===bnd; });\n' +
  '  g.record("LOOP-3","cursors land exactly ON the boundary (evaluate once per H1, as designed)",atBnd.length===12,"atBoundary="+atBnd.length+"/12");\n' +
  '  g.advanceHour();\n' +
  '  const before2=JSON.stringify(alexGLastEvaluatedCloseTime);\n' +
  '  await alexGLivePollTick();\n' +
  '  const bnd2=Math.floor(g.now()/3600000)*3600000;\n' +
  '  const covered2=SCAN_PAIRS.map(function(p){return p.replace("/","_");})\n' +
  '    .filter(function(op){ return alexGLastEvaluatedCloseTime[op]&&alexGLastEvaluatedCloseTime[op].H1===bnd2; });\n' +
  '  g.record("LOOP-4","after one hour ALL 12 re-evaluate (no permanent starvation)",covered2.length===12,"reEvaluated="+covered2.length+"/12");\n' +
  '  await alexGLivePollTick();\n' +
  '  const covered3=SCAN_PAIRS.map(function(p){return p.replace("/","_");})\n' +
  '    .filter(function(op){ return alexGLastEvaluatedCloseTime[op]&&alexGLastEvaluatedCloseTime[op].H1===bnd2; });\n' +
  '  g.record("LOOP-5","a second tick in the SAME hour re-evaluates nothing (cadence gate holds)",covered3.length===12,"stable="+covered3.length+"/12");\n' +
  '  g.advanceHour(); g.setBadPair("EUR_USD"); alexGLastEvaluatedCloseTime={};\n' +
  '  await alexGLivePollTick();\n' +
  '  const bnd3=Math.floor(g.now()/3600000)*3600000;\n' +
  '  const ok3=SCAN_PAIRS.map(function(p){return p.replace("/","_");})\n' +
  '    .filter(function(op){ return alexGLastEvaluatedCloseTime[op]&&alexGLastEvaluatedCloseTime[op].H1===bnd3; });\n' +
  '  g.record("RESIL-1","one instrument with short data does NOT poison the other 11",ok3.length===11,"healthy="+ok3.length+"/11");\n' +
  '  g.record("RESIL-2","the failing instrument sets no cursor (so it is retried, never permanently starved)",!alexGLastEvaluatedCloseTime["EUR_USD"],"cursor unset");\n' +
  '  const errs=decisionEventLog.filter(function(e){return e&&e.reasonCode==="DATA_INSUFFICIENT_HISTORY"&&e.pair==="EUR_USD";});\n' +
  '  g.record("RESIL-3","the failure is recorded with the instrument named",errs.length>0,"events="+errs.length);\n' +
  '  g.setBadPair(null); g.advanceHour();\n' +
  '  await alexGLivePollTick();\n' +
  '  const bnd4=Math.floor(g.now()/3600000)*3600000;\n' +
  '  g.record("RESIL-4","the instrument recovers automatically once data returns",!!(alexGLastEvaluatedCloseTime["EUR_USD"]&&alexGLastEvaluatedCloseTime["EUR_USD"].H1===bnd4),"recovered");\n' +
  '  g.setBadPair(null); g.advanceHour();\n' +
  '  alexGLastEvaluatedCloseTime={}; \n' +
  '  await alexGLivePollTick();\n' +
  '  const bndS=Math.floor(g.now()/3600000)*3600000;\n' +
  // Capture what the poll ACTUALLY hands the durable ledger, rather than asserting on a
  // hand-built observation -- the durable skip record is the operator-visible artifact.
  '  var __lastObs=null; const __origRecObs=evidenceRecordForwardObservations;\n' +
  // Capture the record the DURABLE BUILDER produces, not the raw object handed to the recorder.
  // An earlier version asserted on the seam input and therefore passed even when the builder
  // stripped the field entirely -- it tested the hook, not the schema.
  '  evidenceRecordForwardObservations=function(input){ __lastObs=evidenceBuildPollObservation((input&&input.poll)||{}); return __origRecObs.apply(this,arguments); };\n' +
  '  g.lastObs=function(){ return __lastObs||{}; };\n' +
  '  alexGLastEvaluatedCloseTime["EUR_USD"]={H1:bndS+72*3600000};   // cursor 3 days ahead\n' +
  '  let seen=0,skips=0,flagged=0;\n' +
  '  for(let h=0;h<8;h++){ g.advanceHour(); await alexGLivePollTick();\n' +
  '    const b=Math.floor(g.now()/3600000)*3600000;\n' +
  '    if(alexGLastEvaluatedCloseTime["EUR_USD"].H1===b) seen++;\n' +
  '    const rec=(g.lastObs().instrumentsSkipped||[]).filter(function(x){return x.pair==="EUR_USD";})[0];\n' +
  '    if(rec) skips++; if(rec&&rec.cursorAheadOfClock===true) flagged++; }\n' +
  '  g.record("STARVE-1","an impossible cursor holds the instrument OUT of live evaluation (fail-closed)",\n' +
  '    seen===0&&skips===8,"evaluated "+seen+"/8, skipped "+skips+"/8 -- untrusted timestamps are not traded on");\n' +
  '  const others=SCAN_PAIRS.map(function(p){return p.replace("/","_");}).filter(function(op){return op!=="EUR_USD";})\n' +
  '    .filter(function(op){ return alexGLastEvaluatedCloseTime[op]&&alexGLastEvaluatedCloseTime[op].H1===Math.floor(g.now()/3600000)*3600000; });\n' +
  '  g.record("STARVE-2","the other 11 remain healthy throughout -- the condition is per-instrument",others.length===11,"healthy="+others.length+"/11");\n' +
  '  g.record("STARVE-3","the flag SURVIVES the durable builder -- the ledger separates a normal skip from an impossible cursor",\n' +
  '    flagged===8,"flagged "+flagged+"/8 records built by evidenceBuildPollObservation");\n' +
  '  const cur=decisionEventLog.filter(function(e){return e&&e.reasonCode==="STATE_CURSOR_AHEAD_OF_CLOCK";});\n' +
  '  g.record("STARVE-4","the condition is reported ONCE, not re-emitted every poll (the ring is not flooded)",\n' +
  '    cur.length===1,"events="+cur.length+" across 8 polls");\n' +
  '  const c0=(cur[0]||{}).context||{};\n' +
  '  g.record("STARVE-5","the record carries the cursor, the boundary and how far ahead it was",\n' +
  '    typeof c0.lastEvaluatedH1==="number"&&typeof c0.currentH1Boundary==="number"&&typeof c0.aheadMs==="number","aheadMs="+c0.aheadMs);\n' +
  '  g.record("STARVE-6","the cursor is NOT auto-repaired -- resuming trade evaluation on untrusted time is not the remedy",\n' +
  '    alexGLastEvaluatedCloseTime["EUR_USD"].H1===bndS+72*3600000,"cursor left intact for operator diagnosis");\n' +
  // ── the threshold itself, tested at the boundary rather than 2h away from it ──
  '  alexGLastEvaluatedCloseTime={}; g.advanceHour(); await alexGLivePollTick();\n' +
  '  function cursorEventsFor(op){ return decisionEventLog.filter(function(e){return e&&e.reasonCode==="STATE_CURSOR_AHEAD_OF_CLOCK"&&e.pair===op;}).length; }\n' +
  '  const bT=Math.floor(g.now()/3600000)*3600000;\n' +
  '  alexGLastEvaluatedCloseTime["USD_JPY"]={H1:bT+2*3600000};\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("STARVE-7","exactly +2h does NOT trip the detector -- the boundary is inclusive as written",\n' +
  '    cursorEventsFor("USD_JPY")===0,"no event at +2h exactly");\n' +
  '  alexGLastEvaluatedCloseTime["USD_CHF"]={H1:bT+2*3600000+1};\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("STARVE-8","one millisecond past +2h DOES trip it -- the fixture discriminates at the threshold",\n' +
  '    cursorEventsFor("USD_CHF")===1,"event at +2h+1ms");\n' +
  '  const bH=Math.floor(g.now()/3600000)*3600000; alexGLastEvaluatedCloseTime["AUD_USD"]={H1:bH};\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("STARVE-9","a healthy on-boundary cursor never trips it",cursorEventsFor("AUD_USD")===0,"no false positive");\n' +
  // ── the latch must not outlive the events it refers to ──
  '  alexGLastEvaluatedCloseTime={}; g.advanceHour(); await alexGLivePollTick();\n' +
  '  const bC=Math.floor(g.now()/3600000)*3600000;\n' +
  '  alexGLastEvaluatedCloseTime["GBP_JPY"]={H1:bC+50*3600000};\n' +
  '  await alexGLivePollTick();\n' +
  '  const firstReport=cursorEventsFor("GBP_JPY");\n' +
  '  clearDecisionEvents();\n' +
  '  await alexGLivePollTick();\n' +
  '  g.record("STARVE-10","clearing the bus RE-ARMS the detector -- a dev-only button cannot permanently silence a live fault",\n' +
  '    firstReport===1&&cursorEventsFor("GBP_JPY")===1,"reported again after clear (was "+firstReport+" before)");\n' +
  '  g.record("STARVE-11","the latch is a bounded Set, not an unbounded object -- it cannot grow forever in a long-lived tab",\n' +
  '    alexGCursorSanityReported instanceof Set&&alexGCursorSanityReported.size<=ALEXG_CURSOR_SANITY_REPORTED_MAX,\n' +
  '    "size="+alexGCursorSanityReported.size+" cap="+ALEXG_CURSOR_SANITY_REPORTED_MAX);\n' +
  '  for(let k=0;k<ALEXG_CURSOR_SANITY_REPORTED_MAX+50;k++) alexGMarkCursorSanityReported("SYNTH|"+k);\n' +
  '  g.record("STARVE-12","and it evicts oldest-first at the cap rather than growing past it",\n' +
  '    alexGCursorSanityReported.size===ALEXG_CURSOR_SANITY_REPORTED_MAX&&!alexGCursorSanityReported.has("SYNTH|0"),\n' +
  '    "size="+alexGCursorSanityReported.size+" after inserting cap+50; oldest evicted");\n' +
  // ── STATUS-RING TRUNCATION BIAS: the defect that produced a false starvation diagnosis ──
  // alexGLiveSetupStatuses is a 300-entry ring (PROTECTED alexGRecordLiveSetupStatus: unshift then
  // truncate the TAIL). Pairs are evaluated in SCAN_PAIRS order, so the pairs recorded FIRST sit
  // nearest the tail and are evicted first. Production carries 383 setups per cycle against that
  // 300 cap, so GBP/USD (1st) and EUR/USD (2nd) are evicted BEFORE the cycle even finishes -- and
  // alexGLivePollTick records this same array verbatim into the durable ledger. Any forward-coverage
  // analysis built on it therefore under-reports the pairs at the front of scan order, which is
  // exactly what produced the (false) "EUR_USD is starved" conclusion in MOGO-020.
  '  alexGResetLiveDecisionState();\n' +
  '  const ORDER=SCAN_PAIRS.map(function(p){return p.replace("/","_");});\n' +
  '  let sid=0;\n' +
  '  for(const op of ORDER){ for(let k=0;k<32;k++){ sid++;\n' +
  '    alexGRecordLiveSetupStatus({signalId:"S|"+sid,pair:op,timeframe:"H1",status:"IGNORED"}); } }\n' +
  '  const ringPairs=alexGLiveSetupStatuses.map(function(e){return e.pair;});\n' +
  '  g.record("BIAS-1","one cycle of setups OVERFLOWS the 300-entry status ring",\n' +
  '    sid===384&&alexGLiveSetupStatuses.length===300,"recorded "+sid+" statuses, ring holds "+alexGLiveSetupStatuses.length);\n' +
  '  g.record("BIAS-2","the ring evicts the pairs evaluated FIRST -- scan order decides who disappears",\n' +
  '    ringPairs.indexOf(ORDER[0])===-1&&ringPairs.indexOf(ORDER[1])===-1&&ringPairs.indexOf(ORDER[11])!==-1,\n' +
  '    ORDER[0]+" and "+ORDER[1]+" absent; "+ORDER[11]+" present -- entries="+ringPairs.length);\n' +
  // Names the EXPECTED pairs. An earlier version asserted only "some pair is missing", which is
  // tautologically true whenever 384 entries overflow a 300 cap in ANY eviction direction -- it
  // survived an unshift->push mutation unchanged and therefore proved nothing.
  '  const invisible=ORDER.filter(function(op){return ringPairs.indexOf(op)===-1;});\n' +
  '  g.record("BIAS-3","and the pairs it hides are exactly the FRONT of scan order, not an arbitrary pair",\n' +
  '    invisible.length===2&&invisible[0]===ORDER[0]&&invisible[1]===ORDER[1],\n' +
  '    "invisible in the ring: "+invisible.join(",")+" (expected "+ORDER[0]+","+ORDER[1]+")");\n' +
  // The remediation: instrumentsEvaluated/instrumentsConfigured are built from the poll loop
  // itself, not from the status ring, so they are immune to this truncation.
  '  alexGLastEvaluatedCloseTime={}; g.advanceHour();\n' +
  '  await alexGLivePollTick();\n' +
  '  const obs=g.lastObs();\n' +
  '  g.record("BIAS-4","the DURABLE coverage record coming from the poll loop is NOT subject to that bias",\n' +
  '    (obs.instrumentsEvaluated||[]).length===SCAN_PAIRS.length&&obs.instrumentsConfigured===SCAN_PAIRS.length,\n' +
  '    "instrumentsEvaluated="+((obs.instrumentsEvaluated||[]).length)+"/"+obs.instrumentsConfigured);\n' +
  '  g.record("BIAS-5","and it names EVERY configured instrument, including the ones the ring evicted",\n' +
  '    ORDER.every(function(op){ return (obs.instrumentsEvaluated||[]).indexOf(op)!==-1; }),\n' +
  '    "all "+ORDER.length+" pairs present in the durable coverage record");\n' +
  // ── THE TRADING-FIDELITY CONSEQUENCE: the dedup at index.html:4641 is void for EVERY pair ──
  // A pair's own entries survive to its NEXT turn only if (totalSetups - thatPairsSetups) < 300.
  // In production the most-favoured pair is GBP_CHF at 54 setups: 383 - 54 = 329 > 300. No pair
  // clears the bar, so the "PERMANENT, never reconsidered" contract does not hold for any
  // instrument -- every setup is re-decided on every advancing poll. Measured in the durable
  // ledger at ~47 re-decisions per signalId (377 signalIds, 17,700 evaluation records).
  '  alexGResetLiveDecisionState();\n' +
  '  function cycle(tag){ const seen={};\n' +
  '    ORDER.forEach(function(op,pi){\n' +
  '      const mine=[]; for(let k=0;k<32;k++) mine.push("S|"+op+"|"+k);\n' +
  '      seen[op]=mine.filter(function(id){ return alexGLiveSetupStatuses.some(function(e){return e.signalId===id;}); }).length;\n' +
  '      mine.forEach(function(id){ alexGRecordLiveSetupStatus({signalId:id,pair:op,timeframe:"H1",status:"IGNORED"}); });\n' +
  '    }); return seen; }\n' +
  '  cycle("first");\n' +
  '  const survived=cycle("second");\n' +
  '  const anySurvivor=ORDER.filter(function(op){ return survived[op]===32; });\n' +
  '  g.record("REDEC-1","NO instrument keeps a full cycle of decisions to its next turn -- the ring is too small",\n' +
  '    anySurvivor.length===0,"pairs retaining all 32 prior decisions: "+anySurvivor.length+"/12");\n' +
  '  g.record("REDEC-2","the DISPLAY ring alone could never uphold the PERMANENT contract for any pair -- which is why the decided-authority exists (DECIDED-*)",\n' +
  '    ORDER.every(function(op){ return survived[op]<32; }),\n' +
  '    "retained per pair: "+ORDER.map(function(op){return survived[op];}).join(","));\n' +
  '  g.record("REDEC-3","the pair evaluated LAST is the best case and still loses decisions",\n' +
  '    survived[ORDER[11]]<32,ORDER[11]+" retained "+survived[ORDER[11]]+"/32 of its own prior decisions");\n' +
  // Measures the ring's ACTUAL capacity by filling it, rather than hard-coding 300. An earlier
  // version asserted `12*32 > 300` with 300 as a literal, which touched no production code and
  // survived every mutation -- including raising the cap to 5000, the very fix it described.
  '  alexGResetLiveDecisionState();\n' +
  '  for(let k=0;k<1200;k++) alexGRecordLiveSetupStatus({signalId:"CAP|"+k,pair:"EUR_USD",timeframe:"H1",status:"IGNORED"});\n' +
  '  const measuredCap=alexGLiveSetupStatuses.length;\n' +
  '  g.record("REDEC-4","the ring cannot hold one scan cycle -- measured from the real recorder, not assumed",\n' +
  '    measuredCap<ORDER.length*32,\n' +
  '    "measured cap="+measuredCap+"; one cycle needs "+(ORDER.length*32)+" slots");\n' +
  // The exact survival threshold, from the REAL uneven production distribution rather than a flat
  // 32 per pair: a pair's entries survive to its next turn only if (N - maxPairSetups) < cap.
  '  const LIVE=[31,30,26,31,33,54,30,31,23,36,28,30];\n' +   // GBP_USD..USD_CHF, live 2026-08-14
  '  const N=LIVE.reduce(function(a,b){return a+b;},0), maxPair=Math.max.apply(null,LIVE);\n' +
  '  g.record("REDEC-5","and it fails under the REAL uneven per-pair distribution too, not just a flat one",\n' +
  '    (N-maxPair)>=measuredCap,\n' +
  '    "N="+N+", largest pair="+maxPair+" -> needs cap >= "+(N-maxPair+1)+", ring holds "+measuredCap);\n' +
  // ══ MOGO-021 DECISIONS 2+3 -- STABLE ECONOMIC IDENTITY AND THE DECIDED-AUTHORITY ══
  // The ring fixtures above establish that a 300-entry DISPLAY buffer can never uphold a permanent
  // dedup contract. These prove the authority that replaces it: what it keys on, that it survives
  // the three things that used to defeat identity, that it does NOT collapse genuinely distinct
  // setups, and that its bound is provably lossless rather than merely convenient.
  '  const H1LIM=RULES_ALEXG.config.maxLiveSignalAgeMinutes.H1;\n' +
  '  const WLIM=RULES_ALEXG.config.maxLiveSignalAgeMinutes.W;\n' +
  '  const QT=Date.UTC(2026,7,14,12,0,0);\n' +
  // One economic setup, expressed three ways: as first traded; after a ZONE RE-ANCHOR (zoneId and
  // setupId move, reactionId/qualificationTimestamp hold); and after the WEEKEND CLOSE-TIME
  // RE-ESTIMATION (reactionId AND qualificationTimestamp both move by ~48h).
  '  const asTraded={pair:"AUD_JPY",timeframe:"H1",setupType:"B_breakRetest",\n' +
  '    reactionId:"AGR|AUD_JPY|H1|low|1786503600000",qualificationTimestamp:QT,qualificationClose:1.10250,\n' +
  '    zoneId:"AGZ|AGC|AUD_JPY|H1|high|1775610000000|v1786395600000"};\n' +
  '  const reAnchored=Object.assign({},asTraded,{zoneId:"AGZ|AGC|AUD_JPY|H1|high|1783983600000|v1786420800000"});\n' +
  '  const afterWeekend=Object.assign({},asTraded,{\n' +
  '    reactionId:"AGR|AUD_JPY|H1|low|"+(1786503600000+48*3600000),qualificationTimestamp:QT+48*3600000});\n' +
  '  g.record("DECIDED-1","the STABLE identity survives a zone re-anchor -- the AUD_JPY case that defeated every guard",\n' +
  '    alexGStableSetupIdentity(asTraded)===alexGStableSetupIdentity(reAnchored)&&\n' +
  '    asTraded.zoneId!==reAnchored.zoneId,\n' +
  '    "same identity across two different zoneIds");\n' +
  // This is the one the five-component key CANNOT do, and the reason a second identity exists.
  '  g.record("DECIDED-2","the ECONOMIC identity also survives the weekend close-time re-estimation, which the stable identity does NOT",\n' +
  '    alexGEconomicSetupIdentity(asTraded)===alexGEconomicSetupIdentity(afterWeekend)&&\n' +
  '    alexGStableSetupIdentity(asTraded)!==alexGStableSetupIdentity(afterWeekend),\n' +
  '    "economic identity holds where reactionId and qualificationTimestamp both moved 48h");\n' +
  // ANTI-OVER-BLOCKING. A lossy key that collapsed distinct setups would silently destroy real
  // opportunities, which is worse than the defect it fixes.
  '  const otherPrice=Object.assign({},asTraded,{qualificationClose:1.10251});\n' +
  '  const otherSwing=Object.assign({},asTraded,{reactionId:"AGR|AUD_JPY|H1|high|1786503600000"});\n' +
  '  const otherTf=Object.assign({},asTraded,{timeframe:"H4"});\n' +
  '  const otherType=Object.assign({},asTraded,{setupType:"A_repeatedReaction"});\n' +
  '  const otherPair=Object.assign({},asTraded,{pair:"EUR_USD"});\n' +
  // Pins that the economic identity EXCLUDES the zone anchor. Without this, folding zoneId back into
  // it would pass every other fixture while making it useless for the exact case it exists for.
  '  g.record("DECIDED-2b","the ECONOMIC identity also excludes the zone anchor -- it matches across a re-anchor",\n' +
  '    alexGEconomicSetupIdentity(asTraded)===alexGEconomicSetupIdentity(reAnchored)&&\n' +
  '    asTraded.zoneId!==reAnchored.zoneId&&\n' +
  '    String(alexGEconomicSetupIdentity(asTraded)).indexOf("AGZ")===-1,\n' +
  '    "economic identity carries no zone anchor: "+alexGEconomicSetupIdentity(asTraded));\n' +
  '  g.record("DECIDED-3","genuinely DISTINCT economic setups stay distinct -- one pip, one swing, one timeframe, one type or one pair is enough",\n' +
  '    [otherPrice,otherSwing,otherTf,otherType,otherPair].every(function(x){\n' +
  '      return alexGEconomicSetupIdentity(x)!==alexGEconomicSetupIdentity(asTraded); }),\n' +
  '    "no accidental collapsing of legitimate future setups");\n' +
  '  g.record("DECIDED-4","an unclassifiable record yields NO identity rather than a colliding empty key",\n' +
  '    alexGEconomicSetupIdentity(null)===null&&alexGEconomicSetupIdentity({pair:"EUR_USD"})===null&&\n' +
  '    alexGEconomicSetupIdentity(Object.assign({},asTraded,{qualificationClose:null}))===null);\n' +
  // THE HEADLINE: the decided-authority still knows, after the display ring has thrown the record away.
  '  alexGResetLiveDecisionState();\n' +
  '  alexGMarkSetupDecided(asTraded,"AGL|orig");\n' +
  '  for(let k=0;k<1200;k++) alexGRecordLiveSetupStatus({signalId:"FLOOD|"+k,pair:"EUR_USD",timeframe:"H1",status:"IGNORED"});\n' +
  '  const ringHasIt=alexGLiveSetupStatuses.some(function(e){return e.signalId==="AGL|orig";});\n' +
  '  const foundAfterEviction=alexGFindPriorDecision(reAnchored,"AGL|different");\n' +
  '  g.record("DECIDED-5","duplicate protection SURVIVES display-ring eviction -- the defect this replaces",\n' +
  '    ringHasIt===false&&!!foundAfterEviction&&foundAfterEviction.drifted===true,\n' +
  '    "ring evicted the original ("+ringHasIt+"); authority still reports prior decision, drifted="+\n' +
  '    String(foundAfterEviction&&foundAfterEviction.drifted));\n' +
  '  g.record("DECIDED-6","and it matches the re-anchored AND the post-weekend form of the same setup",\n' +
  '    !!alexGFindPriorDecision(afterWeekend,"AGL|different2"),\n' +
  '    "matched via the economic identity after reactionId and qualificationTimestamp both moved");\n' +
  // ANTI-OVER-BLOCKING, at the GUARD rather than the identity. A later, genuinely new setup on the
  // same pair and timeframe must still be tradeable -- a guard that blocked it would destroy real
  // opportunities, which is worse than the defect it fixes.
  // (Note: a record differing ONLY in qualificationClose is not tested here because it cannot exist
  // -- reactionId and qualificationTimestamp together pin one bar, and that bar has one close. The
  // identity's price discrimination is proved at DECIDED-3 instead.)
  '  const laterSetup=Object.assign({},asTraded,{\n' +
  '    reactionId:"AGR|AUD_JPY|H1|low|"+(1786503600000+7*24*3600000),\n' +
  '    qualificationTimestamp:QT+7*24*3600000,qualificationClose:1.11480});\n' +
  '  g.record("DECIDED-7","a genuinely NEW setup on the same pair and timeframe is NOT blocked -- no lost opportunity",\n' +
  '    alexGFindPriorDecision(laterSetup,"AGL|new")===null&&\n' +
  '    alexGFindPriorDecision(otherPair,"AGL|new2")===null&&\n' +
  '    alexGFindPriorDecision(otherTf,"AGL|new3")===null,\n' +
  '    "a later setup, a different pair and a different timeframe all remain tradeable");\n' +
  // AGE EVICTION, and the proof that it is lossless rather than convenient.
  '  alexGPruneDecidedSetups(QT+(H1LIM-1)*60000,RULES_ALEXG.config);\n' +
  '  const beforeLimit=!!alexGFindPriorDecision(reAnchored,"AGL|x");\n' +
  '  alexGPruneDecidedSetups(QT+(H1LIM+1)*60000,RULES_ALEXG.config);\n' +
  '  const afterLimit=!!alexGFindPriorDecision(reAnchored,"AGL|x");\n' +
  '  g.record("DECIDED-8","the record is kept while the setup is still actionable and evicted only once it is not",\n' +
  '    beforeLimit===true&&afterLimit===false,\n' +
  '    "held inside the H1 staleness window ("+H1LIM+"m), released outside it");\n' +
  // STRENGTHENED (was mis-titled). This fixture claimed eviction was provably lossless but asserted
  // ONLY the pre-existing frozen alexGIsSetupSignalStale boundary -- it touched no eviction code at
  // all and died to no eviction mutation. Renaming it would have been the cheaper fix; it is
  // strengthened instead, because the claim it makes is the one thing that justifies evicting a
  // decided record at all, and a claim that load-bearing should be tested rather than retitled.
  //
  // The two boundaries are now MEASURED against each other, to the millisecond, on every timeframe:
  // for each, the record is pruned exactly AT lim and one millisecond past it, and eviction must
  // agree with staleness at both points. Any prune that reads a different limit, a different config
  // source, or a different comparison than the frozen gate now disagrees somewhere and fails here.
  '  const TIE_TFS=["H1","H4","D","W"];\n' +
  '  const tieRows=TIE_TFS.map(function(tf,i){\n' +
  '    const lim=RULES_ALEXG.config.maxLiveSignalAgeMinutes[tf];\n' +
  '    const rec=Object.assign({},asTraded,{timeframe:tf,qualificationClose:1.20000+i*0.00100});\n' +
  '    function at(ms){\n' +
  '      alexGResetLiveDecisionState();\n' +
  '      alexGMarkSetupDecided(rec,"AGL|tie|"+tf);\n' +
  '      alexGPruneDecidedSetups(QT+ms,RULES_ALEXG.config);\n' +
  '      return{evicted:alexGFindPriorDecision(rec,"AGL|tieprobe")===null,\n' +
  '        stale:alexGIsSetupSignalStale(rec,QT+ms,RULES_ALEXG.config)};\n' +
  '    }\n' +
  '    const on=at(lim*60000),past=at(lim*60000+1);\n' +
  '    return{tf:tf,lim:lim,agree:on.evicted===on.stale&&past.evicted===past.stale,\n' +
  '      discriminates:on.stale===false&&past.stale===true};\n' +
  '  });\n' +
  '  g.record("DECIDED-9","eviction is PROVABLY LOSSLESS -- the eviction boundary IS the frozen staleness boundary, to the millisecond, on every timeframe",\n' +
  '    tieRows.every(function(r){return r.agree&&r.discriminates;})&&\n' +
  '    alexGIsSetupSignalStale(asTraded,QT+(H1LIM+1)*60000,RULES_ALEXG.config)===true&&\n' +
  '    alexGIsSetupSignalStale(asTraded,QT+(H1LIM-1)*60000,RULES_ALEXG.config)===false,\n' +
  '    tieRows.map(function(r){return r.tf+"@"+r.lim+"m"+(r.agree?" tied":" DIVERGED");}).join(", ")+\n' +
  '    " -- measured at the limit and one millisecond past it, so no evicted record could have changed an outcome");\n' +
  // Per-timeframe lifetime: a W setup must be remembered 7 days, not one hour.
  '  alexGResetLiveDecisionState();\n' +
  '  const wSetup=Object.assign({},asTraded,{timeframe:"W",qualificationClose:1.30000});\n' +
  '  alexGMarkSetupDecided(wSetup,"AGL|w");\n' +
  '  alexGPruneDecidedSetups(QT+(H1LIM+60)*60000,RULES_ALEXG.config);\n' +
  '  const wHeld=!!alexGFindPriorDecision(wSetup,"AGL|w2");\n' +
  '  alexGPruneDecidedSetups(QT+(WLIM+1)*60000,RULES_ALEXG.config);\n' +
  '  const wReleased=!alexGFindPriorDecision(wSetup,"AGL|w3");\n' +
  '  g.record("DECIDED-10","the lifetime is PER TIMEFRAME -- a W decision outlives an H1 one by its own contract",\n' +
  '    wHeld===true&&wReleased===true,"W held past the H1 limit ("+H1LIM+"m) and released past its own ("+WLIM+"m)");\n' +
  // Derived from EXISTING durable state -- not a new persistent source of truth.
  '  alexGResetLiveDecisionState();\n' +
  '  const keysBefore=Object.keys(lsStore).length;\n' +
  '  alexGAccount={balance:10000,openPositions:[],closedPositions:[Object.assign({},asTraded,{signalId:"AGL|orig",tradeId:"AGT|orig",status:"closed"})]};\n' +
  '  alexGJournalEntries=[];\n' +
  '  const fromDurable=alexGFindPriorDecision(reAnchored,"AGL|different");\n' +
  '  g.record("DECIDED-11","after a RELOAD (session map empty) the already-traded fact is recovered from the EXISTING durable records",\n' +
  '    !!fromDurable&&fromDurable.source==="durable"&&fromDurable.priorTradeId==="AGT|orig",\n' +
  '    "recovered from closedPositions with no session state and no new storage key");\n' +
  '  g.record("DECIDED-12","and it introduced NO new persistent storage key -- nothing was added as a second source of truth",\n' +
  '    Object.keys(lsStore).length===keysBefore,\n' +
  '    "localStorage keys before="+keysBefore+" after="+Object.keys(lsStore).length);\n' +
  '  alexGAccount={balance:10000,openPositions:[],closedPositions:[]};\n' +
  '  const journalOnly=Object.assign({},asTraded,{tradeId:"AGT|orig"}); delete journalOnly.signalId;\n' +
  '  alexGJournalEntries=[journalOnly];\n' +
  '  g.record("DECIDED-13","the journal alone is sufficient -- positions unreadable does not blind the authority",\n' +
  '    !!alexGFindPriorDecision(reAnchored,"AGL|different"),\n' +
  '    "matched from alexGJournalEntries with an empty account");\n' +
  '  alexGJournalEntries=[];\n' +
  // The reset primitive is what stopped the MOGO-020 attempt from desynchronising.
  '  alexGMarkSetupDecided(asTraded,"AGL|orig");\n' +
  '  alexGRecordLiveSetupStatus({signalId:"AGL|orig",pair:"AUD_JPY",timeframe:"H1",status:"IGNORED"});\n' +
  '  alexGResetLiveDecisionState();\n' +
  '  g.record("DECIDED-14","one primitive clears the ring AND the authority together -- they cannot desynchronise",\n' +
  '    alexGLiveSetupStatuses.length===0&&alexGFindPriorDecision(asTraded,"AGL|any")===null,\n' +
  '    "ring="+alexGLiveSetupStatuses.length+" and authority reports nothing");\n' +
  // ══ THE DURABLE ECONOMIC TERM IS AGE-BOUNDED (MOGO-021, both directions) ══════════════════
  // The stable identity pins qualificationTimestamp exactly, so an exact match needs no age bound.
  // The economic identity deliberately drops time, and until the bound landed the durable half had
  // NO age limit at all: a setup carrying the same categorical fields and the same qualificationClose
  // would have been refused for the life of the account. A permanently lost trade is worse than the
  // duplicate it prevents, so BOTH directions have to hold.
  '  alexGResetLiveDecisionState();\n' +
  '  const tradedRec=Object.assign({},asTraded,{signalId:"AGL|orig",tradeId:"AGT|orig",status:"closed"});\n' +
  '  alexGAccount={balance:10000,openPositions:[],closedPositions:[tradedRec]};\n' +
  '  alexGJournalEntries=[];\n' +
  // (a) the case the term exists for: the weekend close-time re-estimation moved reactionId AND
  // qualificationTimestamp, so ONLY the economic identity can still match.
  '  const wkMatch=alexGFindPriorDecision(afterWeekend,"AGL|weekend");\n' +
  // (b) a genuinely NEW setup three weeks later carrying the IDENTICAL economic identity -- same
  // pair, timeframe, setup type, swing type and qualificationClose. Nothing but the age bound
  // distinguishes it from (a).
  '  const newLater=Object.assign({},asTraded,{\n' +
  '    reactionId:"AGR|AUD_JPY|H1|low|"+(1786503600000+21*24*3600000),\n' +
  '    qualificationTimestamp:QT+21*24*3600000});\n' +
  '  const newMatch=alexGFindPriorDecision(newLater,"AGL|new21d");\n' +
  '  g.record("ECON-AGE-1","the DURABLE economic term still refuses a weekend-shifted re-derivation (~48h apart)",\n' +
  '    !!wkMatch&&wkMatch.source==="durable"&&wkMatch.matchedBy==="economicId"&&\n' +
  '    wkMatch.priorTradeId==="AGT|orig"&&wkMatch.drifted===true&&\n' +
  '    alexGStableSetupIdentity(afterWeekend)!==alexGStableSetupIdentity(tradedRec),\n' +
  '    "matchedBy="+String(wkMatch&&wkMatch.matchedBy)+" source="+String(wkMatch&&wkMatch.source)+\n' +
  '    " -- the stable identity does NOT match, so this is the economic term or nothing");\n' +
  '  g.record("ECON-AGE-2","but a genuinely NEW setup 21 days later with the IDENTICAL economic identity is NOT refused",\n' +
  '    newMatch===null&&\n' +
  '    alexGEconomicSetupIdentity(newLater)===alexGEconomicSetupIdentity(tradedRec)&&\n' +
  '    (newLater.qualificationTimestamp-tradedRec.qualificationTimestamp)>alexGEconomicMatchWindowMs("H1"),\n' +
  '    "same economic identity ("+alexGEconomicSetupIdentity(newLater)+"), gap "+\n' +
  '    Math.round((newLater.qualificationTimestamp-tradedRec.qualificationTimestamp)/86400000)+"d vs window "+\n' +
  '    (alexGEconomicMatchWindowMs("H1")/86400000).toFixed(2)+"d -- an unbounded term would lose this trade forever");\n' +
  '  g.record("ECON-AGE-3","the window is the timeframe’s OWN staleness limit plus the market-gap allowance, per timeframe",\n' +
  '    alexGEconomicMatchWindowMs("H1")===H1LIM*60000+ALEXG_ECONOMIC_MATCH_GAP_MS&&\n' +
  '    alexGEconomicMatchWindowMs("W")===WLIM*60000+ALEXG_ECONOMIC_MATCH_GAP_MS&&\n' +
  '    alexGEconomicMatchWindowMs("W")>alexGEconomicMatchWindowMs("H1"),\n' +
  '    "H1="+alexGEconomicMatchWindowMs("H1")+"ms W="+alexGEconomicMatchWindowMs("W")+"ms");\n' +
  // ══ A DEVELOPER TEST TRADE MUST NOT DURABLY BLOCK A REAL SETUP ════════════════════════════
  // Developer trades travel through the same frozen open/close functions by design, so they land in
  // the account and the journal exactly like real ones -- which is precisely why they have to be
  // excluded HERE rather than assumed absent. The positive control is what makes this non-vacuous:
  // the SAME record without the tags must still block.
  '  alexGResetLiveDecisionState();\n' +
  '  function devScan(over){\n' +
  '    alexGAccount={balance:10000,openPositions:[],\n' +
  '      closedPositions:[Object.assign({},asTraded,{signalId:"AGL|d",tradeId:"AGT|d",status:"closed"},over)]};\n' +
  '    return alexGFindPriorDecision(reAnchored,"AGL|realsetup");\n' +
  '  }\n' +
  '  const realBlocks=devScan({});\n' +
  '  const devFlagged=devScan({isDeveloperTrade:true});\n' +
  '  const testSourced=devScan({tradeSource:"TEST"});\n' +
  '  const bothTagged=devScan({isDeveloperTrade:true,tradeSource:"TEST"});\n' +
  '  g.record("DEV-1","POSITIVE CONTROL: an untagged durable record on that setup DOES refuse it",\n' +
  '    !!realBlocks&&realBlocks.source==="durable"&&realBlocks.priorTradeId==="AGT|d",\n' +
  '    "refused via "+String(realBlocks&&realBlocks.matchedBy)+" -- so silence below is exclusion, not absence");\n' +
  '  g.record("DEV-2","a DEVELOPER test trade does NOT durably block the real setup -- on either tag, or both",\n' +
  '    devFlagged===null&&testSourced===null&&bothTagged===null,\n' +
  '    "isDeveloperTrade=true -> "+String(devFlagged)+", tradeSource=TEST -> "+String(testSourced)+\n' +
  '    ", both -> "+String(bothTagged)+" (the identical untagged record refuses it)");\n' +
  '  alexGAccount={balance:10000,openPositions:[],closedPositions:[]}; alexGJournalEntries=[];\n' +
  // ══ THE COUNT CAP: A BACKSTOP, AND WHAT IT COSTS ══════════════════════════════════════════
  // ALEXG_DECIDED_MAX had no fixture at all: setting it to 1 survived every suite. These pin the
  // two facts that matter -- it bounds BOTH maps, and it is NOT the operating bound, because unlike
  // the age prune it can evict a record that is still inside its staleness window.
  '  alexGResetLiveDecisionState();\n' +
  '  function synthDecided(i,over){ return Object.assign({pair:"EUR_JPY",timeframe:"H1",setupType:"B_breakRetest",\n' +
  '    reactionId:"AGR|EUR_JPY|H1|low|"+(1700000000000+i*3600000),\n' +
  '    qualificationTimestamp:QT,qualificationClose:Number((1.50000+i*0.00001).toFixed(5))},over||{}); }\n' +
  '  const CAPN=ALEXG_DECIDED_MAX;\n' +
  '  for(let i=0;i<CAPN+25;i++) alexGMarkSetupDecided(synthDecided(i),"AGL|cap|"+i);\n' +
  '  g.record("CAP-1","the backstop cap bounds BOTH maps, not just the stable one",\n' +
  '    alexGDecidedSetups.size===CAPN&&alexGDecidedEconomic.size===CAPN,\n' +
  '    "inserted "+(CAPN+25)+" distinct decisions -> stable="+alexGDecidedSetups.size+\n' +
  '    " economic="+alexGDecidedEconomic.size+" (cap "+CAPN+")");\n' +
  // The eviction ORDER as actually observed -- insertion order, oldest first -- rather than an
  // idealised least-recently-used or least-valuable policy.
  '  const capFirst=synthDecided(0),capLast=synthDecided(CAPN+24);\n' +
  '  g.record("CAP-2","and it evicts in INSERTION order: the first 25 recorded are gone, the newest is held",\n' +
  '    alexGFindPriorDecision(capFirst,"AGL|q1")===null&&\n' +
  '    alexGFindPriorDecision(synthDecided(24),"AGL|q2")===null&&\n' +
  '    !!alexGFindPriorDecision(synthDecided(25),"AGL|q3")&&\n' +
  '    !!alexGFindPriorDecision(capLast,"AGL|q4"),\n' +
  '    "records 0..24 evicted, 25 and "+(CAPN+24)+" retained -- oldest-first, not by remaining usefulness");\n' +
  // THE HONEST COST, stated rather than glossed: every one of those evicted records was still inside
  // its staleness window, so the cap CAN throw away a decision that could still have changed an
  // outcome. That is exactly what the age prune does not do, and why the cap is only a backstop.
  '  g.record("CAP-3","HONEST COST: the cap evicts records still INSIDE their staleness window -- unlike the age prune",\n' +
  '    alexGIsSetupSignalStale(capFirst,QT,RULES_ALEXG.config)===false&&\n' +
  '    alexGFindPriorDecision(capFirst,"AGL|q5")===null,\n' +
  '    "the evicted record is not stale at QT yet is no longer known -- a count cap cannot claim losslessness");\n' +
  // And the reason it is only a backstop: at production scale it never fires. One poll cycle is 388
  // setups against a cap of 5,000, so the AGE prune is what actually bounds the maps in service.
  '  alexGResetLiveDecisionState();\n' +
  '  const CYCLE=388;\n' +
  '  for(let i=0;i<CYCLE;i++) alexGMarkSetupDecided(synthDecided(i),"AGL|cycle|"+i);\n' +
  '  const cycleHeld=[];\n' +
  '  for(let i=0;i<CYCLE;i++) if(alexGFindPriorDecision(synthDecided(i),"AGL|c|"+i)) cycleHeld.push(i);\n' +
  '  g.record("CAP-4","the cap is a BACKSTOP, not the operating bound: a full production poll cycle evicts NOTHING",\n' +
  '    cycleHeld.length===CYCLE&&alexGDecidedSetups.size===CYCLE,\n' +
  '    "one cycle of "+CYCLE+" decisions, "+cycleHeld.length+" still known, cap="+CAPN+\n' +
  '    " -- a cap near the cycle size would silently drop live decisions");\n' +
  // ══ THE ECONOMIC INDEX IS AGE-EVICTED ON ITS OWN TERMS ════════════════════════════════════
  // The two maps are NOT guaranteed to hold the same key set. alexGMarkSetupDecided only writes a
  // key that is absent, and the count cap trims each map independently -- so when two setups share
  // one economic identity the economic map fills slower, the stable map hits the cap first, and the
  // economic map is left holding a record the stable map no longer has. A prune that walked only
  // the stable map would leave that orphan blocking for the rest of the session.
  //
  // Nothing here reaches into the maps: the orphan is produced by alexGMarkSetupDecided alone.
  '  alexGResetLiveDecisionState();\n' +
  '  const SHARED=1.99999;\n' +   // r0 and r1 share ONE economic identity and differ in stable identity
  '  const orph0=synthDecided(0,{qualificationClose:SHARED,qualificationTimestamp:QT-(H1LIM+120)*60000});\n' +
  '  const orph1=synthDecided(1,{qualificationClose:SHARED,qualificationTimestamp:QT-(H1LIM+60)*60000});\n' +
  '  alexGMarkSetupDecided(orph0,"AGL|orph0");\n' +
  '  alexGMarkSetupDecided(orph1,"AGL|orph1");\n' +
  '  for(let i=2;i<=CAPN;i++) alexGMarkSetupDecided(synthDecided(i),"AGL|orph|"+i);\n' +
  '  const orphEcon=alexGEconomicSetupIdentity(orph0);\n' +
  '  g.record("ORPHAN-1","precondition: the economic map holds a record the stable map no longer has",\n' +
  '    alexGDecidedSetups.size===CAPN&&alexGDecidedEconomic.size===CAPN&&\n' +
  '    !alexGDecidedSetups.has(alexGStableSetupIdentity(orph0))&&\n' +
  '    alexGDecidedEconomic.get(orphEcon)&&\n' +
  '    alexGDecidedEconomic.get(orphEcon).stableId===alexGStableSetupIdentity(orph0),\n' +
  '    "stable="+alexGDecidedSetups.size+" economic="+alexGDecidedEconomic.size+\n' +
  '    "; the orphan’s stable key was capped out while its economic key survived");\n' +
  // A DIFFERENT setup sharing that economic identity is what the orphan blocks. Before the prune it
  // is refused -- that is the state the prune has to release.
  '  const orphPeer=synthDecided(9999,{qualificationClose:SHARED,qualificationTimestamp:QT});\n' +
  '  const blockedBefore=!!alexGFindPriorDecision(orphPeer,"AGL|peer1");\n' +
  '  alexGPruneDecidedSetups(QT,RULES_ALEXG.config);\n' +
  '  g.record("ORPHAN-2","the age prune walks the ECONOMIC index on its own terms and evicts that orphan",\n' +
  '    blockedBefore===true&&alexGDecidedEconomic.has(orphEcon)===false&&\n' +
  '    alexGFindPriorDecision(orphPeer,"AGL|peer2")===null,\n' +
  '    "orphan aged out at its own qualificationTimestamp; a stable-map-only walk would never reach it "+\n' +
  '    "and would block this setup for the rest of the session");\n' +
  '  g.record("ORPHAN-3","and the walk is age-bounded, not a purge: the still-live economic entries survive it",\n' +
  '    alexGDecidedEconomic.size===CAPN-1&&\n' +
  '    !!alexGFindPriorDecision(synthDecided(CAPN),"AGL|peer3"),\n' +
  '    "economic entries after prune="+alexGDecidedEconomic.size+" of "+CAPN+" -- only the aged one left");\n' +
  '  alexGResetLiveDecisionState();\n' +
  // ══ THE AGE PRUNE IS WIRED INTO THE REAL POLL TICK ════════════════════════════════════════
  // DECIDED-8/9/10 call alexGPruneDecidedSetups DIRECTLY with the right config, so they test the
  // function and not the wiring. Deleting the call from alexGLivePollTick survived the whole gate --
  // and so did passing snapshotAlexGConfig(), which nests the rules under .config so
  // maxLiveSignalAgeMinutes reads undefined and the prune silently does nothing. That exact defect
  // shipped once in this milestone. This drives the REAL tick.
  //
  // Auto-trading is OFF for the tick on purpose: the poll prunes BEFORE the disabled check and
  // returns without evaluating anything, so the tick cannot re-mark the record it just evicted and
  // the observation is unambiguous.
  '  alexGAccount={balance:10000,openPositions:[],closedPositions:[]}; alexGJournalEntries=[];\n' +
  '  const PNOW=g.now();\n' +
  '  const agedDecided={pair:"NZD_USD",timeframe:"H1",setupType:"B_breakRetest",\n' +
  '    reactionId:"AGR|NZD_USD|H1|low|1700000000000",qualificationTimestamp:PNOW-(H1LIM+30)*60000,\n' +
  '    qualificationClose:0.61234};\n' +
  '  const freshDecided={pair:"NZD_USD",timeframe:"H1",setupType:"B_breakRetest",\n' +
  '    reactionId:"AGR|NZD_USD|H1|high|1700003600000",qualificationTimestamp:PNOW-(H1LIM-30)*60000,\n' +
  '    qualificationClose:0.62345};\n' +
  '  alexGMarkSetupDecided(agedDecided,"AGL|aged");\n' +
  '  alexGMarkSetupDecided(freshDecided,"AGL|fresh");\n' +
  '  const wiredBefore=!!alexGFindPriorDecision(agedDecided,"AGL|a1")&&!!alexGFindPriorDecision(freshDecided,"AGL|f1");\n' +
  '  const __enabledWas=alexGAutoTrading.enabled;\n' +
  '  alexGAutoTrading.enabled=false;\n' +
  '  await alexGLivePollTick();\n' +
  '  alexGAutoTrading.enabled=__enabledWas;\n' +
  '  const wiredObs=g.lastObs();\n' +
  // Every earlier poll in this suite ran with trading ENABLED and attempted all twelve pairs, so a
  // durable record carrying tradingEnabled=false and zero attempts can only have come from this
  // tick -- which is what makes it evidence that the tick really executed.
  '  g.record("WIRE-1","the tick really ran and evaluated nothing -- so nothing below can be a re-mark",\n' +
  '    wiredObs.tradingEnabled===false&&wiredObs.instrumentsAttempted===0&&\n' +
  '    (wiredObs.instrumentsEvaluated||[]).length===0,\n' +
  '    "tradingEnabled="+String(wiredObs.tradingEnabled)+" attempted="+String(wiredObs.instrumentsAttempted)+\n' +
  '    " evaluated="+((wiredObs.instrumentsEvaluated)||[]).length);\n' +
  '  g.record("WIRE-2","a REAL poll tick age-evicts an aged decided record and keeps a fresh one",\n' +
  '    wiredBefore===true&&alexGFindPriorDecision(agedDecided,"AGL|a2")===null&&\n' +
  '    !!alexGFindPriorDecision(freshDecided,"AGL|f2"),\n' +
  '    "aged by "+(H1LIM+30)+"m evicted, fresh at "+(H1LIM-30)+"m retained -- the prune is CALLED, "+\n' +
  '    "and called with the same config object the frozen staleness gate reads");\n' +
  '  alexGResetLiveDecisionState();\n' +
  // ══ A PAIR WITH TOO LITTLE H1 HISTORY IS SKIPPED, NOT COUNTED AS EVALUATED ════════════════
  // RESIL-1..3 above prove the pair is not evaluated and that the failure is recorded on the bus.
  // Neither reads the COVERAGE LEDGER, so flipping the early return to evaluated:true survived the
  // gate: the durable record would have claimed a pair was evaluated when the frozen engine was
  // never handed its data. A coverage row that contradicts what happened is a wrong report.
  '  g.setBadPair("EUR_USD"); alexGLastEvaluatedCloseTime={}; g.advanceHour();\n' +
  '  await alexGLivePollTick();\n' +
  '  const insObs=g.lastObs();\n' +
  '  const insSkip=(insObs.instrumentsSkipped||[]).filter(function(x){return x.pair==="EUR_USD";})[0];\n' +
  '  g.record("INSUF-1","a pair whose H1 dataset is too short is reported SKIPPED, never EVALUATED",\n' +
  '    (insObs.instrumentsEvaluated||[]).indexOf("EUR_USD")===-1&&!!insSkip&&\n' +
  '    insSkip.reason==="DATA_INSUFFICIENT_HISTORY",\n' +
  '    "skip reason="+String(insSkip&&insSkip.reason)+"; EUR_USD absent from instrumentsEvaluated");\n' +
  '  g.record("INSUF-2","and the ledger still accounts for every configured instrument exactly once",\n' +
  '    (insObs.instrumentsEvaluated||[]).length===SCAN_PAIRS.length-1&&\n' +
  '    insObs.instrumentsAttempted===SCAN_PAIRS.length&&\n' +
  '    (insObs.instrumentsEvaluated||[]).length+(insObs.instrumentsSkipped||[]).length===SCAN_PAIRS.length,\n' +
  '    "attempted="+insObs.instrumentsAttempted+" evaluated="+((insObs.instrumentsEvaluated)||[]).length+\n' +
  '    " skipped="+((insObs.instrumentsSkipped)||[]).length+" configured="+SCAN_PAIRS.length);\n' +
  '  g.setBadPair(null);\n' +
  // ══ MOGO-021 -- ALEX PIPELINE OBSERVATION ATTRIBUTION UNDER OVERLAPPING TICKS ══
  // alexGLivePollTick has no re-entrancy guard and is driven by setInterval, so two ticks can
  // overlap. The drain used to take the WHOLE shared buffer, so whichever tick drained second wrote
  // the other tick's rows under its own scanId -- the same read-shared-state-after-the-fact mistake
  // the JVM coverage ledger was refuted for twice, on the other engine.
  '  alexGPipelineObservationBuffer=[];\n' +
  '  alexGRecordPipelineStage("CANDIDATE",{scanId:"SCAN|A",pair:"EUR_USD",timeframe:"H1",setupId:"S|A",occurredAt:"2026-08-14T12:00:00.000Z"});\n' +
  '  alexGRecordPipelineStage("CANDIDATE",{scanId:"SCAN|B",pair:"GBP_USD",timeframe:"H1",setupId:"S|B",occurredAt:"2026-08-14T12:00:00.001Z"});\n' +
  '  const drainedA=alexGDrainPipelineObservations("SCAN|A");\n' +
  '  g.record("TICKATTR-1","a tick drains only the observation rows IT produced, never a concurrent tick\\u2019s",\n' +
  '    drainedA.length===1&&drainedA[0].pair==="EUR_USD"&&alexGPipelineObservationBuffer.length===1,\n' +
  '    "tick A drained "+drainedA.length+" row(s) ("+((drainedA[0]||{}).pair)+"); "+\n' +
  '    alexGPipelineObservationBuffer.length+" row(s) left for the concurrent tick");\n' +
  '  const drainedB=alexGDrainPipelineObservations("SCAN|B");\n' +
  '  g.record("TICKATTR-2","and the concurrent tick still gets its OWN row -- nothing is lost, only re-attributed",\n' +
  '    drainedB.length===1&&drainedB[0].pair==="GBP_USD"&&alexGPipelineObservationBuffer.length===0,\n' +
  '    "tick B drained "+drainedB.length+" row(s) ("+((drainedB[0]||{}).pair)+"); buffer now "+alexGPipelineObservationBuffer.length);\n' +
  // The stamp must not leak into the stored observation -- the durable record has to stay byte-identical.
  '  g.record("TICKATTR-3","the ownership stamp is non-enumerable, so the durable observation is unchanged",\n' +
  '    Object.keys(drainedA[0]).indexOf("__tickScanId")===-1&&\n' +
  '    JSON.parse(JSON.stringify(drainedA[0])).__tickScanId===undefined&&\n' +
  '    drainedA[0].__tickScanId==="SCAN|A",\n' +
  '    "readable for attribution, absent from every serialization");\n' +
  '  return g;\n' +
  '})();'
);

wrapped(g).then(function(){
  let failCount=0;
  results.forEach(function(r){
    const tag=r.pass?'PASS':'FAIL';
    if(!r.pass) failCount++;
    console.log(tag+' -- '+r.id+': '+r.desc+(r.detail?('  ['+r.detail+']'):''));
  });
  console.log('---');
  console.log(results.length+' fixtures, '+(results.length-failCount)+' PASS, '+failCount+' FAIL');
  if(failCount) console.log('FAILURES: '+failCount+'/'+results.length);
}).catch(function(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
  if(e&&e.stack) console.log(e.stack);
});
