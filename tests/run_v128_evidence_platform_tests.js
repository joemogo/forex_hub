// Self-contained runner for the MOGO-003 Phase 1 (Evidence Platform) fixture suite.
// Reads index.html directly and extracts its <script> body itself, following the same pattern
// as run_v127_alex_v11_release_tests.js and run_v126_phase2c_wave1_tests.js.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v128_evidence_platform_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically)
//
// DISCLOSED: this harness deliberately provides NO crypto.subtle and NO indexedDB, because
// osascript genuinely has neither. That is not a stub omission -- it is the real degraded
// environment, and several fixtures assert the honest behaviour under it.
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
const testCode=readFile('./tests/v128_evidence_platform_tests.js');

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
    appendChild:function(){},addEventListener:function(){},focus:function(){},setSelectionRange:function(){},click:function(){},files:[],
    getBoundingClientRect:function(){return{top:0,left:0,width:0,height:0};}};
}
const lsStore={};
let lsThrowing=false;
function maybeThrow(){
  if(lsThrowing){ const e=new Error('The quota has been exceeded.'); e.name='QuotaExceededError'; throw e; }
}
globalThis.document={
  getElementById:function(id){ if(!elMap[id]) elMap[id]=makeStub(); return elMap[id]; },
  querySelector:function(){return null;},
  querySelectorAll:function(){return [];},
  createElement:function(){return makeStub();},
  addEventListener:function(){},
  visibilityState:'visible',
  body:{appendChild:function(){},removeChild:function(){}},
  activeElement:null
};
globalThis.window={devicePixelRatio:1};
globalThis.localStorage={
  getItem:function(k){return Object.prototype.hasOwnProperty.call(lsStore,k)?lsStore[k]:null;},
  setItem:function(k,v){maybeThrow();lsStore[k]=v;},
  removeItem:function(k){maybeThrow();delete lsStore[k];},
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
// Deliberately absent, exactly as in the real degraded environments this release must survive:
//   crypto.subtle -- absent on a file:// origin
//   indexedDB     -- absent in this offline harness
// Nothing below stubs either of them into false existence.

const g={};
g.appSource=appCode;
// Brace-depth extraction of a real function's source, so J7/J8/J9 assert against the ACTUAL
// shipped text of protected and ledger functions rather than a paraphrase of them.
g.getSource=function(decl){
  const i=appCode.indexOf(decl);
  if(i===-1) throw new Error('function not found in index.html: '+decl);
  let depth=0,started=false;
  for(let k=i;k<appCode.length;k++){
    const c=appCode[k];
    if(c==='{'){ depth++; started=true; }
    else if(c==='}'){ depth--; if(started&&depth===0) return appCode.slice(i,k+1); }
  }
  throw new Error('unterminated function: '+decl);
};
const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // ── canonicalization + integrity (real, unmodified) ──
  'g.evidenceCanonicalize=evidenceCanonicalize;' +
  'g.evidenceCanonValue=evidenceCanonValue;' +
  'g.evidenceBytesToHex=evidenceBytesToHex;' +
  'g.evidenceHashAvailable=evidenceHashAvailable;' +
  'g.evidenceContentHash=evidenceContentHash;' +
  'g.evidenceFinalizePackage=evidenceFinalizePackage;' +
  'g.evidenceVerifyPackageHash=evidenceVerifyPackageHash;' +
  'g.getEvidenceHashAlgorithm=function(){return EVIDENCE_HASH_ALGORITHM;};' +
  'g.getEvidenceHashScope=function(){return EVIDENCE_HASH_SCOPE;};' +
  'g.getEvidenceHashClaimText=function(){return EVIDENCE_HASH_CLAIM_TEXT;};' +
  'g.getEvidenceHashExcludedFields=function(){return EVIDENCE_HASH_EXCLUDED_FIELDS;};' +
  'g.alexGStableHash=alexGStableHash;' +
  // ── construction + validation ──
  'g.evidenceBuildPackageFromTrade=evidenceBuildPackageFromTrade;' +
  'g.evidenceValidatePackage=evidenceValidatePackage;' +
  'g.evidenceComputeCompleteness=evidenceComputeCompleteness;' +
  // ── failure classification + reporting ──
  'g.evidenceClassifyStorageError=evidenceClassifyStorageError;' +
  'g.evidenceRecordWriteFailure=evidenceRecordWriteFailure;' +
  'g.getEvidenceWriteFailures=function(){return evidenceWriteFailures;};' +
  'g.getEvidenceStorageBanner=function(){return evidenceStorageBanner;};' +
  'g.resetEvidenceRuntime=function(){evidenceWriteFailures=[];evidenceStorageBanner=null;' +
    'evidenceUnexportedCount=0;evidenceUnverifiableCount=0;evidenceCaptureInFlight=false;};' +
  // ── buffer limits + eviction (pure) ──
  'g.evidenceEvictBuffers=evidenceEvictBuffers;' +
  'g.evidenceCountZonesForPair=evidenceCountZonesForPair;' +
  'g.getEvidenceSetupsMax=function(){return EVIDENCE_SETUPS_MAX;};' +
  'g.getEvidenceZonesMaxPerPair=function(){return EVIDENCE_ZONES_MAX_PER_PAIR;};' +
  // ── export / import / backfill ──
  'g.evidenceSanitizeForFilename=evidenceSanitizeForFilename;' +
  'g.evidenceExportFilename=evidenceExportFilename;' +
  'g.evidenceExportPackage=evidenceExportPackage;' +
  'g.evidencePutPackage=evidencePutPackage;' +
  'g.evidenceUpdateExportState=evidenceUpdateExportState;' +
  // ── DoD #10: JVM / current_strategy (real, unmodified) ──
  // ── v12.9.0 replay run identity + capture (real, unmodified) ──
  'g.evidenceNormalizeReplayTrade=evidenceNormalizeReplayTrade;' +
  'g.evidenceCaptureReplayTrades=evidenceCaptureReplayTrades;' +
  'g.evidenceCaptureReplayTradesAsync=evidenceCaptureReplayTradesAsync;' +
  'g.evidenceReplayDatasetHash=evidenceReplayDatasetHash;' +
  'g.alexGBuildReplayRunIdentity=alexGBuildReplayRunIdentity;' +
  'g.evidenceComputeCompleteness=evidenceComputeCompleteness;' +
  'g.evidenceNormalizeJvmTrade=evidenceNormalizeJvmTrade;' +
  'g.evidenceCaptureClosedPaperTrades=evidenceCaptureClosedPaperTrades;' +
  'g.evidenceCaptureClosedPaperTradesAsync=evidenceCaptureClosedPaperTradesAsync;' +
  'g.evidencePersistTradePackage=evidencePersistTradePackage;' +
  'g.evidencePersistTradePackageResolved=evidencePersistTradePackageResolved;' +
  'g.evidenceAllocateSequence=evidenceAllocateSequence;' +
  'g.getJvmStrategyId=function(){return EVIDENCE_JVM_STRATEGY_ID;};' +
  // ── v12.17.0 Ledger reconciliation diagnostics ──
  'g.ledgerBuildReconciliationReport=ledgerBuildReconciliationReport;' +
  'g.ledgerReconciliationDrillDown=ledgerReconciliationDrillDown;' +
  'g.ledgerReconciliationSources=ledgerReconciliationSources;' +
  'g.renderLedgerReconciliation=renderLedgerReconciliation;' +
  'g.getLedgerReconciliationStatuses=function(){return LEDGER_RECONCILIATION_STATUSES;};' +
  // ── v12.16.0 Immutable trade ledger ──
  'g.ledgerNormalizeEvent=ledgerNormalizeEvent;' +
  'g.ledgerBuildEvents=ledgerBuildEvents;' +
  'g.ledgerDeriveAccountState=ledgerDeriveAccountState;' +
  'g.ledgerReconcileBalance=ledgerReconcileBalance;' +
  'g.alexGComputeEquityStats=alexGComputeEquityStats;' +
  // ── v12.15.0 Trade integrity & quarantine ──
  'g.evaluateTradeIntegrity=evaluateTradeIntegrity;' +
  'g.tradeIntegrityIsQuarantined=tradeIntegrityIsQuarantined;' +
  'g.tradeIntegrityFilterForStatistics=tradeIntegrityFilterForStatistics;' +
  'g.tradeIntegrityReport=tradeIntegrityReport;' +
  'g.getTradeIntegrityRules=function(){return TRADE_INTEGRITY_RULES;};' +
  'g.getTradeIntegrityProfiles=function(){return TRADE_INTEGRITY_STRATEGY_PROFILES;};' +
  'g.alexGCloseLivePosition=alexGCloseLivePosition;' +
  'g.alexGUpdatePositionExcursionAndCheckExit=alexGUpdatePositionExcursionAndCheckExit;' +
  // ── v12.14.0 Unit C2-M2 higher-timeframe context ──
  'g.evidenceBuildHigherTimeframeContext=evidenceBuildHigherTimeframeContext;' +
  'g.EVIDENCE_TIMEFRAME_RANK=EVIDENCE_TIMEFRAME_RANK;' +
  'g.getRulesAlexG=function(){return RULES_ALEXG;};' +
  // ── v12.13.0 Unit C2-M1 (CORR-6) market context + lineage ──
  'g.evidenceBuildMarketContext=evidenceBuildMarketContext;' +
  'g.evidenceBuildLineage=evidenceBuildLineage;' +
  'g.alexGRunSetupReplay=alexGRunSetupReplay;' +
  // ── v12.12.0 Unit C1 (CORR-7) excursion timing ──
  'g.evidenceRecomputeExcursionTiming=evidenceRecomputeExcursionTiming;' +
  'g.alexGComputeMAEMFE=alexGComputeMAEMFE;' +
  'g.getCandleCloseTime=getCandleCloseTime;' +
  // ── v12.11.0 Unit B (CORR-1) rule attribution ──
  'g.alexGBuildRuleAttribution=alexGBuildRuleAttribution;' +
  'g.alexGAttributionRecordFromEngineInputs=alexGAttributionRecordFromEngineInputs;' +
  'g.ALEX_ATTRIBUTION_RULE_IDS=ALEX_ATTRIBUTION_RULE_IDS;' +
  'g.getAttributionConditions=function(){return ALEX_ATTRIBUTION_CONDITIONS;};' +
  'g.alexGEvaluateBreakRetest=alexGEvaluateBreakRetest;' +
  'g.alexGEvaluateRepeatedReaction=alexGEvaluateRepeatedReaction;' +
  'g.alexGClassifyTouch=alexGClassifyTouch;' +
  'g.alexGCreateSetupRecord=alexGCreateSetupRecord;' +
  'g.alexGConstructTrade=alexGConstructTrade;' +
  // ── v12.10.0 Unit A (CORR-2/3/4/8) ──
  'g.evidenceComputeRealizedR=evidenceComputeRealizedR;' +
  'g.evidenceBuildCandleRefs=evidenceBuildCandleRefs;' +
  'g.alexGSetupTypeCanonicalName=alexGSetupTypeCanonicalName;' +
  'g.alexGSetupTypeAbbreviation=alexGSetupTypeAbbreviation;' +
  'g.ALEX_SETUP_CANONICAL_NAMES=ALEX_SETUP_CANONICAL_NAMES;' +
  'g.EVIDENCE_REALIZED_R_PROVENANCE=EVIDENCE_REALIZED_R_PROVENANCE;' +
  'g.EVIDENCE_FIELD_PROVENANCE=EVIDENCE_FIELD_PROVENANCE;' +
  'g.EVIDENCE_PACKAGE_SCHEMA_VERSION=EVIDENCE_PACKAGE_SCHEMA_VERSION;' +
  'g.EVIDENCE_REPLAY_RELEASE_GATES=EVIDENCE_REPLAY_RELEASE_GATES;' +
  'g.runAlexGReplay=runAlexGReplay;' +
  'g.runAlexGReplayUI=runAlexGReplayUI;' +
  'g.alexGComputeReplayStats=alexGComputeReplayStats;' +
  'g.evidenceEvaluateExportReimport=evidenceEvaluateExportReimport;' +   // EXP-001 (pure)
  'g.evidenceBuildVerifiedExportState=evidenceBuildVerifiedExportState;' +
  'g.countUnexportedLike=evidenceSummarizePackages;' +                   // the REAL counting rule
  'g.evidenceImportPackageObject=evidenceImportPackageObject;' +
  'g.evidenceImportFile=evidenceImportFile;' +
  'g.evidenceBackfillFromLocalStorage=evidenceBackfillFromLocalStorage;' +
  // ── store contract ──
  'g.evidenceOpenDb=evidenceOpenDb;' +
  'g.evidenceAllocateSequence=evidenceAllocateSequence;' +
  // ── capture seam ──
  'g.evidenceCaptureClosedTrades=evidenceCaptureClosedTrades;' +
  'g.evidenceCaptureClosedTradesAsync=evidenceCaptureClosedTradesAsync;' +
  'g.evidencePersistTradePackage=evidencePersistTradePackage;' +
  'g.alexGCheckLivePositions=alexGCheckLivePositions;' +
  'g.getBaselineAlexFunctions=function(){return BASELINE_ALEX_FUNCTIONS;};' +
  // ── REAL persistence functions under correction (called, never re-implemented) ──
  'g.saveAlexGRest=saveAlexGRest;' +
  'g.saveJvm=save;' +
  // ── decision-event bus (real) ──
  'g.emitDecisionEvent=emitDecisionEvent;' +
  'g.getDecisionEvents=getDecisionEvents;' +
  'g.clearDecisionEvents=clearDecisionEvents;' +
  'g.getReasonCodeRegistry=function(){return REASON_CODE_REGISTRY;};' +
  // ── live-binding accessors, so a fixture observes what the real code actually did ──
  'g.getAlexGSetupState=function(){return alexGSetupState;};' +
  'g.setAlexGSetupState=function(v){alexGSetupState=v;};' +
  'g.getAlexGZoneState=function(){return alexGZoneState;};' +
  'g.setAlexGZoneState=function(v){alexGZoneState=v;};' +
  'g.getAlexGAccount=function(){return alexGAccount;};' +
  'g.setAlexGAccount=function(v){alexGAccount=v;};' +
  'g.getAlexGJournalEntries=function(){return alexGJournalEntries;};' +
  'g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
  'return runEvidencePlatformFixtures(g);'
);
g.setLocalStorageThrowing=function(on){ lsThrowing=!!on; };
try{
  const results=wrapped(g);
  results.forEach(r=>{
    const tag = r.pass===null ? 'NOTE(source)' : (r.pass?'PASS':'FAIL');
    console.log(tag+' -- '+r.name+(r.detail?' ('+r.detail+')':''));
  });
  const executed=results.filter(r=>r.pass!==null);
  const failCount=executed.filter(r=>!r.pass).length;
  console.log('---');
  console.log(failCount===0
    ? ('ALL MOGO-003 PHASE 1 EVIDENCE PLATFORM FIXTURES PASSED ('+executed.length+' executed)')
    : ('FAILURES: '+failCount+'/'+executed.length+' executed'));
}catch(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
  if(e&&e.stack) console.log(e.stack);
}
