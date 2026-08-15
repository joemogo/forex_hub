// Self-contained runner for the MOGO-021 MARKET-DATA CONTINUITY fixture suite (v12.39).
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1239_market_data_continuity_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically)
//
// SCOPE: candle acquisition, merge and storage; pagination termination; the completeness gates;
// candle alignment and period boundaries; forming vs closed bars; and whether MOGO continuously
// and accurately observes EVERY configured instrument and timeframe -- ending at the proof that
// the series a frozen rule engine EVALUATES is the same series the completeness gate blessed.
//
// This runner opens NO browser, touches NO Chrome profile, performs NO real network I/O, opens NO
// paper trade and writes NOTHING to disk. The ONLY seam is globalThis.fetch, answered in OANDA's
// own response shapes by a router the fixtures script per scenario. No application function is
// stubbed, mocked, wrapped or re-implemented -- every assertion runs the real code.
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
const testCode=readFile('./tests/v1239_market_data_continuity_tests.js');

// ── DOM / storage / timer stubs (same shape as run_v_paper_trading_audit_tests.js) ───────────
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
    scrollIntoView:function(){},remove:function(){},
    getBoundingClientRect:function(){return{top:0,left:0,width:0,height:0};}};
}
const lsStore={};
globalThis.document={
  getElementById:function(id){ if(!elMap[id]) elMap[id]=makeStub(); return elMap[id]; },
  querySelector:function(){return null;},querySelectorAll:function(){return [];},
  createElement:function(){return makeStub();},addEventListener:function(){},
  visibilityState:'visible',body:{appendChild:function(){},removeChild:function(){}},activeElement:null
};
globalThis.window={devicePixelRatio:1};
globalThis.localStorage={
  getItem:function(k){return Object.prototype.hasOwnProperty.call(lsStore,k)?lsStore[k]:null;},
  setItem:function(k,v){lsStore[k]=String(v);},
  removeItem:function(k){delete lsStore[k];},
  __keys:function(){return Object.keys(lsStore);},
  __clear:function(){Object.keys(lsStore).forEach(function(k){delete lsStore[k];});}
};
globalThis.alert=function(){};
globalThis.confirm=function(){return true;};
globalThis.Blob=function(parts,opts){return{parts:parts,opts:opts};};
globalThis.URL={createObjectURL:function(){return 'blob:stub';},revokeObjectURL:function(){}};
let __fakeTimerId=0;
globalThis.setTimeout=function(){return ++__fakeTimerId;};globalThis.clearTimeout=function(){};
globalThis.setInterval=function(){return ++__fakeTimerId;};globalThis.clearInterval=function(){};
globalThis.ResizeObserver=function(){return{observe:function(){},disconnect:function(){}};};
globalThis.LightweightCharts={LineStyle:{Solid:0,Dashed:1,Dotted:2},CrosshairMode:{Normal:0}};
globalThis.Notification=undefined;

// ── Scripted network boundary ────────────────────────────────────────────────────────────────
// A ROUTER, not a fixed script: fixtures answer per (instrument, granularity, count, to), which is
// what makes "one instrument fails while the other 34 do not" and "only the Weekly is short"
// expressible at all. Anything the fixture does not answer is a hard error, so an unexpected
// request can never fall through to a real network call.
const REQS=[];
let router=null;
function parseReq(url){
  const u=String(url);
  const mi=u.match(/\/v3\/instruments\/([A-Z_]+)\/candles/);
  const mc=u.match(/[?&]count=(\d+)/);
  const mg=u.match(/[?&]granularity=([A-Z0-9]+)/);
  const mt=u.match(/[?&]to=([^&]+)/);
  const mp=u.match(/\/pricing\?instruments=([A-Z_]+)/);
  return{url:u,kind:mp?'pricing':(mi?'candles':'other'),
    instrument:mp?mp[1]:(mi?mi[1]:null),
    granularity:mg?mg[1]:null,
    count:mc?parseInt(mc[1],10):null,
    to:mt?decodeURIComponent(mt[1]):null};
}
globalThis.fetch=function(url){
  const req=parseReq(url);
  req.index=REQS.length;
  REQS.push(req);
  if(!router) return Promise.reject(new Error('no route configured for '+req.url));
  const res=router(req);
  if(res===undefined||res===null) return Promise.reject(new Error('router returned nothing for '+req.url));
  return Promise.resolve(res);
};
function response(ok,status,body){
  return{ok:ok,status:status,json:function(){return Promise.resolve(body);},text:function(){return Promise.resolve('');}};
}

