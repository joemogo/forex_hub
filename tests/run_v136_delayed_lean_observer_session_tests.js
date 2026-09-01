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
console.log('---');console.log('ALL DELAYED LEAN OBSERVER SESSION FIXTURES PASSED');
