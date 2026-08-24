// Self-contained runner for the Paper Trading Operational Audit fixture suite. Requires no
// separate extraction/preprocessing step -- reads index.html directly and extracts its
// <script> body itself, following the same pattern as run_v1212_tests.js/run_v1213_tests.js.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v_paper_trading_audit_tests.js
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
const testCode=readFile('./tests/v_paper_trading_audit_tests.js');

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
  // -- paper-ledger engine functions under test (real, unmodified, protected) --
  'g.openPaperPosition=openPaperPosition;' +
  'g.TRADE_GEOMETRY=TRADE_GEOMETRY;' +
  'g.paperAuditRehydratedPositions=paperAuditRehydratedPositions;' +
  'g.tradeIntegrityIsQuarantined=tradeIntegrityIsQuarantined;' +
  'g.evaluateTradeIntegrity=evaluateTradeIntegrity;' +
  'g.checkPaperPositions=checkPaperPositions;' +
  'g.closingIds=function(){return Array.from(paperPositionsClosing);};' +
  'g.clearClosing=function(){paperPositionsClosing.clear();};' +
  'g.setPairPriceD3=function(p,v){ if(!pairData[p]) pairData[p]={}; pairData[p].price=v; };' +
  'g.MIN_RISK_PIPS=MIN_RISK_PIPS;' +
  'g.closePaperPosition=closePaperPosition;' +
  'g.showPanel=showPanel;' +
  'g.commitPaperLedger=commitPaperLedger;' +
  'g.loadSaved=loadSaved;' +
  'g.saveAlexG=saveAlexG;' +
  'g.alexGCloseLivePosition=alexGCloseLivePosition;' +
  'g.commitAlexGLedger=commitAlexGLedger;' +
  'g.getAlexGLedgerIntegrityWarning=function(){return alexGLedgerIntegrityWarning;};' +
  'g.getPaperLedgerIntegrityWarning=function(){return paperLedgerIntegrityWarning;};' +
  'g.getPaperEngineErrors=function(){return paperEngineErrors;};' +
  // recordPaperEngineError caps the log at 50 via unshift+slice, so once it saturates the LENGTH
  // stops changing -- which made a negative control pass in exactly the condition it existed to
  // catch. Fixtures need to reset the log and compare CONTENT, not count. (§18.8, defect D5.)
  'g.setPaperEngineErrors=function(v){paperEngineErrors=v;};' +
  'g.getAlexGEngineErrors=function(){return alexGEngineErrors;};' +
  'g.getAlexGAccountKnownVersion=function(){return alexGAccountKnownVersion;};' +
  'g.loadAlexGSaved=loadAlexGSaved;' +
  'g.resetAlexGLiveAccount=resetAlexGLiveAccount;' +
  'g.journalNoteOpenAlex=journalNoteOpenAlex;' +
  'g.rigStaleAlexGVersion=function(){localStorage.setItem("fxhub_alexg_account_version",String(alexGAccountKnownVersion+10));};' +
  'g.resetAlexGVersionGuard=function(){alexGAccountKnownVersion=0;localStorage.removeItem("fxhub_alexg_account_version");};' +
  'g.setAlexGAccountKnownVersion=function(v){alexGAccountKnownVersion=v;};' +
  'g.computeMogoStrategyPerformance=computeMogoStrategyPerformance;' +
  'g.computeCanonicalPerformance=computeCanonicalPerformance;' +
  'g.computePaperLedgerIntegrity=computePaperLedgerIntegrity;' +
  'g.computePaperTradingHealthReport=computePaperTradingHealthReport;' +
  // §18.36: setPaperBalance is a real, shipped, confirm-gated operator action that recorded nothing,
  // so it poisoned the reconciliation verdict permanently. Driven here through the real function
  // with the confirm dialog auto-accepted, exactly as an operator clicking through it.
  'g.setPaperBalance=setPaperBalance;' +
  'g.setBalanceInput=function(v){ document.getElementById("paperBalanceInput").value=String(v); };' +
  'g.buildPaperTradingHealthReportText=buildPaperTradingHealthReportText;' +
  'g.findStrategyEntry=findStrategyEntry;' +
  'g.getUnifiedJournalRecords=getUnifiedJournalRecords;' +
  'g.getFilteredJournalRecords=getFilteredJournalRecords;' +
  'g.buildTjrSessionZones=buildTjrSessionZones;' +
  'g.alexGComputeEquityStats=alexGComputeEquityStats;' +
  'g.alexGComputeReplayStats=alexGComputeReplayStats;' +
  'g.computeReplayStats=computeReplayStats;' +
  // -- MOGO-021 17.2 residual: the WARNING SURFACES, whose detection was covered but whose
  //    display could be silenced forever with zero fixtures objecting --
  'g.renderPaperLedgerBlockingBanner=renderPaperLedgerBlockingBanner;' +
  'g.renderPaperLedgerIntegrityWarningBanner=renderPaperLedgerIntegrityWarningBanner;' +
  'g.renderAlexGLedgerIntegrityWarningBanner=renderAlexGLedgerIntegrityWarningBanner;' +
  'g.evidenceBannerHtml=evidenceBannerHtml;' +
  'g.getBaselineDiagnosticsSummary=getBaselineDiagnosticsSummary;' +
  'g.computeBaselineRegistry=computeBaselineRegistry;' +
  'g.setPaperLedgerBlockingError=function(v){paperLedgerBlockingError=v;};' +
  'g.setPaperLedgerIntegrityWarning=function(v){paperLedgerIntegrityWarning=v;};' +
  'g.setAlexGLedgerIntegrityWarning=function(v){alexGLedgerIntegrityWarning=v;};' +
  'g.setEvidenceStorageBanner=function(v){evidenceStorageBanner=v;};' +
  'g.setEvidenceUnexportedCount=function(v){evidenceUnexportedCount=v;};' +
  'g.elHtml=function(id){ var e=document.getElementById(id); return e?String(e.innerHTML||""):null; };' +
  // -- MOGO-021 16.6 TRADE-ID INTEGRITY: the generator, its floor, and a freezable clock so a
  //    fixture can force MANY opens into ONE millisecond deterministically rather than hoping --
  'g.paperNextTradeId=paperNextTradeId;' +
  'g.alexGTradeId=alexGTradeId;' +
  'g.computeReconciliationPreview=computeReconciliationPreview;' +
  'g.setTradeNotes=function(v){tradeNotes=v;};' +
  'g.setPaperReconciliationAudit=function(v){paperReconciliationAudit=v;};' +
  'g.setPaperResetHistoryList=function(v){paperResetHistory=v;};' +
  'g.paperSeedTradeIdSeq=paperSeedTradeIdSeq;' +
  'g.getPaperTradeIdSeq=function(){return paperTradeIdSeq;};' +
  'g.setPaperTradeIdSeq=function(v){paperTradeIdSeq=v;};' +
  'g.freezeClock=function(ms){ if(!g.__realNow){ g.__realNow=Date.now; } Date.now=function(){return ms;}; };' +
  'g.restoreClock=function(){ if(g.__realNow){ Date.now=g.__realNow; g.__realNow=null; } };' +
  'g.realNow=function(){ return (g.__realNow||Date.now)(); };' +
  'g.setPaperResetHistory=function(v){paperResetHistory=v;};' +
  'g.setAlexGSetupState=function(v){alexGSetupState=v;};' +
  // -- state get/set --
  'g.getJournalEntries=function(){return journalEntries;};g.setJournalEntries=function(v){journalEntries=v;};' +
  'g.getPaperAccount=function(){return paperAccount;};g.setPaperAccount=function(v){paperAccount=v;};' +
  'g.getAlexGAccount=function(){return alexGAccount;};g.setAlexGAccount=function(v){alexGAccount=v;};' +
  'g.getAlexGJournalEntries=function(){return alexGJournalEntries;};g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
  'g.setPairData=function(pair,price){ if(price===null||price===undefined){ delete pairData[pair]; } else { pairData[pair]={price:price}; } };' +
  'g.setCfg=function(v){cfg=v;};g.getCfg=function(){return cfg;};' +
  'g.setAiChat=function(v){aiChat=v;};g.getAiChat=function(){return aiChat;};' +
  // -- version guard + duplicate-close guard (v11.0/v11.0.1 protections) --
  'g.rigStalePaperVersion=function(){localStorage.setItem("fxhub_paper_version",String(paperAccountKnownVersion+10));};' +
  'g.resetPaperVersionGuard=function(){paperAccountKnownVersion=0;localStorage.removeItem("fxhub_paper_version");};' +
  'g.getPaperPositionsClosingSize=function(){return paperPositionsClosing.size;};' +
  'g.resetPaperPositionsClosing=function(){paperPositionsClosing.clear();};' +
  // -- localStorage helpers --
  'g.getLocalStorageItem=function(k){return localStorage.getItem(k);};' +
  'g.setLocalStorageItem=function(k,v){localStorage.setItem(k,v);};' +
  'g.clearLocalStorage=function(){localStorage.__clear();};' +
  // -- D1: the pip-value conversion boundary. pipValuePerLot is PROTECTED and is driven REAL
  //    and UNMODIFIED here; setPairDataObj replaces the whole pairData map so a fixture can
  //    construct the exact rate-availability regime it means to test (the per-pair setPairData
  //    above can only add or delete one key at a time, which cannot express "USD_JPY absent
  //    while GBP_JPY present" without depending on whatever a previous fixture left behind).
  'g.pipValuePerLot=pipValuePerLot;g.pipSize=pipSize;' +
  // -- D4: the AI context string. buildAiContext had ZERO coverage anywhere in the repository
  //    before this, which is why a suppressed pair reaching the model as a measured "0%" market
  //    fact survived every gate. It is driven REAL here.
  'g.buildAiContext=buildAiContext;' +
  'g.setScanData=function(v){scanData=v;};g.getScanData=function(){return scanData;};' +
  'g.SCAN_PAIRS=SCAN_PAIRS;' +
  'g.setPairDataObj=function(v){pairData=v;};g.getPairData=function(){return pairData;};' +
  // -- D3C: the universal geometry invariant across ALEX and ALEX V2 --
  'g.validateTradeGeometry=validateTradeGeometry;' +
  'g.openPositionGeometryQuarantined=openPositionGeometryQuarantined;' +
  'g.alexGCheckLivePositions=alexGCheckLivePositions;' +
  'g.alexGAuditRehydratedPositions=alexGAuditRehydratedPositions;' +
  'g.auditOpenPositionsGeometry=auditOpenPositionsGeometry;' +
  'g.setAlexGEngineErrors=function(v){alexGEngineErrors=v;};' +
  'g.stubAlexExecutableCandles=function(fn){ if(!g.__realAlexFetch){ g.__realAlexFetch=alexGFetchExecutableCandles; } alexGFetchExecutableCandles=fn; };' +
  'g.restoreAlexExecutableCandles=function(){ if(g.__realAlexFetch){ alexGFetchExecutableCandles=g.__realAlexFetch; g.__realAlexFetch=null; } };' +
  'g.alexV2OpenPaperResearchTrade=alexV2OpenPaperResearchTrade;' +
  'g.getAlexV2Account=function(){return alexV2Account;};' +
  'g.resetAlexV2Account=function(){ alexV2Account={balance:10000,openPositions:[],closedPositions:[]};'+
     ' alexV2JournalEntries=[]; alexV2AutoTrading={enabled:false,tradedToday:{},log:[],activatedAt:null,tradedSignals:{}}; };' +
  'g.buildRealAlexPosition=function(){' +
     ' alexGAccount={balance:10000,startingBalance:10000,openPositions:[],closedPositions:[]};' +
     ' alexGJournalEntries=[]; alexGAutoTrading={enabled:false,tradedToday:{},log:[],activatedAt:null,tradedSignals:{}};' +
     ' var candles=[]; for(var i=0;i<60;i++){ var b=1.10000+(i%3)*0.00010;' +
     '   candles.push({t:1750000000+i*3600,o:b,h:b+0.00040,l:b-0.00040,c:b,v:100}); }' +
     ' var setup={strategy:"alex_g_sr_v1",ruleVersion:"alex_g_sr_v1",pair:"EUR_USD",timeframe:"H1",' +
     '   setupId:"AGS|alex_g_sr_v1|EUR_USD|H1|AGZ|D3C|A_repeatedReaction|AGR|D3C",setupType:"A_repeatedReaction",setupLabel:"Repeated Zone Reaction",' +
     '   zoneRoleAtQualification:"support",qualificationBarIndex:59,qualificationClose:1.10000,' +
     '   qualificationTimestamp:1750216000000,zoneId:"AGZ|D3C|1",reactionId:"AGR|D3C|1",zoneTouchNumber:3,' +
     '   zoneStrength:3,zoneQualityAtQualification:"good",zoneLow:1.09900,zoneHigh:1.10000,zoneCenter:1.09950,' +
     '   configurationSnapshot:null};' +
     ' var datasets={H1:candles}; var ba={bid:1.09999,ask:1.10001};' +
     ' var r=alexGConstructLivePosition(setup,datasets,ba,RULES_ALEXG.config,alexGAccount.balance,{});' +
     ' if(r.status!=="TRADE OPENED"||!r.position) return{ok:false,status:r.status,reason:r.reason,geometryState:null,riskPips:null};' +
     ' var p=r.position;' +
     ' var geom=validateTradeGeometry(p.direction,p.entry,p.stop,p.target,pipSize(p.pair),MIN_RISK_PIPS);' +
     ' return{ok:true,status:r.status,position:p,geometryState:geom.state,riskPips:geom.riskPips};' +
   '};' +
  'g.buildRealAlexTightPosition=function(){' +
     ' alexGAccount={balance:10000,startingBalance:10000,openPositions:[],closedPositions:[]};' +
     ' alexGJournalEntries=[]; alexGAutoTrading={enabled:false,tradedToday:{},log:[],activatedAt:null,tradedSignals:{}};' +
     ' var candles=[]; for(var i=0;i<60;i++){ var b=1.10000;' +
     '   candles.push({t:1750000000+i*3600,o:b,h:b+0.00001,l:b-0.00001,c:b,v:100}); }' +
     ' var setup={strategy:"alex_g_sr_v1",ruleVersion:"alex_g_sr_v1",pair:"EUR_USD",timeframe:"H1",' +
     '   setupId:"AGS|alex_g_sr_v1|EUR_USD|H1|AGZ|TIGHT|A_repeatedReaction|AGR|TIGHT",' +
     '   setupType:"A_repeatedReaction",setupLabel:"Repeated Zone Reaction",' +
     '   zoneRoleAtQualification:"support",qualificationBarIndex:59,qualificationClose:1.10000,' +
     '   qualificationTimestamp:1750216000000,zoneId:"AGZ|TIGHT",reactionId:"AGR|TIGHT",zoneTouchNumber:3,' +
     '   zoneStrength:3,zoneQualityAtQualification:"good",zoneLow:1.09995,zoneHigh:1.10000,zoneCenter:1.099975,' +
     '   configurationSnapshot:null};' +
     ' var datasets={H1:candles}; var ba={bid:1.09999,ask:1.10001};' +
     ' var r=alexGConstructLivePosition(setup,datasets,ba,RULES_ALEXG.config,alexGAccount.balance,{});' +
     ' if(r.status!=="TRADE OPENED"||!r.position) return{ok:false,status:r.status,reason:r.reason};' +
     ' var p=r.position;' +
     ' var geom=validateTradeGeometry(p.direction,p.entry,p.stop,p.target,pipSize(p.pair),MIN_RISK_PIPS);' +
     ' return{ok:true,status:r.status,position:p,geometryState:geom.state,riskPips:geom.riskPips,' +
     '   positionSize:p.positionSize,notionalUnits:Math.round(p.positionSize*100000)};' +
   '};' +
  'return runPaperTradingAuditFixtures(g);'
);
const results = wrapped(g);
results.forEach(r=>{
  const tag = r.pass===null ? (r.method==='source-verified'?'NOTE(source)':'NOTE(live-browser)') : (r.pass?'PASS':'FAIL');
  console.log(tag+' -- '+r.name+(r.detail?' ('+r.detail+')':''));
});
const executed=results.filter(r=>r.pass!==null);
const failCount=executed.filter(r=>!r.pass).length;
const noteCount=results.length-executed.length;
console.log('---');
console.log(failCount===0?('ALL PAPER TRADING AUDIT FIXTURES PASSED ('+executed.length+' executed, '+noteCount+' disclosed notes)'):('FAILURES: '+failCount+'/'+executed.length+' executed ('+noteCount+' disclosed notes)'));
