// Self-contained runner for the PROGRAM-001 Phase 2A (Decision Event Schema & Observability
// Foundation) fixture suite. Requires no separate extraction/preprocessing step -- reads
// index.html directly and extracts its <script> body itself, following the same pattern as
// run_v124_baseline_registry_tests.js / run_v_paper_trading_audit_tests.js.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v125_decision_event_tests.js
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
const testCode=readFile('./tests/v125_decision_event_tests.js');

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
  // -- Decision Event Bus functions under test (real, unmodified) --
  'g.createDecisionEvent=createDecisionEvent;' +
  'g.emitDecisionEvent=emitDecisionEvent;' +
  'g.getDecisionEvents=getDecisionEvents;' +
  'g.clearDecisionEvents=clearDecisionEvents;' +
  'g.validateDecisionEvent=validateDecisionEvent;' +
  'g.generateDecisionEventId=generateDecisionEventId;' +
  'g.renderDecisionEventDiagnostics=renderDecisionEventDiagnostics;' +
  'g.getDecisionEventCardEl=function(){return document.getElementById("decisionEventDiagnosticsCard");};' +
  'g.getDecisionEventSchemaVersion=function(){return DECISION_EVENT_SCHEMA_VERSION;};' +
  'g.getDecisionEventTypes=function(){return DECISION_EVENT_TYPES;};' +
  'g.getReasonCodeRegistry=function(){return REASON_CODE_REGISTRY;};' +
  'g.getReasonCodeCategories=function(){return REASON_CODE_CATEGORIES;};' +
  'g.getEvidenceCompletenessLevels=function(){return EVIDENCE_COMPLETENESS_LEVELS;};' +
  'g.getEvidenceFieldProvenance=function(){return EVIDENCE_FIELD_PROVENANCE;};' +
  'g.getDecisionEventValidationFailures=function(){return decisionEventValidationFailures;};' +
  'g.getDecisionEventMaxPayloadChars=function(){return DECISION_EVENT_MAX_PAYLOAD_CHARS;};' +
  'g.getDecisionEventMaxLogSize=function(){return DECISION_EVENT_MAX_LOG_SIZE;};' +
  // -- scan-boundary functions under test (real, unmodified aside from this phase's wrap) --
  'g.scanAll=scanAll;' +
  'g.alexGLivePollTick=alexGLivePollTick;' +
  // -- Baseline Registry (Phase 1) cross-feature isolation checks --
  'g.computeBaselineRegistry=computeBaselineRegistry;' +
  'g.getBaselineJvmFunctions=function(){return BASELINE_JVM_FUNCTIONS;};' +
  'g.getBaselineAlexFunctions=function(){return BASELINE_ALEX_FUNCTIONS;};' +
  'g.getPersistedBaselineRegistry=getPersistedBaselineRegistry;' +
  // -- Developer Mode toggle --
  'g.setDeveloperMode=function(v){developerModeEnabled=v;};' +
  // -- state get/set (mutation-safety checks) --
  'g.getJournalEntries=function(){return journalEntries;};g.setJournalEntries=function(v){journalEntries=v;};' +
  'g.getPaperAccount=function(){return paperAccount;};g.setPaperAccount=function(v){paperAccount=v;};' +
  'g.getAlexGAccount=function(){return alexGAccount;};g.setAlexGAccount=function(v){alexGAccount=v;};' +
  'g.getAlexGJournalEntries=function(){return alexGJournalEntries;};g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
  'g.getScanData=function(){return scanData;};' +
  'g.getAutoTrading=function(){return autoTrading;};' +
  'g.getAlexGAutoTrading=function(){return alexGAutoTrading;};' +
  // -- localStorage helpers --
  'g.getLocalStorageItem=function(k){return localStorage.getItem(k);};' +
  'g.setLocalStorageItem=function(k,v){localStorage.setItem(k,v);};' +
  'g.clearLocalStorage=function(){localStorage.__clear();};' +
  'g.getAllLocalStorageKeys=function(){return localStorage.__keys();};' +
  'return runDecisionEventFixtures(g);'
);
const results = wrapped(g);
results.forEach(r=>{
  const tag = r.pass===null ? (r.method==='source-verified'?'NOTE(source)':'NOTE(live-browser)') : (r.pass?'PASS':'FAIL');
  console.log(tag+' -- '+r.name+(r.detail?' ('+r.detail+')':''));
});
const executed=results.filter(r=>r.pass!==null);
const failCount=executed.filter(r=>!r.pass).length;
const noteCount=results.length-executed.length;
console.log('---');
console.log(failCount===0?('ALL DECISION EVENT FIXTURES PASSED ('+executed.length+' executed, '+noteCount+' disclosed notes)'):('FAILURES: '+failCount+'/'+executed.length+' executed ('+noteCount+' disclosed notes)'));
