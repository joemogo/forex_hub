// Self-contained runner for the v12.38 execution-reporting AGGREGATE STATISTICS fixture suite.
// Reads index.html directly and extracts its <script> body itself -- the same offline JXA harness
// pattern every other suite in this repository uses (stubbed DOM/localStorage/fetch, no real
// browser storage ever touched, no paper trade ever persisted).
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1238_execution_reporting_stats_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically)
ObjC.import('Foundation');
function readFile(path){
  const s=$.NSString.stringWithContentsOfFileEncodingError(path,$.NSUTF8StringEncoding,null);
  return ObjC.unwrap(s);
}
function extractScriptBody(html){
  const m=html.match(/<script>([\s\S]*)<\/script>/);
  if(!m) throw new Error('Could not find <script>...</script> body in index.html -- run this from the project root.');
  return m[1];
}
const html=readFile('./index.html');
const appCode=extractScriptBody(html);
const testCode=readFile('./tests/v1238_execution_reporting_stats_tests.js');

const elMap={};
function makeClassList(){
  const classes=new Set();
  return{
    add:function(c){classes.add(c);},
    remove:function(c){classes.delete(c);},
    toggle:function(c,force){ if(force===undefined){ if(classes.has(c)) classes.delete(c); else classes.add(c); } else if(force) classes.add(c); else classes.delete(c); },
    contains:function(c){return classes.has(c);}
  };
}
function makeStub(){
  return {innerHTML:'',textContent:'',value:'',className:'',style:{},options:[{value:'All'}],width:100,height:100,disabled:false,checked:false,
    classList:makeClassList(),
    getContext:function(){return{clearRect:function(){},beginPath:function(){},moveTo:function(){},lineTo:function(){},stroke:function(){},fillRect:function(){},save:function(){},restore:function(){},setLineDash:function(){},arc:function(){},fill:function(){},closePath:function(){},fillText:function(){},measureText:function(){return{width:0};}};},
    appendChild:function(){},addEventListener:function(){},focus:function(){},setSelectionRange:function(){},
    getBoundingClientRect:function(){return{top:0,left:0,width:0,height:0};}};
}
const lsStore={};
globalThis.document={
  getElementById:function(id){ if(!elMap[id]) elMap[id]=makeStub(); return elMap[id]; },
  querySelector:function(){return null;},
  querySelectorAll:function(){return [];},
  createElement:function(){return makeStub();},
  addEventListener:function(){},
  body:{appendChild:function(){},removeChild:function(){}},
  activeElement:null
};
globalThis.window={devicePixelRatio:1};
globalThis.localStorage={
  getItem:function(k){return Object.prototype.hasOwnProperty.call(lsStore,k)?lsStore[k]:null;},
  setItem:function(k,v){lsStore[k]=v;},
  removeItem:function(k){delete lsStore[k];},
  __keys:function(){return Object.keys(lsStore);},
  __clear:function(){Object.keys(lsStore).forEach(k=>delete lsStore[k]);}
};
globalThis.fetch=function(){return Promise.reject(new Error('no network'));};
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

const g={};
let results;
try{
  const wrapped = new Function('g',
    appCode + '\n' + testCode + '\n' +
    // -- the six aggregate/derived statistics engines under test, real and unmodified.
    //    alexGComputeReplayStats is PROTECTED: it is exported so its OUTPUT can be observed,
    //    and is never modified, wrapped or re-implemented by this suite.
    'g.computeGroupTradeStats=computeGroupTradeStats;' +
    'g.computeReplayStats=computeReplayStats;' +
    'g.alexGComputeReplayStats=alexGComputeReplayStats;' +
    'g.computeCanonicalPerformance=computeCanonicalPerformance;' +
    'g.ledgerDeriveAccountState=ledgerDeriveAccountState;' +
    'g.alexGComputeEquityStats=alexGComputeEquityStats;' +
    'return runV1238ExecutionReportingStatsFixtures(g);'
  );
  results = wrapped(g);
}catch(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
  results = [];
}
results.forEach(r=>{
  console.log((r.pass?'PASS':'FAIL')+' -- '+r.name+(r.detail?' ('+r.detail+')':''));
});
const failCount=results.filter(r=>!r.pass).length;
console.log('---');
// ZERO EXECUTED IS NOT SUCCESS (§18.12). On an internal throw the catch above sets results=[],
// which made failCount 0 and printed "ALL ... PASSED (0 executed)" -- a green last line for a
// suite that ran nothing. run_all.sh catches it twice over (zero fixtures, and the RUNNER ERROR
// line), so the gate was never fooled; a human reading the suite standalone was.
console.log(results.length===0
  ?'SUITE DID NOT RUN -- 0 fixtures executed. This is a FAILURE, not a pass; see the RUNNER ERROR above.'
  :(failCount===0
    ?('ALL v12.38 EXECUTION REPORTING STATISTICS FIXTURES PASSED ('+results.length+' executed)')
    :('FAILURES: '+failCount+'/'+results.length+' executed')));
