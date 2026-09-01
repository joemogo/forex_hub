// RUN_ALL_EXEC: node tests/run_v133_lean_forward_observer_seam_tests.js
const fs=require('fs'),vm=require('vm');
const html=fs.readFileSync('index.html','utf8');
const standalone=fs.readFileSync('platform/lean/alexg_forward_observer.js','utf8');
const emitter=html.match(/\/\/ MOGO_LEAN_PRODUCTION_EMITTER_SEAM_START([\s\S]*?)\/\/ MOGO_LEAN_PRODUCTION_EMITTER_SEAM_END/);
if(!emitter) throw new Error('emitter seam marker missing');
const exported=require('../platform/lean/alexg_forward_observer.js');
const api={observe:exported.alexGObserveNewLeanBreakRetest,defaultEnabled:exported.MOGO_LEAN_FORWARD_OBSERVER_DEFAULT_ENABLED};
api.handoff=exported.alexGBuildObservedLeanEmitterInput;
api.compose=exported.alexGObserveAndBuildLeanExport;
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
test('builds an exact-reference emitter handoff without invoking the emitter',()=>{
  const zone={id:'zone-1'},setup={...b,zoneId:'zone-1',reactionId:'reaction-1'},bars=[{t:1},{t:2}],retestTouch={reactionId:'reaction-1'};
  const metadata={identity:{pair:'EUR_USD',timeframe:'H1'},versions:{strategyVersion:'s'},dataset:{id:'d'},config:{minRR:2}};
  const out=api.handoff({enabled:true,observedSetup:setup,afterSetups:[setup],zone,bars,retestTouch,...metadata});
  equal(out.setup,setup);equal(out.zone,zone);equal(out.bars,bars);equal(out.setupCandles,bars);equal(out.retestTouch,retestTouch);equal(out.enabled,true);
});
test('handoff requires capability, snapshot provenance, and matching anchors',()=>{
  const setup={...b,zoneId:'zone-1',reactionId:'reaction-1'},base={observedSetup:setup,afterSetups:[setup],zone:{id:'zone-1'},bars:[{},{}],retestTouch:{reactionId:'reaction-1'},identity:{},versions:{},dataset:{},config:{}};
  refusal('REFUSE_OBSERVER_HANDOFF_DISABLED',()=>api.handoff({...base,enabled:false}));
  refusal('REFUSE_OBSERVER_HANDOFF_PROVENANCE',()=>api.handoff({...base,enabled:true,afterSetups:[{...setup}]}));
  refusal('REFUSE_OBSERVER_HANDOFF_ZONE',()=>api.handoff({...base,enabled:true,zone:{id:'other'}}));
  refusal('REFUSE_OBSERVER_HANDOFF_RETEST',()=>api.handoff({...base,enabled:true,retestTouch:{reactionId:'other'}}));
});
test('composition returns one in-memory export through an explicit emitter dependency',()=>{
  const setup={...b,zoneId:'zone-1',reactionId:'reaction-1'},bars=[{},{}];let calls=0,received=null;
  const input={enabled:true,beforeSetups:[],afterSetups:[setup],zone:{id:'zone-1'},bars,
    retestTouch:{reactionId:'reaction-1'},identity:{},versions:{},dataset:{},config:{}};
  const out=api.compose(input,{emitLeanZoneRequestV2:(handoff,deps)=>{calls++;received={handoff,deps};return {caseId:handoff.setup.setupId};},emitterDeps:{hash:true}});
  equal(calls,1);equal(out.caseId,'B');equal(received.handoff.setup,setup);equal(received.handoff.bars,bars);equal(received.deps.hash,true);
});
test('composition is disabled, dependency-injected, and emits nothing when no new B&R exists',()=>{
  const base={beforeSetups:[a],afterSetups:[a]};
  refusal('REFUSE_OBSERVER_EXPORT_DISABLED',()=>api.compose({...base,enabled:false},{}));
  refusal('REFUSE_OBSERVER_EXPORT_DEPENDENCY',()=>api.compose({...base,enabled:true},{}));
  let calls=0;equal(api.compose({...base,enabled:true},{emitLeanZoneRequestV2:()=>{calls++;}}),null);equal(calls,0);
});
test('standalone module exposes the same frozen API in a browser-like context',()=>{
  const context={};vm.createContext(context);vm.runInContext(standalone,context);
  const browserApi=context.MogoLeanForwardObserver;
  equal(typeof browserApi,'object');equal(Object.isFrozen(browserApi),true);
  equal(typeof browserApi.alexGObserveAndBuildLeanExport,'function');
  equal(browserApi.MOGO_LEAN_FORWARD_OBSERVER_DEFAULT_ENABLED,false);
  equal(browserApi.alexGObserveNewLeanBreakRetest({enabled:true,beforeSetups:[],afterSetups:[]}),null);
});
test('has no call site, IO, timers, persistence, export, or trading references',()=>{
  equal((html.match(/alexGObserveNewLeanBreakRetest\s*\(/g)||[]).length,0,'application must have no observer call site');
  const executable=standalone.replace(/\/\*[\s\S]*?\*\//g,'').replace(/\/\/[^\n]*/g,'');
  ['fetch\\s*\\(','localStorage','setInterval','setTimeout','download','upload','createObjectURL','openPaperPosition','order','POST\\b'].forEach(pattern=>{if(new RegExp(pattern,'i').test(executable)) throw new Error('forbidden observer reference: '+pattern);});
  equal((executable.match(/alexGBuildLeanZoneRequestV2\s*\(/g)||[]).length,0,'handoff must not invoke emitter');
  equal((html.match(/alexGObserveAndBuildLeanExport\s*\(/g)||[]).length,0,'application must have no composition call site');
  equal(html.includes('platform/lean/alexg_forward_observer.js'),false,'application must not load observer module');
});
results.forEach(r=>console.log((r.pass?'PASS':'FAIL')+' -- '+r.name+(r.detail?' ('+r.detail+')':'')));
const failed=results.filter(r=>!r.pass).length;
console.log('---');console.log(failed?'FAILURES: '+failed+'/'+results.length:'ALL FORWARD OBSERVER SEAM FIXTURES PASSED');
process.exitCode=failed?1:0;
