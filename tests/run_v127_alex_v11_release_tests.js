// Self-contained runner for the MOGO-002.8A (ALEX v1.1 Release) fixture
// suite. Reads index.html directly and extracts its <script> body itself, following the
// same pattern as run_v126_phase2c_wave1_tests.js and run_v125_decision_event_tests.js.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v127_alex_v11_release_tests.js
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
const testCode=readFile('./tests/v127_alex_v11_release_tests.js');

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
const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // -- v1.1 release surface under test (real, unmodified) --
  'g.getRulesAlexGV11=function(){return RULES_ALEXG_V11;};' +
  'g.getAlexV11RuleVersion=function(){return ALEX_V11_RULE_VERSION;};' +
  'g.getAlexV11IntroducedInEngine=function(){return ALEX_V11_INTRODUCED_IN_ENGINE;};' +
  'g.alexGV11EntryDayEligible=alexGV11EntryDayEligible;' +
  'g.alexGV11SetupTypePermitted=alexGV11SetupTypePermitted;' +
  'g.getReasonCodeRegistry=function(){return REASON_CODE_REGISTRY;};' +
  'g.emitDecisionEvent=emitDecisionEvent;' +
  'g.getDecisionEvents=getDecisionEvents;' +
  'g.alexGEvaluateBreakRetest=alexGEvaluateBreakRetest;' +
  'g.alexGUpdatePositionExcursionAndCheckExit=alexGUpdatePositionExcursionAndCheckExit;' +
  'g.alexGRealizedR=alexGRealizedR;' +
  'g.alexGComputeEquityStats=alexGComputeEquityStats;' +
  'g.alexGStartingBalance=alexGStartingBalance;' +
  // -- provenance (real) --
  'g.alexGStrategyVersionReference=alexGStrategyVersionReference;' +
  'g.alexGStampTradeProvenance=alexGStampTradeProvenance;' +
  'g.alexGClassifyTradeProvenance=alexGClassifyTradeProvenance;' +
  'g.alexGProvenanceSummary=alexGProvenanceSummary;' +
  // -- REAL, PROTECTED ALEX functions (called, never re-implemented) --
  'g.alexGEvaluateRepeatedReaction=alexGEvaluateRepeatedReaction;' +
  'g.alexGDetermineTradeDirection=alexGDetermineTradeDirection;' +
  'g.alexGZoneRole=alexGZoneRole;' +
  'g.alexGLiveSignalId=alexGLiveSignalId;' +
  'g.alexGTradeId=alexGTradeId;' +
  'g.isPreferredTradingDay=isPreferredTradingDay;' +
  // -- protected constants / app version (read-only accessors) --
  'g.getRulesAlexG=function(){return RULES_ALEXG;};' +
  'g.getAppVersion=function(){return APP_VERSION;};' +
  'g.getAlexGAccount=function(){return alexGAccount;};' +
  'return runAlexV11ReleaseFixtures(g);'
);
try{
  const results=wrapped(g);
  results.forEach(r=>{
    const tag = r.pass===null ? 'NOTE(source)' : (r.pass?'PASS':'FAIL');
    console.log(tag+' -- '+r.name+(r.detail?' ('+r.detail+')':''));
  });
  const executed=results.filter(r=>r.pass!==null);
  const failCount=executed.filter(r=>!r.pass).length;
  console.log('---');
  console.log(failCount===0
    ? ('ALL ALEX v1.1 RELEASE FIXTURES PASSED ('+executed.length+' executed)')
    : ('FAILURES: '+failCount+'/'+executed.length+' executed'));
}catch(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
  if(e&&e.stack) console.log(e.stack);
}
