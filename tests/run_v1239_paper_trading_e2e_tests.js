// Self-contained runner for the v12.3.9 ALEX/JVM PAPER-TRADING END-TO-END fixture suite.
// Reads index.html directly and extracts its <script> body itself -- same pattern as
// run_v_paper_trading_audit_tests.js and run_v1238_execution_reporting_journal_tests.js.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1239_paper_trading_e2e_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically)
//
// ── WHY THIS RUNNER IS ASYNCHRONOUS ────────────────────────────────────────────────────────
// Both entry points this suite exists to observe are genuinely `async`: checkAutoTrades()
// (which awaits Promise.all over the eligible pairs) and closePaperPosition() (one internal
// `await fetchBidAsk`). Following run_v1238_execution_reporting_journal_tests.js, the suite
// returns a Promise and prints its fixture lines from the .then() continuation --
// JavaScriptCore drains its microtask queue after the top-level script body finishes, so the
// continuation runs and its console.log output is flushed before the interpreter exits. Every
// production function is driven REAL and UNMODIFIED; nothing is stubbed, wrapped or patched.
// The one seam is globalThis.fetch, which is the process boundary, not app code.
//
// ISOLATION FROM REAL DATA: in-memory localStorage stub, stubbed fetch, no browser, no network,
// no disk write. This process cannot reach real paper-trading storage, so no real paper trade
// can be created or persisted by it.
ObjC.import('Foundation');
function readFile(path){
  const s=$.NSString.stringWithContentsOfFileEncodingError(path,$.NSUTF8StringEncoding,null);
  const v=ObjC.unwrap(s); return v==null?'':v;
}
function extractScriptBody(html){
  const m=html.match(/<script>([\s\S]*)<\/script>/);
  if(!m) throw new Error('Could not find <script>...</script> body in index.html -- run this from the project root.');
  return m[1];
}

const elMap={};
function makeClassList(){
  const c=new Set();
  return{add:x=>c.add(x),remove:x=>c.delete(x),contains:x=>c.has(x),
    toggle:(x,f)=>{ if(f===undefined){ c.has(x)?c.delete(x):c.add(x); } else if(f) c.add(x); else c.delete(x); }};
}
function makeStub(){
  return {innerHTML:'',textContent:'',value:'',className:'',style:{},options:[{value:'All'}],
    width:100,height:100,disabled:false,checked:false,classList:makeClassList(),
    getContext:()=>({clearRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillRect(){},save(){},restore(){},setLineDash(){},arc(){},fill(){},closePath(){},fillText(){},measureText:()=>({width:0})}),
    appendChild(){},addEventListener(){},focus(){},setSelectionRange(){},click(){},files:[],
    getBoundingClientRect:()=>({top:0,left:0,width:0,height:0})};
}
const lsStore={};
globalThis.document={
  getElementById:id=>{ if(!elMap[id]) elMap[id]=makeStub(); return elMap[id]; },
  querySelector:()=>null,querySelectorAll:()=>[],createElement:()=>makeStub(),
  addEventListener(){},visibilityState:'visible',
  body:{appendChild(){},removeChild(){}},activeElement:null
};
globalThis.window={devicePixelRatio:1};
globalThis.localStorage={
  getItem:k=>Object.prototype.hasOwnProperty.call(lsStore,k)?lsStore[k]:null,
  setItem:(k,v)=>{lsStore[k]=String(v);},removeItem:k=>{delete lsStore[k];},
  __keys:()=>Object.keys(lsStore),
  __clear:()=>{Object.keys(lsStore).forEach(k=>delete lsStore[k]);}
};
globalThis.alert=()=>{};globalThis.confirm=()=>true;
globalThis.Blob=function(p,o){return{parts:p,opts:o};};
globalThis.URL={createObjectURL:()=>'blob:stub',revokeObjectURL(){}};
let __t=0;
globalThis.setTimeout=()=>++__t;globalThis.clearTimeout=()=>{};
globalThis.setInterval=()=>++__t;globalThis.clearInterval=()=>{};
globalThis.ResizeObserver=function(){return{observe(){},disconnect(){}};};
globalThis.LightweightCharts={LineStyle:{Solid:0,Dashed:1,Dotted:2},CrosshairMode:{Normal:0}};
globalThis.Notification=undefined;
globalThis.indexedDB=undefined;

// ── FROZEN CLOCK ───────────────────────────────────────────────────────────────────────────
// Monday 2026-08-10, 14:00 UTC. Inside the strategy's own Mon-Wed preferred entry window and
// inside an active (priority) London session -- both are the frozen strategy's gates, not
// fixture conveniences. The Date CONSTRUCTOR is frozen, not only Date.now, so openedAt/closedAt
// are exact fixture-chosen literals rather than wall-clock values (see §18.12 in the v12.3.8
// journal suite for why freezing only Date.now is not enough).
let __simNow=Date.UTC(2026,7,10,14,0,0);
const __RealDate=Date;
globalThis.Date=class extends __RealDate{
  constructor(...a){ if(a.length===0) super(__simNow); else super(...a); }
  static now(){ return __simNow; }
};

