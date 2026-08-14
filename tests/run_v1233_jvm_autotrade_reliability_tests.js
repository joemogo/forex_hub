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
globalThis.setInterval=()=>++__t;globalThis.clearInterval=()=>{};
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
let __candleCount=60,__priceOk=true,__mode='flat',__shortPair=null,__shortAll=false;
// Holds one instrument's candle fetch open so a SECOND scanAll can overtake the first -- the
// overlapping-sweep condition scanAll allows (no re-entrancy guard; called unawaited from
// setInterval, from init, and from setTf() on an operator click).
let __gatePair=null,__gateRelease=null,__failPair=null,__throwPair=null;
function __gate(){ return new Promise(function(res){ __gateRelease=res; }); }
globalThis.fetch=function(url){
  const u=String(url);
  if(/\/pricing/.test(u)){
    if(!__priceOk) return Promise.resolve(makeResponse(false,503,{}));
    return Promise.resolve(makeResponse(true,200,{prices:[{bids:[{price:'1.10290'}],asks:[{price:'1.10310'}]}]}));
  }
  if(__mode==='firing'){
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
g.setMode=m=>{__mode=m;};
g.setShortPair=p=>{__shortPair=p;};
g.setShortAll=v=>{__shortAll=v;};
g.holdPair=p=>{__gatePair=p;};
g.failPair=p=>{__failPair=p;};
g.throwPair=p=>{__throwPair=p;};
g.releaseHeld=()=>{__gatePair=null; if(__gateRelease){__gateRelease(); __gateRelease=null;}};
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
  '  evidenceRecordForwardObservations=__origRec;\n' +
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
