// RUN_ALL_EXEC: node tests/run_v133_lean_forward_observer_seam_tests.js
const fs=require('fs');
const html=fs.readFileSync('index.html','utf8');
const standalone=fs.readFileSync('platform/lean/alexg_forward_observer.js','utf8');
const emitter=html.match(/\/\/ MOGO_LEAN_PRODUCTION_EMITTER_SEAM_START([\s\S]*?)\/\/ MOGO_LEAN_PRODUCTION_EMITTER_SEAM_END/);
if(!emitter) throw new Error('emitter seam marker missing');
const exported=require('../platform/lean/alexg_forward_observer.js');
const api={observe:exported.alexGObserveNewLeanBreakRetest,defaultEnabled:exported.MOGO_LEAN_FORWARD_OBSERVER_DEFAULT_ENABLED};
const results=[];
function test(name,fn){try{fn();results.push({name,pass:true});}catch(e){results.push({name,pass:false,detail:e&&e.stack||String(e)});}}
function equal(a,b,m){if(a!==b) throw new Error(m||`${a} !== ${b}`);}
function refusal(code,fn){try{fn();throw new Error('accepted');}catch(e){if(e.message==='accepted'||e.code!==code) throw e;}}
const a={setupId:'A',setupType:'A_repeatedReaction'};
const b={setupId:'B',setupType:'B_breakRetest',pair:'EUR_USD',timeframe:'H1'};
const c={setupId:'C',setupType:'B_breakRetest'};

test('disabled by default and requires explicit per-call capability',()=>{equal(api.defaultEnabled,false);refusal('REFUSE_OBSERVER_DISABLED',()=>api.observe({enabled:false,beforeSetups:[],afterSetups:[]}));});
test('returns the exact single newly observed B&R object',()=>{const after=[a,b];equal(api.observe({enabled:true,beforeSetups:[a],afterSetups:after}),b);});
test('returns null when no new B&R exists',()=>{equal(api.observe({enabled:true,beforeSetups:[a],afterSetups:[a]}),null);equal(api.observe({enabled:true,beforeSetups:[],afterSetups:[a]}),null);});
test('requires separate before and after snapshots',()=>{const same=[];refusal('REFUSE_OBSERVER_SNAPSHOTS',()=>api.observe({enabled:true,beforeSetups:same,afterSetups:same}));});
test('fails closed on missing or duplicate identities',()=>{refusal('REFUSE_OBSERVER_SETUP_IDENTITY',()=>api.observe({enabled:true,beforeSetups:[],afterSetups:[{}]}));refusal('REFUSE_OBSERVER_DUPLICATE_IDENTITY',()=>api.observe({enabled:true,beforeSetups:[],afterSetups:[b,b]}));});
test('fails closed when one sweep contains multiple new B&R setups',()=>{refusal('REFUSE_OBSERVER_AMBIGUOUS_NEW_SETUP',()=>api.observe({enabled:true,beforeSetups:[],afterSetups:[b,c]}));});
test('has no call site, IO, timers, persistence, export, or trading references',()=>{
  equal((html.match(/alexGObserveNewLeanBreakRetest\s*\(/g)||[]).length,0,'application must have no observer call site');
  const executable=standalone.replace(/\/\*[\s\S]*?\*\//g,'').replace(/\/\/[^\n]*/g,'');
  ['fetch\\s*\\(','localStorage','setInterval','setTimeout','download','upload','createObjectURL','alexGBuildLeanZoneRequestV2\\s*\\(','openPaperPosition','order','POST\\b'].forEach(pattern=>{if(new RegExp(pattern,'i').test(executable)) throw new Error('forbidden observer reference: '+pattern);});
});
results.forEach(r=>console.log((r.pass?'PASS':'FAIL')+' -- '+r.name+(r.detail?' ('+r.detail+')':'')));
const failed=results.filter(r=>!r.pass).length;
console.log('---');console.log(failed?'FAILURES: '+failed+'/'+results.length:'ALL FORWARD OBSERVER SEAM FIXTURES PASSED');
process.exitCode=failed?1:0;
