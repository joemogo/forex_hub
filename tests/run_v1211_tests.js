// Self-contained runner for the v12.1.1 Diagnostics Data Integrity fixture suite
// (journal-only-orphan leak fix). Requires no separate extraction/preprocessing step --
// reads index.html directly and extracts its <script> body itself.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1211_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically, alongside the other suites)
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
const testCode=readFile('./tests/v1211_diagnostics_integrity_tests.js');

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
  // -- the v12.1.1 Diagnostics-only snapshot/restore helper --
  'g.diagSnapshot=diagSnapshot;' +
  'g.diagRestore=diagRestore;' +
  // -- trading/journal state --
  'g.setJournalEntries=function(v){journalEntries=v;};' +
  'g.getJournalEntries=function(){return journalEntries;};' +
  'g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
  'g.getAlexGJournalEntries=function(){return alexGJournalEntries;};' +
  'g.setPaperAccount=function(v){paperAccount=v;};' +
  'g.getPaperAccount=function(){return paperAccount;};' +
  'g.setAlexGAccount=function(v){alexGAccount=v;};' +
  'g.getAlexGAccount=function(){return alexGAccount;};' +
  'g.setPairData=function(v){pairData=v;};' +
  'g.getPairData=function(){return pairData;};' +
  'g.setActivePair=function(v){activePair=v;};' +
  'g.getActivePair=function(){return activePair;};' +
  'g.setScanData=function(v){scanData=v;};' +
  'g.getScanData=function(){return scanData;};' +
  // -- real production functions the fixed checks call --
  'g.pipValuePerLot=pipValuePerLot;' +
  'g.placePaperTrade=placePaperTrade;' +
  'g.commitPaperLedger=commitPaperLedger;' +
  // -- R:R Calculator DOM field helper --
  'g.setRrFields=function(e,s,t){document.getElementById("rrEntry").value=e;document.getElementById("rrStop").value=s;document.getElementById("rrTarget").value=t;};' +
  // -- localStorage helpers --
  'g.getLocalStorageItem=function(k){return localStorage.getItem(k);};' +
  'g.setLocalStorageItem=function(k,v){localStorage.setItem(k,v);};' +
  'g.removeLocalStorageItem=function(k){localStorage.removeItem(k);};' +
  'g.getAllLocalStorageKeys=function(){return localStorage.__keys();};' +
  'return runV1211Fixtures(g);'
);
const results = wrapped(g);
results.forEach(r=>console.log((r.pass?'PASS':'FAIL')+' -- '+r.name+(r.detail?' ('+r.detail+')':'')));
const failCount=results.filter(r=>!r.pass).length;
console.log('---');
console.log(failCount===0?'ALL v12.1.1 DIAGNOSTICS DATA INTEGRITY FIXTURES PASSED':('FAILURES: '+failCount+'/'+results.length));
