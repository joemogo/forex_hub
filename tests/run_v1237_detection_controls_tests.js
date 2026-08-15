// MOGO-021 — DETECTION-SURFACE CONTROLS runner (v12.3.7).
//
// PURPOSE
// The MOGO-021 detection-surface coverage audit ran 117 behaviour-changing mutations across the
// signal/AOI/confluence/session/bias surface. 64 of them killed ZERO fixtures out of 1,440: the
// rules were correct, but nothing in the repository would have noticed if they changed. This
// suite closes the proven gaps. It adds fixtures ONLY -- no production line is touched, so it
// changes no behaviour and crosses no governance boundary.
//
// THE STANDING RULE THIS SUITE IS BUILT UNDER
//     THE CANDLES ARE CONSTRUCTED. THE VERDICT IS NOT.
// Every fixture supplies a price series, a clock, a bias table or a live fill -- ordinary inputs
// -- and then reports whatever the frozen function decides. No threshold, weight or rule is
// altered, overridden, stubbed or wrapped anywhere in this suite. ALERT_THRESHOLD, WEIGHTS,
// RULES and RULES_ALEXG are read, never assigned. The only seam is globalThis.fetch, scripted in
// OANDA's own response shapes.
//
// EVERY NEGATIVE CONTROL SITS ONE VARIABLE AWAY FROM A PROVEN POSITIVE CONTROL
// The audit found exclusion fixtures asserting silence against a flat series that could never
// have produced a signal at all -- assertions that would have passed with the rule deleted. In
// this suite each "must not fire" case is paired, in the SAME fixture, with a "does fire" case
// that differs by exactly one input: one bias cell, one candle high, one neighbour's high, one
// live ask. If the positive half stops firing, the negative half stops proving anything and the
// fixture says so.
//
// PROTECTED FUNCTIONS ARE CALLED, NEVER MODIFIED OR RE-IMPLEMENTED:
//   detectSignals, scoreConfluence, bestConfluence, computeAOI, computeAOIWithTouches,
//   findSwingPoints, findAOIs, getSession, getBias, getScore, evaluateLiveTrigger,
//   alexGZoneRole, alexGConstructLivePosition, alexGDetermineTradeDirection, pipSize,
//   alexGRunSetupEngine, alexGCheckSwingAt, alexGFindSwingPoints, alexGAssignCluster, calcATR.
//
// S12 (the ALEX FROZEN ZONE ENGINE) drives the REAL alexGRunSetupEngine over constructed H1
// price series and then asserts the EXACT zone and setup the frozen engine produced -- its
// boundaries, its touch list, its strength tier, its quality, its break direction, its
// qualification close. calcATR is exposed alongside it because several S12 series place a
// candle at an EXACT multiple of the engine's own ATR; the fixture uses the engine's own
// frozen ATR function to build that candle, and then asserts what the engine decides about it.
// Nothing in S12 is stubbed, wrapped or forced: the only writes are to ordinary application
// state (alexGZoneState / alexGSetupState / alexGLastEvaluatedCloseTime), reset between
// fixtures exactly as a fresh page load resets them. NO PAPER TRADE IS EVER PERSISTED --
// alexGConstructLivePosition is the pure decision core and writes to no account or journal.
//
// Run from the project root:
//   osascript -l JavaScript tests/run_v1237_detection_controls_tests.js
// or simply:  tests/run_all.sh   (discovers and runs this automatically)
//
// Opens NO browser, touches NO Chrome profile, performs NO real network I/O, writes NOTHING to
// disk and persists NO paper trade. indexedDB is undefined, localStorage is in-memory, fetch is
// stubbed. Modelled on tests/run_v130_candle_completeness_regression_tests.js.
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
const appCode=extractScriptBody(readFile('./index.html'));
const testCode=readFile('./tests/v1237_detection_controls_tests.js');

// ── DOM / storage stubs (same shape as run_v130 / run_v1233) ─────────────────────────────────
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
  setItem:(k,v)=>{lsStore[k]=String(v);},removeItem:k=>{delete lsStore[k];}
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

