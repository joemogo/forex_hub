// Self-contained runner for the MOGO-003 candle-completeness regression fixture.
// Reads index.html directly and extracts its <script> body itself, following the same pattern
// as run_v128/run_v129 and, for the async driving convention, run_v126_phase2c_wave1_tests.js.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v130_candle_completeness_regression_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically)
//
// ⚠️ THIS SUITE IS EXPECTED TO REPORT FAILURES against current production. The SAFETY-* fixtures
// encode a required safety contract that production does not yet satisfy. See the header of
// tests/v130_candle_completeness_regression_tests.js.
//
// This runner opens NO browser, touches NO Chrome profile, performs NO real network I/O and
// writes NOTHING to disk. The only seam is globalThis.fetch, scripted per scenario in OANDA's
// own response shapes -- no application function is stubbed, mocked or re-implemented.
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
const testCode=readFile('./tests/v130_candle_completeness_regression_tests.js');

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
  removeItem:function(k){delete lsStore[k];}
};
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

// ── Scripted network boundary ────────────────────────────────────────────────────────────────
// One entry per expected request, in order. The last entry repeats if more requests arrive, so
// an unexpected extra page can never silently fall through to a real network call.
let fetchScript=[],fetchIdx=0,fetchUrls=[];
globalThis.fetch=function(url){
  fetchUrls.push(url);
  const step=fetchScript[fetchIdx]||fetchScript[fetchScript.length-1];
  fetchIdx++;
  if(!step) return Promise.reject(new Error('no scripted response'));
  return step();
};
function makeResponse(ok,status,body){
  return{ok:ok,status:status,json:function(){return Promise.resolve(body);},text:function(){return Promise.resolve('');}};
}
// A gently trending series, so signal/confluence detection has genuine structure to find --
// a flat series would make "zero signals" pass for the wrong reason.
function candleArray(rawCount,completeCount){
  const cc=(completeCount===undefined)?rawCount:completeCount;
  const out=[];
  for(let i=0;i<rawCount;i++){
    const base=1.1000+i*0.0004;
    out.push({time:new Date(Date.UTC(2026,0,1,0,i)).toISOString(),complete:i<cc,
      mid:{o:base.toFixed(5),h:(base+0.0012).toFixed(5),l:(base-0.0003).toFixed(5),c:(base+0.0009).toFixed(5)}});
  }
  return out;
}

const g={};
g.setFetchScript=function(steps){ fetchScript=steps; fetchIdx=0; fetchUrls=[]; };
g.fetchCallCount=function(){ return fetchUrls.length; };
g.fetchUrls=function(){ return fetchUrls.slice(); };
g.RESP_429=function(){ return Promise.resolve(makeResponse(false,429,{errorMessage:'Rate limit exceeded'})); };
g.okCandles=function(n){ return function(){ return Promise.resolve(makeResponse(true,200,{candles:candleArray(n)})); }; };
g.okCandlesRaw=function(raw,complete){ return function(){ return Promise.resolve(makeResponse(true,200,{candles:candleArray(raw,complete)})); }; };
g.okPrice=function(){ return function(){ return Promise.resolve(makeResponse(true,200,{prices:[{bids:[{price:'1.10000'}],asks:[{price:'1.10020'}]}]})); }; };
// ADR-011: the contract is ONE abstraction, so this asserts that specific field rather than
// accepting any of a loose set of plausible names. This is STRICTER than the heuristic it
// replaces, which was written before the contract existed and would have accepted a bare
// httpStatus as sufficient -- exactly the transport-level detail consumers must not depend on.
// Deliberately NOT a missingCandles check: session, weekend, holiday and liquidity gaps make
// requested-minus-received unsound as a measure of missing market data.
g.MARKET_DATA_STATES=['COMPLETE','PARTIAL','UNAVAILABLE'];
g.hasCompletenessState=function(v){
  if(!v||typeof v!=='object') return false;
  if(!Object.prototype.hasOwnProperty.call(v,'completenessState')) return false;
  return g.MARKET_DATA_STATES.indexOf(v.completenessState)!==-1;
};
g.completenessStateOf=function(v){ return (v&&typeof v==='object')?v.completenessState:undefined; };
g.diagnosticsHtml=function(){ return (elMap['marketDataCompletenessCard']||{innerHTML:''}).innerHTML||''; };
g.scannerCardHtml=function(){ return (elMap['marketDataCompletenessCardScanner']||{innerHTML:''}).innerHTML||''; };
// The raw document, so a fixture can assert WHERE a container lives rather than merely that
// something was written into it. VISIBILITY-1 could not tell a visible element from one inside a
// display:none panel; these can.
g.rawHtml=function(){ return html; };

const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // ── the real, unmodified market-data and scanner chain under test ──
  'g.fetchCandles=fetchCandles;' +
  'g.fetchCandlesRange=fetchCandlesRange;' +
  'g.scanPair=scanPair;' +
  // ── REAL, PROTECTED functions (called, never re-implemented, never modified) ──
  'g.detectSignals=detectSignals;' +
  'g.bestConfluence=bestConfluence;' +
  'g.scoreConfluence=scoreConfluence;' +
  'g.findSwingPoints=findSwingPoints;' +
  // ── live-binding accessors ──
  'g.marketDataCompletenessOf=marketDataCompletenessOf;' +
  'g.renderMarketDataCompletenessDiagnostics=renderMarketDataCompletenessDiagnostics;' +
  'g.renderChartEvaluationState=renderChartEvaluationState;' +
  'g.chartStateHtml=function(){return (document.getElementById("chartEvaluationState")||{innerHTML:""}).innerHTML||"";};' +
  'g.pairData=function(){return pairData;};' +
  'g.resetPairData=function(){pairData={};};' +
  'g.setActiveTf=function(v){activeTf=v;};' +
  'return runCandleCompletenessFixtures(g);'
);
wrapped(g).then(function(results){
  results.forEach(r=>{
    const tag = r.pass===null ? 'NOTE(source)' : (r.pass?'PASS':'FAIL');
    console.log(tag+' -- '+r.name+(r.detail?' ('+r.detail+')':''));
  });
  const executed=results.filter(r=>r.pass!==null);
  const failCount=executed.filter(r=>!r.pass).length;
  console.log('---');
  if(failCount===0){
    console.log('ALL CANDLE-COMPLETENESS FIXTURES PASSED ('+executed.length+' executed)');
  }else{
    console.log('FAILURES: '+failCount+'/'+executed.length+' executed');
    console.log('NOTE: SAFETY-* failures are EXPECTED against current production. They encode the');
    console.log('required safety contract, not current behaviour. Do not weaken them to go green.');
  }
}).catch(function(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
  if(e&&e.stack) console.log(e.stack);
});
