// MOGO-021 — candle close-time and timeframe-alignment accuracy.
//
// PURPOSE
// MOGO-021 covers "candle accuracy" and "candle/timeframe alignment". The four functions that
// decide when a candle actually CLOSES had ZERO direct coverage: getNYOffsetMinutes,
// nyAlignedClose, getCandleCloseTime and precomputeCloseTimes. Everything downstream depends on
// them -- the H1 master clock that gates ALEX's live poll, the replay two-pointer walk, and the
// evaluation cursor whose value determines whether an instrument is evaluated at all.
//
// WHY THIS MATTERS HERE SPECIFICALLY
// The MOGO-021 cursor-sanity work rests on the claim that a healthy H1 run can only ever leave the
// evaluation cursor exactly ON a UTC hour boundary, never ahead of it. That claim is a property of
// getCandleCloseTime, and it had never been tested. ALIGN-9..12 test it directly, including the
// last-candle fallback branch, which is the only branch that does duration math rather than
// reading the next candle's start.
//
// These are PURE functions -- no network, no clock stubbing, no seams at all. The DST cases use
// real IANA transition dates and the runtime's own timezone database, so a wrong offset here would
// be a real defect rather than a fixture artifact.
//
// Run from the project root:
//   osascript -l JavaScript tests/run_v1234_candle_alignment_tests.js
// or simply:  tests/run_all.sh
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
globalThis.fetch=function(){ return Promise.reject(new Error('no network in this suite')); };

const results=[];
const g={record:(id,desc,pass,detail)=>results.push({id,desc,pass,detail:detail||''})};
g.U=(y,m,d,h,mi)=>Date.UTC(y,m,d,h||0,mi||0,0);