// ── Simulated clock ──────────────────────────────────────────────────────────────────────────
// Monday 2026-08-10, 14:00 UTC. Both facts are the strategy's OWN gates, not fixture
// conveniences: isPreferredTradingDay() requires Mon-Wed, and 14:00 UTC is inside the
// London/NY overlap that getSession() calls a priority window. Fixing the clock is what makes
// the live-trigger fixtures deterministic; nothing about the verdict is fixed with it.
const __RealDate=Date;
let __simNow=__RealDate.UTC(2026,7,10,14,0,0);
globalThis.Date=class extends __RealDate{
  constructor(...a){ if(a.length===0) super(__simNow); else super(...a); }
  static now(){ return __simNow; }
};

// ── Scripted network boundary ────────────────────────────────────────────────────────────────
function makeResponse(ok,status,body){
  return{ok,status,json:()=>Promise.resolve(body),text:()=>Promise.resolve('')};
}
// Wraps a plain OHLC bar list into OANDA's own candle shape. toFixed(5)/parseFloat round-trips
// every 5-decimal price in this suite exactly, so the boundary constructions the fixtures rely
// on survive the transport layer bit-for-bit.
function toOanda(bars){
  return bars.map(function(b,i){
    return{time:new __RealDate(__simNow-(bars.length-i)*900000).toISOString(),complete:true,
      mid:{o:b.o.toFixed(5),h:b.h.toFixed(5),l:b.l.toFixed(5),c:b.c.toFixed(5)}};
  });
}
// Daily/weekly structure for getStructuralAOI(): a support shelf repeatedly touched near 1.0990
// and resistance far above near 1.1201. COPIED VERBATIM from
// tests/run_v1233_jvm_autotrade_reliability_tests.js (which is owned by another agent and is not
// touched by this suite) so both suites drive the frozen AOI engine from identical structure.
// The 3-touch requirement is met by genuine repeated touches, not by widening any tolerance.
function structuralCandles(n){
  const out=[];
  for(let i=n;i>=1;i--){
    const phase=i%6;
    let lo,hi;
    if(phase===0){lo=1.09900;hi=1.11000;}
    else if(phase===1){lo=1.09905;hi=1.11500;}
    else if(phase===2){lo=1.09895;hi=1.12000;}
    else if(phase===3){lo=1.10500;hi=1.11980;}
    else if(phase===4){lo=1.10400;hi=1.12010;}
    else {lo=1.10200;hi=1.11200;}
    out.push({o:lo+0.0005,h:hi,l:lo,c:hi-0.0005});
  }
  return out;
}
let __m15Bars=null,__bid=1.10025,__ask=1.10035;
globalThis.fetch=function(url){
  const u=String(url);
  if(/\/pricing/.test(u)){
    return Promise.resolve(makeResponse(true,200,{prices:[{bids:[{price:__bid.toFixed(5)}],asks:[{price:__ask.toFixed(5)}]}]}));
  }
  if(/granularity=D/.test(u)) return Promise.resolve(makeResponse(true,200,{candles:toOanda(structuralCandles(120))}));
  if(/granularity=W/.test(u)) return Promise.resolve(makeResponse(true,200,{candles:toOanda(structuralCandles(60))}));
  if(__m15Bars) return Promise.resolve(makeResponse(true,200,{candles:toOanda(__m15Bars)}));
  // No M15 series has been installed -- fail loudly rather than let an unscripted request fall
  // through to something that looks like data.
  return Promise.resolve(makeResponse(false,503,{}));
};

// ── the g bridge ─────────────────────────────────────────────────────────────────────────────
const g={};
g.setM15Bars=function(bars){ __m15Bars=bars; };
g.setBidAsk=function(bid,ask){ __bid=bid; __ask=ask; };
g.structuralCandles=structuralCandles;
g.utc=function(y,mo,d,h,mi){ return new __RealDate(__RealDate.UTC(y,mo,d,h||0,mi||0,0)); };
g.now=function(){ return __simNow; };

