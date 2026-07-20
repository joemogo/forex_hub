// Self-contained runner for the v12.3.1 Strategy Workspace Framework fixture suite.
// Same extraction/stub pattern as every other tests/run_*_tests.js runner in this repo.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1231_tests.js
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
const testCode=readFile('./tests/v1231_strategy_workspace_framework_tests.js');

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
  // -- source-inspection (Phase 5 proof) --
  'g.appCodeSource='+JSON.stringify(appCode)+';' +
  // -- Strategy Registry --
  'g.getRegistry=function(){return STRATEGY_REGISTRY;};' +
  'g.setRegistry=function(v){STRATEGY_REGISTRY.length=0;v.forEach(e=>STRATEGY_REGISTRY.push(e));};' +
  'g.findStrategyEntry=findStrategyEntry;' +
  // -- nav + routing --
  'g.renderStrategyNavGroup=renderStrategyNavGroup;' +
  'g.getNavDropdownHtml=function(){return document.getElementById("navStrategiesDropdown").innerHTML;};' +
  'g.showPanel=showPanel;' +
  'g.getElementHtml=function(id){return document.getElementById(id).innerHTML;};' +
  // -- TJR workspace --
  'g.initTjrWorkspace=initTjrWorkspace;' +
  'g.setTjrWsTab=setTjrWsTab;' +
  'g.getTjrWsActiveTab=function(){return tjrWsActiveTab;};' +
  'g.renderTjrWsRulesTab=renderTjrWsRulesTab;' +
  'g.renderTjrWsDiagnosticsTab=renderTjrWsDiagnosticsTab;' +
  'g.renderTjrWsPaperTab=renderTjrWsPaperTab;' +
  'g.renderTjrWsReplayTab=renderTjrWsReplayTab;' +
  'g.renderTjrWsJournalTab=renderTjrWsJournalTab;' +
  'g.renderTjrWsDeveloperTab=renderTjrWsDeveloperTab;' +
  'g.setTjrWsZoneState=function(v){tjrWsZoneState=v;};' +
  'g.getTjrWsZoneState=function(){return tjrWsZoneState;};' +
  'g.setTjrWsChartAndSeries=function(chart,series){tjrWsChart=chart;tjrWsCandleSeries=series;};' +
  'g.setTjrWsZonesVisible=function(v){tjrWsZonesVisible=v;};' +
  'g.drawTjrWorkspaceZoneOverlay=drawTjrWorkspaceZoneOverlay;' +
  'g.clearTjrWorkspaceZoneOverlay=clearTjrWorkspaceZoneOverlay;' +
  'g.destroyTjrWorkspaceChart=destroyTjrWorkspaceChart;' +
  'g.getTjrWsChartIsNull=function(){return tjrWsChart===null;};' +
  'g.getTjrWsCandleSeriesIsNull=function(){return tjrWsCandleSeries===null;};' +
  'g.getTjrWsZoneLinesLengthDirect=function(){return tjrWsZoneLines.length;};' +
  // -- Phase 1 engine (reused, unmodified) --
  'g.buildTjrSessionZones=buildTjrSessionZones;' +
  'g.resolveTjrSessionBoundaries=resolveTjrSessionBoundaries;' +
  'g.drawTjrZoneOverlay=drawTjrZoneOverlay;' +
  'g.getSharedTjrChartZoneLinesLength=function(){return tjrChartZoneLines.length;};' +
  // -- generic named-function get/set (test-harness-only, mirrors the getSession override
  // technique already used in tests/run_v1212_tests.js) --
  'g.getWindowFn=function(name){return eval(name);};' +
  'g.setWindowFn=function(name,fn){eval(name+"=fn;");};' +
  // -- trading/journal state (isolation proof) --
  'g.setPaperAccount=function(v){paperAccount=v;};g.getPaperAccount=function(){return paperAccount;};' +
  'g.setAlexGAccount=function(v){alexGAccount=v;};g.getAlexGAccount=function(){return alexGAccount;};' +
  'g.setJournalEntries=function(v){journalEntries=v;};g.getJournalEntries=function(){return journalEntries;};' +
  'g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};g.getAlexGJournalEntries=function(){return alexGJournalEntries;};' +
  'g.getAllLocalStorageKeys=function(){return localStorage.__keys();};' +
  'return runV1231Fixtures(g);'
);
const results = wrapped(g);
results.forEach(r=>console.log((r.pass?'PASS':'FAIL')+' -- '+r.name+(r.detail?' ('+r.detail+')':'')));
const failCount=results.filter(r=>!r.pass).length;
console.log('---');
console.log(failCount===0?'ALL v12.3.1 STRATEGY WORKSPACE FRAMEWORK FIXTURES PASSED':('FAILURES: '+failCount+'/'+results.length));
