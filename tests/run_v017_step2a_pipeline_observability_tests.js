// Self-contained runner for the MOGO-017 Step 2A (forward PAPER execution observability)
// fixture suite. Reads index.html directly and extracts its <script> body itself, following the
// same pattern as run_v126_phase2c_wave1_tests.js -- whose harness this deliberately mirrors,
// because that suite already drives the real engine all the way to a genuine TRADE OPENED.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v017_step2a_pipeline_observability_tests.js
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
const testCode=readFile('./tests/v017_step2a_pipeline_observability_tests.js');

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
  __clear:function(){Object.keys(lsStore).forEach(k=>delete lsStore[k]);},
  __isTestStub:function(){return true;}
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

// ── MOGO-002.8A DETERMINISM FIX ──────────────────────────────────────────────
// ALEX v1.1 adds a Monday-Wednesday entry-eligibility gate (ALEX_V11_001), which is
// evaluated against the live wall clock. Every fixture below that opens a real trade
// end-to-end would therefore PASS Mon/Tue/Wed and FAIL Thu/Fri/Sat/Sun with no code
// change whatsoever -- a date-dependent regression suite.
//
// This suite exists to verify DECISION-EVENT EMISSION, not day-of-week eligibility
// (which has its own dedicated coverage in v127_alex_v11_release_tests.js, fixtures
// B1-B13). Pinning the clock to a fixed eligible Monday keeps every assertion below
// testing exactly what it was written to test, deterministically, on any day.
//
// NOT A PRODUCTION CHANGE: this pins the clock for this test process only. Zero
// assertions are modified. Zero production code is modified.
const __PINNED_NOW=Date.UTC(2026,0,5,12,0,0); // Monday 2026-01-05 12:00 UTC
const __RealDate=Date;
function __PinnedDate(){
  if(arguments.length===0) return new __RealDate(__PINNED_NOW);
  if(arguments.length===1) return new __RealDate(arguments[0]);
  return new __RealDate(arguments[0],arguments[1],arguments[2]||1,arguments[3]||0,arguments[4]||0,arguments[5]||0,arguments[6]||0);
}
__PinnedDate.now=function(){return __PINNED_NOW;};
__PinnedDate.parse=__RealDate.parse;
__PinnedDate.UTC=__RealDate.UTC;
__PinnedDate.prototype=__RealDate.prototype;
globalThis.Date=__PinnedDate;

