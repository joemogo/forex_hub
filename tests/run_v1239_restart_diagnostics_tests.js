// Self-contained runner for the v12.3.9 RESTART / RECOVERY and DIAGNOSTICS / OBSERVABILITY
// fixture suite. Reads index.html directly and extracts its <script> body itself -- same pattern
// as run_v_paper_trading_audit_tests.js.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1239_restart_diagnostics_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically)
//
// ── WHY THIS RUNNER IS ASYNCHRONOUS ────────────────────────────────────────────────────────
// The restart fixtures need a GENUINELY CLOSED position before the simulated restart, and the
// only way to get one is the real, protected, `async` closePaperPosition() -- every value this
// suite asserts across the reload (exitPrice, pnl, balance, the closedPositions entry itself)
// is produced AFTER its one internal `await fetchBidAsk(...)`. A fixture that called it without
// awaiting would assert on state from BEFORE the close ran and pass against a completely broken
// close path; that exact false-green has already occurred in this repository. This suite
// therefore returns a Promise, the runner prints from its .then() continuation (JavaScriptCore
// drains its microtask queue once the top-level body finishes), and every close is `await`ed.
// See run_v1238_execution_reporting_journal_tests.js for the full reasoning.
//
// The clock CONSTRUCTOR is frozen (not just Date.now), because the close path timestamps with
// `new Date().toISOString()`.
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
function makeClassList(){
  const classes=new Set();
  return{
    add:function(c){classes.add(c);},
    remove:function(c){classes.delete(c);},
    toggle:function(c,force){ if(force===undefined){ if(classes.has(c)) classes.delete(c); else classes.add(c); } else if(force) classes.add(c); else classes.delete(c); },
    contains:function(c){return classes.has(c);}
  };
}
const elMap={};
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
  __raw:function(){return lsStore;},
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

function emit(results){
  results.forEach(r=>{
    const tag = r.pass===null ? 'NOTE' : (r.pass?'PASS':'FAIL');
    console.log(tag+' -- '+r.name+(r.detail?' ('+r.detail+')':''));
  });
  const executed=results.filter(r=>r.pass!==null);
  const failCount=executed.filter(r=>!r.pass).length;
  console.log('---');
  console.log(failCount===0
    ?('ALL RESTART/DIAGNOSTICS FIXTURES PASSED ('+executed.length+' executed)')
    :('FAILURES: '+failCount+'/'+executed.length+' executed'));
}

