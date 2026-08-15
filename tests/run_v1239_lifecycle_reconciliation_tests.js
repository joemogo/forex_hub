// Self-contained runner for the v12.3.9 PAPER-POSITION LIFECYCLE / PERSISTENCE / LEDGER-ACCOUNT-
// JOURNAL RECONCILIATION fixture suite. Reads index.html directly and extracts its <script> body
// itself -- same pattern as run_v1238_execution_reporting_journal_tests.js, whose asynchronous
// design this runner reuses deliberately.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1239_lifecycle_reconciliation_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically)
//
// ── WHY THIS RUNNER IS ASYNCHRONOUS ────────────────────────────────────────────────────────
// Every fixture in this suite that matters observes state AFTER the real, PROTECTED, genuinely
// async closePaperPosition() has run to completion -- the balance move, the removal from
// openPositions, the closedPositions insert, the journal closure, the ledger commit and, when the
// commit is rejected, the rollback of all of it. All of that lives past an internal
// `await fetchBidAsk(...)`. JavaScriptCore DOES drain its microtask queue once the top-level
// script body finishes evaluating, so a continuation attached with .then() runs and its
// console.log() output is flushed before the interpreter exits. This runner therefore returns the
// suite's Promise and emits from the continuation.
//
// THE FAILURE MODE THIS AVOIDS, WHICH THIS REPOSITORY HAS ALREADY PRODUCED: a synchronous fixture
// that calls closePaperPosition() WITHOUT awaiting it observes only the state before the await,
// i.e. the position still open and the balance untouched, and then asserts "after a normal
// open->close cycle the books reconcile". That assertion passes against an account in which the
// close never happened at all, and it passes against a close path that leaves the position in
// BOTH openPositions and closedPositions. tests/v_paper_trading_audit_tests.js:312
// ("Reconciliation.1") is exactly that shape and is disclosed as such in the header of the suite
// file this runner loads. Every close below is awaited.
//
// NOTHING IS STUBBED, WRAPPED OR PATCHED IN PRODUCTION CODE. The only seams are the harness's own
// browser stubs (document/localStorage/fetch), identical to every other suite here, plus two
// additions that belong to the STUB and not to the application:
//   * a deliberate localStorage write/remove failure injector, so the atomic three-key commit's
//     rollback can be observed doing what it claims (a storage quota exception is not otherwise
//     reachable offline), and
//   * the Date CONSTRUCTOR freeze copied verbatim from the v1238 journal runner.
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
// ── the failure injector lives in the STUB, never in the application ──────────────────────────
// savePaperAccountGuarded()'s three-key commit and its compensating rollback are only exercised
// when a storage write throws. In a browser that is a quota/permission exception; offline there is
// no way to provoke one except from the storage object itself. These two sets are empty for every
// fixture that is not deliberately testing the rollback.
const lsFailSet=new Set();
const lsFailRemove=new Set();
globalThis.localStorage={
  getItem:function(k){return Object.prototype.hasOwnProperty.call(lsStore,k)?lsStore[k]:null;},
  setItem:function(k,v){ if(lsFailSet.has(k)) throw new Error('QuotaExceededError (injected by the harness stub) for key '+k); lsStore[k]=v;},
  removeItem:function(k){ if(lsFailRemove.has(k)) throw new Error('SecurityError (injected by the harness stub) removing key '+k); delete lsStore[k];},
  __keys:function(){return Object.keys(lsStore);},
  __clear:function(){Object.keys(lsStore).forEach(k=>delete lsStore[k]);},
  __failSet:lsFailSet,
  __failRemove:lsFailRemove
};
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
// Rejecting fetch is deliberate and is NOT a shortcut around the await: fetchBidAsk() catches its
// own failure and returns null, which drives closePaperPosition() down its documented pairData
// fallback -- an exit price this suite controls exactly, so every asserted balance/P&L figure is a
// fixture-chosen literal rather than something re-derived from live data.
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
  const noteCount=results.length-executed.length;
  console.log('---');
  console.log(failCount===0
    ? ('ALL LIFECYCLE/RECONCILIATION FIXTURES PASSED ('+executed.length+' executed, '+noteCount+' disclosed notes)')
    : ('FAILURES: '+failCount+'/'+executed.length+' executed ('+noteCount+' disclosed notes)'));
}

