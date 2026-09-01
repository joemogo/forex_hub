// RUN_ALL_EXEC: node tests/run_v136_delayed_lean_observer_session_tests.js
const assert=require('assert');
const api=require('../platform/lean/alexg_forward_observer.js');
function setup(id,extra){return {setupId:id,setupType:'B_breakRetest',zoneId:'z-'+id,reactionId:'r-'+id,...extra};}
function input(after,enabled=true){const s=after[0];return {enabled,afterSetups:after,zone:{id:s&&s.zoneId},bars:[{},{}],retestTouch:{reactionId:s&&s.reactionId},identity:{},versions:{},dataset:{},config:{}};}
function refusal(code,fn){assert.throws(fn,error=>error&&error.code===code);}
function emitter(){let calls=0;return {deps:{emitLeanZoneRequestV2:handoff=>({caseId:handoff.setup.setupId,call:++calls})},calls:()=>calls};}

{const e=emitter(),session=api.alexGCreateDelayedLeanExportSession(e.deps),a=setup('A');
 assert.strictEqual(session.run(input([a])),null); assert.strictEqual(e.calls(),0);
 assert.strictEqual(session.run(input([a])),null); assert.strictEqual(e.calls(),0);
 console.log('PASS -- first enabled snapshot primes and repeated snapshot is suppressed');}
{const e=emitter(),session=api.alexGCreateDelayedLeanExportSession(e.deps),a=setup('A');
 assert.strictEqual(session.run(input([a],false)),null); assert.strictEqual(session.run(input([a])),null);
 assert.strictEqual(session.run(input([a],false)),null); assert.strictEqual(session.run(input([],true)),null);
 assert.strictEqual(e.calls(),0); console.log('PASS -- disabled calls do not mutate state');}
{let calls=0,first=true;const session=api.alexGCreateDelayedLeanExportSession({emitLeanZoneRequestV2:handoff=>{
 calls++;if(first){first=false;const error=new Error('REFUSE_QUALIFICATION_INDEX');error.code=error.message;throw error;}return {caseId:handoff.setup.setupId};}}),a=setup('A');
 session.run(input([])); assert.strictEqual(session.run(input([a])),null);
 assert.deepStrictEqual(session.run(input([a])),{caseId:'A'}); assert.strictEqual(calls,2);
 assert.strictEqual(session.run(input([a])),null); console.log('PASS -- qualification delay retries exactly once');}
{const session=api.alexGCreateDelayedLeanExportSession({emitLeanZoneRequestV2:()=>{const e=new Error('REFUSE_OTHER');e.code=e.message;throw e;}}),a=setup('A');
 session.run(input([])); refusal('REFUSE_OTHER',()=>session.run(input([a]))); refusal('REFUSE_OTHER',()=>session.run(input([a])));
 console.log('PASS -- unsupported emitter errors propagate without advancing baseline');}
