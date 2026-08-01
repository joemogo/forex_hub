// Self-contained runner for the INC-001 load-integrity + INC-004 browser-isolation guard suite.
// Reads index.html directly and extracts its <script> body itself, following the same pattern as
// run_v128_evidence_platform_tests.js and run_v127_alex_v11_release_tests.js.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v129_browser_isolation_guard_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically)
//
// This suite opens NO browser and touches NO Chrome profile. The isolation launcher
// (scripts/browser_test_profile.sh) is read as text and statically asserted — never executed.
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
const testCode=readFile('./tests/v129_browser_isolation_guard_tests.js');

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

// Controllable localStorage stub -- the INC-001 fixtures drive the REAL loaders and savers
// through it. Nothing here touches a real browser profile; this is an in-memory object.
let lsStore={};
let getItemThrowing=false;
globalThis.document={
  getElementById:function(id){ if(!elMap[id]) elMap[id]=makeStub(); return elMap[id]; },
  querySelector:function(){return null;},querySelectorAll:function(){return [];},
  createElement:function(){return makeStub();},addEventListener:function(){},
  visibilityState:'visible',body:{appendChild:function(){},removeChild:function(){}},activeElement:null
};
globalThis.window={devicePixelRatio:1};
globalThis.localStorage={
  getItem:function(k){
    if(getItemThrowing){ const e=new Error('storage read denied'); e.name='SecurityError'; throw e; }
    return Object.prototype.hasOwnProperty.call(lsStore,k)?lsStore[k]:null;
  },
  setItem:function(k,v){ lsStore[k]=String(v); },
  removeItem:function(k){ delete lsStore[k]; },
  __keys:function(){return Object.keys(lsStore);}
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
g.appSource=appCode;
g.shellSource=readFile('./scripts/browser_test_profile.sh');
g.v128Source=readFile('./tests/v128_evidence_platform_tests.js');
g.v129Source=testCode;
g.testingDoc=readFile('./docs/TESTING.md');
g.incidentsDoc=readFile('./docs/INCIDENTS.md');
g.knownIssuesDoc=readFile('./docs/KNOWN_ISSUES.md');
g.resetStorage=function(seed){ lsStore={}; Object.keys(seed||{}).forEach(function(k){ lsStore[k]=seed[k]; }); };
g.rawStorage=function(){ return lsStore; };
g.setGetItemThrowing=function(on){ getItemThrowing=!!on; };

const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // ── INC-001 surface under test (real, unmodified) ──
  'g.loadSaved=loadSaved;' +
  'g.loadAlexGSaved=loadAlexGSaved;' +
  'g.loadAlexV2Saved=loadAlexV2Saved;' +
  'g.saveJvm=save;' +
  'g.saveAlexGRest=saveAlexGRest;' +
  'g.savePaperAccountGuarded=savePaperAccountGuarded;' +
  'g.saveAlexGAccountGuarded=saveAlexGAccountGuarded;' +
  'g.storageKeyBlockedFromWrite=storageKeyBlockedFromWrite;' +
  'g.storageLoadFailureKeys=storageLoadFailureKeys;' +
  'g.persistStorageKey=persistStorageKey;' +
  'g.resetLoadFailures=function(){storageLoadFailures={};};' +
  // ── live-binding accessors, so a fixture observes what the real code actually did ──
  'g.getJournalEntries=function(){return journalEntries;};' +
  'g.getPaperAccount=function(){return paperAccount;};' +
  'g.getPaperAccountKnownVersion=function(){return paperAccountKnownVersion;};' +
  'g.setScanData=function(v){scanData=v;};' +
  'g.setAlertLog=function(v){alertLog=v;};' +
  'g.getAlexGSetupState=function(){return alexGSetupState;};' +
  'g.setAlexGZoneState=function(v){alexGZoneState=v;};' +
  'g.getAlexGAccountKnownVersion=function(){return alexGAccountKnownVersion;};' +
  'g.setAlexGAccountKnownVersion=function(v){alexGAccountKnownVersion=v;};' +
  'g.getAlexV2JournalEntries=function(){return alexV2JournalEntries;};' +
  'g.getAlexGEngineErrors=function(){return alexGEngineErrors;};' +
  'g.getPaperEngineErrors=function(){return paperEngineErrors;};' +
  'g.clearEngineErrors=function(){alexGEngineErrors=[];paperEngineErrors=[];};' +
  'return runBrowserIsolationGuardFixtures(g);'
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
    ? ('ALL INC-001 / INC-004 GUARD FIXTURES PASSED ('+executed.length+' executed)')
    : ('FAILURES: '+failCount+'/'+executed.length+' executed'));
}catch(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
  if(e&&e.stack) console.log(e.stack);
}
