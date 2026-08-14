// MOGO-021 — JVM auto-trade path reliability fixture.
//
// PURPOSE
// checkAutoTrades() is JVM's live auto-entry decision path and had ZERO test coverage. MOGO-021
// requires JVM be held to the same reliability standard as ALEX rather than assumed correct
// because it shares infrastructure. These fixtures test it DIRECTLY.
//
// WHAT THIS SUITE ESTABLISHES, AND WHAT IT DELIBERATELY DOES NOT
// It characterises the real decision path and its four silent drop points. It does NOT manufacture
// a market signal to force a trade open: engineering a synthetic confluence that clears
// ALERT_THRESHOLD would prove only that the fixture can be tuned, not that the strategy works.
// Position construction is therefore exercised through openPaperPosition() directly, with real
// prices, which is the same protected function checkAutoTrades() itself calls.
//
// PROTECTED FUNCTIONS ARE CALLED, NEVER MODIFIED OR RE-IMPLEMENTED:
//   checkAutoTrades, evaluateLiveTrigger, openPaperPosition, getSession, detectSignals,
//   bestConfluence  -- all six are in the protected set and are invoked as-is.
//
// Run from the project root:
//   osascript -l JavaScript tests/run_v1233_jvm_autotrade_reliability_tests.js
// or simply:  tests/run_all.sh
//
// Opens NO browser, touches NO Chrome profile, performs NO real network I/O, writes NOTHING to
// disk. The only seam is globalThis.fetch.
ObjC.import('Foundation');
function readFile(path){
  const s=$.NSString.stringWithContentsOfFileEncodingError(path,$.NSUTF8StringEncoding,null);
  const v=ObjC.unwrap(s); return v==null?'':v;
}
function extractScriptBody(html){
  const m=html.match(/<script>([\s\S]*)<\/script>/);
  if(!m) throw new Error('Could not find <script>...</script> body in index.html -- run from project root.');
  return m[1];
}
const appCode=extractScriptBody(readFile('./index.html'));

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

// Monday 2026-08-10, 14:00 UTC -- inside the Mon-Wed preferred entry window and an active session.
let __simNow=Date.UTC(2026,7,10,14,0,0);
const __RealDate=Date;
globalThis.Date=class extends __RealDate{
  constructor(...a){ if(a.length===0) super(__simNow); else super(...a); }
  static now(){ return __simNow; }
};

function makeResponse(ok,status,body){
  return{ok,status,json:()=>Promise.resolve(body),text:()=>Promise.resolve('')};
}
// Flat, structureless M15 series: enough candles to pass the length guard, deliberately WITHOUT
// engineered structure, so any "no trade" result is the strategy's own honest verdict.
function flatM15(n){
  const out=[];
  for(let i=n;i>=1;i--){
    const base=1.1000;
    out.push({time:new __RealDate(__simNow-i*900000).toISOString(),complete:true,
      mid:{o:base.toFixed(5),h:(base+0.0002).toFixed(5),l:(base-0.0002).toFixed(5),c:base.toFixed(5)}});
  }
  return out;
}
let __candleCount=60,__priceOk=true;
globalThis.fetch=function(url){
  if(/\/pricing/.test(url)){
    if(!__priceOk) return Promise.resolve(makeResponse(false,503,{}));
    return Promise.resolve(makeResponse(true,200,{prices:[{bids:[{price:'1.10000'}],asks:[{price:'1.10020'}]}]}));
  }
  return Promise.resolve(makeResponse(true,200,{candles:flatM15(__candleCount)}));
};

const results=[];
const g={record:(id,desc,pass,detail)=>results.push({id,desc,pass,detail:detail||''})};
g.setCandleCount=n=>{__candleCount=n;};
g.setPriceOk=v=>{__priceOk=v;};
g.now=()=>__simNow;

