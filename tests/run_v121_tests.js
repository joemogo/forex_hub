// Self-contained runner for the v12.1.0 Strategy Framework fixture suite (JVM registration,
// Release 2). Requires no separate extraction/preprocessing step -- reads index.html
// directly and extracts its <script> body itself.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v121_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically, alongside run_v120_tests.js)
//
// (Paths below are relative to the current working directory, not to this file's
// location, matching every other suite's documented convention in docs/TESTING.md.)
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
const testCode=readFile('./tests/v121_jvm_registration_tests.js');

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
  return {innerHTML:'',textContent:'',value:'',className:'',style:{},options:[{value:'All'}],width:100,height:100,disabled:false,
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
let __fakeTimerId=0;
globalThis.setTimeout=function(){return ++__fakeTimerId;};globalThis.clearTimeout=function(){};
globalThis.setInterval=function(){return ++__fakeTimerId;};globalThis.clearInterval=function(){};
globalThis.ResizeObserver=function(){return{observe:function(){},disconnect:function(){}};};
globalThis.LightweightCharts={LineStyle:{Solid:0,Dashed:1,Dotted:2},CrosshairMode:{Normal:0}};

const g={};
const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // -- Strategy Registry / Manifest / Services --
  'g.getRegistry=function(){return STRATEGY_REGISTRY;};' +
  'g.setRegistry=function(v){STRATEGY_REGISTRY.length=0;v.forEach(e=>STRATEGY_REGISTRY.push(e));};' +
  'g.getStrategyManifest=getStrategyManifest;' +
  'g.getStrategyServices=getStrategyServices;' +
  'g.getMogoStrategyMeta=function(){return MOGO_STRATEGY_META;};' +
  'g.normalizeJournalRecord=normalizeJournalRecord;' +
  'g.computeMogoStrategyPerformance=computeMogoStrategyPerformance;' +
  // -- trading/journal state --
  'g.setAlexGAccount=function(v){alexGAccount=v;};' +
  'g.getAlexGAccount=function(){return alexGAccount;};' +
  'g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
  'g.getAlexGJournalEntries=function(){return alexGJournalEntries;};' +
  'g.setPaperAccount=function(v){paperAccount=v;};' +
  'g.getPaperAccount=function(){return paperAccount;};' +
  'g.setJournalEntries=function(v){journalEntries=v;};' +
  'g.getJournalEntries=function(){return journalEntries;};' +
  'g.setScanData=function(v){scanData=v;};' +
  'g.getScanData=function(){return scanData;};' +
  'g.setAutoTradingUnseenCount=function(v){autoTrading.unseenCount=v;};' +
  'g.getAutoTradingUnseenCount=function(){return autoTrading.unseenCount;};' +
  'g.getUnifiedJournalRecords=getUnifiedJournalRecords;' +
  'g.getFilteredJournalRecords=getFilteredJournalRecords;' +
  'g.renderMiniJournal=renderMiniJournal;' +
  'g.journalStrategyBadge=journalStrategyBadge;' +
  // -- render/panel/dev-tools --
  'g.renderDashboard=renderDashboard;' +
  'g.showPanel=showPanel;' +
  'g.setDeveloperMode=function(v){developerModeEnabled=v;};' +
  'g.applyDeveloperModeVisibility=applyDeveloperModeVisibility;' +
  'g.toggleDeveloperMode=toggleDeveloperMode;' +
  'g.getAppVersion=function(){return APP_VERSION;};' +
  // -- DOM stub accessors --
  'g.getElementHtml=function(id){return document.getElementById(id).innerHTML;};' +
  'g.getElementText=function(id){return document.getElementById(id).textContent;};' +
  'g.setElementText=function(id,v){document.getElementById(id).textContent=v;};' +
  'g.getElementStyleDisplay=function(id){return document.getElementById(id).style.display;};' +
  'g.setElementDisplay=function(id,v){document.getElementById(id).style.display=v;};' +
  'g.getAllLocalStorageKeys=function(){return localStorage.__keys();};' +
  'return runV121Fixtures(g);'
);
const results = wrapped(g);
results.forEach(r=>console.log((r.pass?'PASS':'FAIL')+' -- '+r.name+(r.detail?' ('+r.detail+')':'')));
const failCount=results.filter(r=>!r.pass).length;
console.log('---');
console.log(failCount===0?'ALL v12.1.0 JVM REGISTRATION FIXTURES PASSED':('FAILURES: '+failCount+'/'+results.length));
