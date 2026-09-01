// RUN_ALL_EXEC: node tests/run_v135_lean_observer_engine_prefix_tests.js
//
// Test-only integration proof: constructed H1 candles enter the real, unmodified
// alexGRunSetupEngine on successive prefixes.  No setup record is constructed by
// this test; the observer sees the engine's before/after snapshots directly.
const fs=require('fs'),vm=require('vm'),crypto=require('crypto'),assert=require('assert');
const html=fs.readFileSync('index.html','utf8');
const script=(html.match(/<script>([\s\S]*)<\/script>/)||[])[1];
if(!script) throw new Error('index.html script missing');
const observer=require('../platform/lean/alexg_forward_observer.js');
const seam=html.match(/\/\/ MOGO_LEAN_PRODUCTION_EMITTER_SEAM_START([\s\S]*?)\/\/ MOGO_LEAN_PRODUCTION_EMITTER_SEAM_END/);
if(!seam) throw new Error('production emitter seam missing');
const emitter=new Function(seam[1]+';return {build:alexGBuildLeanZoneRequestV2,canonical:alexGLeanCanonicalJson};')();
const sha=value=>crypto.createHash('sha256').update(value).digest('hex');

function element(){ return {style:{},classList:{add(){},remove(){},toggle(){},contains(){return false;}},options:[{value:'All'}],
  getContext(){return {clearRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillRect(){},save(){},restore(){},setLineDash(){},arc(){},fill(){},closePath(){},fillText(){},measureText(){return {width:0};}};},
  appendChild(){},addEventListener(){},getBoundingClientRect(){return {top:0,left:0,width:0,height:0};}}; }
const elements={}; let timer=0;
const context={console,Date,Math,JSON,Promise,Set,Map,Array,Object,String,Number,Boolean,RegExp,Error,TypeError,
  document:{getElementById:id=>(elements[id]||(elements[id]=element())),querySelector(){return null;},querySelectorAll(){return [];},createElement:element,addEventListener(){},body:{appendChild(){},removeChild(){}},activeElement:null,visibilityState:'visible'},
  window:{devicePixelRatio:1},localStorage:{getItem(){return null;},setItem(){},removeItem(){}},alert(){},confirm(){return true;},
  Blob:function(){},URL:{createObjectURL(){return 'blob:test';},revokeObjectURL(){}},setTimeout(){return ++timer;},clearTimeout(){},setInterval(){return ++timer;},clearInterval(){},
  ResizeObserver:function(){return {observe(){},disconnect(){}};},LightweightCharts:{LineStyle:{Solid:0,Dashed:1,Dotted:2},CrosshairMode:{Normal:0}},Notification:undefined,fetch(){return Promise.reject(new Error('network disabled by test'));}};
context.globalThis=context;
vm.createContext(context); vm.runInContext(script,context,{filename:'index.html'});

// This is S12's downward-break/retest fixture, copied as ordinary candle input only.
// The real engine decides whether it becomes B_breakRetest and at which prefix.
const T=0.0009765625, t0=Date.UTC(2026,0,5);
const loBar=(low,close)=>({o:close,h:low+T,l:low,c:close});
function candles(){
  const bars=[];
  for(let i=0;i<55;i++) bars.push(loBar(1.09840,1.09880));
  bars[20]=loBar(1.09800,1.09880); bars[28]=loBar(1.09810,1.09880); bars[36]=loBar(1.09790,1.09880);
  bars[39]=loBar(1.09795,1.09800); bars[40]=loBar(1.09795,1.09800); bars[41]=loBar(1.09795,1.09800);
  for(let i=42;i<55;i++) bars[i]=loBar(1.09700,1.09750);
  bars[50]={o:1.09750,h:1.09805,l:1.09805-T,c:1.09750};
  return bars.map((b,i)=>({...b,t:new Date(t0+i*3600000)}));
}
function reset(){ vm.runInContext('alexGZoneState={}; alexGSetupState=[]; alexGLastEvaluatedCloseTime={};',context); }
function run(prefix){ return context.alexGRunSetupEngine('EUR_USD',{H1:prefix,H4:[],D:[],W:[]}); }
function br(setups){ return setups.filter(s=>s.setupType==='B_breakRetest'); }

const all=candles(); reset();
let first=null, before=null, after=null;
for(let n=1;n<=all.length;n++){
  const prefix=all.slice(0,n);
  const result=run(prefix);
  const current=result.setups.slice();
  if(br(current).length){ first={n,result,current,prefix}; break; }
  before=current;
}
assert(first,'real engine did not organically create B_breakRetest on any synthetic prefix');
assert.strictEqual(br(before).length,0,'immediately preceding prefix must contain no B_breakRetest');
after=first.current;
const setup=observer.alexGObserveNewLeanBreakRetest({enabled:true,beforeSetups:before,afterSetups:after});
assert(setup,'observer did not report the real engine first appearance');
assert.strictEqual(setup,br(after)[0],'observer must return the exact engine-owned setup record');
assert.strictEqual(setup.brokenDirection,'downThroughSupport');
assert.strictEqual(setup.qualificationBarIndex,first.n-1,'first appearance must qualify on the just-added candle');
const zone=first.result.zones.H1.validatedZones.find(z=>z.id===setup.zoneId);
assert(zone,'engine-owned setup zone missing');
const retestTouch=zone.touches.find(t=>t.reactionId===setup.reactionId);
assert(retestTouch,'engine-owned setup retest touch missing');
console.log(`PASS -- real engine first emits B_breakRetest at prefix ${first.n}, qualification bar ${setup.qualificationBarIndex}`);

