// RUN_ALL_EXEC: node tests/run_v136_delayed_lean_observer_session_tests.js
const assert=require('assert');
const api=require('../platform/lean/alexg_forward_observer.js');
function setup(id,extra){return {setupId:id,setupType:'B_breakRetest',zoneId:'z-'+id,reactionId:'r-'+id,...extra};}
function input(after,enabled=true){const s=after[0];return {enabled,afterSetups:after,zone:{id:s&&s.zoneId},bars:[{},{}],retestTouch:{reactionId:s&&s.reactionId},identity:{},versions:{},dataset:{},config:{}};}
function refusal(code,fn){assert.throws(fn,error=>error&&error.code===code);}
function emitter(){let calls=0;return {deps:{emitLeanZoneRequestV2:handoff=>({caseId:handoff.setup.setupId,call:++calls})},calls:()=>calls};}
function candles(endpoint=1700003600000){return [endpoint-3600000,endpoint].map(t=>({t:new Date(t),o:1,h:2,l:0.5,c:1.5}));}

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
 assert.strictEqual(s.run({enabled:false,pair:'EUR_USD',timeframe:'H1',candles:candles()}),null);assert.strictEqual(calls,0);
 const captureCandles=candles();assert.strictEqual(s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:captureCandles,identity:{untrusted:'kept'},versions:{},dataset:{},config:{}}),null);
 assert.strictEqual(calls,1);assert.strictEqual(received.frames.H1,captureCandles);assert.deepStrictEqual(received.frames.H4,[]);assert.deepStrictEqual(received.frames.D,[]);assert.deepStrictEqual(received.frames.W,[]);
 for(const key of ['afterSetups','beforeSetups','zone','retestTouch','bars','setupCandles','resolveObserved'])
  refusal('REFUSE_OBSERVER_CAPTURE_CALLER_STATE',()=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:captureCandles,[key]:{}}));
 refusal('REFUSE_OBSERVER_CAPTURE_IDENTITY',()=>s.run({enabled:true,pair:'GBP_USD',timeframe:'H1',candles:captureCandles}));
 assert.strictEqual(calls,1,'caller substitutions and identity switches must not call engine');
 refusal('REFUSE_OBSERVER_CAPTURE_INPUT',()=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H4',candles:captureCandles}));
 refusal('REFUSE_OBSERVER_CAPTURE_INPUT',()=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:[]}));
 refusal('REFUSE_OBSERVER_CAPTURE_INPUT',()=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:new Array(10001)}));
 assert.strictEqual(calls,1,'unsupported timeframe and invalid sizes must not call engine');
 console.log('PASS -- synchronous capture is disabled by default, pins identity, and accepts no caller snapshots');}
{const common={enabled:true,pair:'EUR_USD',timeframe:'H1',candles:candles()};
 for(const result of [Promise.resolve({}),{}, {setups:[],zones:{}}]){
  const s=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:()=>result,emitLeanZoneRequestV2:()=>{}});
  refusal('REFUSE_OBSERVER_CAPTURE_ENGINE_RESULT',()=>s.run(common));
 }
 console.log('PASS -- synchronous capture refuses async and malformed engine results');}
{const candidate=setup('A',{pair:'EUR_USD',timeframe:'H1'}),base={enabled:true,pair:'EUR_USD',timeframe:'H1',candles:candles()};
 function engine(zones){let step=0;return ()=>step++?{setups:[candidate],zones:{H1:{validatedZones:zones}}}:{setups:[],zones:{H1:{validatedZones:[]}}};}
 for(const zones of [[],[{id:'z-A',touches:[]}],[{id:'z-A',touches:[{reactionId:'r-A'},{reactionId:'r-A'}]}],[{id:'z-A',touches:[{reactionId:'r-A'}]},{id:'z-A',touches:[{reactionId:'r-A'}]}]]){
  const s=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:engine(zones),emitLeanZoneRequestV2:()=>({})});
  s.run(base);refusal(zones.length===0?'REFUSE_OBSERVER_CAPTURE_ZONE':zones.length===2?'REFUSE_OBSERVER_CAPTURE_ZONE':'REFUSE_OBSERVER_CAPTURE_RETEST',()=>s.run(base));
 }
 const foreign=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:()=>({setups:[setup('X',{pair:'GBP_USD',timeframe:'H1'})],zones:{H1:{validatedZones:[]}}}),emitLeanZoneRequestV2:()=>({})});
 refusal('REFUSE_OBSERVER_CAPTURE_ENGINE_IDENTITY',()=>foreign.run(base));
 console.log('PASS -- capture refuses foreign engine snapshots and missing or ambiguous derived zone/touch facts');}
{let calls=0,first=true;const candidate=setup('A',{pair:'EUR_USD',timeframe:'H1'});
 const s=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:()=>{
   calls++;return calls===1?{setups:[],zones:{H1:{validatedZones:[]}}}:{setups:[candidate],zones:{H1:{validatedZones:[{id:'z-A',touches:[{reactionId:'r-A'}]}]}}};
 },emitLeanZoneRequestV2:()=>{if(first){first=false;const e=new Error('REFUSE_QUALIFICATION_INDEX');e.code=e.message;throw e;}return {caseId:'A'};}});
 const baseline=candles(1700003600000),pending=candles(1700007200000),stale=candles(1700003600000);
 assert.strictEqual(s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:baseline,versions:{},dataset:{},config:{}}),null);
 assert.strictEqual(s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:pending,versions:{},dataset:{},config:{}}),null);
 refusal('REFUSE_OBSERVER_CAPTURE_STALE_SNAPSHOT',()=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:stale,versions:{},dataset:{},config:{}}));
 assert.deepStrictEqual(s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:pending,versions:{},dataset:{},config:{}}),{caseId:'A'});
 assert.strictEqual(calls,3,'stale snapshots must refuse before engine and equal endpoints may retry');
 console.log('PASS -- stale capture snapshots refuse before engine while an equal pending endpoint recovers');}
{let calls=0;const s=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:()=>{calls++;return {setups:[],zones:{H1:{validatedZones:[]}}};},emitLeanZoneRequestV2:()=>{}});
 for(const bad of [new Array(2),[{t:new Date(1)},,{t:new Date(3)}],[{t:new Date(NaN)},{t:new Date(1)}],[{t:NaN},{t:1}],[{t:0},{t:Infinity}],[{t:0},{t:1.5}],[{t:0},{t:Number.MAX_SAFE_INTEGER+1}],[{t:new Date(1)},{t:new Date(1)}],[{t:new Date(2)},{t:new Date(1)}],[{t:'bad'},{t:new Date(1)}],[{},{t:new Date(1)}]])
  refusal('REFUSE_OBSERVER_CAPTURE_CANDLE_TIMESTAMPS',()=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:bad,versions:{},dataset:{},config:{}}));
 assert.strictEqual(calls,0);console.log('PASS -- malformed or non-increasing capture timestamps refuse before engine');}
{let fail=true,calls=0;const s=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:()=>{calls++;if(fail)throw new Error('synthetic engine failure');return {setups:[],zones:{H1:{validatedZones:[]}}};},emitLeanZoneRequestV2:()=>{}});
 const capture=endpoint=>({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:candles(endpoint)});
 assert.strictEqual(s.run({...capture(1700010800000),enabled:false}),null);
 assert.throws(()=>s.run(capture(1700007200000)),/synthetic engine failure/);fail=false;
 assert.strictEqual(s.run(capture(1700003600000)),null,'disabled and failed calls must not establish watermark');
 assert.strictEqual(calls,2);
 assert.strictEqual(s.run({...capture(1700007200000),candles:candles(1700007200000).map(c=>({...c,t:c.t.getTime()}))}),null,'numeric UTC-ms timestamps are accepted');
 refusal('REFUSE_OBSERVER_CAPTURE_STALE_SNAPSHOT',()=>s.run(capture(1700003600000)));
 assert.strictEqual(calls,3);console.log('PASS -- disabled or failed capture does not advance the accepted watermark');}
{let calls=0;const s=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:()=>{calls++;return {setups:[],zones:{H1:{validatedZones:[]}}};},emitLeanZoneRequestV2:()=>{}});
 const run=bars=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:bars});
 const original=candles();run(original);
 for(const key of ['o','h','l','c']){
   const changed=candles();changed[0][key]+=0.01;
   refusal('REFUSE_OBSERVER_CAPTURE_REVISED_HISTORY',()=>run(changed));
 }
 original[0].c=1.6;
 refusal('REFUSE_OBSERVER_CAPTURE_REVISED_HISTORY',()=>run(original));
 assert.strictEqual(calls,1,'history refusals must precede engine invocation');
 assert.strictEqual(run(candles()),null,'refusals must preserve accepted history');
 const updating=candles();updating[1].c=1.7;assert.strictEqual(run(updating),null,'unclosed sentinel may change');
 const extended=[...updating,{...candles(1700007200000)[1]}];run(extended);
 const revised=extended.map(c=>({...c}));revised[1].c=1.8;
 refusal('REFUSE_OBSERVER_CAPTURE_REVISED_HISTORY',()=>run(revised));
 assert.strictEqual(run(extended.slice(1)),null,'unchanged rolling-window overlap is allowed');
 assert.strictEqual(calls,5);
 console.log('PASS -- copied closed OHLC refuses revisions; sentinel updates and warmup eviction remain valid');}
{let calls=0,fail=false;const s=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:()=>{calls++;if(fail)throw new Error('engine failed');return {setups:[],zones:{H1:{validatedZones:[]}}};},emitLeanZoneRequestV2:()=>{}});
 const run=bars=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:bars});run(candles());
 fail=true;const next=candles(1700007200000);next[0].c=1.7;
 assert.throws(()=>run(next),/engine failed/);fail=false;
 assert.strictEqual(run(candles(1700007200000)),null,'failed engine must not pin newly closed OHLC');
 for(const value of [undefined,NaN,Infinity,'1']){const bad=candles(1700007200000);bad[0].o=value;
   refusal('REFUSE_OBSERVER_CAPTURE_CANDLE_VALUES',()=>run(bad));}
 assert.strictEqual(calls,3);
 console.log('PASS -- failed captures do not pin history; invalid OHLC refuses before engine');}
{let calls=0;const s=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:()=>{calls++;return {setups:[],zones:{H1:{validatedZones:[]}}};},emitLeanZoneRequestV2:()=>{}});
 const bars=[...candles(),candles(1700007200000)[1],candles(1700010800000)[1]];
 const run=cs=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:cs});run(bars);
 refusal('REFUSE_OBSERVER_CAPTURE_DISCONTINUITY',()=>run([bars[0],bars[2],bars[3]]));
 refusal('REFUSE_OBSERVER_CAPTURE_DISCONTINUITY',()=>run([bars[0],{...bars[0],t:new Date(1700001800000)},...bars.slice(1)]));
 refusal('REFUSE_OBSERVER_CAPTURE_DISCONTINUITY',()=>run(candles(1700018000000)));
 refusal('REFUSE_OBSERVER_CAPTURE_DISCONTINUITY',()=>run([{...bars[0],t:new Date(1699996400000)},...bars]));
 assert.strictEqual(calls,1,'disconnected or edited overlap must not invoke engine');
 assert.strictEqual(run(bars.slice(1)),null,'leading eviction retains an exact suffix');
 assert.strictEqual(run([bars[3],candles(1700014400000)[1]]),null,'one-candle overlap may advance');
 assert.strictEqual(calls,3);
 console.log('PASS -- missing, inserted, prepended and nonoverlapping timestamps refuse; suffix eviction and extension recover');}
{let calls=0;const s=api.alexGCreateSynchronousLeanEngineExportSession({runLeanSetupEngine:()=>{calls++;return {setups:[],zones:{H1:{validatedZones:[]}}};},emitLeanZoneRequestV2:()=>{}});
 const run=cs=>s.run({enabled:true,pair:'EUR_USD',timeframe:'H1',candles:cs});
 for(const delta of [1800000,7200000,49*3600000]){
   const bad=candles();bad[1].t=new Date(bad[0].t.getTime()+delta);
   refusal('REFUSE_OBSERVER_CAPTURE_UNSUPPORTED_GAP',()=>run(bad));
 }
 assert.strictEqual(calls,0,'initial gaps and short cadence refuse before priming');run(candles());
 refusal('REFUSE_OBSERVER_CAPTURE_UNSUPPORTED_GAP',()=>run([...candles(),candles(1700010800000)[1]]));
 assert.strictEqual(calls,1,'newly appended gap must refuse before engine');
 assert.strictEqual(run([...candles(),candles(1700007200000)[1]]),null,'gap refusal must preserve baseline');
 assert.strictEqual(calls,2);
 console.log('PASS -- initial and appended cadence gaps refuse without priming or changing accepted history');}
console.log('---');console.log('ALL DELAYED LEAN OBSERVER SESSION FIXTURES PASSED');