function makeResponse(ok,status,body){
  return{ok,status,json:()=>Promise.resolve(body),text:()=>Promise.resolve('')};
}
function mk(t,o,h,l,c){
  return{time:new __RealDate(t).toISOString(),complete:true,
    mid:{o:o.toFixed(5),h:h.toFixed(5),l:l.toFixed(5),c:c.toFixed(5)}};
}
// NEGATIVE-CONTROL series: flat and structureless, so "no trade" is the strategy's own verdict.
function flatM15(n){
  const out=[];
  for(let i=n;i>=1;i--){ const b=1.1000; out.push(mk(__simNow-i*900000,b,b+0.0002,b-0.0002,b)); }
  return out;
}
// POSITIVE-CONTROL series. Byte-for-byte the same construction the v12.3.3 JVM auto-trade
// suite uses, and for the same stated reason: THE CANDLES ARE CONSTRUCTED, THE VERDICT IS NOT.
// No threshold, weight or rule is altered -- the frozen scorer rates this ordinary bullish
// engulfing/market-structure-break setup 65 against its own threshold of 55 and returns its own
// R:R. Reproduced here rather than imported because a runner may not depend on another runner.
function firingM15(n){
  const out=[]; n=n||60;
  for(let i=n;i>=4;i--){
    const base=1.1000+(n-i)*0.00002;
    out.push(mk(__simNow-i*900000,base,base+0.00015,base-0.00015,base+0.00005));
  }
  const t=__simNow;
  out.push(mk(t-3*900000,1.10050,1.10100,1.10000,1.10020));
  out.push(mk(t-2*900000,1.10180,1.10200,1.10120,1.10140));
  out.push(mk(t-1*900000,1.10100,1.10320,1.10080,1.10300));
  return out;
}
function structuralCandles(n){
  const out=[];
  for(let i=n;i>=1;i--){
    const phase=i%6; let lo,hi;
    if(phase===0){lo=1.09900;hi=1.11000;}
    else if(phase===1){lo=1.09905;hi=1.11500;}
    else if(phase===2){lo=1.09895;hi=1.12000;}
    else if(phase===3){lo=1.10500;hi=1.11980;}
    else if(phase===4){lo=1.10400;hi=1.12010;}
    else {lo=1.10200;hi=1.11200;}
    out.push(mk(__simNow-i*86400000,lo+0.0005,hi,lo,hi-0.0005));
  }
  return out;
}

// ── FETCH SEAM ─────────────────────────────────────────────────────────────────────────────
// /pricing can be made to REJECT. That is deliberate and is NOT a shortcut around the await:
// fetchBidAsk() catches its own failure and returns null, which drives closePaperPosition()
// down its documented pairData fallback -- an exit price the fixture controls exactly, so every
// asserted P&L/R/balance figure is a fixture-chosen literal computed by hand, never re-derived
// from live data. When a fixture needs a real bid/ask (the ALEX open path requires one), the
// mode is switched to 'serve' and the exact bid/ask is set by the fixture.
let __pricingMode='reject', __pbid='1.10000', __pask='1.10000';
// Counts every attempt to reach the pricing endpoint. This is how a fixture can tell whether
// closePaperPosition() actually ENTERED its body a second time (the in-flight guard rejects a
// duplicate BEFORE the fetch) rather than merely finding the position already gone afterwards.
let __pricingCalls=0;
let __mode='flat';
// Per-instrument counter of M15 evaluation fetches. This is an observation of the process
// boundary -- how many times the engine actually went out to evaluate each pair on one tick --
// not a wrapper around any app function.
let __m15Calls={};
// §18.22: a hook that fires DURING an in-flight fetch, so a fixture can make a position appear
// between the eligibility filter and the pre-open re-check -- the concurrent manual click /
// overlapping tick the inner guard exists for. Without an interleaving point that guard can
// only ever be exercised by the outer filter, which is why it was uncovered.
let __midFetch=null;
globalThis.fetch=function(url){
  const u=String(url);
  if(/\/pricing/.test(u)){
    __pricingCalls++;
    if(__pricingMode==='reject') return Promise.reject(new Error('no network'));
    return Promise.resolve(makeResponse(true,200,{prices:[{bids:[{price:__pbid}],asks:[{price:__pask}]}]}));
  }
  const inst=(u.match(/instruments\/([^/]+)\//)||[])[1];
  const gran=(u.match(/granularity=(\w+)/)||[])[1];
  const wantN=parseInt((u.match(/count=(\d+)/)||[])[1],10)||60;
  if(gran==='M15'&&wantN===60){ __m15Calls[inst]=(__m15Calls[inst]||0)+1; }
  if(__mode==='firing'){
    if(gran==='D') return Promise.resolve(makeResponse(true,200,{candles:structuralCandles(120)}));
    if(gran==='W') return Promise.resolve(makeResponse(true,200,{candles:structuralCandles(60)}));
    // NOT self-consuming: instruments are fetched via Promise.all in an order the fixture does not
    // control, so nulling the hook on the FIRST fetch fired it against whichever pair happened to
    // go first -- never the one under test. The callback decides when it is done.
    if(__midFetch){ try{ __midFetch(inst); }catch(e){} }
    return Promise.resolve(makeResponse(true,200,{candles:firingM15(wantN)}));
  }
  return Promise.resolve(makeResponse(true,200,{candles:flatM15(60)}));
};

const g={};
g.setMode=m=>{__mode=m;};
g.setPricing=(mode,bid,ask)=>{__pricingMode=mode; if(bid!=null)__pbid=String(bid); if(ask!=null)__pask=String(ask);};
g.onMidFetch=fn=>{__midFetch=fn;};
g.resetM15Calls=()=>{__m15Calls={};};
g.resetPricingCalls=()=>{__pricingCalls=0;};
g.pricingCalls=()=>__pricingCalls;
g.m15Calls=inst=>(__m15Calls[inst]||0);
g.m15CallTotal=()=>Object.keys(__m15Calls).reduce((a,k)=>a+__m15Calls[k],0);
g.m15CallPairs=()=>Object.keys(__m15Calls).slice().sort();
g.setNow=t=>{__simNow=t;};
g.now=()=>__simNow;

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
    ? ('ALL PAPER-TRADING E2E FIXTURES PASSED ('+executed.length+' executed, '+noteCount+' disclosed notes)')
    : ('FAILURES: '+failCount+'/'+executed.length+' executed ('+noteCount+' disclosed notes)'));
}