// At first appearance the exact input array ends at the qualification bar; the reviewed
// emitter correctly refuses because close time is represented by the successor start time.
const engineMetadata=vm.runInContext('({config:RULES_ALEXG.config,versions:{strategyVersion:STRATEGY_ALEXG,ruleVersion:RULES_ALEXG.ruleVersion,appVersion:APP_VERSION}})',context);
const shared={enabled:true,beforeSetups:before,afterSetups:after,zone,bars:first.prefix,retestTouch,
  identity:{pair:'EUR_USD',timeframe:'H1'},versions:engineMetadata.versions,config:engineMetadata.config};
const rows=shared.bars.map((b,index)=>({index,startTimeUtcMs:b.t.getTime(),open:b.o,high:b.h,low:b.l,close:b.c}));
shared.dataset={id:'synthetic-engine-prefix',hash:{algorithm:'SHA-256',value:sha(emitter.canonical(rows))}};
assert.throws(()=>observer.alexGObserveAndBuildLeanExport(shared,{emitLeanZoneRequestV2:emitter.build,emitterDeps:{sha256Hex:sha}}),e=>e.code==='REFUSE_QUALIFICATION_INDEX');
console.log('PASS -- first-appearance exact prefix is honestly refused without a successor close-time anchor');

// A later evaluated prefix supplies that real successor candle. Re-running the engine preserves
// the already-created record; no hand-built record or unevaluated candle is used for export.
const laterBars=all.slice(0,first.n+1);
const later=run(laterBars);
const laterAfter=later.setups.slice();
const laterSetup=br(laterAfter).find(s=>s.setupId===setup.setupId);
assert(laterSetup,'real engine lost first setup on successor prefix');
const laterZone=later.zones.H1.validatedZones.find(z=>z.id===laterSetup.zoneId);
const laterTouch=laterZone.touches.find(t=>t.reactionId===laterSetup.reactionId);
const laterRows=laterBars.map((b,index)=>({index,startTimeUtcMs:b.t.getTime(),open:b.o,high:b.h,low:b.l,close:b.c}));
const exportInput={...shared,beforeSetups:before,afterSetups:laterAfter,setupCandles:undefined,zone:laterZone,bars:laterBars,retestTouch:laterTouch,
  dataset:{id:'synthetic-engine-prefix-successor',hash:{algorithm:'SHA-256',value:sha(emitter.canonical(laterRows))}}};
const exported=observer.alexGObserveAndBuildLeanExport(exportInput,{emitLeanZoneRequestV2:emitter.build,emitterDeps:{sha256Hex:sha}});
assert.strictEqual(exported.caseId,setup.setupId); assert.strictEqual(exported.setup.type,'break-retest');
assert.deepStrictEqual(exported.bars,laterRows,'emitter must receive the exact later engine prefix');
console.log('PASS -- standalone observer and actual emitter export the real engine setup on successor prefix');
// Rebuild like a polling caller: reset engine-owned state for each complete input
// window, while retaining the observer's separately captured prior setup list.
function rebuild(start,end){
  reset();
  const bars=all.slice(start,end);
  return {bars,result:run(bars)};
}
const freshBefore=rebuild(0,53),freshFirst=rebuild(0,54),freshLater=rebuild(0,55);
assert.strictEqual(br(freshBefore.result.setups).length,0);
assert.strictEqual(br(freshFirst.result.setups).length,1);
assert.strictEqual(br(freshLater.result.setups).length,1);
const freshSetup=observer.alexGObserveNewLeanBreakRetest({enabled:true,
  beforeSetups:freshBefore.result.setups,afterSetups:freshFirst.result.setups});
assert.strictEqual(freshSetup,br(freshFirst.result.setups)[0]);
assert.notStrictEqual(freshSetup,setup,'fresh rebuild must produce a new engine record object');
assert.notStrictEqual(freshSetup,br(freshLater.result.setups)[0],'each rebuild must own its records');
assert.strictEqual(freshSetup.setupId,setup.setupId);
assert.strictEqual(freshSetup.qualificationTimestamp,setup.qualificationTimestamp);
assert.strictEqual(observer.alexGObserveNewLeanBreakRetest({enabled:true,
  beforeSetups:freshFirst.result.setups,afterSetups:freshLater.result.setups}),null);
console.log('PASS -- fresh engine rebuilds preserve first appearance and suppress duplicate observation');