try{
  const html=readFile('./index.html');
  const appCode=extractScriptBody(html);
  const testCode=readFile('./tests/v1239_restart_diagnostics_tests.js');
  const g={};
  const wrapped = new Function('g',
    appCode + '\n' + testCode + '\n' +
    // ── the REAL loaders / savers / engines under test (never stubbed, never wrapped) ──
    'g.loadSaved=loadSaved;' +
    'g.loadAlexGSaved=loadAlexGSaved;' +
    'g.savePaperAccountGuarded=savePaperAccountGuarded;' +
    'g.saveAlexGAccountGuarded=saveAlexGAccountGuarded;' +
    'g.saveAlexGRest=saveAlexGRest;' +
    'g.commitPaperLedger=commitPaperLedger;' +
    'g.openPaperPosition=openPaperPosition;' +
    'g.closePaperPosition=closePaperPosition;' +
    'g.recordPaperEngineError=recordPaperEngineError;' +
    'g.recordAlexGEngineError=recordAlexGEngineError;' +
    'g.storageKeyBlockedFromWrite=storageKeyBlockedFromWrite;' +
    'g.storageLoadFailureKeys=storageLoadFailureKeys;' +
    'g.computePaperTradingHealthReport=computePaperTradingHealthReport;' +
    'g.buildPaperTradingHealthReportText=buildPaperTradingHealthReportText;' +
    'g.renderPaperTradingHealthCheck=renderPaperTradingHealthCheck;' +
    'g.renderPaperLedgerIntegrity=renderPaperLedgerIntegrity;' +
    'g.renderAlexGLivePanel=renderAlexGLivePanel;' +
    'g.setAlexGLedgerBlockingError=function(v){alexGLedgerBlockingError=v;};' +
    'g.evidenceSummarizeObservations=evidenceSummarizeObservations;' +
    'g.evidenceContinuityHtml=evidenceContinuityHtml;' +
    'g.EVIDENCE_POLL_EXPECTED_INTERVAL_MS=EVIDENCE_POLL_EXPECTED_INTERVAL_MS;' +
    // ── state get/set ──
    'g.getPaperAccount=function(){return paperAccount;};g.setPaperAccount=function(v){paperAccount=v;};' +
    'g.getJournalEntries=function(){return journalEntries;};g.setJournalEntries=function(v){journalEntries=v;};' +
    'g.getAlexGAccount=function(){return alexGAccount;};g.setAlexGAccount=function(v){alexGAccount=v;};' +
    'g.getAlexGJournalEntries=function(){return alexGJournalEntries;};g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
    'g.getAlexGSetupState=function(){return alexGSetupState;};g.setAlexGSetupState=function(v){alexGSetupState=v;};' +
    'g.getAlexGZoneState=function(){return alexGZoneState;};g.setAlexGZoneState=function(v){alexGZoneState=v;};' +
    'g.getPaperEngineErrors=function(){return paperEngineErrors;};g.setPaperEngineErrors=function(v){paperEngineErrors=v;};' +
    'g.getAlexGEngineErrors=function(){return alexGEngineErrors;};g.setAlexGEngineErrors=function(v){alexGEngineErrors=v;};' +
    'g.getPaperLifecycleLog=function(){return paperLifecycleLog;};g.setPaperLifecycleLog=function(v){paperLifecycleLog=v;};' +
    'g.getPaperReconciliationAudit=function(){return paperReconciliationAudit;};g.setPaperReconciliationAudit=function(v){paperReconciliationAudit=v;};' +
    'g.getPaperAccountKnownVersion=function(){return paperAccountKnownVersion;};g.setPaperAccountKnownVersion=function(v){paperAccountKnownVersion=v;};' +
    'g.getAlexGAccountKnownVersion=function(){return alexGAccountKnownVersion;};g.setAlexGAccountKnownVersion=function(v){alexGAccountKnownVersion=v;};' +
    'g.setDeveloperMode=function(v){developerModeEnabled=!!v;};' +
    'g.toggleDeveloperMode=function(v){developerModeEnabled=!!v; applyDeveloperModeVisibility();};' +
    'g.setPairData=function(pair,price){ if(price===null||price===undefined){ delete pairData[pair]; } else { pairData[pair]={price:price}; } };' +
    'g.resetPaperPositionsClosing=function(){paperPositionsClosing.clear();};' +
    // storageLoadFailures is module-level session state: a fixture must be able to put the
    // session back to "nothing has failed yet", exactly as a fresh page load would.
    'g.resetLoadFailures=function(){storageLoadFailures={};};' +
    // ── localStorage helpers ──
    'g.rawStorage=function(){return localStorage.__raw();};' +
    'g.storageKeys=function(){return localStorage.__keys();};' +
    'g.getLocalStorageItem=function(k){return localStorage.getItem(k);};' +
    'g.setLocalStorageItem=function(k,v){localStorage.setItem(k,v);};' +
    'g.clearLocalStorage=function(){localStorage.__clear();};' +
    'g.elHtml=function(id){ var e=document.getElementById(id); return e?String(e.innerHTML||""):null; };' +
    'g.elText=function(id){ var e=document.getElementById(id); return e?String(e.textContent||""):null; };' +
    // ── clock control: patches the Date CONSTRUCTOR, not only Date.now, because every timestamp
    //    on the close/journal/error path is `new Date().toISOString()` ──
    'g.freezeClock=function(ms){' +
    '  if(!g.__RealDate){ g.__RealDate=Date; }' +
    '  var RD=g.__RealDate;' +
    '  var F=function(){ var a=arguments;' +
    '    switch(a.length){' +
    '      case 0: return new RD(ms);' +
    '      case 1: return new RD(a[0]);' +
    '      case 2: return new RD(a[0],a[1]);' +
    '      case 3: return new RD(a[0],a[1],a[2]);' +
    '      case 4: return new RD(a[0],a[1],a[2],a[3]);' +
    '      case 5: return new RD(a[0],a[1],a[2],a[3],a[4]);' +
    '      case 6: return new RD(a[0],a[1],a[2],a[3],a[4],a[5]);' +
    '      default: return new RD(a[0],a[1],a[2],a[3],a[4],a[5],a[6]);' +
    '    } };' +
    '  F.now=function(){ return ms; }; F.parse=RD.parse; F.UTC=RD.UTC; F.prototype=RD.prototype;' +
    '  Date=F;' +
    '};' +
    'g.restoreClock=function(){ if(g.__RealDate){ Date=g.__RealDate; g.__RealDate=null; } };' +
    'return runV1239RestartDiagnosticsFixtures(g);'
  );
  const out = wrapped(g);
  if(out && typeof out.then==='function'){
    out.then(function(results){
      try{ emit(results); }
      catch(e){ console.log('RUNNER ERROR: emitting results failed -- '+e); }
    }, function(err){
      console.log('RUNNER ERROR: fixture suite rejected -- '+err);
    });
  } else {
    console.log('RUNNER ERROR: the fixture suite did not return a Promise -- an un-awaited async suite is a proven false-green in this repository and is refused rather than reported as passing.');
  }
}catch(e){
  console.log('RUNNER ERROR: '+e);
}
// osascript prints the script's own completion value; without this the suite's pending Promise
// would be echoed as a stray "[object Promise]" line after the results.
void 0;