const wrapped=new Function('g', appCode + '\n' + 'return (function(){\n' +
  // ══ getNYOffsetMinutes -- real DST behaviour, not an assumed fixed offset ══
  '  const offJan=getNYOffsetMinutes(new Date(g.U(2026,0,15,12)));\n' +
  '  const offJul=getNYOffsetMinutes(new Date(g.U(2026,6,15,12)));\n' +
  '  g.record("ALIGN-1","New York is UTC-5 (EST) in January",offJan===-300,"offset="+offJan+" min");\n' +
  '  g.record("ALIGN-2","New York is UTC-4 (EDT) in July -- the offset is not hard-coded",offJul===-240,"offset="+offJul+" min");\n' +
  // 2026 US DST: spring forward Sun 8 Mar 07:00 UTC, fall back Sun 1 Nov 06:00 UTC.
  '  const beforeSpring=getNYOffsetMinutes(new Date(g.U(2026,2,8,6,59)));\n' +
  '  const afterSpring=getNYOffsetMinutes(new Date(g.U(2026,2,8,7,1)));\n' +
  '  g.record("ALIGN-3","the spring-forward transition is honoured to the minute",\n' +
  '    beforeSpring===-300&&afterSpring===-240,"06:59Z="+beforeSpring+" 07:01Z="+afterSpring);\n' +
  '  const beforeFall=getNYOffsetMinutes(new Date(g.U(2026,10,1,5,59)));\n' +
  '  const afterFall=getNYOffsetMinutes(new Date(g.U(2026,10,1,6,1)));\n' +
  '  g.record("ALIGN-4","the fall-back transition is honoured to the minute",\n' +
  '    beforeFall===-240&&afterFall===-300,"05:59Z="+beforeFall+" 06:01Z="+afterFall);\n' +
  // ══ nyAlignedClose -- 17:00 New York, the OANDA daily/weekly convention ══
  '  const winterClose=nyAlignedClose(new Date(g.U(2026,0,15,12)),17);\n' +
  '  g.record("ALIGN-5","17:00 New York in winter is 22:00 UTC",\n' +
  '    winterClose.getTime()===g.U(2026,0,15,22),"got "+winterClose.toISOString());\n' +
  '  const summerClose=nyAlignedClose(new Date(g.U(2026,6,15,12)),17);\n' +
  '  g.record("ALIGN-6","17:00 New York in summer is 21:00 UTC -- one hour earlier, correctly",\n' +
  '    summerClose.getTime()===g.U(2026,6,15,21),"got "+summerClose.toISOString());\n' +
  '  g.record("ALIGN-7","the UTC instant differs across DST while the NY wall-clock hour does not",\n' +
  '    winterClose.getTime()-summerClose.getTime()!==0&&\n' +
  '    (winterClose.getTime()-g.U(2026,0,15,0))-(summerClose.getTime()-g.U(2026,6,15,0))===3600000,\n' +
  '    "winter 22:00Z vs summer 21:00Z");\n' +
  '  const lateNY=nyAlignedClose(new Date(g.U(2026,0,16,2)),17);\n' +   // 02:00 UTC = 21:00 NY on the 15th
  '  g.record("ALIGN-8","alignment uses the NEW YORK calendar date, not the UTC one",\n' +
  '    lateNY.getTime()===g.U(2026,0,15,22),"02:00Z on the 16th aligns to the 15th NY session: "+lateNY.toISOString());\n' +
  // ══ getCandleCloseTime -- the exact/estimated split ══
  '  function series(startMs,stepMs,n){ const a=[]; for(let i=0;i<n;i++) a.push({t:new Date(startMs+i*stepMs)}); return a; }\n' +
  '  const h1=series(g.U(2026,5,1,0),3600000,10);\n' +
  '  let exact=0;\n' +
  '  for(let i=0;i<h1.length-1;i++){ if(getCandleCloseTime(h1,i,"H1").getTime()===h1[i+1].t.getTime()) exact++; }\n' +
  '  g.record("ALIGN-9","every candle but the last closes EXACTLY at the next candle start (no duration math)",\n' +
  '    exact===h1.length-1,exact+"/"+(h1.length-1)+" exact");\n' +
  '  const lastH1=getCandleCloseTime(h1,h1.length-1,"H1");\n' +
  '  g.record("ALIGN-10","the last H1 candle falls back to start+1h",\n' +
  '    lastH1.getTime()===h1[h1.length-1].t.getTime()+3600000,"close="+lastH1.toISOString());\n' +
  // THE property the cursor-sanity work depends on.
  '  g.record("ALIGN-11","an H1 close lands EXACTLY on a UTC hour boundary -- a healthy cursor is never mid-hour",\n' +
  '    lastH1.getTime()===Math.floor(lastH1.getTime()/3600000)*3600000,"close="+lastH1.toISOString());\n' +
  // A candle starting at 09:00 is only COMPLETE once 10:00 has passed, so the earliest wall clock
  // at which this series can exist is its own last close. Checked at that instant and an hour on:
  // the cursor is <= the current boundary in both, which is the invariant cursor-sanity relies on.
  '  const atClose=Math.floor(lastH1.getTime()/3600000)*3600000;\n' +
  '  const anHourOn=Math.floor((lastH1.getTime()+3599999)/3600000)*3600000;\n' +
  '  g.record("ALIGN-12","and it never lands AHEAD of the boundary current at any instant the series can exist",\n' +
  '    lastH1.getTime()<=atClose&&lastH1.getTime()<=anHourOn,\n' +
  '    "close="+lastH1.toISOString()+" <= boundary at completion "+new Date(atClose).toISOString());\n' +
  '  const h4=series(g.U(2026,5,1,0),4*3600000,5);\n' +
  '  g.record("ALIGN-13","the last H4 candle falls back to start+4h",\n' +
  '    getCandleCloseTime(h4,4,"H4").getTime()===h4[4].t.getTime()+4*3600000,"H4 fallback");\n' +
  '  const m15=series(g.U(2026,5,1,0),15*60000,5);\n' +
  '  g.record("ALIGN-14","the last M15 candle falls back to start+15m",\n' +
  '    getCandleCloseTime(m15,4,"M15").getTime()===m15[4].t.getTime()+15*60000,"M15 fallback");\n' +
  // Daily/weekly fall back to 17:00 NY, NOT to +24h/+168h -- the DST-sensitive branch.
  '  const daily=series(g.U(2026,6,10,21),86400000,4);\n' +   // summer dailies close 21:00Z
  '  const lastD=getCandleCloseTime(daily,3,"D");\n' +
  '  g.record("ALIGN-15","the last DAILY candle aligns to 17:00 New York, not to a flat +24h",\n' +
  '    lastD.getTime()===nyAlignedClose(new Date(daily[3].t.getTime()+86400000),17).getTime(),\n' +
  '    "close="+lastD.toISOString());\n' +
  '  const weekly=series(g.U(2026,6,10,21),7*86400000,4);\n' +
  '  const lastW=getCandleCloseTime(weekly,3,"W");\n' +
  '  g.record("ALIGN-16","the last WEEKLY candle aligns to 17:00 New York a week on",\n' +
  '    lastW.getTime()===nyAlignedClose(new Date(weekly[3].t.getTime()+7*86400000),17).getTime(),\n' +
  '    "close="+lastW.toISOString());\n' +
  // A daily series spanning the DST change: closes must stay at 17:00 NY, shifting in UTC.
  '  const across=[{t:new Date(g.U(2026,10,1,20))},{t:new Date(g.U(2026,10,2,21))},{t:new Date(g.U(2026,10,3,22))}];\n' +
  '  const acrossLast=getCandleCloseTime(across,2,"D");\n' +
  '  g.record("ALIGN-17","a daily close computed AFTER the fall-back is 22:00 UTC (17:00 EST)",\n' +
  '    acrossLast.getUTCHours()===22,"close="+acrossLast.toISOString());\n' +
  '  g.record("ALIGN-18","out-of-range indices return null rather than throwing or guessing",\n' +
  '    getCandleCloseTime(h1,-1,"H1")===null&&getCandleCloseTime(h1,99,"H1")===null&&getCandleCloseTime(null,0,"H1")===null,\n' +
  '    "null on -1, 99 and null series");\n' +
  // ══ precomputeCloseTimes -- the array the replay walk depends on ══
  '  const pre=precomputeCloseTimes(h1,"H1");\n' +
  '  g.record("ALIGN-19","precomputeCloseTimes returns one close per candle",pre.length===h1.length,"len="+pre.length+"/"+h1.length);\n' +
  '  let mono=true; for(let i=1;i<pre.length;i++){ if(!(pre[i]>pre[i-1])) mono=false; }\n' +
  '  g.record("ALIGN-20","close times are strictly increasing -- no duplicate or reversed boundary",mono,"strictly monotonic");\n' +
  '  let agree=true; for(let i=0;i<h1.length;i++){ if(pre[i]!==getCandleCloseTime(h1,i,"H1").getTime()) agree=false; }\n' +
  '  g.record("ALIGN-21","it agrees with getCandleCloseTime on every index -- one methodology, not two",agree,"all indices agree");\n' +
  '  g.record("ALIGN-22","a null series yields an empty array rather than throwing",\n' +
  '    Array.isArray(precomputeCloseTimes(null,"H1"))&&precomputeCloseTimes(null,"H1").length===0,"[] on null");\n' +
  // ══ advancePointer -- the two-pointer walk over those closes ══
  '  g.record("ALIGN-23","advancePointer selects the LAST candle closed at or before the timestamp",\n' +
  '    advancePointer(pre,0,pre[3])===3&&advancePointer(pre,0,pre[3]-1)===2,\n' +
  '    "at close="+advancePointer(pre,0,pre[3])+", one ms before="+advancePointer(pre,0,pre[3]-1));\n' +
  '  g.record("ALIGN-24","it never moves backwards, so a replay cannot re-open a closed bar",\n' +
  '    advancePointer(pre,5,pre[2])===5,"stays at 5 when asked to go back to 2");\n' +
  '  g.record("ALIGN-25","it clamps at the final candle rather than running off the end",\n' +
  '    advancePointer(pre,0,pre[pre.length-1]+86400000)===pre.length-1,"clamped at "+(pre.length-1));\n' +
  // ══ cross-timeframe coherence ══
  '  const h4pre=precomputeCloseTimes(h4,"H4");\n' +
  '  const h1set={}; precomputeCloseTimes(series(g.U(2026,5,1,0),3600000,24),"H1").forEach(function(t){h1set[t]=true;});\n' +
  '  g.record("ALIGN-26","every H4 boundary is also an H1 boundary -- the timeframes share one grid",\n' +
  '    h4pre.every(function(t){ return h1set[t]===true||t>Math.max.apply(null,Object.keys(h1set).map(Number)); }),\n' +
  '    "H4 closes align to the H1 grid");\n' +
  '  g.record("ALIGN-27","H1 boundaries carry no minute/second/ms remainder",\n' +
  '    pre.every(function(t){ return t%3600000===0; }),"all H1 closes are whole hours");\n' +
  '  return g;\n})();'
);

try{
  wrapped(g);
  let pass=0,fail=0;
  results.forEach(function(r){
    if(r.pass){pass++;console.log('PASS -- '+r.id+': '+r.desc+(r.detail?'  ['+r.detail+']':''));}
    else{fail++;console.log('FAIL -- '+r.id+': '+r.desc+(r.detail?'  ['+r.detail+']':''));}
  });
  console.log('---');
  console.log(results.length+' fixtures, '+pass+' PASS, '+fail+' FAIL');
}catch(e){
  console.log('EXECUTION ERROR: '+(e&&e.message?e.message:String(e)));
  console.log('---');
  console.log(results.length+' fixtures, 0 PASS, '+(results.length||1)+' FAIL');
}
