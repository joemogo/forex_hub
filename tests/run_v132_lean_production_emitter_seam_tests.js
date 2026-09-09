// RUN_ALL_EXEC: node tests/run_v132_lean_production_emitter_seam_tests.js
// Node-only test for the disabled, in-memory production emitter seam.  It extracts
// only the marked seam, never evaluates the application or accesses production data.
const fs=require('fs'),crypto=require('crypto');
const html=fs.readFileSync('index.html','utf8');
const match=html.match(/\/\/ MOGO_LEAN_PRODUCTION_EMITTER_SEAM_START([\s\S]*?)\/\/ MOGO_LEAN_PRODUCTION_EMITTER_SEAM_END/);
if(!match) throw new Error('production emitter seam markers missing');
const seam=match[1];
const api=new Function(seam+';return {build:alexGBuildLeanZoneRequestV2,canonical:alexGLeanCanonicalJson,defaultEnabled:MOGO_LEAN_PRODUCTION_EMITTER_DEFAULT_ENABLED};')();
const results=[];
function test(name,fn){try{fn();results.push({name,pass:true});}catch(e){results.push({name,pass:false,detail:e&&e.stack||String(e)});}}
function equal(actual,expected,message){if(JSON.stringify(actual)!==JSON.stringify(expected)) throw new Error(message||'not equal');}
function refusal(code,fn){try{fn();throw new Error('accepted');}catch(e){if(e.message==='accepted'||e.code!==code) throw e;}}
const cfg={breakConfirmationCloses:1,maxBarsBetweenBreakAndRetest:50,stopATRBuffer:.25,atrPeriod:14,minRR:2,trendSwingLookback:3,rejectionConfirmWithinBars:1,rejectionDisplacementATRMultiplier:.25};
function sha(text){return crypto.createHash('sha256').update(text).digest('hex');}
function barsFor(direction){
  const closes=direction==='upThroughResistance'?[99.8,100,100.2,100.8,101.1,100.4,100.6,100.7]:[100.7,100.5,100.3,99.7,99.4,100.1,99.9,99.8];
  return closes.map((c,i)=>({t:new Date(1700000000000+i*86400000),o:c,h:c+.2,l:c-.2,c}));
}
function fixture(direction='upThroughResistance'){
  const bars=barsFor(direction),buy=direction==='upThroughResistance';
  const zone={id:'zone-1',low:100,high:100.5,formedAtBar:1,formedAt:bars[2].t.getTime()};
  const setup={setupId:buy?'AGS|buy':'AGS|sell',setupType:'B_breakRetest',pair:'EUR_USD',timeframe:'D',zoneId:'zone-1',reactionId:'AGR|5',brokenDirection:direction,breakCycleId:buy?'AGB|up':'AGB|down',brokenAtBar:3,brokenAt:bars[4].t.getTime(),qualificationBarIndex:6,qualificationTimestamp:bars[7].t.getTime()};
  const retestTouch={reactionId:'AGR|5',barIndex:5,timestamp:bars[6].t.getTime()};
  const rows=bars.map((b,index)=>({index,startTimeUtcMs:b.t.getTime(),open:b.o,high:b.h,low:b.l,close:b.c}));
  const dataset={id:'synthetic-production-shaped',hash:{algorithm:'SHA-256',value:sha(api.canonical(rows))}};
  return{enabled:true,setup,zone,bars,setupCandles:bars,retestTouch,identity:{pair:'EUR_USD',timeframe:'D'},versions:{strategyVersion:'alex_g_sr_v1',ruleVersion:'alex-g-rule-v1',appVersion:'test'},dataset,config:{...cfg}};
}
const deps={sha256Hex:sha};

