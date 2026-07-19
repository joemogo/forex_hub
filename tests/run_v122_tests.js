// Self-contained runner for the v12.2.0 Multi-Strategy Foundation (ADR-006) fixture suite.
// Same extraction/stub pattern as every other tests/run_*_tests.js runner in this repo.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v122_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically)
ObjC.import('Foundation');
function readFile(path){
  const s=$.NSString.stringWithContentsOfFileEncodingError(path,$.NSUTF8StringEncoding,null);
  return ObjC.unwrap(s);
}
function extractScriptBody(html){
  const m=html.match(/<script>([\s\S]*)<\/script>/);
  if(!m) throw new Error('Could not find <script>...</script> body in index.html -- run this from the project root.');
  return m[1];
}
const html=readFile('./index.html');
const appCode=extractScriptBody(html);
const testCode=readFile('./tests/v122_multi_strategy_foundation_tests.js');

const elMap={};
function makeClassList(){
  const classes=new Set();
  return{
    add:function(c){classes.add(c);},
    remove:function(c){classes.delete(c);},
    toggle:function(c,force){ if(force===undefined){ if(classes.has(c)) classes.delete(c); else classes.add(c); } else if(force) classes.add(c); else classes.delete(c); },
    contains:function(c){return classes.has(c);}
  };
}
function makeStub(){
  return {innerHTML:'',textContent:'',value:'',className:'',style:{},options:[{value:'All'}],width:100,height:100,disabled:false,checked:false,
    classList:makeClassList(),
    getContext:function(){return{clearRect:function(){},beginPath:function(){},moveTo:function(){},lineTo:function(){},stroke:function(){},fillRect:function(){},save:function(){},restore:function(){},setLineDash:function(){},arc:function(){},fill:function(){},closePath:function(){},fillText:function(){},measureText:function(){return{width:0};}};},
    appendChild:function(){},addEventListener:function(){},focus:function(){},setSelectionRange:function(){},
    getBoundingClientRect:function(){return{top:0,left:0,width:0,height:0};}};
}
const lsStore={};
globalThis.document={
  getElementById:function(id){ if(!elMap[id]) elMap[id]=makeStub(); return elMap[id]; },
  querySelector:function(){return null;},
  querySelectorAll:function(){return [];},
  createElement:function(){return makeStub();},
  addEventListener:function(){},
  body:{appendChild:function(){},removeChild:function(){}},
  activeElement:null
};
globalThis.window={devicePixelRatio:1};
globalThis.localStorage={
  getItem:function(k){return Object.prototype.hasOwnProperty.call(lsStore,k)?lsStore[k]:null;},
  setItem:function(k,v){lsStore[k]=v;},
  removeItem:function(k){delete lsStore[k];},
  __keys:function(){return Object.keys(lsStore);}
};
globalThis.fetch=function(){return Promise.reject(new Error('no network'));};
globalThis.alert=function(){};globalThis.confirm=function(){return true;};
globalThis.Blob=function(parts,opts){return{parts,opts};};
globalThis.URL={createObjectURL:function(){return 'blob:stub';},revokeObjectURL:function(){}};
let __fakeTimerId=0;
globalThis.setTimeout=function(){return ++__fakeTimerId;};globalThis.clearTimeout=function(){};
globalThis.setInterval=function(){return ++__fakeTimerId;};globalThis.clearInterval=function(){};
globalThis.ResizeObserver=function(){return{observe:function(){},disconnect:function(){}};};
globalThis.LightweightCharts={LineStyle:{Solid:0,Dashed:1,Dotted:2},CrosshairMode:{Normal:0}};
globalThis.Notification=undefined;

const g={};
const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // -- Strategy Registry / Manifest / Services / resolvers under test --
  'g.getRegistry=function(){return STRATEGY_REGISTRY;};' +
  'g.setRegistry=function(v){STRATEGY_REGISTRY.length=0;v.forEach(e=>STRATEGY_REGISTRY.push(e));};' +
  'g.findStrategyEntry=findStrategyEntry;' +
  'g.findStrategyEntryByLabel=findStrategyEntryByLabel;' +
  'g.resolveStrategyEntryForRecord=resolveStrategyEntryForRecord;' +
  'g.normalizeJournalRecord=normalizeJournalRecord;' +
  'g.buildJVMJournalOpenRecord=buildJVMJournalOpenRecord;' +
  'g.buildAlexJournalOpenRecord=buildAlexJournalOpenRecord;' +
  'g.getUnknownBadgeColor=function(){return STRATEGY_UNKNOWN_BADGE_COLOR;};' +
  'g.getMiniJournalInspectorId=function(label){const e=resolveStrategyEntryForRecord({strategyLabel:label});return e?e.manifest.inspectorCardId:"tradeInspectorCard";};' +
  // -- record-level / registry-level seams under test --
  'g.getUnifiedJournalRecords=getUnifiedJournalRecords;' +
  'g.journalStrategyBadge=journalStrategyBadge;' +
  'g.renderMiniJournal=renderMiniJournal;' +
  'g.renderDashboard=renderDashboard;' +
  'g.showPanel=showPanel;' +
  'g.setDeveloperMode=function(v){developerModeEnabled=v;};' +
  'g.applyDeveloperModeVisibility=applyDeveloperModeVisibility;' +
  'g.renderRules=renderRules;' +
  'g.setStrategyCenterTab=setStrategyCenterTab;' +
  // -- trading/journal state --
  'g.setPaperAccount=function(v){paperAccount=v;};g.getPaperAccount=function(){return paperAccount;};' +
  'g.setAlexGAccount=function(v){alexGAccount=v;};g.getAlexGAccount=function(){return alexGAccount;};' +
  'g.setJournalEntries=function(v){journalEntries=v;};g.getJournalEntries=function(){return journalEntries;};' +
  'g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};g.getAlexGJournalEntries=function(){return alexGJournalEntries;};' +
  // -- DOM stub accessors --
  'g.getElementHtml=function(id){return document.getElementById(id).innerHTML;};' +
  'g.getElementStyleDisplay=function(id){return document.getElementById(id).style.display;};' +
  'g.setElementDisplay=function(id,v){document.getElementById(id).style.display=v;};' +
  'return runV122Fixtures(g);'
);
const results = wrapped(g);
results.forEach(r=>console.log((r.pass?'PASS':'FAIL')+' -- '+r.name+(r.detail?' ('+r.detail+')':'')));
const failCount=results.filter(r=>!r.pass).length;
console.log('---');
console.log(failCount===0?'ALL v12.2.0 MULTI-STRATEGY FOUNDATION FIXTURES PASSED':('FAILURES: '+failCount+'/'+results.length));