const g={};
const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // -- ALEX execution path under test (real, unmodified) --
  'g.alexGEvaluatePairForLiveSetups=alexGEvaluatePairForLiveSetups;' +
  'g.alexGAttemptOpenLivePosition=alexGAttemptOpenLivePosition;' +
  'g.alexGConstructLivePosition=alexGConstructLivePosition;' +   // PROTECTED -- called, never edited
  'g.alexGCheckLivePositions=alexGCheckLivePositions;' +
  'g.alexGLiveSignalId=alexGLiveSignalId;' +
  // -- MOGO-017 Step 2A instrumentation under test --
  'g.alexGRecordPipelineStage=alexGRecordPipelineStage;' +
  'g.drainPipeline=alexGDrainPipelineObservations;' +
  'g.pipelineBufferLength=function(){return alexGPipelineObservationBuffer.length;};' +
  'g.getPipelineBufferMax=function(){return EVIDENCE_PIPELINE_BUFFER_MAX;};' +
  'g.fillPipelineBufferToCap=function(){' +
  '  alexGPipelineObservationBuffer=[];' +
  '  for(var i=0;i<EVIDENCE_PIPELINE_BUFFER_MAX;i++) alexGPipelineObservationBuffer.push({kind:"PIPELINE",stage:"FILLER"});' +
  '};' +
  // -- MOGO-013 observation schema (real, unmodified) --
  'g.evidenceBuildPipelineObservation=evidenceBuildPipelineObservation;' +
  'g.evidenceObservationNaturalKey=evidenceObservationNaturalKey;' +
  'g.getObservationKinds=function(){return EVIDENCE_OBSERVATION_KINDS.slice();};' +
  // The durable writer is COUNTED, never allowed to run: this process has no IndexedDB, and the
  // isolation fixtures assert the count stayed at zero. Wrapping it here is what turns "it cannot
  // have written anything" from an argument into a measurement.
  'var __obsWriteAttempts=0;' +
  'var __realEvidencePutObservation=evidencePutObservation;' +
  'evidencePutObservation=function(){ __obsWriteAttempts++; return Promise.resolve({ok:false,reason:"TEST_HARNESS_NO_STORE"}); };' +
  'g.getObservationWriteAttempts=function(){return __obsWriteAttempts;};' +
  'void __realEvidencePutObservation;' +
  // -- Decision Event Bus (real, unmodified) --
  'g.emitDecisionEvent=emitDecisionEvent;' +
  'g.getDecisionEvents=getDecisionEvents;' +
  'g.clearDecisionEvents=clearDecisionEvents;' +
  // -- state get/set (ALEX) --
  'g.getAlexGSetupState=function(){return alexGSetupState;};g.setAlexGSetupState=function(v){alexGSetupState=v;};' +
  'g.getAlexGZoneState=function(){return alexGZoneState;};g.setAlexGZoneState=function(v){alexGZoneState=v;};' +
  'g.getAlexGLastEvaluatedCloseTime=function(){return alexGLastEvaluatedCloseTime;};g.setAlexGLastEvaluatedCloseTime=function(v){alexGLastEvaluatedCloseTime=v;};' +
  'g.getAlexGLiveSetupStatuses=function(){return alexGLiveSetupStatuses;};g.setAlexGLiveSetupStatuses=function(v){alexGLiveSetupStatuses=v;};' +
  'g.getAlexGAccount=function(){return alexGAccount;};g.setAlexGAccount=function(v){alexGAccount=v;};' +
  'g.getAlexGJournalEntries=function(){return alexGJournalEntries;};g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
  'g.getAlexGAutoTrading=function(){return alexGAutoTrading;};g.setAlexGAutoTrading=function(v){alexGAutoTrading=v;};' +
  'g.setAlexGAccountKnownVersion=function(v){alexGAccountKnownVersion=v;};' +
  // -- localStorage helpers --
  'g.clearLocalStorage=function(){localStorage.__clear();};' +
  // ── DETERMINISM, carried over verbatim from the v126 runner and for the same reasons ──
  // MOGO-002.8B suspends A_repeatedReaction from opening LIVE paper positions. Every fixture
  // here that opens a trade end to end builds an A_repeatedReaction setup, so all of them would
  // be correctly withheld by that gate. This suite exists to verify OBSERVABILITY, not setup
  // execution policy (covered by v127 fixtures K1-K23). Disabling the suspension for THIS TEST
  // PROCESS ONLY keeps every assertion testing what it was written to test.
  //
  // NOT A PRODUCTION CHANGE and NOT a weakening of the gate: the production default remains
  // setupSuspensionEnabled:true, asserted by v127 fixture K9. Zero production code is modified.
  'RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=false;' +
  'return runStep2APipelineObservabilityFixtures(g);'
);
wrapped(g).then(function(results){
  results.forEach(r=>{
    const tag = r.pass===null ? 'NOTE' : (r.pass?'PASS':'FAIL');
    console.log(tag+' -- '+r.name+(r.detail?' ('+r.detail+')':''));
  });
  const executed=results.filter(r=>r.pass!==null);
  const failCount=executed.filter(r=>!r.pass).length;
  console.log('---');
  console.log(failCount===0?('ALL MOGO-017 STEP 2A PIPELINE OBSERVABILITY FIXTURES PASSED ('+executed.length+' executed)'):('FAILURES: '+failCount+'/'+executed.length));
}).catch(function(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
  if(e&&e.stack) console.log(e.stack);
});