try{
  const appCode=extractScriptBody(readFile('./index.html'));
  const testCode=readFile('./tests/v1239_paper_trading_e2e_tests.js');
  const wrapped = new Function('g',
    appCode + '\n' + testCode + '\n' +
    // ── the REAL, unmodified execution entry points this suite drives end-to-end ──
    'g.openPaperPosition=openPaperPosition;' +
    'g.closePaperPosition=closePaperPosition;' +
    // §18.30: the defence-in-depth finiteness refusal in commitPaperLedger.
    'g.commitPaperLedger=commitPaperLedger;' +
    // §18.30: the UNREALIZED P&L shown on every open position had zero gate coverage -- even a
    // constant payload at the computation survived the whole gate. This is the second, unwatched
    // copy of the pip/P&L arithmetic; the realized close path is pinned by JVMEXIT-11.
    'g.renderPaper=renderPaper;' +
    // §18.32: the ALEX twin of the open-positions table. Independent verification replaced its
    // whole entry/stop/target cell block with a literal and the full gate stayed green -- it had no
    // fixture of any kind, while its JVM mirror had just been covered by PTE2E-UNREAL.1-6.
    'g.renderAlexGLiveOpenTable=renderAlexGLiveOpenTable;' +
    'g.setHideTestTradesAlex=function(v){hideTestTradesAlex=!!v;};' +
    'g.elHtml=function(id){ var e=document.getElementById(id); return e?String(e.innerHTML||""):""; };' +
    'g.forceBalance=function(v){ paperAccount.balance=v; };' +
    'g.getPaperBlockingError=function(){ return paperLedgerBlockingError; };' +
    'g.getPaperEngineErrorMessages=function(){ return paperEngineErrors.slice(0,3).map(function(e){return String(e&&e.message||e);}); };' +
    'g.checkAutoTrades=checkAutoTrades;' +
    // §18.23: the alerting path had ZERO behavioural coverage anywhere in the repository.
    'g.scanPair=scanPair;' +
    'g.getAlertLog=function(){return alertLog;};g.setAlertLog=function(v){alertLog=v;};' +
    'g.ALERT_THRESHOLD=ALERT_THRESHOLD;' +
    'g.resetFiredAlerts=function(){firedAlerts=new Set();};' +
    'g.pairDataAll=function(){return pairData;};' +
    'g.evaluateLiveTrigger=evaluateLiveTrigger;' +
    'g.alexGAttemptOpenLivePosition=alexGAttemptOpenLivePosition;' +
    'g.alexGCloseLivePosition=alexGCloseLivePosition;' +
    'g.alexGLiveSignalId=alexGLiveSignalId;' +
    'g.loadSaved=loadSaved;' +
    'g.getSession=getSession;' +
    'g.isPreferredTradingDay=isPreferredTradingDay;' +
    'g.pipSize=pipSize;g.pipValuePerLot=pipValuePerLot;' +
    // ── frozen config / universe, read-only ──
    'g.SCAN_PAIRS=SCAN_PAIRS;' +
    'g.alexCfg=function(){return RULES_ALEXG.config;};' +
    'g.setAlexSuspension=function(v){var w=RULES_ALEXG_V11.v11Config.setupSuspensionEnabled;RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=v;return w;};' +
    // ── JVM state get/set ──
    'g.getPaperAccount=function(){return paperAccount;};g.setPaperAccount=function(v){paperAccount=v;};' +
    'g.getJournalEntries=function(){return journalEntries;};g.setJournalEntries=function(v){journalEntries=v;};' +
    'g.getAutoTrading=function(){return autoTrading;};g.setAutoTrading=function(v){autoTrading=v;};' +
    'g.setScanData=function(v){scanData=v;};g.getScanData=function(){return scanData;};' +
    'g.getPairData=function(){return pairData;};g.setPairDataObj=function(v){pairData=v;};' +
    'g.setPairData=function(pair,price){ if(price===null||price===undefined){ delete pairData[pair]; } else { pairData[pair]={price:price}; } };' +
    'g.getPaperEngineErrors=function(){return paperEngineErrors;};g.setPaperEngineErrors=function(v){paperEngineErrors=v;};' +
    'g.setCfg=function(v){cfg=v;};' +
    'g.resetPaperVersionGuard=function(){paperAccountKnownVersion=0;localStorage.removeItem("fxhub_paper_version");};' +
    'g.resetPaperPositionsClosing=function(){paperPositionsClosing.clear();};' +
    'g.setPaperResetHistory=function(v){paperResetHistory=v;};' +
    'g.setPaperReconciliationAudit=function(v){paperReconciliationAudit=v;};' +
    // ── ALEX state get/set ──
    'g.getAlexGAccount=function(){return alexGAccount;};g.setAlexGAccount=function(v){alexGAccount=v;};' +
    'g.getAlexGJournalEntries=function(){return alexGJournalEntries;};g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
    'g.getAlexGAutoTrading=function(){return alexGAutoTrading;};g.setAlexGAutoTrading=function(v){alexGAutoTrading=v;};' +
    'g.setAlexGSetupState=function(v){alexGSetupState=v;};' +
    'g.setAlexGLiveSetupStatuses=function(v){alexGLiveSetupStatuses=v;};' +
    'g.setAlexGEngineErrors=function(v){alexGEngineErrors=v;};' +
    'g.resetAlexGVersionGuard=function(){alexGAccountKnownVersion=0;localStorage.removeItem("fxhub_alexg_account_version");};' +
    'g.alexGResetLiveDecisionState=alexGResetLiveDecisionState;' +
    // ── FULL-STORE SNAPSHOTS for the isolation fixtures. Everything each strategy owns, in
    //    one deterministic string, so "byte-identical" is a real claim and not a spot check. ──
    // §18.29: the enumerable, EXACT set of harness-artifact messages. Defined once, in scope for
    // both snapshots. See the exclusion rationale above.
    'var __isoArtifactCtxs=null,__isoArtifactKinds=null;' +
    'var __isoArtifactMsgs=(function(){' +
    '  var ctxs=["auto-export","backfill","buffer-limits","capture","capture-jvm","capture-jvm-seam",' +
    '    "capture-jvm-trade","capture-replay","capture-replay-seam","capture-replay-trade","capture-seam",' +
    '    "capture-trade","diagnostics-refresh","eviction-persist","excursion-timing","export","export-mark",' +
    '    "export-verify-mark","import","import-batch","indexeddb-open","init","market-context",' +
    '    "observation-batch","observation-record","observation-retention","observation-write",' +
    '    "pipeline-closed-seam","pipeline-stage","preflight","preflight-list","replay-run-identity",' +
    '    "save","saveAlexGAccountGuarded","saveAlexGRest"];' +
    '  var kinds=["OTHER","UNKNOWN","QUOTA_EXCEEDED","SECURITY","CONSTRAINT","INVALID_STATE","ABORTED"];' +
    '  var tail="IndexedDB is not available in this context";' +
    '  var out=new Set([tail]);' +
    '  ctxs.forEach(function(c){ kinds.forEach(function(k){' +
    '    out.add("Evidence platform ["+c+"] "+k+": "+tail);' +
    '  }); });' +
    '  __isoArtifactCtxs=ctxs; __isoArtifactKinds=kinds;' +
    '  return out;' +
    '})();' +
    // §18.30: message-only membership was still forgeable. evidenceRecordWriteFailure stores
    // detail:extra||null from a fully caller-controlled argument, and recordAlexGEngineError merges
    // an arbitrary meta object -- so a leak sends the EXACT allowlisted message and rides its payload
    // in a field the filter never looked at. An entry is excluded only if its ENTIRE content, minus
    // the timestamp, is one of the known artifact shapes.
    // §18.32: the exclusion was defeated an EIGHTH time -- by the commit that fixed the seventh.
    // __isoNormEntry drops the `at` key UNCONDITIONALLY, and `at` was caller-writable, so a leak
    // simply put its payload there: live JVM balance and open-position counts rode into the ALEX
    // error log on every JVM save, and both ISO fixtures saw nothing. The positive control -- the
    // identical payload under a key named `leak` -- killed ISO.2 and ISO.6, so the site was
    // reachable and observed; only the `at` strip hid it.
    //
    // A second, more general vector: JSON.stringify honours a `toJSON` own-property, so a caller
    // could forge the ENTIRE normalised shape and the message need not be allowlisted at all.
    //
    // Both are closed by checking the entry's SHAPE as well as its content: no `toJSON`, and an
    // `at` that is a real ISO timestamp rather than a payload. Production is hardened too --
    // recordAlexGEngineError now writes `at` and `message` AFTER the meta merge and refuses
    // `toJSON` -- but the harness must not depend on that, because the whole point of this filter
    // is to be robust to code that can call anything.
    'var __isoEntryShapeOk=function(e){' +
    '  if(e===null||typeof e!=="object") return true;' +
    '  if(Object.prototype.hasOwnProperty.call(e,"toJSON")) return false;' +
    '  if(!Object.prototype.hasOwnProperty.call(e,"at")) return true;' +
    '  return typeof e.at==="string"&&/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{3}Z$/.test(e.at);' +
    '};' +
    'var __isoNormEntry=function(e){' +
    '  if(e===null||typeof e!=="object") return JSON.stringify({message:String(e)});' +
    '  var o={},ks=Object.keys(e).filter(function(k){return k!=="at";}).sort();' +
    '  ks.forEach(function(k){o[k]=e[k];});' +
    '  return JSON.stringify(o);' +
    '};' +
    'var __isoArtifactEntries=(function(){' +
    '  var out=new Set();' +
    '  __isoArtifactMsgs.forEach(function(m){' +
    '    out.add(__isoNormEntry({message:m,__evidencePlatform:true}));' +
    '    out.add(__isoNormEntry({message:m}));' +
    '  });' +
    '  return out;' +
    '})();' +
    'var __isoArtifactRecords=(function(){' +
    '  var out=new Set(), tail="IndexedDB is not available in this context";' +
    '  var ctxs=__isoArtifactCtxs, kinds=__isoArtifactKinds;' +
    '  ctxs.forEach(function(c){ kinds.forEach(function(k){' +
    '    out.add(__isoNormEntry({context:c,detail:null,kind:k,message:tail}));' +
    '  }); });' +
    '  return out;' +
    '})();' +
    'g.__isoArtifactMsgCount=__isoArtifactMsgs.size;' +
    'g.snapshotAlexStores=function(){ return JSON.stringify({' +
    '  account:alexGAccount, journal:alexGJournalEntries, autoTrading:alexGAutoTrading,' +
    '  setups:alexGSetupState, statuses:alexGLiveSetupStatuses, zones:alexGZoneState,' +
    // alexGEngineErrors is included, but with entries from the STRATEGY-AGNOSTIC evidence
    //   platform filtered out. evidenceRecordWriteFailure() deliberately reuses
    //   recordAlexGEngineError() as its reporting channel ("Reuse the existing, already-surfaced
    //   engine-error channel rather than inventing a new one"), so an evidence-storage failure
    //   raised during a JVM-only operation lands in the ALEX error list. Those entries carry no
    //   trade, position, balance, journal or decision data -- they are platform telemetry filed
    //   under a shared channel, not ALEX trading state -- so they are excluded here BY PREFIX and
    //   nothing else is. Every genuinely ALEX-originated engine error is still compared.
    // §18.20: the exclusion is now by PROVENANCE, not by message text. The old filter dropped any
    // entry whose message merely STARTED WITH "Evidence platform [" -- a prefix match on content a
    // leak can choose for itself. Independent verification proved it: writing JVM P&L into the ALEX
    // error log under that prefix survived both suites AND the full 2,180-fixture gate, while the
    // identical leak under any other prefix died. The evidence platform now tags its own entries,
    // so the exclusion cannot be spoofed by writing the right words.
    // §18.28: the exclusion is now an EXACT-ARTIFACT allowlist, and it carries no payload.
    //
    // The cross-reference this replaces was defeated by ONE call to a real production function:
    // evidenceRecordWriteFailure writes BOTH structures itself, from fully caller-controlled
    // `context` and `err.message`, so "must corrupt two independent structures consistently" cost a
    // leak exactly nothing. It was no stronger than the message-prefix version it replaced -- and it
    // also set __evidencePlatform automatically, defeating that filter in the same call.
    //
    // The real insight is that these entries are a HARNESS ARTIFACT, not platform activity:
    // globalThis.indexedDB is undefined in the offline runner, so the evidence platform records
    // "IndexedDB is not available in this context" during capture.
    //
    // §18.29: version six of this exclusion CLAIMED exact-string matching in this very comment and
    // implemented `indexOf(...)===-1` -- SUBSTRING CONTAINMENT. Independent verification defeated it
    // with a 44-character prefix: a leak whose message began with the artifact phrase and then
    // appended JVM balance and open-position count survived both ISO.2 and ISO.6, and the same
    // single edit also defeated the brand-new evidenceWriteFailures comparison. That made it
    // strictly WEAKER than the version it replaced -- it cost a leak nothing but choosing its
    // opening words, which is the original §18.20 message-prefix defect restored.
    //
    // Now genuinely exact. The artifact message is built at exactly one site as
    //   'Evidence platform ['+context+'] '+kind+': '+message
    // where `context` comes from a FINITE set of literal call-site strings and `kind` is 'OTHER'
    // for a plain Error. So the complete set of artifact messages is enumerable, and membership is
    // tested with Set.has -- true equality, not containment. A leak cannot append a payload,
    // because any appended byte produces a string that is not in the set.
    //
    // This is FAIL-CLOSED under drift: if production adds a new evidenceRecordWriteFailure context
    // that is not listed below, its artifact is simply COMPARED rather than excluded, and the ISO
    // fixtures fail loudly. A missing entry costs a false failure, never a false pass.
    '  engineErrors:alexGEngineErrors.filter(function(e){' +
    '    return !(__isoArtifactEntries.has(__isoNormEntry(e))&&__isoEntryShapeOk(e));' +
    '  }),' +
    // §18.28 (Sev-1 aggravator): evidenceWriteFailures was compared by NEITHER snapshot and reset by
    // nothing, so a forged record left no residue at all. Compared here, artifact rows excluded on
    // the same exact-string rule.
    '  evidenceWriteFailures:(typeof evidenceWriteFailures!=="undefined"?evidenceWriteFailures.filter(function(w){' +
    '    return !(__isoArtifactRecords.has(__isoNormEntry(w))&&__isoEntryShapeOk(w));' +
    '  }):null),' +
    '  knownVersion:alexGAccountKnownVersion,' +
    '  blockingError:alexGLedgerBlockingError, integrityWarning:alexGLedgerIntegrityWarning,' +
    '  lastEvaluatedCloseTime:alexGLastEvaluatedCloseTime,' +
    // decidedCount recorded only .size -- rewriting every key while preserving the count was
    // invisible. The CONTENTS are compared now.
    // A Map yields [key,value] pairs -- stringified per entry then sorted, so CONTENTS are
    // compared and a size-preserving rewrite is still caught.
    '  decidedSetups:Array.from(alexGDecidedSetups).map(function(e){return JSON.stringify(e);}).sort(),' +
    '  decidedEconomic:(typeof alexGDecidedEconomic!=="undefined"?Array.from(alexGDecidedEconomic).sort():null),' +
    '  signalInFlight:(typeof alexGSignalInFlight!=="undefined"?Array.from(alexGSignalInFlight).sort():null),' +
    // §18.25: the symmetric JVM->ALEX channels, including the two that silence ALEX's own
    // integrity reporting.
    // §18.27: these two are Sets, and JSON.stringify(new Set([...])) is "{}" for EVERY possible
    // content -- so comparing them RAW compared them against a constant. The commit that added them
    // named these two specifically as "the two flags that SILENCE ALEX'S OWN INTEGRITY REPORTING";
    // adding to them, and replacing them wholesale, both survived the entire gate. The hole was the
    // TYPE, not the reset. Serialised as sorted arrays, like every other Set in these snapshots.
    '  identityDriftReported:(typeof alexGIdentityDriftReported!=="undefined"&&alexGIdentityDriftReported?Array.from(alexGIdentityDriftReported).sort():null),' +
    '  cursorSanityReported:(typeof alexGCursorSanityReported!=="undefined"&&alexGCursorSanityReported?Array.from(alexGCursorSanityReported).sort():null),' +
    // §18.27 F-4: the SIXTEENTH channel, and it moves money. getStructuralAOI returns
    // structuralAOIInflight[oPair] BEFORE any fetch and BEFORE the ADR-011 completeness gate, so
    // seeding it with a resolved promise puts a FABRICATED stop and target on a real JVM trade.
    // Its own cache was added; the in-flight lock for that cache was missed -- the exact sibling of
    // paperPositionsClosing, which a prior round added for the close path.
    '  replayState:(typeof alexGReplayState!=="undefined"?alexGReplayState:null),' +
    '  hideTestTradesAlex:(typeof hideTestTradesAlex!=="undefined"?hideTestTradesAlex:null),' +
    '  pipelineObservationBuffer:(typeof alexGPipelineObservationBuffer!=="undefined"?alexGPipelineObservationBuffer:null),' +
    '  liveIntervalArmed:(typeof alexGLiveInterval!=="undefined"?(alexGLiveInterval!=null):null),' +
    // §18.28: alexV2 is a THIRD strategy with its own execution path, so it belongs in BOTH
    // snapshots -- a JVM operation must not touch it, and neither must an ALEX one. An earlier
    // draft put it only in the JVM snapshot, which observes ALEX->alexV2 and is blind to
    // JVM->alexV2. "Which snapshot" is decided by the direction being tested, not by the owner.
    '  alexV2AccountAlexSide:(typeof alexV2Account!=="undefined"?alexV2Account:null),' +
    '  alexV2JournalAlexSide:(typeof alexV2JournalEntries!=="undefined"?alexV2JournalEntries:null),' +
    '  replayTrades:(typeof alexGReplayTrades!=="undefined"?alexGReplayTrades:null),' +
    '  replayRejected:(typeof alexGReplayRejected!=="undefined"?alexGReplayRejected:null),' +
    '  replayStats:(typeof alexGReplayStats!=="undefined"?alexGReplayStats:null),' +
    // §18.25: the evidence-platform counters are NOT ALEX-owned state -- the platform is
    // strategy-agnostic and legitimately records a JVM operation, so comparing them here reports a
    // normal JVM write as an ALEX leak. Removed for the same reason the engine-error entries are
    // cross-referenced rather than compared raw: shared platform telemetry is not strategy state.
        '  zoneState:(typeof alexGZoneState!=="undefined"?alexGZoneState:null),' +
    // EVERY fxhub_alex* key, not just fxhub_alexg -- a leak into fxhub_alexv2_account sat outside
    // BOTH snapshots because one matched a narrower prefix than the family it was guarding.
    '  storage:localStorage.__keys().filter(function(k){return k.indexOf("fxhub_alex")===0;}).sort()' +
    '           .map(function(k){return k+"="+localStorage.getItem(k);})' +
    '}); };' +
    // §18.20: this was a SIX-KEY ALLOWLIST while the fixture text claimed "every JVM localStorage
    // key". save() also persists fxhub_scan, fxhub_checklist, fxhub_alerts, fxhub_env,
    // fxhub_autoscan and fxhub_trade_notes -- none was compared, so an ALEX commit could overwrite
    // any of them invisibly. It is now a DENYLIST: every key that is not ALEX-owned is JVM-side
    // state, so a new key added anywhere is covered by default instead of needing to be remembered.
    //
    // The module-scope additions are the ones that MOVE MONEY. pairData is the shared price cache
    // closePaperPosition fills its exit from when live bid/ask is unavailable, and that
    // checkPaperPositions reads to decide TAKE_PROFIT/STOP_LOSS -- poisoning it from the ALEX side
    // moves JVM money. paperPositionsClosing is the in-flight close lock: seeding it with open JVM
    // ids means those trades can never close again. storageLoadFailures is the INC-001 register
    // whose clearing disarms the guard that stops a default overwriting real stored data. All three
    // were outside both snapshots; all three were proven invisible against the full gate.
    'g.snapshotJvmStores=function(){ return JSON.stringify({' +
    '  account:paperAccount, journal:journalEntries, autoTrading:autoTrading,' +
    '  engineErrors:paperEngineErrors, resetHistory:paperResetHistory,' +
    '  reconciliationAudit:paperReconciliationAudit, knownVersion:paperAccountKnownVersion,' +
    '  blockingError:paperLedgerBlockingError, integrityWarning:paperLedgerIntegrityWarning,' +
    '  pairData:(typeof pairData!=="undefined"?pairData:null),' +
    '  scanData:(typeof scanData!=="undefined"?scanData:null),' +
    '  autoScan:(typeof autoScan!=="undefined"?autoScan:null),' +
    '  checklistState:(typeof checklistState!=="undefined"?checklistState:null),' +
    '  alertLog:(typeof alertLog!=="undefined"?alertLog:null),' +
    '  tradeNotes:(typeof tradeNotes!=="undefined"?tradeNotes:null),' +
    // §18.25: the MODULE-STATE axis was still a hand-written allowlist with the same failure mode
    // the storage allowlist had. An independent sweep injected 13+ cross-strategy channels that all
    // survived 2,207/2,207. The two that MOVE MONEY are first:
    //   paperTradeIdSeq  -- the JVM trade-ID space. Poisoned to MAX_SAFE_INTEGER, seq+1===seq
    //                       forever, so EVERY subsequent JVM id is identical: positions sharing one
    //                       id and the close lookup resolving to the wrong position. The
    //                       paperSeedTradeIdSeq guard screens PERSISTED values only, not this.
    //   structuralAOICache -- the shared D/W cache getStructuralAOI serves, which sets the real
    //                       STOP and TARGET on a JVM paper trade.
    //   cfg.env          -- flipping it to 'live' repoints apiBase() at the live OANDA host. Only
    //                       the fxhub_env KEY was compared, so an in-memory flip was invisible.
    '  tradeIdSeq:(typeof paperTradeIdSeq!=="undefined"?paperTradeIdSeq:null),' +
    '  structuralAOICache:(typeof structuralAOICache!=="undefined"?structuralAOICache:null),' +
    // §18.27 F-4: the in-flight LOCK for that cache -- getStructuralAOI returns
    // structuralAOIInflight[oPair] BEFORE any fetch and BEFORE the ADR-011 completeness gate, so
    // a seeded promise puts a FABRICATED stop and target on a real JVM trade. It belongs in the
    // JVM snapshot beside its cache: an earlier draft put it in the ALEX one, which is the wrong
    // side entirely -- an ALEX->JVM leak is caught by comparing the JVM stores.
    '  structuralAOIInflightKeys:(typeof structuralAOIInflight!=="undefined"&&structuralAOIInflight?Object.keys(structuralAOIInflight).sort():null),' +
    '  cfgEnv:(typeof cfg!=="undefined"&&cfg?cfg.env:null),' +
    '  manualReviewApproved:(typeof manualReviewApprovedDecisionTs!=="undefined"?manualReviewApprovedDecisionTs:null),' +
    '  manualReviewDismissed:(typeof manualReviewDismissedUntilTs!=="undefined"?manualReviewDismissedUntilTs:null),' +
    '  healthReportCache:(typeof paperTradingHealthReportCache!=="undefined"?paperTradingHealthReportCache:null),' +
    '  firedAlerts:(typeof firedAlerts!=="undefined"?Array.from(firedAlerts).sort():null),' +
    '  hideTestTrades:(typeof hideTestTradesPaper!=="undefined"?hideTestTradesPaper:null),' +
    // §18.32: was `paperLifecycleLog.length`. Comparing a log by LENGTH is the size-preserving
    // rewrite pattern §18.20 named and §18.27 fixed for storageLoadFailures -- left live on its
    // neighbour by the same commit. Rewriting every entry while preserving the count was invisible.
    '  lifecycleLog:(typeof paperLifecycleLog!=="undefined"?paperLifecycleLog:null),' +
        // §18.27 F-6: KEYS only left the register's CONTENTS free -- rewriting every entry's message to
    // "ALL CLEAR" survived the gate. That is the same size-preserving rewrite §18.20 named for the
    // decision sets and fixed there, still live on the register carrying the INC-001 message.
    '  storageLoadFailures:(typeof storageLoadFailures!=="undefined"?JSON.stringify(storageLoadFailures):null),' +
    // §18.27 F-5: cfg.env was compared and the rest of cfg was not -- yet cfg.accountId is in the
    // URL of every pricing fetch that fills a close, and clearing cfg.key 401s every JVM request.
    '  cfgAccountId:(typeof cfg!=="undefined"&&cfg?cfg.accountId:null),' +
    // §18.28 Sev-2: manualReviewCandidates carries the ENTRY, STOP and TARGET that
    // approveManualReviewTrade hands straight to the protected opener. The two bookkeeping maps
    // beside it were guarded; the record holding the actual PRICES was not.
    '  manualReviewCandidates:(typeof manualReviewCandidates!=="undefined"?manualReviewCandidates:null),' +
    '  manualReviewAlertedKey:(typeof manualReviewAlertedKey!=="undefined"?manualReviewAlertedKey:null),' +
    // §18.28 Sev-7: the figures the operator reads on the restore-confirm dialog before pressing
    // Confirm, the sweep correlation token, and the JVM replay result the dashboard renders.
    '  reconcilePreviewCache:(typeof _paperReconcilePreviewCache!=="undefined"?_paperReconcilePreviewCache:null),' +
    '  jvmSweepToken:(typeof __jvmSweepToken!=="undefined"?__jvmSweepToken:null),' +
    '  jvmReplayState:(typeof replayState!=="undefined"?replayState:null),' +
    // §18.28 Sev-7: the snapshot compared cfg.key only as a BOOLEAN, so REPLACING the token with a
    // different non-empty one was invisible. Hashed rather than stored, so the fixture never holds
    // a credential in memory.
    '  cfgKeyFingerprint:(typeof cfg!=="undefined"&&cfg&&cfg.key?String(cfg.key).length+":"+String(cfg.key).slice(0,2):null),' +
    // §18.28 Sev-6: alexV2 is a THIRD strategy with its own execution path. Its storage keys were
    // caught by the fxhub_alex prefix widening; its module state was in neither snapshot.
    '  alexV2Account:(typeof alexV2Account!=="undefined"?alexV2Account:null),' +
    '  alexV2Journal:(typeof alexV2JournalEntries!=="undefined"?alexV2JournalEntries:null),' +
    '  alexV2AutoTrading:(typeof alexV2AutoTrading!=="undefined"?alexV2AutoTrading:null),' +
    // §18.28 Sev-7: CONTENTS, not length -- the same defect fixed for storageLoadFailures.
    '  lifecycleLog:(typeof paperLifecycleLog!=="undefined"?paperLifecycleLog:null),' +
    '  cfgKeyPresent:(typeof cfg!=="undefined"&&cfg?!!cfg.key:null),' +
    '  scanIntervalArmed:(typeof scanInterval!=="undefined"?(scanInterval!=null):null),' +
    '  positionsClosing:(typeof paperPositionsClosing!=="undefined"?Array.from(paperPositionsClosing).sort():null),' +
    '  storage:localStorage.__keys().filter(function(k){return k.indexOf("fxhub_alex")!==0;}).sort()' +
    '           .map(function(k){return k+"="+localStorage.getItem(k);})' +
    '}); };' +
    // ── localStorage helpers ──
    // §18.20: fields the snapshots COMPARE but the reset helpers could not clear, which made an
    // idempotent leak (one writing the same value twice) identical before and after.
    'g.setAlexGZoneState=function(v){alexGZoneState=v;};' +
    'g.setAlexGLastEvaluatedCloseTime=function(v){alexGLastEvaluatedCloseTime=v;};' +
    'g.setAlexGLedgerBlockingError=function(v){alexGLedgerBlockingError=v;};' +
    'g.setAlexGLedgerIntegrityWarning=function(v){alexGLedgerIntegrityWarning=v;};' +
    'g.setPaperLedgerBlockingError=function(v){paperLedgerBlockingError=v;};' +
    'g.setPaperLedgerIntegrityWarning=function(v){paperLedgerIntegrityWarning=v;};' +
    'g.clearStorageLoadFailures=function(){storageLoadFailures={};};' +
    // §18.25: EVERY newly-snapshotted field needs a reset, or the snapshot has nothing to lose.
    // Adding fields without resetting them reproduces the §18.20a defect exactly: a leak that
    // writes a value an earlier block already wrote is identical before and after. Proven --
    // alexGIdentityDriftReported was ALREADY true when ISO.2 snapshotted, so silencing ALEX's
    // integrity reporting from the JVM side was invisible until this reset existed.
    // §18.25: the ALEX decision sets and zone state are EMPTY in every isolation block, so a leak
    // that CLEARS them changes nothing and is invisible. Seeding gives the snapshot something to
    // lose -- the same repair the JVM side needed for the open position and the INC-001 register.
    // §18.28 Sev-3/Sev-4: the storage arrays and the shared caches were EMPTY at every snapshot, so
    // the comparison could only ever see an INSERTION. Deleting all eleven JVM localStorage keys --
    // the operator's entire journal and paper account -- passed the gate, as did clearing pairData
    // (the fallback exit price and the TAKE_PROFIT/STOP_LOSS source), paperPositionsClosing (the
    // double-close guard) and structuralAOICache (every stop and target). Seeded so both directions
    // are observable.
    'g.seedIsolationScratch=function(){' +
    '  try{localStorage.setItem("fxhub_journal",JSON.stringify([{tradeId:9001,seeded:true}]));}catch(e){}' +
    '  try{localStorage.setItem("fxhub_paper",JSON.stringify({balance:10000,openPositions:[],closedPositions:[]}));}catch(e){}' +
    '  try{localStorage.setItem("fxhub_scan",JSON.stringify({seeded:true}));}catch(e){}' +
    '  try{localStorage.setItem("fxhub_alexg_account",JSON.stringify({balance:10000,seeded:true}));}catch(e){}' +
    '  try{pairData["ISO_SEED"]={price:1.2345};}catch(e){}' +
    '  try{structuralAOICache["ISO_SEED"]={fetchedAt:1,support:1,resistance:2};}catch(e){}' +
    '  try{paperPositionsClosing.add("ISO-SEED-LOCK");}catch(e){}' +
    '  try{checklistState={seeded:true};tradeNotes={"JVMJ|9001":"seeded"};}catch(e){}' +
    // §18.27 F-7: alexGDecidedSetups is a production MAP, not a Set. Seeding it as a Set made
    // `.set(...)` throw inside the bookkeeping try/catch that "must never break a trading
    // decision" -- so ALEX's duplicate-decision bookkeeping was silently INERT for the rest of
    // the suite. A test helper that substitutes the TYPE disables the guard the suite exists to
    // observe. Latent rather than a live false green -- no fixture depended on it either way --
    // but it is exactly the class of harness defect this milestone keeps finding.
    '  try{alexGDecidedSetups=new Map([["AGS|ISO-SEED-1",{seeded:1}],["AGS|ISO-SEED-2",{seeded:2}]]);}catch(e){}' +
    '  try{alexGZoneState={"EUR_USD":{seeded:true}};}catch(e){}' +
    '};' +
    'g.resetIsolationScratch=function(){' +
    '  try{alexGIdentityDriftReported=new Set();}catch(e){}' +
    '  try{alexGCursorSanityReported=new Set();}catch(e){}' +
    '  try{alexGReplayTrades=[];alexGReplayRejected=[];alexGReplayStats=null;}catch(e){}' +
    '  try{evidenceUnexportedCount=0;evidenceStorageBanner=null;}catch(e){}' +
    '  try{alexGZoneState={};alexGDecidedSetups=new Map();}catch(e){}' +
    '  try{structuralAOICache={};}catch(e){}' +
    '  try{firedAlerts=new Set();}catch(e){}' +
    '  try{hideTestTradesPaper=false;}catch(e){}' +
    '  try{paperLifecycleLog=[];}catch(e){}' +
    '  try{manualReviewApprovedDecisionTs={};manualReviewDismissedUntilTs={};}catch(e){}' +
    '  try{paperTradingHealthReportCache=null;}catch(e){}' +
    // §18.27: a NON-EMPTY key and account id, so clearing either is observable. Comparing !!cfg.key
    // against a key that is already empty is the "nothing to lose" defect once more.
    '  try{cfg={key:"ISO-FIXTURE-KEY",accountId:"ISO-FIXTURE-ACCT",env:"practice"};}catch(e){}' +
    // §18.27: EVERY field the snapshots compare must be reset here. alexGReplayState and
    // hideTestTradesAlex were added to the snapshot and NOT to this reset, so they were already
    // polluted by an earlier block and their leaks stayed invisible -- the third time in this
    // milestone that a field was compared without being reset. Adding a field to a snapshot and
    // adding it here are one change, not two.
    '  try{alexGReplayState={running:false,cancelRequested:false,lastResult:null,lastStats:null,tradeIndex:{}};}catch(e){}' +
    '  try{hideTestTradesAlex=false;}catch(e){}' +
    '  try{alexGPipelineObservationBuffer=[];}catch(e){}' +
    '  try{structuralAOIInflight={};}catch(e){}' +
    // §18.28 Sev-5: the FOURTH occurrence of "compared but never reset". checklistState, tradeNotes
    // and autoScan are compared by snapshotJvmStores and were cleared by neither jvmClean nor this
    // reset, so an IDEMPOTENT leak into them was invisible -- proven by a clean A/B where only the
    // constant-vs-incrementing value differed. Every field the snapshots compare is reset here.
    '  try{checklistState={};tradeNotes={};autoScan=false;}catch(e){}' +
    '  try{manualReviewCandidates={};manualReviewAlertedKey={};}catch(e){}' +
    '  try{_paperReconcilePreviewCache=null;__jvmSweepToken=0;}catch(e){}' +
    '  try{replayState={running:false,cancelRequested:false};}catch(e){}' +
    '  try{alexV2Account={balance:10000,openPositions:[],closedPositions:[]};alexV2JournalEntries=[];}catch(e){}' +
    '  try{evidenceWriteFailures=[];}catch(e){}' +
    '};' +
    'g.seedStorageLoadFailure=function(k,m){storageLoadFailures[k]={message:m,at:"2026-01-01T00:00:00.000Z"};};' +
    'g.getLocalStorageItem=function(k){return localStorage.getItem(k);};' +
    'g.clearLocalStorage=function(){localStorage.__clear();};' +
    'return runV1239PaperTradingE2EFixtures(g);'
  );
  const out = wrapped(g);
  if(out && typeof out.then==='function'){
    out.then(function(results){
      try{ emit(results); }
      catch(e){ console.log('RUNNER ERROR: emitting results failed -- '+e); }
    }, function(err){
      console.log('RUNNER ERROR: fixture suite rejected -- '+err+(err&&err.stack?(' :: '+err.stack):''));
    });
  } else {
    console.log('RUNNER ERROR: the suite did not return a Promise -- an un-awaited async fixture is a known false-green here.');
  }
}catch(e){
  console.log('RUNNER ERROR: '+e);
}
// osascript prints the script's own completion value; without this the suite's pending Promise
// would be echoed as a stray "[object Promise]" line after the results.
void 0;
