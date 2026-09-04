// RUN_ALL_EXEC: node tests/run_v134_lean_forward_observer_e2e_tests.js
const fs=require('fs'),crypto=require('crypto'),assert=require('assert');
const html=fs.readFileSync('index.html','utf8');
const seam=html.match(/\/\/ MOGO_LEAN_PRODUCTION_EMITTER_SEAM_START([\s\S]*?)\/\/ MOGO_LEAN_PRODUCTION_EMITTER_SEAM_END/);
if(!seam) throw new Error('production emitter seam missing');
const emitter=new Function(seam[1]+';return {build:alexGBuildLeanZoneRequestV2,canonical:alexGLeanCanonicalJson};')();
const observer=require('../platform/lean/alexg_forward_observer.js');
const sha=text=>crypto.createHash('sha256').update(text).digest('hex');
const closes=[99.8,100,100.2,100.8,101.1,100.4,100.6,100.7];
const bars=closes.map((c,i)=>({t:new Date(1700000000000+i*3600000),o:c,h:c+.2,l:c-.2,c}));
const setup={setupId:'AGS|observed|buy',setupType:'B_breakRetest',pair:'EUR_USD',timeframe:'H1',
  zoneId:'zone-1',reactionId:'AGR|5',brokenDirection:'upThroughResistance',breakCycleId:'AGB|up',
  brokenAtBar:3,brokenAt:bars[4].t.getTime(),qualificationBarIndex:6,qualificationTimestamp:bars[7].t.getTime()};
const rows=bars.map((b,index)=>({index,startTimeUtcMs:b.t.getTime(),open:b.o,high:b.h,low:b.l,close:b.c}));
const input={enabled:true,beforeSetups:[],afterSetups:[setup],zone:{id:'zone-1',low:100,high:100.5,formedAtBar:1,formedAt:bars[2].t.getTime()},
  bars,retestTouch:{reactionId:'AGR|5',barIndex:5,timestamp:bars[6].t.getTime()},identity:{pair:'EUR_USD',timeframe:'H1'},
  versions:{strategyVersion:'alex_g_sr_v1',ruleVersion:'alex-g-rule-v1',appVersion:'synthetic-e2e'},
  dataset:{id:'synthetic-observer-e2e',hash:{algorithm:'SHA-256',value:sha(emitter.canonical(rows))}},
  config:{breakConfirmationCloses:1,maxBarsBetweenBreakAndRetest:50,stopATRBuffer:.25,atrPeriod:14,minRR:2,trendSwingLookback:3,rejectionConfirmWithinBars:1,rejectionDisplacementATRMultiplier:.25}};
const beforeInput=JSON.stringify(input);
const deps={emitLeanZoneRequestV2:emitter.build,emitterDeps:{sha256Hex:sha}};
const out=observer.alexGObserveAndBuildLeanExport(input,deps);
if(out.schemaVersion!=='mogo.lean.zone-request.v2'||out.caseId!==setup.setupId||out.setup.type!=='break-retest'||out.bars.length!==8)
  throw new Error('unexpected observer-to-emitter envelope');
if(out.identity.pair!=='EUR_USD'||out.identity.timeframe!=='H1'||out.dataset.hash.value!==input.dataset.hash.value)
  throw new Error('identity or dataset provenance drift');
assert.deepStrictEqual(out.bars,rows,'all emitted candle values must match');
assert.deepStrictEqual(out.setup.qualificationAt,{index:6,barStartTimeUtcMs:bars[6].t.getTime(),closeTimeUtcMs:bars[7].t.getTime()});
assert.strictEqual(JSON.stringify(input),beforeInput,'composition must not mutate caller inputs');
console.log('PASS -- synthetic composition preserves candle values, qualification anchor and caller inputs');
assert.throws(()=>observer.alexGObserveAndBuildLeanExport({...input,dataset:{...input.dataset,hash:{algorithm:'SHA-256',value:'0'.repeat(64)}}},deps),e=>e.code==='REFUSE_DATASET_HASH');
assert.throws(()=>observer.alexGObserveAndBuildLeanExport({...input,identity:{pair:'GBP_USD',timeframe:'H1'}},deps),e=>e.code==='REFUSE_IDENTITY_MATCH');
assert.strictEqual(JSON.stringify(input),beforeInput,'refusals must not mutate caller inputs');
console.log('PASS -- actual emitter refusals propagate for invalid hash and identity');
assert.strictEqual(observer.alexGObserveAndBuildLeanExport({...input,beforeSetups:[setup]},deps),null);
console.log('PASS -- already-present setup yields no export');
assert.strictEqual((html.match(/alexGObserveAndBuildLeanExport\s*\(/g)||[]).length,0,'application must remain unwired');
assert.strictEqual(html.includes('platform/lean/alexg_forward_observer.js'),false,'application must not load observer');
console.log('PASS -- application remains unloaded and unwired (asserted, not just printed)');
console.log('---');
console.log('ALL FORWARD OBSERVER END-TO-END FIXTURES PASSED');
