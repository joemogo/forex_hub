// MOGO-021 — JVM auto-trade path reliability fixture.
//
// PURPOSE
// checkAutoTrades() is JVM's live auto-entry decision path and had ZERO test coverage. MOGO-021
// requires JVM be held to the same reliability standard as ALEX rather than assumed correct
// because it shares infrastructure. These fixtures test it DIRECTLY.
//
// WHY THIS SUITE NOW CONTAINS A POSITIVE CONTROL (correction to the first version)
// The first version of this suite deliberately refused to construct a firing signal, arguing that
// "engineering a synthetic confluence proves only that the fixture can be tuned." Adversarial
// verification showed that reasoning produced a suite that could not fail: against a flat,
// structureless series NOTHING fires, so every exclusion fixture ("disabled gate", "already has an
// open position", "already traded today", "not in Active watch") asserted openPositions.length===0
// in a world where that count was 0 regardless. Those fixtures would have passed identically had
// the exclusion logic been deleted outright. An exclusion test is only meaningful against a
// baseline that WOULD otherwise fire.
//
// This suite therefore establishes a positive control, under a strict rule:
//     THE CANDLES ARE CONSTRUCTED. THE VERDICT IS NOT.
// No threshold, weight or rule is altered, overridden or stubbed -- ALERT_THRESHOLD, WEIGHTS,
// RULES and every protected function are used exactly as frozen. The fixture supplies a price
// series and reports whatever the strategy decides. The firing series is an ordinary bullish
// setup (3/3 bias, a standard engulfing bar that also breaks structure, a priority session, a
// daily support shelf below with resistance far above); the frozen scorer rates it 65 against its
// own threshold of 55 and returns R:R 3.51:1 of its own accord.
//
// WHAT THE POSITIVE CONTROL DOES AND DOES NOT PROVE
//   DOES prove: the auto-entry path fires end-to-end; each exclusion actually suppresses a trade
//     that would otherwise have opened; position construction and account registration work.
//   DOES NOT prove: that the strategy is profitable, well-calibrated, or that real markets produce
//     this setup at any particular rate. Nothing here is evidence about edge.
//
// PROTECTED FUNCTIONS ARE CALLED, NEVER MODIFIED OR RE-IMPLEMENTED:
//   checkAutoTrades, evaluateLiveTrigger, openPaperPosition, getSession, detectSignals,
//   bestConfluence, scoreConfluence, findAOIs, getScore, getBias -- all invoked as-is.
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
// MOGO-021 TIMER LEAK. The stubs used to be `setInterval=()=>++__t; clearInterval=()=>{}`, which
// hand out ids and forget them -- so a LEAKED timer (one whose handle was overwritten before it was
// cleared) is indistinguishable from a cleared one and no fixture could ever see the leak. The stub
// now keeps a registry of LIVE intervals, keyed by the same id it returns, so "how many hourly
// top-down timers are actually still running?" is answerable. Ids are still `++__t`, so every
// existing fixture sees byte-identical return values; only clearInterval gained an effect. Nothing
// is ever executed -- these are records of live handles, not a scheduler.
const __liveIntervals=new Map();
globalThis.setInterval=function(fn,ms){ const id=++__t; __liveIntervals.set(id,{fn:fn,ms:ms}); return id; };
globalThis.clearInterval=function(id){ if(id!=null) __liveIntervals.delete(id); };
globalThis.ResizeObserver=function(){return{observe(){},disconnect(){}};};
globalThis.LightweightCharts={LineStyle:{Solid:0,Dashed:1,Dotted:2},CrosshairMode:{Normal:0}};
globalThis.Notification=undefined;
globalThis.indexedDB=undefined;

