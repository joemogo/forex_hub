// Self-contained runner for the v12.1.2 TRUE MTF Replay Diagnostics + Manual Review Eligible
// fixture suite. Requires no separate extraction/preprocessing step -- reads index.html
// directly and extracts its <script> body itself.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1212_tests.js
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
const testCode=readFile('./tests/v1212_manual_review_and_replay_diagnostics_tests.js');

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
  __keys:function(){return Object.keys(lsStore);}
};
globalThis.fetch=function(){return Promise.reject(new Error('no network'));};
globalThis.alert=function(){};globalThis.confirm=function(){return true;};
globalThis.Blob=function(parts,opts){return{parts,opts};};
globalThis.URL={createObjectURL:function(){return 'blob:stub';},revokeObjectURL:function(){}};
let __fakeTimerId=0;
globalThis.setTimeout=function(){return ++__fakeTimerId;};globalThis.clearTimeout=function(){};
globalThis.setInterval=function(){return ++__fakeTimerId;};globalThis.clearInterval=function(){};
globalThis.ResizeObserver=function(){return{observe:function(){},disconnect:function(){}};};
globalThis.LightweightCharts={LineStyle:{Solid:0,Dashed:1,Dotted:2},CrosshairMode:{Normal:0}};

const g={};
const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // -- shared evaluator / classifier (fully synchronous) --
  'g.evaluateSetupFullBreakdownCore=evaluateSetupFullBreakdownCore;' +
  'g.classifySetupEligibility=classifySetupEligibility;' +
  'g.SETUP_EVALUATOR_VERSION=SETUP_EVALUATOR_VERSION;' +
  'g.ALERT_THRESHOLD=ALERT_THRESHOLD;' +
  'g.NEAR_MISS_CONFLUENCE_MARGIN=NEAR_MISS_CONFLUENCE_MARGIN;' +
  // -- replay diagnostics: only the synchronous, separable pieces (simulateTrueMTFReplay
  // itself is async and not offline-testable -- see the fixture file's own header comment) --
  'g.mergeReplayDiag=mergeReplayDiag;' +
  'g.renderReplayDiagnostics=renderReplayDiagnostics;' +
  'g.buildExportPayload=function(diag){' +
  '  replayDiagLastRunInfo={diag:diag};' +
  '  return replayDiagBuildExportPayload();' +
  '};' +
  'g.getElementHtml=function(id){return document.getElementById(id).innerHTML;};' +
  // -- manual review state --
  'g.setManualReviewCandidates=function(v){manualReviewCandidates=v;};' +
  'g.getManualReviewCandidates=function(){return manualReviewCandidates;};' +
  'g.setManualReviewApproved=function(v){manualReviewApprovedDecisionTs=v;};' +
  'g.getManualReviewApproved=function(){return manualReviewApprovedDecisionTs;};' +
  'g.getManualReviewDismissed=function(){return manualReviewDismissedUntilTs;};' +
  'g.approveManualReviewTrade=approveManualReviewTrade;' + // now synchronous -- see index.html comment at its definition
  'g.passManualReviewSetup=passManualReviewSetup;' +
  'g.dismissManualReviewUntilNextCandle=dismissManualReviewUntilNextCandle;' +
  'g.computeManualReviewGroupedPerformance=computeManualReviewGroupedPerformance;' +
  'g.computeGroupTradeStats=computeGroupTradeStats;' +
  // -- trading/journal state --
  'g.setJournalEntries=function(v){journalEntries=v;};' +
  'g.getJournalEntries=function(){return journalEntries;};' +
  'g.setPaperAccount=function(v){paperAccount=v;};' +
  'g.getPaperAccount=function(){return paperAccount;};' +
  'g.openPaperPosition=openPaperPosition;' +
  'g.commitPaperLedger=commitPaperLedger;' +
  'g.rigStalePaperVersion=function(){localStorage.setItem("fxhub_paper_version",String(paperAccountKnownVersion+10));};' +
  'g.resetPaperVersionGuard=function(){paperAccountKnownVersion=0;localStorage.removeItem("fxhub_paper_version");};' +
  // -- deterministic session override (test-harness-only; does NOT touch index.html's
  // protected getSession(), only reassigns this offline realm's in-memory copy of it for
  // the duration of the fixtures that call approveManualReviewTrade(), which gates on
  // getSession().active using the REAL wall clock, not the setup's own decisionTs -- a
  // genuine, pre-existing, real-clock dependency that made these fixtures nondeterministic
  // around 00:00-08:00 UTC. Restored immediately after use so no other fixture's behavior
  // is affected. Production behavior is completely unchanged -- this never runs outside
  // this offline test process. --' +
  '(function(){' +
    'const __originalGetSession=getSession;' +
    'g.forceActiveSession=function(){getSession=function(){return{name:"London",active:true,priority:true};};};' +
    'g.restoreSession=function(){getSession=__originalGetSession;};' +
  '})();' +
  // -- localStorage helpers --
  'g.getAllLocalStorageKeys=function(){return localStorage.__keys();};' +
  'return runV1212Fixtures(g);'
);
const results = wrapped(g);
results.forEach(r=>console.log((r.pass?'PASS':'FAIL')+' -- '+r.name+(r.detail?' ('+r.detail+')':'')));
const failCount=results.filter(r=>!r.pass).length;
console.log('---');
console.log(failCount===0?'ALL v12.1.2 REPLAY DIAGNOSTICS + MANUAL REVIEW FIXTURES PASSED':('FAILURES: '+failCount+'/'+results.length));
