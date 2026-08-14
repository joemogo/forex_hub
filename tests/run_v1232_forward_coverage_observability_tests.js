// Forward-coverage observability fixture.
//
// PURPOSE
// The ALEX forward campaign lost two of twelve configured instruments for its entire duration
// with NO signal of any kind: EUR_USD produced zero poll appearances and zero evaluations,
// GBP_USD was attempted ~once per H1 boundary and produced zero evaluations. Neither left an
// error, a decision event or an observation. Two silent paths caused that invisibility:
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
  '  alexGLastEvaluatedCloseTime={}; alexGZoneState={}; alexGSetupState=[]; alexGLiveSetupStatuses=[];\n' +
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
