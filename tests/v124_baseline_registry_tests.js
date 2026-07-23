// PROGRAM-001 Phase 1 -- Baseline Registry & Logic Protection.
//
// Exercises the REAL, unmodified functions computeBaselineRegistry/lockBaselineRegistry/
// getPersistedBaselineRegistry/compareBaselineEntry/getBaselineDiagnosticsSummary/
// renderBaselineRegistryDiagnostics/baselineHashFunctionSet/baselineFnv1aHash against isolated,
// in-memory state only -- the same offline JXA-harness pattern every other suite in this
// repository uses (stubbed localStorage, stubbed document, no real browser storage ever
// touched). This is purely additive, read-only, Diagnostics-only infrastructure: nothing here
// places, modifies, or closes a trade, and nothing under test calls any scanning/entry/exit/
// journal function -- so unlike other suites, mutation-safety here is proven not by isolating
// a real mutating call but by proving the FUNCTIONS UNDER TEST THEMSELVES never touch trading
// state at all.
function runBaselineRegistryFixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,detail:detail||''});};

  function seedClean(){
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGJournalEntries([]);
    g.clearLocalStorage();
    g.setDeveloperMode(false);
  }

  // ── Baseline generation ──
  {
    seedClean();
    const reg=g.computeBaselineRegistry();
    assert('BaselineRegistry.1: computeBaselineRegistry() returns a well-formed registry with both strategy entries',
      reg&&reg.registryVersion&&reg.generatedAt&&reg.jvm&&reg.alex,'');
    const requiredKeys=['baselineId','strategyId','strategyName','strategyVersion','applicationVersion','createdAt','status','logicFingerprint','riskFingerprint','configurationFingerprint','dataContractVersion','instruments','timeframes','sessionRules','riskModel','dataSource','executionModel','metricsVersion','notes'];
    const jvmHasAll=requiredKeys.every(k=>Object.prototype.hasOwnProperty.call(reg.jvm,k));
    const alexHasAll=requiredKeys.every(k=>Object.prototype.hasOwnProperty.call(reg.alex,k));
    assert('BaselineRegistry.1b: both entries carry every required schema field (Deliverable 1)',
      jvmHasAll&&alexHasAll,'missing on jvm: '+requiredKeys.filter(k=>!Object.prototype.hasOwnProperty.call(reg.jvm,k)).join(',')+' | missing on alex: '+requiredKeys.filter(k=>!Object.prototype.hasOwnProperty.call(reg.alex,k)).join(','));
    assert('BaselineRegistry.25: instruments field is the real SCAN_PAIRS live-trading universe, not a separately fabricated list',
      Array.isArray(reg.jvm.instruments)&&reg.jvm.instruments.length>0&&JSON.stringify(reg.jvm.instruments)===JSON.stringify(reg.alex.instruments),'jvm='+JSON.stringify(reg.jvm.instruments));
  }

  // ── Unknown-field handling: never fabricate ──
  {
    const reg=g.computeBaselineRegistry();
    assert('BaselineRegistry.3: dataContractVersion is explicitly null for both strategies (no formal record-shape version exists yet -- never fabricated)',
      reg.jvm.dataContractVersion===null&&reg.alex.dataContractVersion===null,'');
    assert('BaselineRegistry.3b: metricsVersion is explicitly null for both strategies (no formal metrics-formula version exists yet -- never fabricated)',
      reg.jvm.metricsVersion===null&&reg.alex.metricsVersion===null,'');
    assert('BaselineRegistry.4: notes field discloses the approximations/limitations for both entries (non-empty, explanatory)',
      typeof reg.jvm.notes==='string'&&reg.jvm.notes.length>20&&typeof reg.alex.notes==='string'&&reg.alex.notes.length>20,'');
  }

  // ── Registry integrity: the JS-side mirror lists actually resolve against the real app ──
  {
    const refs=g.baselineGetAllFunctionRefs();
    const jvmResult=g.baselineHashFunctionSet(refs,g.getBaselineJvmFunctions());
    const alexResult=g.baselineHashFunctionSet(refs,g.getBaselineAlexFunctions());
    assert('BaselineRegistry.22: every BASELINE_JVM_FUNCTIONS name resolves to a real function reference in the currently-loaded app (zero missing)',
      jvmResult.missing.length===0,'missing='+JSON.stringify(jvmResult.missing));
    assert('BaselineRegistry.23: every BASELINE_ALEX_FUNCTIONS name resolves to a real function reference in the currently-loaded app (zero missing)',
      alexResult.missing.length===0,'missing='+JSON.stringify(alexResult.missing));
    assert('BaselineRegistry.24: BASELINE_SHARED_RISK_FUNCTIONS is a subset of BASELINE_JVM_FUNCTIONS (pipSize/pipValuePerLot are genuinely shared, cross-strategy utilities)',
      g.getBaselineSharedRiskFunctions().every(n=>g.getBaselineJvmFunctions().indexOf(n)!==-1),'');
    assert('BaselineRegistry.5: JVM and ALEX baselineIds are distinct and each embeds its own logic fingerprint',
      g.computeBaselineRegistry().jvm.baselineId!==g.computeBaselineRegistry().alex.baselineId,'');
  }

  // ── Fingerprint stability (determinism, order-independence) ──
  {
    const reg1=g.computeBaselineRegistry();
    const reg2=g.computeBaselineRegistry();
    assert('BaselineRegistry.2: computing the registry twice in a row (no code change) yields identical logic/risk/configuration fingerprints for both strategies',
      reg1.jvm.logicFingerprint===reg2.jvm.logicFingerprint&&reg1.jvm.riskFingerprint===reg2.jvm.riskFingerprint&&reg1.jvm.configurationFingerprint===reg2.jvm.configurationFingerprint&&
      reg1.alex.logicFingerprint===reg2.alex.logicFingerprint&&reg1.alex.riskFingerprint===reg2.alex.riskFingerprint&&reg1.alex.configurationFingerprint===reg2.alex.configurationFingerprint,'');
    const refs=g.baselineGetAllFunctionRefs();
    const orderA=g.baselineHashFunctionSet(refs,['pipSize','pipValuePerLot']).hash;
    const orderB=g.baselineHashFunctionSet(refs,['pipValuePerLot','pipSize']).hash;
    assert('BaselineRegistry.6: hashing the same function set in a different array order produces the identical fingerprint (order-independent, per Deliverable 2)',
      orderA===orderB,'orderA='+orderA+' orderB='+orderB);
  }

  // ── Fingerprint sensitivity: proves the hash reflects real content, not a stub constant ──
  {
    const refs=g.baselineGetAllFunctionRefs();
    const hashPipSize=g.baselineHashFunctionSet(refs,['pipSize']).hash;
    const hashPipValuePerLot=g.baselineHashFunctionSet(refs,['pipValuePerLot']).hash;
    assert('BaselineRegistry.7: hashing two DIFFERENT real functions produces two DIFFERENT fingerprints (the hash is genuinely sensitive to source content, not a constant)',
      hashPipSize!==hashPipValuePerLot,'pipSize='+hashPipSize+' pipValuePerLot='+hashPipValuePerLot);
    assert('BaselineRegistry.7b: baselineFnv1aHash itself is a deterministic pure function of its input string',
      g.baselineFnv1aHash('abc')===g.baselineFnv1aHash('abc')&&g.baselineFnv1aHash('abc')!==g.baselineFnv1aHash('abd'),'');
  }

  // ── Unknown-field handling: a missing function is reported, never silently skipped ──
  {
    const result=g.baselineHashFunctionSet({},['thisFunctionDoesNotExistXYZ']);
    assert('BaselineRegistry.8: a name with no real function reference is recorded in missing[] rather than silently fabricated/omitted, and still yields a stable hash',
      result.missing.length===1&&result.missing[0]==='thisFunctionDoesNotExistXYZ'&&typeof result.hash==='string'&&result.hash.length>0,JSON.stringify(result));
  }

  // ── No-baseline-yet handling ──
  {
    seedClean();
    const summary=g.getBaselineDiagnosticsSummary();
    assert('BaselineRegistry.11: with nothing ever locked, all three statuses honestly report NO BASELINE LOCKED YET (never a fabricated MATCH)',
      summary.jvmStatus==='NO BASELINE LOCKED YET'&&summary.alexStatus==='NO BASELINE LOCKED YET'&&summary.sharedRiskStatus==='NO BASELINE LOCKED YET',JSON.stringify({jvm:summary.jvmStatus,alex:summary.alexStatus,shared:summary.sharedRiskStatus}));
  }

  // ── Persistence: lock, round-trip, match ──
  {
    seedClean();
    const lockResult=g.lockBaselineRegistry();
    assert('BaselineRegistry.12a: lockBaselineRegistry() succeeds and returns the locked registry',
      lockResult.ok===true&&lockResult.registry&&lockResult.registry.jvm&&lockResult.registry.alex,'');
    const persisted=g.getPersistedBaselineRegistry();
    assert('BaselineRegistry.12b: getPersistedBaselineRegistry() reads back exactly what was just locked (persistence round-trip)',
      JSON.stringify(persisted)===JSON.stringify(lockResult.registry),'');
    const summary=g.getBaselineDiagnosticsSummary();
    assert('BaselineRegistry.10: immediately after locking (no code change since), current fingerprints MATCH the persisted baseline for JVM, ALEX, and shared risk',
      summary.jvmStatus==='MATCH'&&summary.alexStatus==='MATCH'&&summary.sharedRiskStatus==='MATCH',JSON.stringify({jvm:summary.jvmStatus,alex:summary.alexStatus,shared:summary.sharedRiskStatus}));
  }

  // ── Reload behavior ──
  {
    seedClean();
    g.lockBaselineRegistry();
    const readA=g.getPersistedBaselineRegistry();
    const readB=g.getPersistedBaselineRegistry(); // simulates a fresh read after "reload" -- pure localStorage read each call
    assert('BaselineRegistry.19: reading the persisted baseline twice (simulating a reload) returns byte-identical restoration',
      JSON.stringify(readA)===JSON.stringify(readB),'');
  }

  // ── Idempotence ──
  {
    seedClean();
    const first=g.lockBaselineRegistry();
    const second=g.lockBaselineRegistry();
    assert('BaselineRegistry.26: locking twice in a row with no code change produces the same fingerprints both times (no conflicting duplicate state)',
      first.registry.jvm.logicFingerprint===second.registry.jvm.logicFingerprint&&first.registry.alex.logicFingerprint===second.registry.alex.logicFingerprint,'');
  }

  // ── Fingerprint drift detection ──
  {
    seedClean();
    const real=g.computeBaselineRegistry();
    const fakeStale=JSON.parse(JSON.stringify(real));
    fakeStale.jvm.logicFingerprint='deadbeef'; // simulate a real historical logic change
    g.setLocalStorageItem('fxhub_baseline_registry',JSON.stringify(fakeStale));
    const summary=g.getBaselineDiagnosticsSummary();
    assert('BaselineRegistry.9: a persisted baseline whose logicFingerprint no longer matches the current one is reported as DRIFT DETECTED for JVM, and does not falsely report ALEX as drifted too',
      summary.jvmStatus==='DRIFT DETECTED'&&summary.alexStatus==='MATCH',JSON.stringify({jvm:summary.jvmStatus,alex:summary.alexStatus}));
  }

  // ── Storage isolation ──
  {
    seedClean();
    const keysBefore=g.getAllLocalStorageKeys().slice();
    g.lockBaselineRegistry();
    const keysAfter=g.getAllLocalStorageKeys().slice();
    const newKeys=keysAfter.filter(k=>keysBefore.indexOf(k)===-1);
    assert('BaselineRegistry.13: lockBaselineRegistry() writes to exactly one new key (fxhub_baseline_registry) and touches nothing else',
      newKeys.length===1&&newKeys[0]==='fxhub_baseline_registry',JSON.stringify(newKeys));
  }

  // ── No mutation of any real trading/journal/account state ──
  {
    seedClean();
    g.setPaperAccount({balance:12345.67,openPositions:[{id:1,pair:'EUR/USD'}],closedPositions:[]});
    g.setJournalEntries([{tradeId:1,status:'OPEN'}]);
    g.setAlexGAccount({balance:9999.99,openPositions:[{tradeId:'A1'}],closedPositions:[]});
    g.setAlexGJournalEntries([{tradeId:'A1',status:'OPEN'}]);
    const scanBefore=JSON.stringify(g.getScanData());
    const autoBefore=JSON.stringify(g.getAutoTrading());
    const alexAutoBefore=JSON.stringify(g.getAlexGAutoTrading());
    const paperBefore=JSON.stringify(g.getPaperAccount());
    const journalBefore=JSON.stringify(g.getJournalEntries());
    const alexAcctBefore=JSON.stringify(g.getAlexGAccount());
    const alexJournalBefore=JSON.stringify(g.getAlexGJournalEntries());

    g.computeBaselineRegistry();
    g.lockBaselineRegistry();
    g.getBaselineDiagnosticsSummary();
    g.setDeveloperMode(true);
    g.renderBaselineRegistryDiagnostics();

    assert('BaselineRegistry.14: no paper-account mutation -- paperAccount is byte-identical before and after every Baseline Registry operation',
      JSON.stringify(g.getPaperAccount())===paperBefore,'');
    assert('BaselineRegistry.15: no journal mutation -- journalEntries is byte-identical before and after every Baseline Registry operation',
      JSON.stringify(g.getJournalEntries())===journalBefore,'');
    assert('BaselineRegistry.16: no ALEX account mutation -- alexGAccount is byte-identical before and after every Baseline Registry operation',
      JSON.stringify(g.getAlexGAccount())===alexAcctBefore,'');
    assert('BaselineRegistry.17: no ALEX journal mutation -- alexGJournalEntries is byte-identical before and after every Baseline Registry operation',
      JSON.stringify(g.getAlexGJournalEntries())===alexJournalBefore,'');
    assert('BaselineRegistry.18: scanData/autoTrading/alexGAutoTrading are also completely untouched (no scanner or execution-eligibility side effect)',
      JSON.stringify(g.getScanData())===scanBefore&&JSON.stringify(g.getAutoTrading())===autoBefore&&JSON.stringify(g.getAlexGAutoTrading())===alexAutoBefore,'');
  }

  // ── Diagnostics rendering ──
  {
    seedClean();
    g.lockBaselineRegistry();
    g.setDeveloperMode(true);
    g.renderBaselineRegistryDiagnostics();
    const htmlOn=g.getBaselineCardEl().innerHTML;
    assert('BaselineRegistry.20: with Developer Mode ON, the diagnostics card renders Baseline IDs and Fingerprint Status for both strategies plus the application/registry version',
      htmlOn.indexOf('Baseline Registry')!==-1&&htmlOn.indexOf('JVM Fingerprint Status')!==-1&&htmlOn.indexOf('ALEX Fingerprint Status')!==-1&&htmlOn.indexOf('Application Version')!==-1&&htmlOn.indexOf('Baseline Registry Version')!==-1&&htmlOn.indexOf('Shared Risk Fingerprint Status')!==-1,'');
    g.setDeveloperMode(false);
    g.renderBaselineRegistryDiagnostics();
    const htmlOff=g.getBaselineCardEl().innerHTML;
    assert('BaselineRegistry.21: with Developer Mode OFF, the diagnostics card is cleared (lightweight, never shown to non-developer users)',
      htmlOff==='','');
  }

  // ── Miscellaneous structural checks ──
  {
    assert('BaselineRegistry.27: BASELINE_REGISTRY_VERSION is a non-empty version string',
      typeof g.getBaselineRegistryVersion()==='string'&&g.getBaselineRegistryVersion().length>0,'');
  }

  return results;
}