const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // ── REAL, PROTECTED functions (called, never re-implemented, never modified) ──
  'g.detectSignals=detectSignals;' +
  'g.scoreConfluence=scoreConfluence;' +
  'g.bestConfluence=bestConfluence;' +
  'g.computeAOI=computeAOI;' +
  'g.computeAOIWithTouches=computeAOIWithTouches;' +
  'g.findSwingPoints=findSwingPoints;' +
  'g.findAOIs=findAOIs;' +
  'g.getSession=getSession;' +
  'g.getBias=getBias;' +
  'g.getScore=getScore;' +
  'g.evaluateLiveTrigger=evaluateLiveTrigger;' +
  'g.alexGZoneRole=alexGZoneRole;' +
  'g.alexGConstructLivePosition=alexGConstructLivePosition;' +
  'g.pipSize=pipSize;' +
  // ── S12: the frozen ALEX zone/setup engine and its own helpers, called never re-implemented ──
  'g.alexGRunSetupEngine=alexGRunSetupEngine;' +
  'g.alexGCheckSwingAt=alexGCheckSwingAt;' +
  'g.alexGFindSwingPoints=alexGFindSwingPoints;' +
  'g.alexGAssignCluster=alexGAssignCluster;' +
  'g.alexGDetermineTradeDirection=alexGDetermineTradeDirection;' +
  'g.calcATR=calcATR;' +
  // ── S13: the two UNCOVERED copies of the counter-trend predicate ──
  'g.evaluateSetupFullBreakdownCore=evaluateSetupFullBreakdownCore;' +
  'g.simulateTrueMTFReplay=simulateTrueMTFReplay;' +
  'g.calcBiasFromCandles=calcBiasFromCandles;' +
  // ── PROTECTED CONSTANTS, read through live accessors so a fixture can never hold a stale copy
  //    and can never assign one back ──
  'g.ALERT_THRESHOLD=function(){return ALERT_THRESHOLD;};' +
  'g.WEIGHTS=function(){return WEIGHTS;};' +
  'g.RULES=function(){return RULES;};' +
  'g.ALEXG_CONFIG=function(){return RULES_ALEXG.config;};' +
  // ── ordinary application state the fixtures set up, exactly as the app itself would ──
  'g.setScanData=function(pair,row){ scanData[pair]=row; };' +
  'g.resetScanData=function(){ scanData={}; };' +
  'g.setCfg=function(){ cfg.key="fixture"; cfg.accountId="acct"; cfg.env="practice"; };' +
  'g.resetStructuralAOICache=function(){ structuralAOICache={}; structuralAOIInflight={}; };' +
  'g.resetAlexG=function(){ alexGAccount={balance:10000,startingBalance:10000,openPositions:[],closedPositions:[]};' +
  '  alexGJournalEntries=[]; alexGAutoTrading={enabled:false,tradedToday:{},log:[],activatedAt:null,tradedSignals:{}}; };' +
  'g.resetPairData=function(){ pairData={}; };' +
  // Ordinary ALEX zone-engine state, reset exactly as a fresh page load resets it (these three
  // are plain module-level variables the app itself re-initialises the same way). Deliberately
  // SEPARATE from the engine run itself, so an S12 fixture can also decline to reset and drive
  // the engine twice over the same persisted state -- which is precisely what live polling does.
  'g.resetAlexGZoneEngine=function(){ alexGZoneState={}; alexGSetupState=[]; alexGLastEvaluatedCloseTime={}; };' +
  'g.alexGZoneStateFor=function(pair,tf){ return alexGZoneState[pair][tf]; };' +
  'g.alexGSetupStateAll=function(){ return alexGSetupState; };' +
  // ── S14: the eleven rules that survived even the first detection-controls pass ──
  'g.clusterLevels=clusterLevels;' +
  'g.alexGIsSameInteraction=alexGIsSameInteraction;' +
  'g.alexGCreateSetupRecord=alexGCreateSetupRecord;' +
  'g.alexGSetupId=alexGSetupId;' +
  'g.marketDataCompletenessOf=marketDataCompletenessOf;' +
  'g.MARKET_DATA_COMPLETENESS=function(){return MARKET_DATA_COMPLETENESS;};' +
  'g.MARKET_DATA_MIN_USABLE_CANDLES=function(){return MARKET_DATA_MIN_USABLE_CANDLES;};' +
  'return runV1237DetectionControlFixtures(g);'
);

wrapped(g).then(function(results){
  let pass=0,fail=0;
  results.forEach(function(r){
    if(r.pass){pass++;console.log('PASS -- '+r.name+(r.detail?'  ['+r.detail+']':''));}
    else{fail++;console.log('FAIL -- '+r.name+(r.detail?'  ['+r.detail+']':''));}
  });
  console.log('---');
  if(fail===0){
    console.log('ALL DETECTION-CONTROL FIXTURES PASSED ('+results.length+' executed)');
  }else{
    console.log('FAILURES: '+fail+'/'+results.length+' executed');
  }
}).catch(function(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
  if(e&&e.stack) console.log(e.stack);
});
