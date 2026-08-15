// Self-contained runner for the v12.3.8 Execution-Reporting JOURNAL WRITE PATH fixture suite.
// Reads index.html directly and extracts its <script> body itself -- same pattern as
// run_v_paper_trading_audit_tests.js / run_v1212_tests.js.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1238_execution_reporting_journal_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically)
//
// ── WHY THIS RUNNER IS ASYNCHRONOUS (and every other one in this repo is not) ──────────────
// closePaperPosition() is genuinely `async`, with one internal `await fetchBidAsk(...)` gating
// EVERY behaviour this suite exists to observe (the exit-price/P&L/result values that reach the
// journal, the journalNoteCloseJVM() call itself, and the SYSTEM_CLOSE close-reason label).
// Earlier suites disclosed that logic as unobservable offline because they tried to read it
// SYNCHRONOUSLY, within the same top-level turn -- and within one turn it genuinely is
// unreachable. What is empirically true of `osascript -l JavaScript` is narrower than that: the
// JavaScriptCore microtask queue IS drained once the top-level script body finishes evaluating,
// so a continuation attached with .then() DOES run, and its console.log() output IS flushed,
// before the interpreter exits. This runner therefore returns a Promise from the suite and
// prints its fixture lines from the continuation. That makes the real, unmodified, PROTECTED
// closePaperPosition() observable end-to-end offline for the first time -- no production
// function is modified, stubbed, or bypassed to achieve it.
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
  __clear:function(){Object.keys(lsStore).forEach(k=>delete lsStore[k]);}
};
// Rejecting fetch is deliberate and is NOT a shortcut around the await: fetchBidAsk() catches its
// own failure and returns null, which drives closePaperPosition() down its documented pairData
// fallback -- an exit price this suite controls exactly, so every asserted P&L/R/exit value is a
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
    ? ('ALL EXECUTION-REPORTING JOURNAL FIXTURES PASSED ('+executed.length+' executed, '+noteCount+' disclosed notes)')
    : ('FAILURES: '+failCount+'/'+executed.length+' executed ('+noteCount+' disclosed notes)'));
}

try{
  const html=readFile('./index.html');
  const appCode=extractScriptBody(html);
  const testCode=readFile('./tests/v1238_execution_reporting_journal_tests.js');
  const g={};
  const wrapped = new Function('g',
    appCode + '\n' + testCode + '\n' +
    // ── the REAL, unmodified, PROTECTED execution entry points this suite drives end-to-end ──
    'g.openPaperPosition=openPaperPosition;' +
    'g.closePaperPosition=closePaperPosition;' +
    'g.alexGCloseLivePosition=alexGCloseLivePosition;' +
    // ── the journal write path under test ──
    'g.applyJournalCloseUpdate=applyJournalCloseUpdate;' +
    'g.journalNoteOpenJVM=journalNoteOpenJVM;' +
    'g.journalNoteOpenAlex=journalNoteOpenAlex;' +
    'g.normalizeJournalRecord=normalizeJournalRecord;' +
    'g.getUnifiedJournalRecords=getUnifiedJournalRecords;' +
    'g.JOURNAL_NOT_RECORDED=JOURNAL_NOT_RECORDED;' +
    // ── state get/set ──
    'g.getJournalEntries=function(){return journalEntries;};g.setJournalEntries=function(v){journalEntries=v;};' +
  // §18.12: clock control, so the close-time assertions can pin EXACT values instead of
  // "is a number and >= 0" -- a shape that passed against a mutation journalling durationMs
  // as 1 for every trade, and against one journalling the open time as the close time.
  // Patches the Date CONSTRUCTOR, not just Date.now. The close path timestamps with
  // `new Date().toISOString()` and derives durationMs from closedAt minus openedAt, so freezing
  // only Date.now left both timestamps on the wall clock and the duration at ~0 -- which is why
  // the assertion could only ever be "is a number and >= 0".
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
    'g.getPaperAccount=function(){return paperAccount;};g.setPaperAccount=function(v){paperAccount=v;};' +
    'g.getAlexGAccount=function(){return alexGAccount;};g.setAlexGAccount=function(v){alexGAccount=v;};' +
    'g.getAlexGJournalEntries=function(){return alexGJournalEntries;};g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
    'g.setPairData=function(pair,price){ if(price===null||price===undefined){ delete pairData[pair]; } else { pairData[pair]={price:price}; } };' +
    'g.setCfg=function(v){cfg=v;};' +
    'g.elHtml=function(id){ var e=document.getElementById(id); return e?String(e.innerHTML||""):null; };' +
    // ── version guards / duplicate-close guard: reset so a commit is never rejected for an
    //    unrelated stale-tab reason while a journal fixture is being observed ──
    'g.resetPaperVersionGuard=function(){paperAccountKnownVersion=0;localStorage.removeItem("fxhub_paper_version");};' +
    'g.resetAlexGVersionGuard=function(){alexGAccountKnownVersion=0;localStorage.removeItem("fxhub_alexg_account_version");};' +
    'g.resetPaperPositionsClosing=function(){paperPositionsClosing.clear();};' +
    'g.clearLocalStorage=function(){localStorage.__clear();};' +
    'return runV1238ExecutionReportingJournalFixtures(g);'
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