test('disabled by default and requires explicit per-call capability',()=>{
  equal(api.defaultEnabled,false);const f=fixture();f.enabled=false;refusal('REFUSE_EMITTER_DISABLED',()=>api.build(f,deps));
});
test('mirrored resistance break emits exact v2 buy envelope',()=>{
  const out=api.build(fixture(),deps);equal(out.schemaVersion,'mogo.lean.zone-request.v2');equal(out.identity,{pair:'EUR_USD',timeframe:'D'});equal(out.zone.preBreakRole,'resistance');equal(out.breakEvent.brokenDirection,'upThroughResistance');equal(out.setup.type,'break-retest');equal(out.setup.retestAt.index,5);equal(out.setup.qualificationAt.index,6);equal(out.barTimestampSemantics,'START_TIME_UTC_MS');equal(out.bars.length,8);equal(Object.keys(out.config).sort(),Object.keys(cfg).sort());
});
test('emitted object has the exact v2 top-level shape and event provenance',()=>{
  const out=api.build(fixture(),deps);equal(Object.keys(out).sort(),['barTimestampSemantics','bars','breakEvent','caseId','config','dataset','identity','schemaVersion','setup','versions','zone']);equal(out.zone.formedAt,{index:1,barStartTimeUtcMs:1700086400000,closeTimeUtcMs:1700172800000});equal(out.breakEvent.at,{index:3,barStartTimeUtcMs:1700259200000,closeTimeUtcMs:1700345600000});equal(out.dataset.hash.algorithm,'SHA-256');equal(out.dataset.hash.value.length,64);
});
test('mirrored support break emits exact v2 sell envelope',()=>{
  const out=api.build(fixture('downThroughSupport'),deps);equal(out.zone.preBreakRole,'support');equal(out.breakEvent.brokenDirection,'downThroughSupport');equal(out.bars[3].close<out.zone.low,true);
});
test('only break and retest setups are accepted',()=>{const f=fixture();f.setup.setupType='A_repeatedReaction';refusal('REFUSE_SETUP_TYPE',()=>api.build(f,deps));});
test('selected setup and zone must match',()=>{const f=fixture();f.zone.id='other';refusal('REFUSE_ZONE_MATCH',()=>api.build(f,deps));});
test('the exact same candle array is required',()=>{const f=fixture();f.setupCandles=f.bars.slice();refusal('REFUSE_EXACT_CANDLE_ARRAY',()=>api.build(f,deps));});
test('identity must agree with the selected setup',()=>{const f=fixture();f.identity.timeframe='H1';refusal('REFUSE_IDENTITY_MATCH',()=>api.build(f,deps));});
test('timeframe cadence must agree with the exact candle array',()=>{const f=fixture();f.setup.timeframe='H1';f.identity.timeframe='H1';refusal('REFUSE_BAR_CADENCE',()=>api.build(f,deps));});
test('timestamps must be safe integer UTC milliseconds',()=>{const f=fixture();f.bars[2].t=1700172800000.5;refusal('REFUSE_BAR_SHAPE',()=>api.build(f,deps));});
test('the v2 10000-bar resource ceiling is enforced',()=>{const f=fixture(),last=f.bars[f.bars.length-1];while(f.bars.length<=10000){const i=f.bars.length;f.bars.push({t:new Date(last.t.getTime()+(i-7)*86400000),o:100,h:100.2,l:99.8,c:100});}refusal('REFUSE_EXACT_CANDLE_ARRAY',()=>api.build(f,deps));});
test('setup zone break and reaction identities must be nonempty',()=>{for(const field of ['setupId','zoneId','breakCycleId','reactionId']){const f=fixture();f.setup[field]='';refusal('REFUSE_SETUP_IDENTITY',()=>api.build(f,deps));}const g=fixture();g.zone.id='';refusal('REFUSE_ZONE_MATCH',()=>api.build(g,deps));});
test('explicit versions and valid v2 configuration values are required',()=>{const f=fixture();delete f.versions.appVersion;refusal('REFUSE_VERSIONS',()=>api.build(f,deps));const g=fixture();delete g.config.minRR;refusal('REFUSE_CONFIG',()=>api.build(g,deps));const h=fixture();h.config.atrPeriod=1.5;refusal('REFUSE_CONFIG',()=>api.build(h,deps));const i=fixture();i.config.minRR=0;refusal('REFUSE_CONFIG',()=>api.build(i,deps));});
test('dataset identity is SHA-256-shaped and recomputed before output',()=>{const f=fixture();f.dataset.hash.value='0'.repeat(64);refusal('REFUSE_DATASET_HASH',()=>api.build(f,deps));const g=fixture();g.dataset.hash.algorithm='MD5';refusal('REFUSE_DATASET_IDENTITY',()=>api.build(g,deps));});
test('break geometry and event ordering fail closed',()=>{const f=fixture();f.setup.brokenAtBar=1;f.setup.brokenAt=f.bars[2].t.getTime();refusal('REFUSE_EVENT_ORDER',()=>api.build(f,deps));const g=fixture();g.bars[3].l=100;g.bars[3].c=100.2;refusal('REFUSE_BREAK_GEOMETRY',()=>api.build(g,deps));});
test('retest anchor and timestamps must be explicit and exact',()=>{const f=fixture();f.retestTouch.reactionId='wrong';refusal('REFUSE_RETEST_ANCHOR',()=>api.build(f,deps));const g=fixture();g.setup.qualificationTimestamp++;refusal('REFUSE_QUALIFICATION_TIMESTAMP',()=>api.build(g,deps));});
test('bar shape and ordering fail closed',()=>{const f=fixture();f.bars[2].h=f.bars[2].l-1;refusal('REFUSE_BAR_SHAPE',()=>api.build(f,deps));const g=fixture();g.bars[3].t=g.bars[2].t;refusal('REFUSE_BAR_ORDER',()=>api.build(g,deps));});
test('no dependency means no hash verification',()=>refusal('REFUSE_HASH_DEPENDENCY',()=>api.build(fixture(),{})));
test('seam has no call site, automatic wiring, IO, or persistence references',()=>{
  equal((html.match(/alexGBuildLeanZoneRequestV2\s*\(/g)||[]).length,1,'seam must have no call site');
  const executable=seam.replace(/\/\*[\s\S]*?\*\//g,'').replace(/\/\/[^\n]*/g,'');
  ['fetch\\s*\\(','localStorage','download','upload','createObjectURL','JSON\\.stringify','setItem\\s*\\(','POST\\b'].forEach(pattern=>{
    if(new RegExp(pattern).test(executable)) throw new Error('forbidden seam reference: '+pattern);
  });
});
results.forEach(r=>console.log((r.pass?'PASS':'FAIL')+' -- '+r.name+(r.detail?' ('+r.detail+')':'')));
const failed=results.filter(r=>!r.pass).length;console.log('---');console.log(failed?'FAILURES: '+failed+'/'+results.length:'ALL PRODUCTION EMITTER SEAM FIXTURES PASSED');process.exitCode=failed?1:0;