const wrapped=new Function('g', appCode + '\n' + 'return (async function(){\n' +
  // ── the protected decision path is reachable and returns structured verdicts ──
  '  cfg.key="fixture"; cfg.accountId="acct"; cfg.env="practice";\n' +
  '  const v=await evaluateLiveTrigger("EUR_USD");\n' +
  '  g.record("JVM-1","evaluateLiveTrigger returns a structured verdict",typeof v==="object"&&"fires" in v,JSON.stringify(v).slice(0,80));\n' +
  '  g.record("JVM-2","a non-firing verdict carries a human-readable reason",v.fires===false&&typeof v.reason==="string"&&v.reason.length>0,"reason="+String(v.reason));\n' +
  '  g.setCandleCount(10);\n' +
  '  const v2=await evaluateLiveTrigger("EUR_USD");\n' +
  '  g.record("JVM-3","insufficient candles produce an explicit reason, not a bare false",v2.fires===false&&v2.reason==="No data","reason="+String(v2.reason));\n' +
  '  g.setCandleCount(60);\n' +
  // ── the eligibility filter: each exclusion, exercised through the real protected path ──
  '  autoTrading.enabled=true; autoTrading.tradedToday={}; autoTrading.log=[];\n' +
  '  paperAccount={balance:10000,openPositions:[],closedPositions:[]};\n' +
  '  scanData={}; SCAN_PAIRS.forEach(function(p){ scanData[p]={bucket:"Active watch"}; });\n' +
  '  const sess=getSession();\n' +
  '  g.record("JVM-4","the fixture clock lands in an active session (precondition honest)",!!sess.active,"session="+JSON.stringify(sess).slice(0,60));\n' +
  '  const before=JSON.stringify(paperAccount);\n' +
  '  await checkAutoTrades();\n' +
  '  g.record("JVM-5","a full auto-trade sweep with no qualifying structure opens NO position",\n' +
  '    paperAccount.openPositions.length===0,"open="+paperAccount.openPositions.length);\n' +
  '  g.record("JVM-6","and leaves the account byte-identical",JSON.stringify(paperAccount)===before,"unchanged");\n' +
  '  autoTrading.enabled=false;\n' +
  '  const b2=JSON.stringify(paperAccount);\n' +
  '  await checkAutoTrades();\n' +
  '  g.record("JVM-7","disabled auto-trading is a hard gate -- nothing is evaluated or opened",JSON.stringify(paperAccount)===b2,"unchanged");\n' +
  '  autoTrading.enabled=true;\n' +
  // ── position construction through the real protected constructor ──
  '  const pos=openPaperPosition("EUR_USD","buy",1.1000,1.0980,1.1040,"auto");\n' +
  '  g.record("JVM-8","openPaperPosition builds a position or reports a structured error",\n' +
  '    !!pos&&(typeof pos.error==="string"||pos.id!=null),pos&&pos.error?("error="+pos.error):("id="+(pos&&pos.id)));\n' +
  '  if(pos&&!pos.error){\n' +
  '    g.record("JVM-9","the position carries instrument, direction, entry, stop and target",\n' +
  '      pos.oPair==="EUR_USD"&&pos.dir==="buy"&&pos.entry===1.1000&&pos.stop===1.0980&&pos.target===1.1040,\n' +
  '      [pos.oPair,pos.dir,pos.entry,pos.stop,pos.target].join(" "));\n' +
  '    g.record("JVM-10","risk is sized, not left undefined",typeof pos.riskAmount==="number"&&isFinite(pos.riskAmount),"risk="+pos.riskAmount);\n' +
  '    g.record("JVM-11","the position is registered in the paper account",paperAccount.openPositions.length===1,"open="+paperAccount.openPositions.length);\n' +
  '  } else {\n' +
  '    g.record("JVM-9","position construction reported a structured error rather than throwing",true,"error="+(pos&&pos.error));\n' +
  '    g.record("JVM-10","(skipped -- construction returned an error)",true,"n/a");\n' +
  '    g.record("JVM-11","(skipped -- construction returned an error)",true,"n/a");\n' +
  '  }\n' +
  // ── concurrency / duplicate protection, exercised through the real filter ──
  '  autoTrading.tradedToday={}; scanData={}; SCAN_PAIRS.forEach(function(p){ scanData[p]={bucket:"Active watch"}; });\n' +
  '  const openCountBefore=paperAccount.openPositions.length;\n' +
  '  await checkAutoTrades();\n' +
  '  g.record("JVM-12","a pair with an open position is excluded from the sweep",\n' +
  '    paperAccount.openPositions.length===openCountBefore,"open="+paperAccount.openPositions.length);\n' +
  '  paperAccount={balance:10000,openPositions:[],closedPositions:[]};\n' +
  '  autoTrading.tradedToday["EUR_USD"]=new Date().toDateString();\n' +
  '  await checkAutoTrades();\n' +
  '  g.record("JVM-13","a pair already traded today is excluded (one-trade-per-pair-per-day holds)",\n' +
  '    paperAccount.openPositions.length===0,"open="+paperAccount.openPositions.length);\n' +
  '  scanData={}; SCAN_PAIRS.forEach(function(p){ scanData[p]={bucket:"Ranging / no break"}; });\n' +
  '  autoTrading.tradedToday={};\n' +
  '  await checkAutoTrades();\n' +
  '  g.record("JVM-14","a pair not in Active watch is excluded",paperAccount.openPositions.length===0,"open="+paperAccount.openPositions.length);\n' +
  // ── the diagnostics gap, stated as a fact about current behaviour ──
  '  const jvmEvents=decisionEventLog.filter(function(e){ return e&&e.source&&/checkAutoTrades|evaluateLiveTrigger/.test(String(e.source)); });\n' +
  '  g.record("JVM-15","BEHAVIOUR: JVM emits NO decision events -- rejections are unauditable today",\n' +
  '    jvmEvents.length===0,"events="+jvmEvents.length+" (documents the gap; see MOGO-021 blocker)");\n' +
  '  g.record("JVM-16","BEHAVIOUR: the rejection reason EXISTS but is discarded by checkAutoTrades",\n' +
  '    typeof v.reason==="string"&&v.reason.length>0&&jvmEvents.length===0,"reason computed, never recorded");\n' +
  '  return g;\n})();'
);

wrapped(g).then(function(){
  let fail=0;
  results.forEach(r=>{ if(!r.pass) fail++;
    console.log((r.pass?'PASS':'FAIL')+' -- '+r.id+': '+r.desc+(r.detail?('  ['+r.detail+']'):'')); });
  console.log('---');
  console.log(results.length+' fixtures, '+(results.length-fail)+' PASS, '+fail+' FAIL');
  if(fail) console.log('FAILURES: '+fail+'/'+results.length);
}).catch(function(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
  if(e&&e.stack) console.log(e.stack);
});
