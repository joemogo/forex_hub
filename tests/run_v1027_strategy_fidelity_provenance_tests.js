// Self-contained runner for the MOGO-002.5 (Strategy Fidelity Audit) provenance fixture
// suite. Reads index.html directly and extracts its <script> body itself, following the
// same pattern as run_v126_phase2c_wave1_tests.js and run_v125_decision_event_tests.js.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1027_strategy_fidelity_provenance_tests.js
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
const testCode=readFile('./tests/v1027_strategy_fidelity_provenance_tests.js');

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
  // -- MOGO-002.5 Phase 5 provenance functions under test (real, unmodified) --
  'g.alexGStableHash=alexGStableHash;' +
  'g.alexGStrategyVersionReference=alexGStrategyVersionReference;' +
  'g.alexGStampTradeProvenance=alexGStampTradeProvenance;' +
  'g.alexGClassifyTradeProvenance=alexGClassifyTradeProvenance;' +
  'g.alexGProvenanceSummary=alexGProvenanceSummary;' +
  'g.getAlexProvenanceClasses=function(){return ALEX_PROVENANCE_CLASSES;};' +
  'g.getAlexProvenanceSchemaVersion=function(){return ALEX_PROVENANCE_SCHEMA_VERSION;};' +
  'g.getAlexImplementationVersion=function(){return ALEX_IMPLEMENTATION_VERSION;};' +
  // -- REAL, PROTECTED ALEX functions (called, never re-implemented) --
  'g.alexGEvaluateRepeatedReaction=alexGEvaluateRepeatedReaction;' +
  'g.alexGDetermineTradeDirection=alexGDetermineTradeDirection;' +
  'g.alexGZoneRole=alexGZoneRole;' +
  'g.alexGDetermineFromSide=alexGDetermineFromSide;' +
  'g.alexGComputeTrendContext=alexGComputeTrendContext;' +
  'g.alexGComputeSessionMetadata=alexGComputeSessionMetadata;' +
  'g.snapshotAlexGConfig=snapshotAlexGConfig;' +
  // -- protected constants / app version (read-only accessors) --
  'g.getRulesAlexG=function(){return RULES_ALEXG;};' +
  'g.getAppVersion=function(){return APP_VERSION;};' +
  'g.getDecisionEventSchemaVersion=function(){return DECISION_EVENT_SCHEMA_VERSION;};' +
  // -- state get/set (ALEX) --
  'g.getAlexGAccount=function(){return alexGAccount;};' +
  'g.getAlexGJournalEntries=function(){return alexGJournalEntries;};' +
  // -- localStorage helpers --
  'g.getAllLocalStorageKeys=function(){return localStorage.__keys();};' +
  'return runStrategyFidelityProvenanceFixtures(g);'
);
try{
  const results=wrapped(g);
  results.forEach(r=>{
    const tag = r.pass===null ? 'NOTE(source)' : (r.pass?'PASS':'FAIL');
    console.log(tag+' -- '+r.name+(r.detail?' ('+r.detail+')':''));
  });
  const executed=results.filter(r=>r.pass!==null);
  const failCount=executed.filter(r=>!r.pass).length;
  const noteCount=results.length-executed.length;
  console.log('---');
  console.log(failCount===0
    ? ('ALL STRATEGY FIDELITY PROVENANCE FIXTURES PASSED ('+executed.length+' executed, '+noteCount+' disclosed notes)')
    : ('FAILURES: '+failCount+'/'+executed.length+' executed ('+noteCount+' disclosed notes)'));
}catch(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
  if(e&&e.stack) console.log(e.stack);
}