// Monday 2026-08-10, 14:00 UTC -- inside the Mon-Wed preferred entry window and an active
// (priority) London session. Both are the strategy's own gates, not fixture conveniences.
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
// NEGATIVE CONTROL. Flat, structureless M15 series: enough candles to clear the length guard,
// deliberately WITHOUT structure, so any "no trade" outcome is the strategy's own verdict.
function flatM15(n){
  const out=[];
  for(let i=n;i>=1;i--){
    const base=1.1000;
    out.push(mk(__simNow-i*900000,base,base+0.0002,base-0.0002,base));
  }
  return out;
}
// POSITIVE CONTROL, M15. An ordinary bullish continuation: a quiet uptrend, then a standard
// bullish engulfing bar that also takes out the prior high (market-structure break). Nothing here
// targets a score -- it is a textbook setup, and the frozen scorer values it at 65 against its own
// threshold of 55 (bias 25 + engulf 20 + session 10 + MSB 10; AOI and wick both score ZERO).
// n defaults to 60 (what evaluateLiveTrigger requests). scanPair asks for 220, and ADR-011 treats
// a short response as PARTIAL -- deliberately suppressing evaluation -- so the stub must honour the
// requested count or every scanned pair is legitimately reported as suppressed.
function firingM15(n){
  const out=[]; n=n||60;
  for(let i=n;i>=4;i--){
    const base=1.1000+(n-i)*0.00002;
    out.push(mk(__simNow-i*900000,base,base+0.00015,base-0.00015,base+0.00005));
  }
  const t=__simNow;
  out.push(mk(t-3*900000,1.10050,1.10100,1.10000,1.10020)); // prior bar : high 1.10100
  out.push(mk(t-2*900000,1.10180,1.10200,1.10120,1.10140)); // previous  : bearish, high 1.10200
  out.push(mk(t-1*900000,1.10100,1.10320,1.10080,1.10300)); // last      : engulfs it, new high
  return out;
}
// POSITIVE CONTROL, daily/weekly structure for getStructuralAOI(): a support shelf repeatedly
// touched near 1.0990 and resistance far above near 1.1200. The 3-touch requirement in the frozen
// AOI engine is met by genuine repeated touches, not by widening any tolerance.
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
    out.push(mk(__simNow-i*86400000,lo+0.0005,hi,lo,hi-0.0005));
  }
  return out;
}
// MOGO-021 JVM EXIT MATH. The /pricing response used to be a hard-coded symmetric-ish pair. It is
// now settable, DEFAULTING TO THE EXACT PREVIOUS BYTES, so every pre-existing fixture sees an
// identical response and only the new exit-math fixtures ever change it. A close fills at the bid
// (buy) or the ask (sell), so a fixture cannot tell a wrong FILL SIDE from a wrong MID unless
// bid, ask and mid are three distinguishable numbers -- which requires setting them per fixture.
const __BID_DEFAULT='1.10290',__ASK_DEFAULT='1.10310';
let __pbid=__BID_DEFAULT,__pask=__ASK_DEFAULT;
let __candleCount=60,__priceOk=true,__mode='flat',__shortPair=null,__shortAll=false;
// Holds one instrument's candle fetch open so a SECOND scanAll can overtake the first -- the
// overlapping-sweep condition scanAll allows (no re-entrancy guard; called unawaited from
// setInterval, from init, and from setTf() on an operator click).
let __gatePair=null,__gateRelease=null,__failPair=null,__throwPair=null;
// MOGO-021 JVM completeness parity: make ONE granularity short for ONE instrument, so a fixture
// can prove each required timeframe fails closed independently rather than all at once.
let __shortGranPair=null,__shortGranTf=null;
function __gate(){ return new Promise(function(res){ __gateRelease=res; }); }
globalThis.fetch=function(url){
  const u=String(url);
  if(/\/pricing/.test(u)){
    if(!__priceOk) return Promise.resolve(makeResponse(false,503,{}));
    return Promise.resolve(makeResponse(true,200,{prices:[{bids:[{price:__pbid}],asks:[{price:__pask}]}]}));
  }
  if(__mode==='firing'){
    // MOGO-021: this must run BEFORE the D/W early returns below, which short-circuit on
    // granularity alone and would otherwise make a per-granularity short response unreachable.
    if(__shortGranPair&&__shortGranTf){
      const __inst=(u.match(/instruments\/([^/]+)\//)||[])[1];
      const __g=(u.match(/granularity=(\w+)/)||[])[1];
      if(__inst===__shortGranPair&&__g===__shortGranTf){
        // Short by a handful, not to nothing: a truncated-but-usable response is the case that
        // slipped past every guard, and the one a length floor cannot catch.
        const __want=parseInt((u.match(/count=(\d+)/)||[])[1],10)||60;
        if(__g==='D'||__g==='W') return Promise.resolve(makeResponse(true,200,{candles:structuralCandles(Math.max(20,__want-3))}));
        return Promise.resolve(makeResponse(true,200,{candles:firingM15(Math.max(30,__want-3))}));
      }
    }
    if(/granularity=D/.test(u)) return Promise.resolve(makeResponse(true,200,{candles:structuralCandles(120)}));
    if(/granularity=W/.test(u)) return Promise.resolve(makeResponse(true,200,{candles:structuralCandles(60)}));
    const wantN=parseInt((u.match(/count=(\d+)/)||[])[1],10)||60;
    const instMatch=(u.match(/instruments\/([^/]+)\//)||[])[1];
    if(__gatePair&&instMatch===__gatePair){
      const held=__gate();
      return held.then(function(){ return makeResponse(true,200,{candles:firingM15(wantN)}); });
    }
    // One instrument can be made to return a SHORT history, which ADR-011 classifies as PARTIAL
    // and deliberately suppresses from evaluation -- the state JVMOBS-10 asserts is reported.
    // A hard transport failure for one instrument: fetchCandles returns null, so completeness is
    // UNAVAILABLE rather than PARTIAL -- a different fact from an ADR-011 suppression.
    if(__failPair&&instMatch===__failPair) return Promise.resolve(makeResponse(false,503,{}));
    // A REJECTED fetch, not merely a non-OK response: the instrument is dispatched but its scanPair
    // never reaches the write, so this sweep holds no result for it at all. That is the only way to
    // reach DISPATCHED_NO_RESULT, which shipped with zero coverage.
    if(__throwPair&&instMatch===__throwPair) return Promise.reject(new Error('forced transport throw'));
    if(__shortAll||(__shortPair&&instMatch===__shortPair)) return Promise.resolve(makeResponse(true,200,{candles:firingM15(20)}));
    return Promise.resolve(makeResponse(true,200,{candles:firingM15(wantN)}));
  }
  return Promise.resolve(makeResponse(true,200,{candles:flatM15(__candleCount)}));
};

const results=[];
const g={record:(id,desc,pass,detail)=>results.push({id,desc,pass,detail:detail||''})};
g.setCandleCount=n=>{__candleCount=n;};
g.setPriceOk=v=>{__priceOk=v;};
g.setBidAsk=(b,a)=>{__pbid=String(b);__pask=String(a);};
g.resetBidAsk=()=>{__pbid=__BID_DEFAULT;__pask=__ASK_DEFAULT;};
g.setMode=m=>{__mode=m;};
g.setShortPair=p=>{__shortPair=p;};
g.setShortAll=v=>{__shortAll=v;};
g.holdPair=p=>{__gatePair=p;};
g.failPair=p=>{__failPair=p;};
g.throwPair=p=>{__throwPair=p;};
g.setShortGran=(p,tf)=>{__shortGranPair=p;__shortGranTf=tf;};
g.releaseHeld=()=>{__gatePair=null; if(__gateRelease){__gateRelease(); __gateRelease=null;}};
// How many LIVE intervals are currently registered against this exact callback. Identity, not the
// period, is the test: counting `ms===3600000` would also count any other hourly timer and would
// still pass if the hourly handle were stranded and a second one created against a different fn.
g.liveTimersFor=fn=>{ let n=0; __liveIntervals.forEach(v=>{ if(v.fn===fn) n++; }); return n; };
// §18.23: the PERIOD, not just the handle count. Deleting either 60-second scanner timer, or
// changing its period, previously killed nothing anywhere in the gate.
g.liveTimerMsFor=fn=>{ let ms=null; __liveIntervals.forEach(v=>{ if(v.fn===fn) ms=v.ms; }); return ms; };
g.liveTimerIds=()=>Array.from(__liveIntervals.keys());
g.setNow=t=>{__simNow=t;};
g.now=()=>__simNow;
g.utc=(y,mo,d,h)=>__RealDate.UTC(y,mo,d,h,0,0);

const wrapped=new Function('g', appCode + '\n' + 'return (async function(){\n' +
  // ══ the protected decision path is reachable and returns structured verdicts ══
  '  cfg.key="fixture"; cfg.accountId="acct"; cfg.env="practice";\n' +
  '  const v=await evaluateLiveTrigger("EUR_USD");\n' +
  '  g.record("JVM-1","evaluateLiveTrigger returns a structured verdict",typeof v==="object"&&"fires" in v,JSON.stringify(v).slice(0,80));\n' +
  '  g.record("JVM-2","a non-firing verdict carries a human-readable reason",v.fires===false&&typeof v.reason==="string"&&v.reason.length>0,"reason="+String(v.reason));\n' +
  '  g.setCandleCount(10);\n' +
  '  const v2=await evaluateLiveTrigger("EUR_USD");\n' +
  '  g.record("JVM-3","insufficient candles produce an explicit reason, not a bare false",v2.fires===false&&v2.reason==="No data","reason="+String(v2.reason));\n' +
  '  g.setCandleCount(60);\n' +
  // ══ NEGATIVE CONTROL ══
  '  autoTrading.enabled=true; autoTrading.tradedToday={}; autoTrading.log=[]; autoTrading._lastDay=null;\n' +
  '  paperAccount={balance:10000,openPositions:[],closedPositions:[]};\n' +
  '  scanData={}; SCAN_PAIRS.forEach(function(p){ scanData[p]={weekly:"Bullish",daily:"Bullish",fh:"Bullish",bucket:"Active watch"}; });\n' +
  '  const sess=getSession();\n' +
  '  g.record("JVM-4","the fixture clock lands in an active session (precondition honest)",!!sess.active,"session="+String(sess.name));\n' +
  '  const before=JSON.stringify(paperAccount);\n' +
  '  await checkAutoTrades();\n' +
  '  g.record("JVM-5","NEGATIVE CONTROL: a sweep with no qualifying structure opens NO position",\n' +
  '    paperAccount.openPositions.length===0,"open="+paperAccount.openPositions.length);\n' +
  '  g.record("JVM-6","and leaves the account byte-identical",JSON.stringify(paperAccount)===before,"unchanged");\n' +
  // ══ POSITIVE CONTROL: the frozen strategy fires on its own ══
  '  g.setMode("firing"); structuralAOICache={};\n' +
  '  const c=await fetchCandles("EUR_USD","M15",60);\n' +
  '  const conf=bestConfluence(c,"EUR_USD");\n' +
  '  g.record("JVM-7","POSITIVE CONTROL: the FROZEN scorer rates the setup at or above its OWN threshold",\n' +
  '    conf.total>=ALERT_THRESHOLD,"confluence="+conf.total+" vs ALERT_THRESHOLD="+ALERT_THRESHOLD+" dir="+conf.direction);\n' +
  '  g.record("JVM-8","the score is earned across several components, not one dominant term",\n' +
  '    conf.items.filter(function(i){return i.pts>0;}).length>=3,\n' +
  '    conf.items.map(function(i){return i.label+":"+i.pts;}).join(", "));\n' +
  '  const vf=await evaluateLiveTrigger("EUR_USD");\n' +
  '  g.record("JVM-9","evaluateLiveTrigger FIRES, clearing every gate it applies, of its own accord",\n' +
  '    vf.fires===true,JSON.stringify(vf));\n' +
  '  g.record("JVM-10","the fired verdict carries direction, entry, stop, target and an R:R the strategy itself accepted",\n' +
  '    vf.dir==="buy"&&typeof vf.entry==="number"&&typeof vf.stop==="number"&&typeof vf.target==="number"&&vf.ratio>=1.99,\n' +
  '    "entry="+vf.entry+" stop="+vf.stop+" target="+vf.target+" R:R="+(vf.ratio&&vf.ratio.toFixed(2)));\n' +
  '  g.record("JVM-11","stop sits below entry and target above it for a long -- the trade is coherent",\n' +
  '    vf.stop<vf.entry&&vf.target>vf.entry,"stop<entry<target");\n' +
  // ══ END-TO-END ══
  '  function resetFiring(){ autoTrading.enabled=true; autoTrading.tradedToday={}; autoTrading.log=[]; autoTrading._lastDay=null;\n' +
  '    paperAccount={balance:10000,openPositions:[],closedPositions:[]};\n' +
  '    scanData={}; SCAN_PAIRS.forEach(function(p){ scanData[p]={weekly:"Bullish",daily:"Bullish",fh:"Bullish",bucket:"Active watch"}; }); }\n' +
  '  resetFiring();\n' +
  '  await checkAutoTrades();\n' +
  '  const openedBaseline=paperAccount.openPositions.length;\n' +
  '  g.record("JVM-12","END-TO-END: checkAutoTrades OPENS a paper position from a firing signal",\n' +
  '    openedBaseline>0,"opened="+openedBaseline+" pairs="+paperAccount.openPositions.map(function(p){return p.oPair;}).join(","));\n' +
  '  const p0=paperAccount.openPositions[0]||{};\n' +
  '  const target1=p0.oPair;\n' +
  '  g.record("JVM-13","the opened position carries instrument, direction, entry, stop and target",\n' +
  '    typeof p0.oPair==="string"&&p0.dir==="buy"&&typeof p0.entry==="number"&&typeof p0.stop==="number"&&typeof p0.target==="number",\n' +
  '    [p0.oPair,p0.dir,p0.entry,p0.stop,p0.target].join(" "));\n' +
  '  g.record("JVM-14","risk is sized, not left undefined",typeof p0.riskAmount==="number"&&isFinite(p0.riskAmount)&&p0.riskAmount>0,"risk="+p0.riskAmount);\n' +
  '  g.record("JVM-15","the trade is journalled with its confluence and marked traded-today",\n' +
  '    autoTrading.log.length===openedBaseline&&autoTrading.log.length>0&&\n' +
  '    autoTrading.log[0].confluence>=ALERT_THRESHOLD&&!!autoTrading.tradedToday[target1],\n' +
  '    "log="+autoTrading.log.length+" conf="+((autoTrading.log[0]||{}).confluence));\n' +
  '  g.record("JVM-16","the position is tagged auto-sourced, distinguishable from a manual trade",\n' +
  '    p0.source==="auto","source="+String(p0.source));\n' +
  // ══ EXCLUSIONS, each re-asserted AGAINST the firing baseline ══
  '  resetFiring(); autoTrading.enabled=false;\n' +
  '  await checkAutoTrades();\n' +
  '  g.record("JVM-17","EXCLUSION: disabled auto-trading suppresses a trade that WOULD otherwise open",\n' +
  '    paperAccount.openPositions.length===0&&openedBaseline>0,"opened="+paperAccount.openPositions.length+" vs baseline "+openedBaseline);\n' +
  '  resetFiring();\n' +
  '  SCAN_PAIRS.forEach(function(p){ scanData[p].bucket="Ranging / no break"; });\n' +
  '  await checkAutoTrades();\n' +
  '  g.record("JVM-18","EXCLUSION: a pair not in Active watch is skipped despite a firing signal",\n' +
  '    paperAccount.openPositions.length===0&&openedBaseline>0,"opened="+paperAccount.openPositions.length+" vs baseline "+openedBaseline);\n' +
  '  resetFiring();\n' +
  '  autoTrading.tradedToday[target1]=new Date().toDateString(); autoTrading._lastDay=new Date().toDateString();\n' +
  '  await checkAutoTrades();\n' +
  '  const tradedAgain=paperAccount.openPositions.some(function(p){return p.oPair===target1;});\n' +
  '  g.record("JVM-19","EXCLUSION: already-traded-today blocks THAT pair while the others still fire",\n' +
  '    tradedAgain===false&&paperAccount.openPositions.length===openedBaseline-1,\n' +
  '    target1+(tradedAgain?" NOT blocked":" blocked")+"; opened="+paperAccount.openPositions.length+" of baseline "+openedBaseline);\n' +
  '  resetFiring();\n' +
  '  paperAccount.openPositions.push({oPair:target1,dir:"buy",entry:1.1,stop:1.09,target:1.12,id:"pre-existing"});\n' +
  '  await checkAutoTrades();\n' +
  '  const dupes=paperAccount.openPositions.filter(function(p){return p.oPair===target1;}).length;\n' +
  '  g.record("JVM-20","EXCLUSION: an existing open position prevents a SECOND position on that pair",\n' +
  '    dupes===1,target1+" positions="+dupes);\n' +
  '  const savedNow=g.now();\n' +
  '  resetFiring();\n' +
  '  g.setNow(g.utc(2026,7,10,3)); structuralAOICache={};\n' +
  '  await checkAutoTrades();\n' +
  '  g.record("JVM-21","EXCLUSION: an inactive session suppresses the trade",\n' +
  '    paperAccount.openPositions.length===0&&!getSession().active,"session="+String(getSession().name)+" active="+getSession().active);\n' +
  '  resetFiring();\n' +
  '  g.setNow(g.utc(2026,7,13,14)); structuralAOICache={};\n' +
  '  const vThu=await evaluateLiveTrigger("EUR_USD");\n' +
  '  await checkAutoTrades();\n' +
  '  g.record("JVM-22","EXCLUSION: outside the Mon-Wed window nothing opens, and the reason says so",\n' +
  '    vThu.fires===false&&/Mon-Wed/.test(String(vThu.reason))&&paperAccount.openPositions.length===0,"reason="+String(vThu.reason));\n' +
  '  g.setNow(savedNow); structuralAOICache={};\n' +
  // ══ SILENT DROP POINTS ══
  // The MECHANISM is real production code; the RATE this fixture shows is not. pipValuePerLot()
  // needs pairData[USD_<quote>].price for any non-USD-quoted pair, and pairData is populated only
  // by scanPair(). Calling checkAutoTrades() directly -- as every fixture above does -- leaves
  // pairData empty, so every non-USD-quoted pair fails to size. JVM-25 below runs the REAL
  // production entry point and shows the difference, so this is not mistaken for a production rate.
  '  resetFiring(); pairData={};\n' +
  '  const conv=await evaluateLiveTrigger("USD_CAD");\n' +
  '  const convPos=openPaperPosition("USD_CAD",conv.dir,conv.entry,conv.stop,conv.target,"auto");\n' +
  '  g.record("JVM-23","DROP POINT: with no conversion rate loaded, a FIRING signal is rejected by openPaperPosition",\n' +
  '    conv.fires===true&&!!convPos.error,"fires="+conv.fires+" error="+String(convPos.error).slice(0,58));\n' +
  '  resetFiring(); pairData={};\n' +
  '  await checkAutoTrades();\n' +
  '  const directOpened=paperAccount.openPositions.length;\n' +
  '  const droppedPairs=SCAN_PAIRS.map(function(p){return p.replace("/","_");})\n' +
  '    .filter(function(op){ return !paperAccount.openPositions.some(function(p){return p.oPair===op;}); });\n' +
  '  g.record("JVM-24","DROP POINT: a rejected trade leaves NO trace -- no journal entry, no traded-today mark",\n' +
  '    droppedPairs.length>0&&autoTrading.log.length===directOpened&&\n' +
  '    droppedPairs.every(function(op){ return !autoTrading.tradedToday[op]; }),\n' +
  '    "dropped="+droppedPairs.length+" of "+SCAN_PAIRS.length+", journal entries="+autoTrading.log.length);\n' +
  // The production contrast: scanAll() populates pairData for ALL_PAIRS BEFORE calling
  // checkAutoTrades, so conversion rates ARE available on a real sweep.
  '  resetFiring(); pairData={}; firedAlerts=new Set(); clearDecisionEvents();\n' +
  '  await scanAll();\n' +
  '  const viaScanAll=paperAccount.openPositions.length;\n' +
  '  g.record("JVM-25","HONESTY CHECK: through the REAL entry point scanAll(), which loads prices first, MORE pairs open",\n' +
  '    viaScanAll>directOpened,"scanAll="+viaScanAll+" vs direct checkAutoTrades="+directOpened+\n' +
  '    " -- the conversion drops above are a fixture artifact, not a production rate");\n' +
  '  const remaining=SCAN_PAIRS.map(function(p){return p.replace("/","_");})\n' +
  '    .filter(function(op){ return !paperAccount.openPositions.some(function(p){return p.oPair===op;}); });\n' +
  '  const rrDeclines=[];\n' +
  '  for(const op of remaining){ const vv=await evaluateLiveTrigger(op); if(!vv.fires) rrDeclines.push(op+":"+vv.reason); }\n' +
  '  g.record("JVM-26","and the pairs still not traded are declined by the STRATEGY, with its own stated reason",\n' +
  '    rrDeclines.length===remaining.length,rrDeclines.join(", ").slice(0,110));\n' +
  // ══ auditability, stated accurately: scan-level events exist, candidate-level ones do not ══
  '  const types={}; decisionEventLog.forEach(function(e){ types[e.eventType]=(types[e.eventType]||0)+1; });\n' +
  '  const CANDIDATE_LEVEL=["CANDIDATE_CREATED","CANDIDATE_APPROVED","CANDIDATE_REJECTED","RULE_EVALUATED",\n' +
  '    "TRADE_OPEN_REQUESTED","TRADE_OPENED","TRADE_OPEN_FAILED"];\n' +
  // MOGO-021 DECISION 4 -- INVERTED, DELIBERATELY. This fixture asserted the auditability GAP: that a
  // real JVM sweep emitted scan-level events and NOT ONE candidate-level event. The owner authorized
  // closing that gap, so the fixture now asserts the contract instead of the defect. It is the proof
  // the diagnostic landed, and it fails again the moment the diagnostic is removed.
  '  g.record("JVM-27","a real JVM sweep now emits CANDIDATE-level rejections alongside its scan-level events",\n' +
  '    (types.SCAN_STARTED||0)>0&&(types.SCAN_COMPLETED||0)>0&&(types.CANDIDATE_REJECTED||0)>0&&viaScanAll>0,\n' +
  '    "eventTypes="+JSON.stringify(types)+" while "+viaScanAll+" positions opened");\n' +
  // Strategy-sourced events only. The evidence platform emits its own DATA_UNAVAILABLE events when
  // the observation store is unreachable (IndexedDB is absent in this harness), and those are
  // infrastructure, not the JVM decision path -- including them would make this assertion about
  // storage availability rather than about what JVM reports.
  '  const stratEvents=decisionEventLog.filter(function(e){ return String(e.source||"")!=="evidence-platform"; });\n' +
  '  g.record("JVM-28","the DECISION PATH now reports itself -- events are sourced to checkAutoTrades, not only scanAll",\n' +
  '    stratEvents.length>0&&stratEvents.some(function(e){ return e.source==="checkAutoTrades"; })&&\n' +
  '    stratEvents.every(function(e){ return e.source==="scanAll"||e.source==="checkAutoTrades"; }),\n' +
  '    "strategy sources="+JSON.stringify(Object.keys(stratEvents.reduce(function(a,e){a[e.source]=1;return a;},{})))+\n' +
  '    "; all sources="+JSON.stringify(Object.keys(decisionEventLog.reduce(function(a,e){a[e.source]=1;return a;},{}))));\n' +
  // the discarded reason, with the discard itself asserted
  '  g.setMode("flat"); structuralAOICache={}; resetFiring(); pairData={}; clearDecisionEvents();\n' +
  '  const vrej=await evaluateLiveTrigger("EUR_USD");\n' +
  '  await checkAutoTrades();\n' +
  '  const rejEvents=decisionEventLog.filter(function(e){ return e.eventType==="CANDIDATE_REJECTED"&&e.source==="checkAutoTrades"; });\n' +
  '  g.record("JVM-29","the rejection reason computed at the source is now RECORDED VERBATIM, and no trade is taken",\n' +
  '    vrej.fires===false&&typeof vrej.reason==="string"&&vrej.reason.length>0&&\n' +
  '    rejEvents.length>0&&rejEvents.every(function(e){ return e.reasonText===vrej.reason; })&&\n' +
  '    autoTrading.log.length===0&&Object.keys(autoTrading.tradedToday).length===0,\n' +
  '    "computed ["+String(vrej.reason)+"] recorded on "+rejEvents.length+" event(s) as ["+String((rejEvents[0]||{}).reasonText)+"]"+\n' +
  '    " -- still journal=0, tradedToday=0");\n' +
  // The reason CODE must correspond to the reason the strategy actually returned -- a diagnostic
  // that reports a plausible-but-wrong code is worse than none. Every code below already existed in
  // the registry; none was invented for this change.
  '  g.record("JVM-30","the recorded reason CODE corresponds to the actual computation, not a fixed placeholder",\n' +
  '    jvmLiveTriggerReasonCode("Confluence below threshold")==="CONFLUENCE_BELOW_THRESHOLD"&&\n' +
  '    jvmLiveTriggerReasonCode("R:R only 1.42:1")==="ENTRY_RATIO_BELOW_MINIMUM"&&\n' +
  '    jvmLiveTriggerReasonCode("Outside Mon-Wed preferred entry window")==="SESSION_OUTSIDE_PREFERRED_DAY"&&\n' +
  '    jvmLiveTriggerReasonCode("No engulfing trigger yet")==="ENTRY_SIGNAL_NOT_PRESENT"&&\n' +
  '    jvmLiveTriggerReasonCode("No valid support AOI")==="STRUCTURE_AOI_NOT_VALIDATED"&&\n' +
  '    jvmLiveTriggerReasonCode("No valid resistance AOI")==="STRUCTURE_AOI_NOT_VALIDATED"&&\n' +
  '    jvmLiveTriggerReasonCode("Invalid stop distance")==="RISK_ZERO_STOP_DISTANCE"&&\n' +
  '    jvmLiveTriggerReasonCode("No data")==="DATA_CANDLES_UNAVAILABLE"&&\n' +
  '    jvmLiveTriggerReasonCode("something nobody mapped")==="UNKNOWN_NOT_RECORDED",\n' +
  '    "all eight real reasons map to a distinct pre-existing registry code; an unknown reason is not fabricated");\n' +
  '  g.record("JVM-31","every recorded reason code is REGISTERED -- the diagnostic cannot emit an unknown code",\n' +
  '    rejEvents.every(function(e){ return !!REASON_CODE_REGISTRY[e.reasonCode]; }),\n' +
  '    "codes="+JSON.stringify(rejEvents.map(function(e){return e.reasonCode;})));\n' +
  // ══ MOGO-021 §17.4: the completeness contract is now ENFORCED, not merely commented ══
  // evaluateLiveTrigger short-circuits on its first failed gate, so a LIVE_TRIGGER rejection can
  // never have complete evidence. The code comment stated that rule; nothing enforced it, and the
  // record could claim COMPLETE with the whole gate silent. These fixtures pin BOTH directions:
  // the real emitter's actual claim, the refusal of a false one, that the refusal is SURFACED
  // rather than silent, and -- critically -- that the rule is scoped rather than a blanket ban.
  '  g.record("JVM-32","every real CANDIDATE_REJECTED record claims PARTIAL, never COMPLETE -- the short-circuit means later gates genuinely were not evaluated",\n' +
  '    rejEvents.length>0&&rejEvents.every(function(e){ return e.evidenceCompleteness==="PARTIAL"; }),\n' +
  '    "n="+rejEvents.length+" levels="+JSON.stringify(rejEvents.map(function(e){return e.evidenceCompleteness;})));\n' +
  '  var __vfBefore=decisionEventValidationFailures.length, __logBefore=decisionEventLog.length;\n' +
  '  var __badRes=emitDecisionEvent({eventType:"CANDIDATE_REJECTED",strategyId:"current_strategy",\n' +
  '    pair:"EUR_USD",source:"checkAutoTrades",stage:"LIVE_TRIGGER",decision:"REJECTED",\n' +
  '    reasonCode:"CONFLUENCE_BELOW_THRESHOLD",evidenceCompleteness:"COMPLETE"});\n' +
  '  g.record("JVM-33","a LIVE_TRIGGER rejection claiming COMPLETE is REFUSED and never enters the append-only ledger",\n' +
  '    __badRes&&__badRes.ok===false&&decisionEventLog.length===__logBefore,\n' +
  '    "ok="+String(__badRes&&__badRes.ok)+" logGrew="+String(decisionEventLog.length-__logBefore));\n' +
  '  g.record("JVM-34","and the refusal is SURFACED as a validation failure rather than silently dropping an audit record",\n' +
  '    decisionEventValidationFailures.length===__vfBefore+1&&\n' +
  '    String(decisionEventValidationFailures[decisionEventValidationFailures.length-1].errors.join(" ")).indexOf("short-circuits")!==-1,\n' +
  '    JSON.stringify(decisionEventValidationFailures.slice(-1)));\n' +
  '  var __okRes=emitDecisionEvent({eventType:"CANDIDATE_REJECTED",strategyId:"current_strategy",\n' +
  '    pair:"EUR_USD",source:"checkAutoTrades",stage:"LIVE_TRIGGER",decision:"REJECTED",\n' +
  '    reasonCode:"CONFLUENCE_BELOW_THRESHOLD",evidenceCompleteness:"PARTIAL"});\n' +
  '  g.record("JVM-35","POSITIVE CONTROL: the identical record claiming PARTIAL is accepted -- the rule rejects the false claim, not the event type",\n' +
  '    __okRes&&__okRes.ok===true,"ok="+String(__okRes&&__okRes.ok)+" errs="+JSON.stringify(__okRes&&__okRes.errors));\n' +
  '  var __otherStage=emitDecisionEvent({eventType:"CANDIDATE_REJECTED",strategyId:"alex_g_sr_v1",\n' +
  '    pair:"EUR_USD",source:"alexGRunSetupEngine",stage:"SETUP_QUALIFICATION",decision:"REJECTED",\n' +
  '    reasonCode:"CONFLUENCE_BELOW_THRESHOLD",evidenceCompleteness:"COMPLETE"});\n' +
  '  g.record("JVM-36","POSITIVE CONTROL: the rule is SCOPED to the short-circuiting LIVE_TRIGGER stage -- a rejection from a stage that does evaluate everything may still claim COMPLETE",\n' +
  '    __otherStage&&__otherStage.ok===true,\n' +
  '    "ok="+String(__otherStage&&__otherStage.ok)+" errs="+JSON.stringify(__otherStage&&__otherStage.errors));\n' +
  // JVM-37 needs a MIXED set of reasons and would otherwise be vacuous. The scenario above runs
  // setMode("flat"), where every pair rejects for the SAME reason -- so a reasonText hard-coded to
  // that one reason stays self-consistent with its own code and nothing notices. (Proven: a
  // hard-coded reasonText survived the entire 1,644-fixture gate against the first version of this
  // fixture.) Driving the real recorder with three of the eight reason strings evaluateLiveTrigger
  // genuinely returns makes any single hard-coded text contradict at least two records. The reasons
  // are real strategy outputs taken from JVM-30's mapping; no verdict is faked.
  '  clearDecisionEvents();\n' +
  '  jvmRecordCandidateRejected("EUR_USD",{reason:"Confluence below threshold",conf:{total:40}});\n' +
  '  jvmRecordCandidateRejected("GBP_USD",{reason:"No engulfing trigger yet",conf:{total:70}});\n' +
  '  jvmRecordCandidateRejected("USD_JPY",{reason:"Invalid stop distance",conf:{total:80}});\n' +
  '  var __mixed=decisionEventLog.filter(function(e){ return e.eventType==="CANDIDATE_REJECTED"&&e.source==="checkAutoTrades"; });\n' +
  '  var __mixedCodes={}; __mixed.forEach(function(e){ __mixedCodes[e.reasonCode]=1; });\n' +
  '  g.record("JVM-37","reasonText carries the reason the strategy ACTUALLY returned -- across a MIXED set of rejections the code and the text can never contradict each other in the same record",\n' +
  '    Object.keys(__mixedCodes).length>=3&&\n' +
  '    __mixed.length===3&&\n' +
  '    __mixed.every(function(e){ return e.reasonText!=null&&jvmLiveTriggerReasonCode(e.reasonText)===e.reasonCode; }),\n' +
  '    "distinctCodes="+Object.keys(__mixedCodes).length+" "+JSON.stringify(__mixed.map(function(e){return{code:e.reasonCode,text:e.reasonText,recomputed:jvmLiveTriggerReasonCode(e.reasonText)};})));\n' +
  '  g.record("JVM-38","and each of those mixed records still claims PARTIAL -- the completeness contract holds per record, not just for one reason",\n' +
  '    __mixed.length===3&&__mixed.every(function(e){ return e.evidenceCompleteness==="PARTIAL"; }),\n' +
  '    JSON.stringify(__mixed.map(function(e){return e.evidenceCompleteness;})));\n' +
  '  clearDecisionEvents();\n' +
  // ══ JVM FORWARD-COVERAGE LEDGER (report 2.14) ══
  // JVM previously recorded NO forward coverage at all -- the ledger that makes "was this
  // instrument actually evaluated?" answerable, and whose absence left the EUR_USD question
  // unanswerable for four investigations. These fixtures prove it records, is labelled as JVM
  // rather than ALEX, survives a failed scan, and does not disturb ALEX's own records.
  '  var __jvmObs=null,__jvmAll=[]; const __origRec=evidenceRecordForwardObservations;\n' +
  '  evidenceRecordForwardObservations=function(input){ __jvmObs=evidenceBuildPollObservation((input&&input.poll)||{}); __jvmAll.push(__jvmObs); return __origRec.apply(this,arguments); };\n' +
  '  g.setMode("firing"); structuralAOICache={}; pairData={}; firedAlerts=new Set(); clearDecisionEvents();\n' +
  '  autoTrading.enabled=true; autoTrading.tradedToday={}; autoTrading.log=[]; autoTrading._lastDay=null;\n' +
  '  paperAccount={balance:10000,openPositions:[],closedPositions:[]};\n' +
  '  scanData={}; SCAN_PAIRS.forEach(function(p){ scanData[p]={weekly:"Bullish",daily:"Bullish",fh:"Bullish",bucket:"Active watch"}; });\n' +
  '  await scanAll();\n' +
  '  g.record("JVMOBS-1","a JVM sweep now records a durable forward-coverage observation at all",\n' +
  '    !!__jvmObs&&__jvmObs.kind==="POLL","kind="+String(__jvmObs&&__jvmObs.kind));\n' +
  '  g.record("JVMOBS-2","and it is labelled as JVM, not silently stamped with ALEX\u2019s ruleVersion",\n' +
  '    __jvmObs.strategyId==="current_strategy"&&__jvmObs.strategyId!==RULES_ALEXG.ruleVersion,\n' +
  '    "strategyId="+String(__jvmObs.strategyId)+" (ALEX would be "+String(RULES_ALEXG.ruleVersion)+")");\n' +
  '  g.record("JVMOBS-3","it records the SCANNED universe, which is ALL_PAIRS and not the 12 tradeable ones",\n' +
  '    __jvmObs.instrumentsConfigured===ALL_PAIRS.length&&\n' +
  '    (__jvmObs.instrumentsEvaluated||[]).length===ALL_PAIRS.length&&ALL_PAIRS.length>SCAN_PAIRS.length,\n' +
  '    "evaluated="+((__jvmObs.instrumentsEvaluated)||[]).length+"/"+__jvmObs.instrumentsConfigured+\n' +
  '    ", tradeable universe is "+SCAN_PAIRS.length);\n' +
  '  g.record("JVMOBS-4","the observation carries the real outcome and whether auto-trading was on",\n' +
  '    __jvmObs.outcome==="OK"&&__jvmObs.tradingEnabled===true&&__jvmObs.evaluationAdvanced===true,\n' +
  '    "outcome="+__jvmObs.outcome+" tradingEnabled="+__jvmObs.tradingEnabled);\n' +
  // A failed scan must STILL be recorded -- a ledger that only remembers successful scans hides
  // exactly the gaps it exists to expose -- and the original error must still propagate.
  '  __jvmObs=null;\n' +
  '  const __origRender=renderPairList; renderPairList=function(){ throw new Error("forced scan failure"); };\n' +
  '  let __threw=false;\n' +
  '  try{ await scanAll(); }catch(e){ __threw=/forced scan failure/.test(String(e&&e.message)); }\n' +
  '  renderPairList=__origRender;\n' +
  '  g.record("JVMOBS-5","a FAILED scan is still recorded, and the original error still propagates",\n' +
  '    __threw===true&&!!__jvmObs&&__jvmObs.outcome==="ERROR"&&/forced scan failure/.test(String(__jvmObs.errorText)),\n' +
  '    "threw="+__threw+" outcome="+String(__jvmObs&&__jvmObs.outcome));\n' +
  // The change that carried real regression risk: evidenceObservationBase is shared with ALEX.
  '  const alexShaped=evidenceBuildPollObservation({tickId:"T",startedAt:new Date().toISOString()});\n' +
  '  g.record("JVMOBS-6","ALEX records are UNCHANGED when strategyId is omitted -- the shared builder did not regress",\n' +
  '    alexShaped.strategyId===RULES_ALEXG.ruleVersion,\n' +
  '    "omitted strategyId still resolves to "+String(alexShaped.strategyId));\n' +
  // ── the fields that had NO fixture able to fail ──
  // An ABORTED sweep is the case the finally exists for, and the case a persistent-state check
  // gets wrong: pairs never reached still hold the PREVIOUS scan's pairData. This asserts the
  // ledger reports only what this sweep actually touched.
  '  __jvmObs=null; pairData={};\n' +
  '  await scanAll();\n' +
  '  const fullCount=(__jvmObs.instrumentsEvaluated||[]).length;\n' +
  '  __jvmObs=null;\n' +
  '  const __origRender2=renderPairList; let __chunks=0;\n' +
  '  renderPairList=function(){ __chunks++; if(__chunks>=2) throw new Error("abort mid-sweep"); };\n' +
  '  try{ await scanAll(); }catch(e){}\n' +
  '  renderPairList=__origRender2;\n' +
  // EXACT numbers. The abort fires on the 2nd renderPairList, i.e. after two 5-pair chunks, so the
  // sweep reached precisely 10 and left 25. A range assertion passed for any partial value and let
  // both an off-by-one and a whole lost chunk through.
  '  g.record("JVMOBS-7","an ABORTED sweep reports EXACTLY the instruments it reached -- 10, not last scan\u2019s 35",\n' +
  '    (__jvmObs.instrumentsEvaluated||[]).length===10&&fullCount===ALL_PAIRS.length,\n' +
  '    "aborted sweep evaluated "+((__jvmObs.instrumentsEvaluated)||[]).length+" (expected exactly 10); a stale check claimed all "+fullCount);\n' +
  '  g.record("JVMOBS-8","and EXACTLY the other 25 are named NOT_REACHED_THIS_SCAN",\n' +
  '    (__jvmObs.instrumentsSkipped||[]).length===25&&\n' +
  '    (__jvmObs.instrumentsSkipped||[]).filter(function(x){return x.reason==="NOT_REACHED_THIS_SCAN";}).length===25&&\n' +
  '    __jvmObs.instrumentsAttempted===10,\n' +
  '    "skipped="+((__jvmObs.instrumentsSkipped)||[]).length+" all NOT_REACHED, attempted="+__jvmObs.instrumentsAttempted);\n' +
  // tradingEnabled and evaluationAdvanced were asserted only against a fixture that set them true.
  '  __jvmObs=null; pairData={}; autoTrading.enabled=false;\n' +
  '  await scanAll();\n' +
  '  g.record("JVMOBS-9","tradingEnabled reflects the REAL flag, not a constant",\n' +
  '    __jvmObs.tradingEnabled===false,"tradingEnabled="+__jvmObs.tradingEnabled+" with auto-trading off");\n' +
  '  autoTrading.enabled=true;\n' +
  // ADR-011: an instrument whose history came back short is NOT evaluated by the app. The ledger
  // must not claim it was -- an empty candle array is truthy, which is how it previously did.
  '  __jvmObs=null; pairData={}; g.setShortPair("EUR_USD");\n' +
  '  await scanAll();\n' +
  '  g.setShortPair(null);\n' +
  '  g.record("JVMOBS-10","an instrument SUPPRESSED by the completeness contract is reported skipped, not evaluated",\n' +
  '    (__jvmObs.instrumentsEvaluated||[]).indexOf("EUR_USD")===-1&&\n' +
  '    (__jvmObs.instrumentsSkipped||[]).some(function(x){return x.pair==="EUR_USD"&&x.reason==="EVALUATION_SUPPRESSED_INCOMPLETE_DATA";}),\n' +
  '    "EUR_USD suppressed by ADR-011 and reported as such, evaluated="+((__jvmObs.instrumentsEvaluated)||[]).length);\n' +
  // Tested where evaluated===0. Asserting the identity against a scan that DID evaluate would be
  // satisfied by a hard-coded `true`, which is exactly how this field escaped coverage before.
  '  __jvmObs=null; pairData={}; g.setShortAll(true);\n' +
  '  await scanAll();\n' +
  '  g.setShortAll(false);\n' +
  '  g.record("JVMOBS-11","evaluationAdvanced is FALSE when nothing could be evaluated -- it is not hard-coded",\n' +
  '    (__jvmObs.instrumentsEvaluated||[]).length===0&&__jvmObs.evaluationAdvanced===false&&\n' +
  '    (__jvmObs.instrumentsSkipped||[]).length===ALL_PAIRS.length,\n' +
  '    "evaluated=0/"+ALL_PAIRS.length+" evaluationAdvanced="+__jvmObs.evaluationAdvanced+" (every pair suppressed by ADR-011)");\n' +
  // ── the concurrency case that defeated object-identity diffing ──
  '  __jvmObs=null; pairData={}; autoTrading.enabled=true;\n' +
  '  g.holdPair("EUR_USD");\n' +
  '  __jvmAll=[];\n' +
  '  const sweepA=scanAll();\n' +
  '  for(let y=0;y<25;y++) await Promise.resolve();\n' +
  '  g.releaseHeld();\n' +
  '  const sweepB=scanAll();\n' +
  '  await sweepB; try{ await sweepA; }catch(e){}\n' +
  // CORRECTED INVARIANT. The previous version asserted that the two sweeps' evaluated sets SUM to 35
  // with no instrument credited twice. That premise is wrong: overlapping sweeps do not partition the
  // instrument universe -- each independently scans all 35, so two complete sweeps legitimately report
  // 35 EACH and every instrument legitimately appears in both. "Combined 35" held only for one
  // particular interleaving; other interleavings of the same code produced 66 and 0, so the fixture
  // was pinning an accident rather than a property.
  //
  // The property that actually matters is PER-SWEEP HONESTY: each sweep reports exactly the
  // instruments IT evaluated, whatever the interleaving. Here sweep A is held mid-chunk, released,
  // and overtaken by sweep B; both go on to complete, so both must report their own full 35.
  '  const evalCounts=__jvmAll.map(function(o){ return (o.instrumentsEvaluated||[]).length; });\n' +
  '  const dispatchHonest=__jvmAll.every(function(o){\n' +
  '    return (o.instrumentsEvaluated||[]).length<=o.instrumentsAttempted\n' +
  '      &&(o.instrumentsEvaluated||[]).length+(o.instrumentsSkipped||[]).length===ALL_PAIRS.length; });\n' +
  '  g.record("JVMOBS-12","two OVERLAPPING sweeps each report their OWN full coverage -- neither is erased or inflated by the other",\n' +
  '    __jvmAll.length===2&&evalCounts.every(function(n){ return n===ALL_PAIRS.length; })&&dispatchHonest,\n' +
  '    "per-sweep evaluated="+JSON.stringify(evalCounts)+"/"+ALL_PAIRS.length+\n' +
  '    " (each sweep genuinely scanned all 35; evaluated+skipped==35 and evaluated<=attempted for both)");\n' +
  // R3 had no coverage at all: reverting the non-empty-string guard survived both gates.
  '  const isoNow=new Date().toISOString();\n' +
  '  g.record("JVMOBS-13","a FALSY strategyId is not accepted as an identity -- it falls back to ALEX",\n' +
  '    evidenceObservationBase("POLL",isoNow,"").strategyId===RULES_ALEXG.ruleVersion&&\n' +
  '    evidenceObservationBase("POLL",isoNow,false).strategyId===RULES_ALEXG.ruleVersion&&\n' +
  '    evidenceObservationBase("POLL",isoNow,0).strategyId===RULES_ALEXG.ruleVersion&&\n' +
  '    evidenceObservationBase("POLL",isoNow,"current_strategy").strategyId==="current_strategy",\n' +
  '    "empty string, false and 0 all resolve to "+RULES_ALEXG.ruleVersion+"; a real id still overrides");\n' +
  // transport failure and contract suppression must not share a label
  '  __jvmObs=null; pairData={}; g.setShortPair("EUR_USD");\n' +
  '  await scanAll();\n' +
  '  g.setShortPair(null);\n' +
  '  const skEur=(__jvmObs.instrumentsSkipped||[]).filter(function(x){return x.pair==="EUR_USD";})[0]||{};\n' +
  '  g.record("JVMOBS-14","a skipped instrument carries the completenessState that explains WHY",\n' +
  '    skEur.completenessState===MARKET_DATA_COMPLETENESS.PARTIAL&&\n' +
  '    skEur.reason==="EVALUATION_SUPPRESSED_INCOMPLETE_DATA",\n' +
  '    "reason="+skEur.reason+" completenessState="+skEur.completenessState);\n' +
  // A TRANSPORT failure and a CONTRACT suppression are different facts and must not share a label.
  // Collapsing them is how "no data arrived" starts reading as "the strategy declined to score it".
  '  __jvmObs=null; pairData={}; g.failPair("GBP_USD"); g.setShortPair("EUR_USD");\n' +
  '  await scanAll();\n' +
  '  g.failPair(null); g.setShortPair(null);\n' +
  '  const skFail=(__jvmObs.instrumentsSkipped||[]).filter(function(x){return x.pair==="GBP_USD";})[0]||{};\n' +
  '  const skShort=(__jvmObs.instrumentsSkipped||[]).filter(function(x){return x.pair==="EUR_USD";})[0]||{};\n' +
  '  g.record("JVMOBS-15","a TRANSPORT failure is reported distinctly from an ADR-011 suppression",\n' +
  '    skFail.reason==="MARKET_DATA_UNAVAILABLE"&&skFail.completenessState===MARKET_DATA_COMPLETENESS.UNAVAILABLE&&\n' +
  '    skShort.reason==="EVALUATION_SUPPRESSED_INCOMPLETE_DATA"&&skShort.completenessState===MARKET_DATA_COMPLETENESS.PARTIAL&&\n' +
  '    skFail.reason!==skShort.reason,\n' +
  '    "no data arrived -> "+skFail.reason+"; short history -> "+skShort.reason);\n' +
  // ── MOGO-021: the interleaving that the sweep-TOKEN version got backwards ──
  // Reading attribution back out of pairData in the `finally` measures the LAST WRITER, not this
  // sweep. Sweep A completes all 35 writes and then sits in its post-chunk work (checkAutoTrades /
  // runManualReviewScan, both real network I/O in production) while sweep B overwrites pairData and
  // finishes first. Under the token-counted-from-pairData form, A reported ZERO evaluated and 35
  // DISPATCHED_NO_RESULT -- a fabricated total outage on a sweep that did everything right.
  '  __jvmObs=null; __jvmAll=[]; pairData={}; autoTrading.enabled=true;\n' +
  '  const __origMRS=runManualReviewScan; let __parked=0,__releaseMRS=null;\n' +
  '  runManualReviewScan=function(){ __parked++;\n' +
  '    if(__parked===1) return new Promise(function(res){ __releaseMRS=res; });\n' +
  '    return Promise.resolve(); };\n' +
  '  const swA=scanAll();\n' +
  '  for(let y=0;y<400;y++) await Promise.resolve();\n' +
  '  const swB=scanAll();\n' +
  '  await swB;\n' +
  '  if(__releaseMRS) __releaseMRS();\n' +
  '  try{ await swA; }catch(e){}\n' +
  '  runManualReviewScan=__origMRS;\n' +
  '  const recA=__jvmAll[__jvmAll.length-1]||{};\n' +
  '  g.record("JVMOBS-16","a sweep that finishes LAST still reports its OWN 35 evaluations, not the later sweep\\u2019s overwrite",\n' +
  '    __jvmAll.length===2&&(recA.instrumentsEvaluated||[]).length===ALL_PAIRS.length&&\n' +
  '    recA.evaluationAdvanced===true&&\n' +
  '    (recA.instrumentsSkipped||[]).filter(function(x){return x.reason==="DISPATCHED_NO_RESULT";}).length===0,\n' +
  '    "overtaken sweep evaluated "+((recA.instrumentsEvaluated)||[]).length+"/"+ALL_PAIRS.length+\n' +
  '    " advanced="+recA.evaluationAdvanced+" phantom DISPATCHED_NO_RESULT="+\n' +
  '    ((recA.instrumentsSkipped)||[]).filter(function(x){return x.reason==="DISPATCHED_NO_RESULT";}).length+\n' +
  '    " (reading pairData back produced 0/35 evaluated and 35 phantom skips)");\n' +
  '  g.record("JVMOBS-17","and BOTH overlapping sweeps report their own full coverage -- neither is erased by the other",\n' +
  '    __jvmAll.length===2&&__jvmAll.every(function(o){ return (o.instrumentsEvaluated||[]).length===ALL_PAIRS.length; }),\n' +
  '    "per-sweep evaluated="+JSON.stringify(__jvmAll.map(function(o){return (o.instrumentsEvaluated||[]).length;})));\n' +
  // DISPATCHED_NO_RESULT shipped with ZERO coverage -- deleting the branch entirely survived the gate.
  //
  // REACHABILITY, stated honestly. It cannot be reached through the I/O layer: fetchCandles and
  // fetchPrice both end in `catch{return null;}`, so a rejected request becomes a null dataset and the
  // instrument IS written, as UNAVAILABLE (JVMOBS-18a proves exactly that -- a rejected fetch is
  // MARKET_DATA_UNAVAILABLE, not DISPATCHED_NO_RESULT). But the branch is NOT dead code and NOT
  // merely defensive: independent verification reached it through the REAL, unstubbed scanPair by
  // making the protected bestConfluence throw, and it also fires for an instrument that never threw
  // at all -- a sibling still in flight when its own sweep aborts mid-chunk. It is exercised here at
  // the dispatch seam because that is deterministic; scanPair is not protected and is scanAll's
  // single dispatch point, so substituting it for one instrument tests scanAll's classification
  // directly. (A strictly stronger organic construction exists -- throw from bestConfluence -- and
  // is a disclosed follow-up rather than a gap: the fixture below is not vacuous, it dies to the
  // deletion of the branch it names.)
  '  __jvmObs=null; __jvmAll=[]; pairData={}; g.throwPair("USD_CHF");\n' +
  '  try{ await scanAll(); }catch(e){}\n' +
  '  g.throwPair(null);\n' +
  '  const skThrown=(__jvmObs.instrumentsSkipped||[]).filter(function(x){return x.pair==="USD_CHF";})[0]||{};\n' +
  '  g.record("JVMOBS-18a","a REJECTED candle request is still a written result -- UNAVAILABLE, not DISPATCHED_NO_RESULT",\n' +
  '    skThrown.reason==="MARKET_DATA_UNAVAILABLE"&&skThrown.completenessState===MARKET_DATA_COMPLETENESS.UNAVAILABLE&&\n' +
  '    (__jvmObs.instrumentsEvaluated||[]).indexOf("USD_CHF")===-1,\n' +
  '    "rejected fetch -> reason="+String(skThrown.reason)+" completenessState="+String(skThrown.completenessState));\n' +
  '  __jvmObs=null; __jvmAll=[]; pairData={};\n' +
  '  const __origScanPair=scanPair;\n' +
  '  scanPair=function(p,tok,sink){ if(p==="USD_CHF") return Promise.resolve(); return __origScanPair(p,tok,sink); };\n' +
  '  await scanAll();\n' +
  '  scanPair=__origScanPair;\n' +
  '  const skNoRes=(__jvmObs.instrumentsSkipped||[]).filter(function(x){return x.pair==="USD_CHF";})[0]||{};\n' +
  '  g.record("JVMOBS-18","an instrument DISPATCHED whose scan produced NO result is named DISPATCHED_NO_RESULT, not conflated with a data fault",\n' +
  '    skNoRes.reason==="DISPATCHED_NO_RESULT"&&skNoRes.completenessState===null&&\n' +
  '    (__jvmObs.instrumentsEvaluated||[]).indexOf("USD_CHF")===-1&&\n' +
  '    (__jvmObs.instrumentsEvaluated||[]).length===ALL_PAIRS.length-1,\n' +
  '    "USD_CHF reason="+String(skNoRes.reason)+" completenessState="+String(skNoRes.completenessState)+\n' +
  '    " evaluated="+((__jvmObs.instrumentsEvaluated)||[]).length+"/"+ALL_PAIRS.length);\n' +
  // instrumentsAttempted is the DISPATCH list, not a count of writes. Reverting it to the write
  // count (its pre-MOGO-021 meaning) must fail here, or the headline fix has no coverage.
  '  g.record("JVMOBS-19","instrumentsAttempted counts the DISPATCH, so an instrument attempted-and-failed is not invisible",\n' +
  '    __jvmObs.instrumentsAttempted>(__jvmObs.instrumentsEvaluated||[]).length&&\n' +
  '    __jvmObs.instrumentsAttempted===__jvmObs.instrumentsEvaluated.length+\n' +
  '      (__jvmObs.instrumentsSkipped||[]).filter(function(x){return x.reason!=="NOT_REACHED_THIS_SCAN";}).length,\n' +
  '    "attempted="+__jvmObs.instrumentsAttempted+" evaluated="+((__jvmObs.instrumentsEvaluated)||[]).length+\n' +
  '    " (a write-count would have reported "+((__jvmObs.instrumentsEvaluated)||[]).length+")");\n' +
  // ══ MOGO-021 JVM COMPLETENESS PARITY (owner-authorized) ═══════════════════════════════════
  // scanPair -- which only SCORES for display -- has been ADR-011 gated since v12.8.3. The path
  // that actually opens trades was not: evaluateLiveTrigger was guarded only by length<25, and
  // getStructuralAOI set real stops and targets from D/W data it never checked. JVM's display layer
  // was stricter than its trading layer, which nobody chose. These prove the parity, in both
  // directions -- it must fail closed on bad data AND must not cost a single valid setup.
  '  evidenceRecordForwardObservations=__origRec;\n' +
  '  function jvmFreshFiring(){ g.setMode("firing"); structuralAOICache={}; structuralAOIInflight={}; pairData={};\n' +
  '    firedAlerts=new Set(); clearDecisionEvents(); autoTrading.enabled=true; autoTrading.tradedToday={};\n' +
  '    autoTrading.log=[]; autoTrading._lastDay=null; paperAccount={balance:10000,openPositions:[],closedPositions:[]};\n' +
  '    scanData={}; SCAN_PAIRS.forEach(function(p){ scanData[p]={weekly:"Bullish",daily:"Bullish",fh:"Bullish",bucket:"Active watch"}; }); }\n' +
  // 1 + 11 + 12: COMPLETE data still evaluates, still fires, and still produces the SAME economic
  // decision. This is the anti-over-blocking control and it carries requirement 12 on its own.
  '  jvmFreshFiring();\n' +
  '  const baseTrig=await evaluateLiveTrigger("EUR_USD");\n' +
  '  await checkAutoTrades();\n' +
  '  const baseOpened=paperAccount.openPositions.length;\n' +
  '  g.record("JVMCG-1","COMPLETE required data still evaluates and still FIRES -- the gate costs no valid setup",\n' +
  '    baseTrig.fires===true&&baseOpened>0,\n' +
  '    "trigger fires="+baseTrig.fires+" ratio="+String(baseTrig.ratio)+", positions opened="+baseOpened);\n' +
  '  const baseShape=JSON.stringify({dir:baseTrig.dir,entry:baseTrig.entry,stop:baseTrig.stop,target:baseTrig.target,conf:baseTrig.confluence});\n' +
  '  g.record("JVMCG-2","and the economic decision is unchanged -- direction, entry, stop, target and confluence all present and self-consistent",\n' +
  '    baseTrig.dir&&baseTrig.entry>0&&baseTrig.stop>0&&baseTrig.target>0&&baseTrig.ratio>=1.99&&\n' +
  '    ((baseTrig.dir==="buy"&&baseTrig.stop<baseTrig.entry&&baseTrig.target>baseTrig.entry)||\n' +
  '     (baseTrig.dir==="sell"&&baseTrig.stop>baseTrig.entry&&baseTrig.target<baseTrig.entry)),\n' +
  '    baseShape);\n' +
  // 2: the REQUIRED entry timeframe. JVM's trade path requires M15 (entry timing) + D and W (the
  // structural AOI that sets the stop). H1 is required only when it is the active SCAN timeframe,
  // and that path (scanPair) was already gated -- stated plainly rather than implied.
  '  jvmFreshFiring(); g.setShortGran("EUR_USD","M15");\n' +
  '  const shortM15=await evaluateLiveTrigger("EUR_USD");\n' +
  '  await checkAutoTrades();\n' +
  '  const m15Open=paperAccount.openPositions.filter(function(p){return p.oPair==="EUR_USD";}).length;\n' +
  '  g.setShortGran(null,null);\n' +
  '  g.record("JVMCG-3","INCOMPLETE entry-timeframe (M15) data FAILS CLOSED -- no evaluation, no trade",\n' +
  '    shortM15.fires===false&&/Incomplete market data/.test(String(shortM15.reason))&&m15Open===0,\n' +
  '    "reason=["+String(shortM15.reason)+"] positions on that pair="+m15Open);\n' +
  // 4 + 5: the D and W structure that sets the REAL stop and target.
  '  jvmFreshFiring(); g.setShortGran("EUR_USD","D");\n' +
  '  const shortD=await evaluateLiveTrigger("EUR_USD");\n' +
  '  await checkAutoTrades();\n' +
  '  const dOpen=paperAccount.openPositions.filter(function(p){return p.oPair==="EUR_USD";}).length;\n' +
  '  g.setShortGran(null,null);\n' +
  '  g.record("JVMCG-4","INCOMPLETE DAILY data FAILS CLOSED -- the stop is never derived from it",\n' +
  '    shortD.fires===false&&/Incomplete market data/.test(String(shortD.reason))&&dOpen===0,\n' +
  '    "reason=["+String(shortD.reason)+"] positions on that pair="+dOpen);\n' +
  '  jvmFreshFiring(); g.setShortGran("EUR_USD","W");\n' +
  '  const shortW=await evaluateLiveTrigger("EUR_USD");\n' +
  '  await checkAutoTrades();\n' +
  '  const wOpen=paperAccount.openPositions.filter(function(p){return p.oPair==="EUR_USD";}).length;\n' +
  '  g.setShortGran(null,null);\n' +
  '  g.record("JVMCG-5","INCOMPLETE WEEKLY data FAILS CLOSED -- the structural AOI is refused, not approximated",\n' +
  '    shortW.fires===false&&/Incomplete market data/.test(String(shortW.reason))&&wOpen===0,\n' +
  '    "reason=["+String(shortW.reason)+"] positions on that pair="+wOpen);\n' +
  // 3: H4 reaches the trade decision through the bias scan -> scanData.bucket -> the eligibility
  // filter, so it is a required trade-path input even though checkAutoTrades never fetches it.
  '  jvmFreshFiring(); scanData={}; g.setShortGran("EUR_USD","H4");\n' +
  '  await runAutoTopDownScan();\n' +
  '  g.setShortGran(null,null);\n' +
  '  const eurRow=scanData["EUR/USD"]||{};\n' +
  '  g.record("JVMCG-6","INCOMPLETE H4 data FAILS CLOSED in the bias scan, so the pair cannot become auto-trade ELIGIBLE",\n' +
  '    eurRow.completenessSuppressed===true&&eurRow.bucket!=="Active watch",\n' +
  '    "bucket=["+String(eurRow.bucket)+"] suppressed="+String(eurRow.completenessSuppressed)+\n' +
  '    " byTf="+JSON.stringify(eurRow.completenessByTimeframe));\n' +
  // 6: UNKNOWN/unclassified must fail closed -- marketDataCompletenessOf reports it UNAVAILABLE.
  '  g.record("JVMCG-7","UNKNOWN completeness FAILS CLOSED -- unclassified data is never assumed complete",\n' +
  '    marketDataCompletenessOf([1,2,3])===MARKET_DATA_COMPLETENESS.UNAVAILABLE&&\n' +
  '    marketDataCompletenessOf(null)===MARKET_DATA_COMPLETENESS.UNAVAILABLE&&\n' +
  '    marketDataCompletenessOf(undefined)===MARKET_DATA_COMPLETENESS.UNAVAILABLE,\n' +
  '    "an array carrying no completeness verdict reads UNAVAILABLE, not COMPLETE");\n' +
  // 8: scoped to the instrument. An incomplete pair must not cost the healthy eleven.
  '  jvmFreshFiring(); g.setShortGran("EUR_USD","D");\n' +
  '  await checkAutoTrades();\n' +
  '  const others=paperAccount.openPositions.filter(function(p){return p.oPair!=="EUR_USD";}).length;\n' +
  '  const eurs=paperAccount.openPositions.filter(function(p){return p.oPair==="EUR_USD";}).length;\n' +
  '  g.setShortGran(null,null);\n' +
  '  g.record("JVMCG-8","one INCOMPLETE instrument does not suppress the healthy ones -- suppression is per-pair",\n' +
  '    eurs===0&&others>0,\n' +
  '    "EUR_USD opened "+eurs+"; other instruments opened "+others);\n' +
  // 9 + 10: three different facts, three different codes. Collapsing any two would make a data
  // fault indistinguishable from a rule rejection.
  '  g.record("JVMCG-9","TRANSPORT failure, COMPLETENESS suppression and STRATEGY rejection carry three DISTINCT codes",\n' +
  '    jvmLiveTriggerReasonCode("No data")==="DATA_CANDLES_UNAVAILABLE"&&\n' +
  '    jvmLiveTriggerReasonCode("Incomplete market data (M15)")==="DATA_TIMEFRAME_INCOMPLETE"&&\n' +
  '    jvmLiveTriggerReasonCode("Incomplete market data (D/W)")==="DATA_TIMEFRAME_INCOMPLETE"&&\n' +
  '    jvmLiveTriggerReasonCode("Confluence below threshold")==="CONFLUENCE_BELOW_THRESHOLD"&&\n' +
  '    jvmLiveTriggerReasonCode("No valid support AOI")==="STRUCTURE_AOI_NOT_VALIDATED"&&\n' +
  '    !!REASON_CODE_REGISTRY["DATA_TIMEFRAME_INCOMPLETE"],\n' +
  '    "no data -> transport; incomplete -> contract; low confluence / no AOI -> strategy");\n' +
  // A data fault must NOT be reported as the strategy declining to score -- the specific confusion
  // the old code produced, since an incomplete AOI simply looked like "no valid support AOI".
  '  jvmFreshFiring(); g.setShortGran("EUR_USD","D");\n' +
  '  const rej=await evaluateLiveTrigger("EUR_USD");\n' +
  '  g.setShortGran(null,null);\n' +
  '  g.record("JVMCG-10","an incomplete AOI is reported as a DATA fault, never as \\u201cno valid support AOI\\u201d",\n' +
  '    /Incomplete market data/.test(String(rej.reason))&&!/No valid (support|resistance) AOI/.test(String(rej.reason)),\n' +
  '    "reason=["+String(rej.reason)+"]");\n' +
  // 7: the reproduced defect shape -- a short broker page must not produce a JVM paper trade.
  '  jvmFreshFiring(); g.setShortGran("EUR_USD","D");\n' +
  '  await scanAll();\n' +
  '  const afterSweep=paperAccount.openPositions.filter(function(p){return p.oPair==="EUR_USD";}).length;\n' +
  '  g.setShortGran(null,null);\n' +
  '  g.record("JVMCG-11","a SHORT BROKER PAGE cannot generate a JVM paper trade, through the real sweep",\n' +
  '    afterSweep===0,"EUR_USD positions after a full scanAll with a short daily page="+afterSweep);\n' +
  // 14: overlapping sweeps must not let the gated instrument through on either pass.
  '  jvmFreshFiring(); g.setShortGran("EUR_USD","D");\n' +
  '  const sw1=scanAll(); const sw2=scanAll();\n' +
  '  await sw2; try{ await sw1; }catch(e){}\n' +
  '  const overlapEur=paperAccount.openPositions.filter(function(p){return p.oPair==="EUR_USD";}).length;\n' +
  '  const overlapOthers=paperAccount.openPositions.filter(function(p){return p.oPair!=="EUR_USD";}).length;\n' +
  '  g.setShortGran(null,null);\n' +
  '  g.record("JVMCG-12","OVERLAPPING sweeps cannot bypass the gate -- neither pass admits the incomplete instrument",\n' +
  '    overlapEur===0&&overlapOthers>0,\n' +
  '    "across two concurrent sweeps EUR_USD opened "+overlapEur+" and healthy instruments opened "+overlapOthers);\n' +
  // 13: recovery. A transient fault must not be cached into a lasting refusal -- that would lose
  // valid setups, which the authorization explicitly rules out.
  '  jvmFreshFiring(); g.setShortGran("EUR_USD","D");\n' +
  '  const faulted=await evaluateLiveTrigger("EUR_USD");\n' +
  '  g.setShortGran(null,null);\n' +
  '  const recovered=await evaluateLiveTrigger("EUR_USD");\n' +
  '  g.record("JVMCG-13","RECOVERY: a transient short page is not cached into a lasting refusal",\n' +
  '    faulted.fires===false&&/Incomplete market data/.test(String(faulted.reason))&&recovered.fires===true,\n' +
  '    "faulted=["+String(faulted.reason)+"] then recovered fires="+recovered.fires+\n' +
  '    " (an incomplete AOI is deliberately NOT cached, or one bad page would cost 15 minutes of trading)");\n' +
  // ══ MOGO-021 SCAN FAILURE ISOLATION -- one instrument must not suppress the whole trade pass ══
  // scanPair had no try/catch and was dispatched BARE into Promise.all, so ONE instrument throwing
  // rejected its chunk, aborted every remaining chunk, and skipped checkPaperPositions,
  // checkAutoTrades AND runManualReviewScan for the entire sweep: one instrument's display fault
  // suppressing every trade decision on the other 34. That had no fixture anywhere -- removing the
  // per-dispatch .catch() left the whole gate green.
  //
  // The fault is injected at bestConfluence for ONE instrument, so it throws inside the REAL,
  // unstubbed scanPair and BEFORE the pairData/__jvmResults write -- the organic shape of the
  // defect, and the only shape that also reaches DISPATCHED_NO_RESULT. EUR_GBP is deliberately an
  // ALL_PAIRS-only instrument (NOT one of the 12 SCAN_PAIRS), so the injected fault cannot reach
  // checkAutoTrades' own evaluateLiveTrigger call: the trade pass is measured on instruments the
  // fault never touched, which is the point -- their trades must not be collateral damage.
  '  var __isoObs=null; const __isoRec=evidenceRecordForwardObservations;\n' +
  '  evidenceRecordForwardObservations=function(input){ __isoObs=evidenceBuildPollObservation((input&&input.poll)||{}); return __isoRec.apply(this,arguments); };\n' +
  '  jvmFreshFiring(); paperEngineErrors=[];\n' +
  '  const __isoBC=bestConfluence;\n' +
  '  bestConfluence=function(candles,pairKey,overrides){\n' +
  '    if(pairKey==="EUR_GBP") throw new Error("fixture display fault"); return __isoBC.apply(this,arguments); };\n' +
  '  const __isoCAT=checkAutoTrades; let __isoCATCalls=0;\n' +
  '  checkAutoTrades=function(){ __isoCATCalls++; return __isoCAT.apply(this,arguments); };\n' +
  '  const __isoMRS=runManualReviewScan; let __isoMRSCalls=0;\n' +
  '  runManualReviewScan=function(){ __isoMRSCalls++; return __isoMRS.apply(this,arguments); };\n' +
  '  let __isoThrew=false;\n' +
  '  try{ await scanAll(); }catch(e){ __isoThrew=true; }\n' +
  '  bestConfluence=__isoBC; checkAutoTrades=__isoCAT; runManualReviewScan=__isoMRS;\n' +
  '  evidenceRecordForwardObservations=__isoRec;\n' +
  '  const __isoErr=paperEngineErrors.filter(function(e){ return /^scanPair\\(EUR_GBP\\): fixture display fault/.test(String(e&&e.message)); });\n' +
  '  g.record("JVMISO-1","PRECONDITION: the injected fault really threw inside scanPair, was recorded per-instrument, and did NOT abort the sweep",\n' +
  '    __isoErr.length===1&&__isoThrew===false,\n' +
  '    "scanPair(EUR_GBP) errors recorded="+__isoErr.length+" ["+String((__isoErr[0]||{}).message).slice(0,44)+"], scanAll threw="+__isoThrew);\n' +
  '  g.record("JVMISO-2","the OTHER 34 instruments still complete and are reported evaluated -- one fault does not abort the remaining chunks",\n' +
  '    (__isoObs.instrumentsEvaluated||[]).length===ALL_PAIRS.length-1&&\n' +
  '    (__isoObs.instrumentsEvaluated||[]).indexOf("EUR_GBP")===-1,\n' +
  '    "evaluated="+((__isoObs.instrumentsEvaluated)||[]).length+"/"+ALL_PAIRS.length+" with EUR_GBP absent");\n' +
  '  const __isoSk=(__isoObs.instrumentsSkipped||[]).filter(function(x){return x.pair==="EUR_GBP";})[0]||{};\n' +
  '  g.record("JVMISO-3","the throwing instrument is reported DISPATCHED_NO_RESULT -- isolated, not silently absorbed",\n' +
  '    __isoSk.reason==="DISPATCHED_NO_RESULT"&&__isoSk.completenessState===null&&\n' +
  '    (__isoObs.instrumentsSkipped||[]).length===1&&__isoObs.instrumentsAttempted===ALL_PAIRS.length,\n' +
  '    "EUR_GBP reason="+String(__isoSk.reason)+" completenessState="+String(__isoSk.completenessState)+\n' +
  '    " attempted="+__isoObs.instrumentsAttempted+" skipped="+((__isoObs.instrumentsSkipped)||[]).length);\n' +
  // THE ONE THAT MATTERS. A display fault on a single instrument used to cost the ENTIRE trade pass:
  // Promise.all rejected, the throw propagated out of the chunk loop, and checkAutoTrades was never
  // reached. Asserting the call alone would be satisfied by a call that failed, so the opened
  // positions are asserted too -- the pass ran to completion, not merely started.
  '  g.record("JVMISO-4","THE TRADE PASS STILL RUNS: checkAutoTrades and runManualReviewScan are reached and real positions still open",\n' +
  '    __isoCATCalls===1&&__isoMRSCalls===1&&paperAccount.openPositions.length>0,\n' +
  '    "checkAutoTrades calls="+__isoCATCalls+" runManualReviewScan calls="+__isoMRSCalls+\n' +
  '    " positions opened="+paperAccount.openPositions.length+" (bare dispatch skipped the whole pass)");\n' +
  // ══ "OBSERVATION MUST NEVER REACH THE TRADING PATH" -- THE CATCH BLOCK ITSELF ═════════════
  // scanAll's forward-coverage ledger sits in a `finally`, wrapped in a catch whose entire purpose
  // is to keep an observation defect away from the trading path -- and that catch had no fixture:
  // turning it into a rethrow left the whole gate green. In a `finally` a rethrow is especially
  // severe, because it REPLACES the sweep's normal completion: a durable-write failure would start
  // reporting itself as a failed scan to every caller.
  '  jvmFreshFiring();\n' +
  '  const __obsRec=evidenceRecordForwardObservations; let __obsHits=0;\n' +
  '  evidenceRecordForwardObservations=function(){ __obsHits++; throw new Error("fixture ledger write fault"); };\n' +
  '  let __obsThrew=false;\n' +
  '  try{ await scanAll(); }catch(e){ __obsThrew=true; }\n' +
  '  evidenceRecordForwardObservations=__obsRec;\n' +
  '  g.record("JVMOBSISO-1","a throwing durable LEDGER WRITE cannot turn a healthy sweep into a failed one",\n' +
  '    __obsHits===1&&__obsThrew===false&&paperAccount.openPositions.length>0,\n' +
  '    "ledger faults raised="+__obsHits+", scanAll threw="+__obsThrew+", positions still opened="+\n' +
  '    paperAccount.openPositions.length);\n' +
  // ══ checkAutoTrades: THE POST-AWAIT DUPLICATE RE-CHECK ════════════════════════════════════
  // checkAutoTrades builds `eligible` synchronously and only THEN awaits evaluateLiveTrigger, so a
  // second invocation entering while the first is mid-await sees the identical eligible list. The
  // re-check immediately before openPaperPosition is the only thing standing between that and two
  // positions on the same instrument -- and it had no behavioural fixture at all: only the
  // protected-drift byte check stood between it and silent removal, and a drift check proves the
  // bytes did not change, never that the guard works.
  //
  // The concurrency is REAL, not simulated: checkAutoTrades has no re-entrancy guard and is called
  // unawaited from scanAll, which has none either.
  '  jvmFreshFiring();\n' +
  '  await checkAutoTrades();\n' +
  '  const __dupBaseline=paperAccount.openPositions.length;\n' +
  '  jvmFreshFiring();\n' +
  '  const __dupA=checkAutoTrades(), __dupB=checkAutoTrades();\n' +
  '  await Promise.all([__dupA,__dupB]);\n' +
  '  const __dupCounts={}; paperAccount.openPositions.forEach(function(p){ __dupCounts[p.oPair]=(__dupCounts[p.oPair]||0)+1; });\n' +
  '  const __dupPairs=Object.keys(__dupCounts).filter(function(k){ return __dupCounts[k]>1; });\n' +
  '  g.record("JVMDUP-1","PRECONDITION: a single pass genuinely opens positions, so the concurrent pass below has something to duplicate",\n' +
  '    __dupBaseline>0,"one sequential checkAutoTrades opened "+__dupBaseline+" position(s)");\n' +
  '  g.record("JVMDUP-2","TWO CONCURRENT checkAutoTrades passes cannot open a SECOND position on the same instrument",\n' +
  '    __dupPairs.length===0&&paperAccount.openPositions.length===__dupBaseline&&\n' +
  '    autoTrading.log.length===paperAccount.openPositions.length,\n' +
  '    "concurrent pass opened "+paperAccount.openPositions.length+" (sequential baseline "+__dupBaseline+\n' +
  '    "), instruments held twice="+__dupPairs.length+", journal entries="+autoTrading.log.length);\n' +
  // The re-check has TWO halves and they answer different questions, so each needs its own control:
  // against two concurrent auto passes the tradedToday half alone already blocks the duplicate, and
  // removing only the open-position half survived the fixture above. These two isolate each half by
  // creating the state it exists for DURING the await, which is the only window either can matter
  // in. The seam is evaluateLiveTrigger -- wrapped, never altered: the real one is called and its
  // real verdict returned; the wrapper only mutates the surrounding account state while the pass is
  // suspended on it, which is exactly what a manual click or a sibling pass does in production.
  '  jvmFreshFiring();\n' +
  '  const __mcOrig=evaluateLiveTrigger; let __mcPair=null;\n' +
  '  evaluateLiveTrigger=async function(oPair){ const r=await __mcOrig.apply(this,arguments);\n' +
  '    if(__mcPair===null&&r&&r.fires){ __mcPair=oPair;\n' +
  '      paperAccount.openPositions.push({oPair:oPair,dir:"buy",entry:1.1,stop:1.09,target:1.12,\n' +
  '        lots:1,riskAmount:100,id:"manual-click-during-await",source:"manual"}); }\n' +
  '    return r; };\n' +
  '  await checkAutoTrades();\n' +
  '  evaluateLiveTrigger=__mcOrig;\n' +
  '  const __mcHeld=paperAccount.openPositions.filter(function(p){ return p.oPair===__mcPair; });\n' +
  '  g.record("JVMDUP-3","a MANUAL open landing during the await blocks the auto entry -- the open-position half of the re-check, isolated",\n' +
  '    !!__mcPair&&__mcHeld.length===1&&__mcHeld[0].id==="manual-click-during-await"&&\n' +
  '    !autoTrading.tradedToday[__mcPair],\n' +
  '    __mcPair+" positions="+__mcHeld.length+" ["+__mcHeld.map(function(p){return String(p.source);}).join(",")+\n' +
  '    "], tradedToday unset -- so ONLY the open-position half could have blocked this");\n' +
  '  jvmFreshFiring();\n' +
  '  const __ttOrig=evaluateLiveTrigger; let __ttPair=null;\n' +
  '  evaluateLiveTrigger=async function(oPair){ const r=await __ttOrig.apply(this,arguments);\n' +
  '    if(__ttPair===null&&r&&r.fires){ __ttPair=oPair; autoTrading.tradedToday[oPair]=new Date().toDateString(); }\n' +
  '    return r; };\n' +
  '  await checkAutoTrades();\n' +
  '  evaluateLiveTrigger=__ttOrig;\n' +
  '  const __ttHeld=paperAccount.openPositions.filter(function(p){ return p.oPair===__ttPair; });\n' +
  '  g.record("JVMDUP-4","a pair marked traded-today during the await is not traded again -- the traded-today half, isolated",\n' +
  '    !!__ttPair&&__ttHeld.length===0&&paperAccount.openPositions.length>0,\n' +
  '    __ttPair+" positions="+__ttHeld.length+" while "+paperAccount.openPositions.length+\n' +
  '    " other instruments still opened -- no open position existed for it, so ONLY the traded-today half could have blocked it");\n' +
  // ══ closePaperPosition: THE paperPositionsClosing CONCURRENT-CLOSE GUARD ══════════════════
  // Stated precisely, because it is easy to over-claim here: the pre-existing idx2 re-validation
  // ALREADY prevents a second closed record in this interleaving, so "only one close happened" is
  // NOT what proves this guard. What the guard alone does is reject the duplicate call OUTRIGHT --
  // before it does any I/O at all. The discriminating clause below is therefore the fetchBidAsk
  // count: with the guard, one; without it, the second call runs the whole bid/ask fetch and only
  // then discovers the position is gone. Like the re-check above, it had only the drift byte check.
  '  jvmFreshFiring();\n' +
  '  await checkAutoTrades();\n' +
  '  const __clPos=paperAccount.openPositions[0]||{};\n' +
  '  const __clBalBefore=paperAccount.balance;\n' +
  '  const __clFBA=fetchBidAsk; let __clFBACalls=0;\n' +
  '  fetchBidAsk=function(p){ __clFBACalls++; return __clFBA.apply(this,arguments); };\n' +
  '  const __cl1=closePaperPosition(__clPos.id,true), __cl2=closePaperPosition(__clPos.id,true);\n' +
  '  await Promise.all([__cl1,__cl2]);\n' +
  '  fetchBidAsk=__clFBA;\n' +
  '  const __clClosed=paperAccount.closedPositions.filter(function(p){ return p.id===__clPos.id; });\n' +
  '  g.record("JVMCLOSE-1","PRECONDITION: the concurrent duplicate close was fired against a REAL open position and it did close, exactly once",\n' +
  '    !!__clPos.id&&__clClosed.length===1&&\n' +
  '    !paperAccount.openPositions.some(function(p){ return p.id===__clPos.id; })&&\n' +
  '    paperAccount.balance===parseFloat((__clBalBefore+__clClosed[0].pnl).toFixed(2)),\n' +
  '    "id="+String(__clPos.id)+" closed records="+__clClosed.length+", balance "+__clBalBefore+" -> "+\n' +
  '    paperAccount.balance+" (exactly one P&L application)");\n' +
  '  g.record("JVMCLOSE-2","the concurrent duplicate is rejected OUTRIGHT -- it never reaches the bid/ask fetch, let alone the ledger",\n' +
  '    __clFBACalls===1,\n' +
  '    "fetchBidAsk calls across two concurrent closes of the same id="+__clFBACalls+\n' +
  '    " (without the in-flight guard the second call fetches too, and only then finds the position gone)");\n' +
  // ══ MOGO-021 JVM EXIT MATH: the FILL SIDE, the ARITHMETIC and the LABELS ══════════════════
  // WHY THESE EXIST. JVMCLOSE-1 above asserts balance === balBefore + closedPos.pnl. That compares
  // TWO OUTPUTS OF THE SAME COMPUTATION: it dies only if the balance diverges FROM the recorded
  // P&L, and is blind to a wrong P&L, a wrong exit price, a wrong side or a wrong result label --
  // flipping the P&L sign flips both together and it still passes. Every other fixture in this
  // repository claiming to cover closePaperPosition matches SOURCE TEXT (getSource(...) containing
  // literal strings), which every behaviour-changing mutation leaves intact. An adversarial audit
  // ran 96 mutations against this 1,538-fixture gate; 47 killed nothing, concentrated right here.
  //
  // THE RULE THESE FIXTURES FOLLOW: every assertion is against a value THE FIXTURE CHOSE, computed
  // by hand from fixture literals, never against the record calculating itself. Positions are
  // opened through the real openPaperPosition and closed through the real closePaperPosition; the
  // only seams are globalThis.fetch and the /pricing response, both already used by this suite. No
  // protected function has its outcome stubbed, overridden or forced anywhere below.
  //
  // THE ARITHMETIC, done by hand ONCE and reused as literals:
  //   balance $10,000, risk 1% = $100. EUR_USD: pip 0.0001, pipValuePerLot = $10 per pip per lot.
  //   entry 1.10000, stop 1.09800 -> 20 pips of risk -> lots = 100/(20*10) = 0.50 exactly.
  //   A buy filled at bid 1.10500 is +50 pips -> 50 * $10 * 0.50 = +$250.00 -> balance $10,250.00.
  // The spread is deliberately ASYMMETRIC -- bid 1.10500, ask 1.10530, mid 1.10515 -- so the three
  // candidate fills are three DISTINGUISHABLE dollar figures: $250.00 on the bid, $265.00 on the
  // ask, $257.50 at the mid. Against a symmetric spread a wrong SIDE is indistinguishable from a
  // wrong MID, which is exactly how "buy closes on the ask" survived the whole gate.
  '  function jvmClosedRec(id){ return paperAccount.closedPositions.filter(function(p){ return p.id===id; })[0]||{}; }\n' +
  '  function jvmStillOpen(id){ return paperAccount.openPositions.some(function(p){ return p.id===id; }); }\n' +
  '  function jvmFreshAccount(){ pairData={}; paperAccount={balance:10000,openPositions:[],closedPositions:[]}; }\n' +
  // ── the buy: fill side, dollars, balance, label ──
  '  jvmFreshAccount();\n' +
  '  const __cbBuy=openPaperPosition("EUR_USD","buy",1.10000,1.09800,1.10600,"fixture");\n' +
  '  g.record("JVMCLOSE-3","PRECONDITION: the position the hand-computed dollars below assume -- 0.50 lots at $10 per pip from a $10,000 account",\n' +
  '    __cbBuy.lots===0.5&&__cbBuy.pipValueAtEntry===10&&__cbBuy.entry===1.10000&&__cbBuy.dir==="buy"&&\n' +
  '    __cbBuy.riskAmount===100&&paperAccount.balance===10000&&paperAccount.openPositions.length===1,\n' +
  '    "lots="+__cbBuy.lots+" pipValueAtEntry="+__cbBuy.pipValueAtEntry+" entry="+__cbBuy.entry+\n' +
  '    " risk="+__cbBuy.riskAmount+" balance="+paperAccount.balance+" (every literal below follows from these)");\n' +
  '  g.setBidAsk("1.10500","1.10530");\n' +
  '  await closePaperPosition(__cbBuy.id,false,"Win");\n' +
  '  const __cbRec=jvmClosedRec(__cbBuy.id);\n' +
  '  g.record("JVMCLOSE-4","a BUY is filled at the BID the fixture stubbed -- not the ask, not the mid",\n' +
  '    __cbRec.exitPrice===1.10500&&__cbRec.exitPrice!==1.10530&&__cbRec.exitPrice!==1.10515&&\n' +
  '    __cbRec.exitPrice!==__cbBuy.entry,\n' +
  '    "exitPrice="+__cbRec.exitPrice+" against stubbed bid 1.10500 / ask 1.10530 / mid 1.10515 / entry 1.10000");\n' +
  '  g.record("JVMCLOSE-5","the recorded P&L equals the HAND-COMPUTED dollars: +50 pips * $10 * 0.50 lots = +$250.00",\n' +
  '    __cbRec.pnl===250,\n' +
  '    "pnl="+__cbRec.pnl+" (the ask would be 265.00, the mid 257.50, an inverted sign -250.00)");\n' +
  '  g.record("JVMCLOSE-6","the balance equals the CONSTANT 10000 + 250 -- asserted against the fixture literal, never against balanceBefore + the record own pnl",\n' +
  '    paperAccount.balance===10250,\n' +
  '    "balance="+paperAccount.balance+" vs the literal 10250 (a sign flip moves both balance and pnl together and passes a before+pnl check)");\n' +
  '  g.record("JVMCLOSE-7","an automatic WIN is labelled Win and reasoned TAKE_PROFIT, and the position is gone from the book",\n' +
  '    __cbRec.result==="Win"&&__cbRec.closeReason==="TAKE_PROFIT"&&!jvmStillOpen(__cbBuy.id)&&\n' +
  '    paperAccount.closedPositions.filter(function(p){ return p.id===__cbBuy.id; }).length===1,\n' +
  '    "result="+__cbRec.result+" closeReason="+__cbRec.closeReason);\n' +
  // ── the losing buy: the same four values with the opposite sign, so no assertion above is
  //    satisfiable by a constant. TAKE_PROFIT/STOP_LOSS cannot be swapped without failing here.
  '  jvmFreshAccount();\n' +
  '  const __clBuy=openPaperPosition("EUR_USD","buy",1.10000,1.09800,1.10600,"fixture");\n' +
  '  g.setBidAsk("1.09700","1.09730");\n' +
  '  await closePaperPosition(__clBuy.id,false,"Loss");\n' +
  '  const __clRec=jvmClosedRec(__clBuy.id);\n' +
  '  g.record("JVMCLOSE-8","a LOSING buy fills at the bid too and debits the HAND-COMPUTED -30 pips * $10 * 0.50 = -$150.00",\n' +
  '    __clRec.exitPrice===1.09700&&__clRec.pnl===-150&&paperAccount.balance===9850,\n' +
  '    "exitPrice="+__clRec.exitPrice+" pnl="+__clRec.pnl+" balance="+paperAccount.balance+\n' +
  '    " vs literals 1.09700 / -150 / 9850 (ask would be -135.00, mid -142.50)");\n' +
  '  g.record("JVMCLOSE-9","and it is reasoned STOP_LOSS, not TAKE_PROFIT -- the two reasons are not interchangeable",\n' +
  '    __clRec.result==="Loss"&&__clRec.closeReason==="STOP_LOSS"&&__cbRec.closeReason==="TAKE_PROFIT"&&\n' +
  '    __clRec.closeReason!==__cbRec.closeReason,\n' +
  '    "winning close -> "+__cbRec.closeReason+", losing close -> "+__clRec.closeReason);\n' +
  // ── the SELL. Every P&L assertion in this repository is a long, so the (dir==="buy"?1:-1) term
  //    could be reduced to a constant 1 and nothing anywhere failed. A sell closes on the ASK.
  '  jvmFreshAccount();\n' +
  '  const __csSell=openPaperPosition("EUR_USD","sell",1.10000,1.10200,1.09400,"fixture");\n' +
  '  g.record("JVMCLOSE-10","PRECONDITION: the SELL is sized identically -- 0.50 lots at $10 per pip, entry 1.10000",\n' +
  '    __csSell.lots===0.5&&__csSell.pipValueAtEntry===10&&__csSell.entry===1.10000&&__csSell.dir==="sell"&&\n' +
  '    paperAccount.balance===10000,\n' +
  '    "lots="+__csSell.lots+" pipValueAtEntry="+__csSell.pipValueAtEntry+" dir="+__csSell.dir);\n' +
  '  g.setBidAsk("1.09400","1.09430");\n' +
  '  await closePaperPosition(__csSell.id,false,"Win");\n' +
  '  const __csRec=jvmClosedRec(__csSell.id);\n' +
  '  g.record("JVMCLOSE-11","a SELL is bought back at the ASK -- the opposite side from a buy, and not the mid",\n' +
  '    __csRec.exitPrice===1.09430&&__csRec.exitPrice!==1.09400&&__csRec.exitPrice!==1.09415,\n' +
  '    "exitPrice="+__csRec.exitPrice+" against stubbed bid 1.09400 / ask 1.09430 / mid 1.09415");\n' +
  '  g.record("JVMCLOSE-12","a SELL that falls is a PROFIT: hand-computed +57 pips * $10 * 0.50 = +$285.00, balance 10000 + 285",\n' +
  '    __csRec.pnl===285&&paperAccount.balance===10285&&__csRec.result==="Win",\n' +
  '    "pnl="+__csRec.pnl+" balance="+paperAccount.balance+" result="+__csRec.result+\n' +
  '    " -- dropping the short-side negation reports -285.00 and every long-only fixture still passes");\n' +
  // ── the MANUAL branch: this is where Win/Loss is classified from the P&L and where
  //    BREAK_EVEN_R_EPSILON lives. Both fixtures are the SAME position and differ ONLY in the bid.
  '  jvmFreshAccount();\n' +
  '  const __cmWin=openPaperPosition("EUR_USD","buy",1.10000,1.09800,1.10600,"fixture");\n' +
  '  g.setBidAsk("1.10500","1.10530");\n' +
  '  await closePaperPosition(__cmWin.id,true);\n' +
  '  const __cmWinRec=jvmClosedRec(__cmWin.id);\n' +
  '  g.record("JVMCLOSE-13","a MANUAL close in profit is classified Win / MANUAL_CLOSE -- realized R of 2.50 is not inside the break-even epsilon",\n' +
  '    __cmWinRec.pnl===250&&__cmWinRec.result==="Win"&&__cmWinRec.closeReason==="MANUAL_CLOSE"&&\n' +
  '    paperAccount.balance===10250,\n' +
  '    "pnl="+__cmWinRec.pnl+" (realized R = 250/100 = 2.50) result="+__cmWinRec.result+\n' +
  '    " closeReason="+__cmWinRec.closeReason+" -- widening BREAK_EVEN_R_EPSILON to 1e9 reports Break even / BREAK_EVEN here");\n' +
  '  jvmFreshAccount();\n' +
  '  const __cmFlat=openPaperPosition("EUR_USD","buy",1.10000,1.09800,1.10600,"fixture");\n' +
  '  g.setBidAsk("1.10000","1.10030");\n' +
  '  await closePaperPosition(__cmFlat.id,true);\n' +
  '  const __cmFlatRec=jvmClosedRec(__cmFlat.id);\n' +
  '  g.record("JVMCLOSE-14","SIBLING CONTROL, one variable away: the SAME manual close filled exactly at entry IS Break even / BREAK_EVEN",\n' +
  '    __cmFlatRec.exitPrice===1.10000&&__cmFlatRec.pnl===0&&__cmFlatRec.result==="Break even"&&\n' +
  '    __cmFlatRec.closeReason==="BREAK_EVEN"&&paperAccount.balance===10000,\n' +
  '    "only the stubbed bid changed (1.10500 -> 1.10000): pnl="+__cmFlatRec.pnl+" result="+__cmFlatRec.result+\n' +
  '    " closeReason="+__cmFlatRec.closeReason+" -- so JVMCLOSE-13 is not passing because Break even is unreachable");\n' +
  // ── the THIRD classifier: an automatic close with NO caller-supplied label falls back to
  //    exitPrice-vs-target. The discriminating case is a fill BELOW target that is nonetheless in
  //    PROFIT: the label must follow the target comparison, never the sign of the P&L.
  '  jvmFreshAccount();\n' +
  '  const __caHit=openPaperPosition("EUR_USD","buy",1.10000,1.09800,1.10400,"fixture");\n' +
  '  g.setBidAsk("1.10500","1.10530");\n' +
  '  await closePaperPosition(__caHit.id,false);\n' +
  '  const __caHitRec=jvmClosedRec(__caHit.id);\n' +
  '  g.record("JVMCLOSE-15","an UNLABELLED automatic close whose fill CLEARS the target is a Win / TAKE_PROFIT",\n' +
  '    __caHitRec.result==="Win"&&__caHitRec.closeReason==="TAKE_PROFIT"&&__caHitRec.exitPrice===1.10500&&\n' +
  '    __caHit.target===1.10400&&__caHitRec.pnl===250,\n' +
  '    "fill 1.10500 vs target "+__caHit.target+" -> "+__caHitRec.result+" / "+__caHitRec.closeReason);\n' +
  '  jvmFreshAccount();\n' +
  '  const __caMiss=openPaperPosition("EUR_USD","buy",1.10000,1.09800,1.10600,"fixture");\n' +
  '  g.setBidAsk("1.10500","1.10530");\n' +
  '  await closePaperPosition(__caMiss.id,false);\n' +
  '  const __caMissRec=jvmClosedRec(__caMiss.id);\n' +
  '  g.record("JVMCLOSE-16","and one that FALLS SHORT of the target is a Loss EVEN THOUGH IT BOOKED +$250 -- the label reads the target, not the P&L sign",\n' +
  '    __caMissRec.result==="Loss"&&__caMissRec.closeReason==="STOP_LOSS"&&__caMissRec.pnl===250&&\n' +
  '    paperAccount.balance===10250&&__caMiss.target===1.10600,\n' +
  '    "fill 1.10500 vs target "+__caMiss.target+" -> "+__caMissRec.result+" while pnl="+__caMissRec.pnl+\n' +
  '    " -- only two fixtures one variable apart can separate the target comparison from the P&L sign");\n' +
  // ── the post-await re-validation. The position vanishes WHILE the bid/ask fetch is in flight,
  //    which is the only window the second findIndex exists for. The seam is fetchBidAsk, wrapped
  //    as a pure pass-through: the real function is called and its real verdict returned; the
  //    wrapper only mutates the surrounding account state while the close is suspended on it,
  //    which is exactly what a sibling close resolving first does in production. Without the
  //    re-validation the stale index is reused and it splices out the WRONG POSITION.
  '  jvmFreshAccount();\n' +
  '  const __rvA=openPaperPosition("EUR_USD","buy",1.10000,1.09800,1.10600,"fixture");\n' +
  '  paperAccount.openPositions.push({id:"JVMCLOSE-SIBLING",pair:"GBP/USD",oPair:"GBP_USD",dir:"buy",\n' +
  '    entry:1.30000,stop:1.29800,target:1.30600,lots:0.5,riskAmount:100,pipValueAtEntry:10,\n' +
  '    openedAt:new Date().toISOString(),source:"fixture"});\n' +
  '  const __rvOrigFBA=fetchBidAsk; let __rvHits=0;\n' +
  '  fetchBidAsk=async function(p){ const r=await __rvOrigFBA.apply(this,arguments);\n' +
  '    if(++__rvHits===1){ const k=paperAccount.openPositions.findIndex(function(x){ return x.id===__rvA.id; });\n' +
  '      if(k>-1) paperAccount.openPositions.splice(k,1); }\n' +
  '    return r; };\n' +
  '  g.setBidAsk("1.10500","1.10530");\n' +
  '  const __rvRet=await closePaperPosition(__rvA.id,true);\n' +
  '  fetchBidAsk=__rvOrigFBA;\n' +
  '  g.record("JVMCLOSE-17","PRECONDITION: the position really did disappear DURING the bid/ask fetch, and a sibling was sitting behind it",\n' +
  '    __rvHits===1&&!jvmStillOpen(__rvA.id)&&__rvA.lots===0.5,\n' +
  '    "fetchBidAsk calls="+__rvHits+", the closing position was removed mid-await, sibling JVMCLOSE-SIBLING was at the index it vacated");\n' +
  '  g.record("JVMCLOSE-18","the POST-AWAIT re-validation abandons the close: no closed record, balance untouched at the literal 10000, and the SIBLING is still open",\n' +
  '    __rvRet===undefined&&paperAccount.closedPositions.length===0&&paperAccount.balance===10000&&\n' +
  '    jvmStillOpen("JVMCLOSE-SIBLING")&&paperAccount.openPositions.length===1,\n' +
  '    "returned="+String(__rvRet)+" closedPositions="+paperAccount.closedPositions.length+" balance="+\n' +
  '    paperAccount.balance+" open="+JSON.stringify(paperAccount.openPositions.map(function(p){return String(p.id);}))+\n' +
  '    " (reusing the pre-await index splices the SIBLING out and books the vanished position anyway)");\n' +
  // ── §18.31 F-2: the OTHER quadrant of the post-await index re-validation. JVMCLOSE-17/18 above
  //    remove the CLOSING position mid-await, so idx2 === -1 and the function returns BEFORE the
  //    splice -- they pin the early return, never the index. JVMCLOSE-18's own failure text says
  //    'reusing the pre-await index splices the SIBLING out and books the vanished position
  //    anyway', but independent verification proved that replacing splice(idx2,1) with
  //    splice(idx,1) kills ZERO of 2,222 fixtures. The quadrant that exercises the index is the
  //    one where the closing position SURVIVES and something BEFORE it goes away, shifting it.
  //    Shipped behaviour is correct; nothing proved it.
  //
  //    A closes during B's bid/ask await, so [A,B] becomes [B]: B's captured idx was 1, its real
  //    index is now 0. Under the mutant splice(1,1) removes NOTHING -- B is credited to the
  //    balance, pushed to closedPositions, journalled closed, and LEFT OPEN to be closed again.
  '  jvmFreshAccount();\n' +
  '  const __ixA=openPaperPosition("EUR_USD","buy",1.10000,1.09800,1.10600,"fixture");\n' +
  '  const __ixB=openPaperPosition("GBP_USD","buy",1.30000,1.29800,1.30600,"fixture");\n' +
  '  const __ixIdxBefore=paperAccount.openPositions.findIndex(function(x){return x.id===__ixB.id;});\n' +
  '  const __ixBalBefore=paperAccount.balance;\n' +
  '  const __ixOrigFBA=fetchBidAsk; let __ixHits=0;\n' +
  '  fetchBidAsk=async function(p){ const r=await __ixOrigFBA.apply(this,arguments);\n' +
  '    if(++__ixHits===1){ const k=paperAccount.openPositions.findIndex(function(x){ return x.id===__ixA.id; });\n' +
  '      if(k>-1) paperAccount.openPositions.splice(k,1); }\n' +
  '    return r; };\n' +
  '  g.setBidAsk("1.30500","1.30530");\n' +
  '  const __ixRet=await closePaperPosition(__ixB.id,true);\n' +
  '  fetchBidAsk=__ixOrigFBA;\n' +
  '  g.record("JVMCLOSE-18b","PRECONDITION: the position being closed really did SHIFT during the await -- it was at index 1 and a position ahead of it was removed, so the pre-await index is now stale by one",\n' +
  '    __ixHits===1&&__ixIdxBefore===1&&!jvmStillOpen(__ixA.id),\n' +
  '    "fetchBidAsk calls="+__ixHits+" indexBefore="+__ixIdxBefore+" siblingRemovedMidAwait="+String(!jvmStillOpen(__ixA.id)));\n' +
  '  g.record("JVMCLOSE-18c","the close uses the RE-VALIDATED index: the closed position is removed from openPositions exactly once, booked exactly once, and is NOT left open to be closed again",\n' +
  '    !jvmStillOpen(__ixB.id)&&paperAccount.openPositions.length===0&&paperAccount.closedPositions.length===1&&\n' +
  '    String(paperAccount.closedPositions[0].id)===String(__ixB.id)&&paperAccount.balance!==__ixBalBefore,\n' +
  '    "stillOpen="+String(jvmStillOpen(__ixB.id))+" open="+JSON.stringify(paperAccount.openPositions.map(function(p){return String(p.id);}))+\n' +
  '    " closed="+paperAccount.closedPositions.length+" balance="+paperAccount.balance+" (reusing the stale pre-await index splices NOTHING, so the trade is credited AND stays open)");\n' +
  // ── the failed-commit ROLLBACK. The commit is made to fail through STORAGE ONLY -- another tab
  //    is simulated by writing a newer fxhub_paper_version straight into the fixture localStorage.
  //    Nothing is stubbed: savePaperAccountGuarded reaches its own real STALE_VERSION branch.
  '  jvmFreshAccount();\n' +
  '  const __rbPos=openPaperPosition("EUR_USD","buy",1.10000,1.09800,1.10600,"fixture");\n' +
  '  const __rbSavedVer=localStorage.getItem("fxhub_paper_version");\n' +
  '  localStorage.setItem("fxhub_paper_version",String(paperAccountKnownVersion+5));\n' +
  '  g.setBidAsk("1.10500","1.10530");\n' +
  '  const __rbRet=await closePaperPosition(__rbPos.id,true);\n' +
  '  g.record("JVMCLOSE-19","a REJECTED ledger commit leaves the close UNAPPLIED IN MEMORY -- position still open, balance still the literal 10000, no closed record",\n' +
  '    !!__rbRet&&__rbRet.blocked===true&&typeof __rbRet.error==="string"&&\n' +
  '    paperAccount.balance===10000&&jvmStillOpen(__rbPos.id)&&paperAccount.closedPositions.length===0,\n' +
  '    "blocked="+String(__rbRet&&__rbRet.blocked)+" balance="+paperAccount.balance+" (never 10250) stillOpen="+\n' +
  '    jvmStillOpen(__rbPos.id)+" closedPositions="+paperAccount.closedPositions.length);\n' +
  '  localStorage.setItem("fxhub_paper_version",__rbSavedVer);\n' +
  '  const __rbRet2=await closePaperPosition(__rbPos.id,true);\n' +
  '  const __rbRec2=jvmClosedRec(__rbPos.id);\n' +
  '  g.record("JVMCLOSE-20","SIBLING CONTROL, one variable away: with the version conflict cleared the SAME close succeeds and books the same +$250.00",\n' +
  '    !!__rbRet2&&__rbRet2.committed===true&&__rbRec2.pnl===250&&paperAccount.balance===10250&&\n' +
  '    !jvmStillOpen(__rbPos.id),\n' +
  '    "only the stored fxhub_paper_version changed: pnl="+__rbRec2.pnl+" balance="+paperAccount.balance+\n' +
  '    " -- so JVMCLOSE-19 is not passing because this close could never have completed");\n' +
  // ── the missing pip value. A position carrying no pipValueAtEntry on a pair with no conversion
  //    rate loaded cannot be priced in dollars, and the close must REFUSE rather than guess. The
  //    trap: deleting the guard does NOT produce NaN -- null multiplies to ZERO, so the balance is
  //    unchanged and a balance assertion alone proves nothing. The position and the closed-record
  //    count are what discriminate.
  '  jvmFreshAccount();\n' +
  '  paperAccount.openPositions.push({id:"JVMCLOSE-NOPIP",pair:"EUR/GBP",oPair:"EUR_GBP",dir:"buy",\n' +
  '    entry:0.85000,stop:0.84800,target:0.85600,lots:0.5,riskAmount:100,\n' +
  '    openedAt:new Date().toISOString(),source:"fixture"});\n' +
  '  g.setBidAsk("0.85500","0.85530");\n' +
  '  const __npRet=await closePaperPosition("JVMCLOSE-NOPIP",true);\n' +
  '  g.record("JVMCLOSE-21","with NO pip value available the close is REFUSED and the position is left open -- it is never booked at a fabricated P&L",\n' +
  '    pipValuePerLot("EUR_GBP")===null&&__npRet===undefined&&jvmStillOpen("JVMCLOSE-NOPIP")&&\n' +
  '    paperAccount.closedPositions.length===0&&paperAccount.balance===10000,\n' +
  '    "pipValuePerLot(EUR_GBP)="+String(pipValuePerLot("EUR_GBP"))+" returned="+String(__npRet)+\n' +
  '    " stillOpen="+jvmStillOpen("JVMCLOSE-NOPIP")+" closedPositions="+paperAccount.closedPositions.length+\n' +
  '    " (dropping the guard books it at pnl 0, since null multiplies to zero and the balance never moves)");\n' +
  '  pairData["USD_GBP"]={price:0.80000};\n' +
  '  const __npRet2=await closePaperPosition("JVMCLOSE-NOPIP",true);\n' +
  '  const __npRec2=jvmClosedRec("JVMCLOSE-NOPIP");\n' +
  '  g.record("JVMCLOSE-22","SIBLING CONTROL, one variable away: once a USD_GBP rate exists the SAME position closes at the hand-computed +50 pips * $12.50 * 0.50 = +$312.50",\n' +
  '    pipValuePerLot("EUR_GBP")===12.5&&!!__npRet2&&__npRec2.exitPrice===0.85500&&__npRec2.pnl===312.5&&\n' +
  '    paperAccount.balance===10312.5&&!jvmStillOpen("JVMCLOSE-NOPIP"),\n' +
  '    "only pairData.USD_GBP changed: pipValuePerLot="+pipValuePerLot("EUR_GBP")+" exitPrice="+__npRec2.exitPrice+\n' +
  '    " pnl="+__npRec2.pnl+" balance="+paperAccount.balance+" -- so JVMCLOSE-21 is not passing because this close was impossible");\n' +
  // ══ MOGO-021 JVM AUTOMATIC EXIT DETECTION: checkPaperPositions ════════════════════════════
  // NO FIXTURE ANYWHERE CALLED THIS FUNCTION. It could be reduced to a bare `return;` and the whole
  // 1,538-fixture gate stayed green -- JVM would simply have stopped taking profits and stopping
  // out, silently. It is synchronous, so a direct unit fixture is sufficient and honest.
  //
  // The spy below is a PURE PASS-THROUGH: it records the arguments checkPaperPositions hands to
  // closePaperPosition, calls the real function, returns its real promise unaltered, and collects
  // the promises so the assertions can await them deterministically rather than counting
  // microtasks. No outcome is forced. Both the call arguments AND the resulting closed record are
  // asserted, because either alone leaves half the path unproven.
  '  async function jvmExitSweep(){ const __oC=closePaperPosition; const calls=[],proms=[];\n' +
  '    closePaperPosition=function(id,manual,autoResult){ calls.push({id:String(id),manual:manual,autoResult:autoResult});\n' +
  '      const pr=__oC.apply(this,arguments); proms.push(pr); return pr; };\n' +
  '    try{ checkPaperPositions(); } finally { closePaperPosition=__oC; }\n' +
  '    await Promise.all(proms); return calls; }\n' +
  '  function jvmSeedPosition(id,dir,entry,stop,target){\n' +
  '    paperAccount.openPositions.push({id:id,pair:"EUR/USD",oPair:"EUR_USD",dir:dir,entry:entry,stop:stop,\n' +
  '      target:target,lots:0.5,riskAmount:100,pipValueAtEntry:10,openedAt:new Date().toISOString(),source:"fixture"}); }\n' +
  // TARGET CROSSED. The fill is deliberately BELOW the target (bid 1.10500 vs target 1.10600):
  // the Win label must come from the level the CALLER saw crossed, not from re-deriving it from
  // the post-spread fill -- which is the documented contract and would misclassify this as a Loss.
  '  jvmFreshAccount();\n' +
  '  jvmSeedPosition("JVMEXIT-WIN","buy",1.10000,1.09800,1.10600);\n' +
  '  pairData["EUR_USD"]={price:1.10700};\n' +
  '  g.setBidAsk("1.10500","1.10530");\n' +
  '  const __exWin=await jvmExitSweep();\n' +
  '  const __exWinRec=jvmClosedRec("JVMEXIT-WIN");\n' +
  '  g.record("JVMEXIT-1","a live price THROUGH the target closes the position exactly once, as an AUTOMATIC Win",\n' +
  '    __exWin.length===1&&__exWin[0].id==="JVMEXIT-WIN"&&__exWin[0].manual===false&&__exWin[0].autoResult==="Win"&&\n' +
  '    paperAccount.closedPositions.length===1&&__exWinRec.result==="Win"&&__exWinRec.closeReason==="TAKE_PROFIT",\n' +
  '    "price 1.10700 vs target 1.10600 -> closePaperPosition("+JSON.stringify(__exWin)+"), record result="+\n' +
  '    __exWinRec.result+"/"+__exWinRec.closeReason);\n' +
  '  g.record("JVMEXIT-2","and the exit is booked at the hand-computed +50 pips * $10 * 0.50 = +$250.00, balance 10000 + 250",\n' +
  '    __exWinRec.exitPrice===1.10500&&__exWinRec.pnl===250&&paperAccount.balance===10250&&\n' +
  '    !jvmStillOpen("JVMEXIT-WIN"),\n' +
  '    "exitPrice="+__exWinRec.exitPrice+" pnl="+__exWinRec.pnl+" balance="+paperAccount.balance+\n' +
  '    " -- the fill 1.10500 is BELOW the target, so the Win cannot have been re-derived from it");\n' +
  // STOP CROSSED.
  '  jvmFreshAccount();\n' +
  '  jvmSeedPosition("JVMEXIT-LOSS","buy",1.10000,1.09800,1.10600);\n' +
  '  pairData["EUR_USD"]={price:1.09700};\n' +
  '  g.setBidAsk("1.09700","1.09730");\n' +
  '  const __exLoss=await jvmExitSweep();\n' +
  '  const __exLossRec=jvmClosedRec("JVMEXIT-LOSS");\n' +
  '  g.record("JVMEXIT-3","a live price THROUGH the stop closes the position exactly once, as an AUTOMATIC Loss -- the opposite label from the same code path",\n' +
  '    __exLoss.length===1&&__exLoss[0].autoResult==="Loss"&&__exLoss[0].manual===false&&\n' +
  '    __exLossRec.result==="Loss"&&__exLossRec.closeReason==="STOP_LOSS"&&\n' +
  '    __exLossRec.pnl===-150&&paperAccount.balance===9850,\n' +
  '    "price 1.09700 vs stop 1.09800 -> "+JSON.stringify(__exLoss)+", pnl="+__exLossRec.pnl+\n' +
  '    " balance="+paperAccount.balance+" (Win and Loss are not interchangeable at this call site)");\n' +
  // NEGATIVE CONTROL, one variable from both positives: the SAME position, a price INSIDE the
  // bracket. Nothing is called at all.
  '  jvmFreshAccount();\n' +
  '  jvmSeedPosition("JVMEXIT-INSIDE","buy",1.10000,1.09800,1.10600);\n' +
  '  pairData["EUR_USD"]={price:1.10100};\n' +
  '  g.setBidAsk("1.10100","1.10130");\n' +
  '  const __exInside=await jvmExitSweep();\n' +
  '  g.record("JVMEXIT-4","NEGATIVE CONTROL: a price INSIDE the bracket closes nothing -- closePaperPosition is not called at all",\n' +
  '    __exInside.length===0&&jvmStillOpen("JVMEXIT-INSIDE")&&paperAccount.closedPositions.length===0&&\n' +
  '    paperAccount.balance===10000,\n' +
  '    "price 1.10100 sits between stop 1.09800 and target 1.10600: calls="+__exInside.length+\n' +
  '    " stillOpen="+jvmStillOpen("JVMEXIT-INSIDE")+" balance="+paperAccount.balance);\n' +
  // THE AMBIGUITY CASE -- the ONLY fixture that can detect a reordering of the two branches.
  // It requires a position in which BOTH levels read as crossed on a single tick, and for a buy
  // that is only possible when the stop sits ABOVE the target. That is a DEGENERATE position by
  // construction, stated plainly rather than dressed up as a market scenario: no live price series
  // can produce this state on a coherent bracket (stop < entry < target), so it is seeded
  // directly. It is not hypothetical either -- it is exactly the state a mis-applied stop
  // adjustment leaves behind, and it is the state in which the evaluation ORDER decides the
  // recorded result. The shipped ordering checks the target first and must record a Win.
  '  jvmFreshAccount();\n' +
  '  jvmSeedPosition("JVMEXIT-BOTH","buy",1.10000,1.10500,1.10200);\n' +
  '  pairData["EUR_USD"]={price:1.10300};\n' +
  '  g.setBidAsk("1.10300","1.10330");\n' +
  // Read back the state the sweep is about to see, so this precondition is an assertion about the
  // ACTUAL seeded book and price feed and fails if either drifts -- not a restatement of literals,
  // which would be true for every input and could never fail.
  '  const __exBothSeed=paperAccount.openPositions.filter(function(p){ return p.id==="JVMEXIT-BOTH"; })[0]||{};\n' +
  '  const __exBothLive=(pairData["EUR_USD"]||{}).price;\n' +
  '  const __exBoth=await jvmExitSweep();\n' +
  '  const __exBothRec=jvmClosedRec("JVMEXIT-BOTH");\n' +
  '  g.record("JVMEXIT-5","PRECONDITION: the position actually in the book, at the price actually in the feed, satisfies BOTH crossing tests on the same tick",\n' +
  '    __exBothSeed.dir==="buy"&&__exBothLive>=__exBothSeed.target&&__exBothLive<=__exBothSeed.stop&&\n' +
  '    __exBothSeed.stop>__exBothSeed.target,\n' +
  '    "live "+__exBothLive+" >= target "+__exBothSeed.target+" AND live "+__exBothLive+" <= stop "+__exBothSeed.stop+\n' +
  '    " -- both hitTarget and hitStop are true, which for a buy requires the degenerate stop-above-target bracket seeded here");\n' +
  // D3B REWRITE. This fixture previously asserted that the degenerate bracket produces a WIN of
  // +$150 and a balance of 10150 -- i.e. it encoded a FABRICATED WINNER from geometry that cannot
  // exist, as expected behaviour. Both hitTarget and hitStop can only be true together when
  // stop >= target, and for a valid buy stop < entry < target, so the branch-ordering question is
  // reachable ONLY through a wrong-side-stop position. D3B quarantines exactly that, so the
  // ordering is now unreachable by construction and the correct assertion is the stronger one:
  // NO close of ANY label is produced, and the balance does not move. Not a weakened test --
  // previously one fabricated outcome was permitted, now none is.
  '  g.record("JVMEXIT-6","D3B: the degenerate stop-above-target bracket is QUARANTINED, so neither exit branch fires and no fabricated Win is booked (was: TARGET-FIRST ordering records a Win of +150)",\n' +
  '    __exBoth.length===0&&paperAccount.closedPositions.length===0&&!__exBothRec.result&&\n' +
  '    paperAccount.balance===10000&&jvmStillOpen("JVMEXIT-BOTH"),\n' +
  '    "calls="+JSON.stringify(__exBoth)+" closed="+paperAccount.closedPositions.length+" balance="+paperAccount.balance+\n' +
  '    " -- the position remains open, byte-identical and inspectable; it is barred from processing, not deleted");\n' +
  // SIBLING CONTROL for the ambiguity fixture: the SAME degenerate position, one variable moved
  // (the live price), so the stop branch is the only one that can fire. Without this, JVMEXIT-6
  // could be passing simply because this bracket always yields Win.
  '  jvmFreshAccount();\n' +
  '  jvmSeedPosition("JVMEXIT-BOTH2","buy",1.10000,1.10500,1.10200);\n' +
  '  pairData["EUR_USD"]={price:1.10100};\n' +
  '  g.setBidAsk("1.10100","1.10130");\n' +
  '  const __exOne=await jvmExitSweep();\n' +
  '  const __exOneRec=jvmClosedRec("JVMEXIT-BOTH2");\n' +
  // D3B REWRITE. Previously asserted the same degenerate bracket records a LOSS whose pnl is
  // +50 -- POSITIVE -- its own text conceding "the label follows the level crossed, not the
  // money". That is a fabricated loser with a positive P&L, from a position that cannot exist.
  // The quarantine removes it at ANY live price, which is what this control now proves: the
  // outcome does not depend on where the price sits, because the position is never processed.
  '  g.record("JVMEXIT-7","D3B SIBLING CONTROL: the SAME degenerate bracket is quarantined at a DIFFERENT live price too, so the refusal is a property of the geometry and not of where price happens to sit (was: records a Loss with a POSITIVE pnl of +50)",\n' +
  '    __exOne.length===0&&paperAccount.closedPositions.length===0&&!__exOneRec.result&&\n' +
  '    paperAccount.balance===10000&&jvmStillOpen("JVMEXIT-BOTH2"),\n' +
  '    "only the live price changed (1.10300 -> 1.10100): calls="+JSON.stringify(__exOne)+\n' +
  '    " closed="+paperAccount.closedPositions.length+" balance="+paperAccount.balance);\n' +
  // ══ 🔴 MOGO-021 §18.26: three MONEY-PATH mutations inside PROTECTED functions had no
  //    behavioural coverage at all -- the drift baseline was their only control, and a drift hash
  //    says the bytes did not change, never that the arithmetic is right. Each survived the full
  //    2,207-fixture gate when an independent sweep injected it.
  //
  // (a) BOUNDARY: exactly AT the target. `live>=pos.target` -> `live>` means a price that touches
  //     the target to the pip never takes profit, and the trade runs on to its stop.
  '  jvmFreshAccount();\n' +
  '  jvmSeedPosition("JVMEXIT-ATTARGET","buy",1.10000,1.09800,1.10600);\n' +
  '  pairData["EUR_USD"]={price:1.10600};\n' +           // EXACTLY the target, not through it
  '  g.setBidAsk("1.10600","1.10630");\n' +
  '  const __exAt=await jvmExitSweep();\n' +
  '  const __exAtRec=jvmClosedRec("JVMEXIT-ATTARGET");\n' +
  '  g.record("JVMEXIT-10","a live price EXACTLY at the target takes profit -- the comparison is inclusive, so a trade that touches its target to the pip is not left running on to its stop",\n' +
  '    __exAt.length===1&&__exAt[0].autoResult==="Win"&&__exAtRec.result==="Win"&&\n' +
  '    __exAtRec.closeReason==="TAKE_PROFIT",\n' +
  '    "live 1.10600 === target 1.10600 -> "+JSON.stringify(__exAt)+" record="+__exAtRec.result+"/"+__exAtRec.closeReason);\n' +
  // §18.27: JVMEXIT-10 closed ONE of the FOUR exit boundaries -- the buy target. Independent
  //   verification showed the other three each survived the whole gate, and two of them are the
  //   STOP side: a price that touches the stop to the pip does not stop out and the position runs
  //   on past its stop with no bound. That is strictly worse than the target case the first
  //   fixture was written for. All four quadrants are pinned here.
  '  jvmFreshAccount();\n' +
  '  jvmSeedPosition("JVMEXIT-BUYSTOP","buy",1.10000,1.09800,1.10600);\n' +
  '  pairData["EUR_USD"]={price:1.09800};\n' +           // EXACTLY the stop
  '  g.setBidAsk("1.09800","1.09830");\n' +
  '  const __exBS=await jvmExitSweep();\n' +
  '  const __exBSRec=jvmClosedRec("JVMEXIT-BUYSTOP");\n' +
  '  g.record("JVMEXIT-13","a LONG whose live price is EXACTLY at its stop stops out -- the comparison is inclusive, so a position that touches its stop to the pip is not left running on past it with no bound",\n' +
  '    __exBS.length===1&&__exBS[0].autoResult==="Loss"&&__exBSRec.result==="Loss"&&\n' +
  '    __exBSRec.closeReason==="STOP_LOSS",\n' +
  '    "live 1.09800 === stop 1.09800 -> "+JSON.stringify(__exBS)+" record="+__exBSRec.result+"/"+__exBSRec.closeReason);\n' +
  '  jvmFreshAccount();\n' +
  '  jvmSeedPosition("JVMEXIT-SELLTGT","sell",1.30000,1.31000,1.28000);\n' +
  '  pairData["EUR_USD"]={price:1.28000};\n' +           // EXACTLY the short target
  '  g.setBidAsk("1.28000","1.28030");\n' +
  '  const __exST=await jvmExitSweep();\n' +
  '  const __exSTRec=jvmClosedRec("JVMEXIT-SELLTGT");\n' +
  '  g.record("JVMEXIT-14","a SHORT whose live price is EXACTLY at its target takes profit -- the inclusive comparison holds on the sell side too, not only the buy side JVMEXIT-10 pins",\n' +
  '    __exST.length===1&&__exST[0].autoResult==="Win"&&__exSTRec.result==="Win"&&\n' +
  '    __exSTRec.closeReason==="TAKE_PROFIT",\n' +
  '    "live 1.28000 === short target 1.28000 -> "+JSON.stringify(__exST)+" record="+__exSTRec.result+"/"+__exSTRec.closeReason);\n' +
  '  jvmFreshAccount();\n' +
  '  jvmSeedPosition("JVMEXIT-SELLSTOP","sell",1.30000,1.31000,1.28000);\n' +
  '  pairData["EUR_USD"]={price:1.31000};\n' +           // EXACTLY the short stop
  '  g.setBidAsk("1.31000","1.31030");\n' +
  '  const __exSS=await jvmExitSweep();\n' +
  '  const __exSSRec=jvmClosedRec("JVMEXIT-SELLSTOP");\n' +
  '  g.record("JVMEXIT-15","a SHORT whose live price is EXACTLY at its stop stops out -- the fourth and last exit boundary, and the second of the two RISK-LIMITING ones that had no coverage at all",\n' +
  '    __exSS.length===1&&__exSS[0].autoResult==="Loss"&&__exSSRec.result==="Loss"&&\n' +
  '    __exSSRec.closeReason==="STOP_LOSS",\n' +
  '    "live 1.31000 === short stop 1.31000 -> "+JSON.stringify(__exSS)+" record="+__exSSRec.result+"/"+__exSSRec.closeReason);\n' +
  // (b) The pip value is FIXED AT ENTRY, never re-derived at close. Seeded deliberately at 25 --
  //     a value pipValuePerLot would never produce for this pair -- so a recomputation at close
  //     yields different money and this literal cannot be satisfied by both formulas.
  '  jvmFreshAccount();\n' +
  '  paperAccount.openPositions.push({id:"JVMEXIT-PIPFIX",pair:"EUR/USD",oPair:"EUR_USD",dir:"buy",\n' +
  '    entry:1.10000,stop:1.09800,target:1.10600,lots:0.5,riskAmount:100,pipValueAtEntry:25,\n' +
  '    openedAt:new Date().toISOString(),source:"fixture"});\n' +
  '  pairData["EUR_USD"]={price:1.10700};\n' +
  '  g.setBidAsk("1.10500","1.10530");\n' +
  '  const __exPip=await jvmExitSweep();\n' +
  '  const __exPipRec=jvmClosedRec("JVMEXIT-PIPFIX");\n' +
  '  g.record("JVMEXIT-11","the close uses the pip value FIXED AT ENTRY, not one re-derived at close time -- 50 pips * $25 (the entry value) * 0.5 lots = exactly +$625.00, where a recomputation would have produced $250.00",\n' +
  '    __exPipRec.pnl===625&&paperAccount.balance===10625,\n' +
  '    "pnl="+__exPipRec.pnl+" balance="+paperAccount.balance+" (pipValueAtEntry 25, not the ~10 a re-derivation gives)");\n' +
  // (c) A MANUAL close with no live bid/ask AND no cached price must still fill, at the entry --
  //     collapsing the fallback makes it silently NO-OP and the position stays open forever.
  '  jvmFreshAccount();\n' +
  '  jvmSeedPosition("JVMEXIT-NOFEED","buy",1.10000,1.09800,1.10600);\n' +
  '  delete pairData["EUR_USD"];\n' +
  '  g.setPriceOk(false);\n' +
  '  const __exNo=await closePaperPosition("JVMEXIT-NOFEED",true,null);\n' +
  '  g.setPriceOk(true);\n' +
  '  const __exNoRec=jvmClosedRec("JVMEXIT-NOFEED");\n' +
  '  g.record("JVMEXIT-12","a MANUAL close with no live bid/ask and no cached price still closes, filled at the entry for exactly $0.00 -- it does not silently no-op and strand the position open",\n' +
  '    !!__exNoRec&&__exNoRec.exitPrice===1.10000&&__exNoRec.pnl===0&&\n' +
  '    paperAccount.openPositions.filter(function(p){return p.id==="JVMEXIT-NOFEED";}).length===0,\n' +
  '    "exitPrice="+__exNoRec.exitPrice+" pnl="+__exNoRec.pnl+" stillOpen="+\n' +
  '    paperAccount.openPositions.filter(function(p){return p.id==="JVMEXIT-NOFEED";}).length);\n' +
  '  g.resetBidAsk(); jvmFreshAccount();\n' +
  // ══ 🔴 MOGO-021 §18.23: JVM's SHORT side of checkPaperPositions had no fixture ══════════════
  // Every jvmSeedPosition call above passes "buy". An independent completeness audit showed a
  // sell-only mutation of the exit comparison therefore survives the entire gate -- on PROTECTED,
  // money-moving code that decides TAKE_PROFIT vs STOP_LOSS. ALEX has both sides (F3.7-F3.9,
  // F4.10-F4.12); JVM had one. A short position profits as price FALLS, so the target sits BELOW
  // the entry and the stop ABOVE it -- the mirror of every fixture above.
  '  jvmFreshAccount();\n' +
  '  jvmSeedPosition("JVMEXIT-SELLWIN","sell",1.30000,1.31000,1.28000);\n' +
  '  pairData["EUR_USD"]={price:1.27900};\n' +
  '  g.setBidAsk("1.27900","1.27930");\n' +
  '  const __exSellWin=await jvmExitSweep();\n' +
  '  const __exSellWinRec=jvmClosedRec("JVMEXIT-SELLWIN");\n' +
  '  g.record("JVMEXIT-8","a SHORT whose live price falls THROUGH its target closes exactly once as an AUTOMATIC Win -- the mirror of JVMEXIT-1, and the only fixture that exercises the sell branch of the exit comparison",\n' +
  '    __exSellWin.length===1&&__exSellWin[0].id==="JVMEXIT-SELLWIN"&&__exSellWin[0].manual===false&&\n' +
  '    __exSellWin[0].autoResult==="Win"&&__exSellWinRec.result==="Win"&&__exSellWinRec.closeReason==="TAKE_PROFIT",\n' +
  '    "price 1.27900 vs SHORT target 1.28000 -> "+JSON.stringify(__exSellWin)+" record="+\n' +
  '    __exSellWinRec.result+"/"+__exSellWinRec.closeReason);\n' +
  '  jvmFreshAccount();\n' +
  '  jvmSeedPosition("JVMEXIT-SELLLOSS","sell",1.30000,1.31000,1.28000);\n' +
  '  pairData["EUR_USD"]={price:1.31100};\n' +
  '  g.setBidAsk("1.31100","1.31130");\n' +
  '  const __exSellLoss=await jvmExitSweep();\n' +
  '  const __exSellLossRec=jvmClosedRec("JVMEXIT-SELLLOSS");\n' +
  '  g.record("JVMEXIT-9","SIBLING CONTROL: the SAME short whose price rises THROUGH its stop records a Loss with STOP_LOSS -- so JVMEXIT-8 is the direction being read correctly and not a branch that always says Win",\n' +
  '    __exSellLoss.length===1&&__exSellLoss[0].autoResult==="Loss"&&\n' +
  '    __exSellLossRec.result==="Loss"&&__exSellLossRec.closeReason==="STOP_LOSS",\n' +
  '    "price 1.31100 vs SHORT stop 1.31000 -> "+JSON.stringify(__exSellLoss)+" record="+\n' +
  '    __exSellLossRec.result+"/"+__exSellLossRec.closeReason);\n' +
  // ══ 🔴 MOGO-021 §18.23: SCANNER CADENCE -- nothing knew the scanner is ever STARTED ═════════
  // An independent completeness audit found both 60-second timers could be DELETED OUTRIGHT -- a
  // total scanning outage in production -- and the whole gate stayed green. Every runner stubs
  // setInterval and every fixture calls scanAll()/alexGLivePollTick() DIRECTLY, so the evidence
  // proved ONE SWEEP, never that sweeps HAPPEN. The word "continuous" in the standard was untested.
  // This harness is the only one that records {fn,ms}, so the assertions live here.
  '  alexGLiveInterval=null;\n' +
  // The starter is a no-op unless polling SHOULD run (auto-trading on, or an open ALEX position).
  // Enabling it is the precondition, and JVMTMR-6 turns it back off as the negative control.
  '  alexGAutoTrading=alexGAutoTrading||{}; alexGAutoTrading.enabled=true;\n' +
  '  g.record("JVMTMR-2b","PRECONDITION: live polling SHOULD run in this state, so the starter below is not a no-op",\n' +
  '    alexGLivePollingShouldRun()===true,"shouldRun="+alexGLivePollingShouldRun());\n' +
  '  const __tmrBefore=g.liveTimersFor(alexGLivePollTick);\n' +
  '  startAlexGLivePollingIfNeeded();\n' +
  '  const __tmrAfter=g.liveTimersFor(alexGLivePollTick);\n' +
  '  const __tmrMs=g.liveTimerMsFor(alexGLivePollTick);\n' +
  '  g.record("JVMTMR-3","the ALEX live poller is ARMED by its own starter -- one live handle where there was none, so a deleted setInterval is a failure rather than a silent outage",\n' +
  '    __tmrBefore===0&&__tmrAfter===1,\n' +
  '    "handles before="+__tmrBefore+" after="+__tmrAfter);\n' +
  '  g.record("JVMTMR-4","and it is armed at exactly 60000ms -- the period is asserted, not just the existence of a timer, so shortening or lengthening the sweep is caught",\n' +
  '    __tmrMs===60000,"period="+__tmrMs);\n' +
  '  startAlexGLivePollingIfNeeded();\n' +
  '  g.record("JVMTMR-5","calling the starter a SECOND time does not strand a second sweep -- the double-start guard holds, so a re-entry cannot double every scan",\n' +
  '    g.liveTimersFor(alexGLivePollTick)===1,"handles after a second start="+g.liveTimersFor(alexGLivePollTick));\n' +
  '  const __alexIntervalBefore=alexGLiveInterval;\n' +
  '  alexGAutoTrading.enabled=false;\n' +
  '  stopAlexGLivePollingIfDone();\n' +
  '  g.record("JVMTMR-6","NEGATIVE CONTROL: when live polling should no longer run the handle is CLEARED, so JVMTMR-3 is a real arming rather than a counter that only ever increases",\n' +
  '    __alexIntervalBefore!=null&&g.liveTimersFor(alexGLivePollTick)===0&&alexGLiveInterval===null,\n' +
  '    "before="+String(__alexIntervalBefore!=null)+" handles now="+g.liveTimersFor(alexGLivePollTick));\n' +
  '  alexGAutoTrading.enabled=true; alexGLiveInterval=null;\n' +
  '  g.resetBidAsk(); jvmFreshAccount();\n' +
  // ══ MOGO-021 LEAKED HOURLY TIMER ══════════════════════════════════════════════════════════
  // disconnect() cleared scanInterval and countdownInterval but NOT autoScanTimer, and initAll then
  // assigned a NEW hourly timer over the handle -- so the old one kept running with nothing left to
  // stop it, and every disconnect/reconnect cycle permanently added one top-down scan per hour.
  // That scan writes scanData[pair].bucket, which IS checkAutoTrades' eligibility gate, so the leak
  // is trading-adjacent rather than cosmetic. Both halves are proven separately below, because
  // either one alone masks the other in the end-to-end cycle.
  '  g.setMode("flat"); structuralAOICache={}; pairData={};\n' +
  '  if(autoScanTimer){ clearInterval(autoScanTimer); autoScanTimer=null; }\n' +
  // POSITIVE CONTROL FIRST. Without it, every count below could be a harness that simply cannot
  // report more than one live timer, and the two fixtures after it would be vacuous by construction.
  '  const __ctlA=setInterval(runAutoTopDownScan,60*60*1000);\n' +
  '  const __ctlB=setInterval(runAutoTopDownScan,60*60*1000);\n' +
  '  const __ctlBoth=g.liveTimersFor(runAutoTopDownScan);\n' +
  '  clearInterval(__ctlA); const __ctlOne=g.liveTimersFor(runAutoTopDownScan); clearInterval(__ctlB);\n' +
  '  g.record("JVMTMR-0","POSITIVE CONTROL: a STRANDED hourly timer is actually observable -- two live handles read as two, one as one, none as none",\n' +
  '    __ctlBoth===2&&__ctlOne===1&&g.liveTimersFor(runAutoTopDownScan)===0&&__ctlA!==__ctlB,\n' +
  '    "two handles -> "+__ctlBoth+" live, after clearing one -> "+__ctlOne+", after clearing both -> "+g.liveTimersFor(runAutoTopDownScan));\n' +
  // lastRunAt is fresh on purpose: `stale` must be false so neither toggleAutoScan nor initAll kicks
  // off a real top-down scan. This fixture is about the HANDLE, not about the scan.
  '  autoScan={enabled:true,lastRunAt:new Date().toISOString()};\n' +
  '  document.getElementById("autoScanToggle").checked=true;\n' +
  '  toggleAutoScan();\n' +
  '  const __tmrOn=g.liveTimersFor(runAutoTopDownScan),__tmrHandleOn=autoScanTimer;\n' +
  '  disconnect();\n' +
  '  g.record("JVMTMR-1","DISCONNECT stops the hourly top-down timer instead of stranding it unstoppable",\n' +
  '    __tmrOn===1&&__tmrHandleOn!=null&&autoScanTimer===null&&g.liveTimersFor(runAutoTopDownScan)===0,\n' +
  '    "before disconnect: handle="+String(__tmrHandleOn)+" live="+__tmrOn+"; after disconnect: handle="+\n' +
  '    String(autoScanTimer)+" live="+g.liveTimersFor(runAutoTopDownScan));\n' +
  // The RECONNECT half. initAll assigns the hourly timer, and a second initAll must not leave the
  // first one running behind an overwritten handle -- the guard toggleAutoScan always had.
  '  cfg.key="fixture"; cfg.accountId="acct"; cfg.env="practice";\n' +
  '  try{ initAll(); }catch(e){}\n' +
  '  const __tmrH1=autoScanTimer,__tmrAfter1=g.liveTimersFor(runAutoTopDownScan);\n' +
  '  try{ initAll(); }catch(e){}\n' +
  '  const __tmrH2=autoScanTimer,__tmrAfter2=g.liveTimersFor(runAutoTopDownScan);\n' +
  '  g.record("JVMTMR-2","a SECOND initAll cannot strand the running timer behind an overwritten handle",\n' +
  '    __tmrAfter1===1&&__tmrAfter2===1&&__tmrH1!=null&&__tmrH2!=null&&__tmrH1!==__tmrH2,\n' +
  '    "after one initAll: handle="+String(__tmrH1)+" live="+__tmrAfter1+"; after a second: handle="+\n' +
  '    String(__tmrH2)+" live="+__tmrAfter2+" (unguarded, the first handle would still be running)");\n' +
  '  if(autoScanTimer){ clearInterval(autoScanTimer); autoScanTimer=null; }\n' +
  '  autoScan={enabled:false,lastRunAt:null};\n' +

  '  return g;\n})();'
);

wrapped(g).then(function(){
  let pass=0,fail=0;
  results.forEach(function(r){
    if(r.pass){pass++;console.log('PASS -- '+r.id+': '+r.desc+(r.detail?'  ['+r.detail+']':''));}
    else{fail++;console.log('FAIL -- '+r.id+': '+r.desc+(r.detail?'  ['+r.detail+']':''));}
  });
  console.log('---');
  console.log(results.length+' fixtures, '+pass+' PASS, '+fail+' FAIL');
}).catch(function(e){
  console.log('EXECUTION ERROR: '+(e&&e.message?e.message:String(e)));
  console.log('---');
  console.log(results.length+' fixtures, 0 PASS, '+(results.length||1)+' FAIL');
});
