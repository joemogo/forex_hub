// Self-contained runner for the v12.3.9 CHART / AOI FIDELITY fixture suite.
//
// WHY THIS SUITE EXISTS. A mutation re-score of the CHART side of the strategy -- what the
// operator SEES drawn over the candles, and whether the scanner actually visits every
// configured instrument and timeframe -- found a large block of behaviour-changing mutations
// that killed ZERO fixtures anywhere in the gate. The structural cause is the one the
// programme report already names in §10.3: nothing in the repository ever ran loadChart(),
// drawTradeOverlay() or renderAlexGLiveSetupsPanel(), and the one fixture that claimed to
// protect the chart-versus-engine authority property (v13.0 CHART-3) asserts on the TEXT of
// index.html rather than on anything the chart draws. An AOI band could be drawn inverted,
// at the wrong level, on the wrong side, for a zone the engine REJECTED, or recomputed at
// draw time so the chart and the engine silently disagree -- with no fixture objecting.
//
// WHAT THIS SUITE DOES. It drives the REAL, unmodified chart/scan functions against isolated
// in-memory state with the network stubbed at the fetch() boundary ONLY (OANDA's own response
// shape, so the real fetchCandles/getStructuralAOI/computeAOI chain genuinely parses and
// computes), and a recording Lightweight-Charts stub in place of the real charting library.
// It then reads back the EXACT price levels, titles, markers and rendered strings, and
// compares them against literals computed BY HAND in the fixture file from a candle series
// designed so that every expected number is derivable on paper.
//
//   * NO source-text assertions. Nothing here reads index.html or matches a function body.
//   * NO presence-only assertions where a wrong PRICE would still pass -- every drawn level
//     is asserted as a value, not as a count.
//   * NO re-derivation. Expected levels are literals (1.17000 support, band 0.00400,
//     therefore 1.17400/1.16600), never recomputed the way computeAOI computes them.
//   * The AOI computation, the zone engine and the scanner are never called directly to
//     "prove they work" -- they are asserted THROUGH the renderer or the sweep that must
//     reach them, so a call site deleted at the display layer fails the fixture too.
//
// NO REAL PAPER TRADE IS EVER PERSISTED: this process has stubbed localStorage, stubbed
// fetch, and no access to any real saved data.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1239_chart_aoi_fidelity_tests.js
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
try{
const html=readFile('./index.html');
const appCode=extractScriptBody(html);
const testCode=readFile('./tests/v1239_chart_aoi_fidelity_tests.js');

const elMap={};
const makeClassList=function(){
  const classes=new Set();
  return{
    add:function(c){classes.add(c);},
    remove:function(c){classes.delete(c);},
    toggle:function(c,force){ if(force===undefined){ if(classes.has(c)) classes.delete(c); else classes.add(c); } else if(force) classes.add(c); else classes.delete(c); },
    contains:function(c){return classes.has(c);}
  };
};
const makeStub=function(){
  return {innerHTML:'',textContent:'',value:'',className:'',style:{},options:[{value:'All'}],width:100,height:100,
    clientWidth:800,clientHeight:320,disabled:false,checked:false,
    classList:makeClassList(),
    getContext:function(){return{clearRect:function(){},beginPath:function(){},moveTo:function(){},lineTo:function(){},stroke:function(){},fillRect:function(){},strokeRect:function(){},save:function(){},restore:function(){},setLineDash:function(){},arc:function(){},fill:function(){},closePath:function(){},fillText:function(){},setTransform:function(){},transform:function(){},scale:function(){},translate:function(){},rotate:function(){},rect:function(){},quadraticCurveTo:function(){},bezierCurveTo:function(){},createLinearGradient:function(){return{addColorStop:function(){}};},measureText:function(){return{width:0};},lineWidth:1,strokeStyle:'',fillStyle:'',font:'',globalAlpha:1,textAlign:'',textBaseline:'',lineCap:'',lineJoin:''};},
    appendChild:function(){},addEventListener:function(){},focus:function(){},setSelectionRange:function(){},
    getBoundingClientRect:function(){return{top:0,left:0,width:800,height:320};}};
};
const lsStore={};
globalThis.document={
  getElementById:function(id){ if(!elMap[id]) elMap[id]=makeStub(); return elMap[id]; },
  querySelector:function(){return null;},
  querySelectorAll:function(){return [];},
  createElement:function(){return makeStub();},
  addEventListener:function(){},
  body:{appendChild:function(){},removeChild:function(){}},
  activeElement:null,
  fullscreenElement:null
};
globalThis.window={devicePixelRatio:1};
globalThis.localStorage={
  getItem:function(k){return Object.prototype.hasOwnProperty.call(lsStore,k)?lsStore[k]:null;},
  setItem:function(k,v){lsStore[k]=v;},
  removeItem:function(k){delete lsStore[k];},
  __keys:function(){return Object.keys(lsStore);},
  __clear:function(){Object.keys(lsStore).forEach(k=>delete lsStore[k]);}
};
globalThis.alert=function(){};
globalThis.confirm=function(){return true;};
globalThis.Blob=function(parts,opts){return{parts,opts};};
globalThis.URL={createObjectURL:function(){return 'blob:stub';},revokeObjectURL:function(){}};
let __fakeTimerId=0;
globalThis.setTimeout=function(){return ++__fakeTimerId;};globalThis.clearTimeout=function(){};
globalThis.setInterval=function(){return ++__fakeTimerId;};globalThis.clearInterval=function(){};
globalThis.ResizeObserver=function(){return{observe:function(){},disconnect:function(){}};};
globalThis.Notification=undefined;

// ── RECORDING CHART STUB ───────────────────────────────────────────────────────────────
// Stands in for the real Lightweight Charts library (which is a <script src> the offline
// harness cannot load) and records exactly what the application asked it to draw: every
// series with its options and its data, every price line, every marker set. This is a
// LIBRARY boundary stub -- no application function is replaced, wrapped or re-implemented.
const chartRec={series:[],priceLines:[],markers:[],chartsCreated:0,seriesRemoved:0};
// NOTE: these are function EXPRESSIONS, not declarations. A function DECLARATION inside this
// try block is hoisted out of the block by JavaScriptCore and loses its closure over the
// block-scoped recorder, which then fails only when called back from inside new Function().
const resetChartRec=function(){ chartRec.series=[]; chartRec.priceLines=[]; chartRec.markers=[];
  chartRec.chartsCreated=0; chartRec.seriesRemoved=0; };
const makeSeriesStub=function(kind,opts){
  const s={kind:kind,opts:opts||{},data:null,
    setData:function(d){this.data=d;},
    setMarkers:function(m){chartRec.markers=m||[];},
    applyOptions:function(o){Object.assign(this.opts,o||{});},
    createPriceLine:function(o){const l={opts:o,series:this};chartRec.priceLines.push(l);return l;},
    removePriceLine:function(l){const i=chartRec.priceLines.indexOf(l);if(i>=0)chartRec.priceLines.splice(i,1);},
    priceToCoordinate:function(){return 100;},
    coordinateToPrice:function(){return 1.1;}};
  chartRec.series.push(s);
  return s;
};
globalThis.LightweightCharts={
  LineStyle:{Solid:0,Dashed:1,Dotted:2},
  CrosshairMode:{Normal:0},
  createChart:function(){
    chartRec.chartsCreated++;
    const ts={fitContent:function(){},applyOptions:function(){},setVisibleLogicalRange:function(){},
      getVisibleLogicalRange:function(){return{from:0,to:10};},
      subscribeVisibleLogicalRangeChange:function(){},
      coordinateToTime:function(){return null;},timeToCoordinate:function(){return 0;},
      options:function(){return{barSpacing:6};}};
    return{
      addCandlestickSeries:function(o){return makeSeriesStub('candle',o);},
      addLineSeries:function(o){return makeSeriesStub('line',o);},
      addBaselineSeries:function(o){return makeSeriesStub('baseline',o);},
      applyOptions:function(){},remove:function(){},
      removeSeries:function(s){chartRec.seriesRemoved++;const i=chartRec.series.indexOf(s);if(i>=0)chartRec.series.splice(i,1);},
      subscribeCrosshairMove:function(){},
      timeScale:function(){return ts;},
      priceScale:function(){return{applyOptions:function(){}};}
    };
  }
};

// ── NETWORK BOUNDARY STUB ──────────────────────────────────────────────────────────────
// One fetch() implementation for the whole suite. It logs every request (instrument,
// granularity, requested count) so a fixture can prove WHICH instruments and WHICH
// timeframes the real sweep actually reached, and delegates the response to whatever
// router the current fixture installed. The real fetchCandles/fetchCandlesRange/fetchPrice
// parse these responses -- they are never replaced.
let fetchRouter=null;
const fetchLog=[];
globalThis.fetch=async function(url){
  const u=String(url);
  const cm=u.match(/instruments\/([^/]+)\/candles\?count=(\d+)&granularity=([A-Za-z0-9]+)/);
  // §18.26: fetchCandlesAroundWindow builds a DIFFERENT url shape --
  // `?granularity=X&price=M&count=5000&from=...` -- so the regex above never matched it and the
  // router was handed a null context. That is why the real overlay draw path
  // (focusTradeOnChart -> focusChartOnTradeWindow -> drawTradeOverlay) could not be driven, and
  // why deleting either overlay call site killed nothing.
  const wm=u.match(/instruments\/([^/]+)\/candles\?granularity=([A-Za-z0-9]+)&price=M&count=(\d+)&from=([^&]+)/);
  if(cm) fetchLog.push({kind:'candles',instrument:cm[1],count:parseInt(cm[2],10),granularity:cm[3],paged:/&to=/.test(u)});
  // §18.32: the WINDOWED shape (granularity&price=M&count&from) was matched for routing but never
  // RECORDED, so fetchCandlesAroundWindow's paging was invisible to any fixture reading the log.
  // A fixture asserting on those requests saw an empty list, where `every` is vacuously true.
  if(!cm&&wm) fetchLog.push({kind:'candles',instrument:wm[1],count:parseInt(wm[3],10),granularity:wm[2],windowed:true,from:decodeURIComponent(wm[4])});
  const pm=u.match(/pricing\?instruments=([^&]+)/);
  if(pm) fetchLog.push({kind:'pricing',instrument:pm[1]});
  const ctx = cm?{instrument:cm[1],count:parseInt(cm[2],10),granularity:cm[3],paged:/&to=/.test(u)}
          : (wm?{instrument:wm[1],granularity:wm[2],count:parseInt(wm[3],10),from:decodeURIComponent(wm[4]),windowed:true}:null);
  if(fetchRouter){ const r=await fetchRouter(u,ctx); if(r) return r; }
  return{ok:false,status:503,json:async function(){return{};}};
};

const g={};
g.chartRec=chartRec;
g.resetChartRec=resetChartRec;
g.setFetchRouter=function(fn){fetchRouter=fn;};
g.fetchLog=function(){return fetchLog.slice();};
g.clearFetchLog=function(){fetchLog.length=0;};
// OANDA candle response shape, built from plain {t,o,h,l,c} objects.
g.oandaCandles=function(arr){
  return{ok:true,status:200,json:async function(){return{candles:arr.map(function(c){
    return{time:c.t.toISOString(),complete:true,mid:{o:String(c.o),h:String(c.h),l:String(c.l),c:String(c.c)}};
  })};}};
};
// §18.32: a page in which the LAST bar is still forming. fetchCandlesAroundWindow filters on
// c.complete, and removing that filter let a forming bar into the drawn chart series with nothing
// objecting -- so the fixture needs a way to serve one.
g.oandaCandlesWithForming=function(arr){
  return{ok:true,status:200,json:async function(){return{candles:arr.map(function(c,i){
    return{time:c.t.toISOString(),complete:i<arr.length-1,mid:{o:String(c.o),h:String(c.h),l:String(c.l),c:String(c.c)}};
  })};}};
};
// §18.32: a MONDAY clock. evaluateLiveTrigger's first line is
// `if(!isPreferredTradingDay()) return ...`, which reads the real clock -- so any fixture driving it
// through loadChart silently does nothing from Thursday to Sunday and would be green for the wrong
// reason on those days. Freezing removes the weekday dependence entirely.
const __RealDate=Date, __realNow=Date.now;
g.freezeClock=function(ms){
  Date.now=function(){return ms;};
  const F=function(){ return arguments.length===0?new __RealDate(ms):new __RealDate(...arguments); };
  F.now=function(){return ms;}; F.parse=__RealDate.parse; F.UTC=__RealDate.UTC; F.prototype=__RealDate.prototype;
  globalThis.Date=F;
};
g.restoreClock=function(){ globalThis.Date=__RealDate; Date.now=__realNow; };
g.oandaPrice=function(bid,ask){
  return{ok:true,status:200,json:async function(){return{prices:[{bids:[{price:String(bid)}],asks:[{price:String(ask)}]}]};}};
};

const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // ── the REAL functions under test. Every one either draws on the chart, writes into the
  //    DOM, or is the genuine outer sweep boundary. ──
  'g.loadChart=loadChart;' +
  'g.drawTradeOverlay=drawTradeOverlay;' +
  'g.focusTradeOnChart=focusTradeOnChart;' +
  // §18.31 PD-3: the INNER function, so a fixture can put the operator's pair click exactly where
  // it lands in production -- after this function's own fetch has begun. Driving the outer
  // focusTradeOnChart instead is useless, because it assigns activePair itself before calling this.
  'g.focusChartOnTradeWindow=focusChartOnTradeWindow;' +
  'g.setJournalEntries=function(v){journalEntries=v;};' +
  'g.clearTradeOverlay=clearTradeOverlay;' +
  'g.renderAlexGLiveSetupsPanel=renderAlexGLiveSetupsPanel;' +
  'g.renderAlexGDashboard=renderAlexGDashboard;' +
  'g.drawTjrZoneOverlay=drawTjrZoneOverlay;' +
  'g.scanAll=scanAll;' +
  'g.alexGLivePollTick=alexGLivePollTick;' +
  'g.alexGEvaluatePairForLiveSetups=alexGEvaluatePairForLiveSetups;' +
  'g.runAlexGReplay=runAlexGReplay;' +
  // ── DOM read-back ──
  'g.elHtml=function(id){ var e=document.getElementById(id); return e?String(e.innerHTML||""):null; };' +
  'g.elText=function(id){ var e=document.getElementById(id); return e?String(e.textContent||""):null; };' +
  'g.elStyle=function(id,k){ var e=document.getElementById(id); return e&&e.style?e.style[k]:null; };' +
  'g.clearEl=function(id){ var e=document.getElementById(id); if(e){e.innerHTML="";e.textContent="";} };' +
  // ── configured universes (read-only, so a fixture can assert coverage against the real list) ──
  'g.allPairs=function(){ return ALL_PAIRS.slice(); };' +
  'g.scanPairsList=function(){ return SCAN_PAIRS.slice(); };' +
  // ── state set/reset ──
  'g.setCfg=function(){ cfg.key="fixture"; cfg.accountId="acct"; cfg.env="practice"; };' +
  'g.setActivePair=function(p){ activePair=p; };' +
  'g.setActiveTf=function(tf){ activeTf=tf; };' +
  'g.getActiveTf=function(){ return activeTf; };' +
  'g.pairDataEntry=function(p){ return pairData[p]; };' +
  'g.setChartEvaluationStateHtml=function(h){ var e=document.getElementById("chartEvaluationState"); if(e) e.innerHTML=h; };' +
  'g.setElHtml=function(id,h){ var e=document.getElementById(id); if(e) e.innerHTML=h; };' +
  'g.alexGSetupDisplayLabel=alexGSetupDisplayLabel;' +
  'g.setPairDataEntry=function(p,v){ if(v===null) delete pairData[p]; else pairData[p]=v; };' +
  'g.resetPairData=function(){ pairData={}; };' +
  'g.setPairDataObject=function(o){ pairData=o; };' +
  'g.getPaperEngineErrors=function(){ return paperEngineErrors.slice(); };' +
  'g.resetScanData=function(){ scanData={}; initScan(); };' +
  'g.setChartOverlayToggles=function(v){ chartOverlayToggles=v; };' +
  'g.setFocusedTradeRecord=function(v){ focusedTradeRecord=v; };' +
  'g.setStructuralAOICache=function(v){ structuralAOICache=v; };' +
  // §18.31: the in-flight map is a SECOND cache and it was never reset. getStructuralAOI returns
  // structuralAOIInflight[pair] before issuing any request, so a promise left behind by an earlier
  // fixture silently served later ones -- and a fixture asserting on the AOI REQUEST saw no request
  // at all. Adding a field to the reset and adding it to the snapshot are one change, not two;
  // the same is true of a cache and its in-flight lock.
  'g.clearStructuralAOIInflight=function(){ structuralAOIInflight={}; };' +
  'g.setAutoTradingEnabled=function(v){ autoTrading.enabled=v; };' +
  'g.setAlexGLiveSetupStatuses=function(v){ alexGLiveSetupStatuses=v; };' +
  'g.getAlexGLiveSetupStatuses=function(){ return alexGLiveSetupStatuses.slice(); };' +
  'g.setAlexGAutoTrading=function(v){ alexGAutoTrading=v; };' +
  'g.setAlexGZoneState=function(v){ alexGZoneState=v; };' +
  'g.setAlexGSetupState=function(v){ alexGSetupState=v; };' +
  'g.getAlexGSetupState=function(){ return alexGSetupState; };' +
  'g.setAlexGLastEvaluatedCloseTime=function(v){ alexGLastEvaluatedCloseTime=v; };' +
  'g.getAlexGLastEvaluatedCloseTime=function(){ return alexGLastEvaluatedCloseTime; };' +
  'g.setAlexGAccount=function(v){ alexGAccount=v; };' +
  'g.setAlexGJournalEntries=function(v){ alexGJournalEntries=v; };' +
  'g.resetFiredAlerts=function(){ firedAlerts=new Set(); };' +
  'g.clearLocalStorage=function(){ localStorage.__clear(); };' +
  'g.clearDecisionEvents=function(){ try{ clearDecisionEvents(); }catch(e){} };' +
  'g.zoneCountsFor=function(p){ var z=alexGZoneState[p]; return z?{H1:z.H1.validatedZones.length,H4:z.H4.validatedZones.length,D:z.D.validatedZones.length,W:z.W.validatedZones.length}:null; };' +
  'return runChartAoiFidelityFixtures(g);'
);
const resultsPromise = wrapped(g);
Promise.resolve(resultsPromise).then(function(results){
  results.forEach(function(r){
    const tag = r.pass===null ? 'NOTE' : (r.pass?'PASS':'FAIL');
    console.log(tag+' -- '+r.name+': '+r.desc+(r.detail?' ['+r.detail+']':''));
  });
  const executed=results.filter(function(r){return r.pass!==null;});
  const failCount=executed.filter(function(r){return !r.pass;}).length;
  const noteCount=results.length-executed.length;
  console.log('---');
  console.log(failCount===0
    ?('ALL CHART / AOI FIDELITY FIXTURES PASSED ('+executed.length+' executed, '+noteCount+' disclosed notes)')
    :('FAILURES: '+failCount+'/'+executed.length+' executed ('+noteCount+' disclosed notes)'));
}).catch(function(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
});
}catch(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
}
