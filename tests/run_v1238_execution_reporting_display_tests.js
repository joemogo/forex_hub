// Self-contained runner for the v12.3.8 EXECUTION REPORTING DISPLAY fixture suite.
//
// WHY THIS SUITE EXISTS. A mutation re-score of the paper-trade execution REPORTING surface
// found that 79 of 110 behaviour-changing mutations killed zero fixtures. The structural cause
// was that NOTHING THAT RENDERS WAS OBSERVED: no fixture in the repository called renderPaper(),
// renderPaperMiniJournal(), renderJournalRecordRows(), renderAlexGLiveClosedTable(),
// renderTiMetrics(), fmtRMult() or fmtDuration(), and no fixture read back the DOM ids
// 'paper-stats', 'paper-closed', 'paperMiniJournal', 'alexgLiveStats', 'alexgLiveClosedTable'
// or 'tradeInspectorPanelBody'. Every number the operator actually SEES about a real executed
// trade could be sign-flipped, swapped, truncated or silenced with no fixture objecting.
//
// WHAT THIS SUITE DOES. It drives the REAL, unmodified render functions against isolated,
// in-memory state, then reads the resulting innerHTML back out of the stubbed DOM and asserts
// the EXACT rendered string -- a literal chosen and computed by hand in the fixture, never a
// value re-derived the way the renderer derives it. No fixture here asserts against source
// text, and no fixture compares two outputs of the same computation.
//
// NO REAL PAPER TRADE IS EVER PERSISTED: this process has stubbed localStorage and stubbed
// fetch and no access to any real saved data in the first place.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1238_execution_reporting_display_tests.js
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
try{
const html=readFile('./index.html');
const appCode=extractScriptBody(html);
const testCode=readFile('./tests/v1238_execution_reporting_display_tests.js');

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
  __keys:function(){return Object.keys(lsStore);},
  __clear:function(){Object.keys(lsStore).forEach(k=>delete lsStore[k]);}
};
globalThis.fetch=function(){return Promise.reject(new Error('no network'));};
globalThis.alert=function(){};
globalThis.confirm=function(){return true;};
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
  // ── the RENDERERS under test: real, unmodified. Every one of these writes into the DOM
  //    (or is reached by one that does); no fixture calls a formatter helper directly, so a
  //    "covered but wired to nothing" pass is impossible here. ──
  'g.renderPaper=renderPaper;' +
  'g.renderPaperMiniJournal=renderPaperMiniJournal;' +
  'g.renderJournal=renderJournal;' +
  'g.renderAlexGLivePanel=renderAlexGLivePanel;' +
  'g.renderAlexGLiveClosedTable=renderAlexGLiveClosedTable;' +
  'g.renderTradeInspectorPanel=renderTradeInspectorPanel;' +
  'g.openTradeInspector=openTradeInspector;' +
  'g.getFilteredJournalRecords=getFilteredJournalRecords;' +
  'g.getUnifiedJournalRecords=getUnifiedJournalRecords;' +
  // ── DOM read-back ──
  'g.elHtml=function(id){ var e=document.getElementById(id); return e?String(e.innerHTML||""):null; };' +
  'g.elText=function(id){ var e=document.getElementById(id); return e?String(e.textContent||""):null; };' +
  'g.clearEl=function(id){ var e=document.getElementById(id); if(e){e.innerHTML="";e.textContent="";} };' +
  // ── state set ──
  'g.setPaperAccount=function(v){paperAccount=v;};' +
  'g.setJournalEntries=function(v){journalEntries=v;};' +
  'g.setAlexGAccount=function(v){alexGAccount=v;};' +
  'g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
  'g.setPaperResetHistory=function(v){paperResetHistory=v;};' +
  'g.setTradeNotes=function(v){tradeNotes=v;};' +
  'g.setHideTestTradesPaper=function(v){hideTestTradesPaper=v;};' +
  'g.setHideTestTradesAlex=function(v){hideTestTradesAlex=v;};' +
  'g.setAlexGLiveSetupStatuses=function(v){alexGLiveSetupStatuses=v;};' +
  'g.setPairData=function(pair,price){ if(price===null||price===undefined){ delete pairData[pair]; } else { pairData[pair]={price:price}; } };' +
  'g.resetJournalFilters=function(){journalFilters={strategy:"All",source:"All",status:"All",result:"All",pair:"All",timeframe:"All",setup:"",dateFrom:"",dateTo:""};};' +
  'g.clearLocalStorage=function(){localStorage.__clear();};' +
  'return runExecutionReportingDisplayFixtures(g);'
);
const results = wrapped(g);
results.forEach(r=>{
  const tag = r.pass===null ? 'NOTE' : (r.pass?'PASS':'FAIL');
  console.log(tag+' -- '+r.name+': '+r.desc+(r.detail?' ['+r.detail+']':''));
});
const executed=results.filter(r=>r.pass!==null);
const failCount=executed.filter(r=>!r.pass).length;
const noteCount=results.length-executed.length;
console.log('---');
console.log(failCount===0
  ?('ALL EXECUTION REPORTING DISPLAY FIXTURES PASSED ('+executed.length+' executed, '+noteCount+' disclosed notes)')
  :('FAILURES: '+failCount+'/'+executed.length+' executed ('+noteCount+' disclosed notes)'));
}catch(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
}