// One rolling-window shift removes only a pre-event warmup candle. The bar index
// changes, but this particular event retains its identity and must not become new.
// This does not establish behavior when a zone anchor is evicted or re-created.
const shifted=rebuild(1,55),shiftedSetup=br(shifted.result.setups)[0];
assert.strictEqual(br(shifted.result.setups).length,1);
assert.strictEqual(shiftedSetup.qualificationBarIndex,freshSetup.qualificationBarIndex-1);
assert.strictEqual(shiftedSetup.qualificationTimestamp,freshSetup.qualificationTimestamp);
assert.strictEqual(shiftedSetup.setupId,freshSetup.setupId);
assert.strictEqual(observer.alexGObserveNewLeanBreakRetest({enabled:true,
  beforeSetups:freshLater.result.setups,afterSetups:shifted.result.setups}),null);
console.log('PASS -- one pre-event warmup-bar eviction changes index without re-observing the same event');
// Exercise the production-independent session helper with actual engine snapshots:
// prime -> wait for successor -> export exactly once across repeated polls.
const session=observer.alexGCreateDelayedLeanExportSession({emitLeanZoneRequestV2:emitter.build,emitterDeps:{sha256Hex:sha}});
function sessionInput(capture){
  const candidate=br(capture.result.setups)[0];
  const zone=candidate&&capture.result.zones.H1.validatedZones.find(z=>z.id===candidate.zoneId);
  const rows=capture.bars.map((b,index)=>({index,startTimeUtcMs:b.t.getTime(),open:b.o,high:b.h,low:b.l,close:b.c}));
  return {...shared,afterSetups:capture.result.setups,bars:capture.bars,zone,
    retestTouch:zone&&zone.touches.find(t=>t.reactionId===candidate.reactionId),
    dataset:{id:'synthetic-session-prefix',hash:{algorithm:'SHA-256',value:sha(emitter.canonical(rows))}}};
}
assert.strictEqual(session.run(sessionInput(freshBefore)),null,'priming must not emit historical setups');
assert.strictEqual(session.run(sessionInput(freshFirst)),null,'first appearance waits for successor');
const sessionExport=session.run(sessionInput(freshLater));
assert.strictEqual(sessionExport.caseId,freshSetup.setupId);
assert.deepStrictEqual(sessionExport.bars,laterRows);
assert.strictEqual(session.run(sessionInput(freshLater)),null,'same snapshot must not export twice');
console.log('PASS -- delayed session primes, retains actual engine candidate, exports on successor, and suppresses repeat');

// The synchronous capture wrapper receives only candles and metadata.  Its explicit
// engine dependency owns the setup snapshots, zone and touch; 53 -> 54 -> 55 is
// rebuilt as ordinary engine input on each poll, with no caller-provided handoff facts.
let engineCalls=0; const captureSetupCounts=[];
const captureSession=observer.alexGCreateSynchronousLeanEngineExportSession({
  runLeanSetupEngine(pair,frames){
    engineCalls++; assert.strictEqual(pair,'EUR_USD'); assert.strictEqual(frames.H1,captureBars);
    assert.deepStrictEqual(frames.H4,[]);assert.deepStrictEqual(frames.D,[]);assert.deepStrictEqual(frames.W,[]);
    reset(); const result=run(frames.H1); captureSetupCounts.push(br(result.setups).length); return result;
  },emitLeanZoneRequestV2:emitter.build,emitterDeps:{sha256Hex:sha}
});
let captureBars;
function captured(prefix){
  captureBars=all.slice(0,prefix);
  const captureRows=captureBars.map((b,index)=>({index,startTimeUtcMs:b.t.getTime(),open:b.o,high:b.h,low:b.l,close:b.c}));
  return {enabled:true,pair:'EUR_USD',timeframe:'H1',candles:captureBars,
    identity:{pair:'caller-cannot-select-this'},versions:engineMetadata.versions,config:engineMetadata.config,
    dataset:{id:'synthetic-capture-prefix',hash:{algorithm:'SHA-256',value:sha(emitter.canonical(captureRows))}}};
}
assert.strictEqual(captureSession.run(captured(53)),null);
assert.strictEqual(captureSession.run(captured(54)),null);
assert.throws(()=>captureSession.run(captured(53)),error=>error.code==='REFUSE_OBSERVER_CAPTURE_STALE_SNAPSHOT');
assert.strictEqual(engineCalls,2,'stale prefix must not invoke engine or disturb pending export');
const capturedExport=captureSession.run(captured(55));
assert.deepStrictEqual(captureSetupCounts,[0,1,1]);
assert.strictEqual(capturedExport.caseId,freshSetup.setupId);
assert.deepStrictEqual(capturedExport.bars,laterRows);
assert.strictEqual(captureSession.run(captured(55)),null,'duplicate engine snapshot must not export twice');
assert.strictEqual(engineCalls,4);
console.log('PASS -- synchronous capture derives 53 -> 54 -> 55 handoff, rejects stale prefix while pending, recovers and suppresses duplicates');
console.log('---'); console.log('ALL LEAN OBSERVER ENGINE PREFIX FIXTURES PASSED');
