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
    '  engineErrors:alexGEngineErrors.filter(function(e){return !(e&&e.__evidencePlatform===true);}),' +
    '  knownVersion:alexGAccountKnownVersion,' +
    '  blockingError:alexGLedgerBlockingError, integrityWarning:alexGLedgerIntegrityWarning,' +
    '  lastEvaluatedCloseTime:alexGLastEvaluatedCloseTime,' +
    // decidedCount recorded only .size -- rewriting every key while preserving the count was
    // invisible. The CONTENTS are compared now.
    '  decidedSetups:Array.from(alexGDecidedSetups).sort(),' +
    '  decidedEconomic:(typeof alexGDecidedEconomic!=="undefined"?Array.from(alexGDecidedEconomic).sort():null),' +
    '  signalInFlight:(typeof alexGSignalInFlight!=="undefined"?Array.from(alexGSignalInFlight).sort():null),' +
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
    '  storageLoadFailures:(typeof storageLoadFailures!=="undefined"?Object.keys(storageLoadFailures).sort():null),' +
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