function delayed(){let first=true;return api.alexGCreateDelayedLeanExportSession({emitLeanZoneRequestV2:()=>{if(first){first=false;const e=new Error('REFUSE_QUALIFICATION_INDEX');e.code=e.message;throw e;}return {};}});}
{const s=delayed(),a=setup('A');s.run(input([]));assert.strictEqual(s.run(input([a])),null);
 refusal('REFUSE_OBSERVER_PENDING_MISSING',()=>s.run(input([]))); console.log('PASS -- vanished pending setup refuses');}
{const s=delayed(),a=setup('A'),b=setup('B');s.run(input([]));assert.strictEqual(s.run(input([a])),null);
 refusal('REFUSE_OBSERVER_PENDING_SUBSTITUTION',()=>s.run(input([b]))); console.log('PASS -- substituted pending setup refuses');}
{const s=delayed(),a=setup('A'),b=setup('B');s.run(input([]));assert.strictEqual(s.run(input([a])),null);
 refusal('REFUSE_OBSERVER_AMBIGUOUS_NEW_SETUP',()=>s.run(input([a,b]))); console.log('PASS -- ambiguous retry refuses');}
{const s=delayed(),a=setup('A',{pair:'EUR_USD',timeframe:'H1',breakCycleId:'cycle-1',brokenDirection:'down',qualificationTimestamp:10});s.run(input([]));assert.strictEqual(s.run(input([a])),null);
 refusal('REFUSE_OBSERVER_PENDING_IDENTITY',()=>s.run(input([setup('A',{pair:'EUR_USD',timeframe:'H1',breakCycleId:'cycle-1',brokenDirection:'down',qualificationTimestamp:10,reactionId:'changed'})])));
 console.log('PASS -- pending economic identity changes refuse');}
{const e=emitter(),s=api.alexGCreateDelayedLeanExportSession(e.deps),a=setup('A');const original=[a];s.run(input(original));
 original.length=0;a.setupId='MUTATED';a.setupType='A_repeatedReaction';
 assert.strictEqual(s.run(input([setup('A')])),null);assert.strictEqual(e.calls(),0);
 const b=setup('B');
 assert.deepStrictEqual(s.run(input([b])),{caseId:'B',call:1}); console.log('PASS -- baseline uses copied identities');}
{const e=emitter(),s=api.alexGCreateDelayedLeanExportSession(e.deps),a=setup('A'),b=setup('B');
 s.run(input([a],false));assert.strictEqual(s.run(input([b])),null);assert.strictEqual(e.calls(),0);
 s.run(input([a],false));assert.strictEqual(s.run(input([b])),null);assert.strictEqual(e.calls(),0);
 console.log('PASS -- disabled snapshots cannot prime or replace an established baseline');}
{const e=emitter(),s=api.alexGCreateDelayedLeanExportSession(e.deps,{maxSnapshotSetups:1});
 refusal('REFUSE_OBSERVER_SESSION_LIMIT',()=>api.alexGCreateDelayedLeanExportSession(e.deps,{maxSnapshotSetups:1025}));
 refusal('REFUSE_OBSERVER_SESSION_SNAPSHOT_LIMIT',()=>s.run(input([setup('A'),setup('B')])));
 assert.strictEqual(s.run(input([setup('C')])),null);assert.strictEqual(e.calls(),0);
 console.log('PASS -- oversized snapshots refuse before mutating state');}
{let calls=0,received;const engine=(pair,frames)=>{calls++;received={pair,frames};return {setups:[],zones:{H1:{validatedZones:[]}}};};
 const s=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:engine,emitLeanZoneRequestV2:()=>{throw new Error('must not emit');}});
 assert.strictEqual(s.run({enabled:false,pair:'EUR_USD',timeframe:'H1',candles:[{},{}]}),null);assert.strictEqual(calls,0);
 const candles=[{},{}];assert.strictEqual(s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles,identity:{untrusted:'kept'},versions:{},dataset:{},config:{}}),null);
 assert.strictEqual(calls,1);assert.strictEqual(received.frames.H1,candles);assert.deepStrictEqual(received.frames.H4,[]);assert.deepStrictEqual(received.frames.D,[]);assert.deepStrictEqual(received.frames.W,[]);
 for(const key of ['afterSetups','beforeSetups','zone','retestTouch','bars','setupCandles','resolveObserved'])
  refusal('REFUSE_OBSERVER_CAPTURE_CALLER_STATE',()=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles,[key]:{}}));
 refusal('REFUSE_OBSERVER_CAPTURE_IDENTITY',()=>s.run({enabled:true,pair:'GBP_USD',timeframe:'H1',candles}));
 assert.strictEqual(calls,1,'caller substitutions and identity switches must not call engine');
 refusal('REFUSE_OBSERVER_CAPTURE_INPUT',()=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H4',candles}));
 refusal('REFUSE_OBSERVER_CAPTURE_INPUT',()=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:[]}));
 refusal('REFUSE_OBSERVER_CAPTURE_INPUT',()=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:new Array(10001)}));
 assert.strictEqual(calls,1,'unsupported timeframe and invalid sizes must not call engine');
 console.log('PASS -- synchronous capture is disabled by default, pins identity, and accepts no caller snapshots');}
{const common={enabled:true,pair:'EUR_USD',timeframe:'H1',candles:[{},{}]};
 for(const result of [Promise.resolve({}),{}, {setups:[],zones:{}}]){
  const s=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:()=>result,emitLeanZoneRequestV2:()=>{}});
  refusal('REFUSE_OBSERVER_CAPTURE_ENGINE_RESULT',()=>s.run(common));
 }
 console.log('PASS -- synchronous capture refuses async and malformed engine results');}
{const candidate=setup('A',{pair:'EUR_USD',timeframe:'H1'}),base={enabled:true,pair:'EUR_USD',timeframe:'H1',candles:[{},{}]};
 function engine(zones){let step=0;return ()=>step++?{setups:[candidate],zones:{H1:{validatedZones:zones}}}:{setups:[],zones:{H1:{validatedZones:[]}}};}
 for(const zones of [[],[{id:'z-A',touches:[]}],[{id:'z-A',touches:[{reactionId:'r-A'},{reactionId:'r-A'}]}],[{id:'z-A',touches:[{reactionId:'r-A'}]},{id:'z-A',touches:[{reactionId:'r-A'}]}]]){
  const s=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:engine(zones),emitLeanZoneRequestV2:()=>({})});
  s.run(base);refusal(zones.length===0?'REFUSE_OBSERVER_CAPTURE_ZONE':zones.length===2?'REFUSE_OBSERVER_CAPTURE_ZONE':'REFUSE_OBSERVER_CAPTURE_RETEST',()=>s.run(base));
 }
 const foreign=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:()=>({setups:[setup('X',{pair:'GBP_USD',timeframe:'H1'})],zones:{H1:{validatedZones:[]}}}),emitLeanZoneRequestV2:()=>({})});
 refusal('REFUSE_OBSERVER_CAPTURE_ENGINE_IDENTITY',()=>foreign.run(base));
 console.log('PASS -- capture refuses foreign engine snapshots and missing or ambiguous derived zone/touch facts');}
console.log('---');console.log('ALL DELAYED LEAN OBSERVER SESSION FIXTURES PASSED');
