// Self-contained runner for the G-4 exit provenance (MOGO-024) fixture suite. Requires no separate
// extraction/preprocessing step -- reads index.html directly and extracts its <script> body
// itself, following the same pattern as run_v1212_tests.js.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v1213_tests.js
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
const testCode=readFile('./tests/v1241_exit_provenance_tests.js');

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
globalThis.alert=function(){};
// __confirmState is a genuine global (not an outer-script `let`) because functions created via
// `new Function(...)` below only close over the realm's global environment, not this runner
// script's own lexical scope -- a bare `__confirmState` reference inside that Function's body
// resolves through globalThis, so it must actually live there.
globalThis.__confirmState={returnVal:true,lastMsg:''};
globalThis.confirm=function(msg){__confirmState.lastMsg=msg;return __confirmState.returnVal;};
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
  // -- escaping / rendering under test --
  'g.escapeHtml=escapeHtml;' +
  'g.inspectorRows=inspectorRows;' +
  'g.renderTradeInspectorContent=renderTradeInspectorContent;' +
  'g.renderAlertLog=renderAlertLog;' +
  'g.setAlertLog=function(v){alertLog=v;};' +
  'g.getElementHtml=function(id){return document.getElementById(id).innerHTML;};' +
  // -- Manual Lock --
  'g.isLocked=function(){return mogoLock.locked;};' +
  'g.setLocked=function(v){mogoLock.locked=v;};' +
  'g.mogoLockNow=mogoLockNow;' +
  'g.mogoUnlock=mogoUnlock;' +
  'g.mogoLockBlocked=mogoLockBlocked;' +
  'g.getOverlayDisplay=function(){return document.getElementById("mogoLockOverlay").style.display;};' +
  // -- guarded actions under test --
  'g.toggleAutoTrading=toggleAutoTrading;' +
  'g.toggleAlexGLiveTrading=toggleAlexGLiveTrading;' +
  'g.disconnect=disconnect;' +
  'g.saveAiKey=saveAiKey;' +
  // §18.30: the OANDA-token fixtures installed a sentinel into cfg and read localStorage
  // IMMEDIATELY -- zero production persistence ran in between, so no behaviour of any persistence
  // path could make them fail. These exports let them exercise the REAL write surface while the
  // sentinel is live, and give the assertion a positive control.
  'g.exercisePersistence=function(){' +
  '  var n=0;' +
  '  try{ save(); n++; }catch(e){}' +
  '  try{ saveAlexGRest(); n++; }catch(e){}' +
  '  try{ commitPaperLedger(); n++; }catch(e){}' +
  '  try{ saveChecklist(); n++; }catch(e){}' +
  '  try{ saveTradeNotes(); n++; }catch(e){}' +
  '  try{ persistStorageKey("fxhub_scan",JSON.stringify(scanData||{})); n++; }catch(e){}' +
  '  return n;' +
  '};' +
  'g.plantSentinelInStorage=function(k,v){ try{ localStorage.setItem(k,v); }catch(e){} };' +
  'g.clearAiKey=clearAiKey;' +
  'g.clearAiChat=clearAiChat;' +
  'g.deleteEntry=deleteEntry;' +
  'g.confirmPaperResetAccountOnly=confirmPaperResetAccountOnly;' +
  'g.confirmPaperResetFull=confirmPaperResetFull;' +
  'g.clearTestTradesPaper=clearTestTradesPaper;' +
  'g.confirmPaperReconciliationUI=confirmPaperReconciliationUI;' +
  'g.resetAlexGLiveAccount=resetAlexGLiveAccount;' +
  'g.setPaperBalance=setPaperBalance;' +
  'g.approveManualReviewTrade=approveManualReviewTrade;' +
  // -- state get/set --
  'g.getCfg=function(){return cfg;};g.setCfg=function(v){cfg=v;};' +
  'g.getAiChat=function(){return aiChat;};g.setAiChat=function(v){aiChat=v;};' +
  'g.getAutoTrading=function(){return autoTrading;};g.setAutoTrading=function(v){autoTrading=v;};' +
  'g.getAlexGAutoTrading=function(){return alexGAutoTrading;};g.setAlexGAutoTrading=function(v){alexGAutoTrading=v;};' +
  'g.getJournalEntries=function(){return journalEntries;};g.setJournalEntries=function(v){journalEntries=v;};' +
  'g.getPaperAccount=function(){return paperAccount;};g.setPaperAccount=function(v){paperAccount=v;};' +
  'g.getAlexGAccount=function(){return alexGAccount;};g.setAlexGAccount=function(v){alexGAccount=v;};' +
  'g.setManualReviewCandidates=function(v){manualReviewCandidates=v;};' +
  'g.getManualReviewCandidates=function(){return manualReviewCandidates;};' +
  // -- DOM / localStorage / confirm helpers --
  'g.setElementValue=function(id,v){document.getElementById(id).value=v;};' +
  'g.getElementValue=function(id){return document.getElementById(id).value;};' +
  'g.setElementChecked=function(id,v){document.getElementById(id).checked=v;};' +
  'g.getElementChecked=function(id){return document.getElementById(id).checked;};' +
  'g.getAllLocalStorageKeys=function(){return localStorage.__keys();};' +
  'g.getLocalStorageItem=function(k){return localStorage.getItem(k);};' +
  'g.setConfirmReturn=function(v){__confirmState.returnVal=v;};' +
  'g.getLastConfirmMessage=function(){return __confirmState.lastMsg;};' +
  'g.seedOpenPosition=function(){' +
  '  var id="AGT|TEST|v1241|"+(Math.random().toString(36).slice(2));' +
  '  alexGAccount.openPositions.push({tradeId:id,signalId:id+"|sig",setupId:id+"|setup",' +
  '    strategy:"alex_g_sr_v1",ruleVersion:"v1",pair:"EUR/USD",timeframe:"H1",' +
  '    setupType:"B_breakRetest",setupLabel:"BREAK & RETEST",direction:"buy",' +
  '    entry:1.10,stop:1.09,target:1.12,plannedRR:2,riskPercent:1,riskAmount:100,' +
  '    pipValue:10,positionSize:1,balanceAtEntry:alexGAccount.balance,' +
  '    openedAt:new Date().toISOString(),atrAtEntry:0.001,' +
  '    status:"open",exitPrice:null,closedAt:null,result:null,resultR:null,pnl:null,' +
  '    maePips:0,mfePips:0,maeR:0,mfeR:0,qualificationClose:1.10,liveFillPrice:1.10,' +
  '    entryDelayPips:0,entryBid:1.0999,entryAsk:1.1001,entrySpreadPips:0.2,' +
  '    qualificationPlannedTarget:1.12,liveFillAdjustedTarget:1.12,' +
  '    exitBid:null,exitAsk:null,exitSpreadPips:null,lastExitCheckTimestamp:Date.now(),' +
  '    exitTriggerLevel:null,exitDetectionSource:null,exitDetectedAt:null,' +
  '    exitCandleStart:null,exitCandleEnd:null,ambiguous:false,ambiguousMode:null,' +
  '    createdByEngineVersion:"test",liveEvaluationFinal:true});' +
  '  return id;};' +
  'g.closeWithMeta=function(id,meta){ return alexGCloseLivePosition(id,"Loss",1.09,null,meta); };' +
  'g.closeNoMeta=function(id){ return alexGCloseLivePosition(id,"Loss",1.09,null); };' +
  'g.lastClosed=function(){ return alexGAccount.closedPositions[0]||null; };' +
  'g.closedCount=function(){ return alexGAccount.closedPositions.length; };' +
  'g.buildPackage=function(rec){ var p=evidenceBuildPackageFromTrade(rec,{strategyId:"alex_g_sr_v1"});' +
  '  return p&&p.objects?{outcome:(p.objects.outcomes||[])[0]||null,pkg:p}:{outcome:null,pkg:p}; };' +
  'g.canonicalize=function(w){ return evidenceCanonicalize(w.pkg); };' +
  'g.setDeveloperMode=function(on){ developerModeEnabled=!!on; };' +
  'g.isDeveloperMode=function(){ return !!developerModeEnabled; };' +
  'g.primeDevPrice=function(){ var op=SCAN_PAIRS[0].replace("/","_"); pairData[op]={price:1.25000}; return op; };' +
  'g.pipValueFor=function(op){ return pipValuePerLot(op); };' +
  'g.runGenerateTestAlexTrade=function(dir,forceResult){ return generateTestAlexTrade(dir,forceResult); };' +
  'g.openCount=function(){ return alexGAccount.openPositions.length; };' +
  'g.resetAlexAccount=function(){ alexGAccount={balance:10000,openPositions:[],closedPositions:[]};' +
  '  alexGJournalEntries=[]; return true; };' +
  'return runV1241Fixtures(g).concat(runV1241DeveloperPathFixtures(g));'
);
const results = wrapped(g);
results.forEach(r=>console.log((r.pass?'PASS':'FAIL')+' -- '+r.name+(r.detail?' ('+r.detail+')':'')));
const failCount=results.filter(r=>!r.pass).length;
console.log('---');
console.log(failCount===0?'ALL G-4 EXIT PROVENANCE FIXTURES PASSED':('FAILURES: '+failCount+'/'+results.length));