try{
  const html=readFile('./index.html');
  const appCode=extractScriptBody(html);
  const testCode=readFile('./tests/v1239_lifecycle_reconciliation_tests.js');
  const g={};
  const wrapped = new Function('g',
    appCode + '\n' + testCode + '\n' +
    // ── the REAL, unmodified, PROTECTED lifecycle entry points driven end to end ──
    'g.openPaperPosition=openPaperPosition;' +
    'g.closePaperPosition=closePaperPosition;' +
    // ── persistence / commit layer under test ──
    'g.commitPaperLedger=commitPaperLedger;' +
    'g.savePaperAccountGuarded=savePaperAccountGuarded;' +
    // ── reconciliation / integrity layer under test ──
    'g.computePaperLedgerIntegrity=computePaperLedgerIntegrity;' +
    'g.ledgerDeriveAccountState=ledgerDeriveAccountState;' +
    'g.ledgerReconcileBalance=ledgerReconcileBalance;' +
    'g.computeReconciliationPreview=computeReconciliationPreview;' +
    'g.applyPaperReconciliation=applyPaperReconciliation;' +
    // ── state get/set ──
    'g.getPaperAccount=function(){return paperAccount;};g.setPaperAccount=function(v){paperAccount=v;};' +
    'g.getJournalEntries=function(){return journalEntries;};g.setJournalEntries=function(v){journalEntries=v;};' +
    'g.setAlexGAccount=function(v){alexGAccount=v;};g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
    'g.setPaperReconciliationAudit=function(v){paperReconciliationAudit=v;};' +
    'g.getPaperReconciliationAudit=function(){return paperReconciliationAudit;};' +
    'g.setPaperResetHistory=function(v){paperResetHistory=v;};' +
    'g.setPairData=function(pair,price){ if(price===null||price===undefined){ delete pairData[pair]; } else { pairData[pair]={price:price}; } };' +
    // ── the optimistic-concurrency version guard's session state ──
    'g.getKnownVersion=function(){return paperAccountKnownVersion;};' +
    'g.setKnownVersion=function(v){paperAccountKnownVersion=v;};' +
    'g.resetPaperVersionGuard=function(){paperAccountKnownVersion=0;localStorage.removeItem("fxhub_paper_version");};' +
    'g.resetPaperPositionsClosing=function(){paperPositionsClosing.clear();};' +
    // ── INC-001 load-integrity state (the present-but-unreadable key register) ──
    'g.setStorageLoadFailures=function(v){storageLoadFailures=v||{};};' +
    // Returned as the ARRAY, and every fixture below reads its newest entry's MESSAGE. Never its
    // LENGTH: recordPaperEngineError caps the log at 50 via unshift+slice, so a length comparison
    // stops changing once the log is saturated and would pass in exactly the condition it exists to
    // catch. That false-positive control has already been found in this repository once.
    'g.getPaperEngineErrors=function(){ try{ return paperEngineErrors; }catch(e){ return []; } };' +
    'g.setPaperEngineErrors=function(v){ try{ paperEngineErrors=v; }catch(e){} };' +
    // ── storage inspection + the stub-level failure injector ──
    'g.lsGet=function(k){return localStorage.getItem(k);};' +
    'g.lsSet=function(k,v){return localStorage.setItem(k,v);};' +
    'g.lsKeys=function(){return localStorage.__keys();};' +
    'g.clearLocalStorage=function(){localStorage.__clear();};' +
    'g.failSetOn=function(keys){ localStorage.__failSet.clear(); (keys||[]).forEach(function(k){localStorage.__failSet.add(k);}); };' +
    'g.failRemoveOn=function(keys){ localStorage.__failRemove.clear(); (keys||[]).forEach(function(k){localStorage.__failRemove.add(k);}); };' +
    'g.clearStorageFailures=function(){ localStorage.__failSet.clear(); localStorage.__failRemove.clear(); };' +
    // ── clock control, copied verbatim from the v1238 journal runner: patches the Date
    //    CONSTRUCTOR, not merely Date.now, because openedAt/closedAt come from `new Date()`. ──
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
    'return runV1239LifecycleReconciliationFixtures(g);'
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
    emit(out);
  }
}catch(e){
  console.log('RUNNER ERROR: '+e);
}
// osascript prints the script's own completion value; without this the suite's pending Promise
// would be echoed as a stray "[object Promise]" line after the results.
void 0;