const g={};
// ── deterministic synthetic market ───────────────────────────────────────────────────────────
// Bar k of a granularity starts at baseMs + k*durMs. Prices trend gently so the frozen
// evaluators have genuine structure to find -- a flat series would make "zero signals" pass for
// the wrong reason. Every price is a pure function of the bar's absolute start time, so two
// fixtures describing the same bar describe the SAME bar.
g.TF_MS={M15:900000,H1:3600000,H4:4*3600000,D:86400000,W:7*86400000};
g.ISO=function(ms){ return new Date(ms).toISOString(); };
function priceOf(startMs){ return 1.1000+((startMs/60000)%9973)*0.0000041; }
// One OANDA-shape candle for the bar starting at startMs.
g.bar=function(startMs,complete){
  const base=priceOf(startMs);
  return{time:new Date(startMs).toISOString(),complete:complete!==false,
    mid:{o:base.toFixed(5),h:(base+0.0012).toFixed(5),l:(base-0.0003).toFixed(5),c:(base+0.0009).toFixed(5)}};
};
// `n` consecutive bars, OLDEST FIRST (OANDA's own order), the LAST of which is optionally still
// forming. endMs is the START of the newest bar in the page.
g.bars=function(endMs,durMs,n,formingLast){
  const out=[];
  for(let i=n-1;i>=0;i--) out.push(g.bar(endMs-i*durMs,!(formingLast&&i===0)));
  return out;
};
g.okPage=function(candles){ return response(true,200,{candles:candles}); };
g.errPage=function(status){ return response(false,status,{errorMessage:'scripted '+status}); };
g.emptyPage=function(){ return response(true,200,{candles:[]}); };
g.okPrice=function(){ return response(true,200,{prices:[{bids:[{price:'1.10000'}],asks:[{price:'1.10020'}]}]}); };
g.route=function(fn){ router=fn; REQS.length=0; };
g.reqs=function(){ return REQS.slice(); };
g.candleReqs=function(){ return REQS.filter(function(r){return r.kind==='candles';}); };
g.reqCount=function(){ return REQS.length; };
// Clock control -- a market-data suite that reads the real wall clock is not reproducible.
g.freezeClock=function(ms){ if(!g.__realNow){ g.__realNow=Date.now; } Date.now=function(){return ms;}; };
g.restoreClock=function(){ if(g.__realNow){ Date.now=g.__realNow; g.__realNow=null; } };
g.lsKeys=function(){ return localStorage.__keys(); };
g.lsGet=function(k){ return localStorage.getItem(k); };
g.lsClear=function(){ localStorage.__clear(); };
g.elHtml=function(id){ const e=elMap[id]; return e?String(e.innerHTML||''):''; };

const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // ── the real, unmodified acquisition / continuity chain under test ──
  'g.fetchCandles=fetchCandles;' +
  'g.fetchCandlesRange=fetchCandlesRange;' +
  'g.marketDataCompletenessOf=marketDataCompletenessOf;' +
  'g.MARKET_DATA_COMPLETENESS=MARKET_DATA_COMPLETENESS;' +
  'g.MARKET_DATA_MIN_USABLE_CANDLES=MARKET_DATA_MIN_USABLE_CANDLES;' +
  'g.getCandleCloseTime=getCandleCloseTime;' +
  'g.precomputeCloseTimes=precomputeCloseTimes;' +
  'g.getNYOffsetMinutes=getNYOffsetMinutes;' +
  'g.nyAlignedClose=nyAlignedClose;' +
  // ── the real observation paths ──
  'g.scanPair=scanPair;' +
  'g.scanAll=scanAll;' +
  'g.runAutoTopDownScan=runAutoTopDownScan;' +
  'g.evaluateLiveTrigger=evaluateLiveTrigger;' +
  'g.getStructuralAOI=getStructuralAOI;' +
  'g.resetStructuralAOICache=function(){structuralAOICache={};structuralAOIInflight={};};' +
  'g.alexGEvaluatePairForLiveSetups=alexGEvaluatePairForLiveSetups;' +
  'g.fetchAlexGReplayDatasets=fetchAlexGReplayDatasets;' +
  // ── REAL, PROTECTED evaluators (called, never re-implemented, never modified) ──
  'g.detectSignals=detectSignals;' +
  'g.bestConfluence=bestConfluence;' +
  // ── live-binding state accessors ──
  'g.ALL_PAIRS=ALL_PAIRS;' +
  'g.SCAN_PAIRS=SCAN_PAIRS;' +
  'g.pairData=function(){return pairData;};' +
  'g.resetPairData=function(){pairData={};};' +
  'g.setActiveTf=function(v){activeTf=v;};' +
  'g.setActivePair=function(v){activePair=v;};' +
  'g.getScanData=function(){return scanData;};' +
  'g.setScanData=function(v){scanData=v;};' +
  'g.initScan=initScan;' +
  'g.loadSaved=loadSaved;' +
  'g.setCfg=function(v){cfg=v;};' +
  'g.getAutoTrading=function(){return autoTrading;};' +
  'g.setAutoTradingEnabled=function(v){autoTrading.enabled=v;};' +
  'g.resetFiredAlerts=function(){firedAlerts.clear();};' +
  'g.getDecisionEvents=function(){return decisionEventLog.slice();};' +
  'g.clearDecisionEvents=function(){clearDecisionEvents();};' +
  // The DURABLE poll observation scanAll hands the forward-coverage ledger. Captured through the
  // real builder, not the raw seam input: asserting on the seam argument would pass even if the
  // builder dropped the field, which tests the hook rather than the record.
  'var __lastObs=null; const __origRecObs=evidenceRecordForwardObservations;' +
  'evidenceRecordForwardObservations=function(input){ try{ __lastObs=evidenceBuildPollObservation((input&&input.poll)||{}); }catch(e){ __lastObs=(input&&input.poll)||{}; } return __origRecObs.apply(this,arguments); };' +
  'g.lastObs=function(){ return __lastObs||{}; };' +
  'g.resetObs=function(){ __lastObs=null; };' +
  'return runMarketDataContinuityFixtures(g);'
);
wrapped(g).then(function(results){
  results.forEach(function(r){
    const tag = r.pass===null ? 'NOTE' : (r.pass?'PASS':'FAIL');
    console.log(tag+' -- '+r.name+(r.detail?' ('+r.detail+')':''));
  });
  const executed=results.filter(function(r){return r.pass!==null;});
  const failCount=executed.filter(function(r){return !r.pass;}).length;
  console.log('---');
  console.log(failCount===0
    ?('ALL MARKET-DATA CONTINUITY FIXTURES PASSED ('+executed.length+' executed)')
    :('FAILURES: '+failCount+'/'+executed.length+' executed'));
}).catch(function(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
  if(e&&e.stack) console.log(e.stack);
});
