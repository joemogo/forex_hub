// Self-contained runner for the v12.3.8 Execution-Reporting Provenance fixture suite
// (MOGO tranche D: record classification, trade notes, export/evidence).
//
// Modelled on tests/run_v_paper_trading_audit_tests.js -- reads index.html directly, extracts
// its <script> body, stubs the DOM/localStorage, and exposes the real app internals onto `g.`.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1238_execution_reporting_provenance_tests.js
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
const testCode=readFile('./tests/v1238_execution_reporting_provenance_tests.js');

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
    appendChild:function(){},addEventListener:function(){},focus:function(){},click:function(){},setSelectionRange:function(){},
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
// The CSV/JSON export path is genuinely `new Blob([text]) -> URL.createObjectURL -> a.click()`.
// Capturing the Blob's own parts is the only way to observe the exact bytes the real
// exportReplayDiagnosticsCSV() would hand the browser, without changing the production path.
let __lastDownload=null;
globalThis.Blob=function(parts,opts){ __lastDownload={parts:parts,opts:opts,text:(parts||[]).join('')}; return{parts,opts};};
globalThis.URL={createObjectURL:function(){return 'blob:stub';},revokeObjectURL:function(){}};
let __fakeTimerId=0;
globalThis.setTimeout=function(){return ++__fakeTimerId;};globalThis.clearTimeout=function(){};
globalThis.setInterval=function(){return ++__fakeTimerId;};globalThis.clearInterval=function(){};
globalThis.ResizeObserver=function(){return{observe:function(){},disconnect:function(){}};};
globalThis.LightweightCharts={LineStyle:{Solid:0,Dashed:1,Dotted:2},CrosshairMode:{Normal:0}};
globalThis.Notification=undefined;

const g={};
g.getLastDownload=function(){ return __lastDownload; };
g.clearLastDownload=function(){ __lastDownload=null; };
const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // ── RECORD CLASSIFICATION ─────────────────────────────────────────────────────────────────
  'g.classifyJvmJournalRecord=classifyJvmJournalRecord;' +
  'g.normalizeJournalRecord=normalizeJournalRecord;' +
  'g.JVM_RECORD_CLASS=JVM_RECORD_CLASS;' +
  'g.renderPaperMiniJournal=renderPaperMiniJournal;' +
  'g.renderMiniJournal=renderMiniJournal;' +
  // Exposed so a fixture can simulate a display-label RENAME -- the exact edit ADR-006 says labels
  // exist to permit, and the one that silently reintroduced the mini-journal defect (§18.12).
  'g.JVM_MANIFEST=JVM_MANIFEST;' +
  'g.ALEX_MANIFEST=ALEX_MANIFEST;' +
  'g.getFilteredJournalRecords=getFilteredJournalRecords;' +
  'g.getUnifiedJournalRecords=getUnifiedJournalRecords;' +
  'g.computePaperLedgerIntegrity=computePaperLedgerIntegrity;' +
  // ── TRADE NOTES (real save-and-read path) ─────────────────────────────────────────────────
  'g.getTradeNote=getTradeNote;' +
  'g.saveTiNotes=saveTiNotes;' +               // the REAL onclick target of the Save Note button
  'g.renderTiNotes=renderTiNotes;' +
  'g.renderTradeInspectorPanel=renderTradeInspectorPanel;' +
  'g.findJournalRecordById=findJournalRecordById;' +
  'g.migrateJournalEntryIds=migrateJournalEntryIds;' +
  'g.getTradeNotes=function(){return tradeNotes;};' +
  'g.setTradeNotes=function(v){tradeNotes=v;};' +
  'g.loadSaved=loadSaved;' +
  // ── EXPORT / EVIDENCE ─────────────────────────────────────────────────────────────────────
  'g.evidenceNormalizeJvmTrade=evidenceNormalizeJvmTrade;' +
  'g.evidenceBuildPackageFromTrade=evidenceBuildPackageFromTrade;' +
  'g.EVIDENCE_JVM_STRATEGY_ID=EVIDENCE_JVM_STRATEGY_ID;' +
  'g.replayDiagCsvEscape=replayDiagCsvEscape;' +
  'g.replayDiagBuildExportPayload=replayDiagBuildExportPayload;' +
  'g.exportReplayDiagnosticsCSV=exportReplayDiagnosticsCSV;' +
  'g.exportReplayDiagnosticsJSON=exportReplayDiagnosticsJSON;' +
  'g.renderReplayDiagnostics=renderReplayDiagnostics;' +
  'g.SETUP_EVALUATOR_VERSION=SETUP_EVALUATOR_VERSION;' +
  'g.clearReplayParityDemo=function(){window.__replayParityDemoMismatch=false;};' +
  // ── state get/set ─────────────────────────────────────────────────────────────────────────
  'g.getJournalEntries=function(){return journalEntries;};g.setJournalEntries=function(v){journalEntries=v;};' +
  'g.getAlexGJournalEntries=function(){return alexGJournalEntries;};g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
  'g.getPaperAccount=function(){return paperAccount;};g.setPaperAccount=function(v){paperAccount=v;};' +
  'g.setAlexGAccount=function(v){alexGAccount=v;};' +
  'g.setPaperResetHistory=function(v){paperResetHistory=v;};' +
  'g.resetPaperVersionGuard=function(){paperAccountKnownVersion=0;localStorage.removeItem("fxhub_paper_version");};' +
  'g.resetAlexGVersionGuard=function(){alexGAccountKnownVersion=0;localStorage.removeItem("fxhub_alexg_account_version");};' +
  // ── DOM read/write helpers ────────────────────────────────────────────────────────────────
  'g.elHtml=function(id){ var e=document.getElementById(id); return e?String(e.innerHTML||""):null; };' +
  'g.elText=function(id){ var e=document.getElementById(id); return e?String(e.textContent||""):null; };' +
  'g.setElValue=function(id,v){ document.getElementById(id).value=v; };' +
  'g.getElValue=function(id){ return document.getElementById(id).value; };' +
  // ── localStorage helpers ──────────────────────────────────────────────────────────────────
  'g.getLocalStorageItem=function(k){return localStorage.getItem(k);};' +
  'g.setLocalStorageItem=function(k,v){localStorage.setItem(k,v);};' +
  'g.clearLocalStorage=function(){localStorage.__clear();};' +
  'return runExecutionReportingProvenanceFixtures(g);'
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
console.log(failCount===0?('ALL EXECUTION REPORTING PROVENANCE FIXTURES PASSED ('+executed.length+' executed, '+noteCount+' disclosed notes)'):('FAILURES: '+failCount+'/'+executed.length+' executed ('+noteCount+' disclosed notes)'));
