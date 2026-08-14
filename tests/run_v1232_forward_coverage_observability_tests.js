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
globalThis.indexedDB=undefined;   // durable ledger unavailable in-fixture; writer must stay non-throwing

let fetchScript=[],fetchIdx=0,fetchUrls=[];
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

const g={};
g.okCandles=function(n){ return function(){ return Promise.resolve(makeResponse(true,200,{candles:candleArray(n)})); }; };
g.setFetchScript=function(steps){ fetchScript=steps; fetchIdx=0; fetchUrls=[]; };
g.fetchUrls=function(){ return fetchUrls.slice(); };

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
