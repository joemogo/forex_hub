// MOGO-003 Phase 1 — Evidence Platform fixture suite (v12.8.0).
//
// Verifies the Engineering-Authority-approved Phase 1 against rulings C1-C5 and minor
// corrections 1-5. Every fixture calls the REAL functions from index.html -- none is
// re-implemented here.
//
// DISCLOSED HARNESS LIMITATION (spec 11.3): the offline JXA runner provides neither
// crypto.subtle nor IndexedDB, and cannot resolve genuine async chains. The SHA-256 digest
// itself and the IndexedDB read/write layer are therefore browser-verified, not fixture-
// verified -- the same documented offline/live split already used for alexGCloseLivePosition.
// The fixtures below cover every PURE layer by real execution, and cover the async-gated
// behaviours by asserting against the real shipped source text (a genuine executing
// assertion, not a claim). Nothing is asserted that was not actually checked.
function runEvidencePlatformFixtures(g){
  const out=[];
  function t(name,fn){
    try{ const d=fn(); out.push({name,pass:true,detail:d||''}); }
    catch(e){ out.push({name,pass:false,detail:(e&&e.message)?e.message:String(e)}); }
  }
  function eq(a,b,m){ if(a!==b) throw new Error((m||'')+' expected '+JSON.stringify(b)+', got '+JSON.stringify(a)); }
  function ok(v,m){ if(!v) throw new Error(m||'expected truthy'); }
  function no(v,m){ if(v) throw new Error(m||'expected falsy'); }
  function throws(fn,m){
    let threw=false;
    try{ fn(); }catch(e){ threw=true; }
    if(!threw) throw new Error(m||'expected a throw');
  }
  const SRC=g.appSource||'';
  // The evidence layer's exact source span, bounded by its own begin/end markers -- so a
  // "this string appears nowhere in the layer" assertion really is scoped to the layer and
  // cannot accidentally pass or fail on unrelated application code.
  const LAYER=(function(){
    const a=SRC.indexOf('MOGO-003 PHASE 1 — EVIDENCE PLATFORM (v12.8.0)');
    const b=SRC.indexOf('END MOGO-003 PHASE 1 — EVIDENCE PLATFORM');
    if(a===-1||b===-1||b<=a) throw new Error('could not bound the evidence layer in index.html');
    return SRC.slice(a,b);
  })();

  // A minimal but genuinely shaped closed ALEX position, matching the real record produced by
  // the protected alexGCloseLivePosition.
  function sampleTrade(over){
    const base={tradeId:'AGT|EUR_USD|1',signalId:'AGS|sig|1',setupId:'AGS|EUR_USD|H1|z1|B_breakRetest|r1',
      strategy:'alex_g_sr_v1',ruleVersion:'alex_g_sr_v1',pair:'EUR_USD',timeframe:'H1',
      setupType:'B_breakRetest',setupLabel:'BREAK & RETEST',direction:'buy',
      entry:1.1000,stop:1.0950,target:1.1100,plannedRR:2,riskPercent:1,riskAmount:100,
      pipValue:10,positionSize:0.2,balanceAtEntry:10000,openedAt:'2026-07-20T10:00:00.000Z',
      qualificationTimestamp:1753000000000,qualificationClose:1.0999,zoneId:'AGZ|z1',
      // touch 4 (touchIndex 3) is the earliest reaction the engine can turn into a setup at all;
      // the previous value of 3 described a record the protected engine could never have created.
      reactionId:'AGR|r1',zoneTouchNumber:4,zoneStrength:4,zoneQualityAtQualification:'A',
      zoneRoleAtQualification:'support',zoneLow:1.0940,zoneHigh:1.0960,zoneCenter:1.0950,
      atrAtEntry:0.0012,session:'London',dayOfWeek:1,hourOfDay:10,trendContext:'up',
      status:'closed',exitPrice:1.1100,closedAt:'2026-07-20T14:00:00.000Z',result:'Win',
      resultR:2,pnl:200,balanceAfter:10200,maePips:5,mfePips:100,maeR:-0.1,mfeR:2,
      exitTriggerLevel:1.1100,exitDetectionSource:'historical_candle',exitDetectedAt:1753020000000,
      exitCandleStart:1753019940000,exitCandleEnd:1753020000000,ambiguous:false,ambiguousMode:null,
      configurationSnapshot:{ruleVersion:'alex_g_sr_v1',config:{a:1}},createdByEngineVersion:'12.8.0',
      liveFillPrice:1.1000,entryDelayPips:0.4,entryBid:1.0999,entryAsk:1.1000,entrySpreadPips:0.1};
    if(over) Object.keys(over).forEach(function(k){ base[k]=over[k]; });
    return base;
  }
  function builtPackage(over,opts){
    const o=opts||{};
    return g.evidenceBuildPackageFromTrade(sampleTrade(over),
      {packageId:o.packageId||'PKG|alex_g_sr_v1|20260720|1',captureBasis:o.captureBasis||'LIVE_CLOSE',
       createdAt:'2026-07-20T14:00:01.000Z',engineVersion:'12.8.0'});
  }

  // ══ GROUP 1 — CANONICALIZATION (mogo.evidence-canon.v1, rules K1-K8) ═══════════════════
  t('C1 canonicalization is deterministic across repeated calls',function(){
    const p=builtPackage();
    eq(g.evidenceCanonicalize(p),g.evidenceCanonicalize(p),'the same package must canonicalize identically every time');
  });
  t('C2 object key order is INSIGNIFICANT (K3)',function(){
    const a={packageSchemaVersion:'x',alpha:1,beta:{p:1,q:2},zeta:[1,2]};
    const b={zeta:[1,2],beta:{q:2,p:1},alpha:1,packageSchemaVersion:'x'};
    eq(g.evidenceCanonicalize(a),g.evidenceCanonicalize(b),'reordering object keys must not change the canonical form');
  });
  t('C3 ARRAY order is SIGNIFICANT (K4) -- a reordered chain is a different chain',function(){
    const a={items:[1,2,3]},b={items:[3,2,1]};
    ok(g.evidenceCanonicalize(a)!==g.evidenceCanonicalize(b),'array reordering MUST change the canonical form');
  });
  t('C4 undefined becomes an explicit null and the key is retained (K5)',function(){
    const withUndef={a:undefined,b:1};
    eq(g.evidenceCanonicalize(withUndef),'{"a":null,"b":1}','a missing value must be an explicit null, never a dropped key');
  });
  t('C5 non-finite numbers are a validation error, never silently coerced (K6)',function(){
    throws(function(){ g.evidenceCanonicalize({a:NaN}); },'NaN must throw');
    throws(function(){ g.evidenceCanonicalize({a:Infinity}); },'Infinity must throw');
    throws(function(){ g.evidenceCanonicalize({a:-Infinity}); },'-Infinity must throw');
  });
  t('C6 all five integrity fields AND the whole export block are excluded (K2)',function(){
    const p=builtPackage();
    const before=g.evidenceCanonicalize(p);
    p.contentHash='deadbeef'; p.contentHashAlgorithm='X'; p.contentHashCanonicalization='Y';
    p.contentHashProvenance='Z'; p.contentHashScope='W';
    p.export={exportedAt:'2026-07-21T00:00:00Z',exportMechanism:'MANUAL',exportFilename:'f.json',exportVerified:true};
    eq(g.evidenceCanonicalize(p),before,'marking a package exported must never change its hash');
  });
  t('C7 canonical form has no whitespace, and rejects circular/unsupported values (K8)',function(){
    const s=g.evidenceCanonicalize({a:1,b:'x y'});
    eq(s,'{"a":1,"b":"x y"}','no structural whitespace may be emitted');
    const circ={}; circ.self=circ;
    throws(function(){ g.evidenceCanonicalize(circ); },'a circular structure must throw rather than hang');
    throws(function(){ g.evidenceCanonicalize({f:function(){}}); },'a function value must throw');
  });

  // ══ GROUP 2 — INTEGRITY (synchronously testable parts; ruling C1) ══════════════════════
  t('H1 evidenceBytesToHex emits lowercase, zero-padded, 2-chars-per-byte hex',function(){
    eq(g.evidenceBytesToHex(new Uint8Array([0,1,15,16,255]).buffer),'00010f10ff');
  });
  t('H2 mutating any CONTENT field changes the canonical string (alteration is detectable)',function(){
    const p=builtPackage(),before=g.evidenceCanonicalize(p);
    p.objects.outcomes[0].pnl=999999;
    ok(g.evidenceCanonicalize(p)!==before,'an altered outcome must change the canonical form');
  });
  t('H3 the declared hash algorithm is SHA-256 and the scope field is integrity-only',function(){
    eq(g.getEvidenceHashAlgorithm(),'SHA-256');
    eq(g.getEvidenceHashScope(),'INTEGRITY_ONLY_NOT_AUTHENTICITY');
  });
  t('H4 alexGStableHash is NEVER used as the package content hash',function(){
    const p=builtPackage();
    // The stable hash is 16 hex chars (64-bit FNV variant); a SHA-256 hash is 64. If the two
    // were ever wired together this equality would hold.
    const weak=g.alexGStableHash(p);
    eq(weak.length,16,'alexGStableHash is a 16-char non-cryptographic digest');
    ok(g.getEvidenceHashExcludedFields().indexOf('contentHash')!==-1);
    // And the finalizer must not reference it anywhere.
    const fin=String(g.evidenceFinalizePackage);
    eq(fin.indexOf('alexGStableHash'),-1,'evidenceFinalizePackage must never call alexGStableHash');
  });
  t('H5 when Web Crypto is absent, nothing falls back to a weak digest',function(){
    // This harness genuinely has no crypto.subtle, so this is the real degraded path.
    eq(g.evidenceHashAvailable(),false,'the JXA harness has no Web Crypto -- this is the real absent case');
    const src=String(g.evidenceContentHash);
    ok(src.indexOf('return null')!==-1||src.indexOf('return null;')!==-1,'evidenceContentHash must return null rather than substituting a weak hash');
    eq(src.indexOf('alexGStableHash'),-1,'no weak-hash fallback may exist');
  });
  t('H6 no user-facing integrity string claims signed / authentic / tamper-proof',function(){
    const claim=g.getEvidenceHashClaimText();
    ok(/integrity/i.test(claim),'the claim must describe integrity');
    ok(!/tamper[- ]?proof/i.test(claim),'"tamper-proof" is forbidden');
    ok(!/\bsigned\b/i.test(claim),'"signed" is forbidden');
    ok(/not authenticity/i.test(claim),'the claim must explicitly disclaim authenticity');
    // And the same must hold for every rendered surface in the shipped source.
    const layer=LAYER;
    ok(!/tamper[- ]?proof/i.test(layer),'the shipped evidence layer must not contain "tamper-proof"');
    ok(!/verified authentic/i.test(layer),'the shipped evidence layer must not claim "verified authentic"');
  });

  // ══ GROUP 3 — SCHEMA AND VALIDATION ═══════════════════════════════════════════════════
  t('S1 a freshly built package validates against v1',function(){
    const v=g.evidenceValidatePackage(builtPackage());
    ok(v.valid,'expected a valid package, got: '+v.errors.join('; '));
  });
  t('S2 unknown fields are preserved and are covered by the hash',function(){
    const p=builtPackage();
    p.someFutureField={nested:true};
    const v=g.evidenceValidatePackage(p);
    ok(v.valid,'unknown fields must not invalidate a package');
    ok(g.evidenceCanonicalize(p).indexOf('someFutureField')!==-1,'unknown fields must be inside the hashed canonical form');
  });
  t('S3 completenessReport is mandatory and its reasons come from EVIDENCE_FIELD_PROVENANCE',function(){
    const p=builtPackage();
    ok(p.completenessReport,'a package must carry a completenessReport');
    ok(p.completenessReport.missing.length>0,'Phase 1 has genuine gaps and must name them');
    p.completenessReport.missing.push({field:'x',reason:'MADE_UP_REASON'});
    no(g.evidenceValidatePackage(p).valid,'an unregistered provenance reason must be rejected');
    delete p.completenessReport;
    no(g.evidenceValidatePackage(p).valid,'a missing completenessReport must be rejected');
  });
  t('S4 Phase 1 honestly reports PARTIAL, and backfill reports MINIMAL',function(){
    eq(builtPackage().completenessReport.level,'PARTIAL','a live Phase 1 package must never claim COMPLETE');
    eq(builtPackage(null,{captureBasis:'HISTORICAL_BACKFILL'}).completenessReport.level,'MINIMAL');
  });
  t('S5 objectCounts must match objects exactly',function(){
    const p=builtPackage();
    eq(p.objectCounts.positions,p.objects.positions.length);
    eq(p.objectCounts.outcomes,p.objects.outcomes.length);
    p.objectCounts.positions=99;
    no(g.evidenceValidatePackage(p).valid,'a count that disagrees with its array must be rejected');
  });
  t('S6 marketContexts is empty and named as FUTURE_WORK, never silently absent',function(){
    const p=builtPackage();
    eq(p.objects.marketContexts.length,0);
    ok(p.completenessReport.missing.some(function(m){ return m.field==='objects.marketContexts'&&m.reason==='FUTURE_WORK'; }),
      'the Phase 3 market-context gap must be recorded as a gap');
  });
  t('S7 commitHash is null with an explicit UNAVAILABLE provenance, never fabricated',function(){
    const p=builtPackage();
    eq(p.identity.commitHash,null);
    eq(p.identity.commitHashProvenance,'UNAVAILABLE');
    ok(p.completenessReport.missing.some(function(m){ return m.field==='identity.commitHash'&&m.reason==='UNAVAILABLE'; }));
  });
  t('S8 malformed packages are rejected with reasons, and hash shape is enforced',function(){
    no(g.evidenceValidatePackage(null).valid);
    no(g.evidenceValidatePackage({}).valid);
    const p=builtPackage();
    p.contentHash='NOTHEX'; p.contentHashAlgorithm='SHA-256';
    const v=g.evidenceValidatePackage(p);
    no(v.valid,'a non-64-lowercase-hex contentHash must be rejected');
    ok(v.errors.length>0,'rejection must state why');
  });

  // ══ GROUP 4 — WRITE-FAILURE DETECTION (nothing may fail silently) ══════════════════════
  t('W1 QuotaExceededError is classified as QUOTA_EXCEEDED, by name and by legacy code',function(){
    const e1=new Error('full'); e1.name='QuotaExceededError';
    eq(g.evidenceClassifyStorageError(e1),'QUOTA_EXCEEDED');
    const e2=new Error('x'); e2.code=22;
    eq(g.evidenceClassifyStorageError(e2),'QUOTA_EXCEEDED');
    const e3=new Error('x'); e3.name='NS_ERROR_DOM_QUOTA_REACHED';
    eq(g.evidenceClassifyStorageError(e3),'QUOTA_EXCEEDED');
  });
  t('W2 non-quota errors are classified DISTINCTLY from quota',function(){
    const sec=new Error('no'); sec.name='SecurityError';
    eq(g.evidenceClassifyStorageError(sec),'SECURITY');
    const con=new Error('dupe'); con.name='ConstraintError';
    eq(g.evidenceClassifyStorageError(con),'CONSTRAINT');
    eq(g.evidenceClassifyStorageError(new Error('plain')),'OTHER');
  });
  t('W3 a quota failure is RECORDED -- never silent',function(){
    g.resetEvidenceRuntime();
    const e=new Error('quota'); e.name='QuotaExceededError';
    g.evidenceRecordWriteFailure('saveAlexGRest',e);
    eq(g.getEvidenceWriteFailures().length,1,'the failure must be recorded');
    eq(g.getEvidenceWriteFailures()[0].kind,'QUOTA_EXCEEDED');
  });
  t('W4 a quota failure raises a persistent, critical banner',function(){
    g.resetEvidenceRuntime();
    const e=new Error('quota'); e.name='QuotaExceededError';
    g.evidenceRecordWriteFailure('saveAlexGRest',e);
    const b=g.getEvidenceStorageBanner();
    ok(b,'a banner must be set');
    eq(b.severity,'critical');
    ok(/Storage full/i.test(b.message),'the banner must say storage is full');
  });
  t('W5 a write failure emits a DATA_UNAVAILABLE event with a REGISTERED reason code',function(){
    g.resetEvidenceRuntime();
    g.clearDecisionEvents();
    const e=new Error('quota'); e.name='QuotaExceededError';
    g.evidenceRecordWriteFailure('saveAlexGRest',e);
    const evs=g.getDecisionEvents().filter(function(x){ return x.eventType==='DATA_UNAVAILABLE'; });
    eq(evs.length,1,'exactly one DATA_UNAVAILABLE must be retained -- an unregistered code would be dropped');
    eq(evs[0].reasonCode,'DATA_STORAGE_QUOTA_EXCEEDED');
    ok(g.getReasonCodeRegistry()['DATA_STORAGE_QUOTA_EXCEEDED'],'the code must be in the central registry');
    ok(g.getReasonCodeRegistry()['DATA_STORAGE_WRITE_FAILED']);
    ok(g.getReasonCodeRegistry()['DATA_EVIDENCE_STORE_UNAVAILABLE']);
  });
  t('W6 saveAlexGRest and save REPORT their failure and still never throw',function(){
    g.resetEvidenceRuntime();
    g.setLocalStorageThrowing(true);
    let threw=false;
    try{ g.saveAlexGRest(); }catch(e){ threw=true; }
    g.setLocalStorageThrowing(false);
    no(threw,'saveAlexGRest must never throw -- commitAlexGLedger depends on its best-effort semantics');
    ok(g.getEvidenceWriteFailures().length>0,'but the failure must be recorded, not swallowed');
    eq(g.getEvidenceWriteFailures()[0].context,'saveAlexGRest');
    g.resetEvidenceRuntime();
    g.setLocalStorageThrowing(true);
    let threw2=false;
    try{ g.saveJvm(); }catch(e){ threw2=true; }
    g.setLocalStorageThrowing(false);
    no(threw2,'JVM save() must never throw');
    ok(g.getEvidenceWriteFailures().length>0,'JVM save() failure must be recorded');
  });
  t('W7 IndexedDB unavailability is surfaced as a distinct critical banner',function(){
    g.resetEvidenceRuntime();
    g.evidenceRecordWriteFailure('indexeddb-open',new Error('IndexedDB is not available in this context'));
    const b=g.getEvidenceStorageBanner();
    eq(b.severity,'critical');
    ok(/Durable evidence storage unavailable/i.test(b.message));
    ok(/buffer-only/i.test(b.message),'the operator must be told capture is not happening');
  });

  // ══ GROUP 5 — BUFFER CAPS AND THE EVICTION SAFETY RULE (ruling C4) ═════════════════════
  t('B1 the setups cap is 1,000 and the zones cap is 200 per pair',function(){
    eq(g.getEvidenceSetupsMax(),1000);
    eq(g.getEvidenceZonesMaxPerPair(),200);
  });
  t('B2 setups over the cap are evicted oldest-first once evidence is safe',function(){
    const setups=[];
    for(let i=0;i<1005;i++) setups.push({setupId:'S'+i,qualificationTimestamp:i});
    g.setAlexGSetupState(setups);
    g.setAlexGAccount({balance:0,openPositions:[],closedPositions:[]});
    const r=g.evidenceEvictBuffers({});
    eq(r.evictedSetups,5,'exactly the overflow must be evicted');
    eq(g.getAlexGSetupState().length,1000);
    ok(!g.getAlexGSetupState().some(function(s){ return s.setupId==='S0'; }),'the oldest must go first');
    ok(g.getAlexGSetupState().some(function(s){ return s.setupId==='S1004'; }),'the newest must survive');
  });
  t('B3 EVICTION IS BLOCKED while a closed trade has no tier-(b) package',function(){
    const setups=[];
    for(let i=0;i<1005;i++) setups.push({setupId:'S'+i,qualificationTimestamp:i});
    g.setAlexGSetupState(setups);
    g.setAlexGAccount({balance:0,openPositions:[],
      closedPositions:[{tradeId:'T0',setupId:'S0'},{tradeId:'T1',setupId:'S1'}]});
    const r=g.evidenceEvictBuffers({});                 // nothing persisted to tier (b) yet
    eq(r.skipped,2,'both unpersisted setups must be retained');
    ok(g.getAlexGSetupState().some(function(s){ return s.setupId==='S0'; }),'S0 must survive -- its evidence is not safe');
    ok(g.getAlexGSetupState().some(function(s){ return s.setupId==='S1'; }),'S1 must survive -- its evidence is not safe');
  });
  t('B4 once the package IS committed, the same record becomes evictable',function(){
    const setups=[];
    for(let i=0;i<1005;i++) setups.push({setupId:'S'+i,qualificationTimestamp:i});
    g.setAlexGSetupState(setups);
    g.setAlexGAccount({balance:0,openPositions:[],
      closedPositions:[{tradeId:'T0',setupId:'S0'},{tradeId:'T1',setupId:'S1'}]});
    const r=g.evidenceEvictBuffers({T0:true,T1:true});  // evidence now safe in tier (b)
    eq(r.skipped,0,'nothing should be blocked once evidence is persisted');
    eq(r.evictedSetups,5);
  });
  t('B5 a setup belonging to an OPEN position is never evicted',function(){
    const setups=[];
    for(let i=0;i<1005;i++) setups.push({setupId:'S'+i,qualificationTimestamp:i});
    g.setAlexGSetupState(setups);
    g.setAlexGAccount({balance:0,openPositions:[{tradeId:'OPEN1',setupId:'S0'}],closedPositions:[]});
    g.evidenceEvictBuffers({});
    ok(g.getAlexGSetupState().some(function(s){ return s.setupId==='S0'; }),'a live position\'s setup must never be evicted');
  });
  t('B6 zones are capped at 200 per pair, newest kept, oldest by formedAt evicted',function(){
    const zones=[];
    for(let i=0;i<205;i++) zones.push({id:'Z'+i,formedAt:i});
    g.setAlexGZoneState({EUR_USD:{H1:{pendingAnchors:[],provisionalClusters:[],validatedZones:zones}}});
    g.setAlexGSetupState([]);
    g.setAlexGAccount({balance:0,openPositions:[],closedPositions:[]});
    const r=g.evidenceEvictBuffers({});
    eq(r.evictedZones,5);
    eq(g.getAlexGZoneState().EUR_USD.H1.validatedZones.length,200);
    ok(!g.getAlexGZoneState().EUR_USD.H1.validatedZones.some(function(z){ return z.id==='Z0'; }),'the oldest zone must go first');
  });
  t('B7 the ALEX JOURNAL/LEDGER is never capped, evicted or rewritten (ruling C4)',function(){
    const journal=[];
    for(let i=0;i<3000;i++) journal.push({journalEntryId:'J'+i,tradeId:'T'+i,status:'closed'});
    g.setAlexGJournalEntries(journal);
    const acct={balance:1234,openPositions:[],closedPositions:[]};
    for(let i=0;i<3000;i++) acct.closedPositions.push({tradeId:'T'+i,setupId:null});
    g.setAlexGAccount(acct);
    g.setAlexGSetupState([]); g.setAlexGZoneState({});
    g.evidenceEvictBuffers({});
    eq(g.getAlexGJournalEntries().length,3000,'the journal must be untouched by any buffer limit');
    eq(g.getAlexGAccount().closedPositions.length,3000,'the ledger must be untouched');
    eq(g.getAlexGAccount().balance,1234,'the balance must be untouched');
    // And no evidence function may reference the journal cap at all.
    eq(String(g.evidenceEvictBuffers).indexOf('alexGJournalEntries'),-1,'the eviction path must not even mention the journal');
  });

  // ══ GROUP 6 — EXPORT ══════════════════════════════════════════════════════════════════
  t('X1 packageId is sanitized for the filename, and the canonical ID is preserved (Minor 1)',function(){
    const p=builtPackage();
    p.contentHash='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';
    const fn=g.evidenceExportFilename(p);
    eq(p.packageId,'PKG|alex_g_sr_v1|20260720|1','the canonical ID inside the package must keep its | delimiter');
    eq(fn.indexOf('|'),-1,'no raw | may reach a filename');
    ok(/^mogo-evidence-alex_g_sr_v1-PKG_alex_g_sr_v1_20260720_1-0123456789ab\.json$/.test(fn),'unexpected filename: '+fn);
  });
  t('X2 sanitization strips path separators and every unsafe character',function(){
    eq(g.evidenceSanitizeForFilename('a/b\\c:d*e?f"g<h>i|j'),'a_b_c_d_e_f_g_h_i_j');
    eq(g.evidenceSanitizeForFilename('../../etc/passwd'),'etc_passwd');
    eq(g.evidenceSanitizeForFilename('...'),null,'an all-punctuation name must be rejected, not silently emitted');
    eq(g.evidenceSanitizeForFilename(''),null);
    eq(g.evidenceSanitizeForFilename('x'.repeat(200)).length,64,'names must be truncated');
  });
  t('X3 an unhashed package is labelled unverified in its own filename',function(){
    const p=builtPackage();
    p.contentHash=null;
    ok(/-unverified\.json$/.test(g.evidenceExportFilename(p)),'an unverifiable package must not look verified');
  });
  t('X4 EXP-001: a download NEVER marks a package exported — it records an attempt only',function(){
    const src=String(g.evidenceExportPackage);
    // Strengthened after EXP-001: previously this asserted ordering around a marking step that
    // should not exist at all. A browser download cannot report whether bytes reached the disk,
    // so the export path must never set exportedAt under any ordering.
    ok(/exportedAt:null/.test(src),'the export path must set exportedAt to null, always');
    ok(!/exportedAt:new Date\(\)/.test(src),'the export path must NEVER stamp exportedAt');
    ok(/exportAttemptedAt:new Date\(\)/.test(src),'it must record an attempt timestamp instead');
    ok(src.indexOf('HASH_MISMATCH')!==-1,'a hash mismatch must still abort before any write');
    ok(src.indexOf('HASH_MISMATCH')<src.indexOf('downloadTextFile'),'verification precedes the write');
    ok(src.indexOf('WRITE_FAILED')<src.indexOf('exportAttemptedAt'),'a failed download returns before any state is recorded');
    ok(/requiresReimport:true/.test(src),'the caller must be told confirmation is still required');
  });
  t('X5 the exact bytes about to be written are re-parsed and re-hashed before marking',function(){
    const src=String(g.evidenceExportPackage);
    ok(src.indexOf('JSON.stringify(pkg')!==-1,'the bytes must be produced first');
    ok(src.indexOf('JSON.parse(text)')!==-1,'the exact serialized text must be re-parsed');
    ok(src.indexOf('evidenceVerifyPackageHash(reparsed)')!==-1,'the re-parsed bytes must be the thing verified');
  });
  t('X6 exportMechanism can only ever be AUTO_DOWNLOAD or MANUAL -- never FS_ACCESS (C3)',function(){
    const src=String(g.evidenceExportPackage);
    ok(src.indexOf("'MANUAL'")!==-1&&src.indexOf("'AUTO_DOWNLOAD'")!==-1);
    const layer=LAYER;
    eq(layer.indexOf('showDirectoryPicker'),-1,'the File System Access API must not appear anywhere');
    eq(layer.indexOf('FileSystemDirectoryHandle'),-1);
    eq(layer.indexOf("exportMechanism:'FS_ACCESS'"),-1,'FS_ACCESS must never be emitted');
  });

  // ══ GROUP 6B — EXP-001: EXPORT IS AN ATTEMPT UNTIL A RE-IMPORT PROVES IT ═══════════════
  // Every rule is exercised through the REAL, pure evidenceEvaluateExportReimport() decision
  // function, so the whole EXP-001 contract is genuinely executed offline rather than asserted
  // from source text. Proven live on 2026-07-31: Chrome silently refused a real download while
  // the old code reported success and cleared the warning.
  function storedPkg(over){
    const p=builtPackage(over);
    p.contentHash='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';
    p.contentHashAlgorithm='SHA-256';
    p.contentHashProvenance='OBSERVED';
    p.export={exportedAt:null,exportAttemptedAt:'2026-07-31T14:00:00.000Z',
              exportMechanism:'MANUAL',exportFilename:'f.json',exportVerified:false,
              exportVerificationMethod:null,exportAttemptCount:1};
    return p;
  }
  const VERIFIED={status:'VERIFIED'}, MISMATCH={status:'MISMATCH'}, UNVERIFIABLE={status:'UNVERIFIABLE'};

  t('E1 attempted export: a download records an attempt and leaves the package unexported',function(){
    const p=storedPkg();
    eq(p.export.exportedAt,null,'a downloaded package must NOT be marked exported');
    ok(p.export.exportAttemptedAt,'but the attempt must be recorded');
    eq(p.export.exportVerified,false);
    // and the unexported counter keys on exportedAt, so the warning cannot clear
    eq(g.countUnexportedLike([p]).unexported,1,'an attempted package still counts as unexported');
    eq(g.countUnexportedLike([p]).attempted,1,'and is reported as awaiting confirmation');
  });

  t('E2 cancelled or missing download: nothing is recorded as exported',function(){
    const src=String(g.evidenceExportPackage);
    ok(src.indexOf('WRITE_FAILED')<src.indexOf('exportAttemptedAt'),
      'a throwing download returns before any state is written');
    const p=storedPkg(); p.export={exportedAt:null,exportAttemptedAt:null,exportVerified:false};
    eq(g.countUnexportedLike([p]).unexported,1,'a package whose download never happened stays unexported');
    eq(g.countUnexportedLike([p]).attempted,0,'and is not even counted as attempted');
  });

  t('E3 absent re-import: an attempted package is never promoted on its own',function(){
    const p=storedPkg();
    // No re-import has occurred. Nothing in the counting path may promote it.
    eq(g.countUnexportedLike([p]).unexported,1);
    eq(p.export.exportedAt,null,'time passing is not evidence');
    // The ONLY function that can stamp exportedAt is the verified-export state builder.
    ok(/exportedAt:new Date\(\)\.toISOString\(\)/.test(String(g.evidenceBuildVerifiedExportState)),
      'only the verified-export builder may stamp exportedAt');
  });

  t('E4 malformed re-import is rejected',function(){
    eq(g.evidenceEvaluateExportReimport(null,storedPkg(),VERIFIED).reason,'MALFORMED');
    eq(g.evidenceEvaluateExportReimport([],storedPkg(),VERIFIED).reason,'MALFORMED');
    no(g.evidenceEvaluateExportReimport('not an object',storedPkg(),VERIFIED).verified);
  });

  t('E5 mismatched package identity is rejected',function(){
    const stored=storedPkg();
    const other=storedPkg(); other.packageId='PKG|alex_g_sr_v1|20260720|999';
    const r=g.evidenceEvaluateExportReimport(other,stored,VERIFIED);
    no(r.verified); eq(r.reason,'IDENTITY_MISMATCH');
    const wrongTrade=JSON.parse(JSON.stringify(stored)); wrongTrade.sourceTradeId='AGT|SOMEONE_ELSE|1';
    eq(g.evidenceEvaluateExportReimport(wrongTrade,stored,VERIFIED).reason,'IDENTITY_MISMATCH');
  });

  t('E6 failed SHA-256 verification is rejected',function(){
    const stored=storedPkg(), copy=JSON.parse(JSON.stringify(stored));
    const r=g.evidenceEvaluateExportReimport(copy,stored,MISMATCH);
    no(r.verified,'a hash mismatch must never verify an export');
    eq(r.reason,'HASH_MISMATCH');
  });

  t('E7 an UNVERIFIABLE hash never confirms an export',function(){
    const stored=storedPkg(), copy=JSON.parse(JSON.stringify(stored));
    const r=g.evidenceEvaluateExportReimport(copy,stored,UNVERIFIABLE);
    no(r.verified,'without Web Crypto nothing can be proven -- it must not be assumed');
    eq(r.reason,'HASH_UNVERIFIABLE');
  });

  t('E8 noncanonical content mismatch is rejected even when the hash "verifies"',function(){
    const stored=storedPkg();
    const altered=JSON.parse(JSON.stringify(stored));
    altered.objects.outcomes[0].pnl=999999;             // same id, same claimed hash, different content
    const r=g.evidenceEvaluateExportReimport(altered,stored,VERIFIED);
    no(r.verified,'content must be compared against what is STORED, not merely be self-consistent');
    eq(r.reason,'CANONICAL_CONTENT_MISMATCH');
  });

  t('E9 a VALID re-import verifies, and only then may the package be marked exported',function(){
    const stored=storedPkg();
    const written=JSON.parse(JSON.stringify(stored));
    written.export={exportedAt:null,exportAttemptedAt:null,exportMechanism:null,
                    exportFilename:null,exportVerified:null};  // the file was written before marking
    const r=g.evidenceEvaluateExportReimport(written,stored,VERIFIED);
    ok(r.verified,'the exact written bytes must verify: '+r.reason);
    eq(r.reason,'REIMPORT_VERIFIED');
    const st=g.evidenceBuildVerifiedExportState(stored,'f.json');
    ok(st.exportedAt,'only now is exportedAt stamped');
    eq(st.exportVerified,true);
    eq(st.exportVerificationMethod,'REIMPORT_VERIFIED');
    eq(st.exportAttemptedAt,'2026-07-31T14:00:00.000Z','the original attempt is preserved');
  });

  t('E10 the warning clears ONLY after successful verification',function(){
    const attempted=storedPkg();
    eq(g.countUnexportedLike([attempted]).unexported,1,'attempted -> warning still shown');
    const verified=storedPkg();
    verified.export=g.evidenceBuildVerifiedExportState(verified,'f.json');
    eq(g.countUnexportedLike([verified]).unexported,0,'verified -> warning cleared');
    eq(g.countUnexportedLike([verified]).attempted,0);
    eq(g.countUnexportedLike([attempted,verified]).unexported,1,'mixed set counts only the unverified one');
  });

  t('E11 no operator-confirmation shortcut and no File System Access path exists',function(){
    const layer=LAYER;
    eq(layer.indexOf('showSaveFilePicker'),-1,'no File System Access API');
    eq(layer.indexOf('showDirectoryPicker'),-1);
    // The verification decision must depend only on bytes -- never on a prompt/confirm/flag.
    const decide=String(g.evidenceEvaluateExportReimport);
    eq(decide.indexOf('confirm('),-1,'the decision must not consult the operator');
    eq(decide.indexOf('prompt('),-1);
    ok(/hashVerification/.test(decide)&&/evidenceCanonicalize/.test(decide),
      'it must depend on the hash verdict and the canonical content only');
  });

  // ══ GROUP 6C — D-2: A RE-EXPORT MAY NEVER REVOKE A CONFIRMATION ═══════════════════════════
  // Every fixture calls the REAL, pure evidenceMergeExportState(), so the monotonicity contract is
  // genuinely executed offline rather than asserted from source text.
  //
  // The defect: evidenceExportPackage proposes exportedAt:null on every attempt (correct -- a
  // download cannot prove disk persistence), and the export block was previously REPLACED with
  // that proposal. evidenceExportAll walks every package, so one later click silently un-confirmed
  // every package already confirmed by a verified re-import.
  const CONFIRMED={exportedAt:'2026-08-01T00:00:00.000Z',exportAttemptedAt:'2026-07-31T00:00:00.000Z',
    exportMechanism:'MANUAL',exportFilename:'pkg.json',exportVerified:true,
    exportVerificationMethod:'REIMPORT_VERIFIED',exportAttemptCount:2};
  // exactly what evidenceExportPackage hands in on a fresh attempt
  function attempt(count){
    return{exportedAt:null,exportAttemptedAt:'2026-08-09T00:00:00.000Z',exportMechanism:'MANUAL',
      exportFilename:'pkg.json',exportVerified:false,exportVerificationMethod:null,
      exportAttemptCount:count};
  }

  t('M1 a re-export CANNOT clear an earned exportedAt',function(){
    const m=g.evidenceMergeExportState(CONFIRMED,attempt(3));
    eq(m.exportedAt,'2026-08-01T00:00:00.000Z','the confirmation timestamp survives the attempt');
    eq(m.exportVerified,true,'and the package stays verified');
    eq(m.exportVerificationMethod,'REIMPORT_VERIFIED','with its verification method intact');
  });
  t('M2 the attempt is still recorded -- history is not suppressed to protect the stamp',function(){
    const m=g.evidenceMergeExportState(CONFIRMED,attempt(3));
    eq(m.exportAttemptedAt,'2026-08-09T00:00:00.000Z','the newer attempt timestamp is kept');
    eq(m.exportAttemptCount,3,'and the attempt count advances');
  });
  t('M3 exportAttemptCount can never decrease',function(){
    eq(g.evidenceMergeExportState(CONFIRMED,attempt(1)).exportAttemptCount,2,'a lower count cannot rewind it');
    eq(g.evidenceMergeExportState({exportAttemptCount:9},attempt(0)).exportAttemptCount,9);
    eq(g.evidenceMergeExportState({},attempt(1)).exportAttemptCount,1,'a first attempt still counts');
  });
  t('M4 an UNconfirmed package is unaffected -- an attempt stays an attempt',function(){
    const prev={exportedAt:null,exportAttemptedAt:'2026-08-08T00:00:00.000Z',exportVerified:false,exportAttemptCount:1};
    const m=g.evidenceMergeExportState(prev,attempt(2));
    eq(m.exportedAt,null,'nothing fabricates a confirmation that was never earned');
    eq(m.exportVerified,false);
    eq(m.exportAttemptCount,2);
  });
  t('M5 a verified re-import may still SET exportedAt -- advancing is always allowed',function(){
    const prev={exportedAt:null,exportAttemptedAt:'2026-08-08T00:00:00.000Z',exportVerified:false,exportAttemptCount:1};
    const verified=g.evidenceBuildVerifiedExportState({export:prev},'pkg.json');
    const m=g.evidenceMergeExportState(prev,verified);
    ok(!!m.exportedAt,'the confirmation is applied');
    eq(m.exportVerified,true);
    eq(m.exportVerificationMethod,'REIMPORT_VERIFIED');
  });
  t('M6 re-confirmation keeps the NEWER confirmation, not the older one',function(){
    const newer=Object.assign({},CONFIRMED,{exportedAt:'2026-08-09T12:00:00.000Z'});
    eq(g.evidenceMergeExportState(CONFIRMED,newer).exportedAt,'2026-08-09T12:00:00.000Z');
  });
  t('M7 monotonicity holds over an arbitrary sequence of attempts',function(){
    // the real hazard: Export all, repeatedly, long after a confirmation was earned
    let s=CONFIRMED;
    for(let i=3;i<=12;i++) s=g.evidenceMergeExportState(s,attempt(i));
    eq(s.exportedAt,'2026-08-01T00:00:00.000Z','ten re-exports later the confirmation still stands');
    eq(s.exportVerified,true);
    eq(s.exportAttemptCount,12,'and every attempt was counted');
  });
  t('M8 malformed or absent prior state cannot throw or fabricate',function(){
    eq(g.evidenceMergeExportState(null,attempt(1)).exportedAt,null);
    eq(g.evidenceMergeExportState(undefined,attempt(1)).exportAttemptCount,1);
    eq(g.evidenceMergeExportState('nonsense',attempt(1)).exportedAt,null);
    eq(g.evidenceMergeExportState(CONFIRMED,null).exportedAt,'2026-08-01T00:00:00.000Z',
      'even a null proposal cannot erase a confirmation');
  });
  // M9 IS THE INTEGRATION GUARD, and it carries that weight alone on purpose.
  // M1-M8 and M11 exercise the merge contract directly, so they still pass if the store stops
  // CALLING the merge -- proven by mutation: reverting the call site left every one of them green
  // and only this fixture red. A test that passes because a different guard fired is not evidence
  // of the guard it names, so this one pins the wiring itself: the assigned value must BE the
  // merge, which no wholesale form can satisfy.
  // Asserted from source text because the offline harness has no IndexedDB (see the header note);
  // this is the same disclosed offline/live split the async layer already carries.
  t('M9 the store write-back routes through the merge, so no caller can bypass it',function(){
    const src=String(g.evidenceUpdateExportState);
    const m=src.match(/existing\.export\s*=\s*([^;]+);/);
    ok(!!m,'the export block must be assigned exactly once');
    const rhs=m?m[1].trim():'';
    ok(/^evidenceMergeExportState\(\s*existing\.export\s*,\s*exportState\s*\)$/.test(rhs),
      'the assigned value must be the MERGE of prior and proposed state, never the proposal itself '+
      '(saw: '+rhs+')');
  });
  t('M10 the export path still refuses to stamp exportedAt itself (EXP-001 intact)',function(){
    const src=String(g.evidenceExportPackage);
    ok(/exportedAt:null/.test(src),'an attempt still proposes null -- a download proves nothing');
    ok(!/exportedAt:new Date\(\)/.test(src),'and never stamps a confirmation of its own');
  });
  t('M11 the counting rule is unchanged: only a real exportedAt clears the warning',function(){
    const confirmed={export:CONFIRMED};
    const attempted={export:attempt(1)};
    eq(g.countUnexportedLike([confirmed]).unexported,0,'a confirmed package is not unexported');
    eq(g.countUnexportedLike([attempted]).unexported,1,'an attempted one still is');
    // and the merge cannot flip that classification
    const after={export:g.evidenceMergeExportState(CONFIRMED,attempt(5))};
    eq(g.countUnexportedLike([after]).unexported,0,
      'a re-export does not push a confirmed package back into the unexported count');
  });

  // ══ GROUP 6D — M-6 (D-16): THE STORE IDENTITY IS PINNED ═══════════════════════════════════
  // WHY THIS GROUP EXISTS, and it is worth stating plainly because it corrects a finding.
  //
  // Step 4 recorded D-16: "the running build is not the committed index.html", on the strength of
  // a live on-screen reading that the 8751 origin's database was named `mogo_evidence_v1` -- a
  // name that appears nowhere in this repository. That reading was WRONG. Read directly out of the
  // preservation checkpoint's IndexedDB metadata, the database name is exactly `mogo_evidence`,
  // appearing once, with object stores `packages` and `meta` -- precisely what the constants below
  // declare. What the observer almost certainly saw was `alex_g_sr_v1`, ALEX's strategy id, which
  // is embedded in every single packageId (`PKG|alex_g_sr_v1|<date>|<n>`) and appears 1,798 times
  // in the store. There was no second build. D-16 was a misreading, not a divergence.
  //
  // The lesson is the one this milestone keeps relearning: a value read off a screen and retyped
  // into a report is not a measurement. So the identity is pinned here, in the canonical gate,
  // where a genuine future divergence FAILS rather than waiting to be discovered forensically.
  //
  // These are the values the preserved 222-package corpus was actually written with, confirmed by
  // independently re-deriving 220 of its content hashes with this repository's own canonicalizer:
  // 220 verified, 0 mismatched.
  t('SI1 the evidence database identity is exactly what the corpus was written with',function(){
    eq(g.EVIDENCE_DB_NAME,'mogo_evidence',
      'the checkpoint metadata reads `mogo_evidence` -- never `mogo_evidence_v1` (D-16 was a misreading)');
    // MOGO-013 bumped this to 2 to add the `observations` store. Pinning it is the point: a
    // schema change must be a visible, reviewed edit here, never something the gate tolerates
    // silently. The upgrade is additive -- `packages` and `meta` are untouched.
    eq(g.EVIDENCE_DB_VERSION,2,'and version 2 (MOGO-013 added the observations store)');
  });
  t('SI2 the object store names match the preserved store',function(){
    eq(g.EVIDENCE_STORE_PACKAGES,'packages','the checkpoint carries exactly one store named packages');
    eq(g.EVIDENCE_STORE_META,'meta','and one named meta');
    eq(g.EVIDENCE_STORE_OBSERVATIONS,'observations','and, from MOGO-013, one named observations');
  });
  t('SI3 the package schema and canonicalization identifiers are pinned',function(){
    eq(g.EVIDENCE_PACKAGE_SCHEMA_VERSION,'mogo.evidence-package.v1',
      'every recovered package declares this schema');
    eq(g.EVIDENCE_CANON_VERSION,'mogo.evidence-canon.v1',
      'and this canonicalization -- the one that reproduced 220 stored hashes exactly');
  });
  t('SI4 the hash algorithm is pinned, and is never silently weakened',function(){
    eq(g.getEvidenceHashAlgorithm(),'SHA-256','the corpus was written under SHA-256');
  });
  t('SI5 renaming the database would strand every existing package',function(){
    // Not a style rule. IndexedDB has no rename: a changed name opens a DIFFERENT, EMPTY database,
    // and the 220-package corpus becomes unreachable in place while the app reports zero packages
    // and cheerfully starts over. That failure is silent, which is exactly the class EXP-001 named.
    //
    // The assertion is deliberately made against the REAL open path, which is exported for this
    // purpose. An earlier draft of this fixture read a function that was never exported, so
    // String(undefined) made it pass while asserting nothing -- the same trap M9 documents. A
    // fixture that cannot fail is not a guard.
    const src=String(g.evidenceOpenDb);
    ok(src.length>50,'the real open path must be under test, not an absent binding');
    ok(/indexedDB\.open\(\s*EVIDENCE_DB_NAME\s*,\s*EVIDENCE_DB_VERSION\s*\)/.test(src),
      'the open path must reference the pinned constants, never an inline literal (saw: '+
      (src.match(/indexedDB\.open\([^)]*\)/)||['none'])[0]+')');
  });

  // ══ GROUP 6E — M-7 (D-15): THE COMMITTED EVIDENCE HASH BASELINE ═══════════════════════════
  // The 220-package corpus survived D-15 only because someone copied it by hand, once. A copy
  // nobody can verify is a copy nobody can rely on, so the corpus now has a COMMITTED baseline:
  // docs/evidence/EVIDENCE_BASELINE.json, holding every package's re-derived content hash, a
  // rollup over them, and a SHA-256 of every store file.
  //
  // These fixtures do NOT re-derive hashes -- this harness has no crypto.subtle, which is the same
  // disclosed offline/live split the suite already carries. Re-derivation is the job of
  // `mogo_evidence_leveldb_extract.js --baseline verify`, which reconstructs every package from
  // the checkpoint and recomputes its hash with the canonicalizer extracted from index.html; it is
  // proven to fail closed on a single altered field, a flipped byte and a deleted store file.
  //
  // What IS enforced here, in the canonical gate, on every run: that the committed baseline is
  // present, well-formed, internally consistent, and still agrees with the constants the engine
  // actually uses. A baseline that silently disagrees with EVIDENCE_CANON_VERSION would verify
  // nothing while appearing to verify everything.
  const BASELINE=(function(){
    try{ return JSON.parse(g.__EVIDENCE_BASELINE_TEXT__||''); }catch(e){ return null; }
  })();
  t('BL1 the committed evidence baseline exists and parses',function(){
    ok(!!BASELINE,'docs/evidence/EVIDENCE_BASELINE.json must be present and valid JSON -- a missing '+
      'baseline is a FAILURE, never a skipped group');
    eq(BASELINE&&BASELINE.baselineVersion,'mogo.evidence-baseline.v1','and declare its version');
  });
  t('BL2 the baseline agrees with the engine constants it claims to verify',function(){
    // If these drift apart, the baseline verifies a canonicalization the engine no longer uses.
    ok(BASELINE.canonicalization.indexOf(g.EVIDENCE_CANON_VERSION)!==-1,
      'the baseline canonicalization must include the engine\'s '+g.EVIDENCE_CANON_VERSION);
    ok(BASELINE.hashAlgorithm.indexOf(g.getEvidenceHashAlgorithm())!==-1,
      'and the engine\'s hash algorithm');
    ok(BASELINE.packageSchema.indexOf(g.EVIDENCE_PACKAGE_SCHEMA_VERSION)!==-1,
      'and the engine\'s package schema');
  });
  t('BL3 the baseline is internally consistent -- counts, uniqueness and shape',function(){
    eq(BASELINE.mismatched,0,'a baseline may NEVER be committed with a mismatch in it');
    eq(BASELINE.packageHashes.length,BASELINE.verified,
      'the hash list length must equal the verified count');
    eq(new Set(BASELINE.packageHashes).size,BASELINE.packageHashes.length,
      'every baseline hash must be distinct -- a duplicate would mask a lost package');
    const bad=BASELINE.packageHashes.filter(function(h){ return !/^[0-9a-f]{64}$/.test(h); });
    eq(bad.length,0,'every hash must be 64 lowercase hex characters (saw '+bad.length+' malformed)');
  });
  t('BL4 the baseline covers a real corpus, not an empty one',function(){
    // A baseline that verifies nothing would pass every other check in this group.
    ok(BASELINE.verified>=200,'the baseline must cover the preserved corpus (verified: '+BASELINE.verified+')');
    eq(BASELINE.verified,BASELINE.uniqueSourceTradeIds,
      'one verified package per distinct source trade -- counted by sourceTradeId, never packageId (D-8)');
  });
  t('BL5 the store files are pinned by hash, so file-level tampering is detectable',function(){
    ok(BASELINE.storeFiles.length>0,'the baseline must pin the store files it was taken from');
    const bad=BASELINE.storeFiles.filter(function(f){
      return !/^[0-9a-f]{64}$/.test(f.sha256)||typeof f.bytes!=='number'||!f.file;
    });
    eq(bad.length,0,'every pinned store file needs a name, a byte count and a SHA-256');
  });
  t('BL6 the baseline records the origin it came from (D-12 provenance)',function(){
    ok(!!BASELINE.origin,'an evidence baseline with no origin cannot be reconciled against a store');
    ok(/^https?:\/\/(localhost|127\.0\.0\.1):\d+$/.test(BASELINE.origin),
      'and that origin must be a secure context, or its packages could not have been hashed (D-14) '+
      '(saw: '+BASELINE.origin+')');
  });

  // ══ GROUP 6F — M-2 (D-1): A BANNER MAY NOT NAME A CONTROL ITS OWN POLICY HIDES ════════════
  // The defect, stated exactly: evidenceBannerHtml() is UNGATED and told the operator to use
  // "Import package… in Diagnostics". renderEvidencePlatformDiagnostics() begins with
  // `if(!developerModeEnabled){ el.innerHTML=''; return; }`. An operator following the instruction
  // exactly would find nothing there. That is why 0 of 220 packages were confirmed despite 220
  // export attempts -- the confirmation path existed and was unreachable.
  //
  // The general rule, which is what these fixtures actually enforce: NO OPERATOR-FACING SURFACE
  // MAY INSTRUCT THE USE OF A CONTROL THAT ITS OWN VISIBILITY POLICY HIDES.
  const BANNER_CONTROL_IDS=['evidenceImportInputBanner','evidenceImportFolderBanner'];
  function bannerWithAttempts(){
    g.setEvidenceBannerCounts(220,220,0);
    const html=g.evidenceBannerHtml();
    g.setEvidenceBannerCounts(0,0,0);
    return html;
  }
  t('CR1 the banner that instructs confirmation CARRIES the confirmation control',function(){
    const html=bannerWithAttempts();
    ok(html.indexOf('Import package(s)')!==-1,
      'the ungated banner must offer the control it names, not point at another surface');
    BANNER_CONTROL_IDS.forEach(function(id){
      ok(html.indexOf(id)!==-1,'the banner must render its own input '+id);
    });
  });
  t('CR2 the banner never sends the operator to a Developer-Mode-only surface',function(){
    const html=bannerWithAttempts();
    eq(/in\s+Diagnostics/i.test(html),false,
      'the banner must not direct the operator to the Developer-Mode diagnostics card (D-1)');
  });
  t('CR3 the banner control is NOT gated on developerModeEnabled',function(){
    const src=String(g.evidenceBannerHtml);
    eq(src.indexOf('developerModeEnabled'),-1,
      'the banner must contain no developer-mode gate of any kind');
    // and the diagnostics card demonstrably IS gated -- so the two really are different policies
    ok(String(g.renderEvidencePlatformDiagnostics).indexOf('developerModeEnabled')!==-1,
      'the diagnostics card is developer-mode gated, which is exactly why the banner needed its own control');
  });
  t('CR4 every control the banner names routes to the real confirmation handler',function(){
    const html=bannerWithAttempts();
    BANNER_CONTROL_IDS.forEach(function(id){
      const m=html.match(new RegExp('id="'+id+'"[^>]*'));
      ok(!!m,'input '+id+' must exist');
      ok(m&&/onchange="evidenceHandleImportInputMulti\(this\)"/.test(m[0]),
        id+' must route to evidenceHandleImportInputMulti, never a private or weaker path');
    });
  });
  t('CR5 the two surfaces use DISTINCT element ids',function(){
    // Two elements sharing an id makes getElementById return whichever rendered first, so one
    // button would silently drive the other surface's input.
    const banner=bannerWithAttempts();
    ok(banner.indexOf('id="evidenceImportInput"')===-1,
      'the banner must not reuse the diagnostics card id evidenceImportInput');
    const ids=(banner.match(/id="[^"]+"/g)||[]);
    eq(new Set(ids).size,ids.length,'no id may repeat within the banner itself');
  });
  t('CR6 the banner offers no confirmation control when there is nothing to confirm',function(){
    g.setEvidenceBannerCounts(0,0,0);
    const html=g.evidenceBannerHtml();
    // NOTE: this asserts the absence of the CONTROL, not an empty string. The separate storage
    // banner is legitimately present in this harness -- osascript has no IndexedDB, so
    // evidenceStorageBanner is set, which is the honest degraded behaviour several other fixtures
    // rely on. An earlier draft asserted html==='' and failed for that reason: the fixture was
    // wrong, not the code.
    BANNER_CONTROL_IDS.forEach(function(id){
      eq(html.indexOf(id),-1,'with nothing unexported the banner must not offer '+id);
    });
    eq(html.indexOf('Import package(s)'),-1,'nor name the control -- it never nags');
  });

  // ══ GROUP 6G — M-3 (D-3): BATCH IMPORT IS A LOOP, NOT A NEW KIND OF PROOF ═════════════════
  // The whole risk of batch import is that it becomes a SHORTCUT -- a bulk digest, a manifest
  // taken on trust, a receipt that confirms packages without reading their bytes. These fixtures
  // exist to prove it did not.
  //
  // DISCLOSED LIMITATION, consistent with this suite's existing offline/live split: the async
  // loop inside evidenceImportFiles() cannot be executed here, because this harness has neither
  // IndexedDB nor the ability to resolve a real await -- the same permanent limitation already
  // documented for the async layer. So the loop's BEHAVIOUR is proven three ways that do execute:
  // the reporting rule is a pure function exercised directly (BI2-BI8), the delegation and the
  // absence of any shortcut are asserted against the real source text (BI1, BI9), and the wiring
  // from both surfaces is asserted against the rendered markup and the real handler (BI10).
  // What is NOT claimed is an end-to-end offline execution of 220 real file reads.
  t('BI1 batch import calls the SAME per-file path a human clicking would',function(){
    const src=String(g.evidenceImportFiles);
    // This fixture was WEAKER than it looked and the mutation protocol caught it. It first read
    // `src.indexOf('evidenceImportFile')!==-1`, which is true no matter what the body does --
    // the function's own NAME, evidenceImportFiles, contains that substring. Replacing the real
    // call with a fabricated confirmation left it green. A test that passes because of the name
    // it is testing is not evidence of anything; the same trap M9 documents.
    //
    // It now pins the CALL, and separately forbids the batch from ever minting a confirmation
    // itself -- which is the whole shortcut class, stated directly.
    ok(/await\s+evidenceImportFile\s*\(/.test(src),
      'the batch must AWAIT the single-file import per file, so every file is re-read and re-hashed');
    eq(/EXPORT_VERIFIED_BY_REIMPORT|exportVerified\s*:\s*true/.test(src),false,
      'the batch must never mint a confirmation of its own -- only the per-file path may return one');
    eq(/manifest|bulkHash|trustList|receipt/i.test(src),false,
      'and it must introduce no bulk digest, manifest or receipt -- there is no weaker path');
  });
  t('BI1b NO SILENT CAPS -- every selected file reaches the plan, however many there are',function(){
    // This fixture exists because the mutation protocol found a real gap: a batch silently
    // truncated to its first file SURVIVED, since the only guard was source text. Selection is now
    // a pure function, so truncation is caught by running it rather than by reading it.
    const many=[];
    for(let i=0;i<220;i++) many.push({name:'pkg-'+i+'.json'});
    const plan=g.evidencePlanImportSelection(many);
    eq(plan.length,220,'a 220-file selection must plan 220 files -- no cap, no sampling');
    eq(plan.filter(function(p){return p.importable;}).length,220,'all of them importable');
    eq(plan[219].name,'pkg-219.json','including the last one');
    const mixed=g.evidencePlanImportSelection([{name:'a.json'},{name:'.DS_Store'},{name:'b.json'}]);
    eq(mixed.length,3,'non-importable files stay IN the plan so they can be reported');
    eq(mixed[1].importable,false,'flagged, not dropped');
    eq(g.evidencePlanImportSelection(null).length,0,'a null selection plans nothing and cannot throw');
  });
  t('BI2 the summary counts a confirmation and a first import as DIFFERENT events',function(){
    const s=g.evidenceSummarizeImportResults([
      {name:'a.json',result:{ok:true,reason:'EXPORT_VERIFIED_BY_REIMPORT',imported:false,exportVerified:true}},
      {name:'b.json',result:{ok:true,reason:'VERIFIED',imported:true}},
      {name:'c.json',result:{ok:true,reason:'DUPLICATE_IDENTICAL_UNVERIFIABLE',imported:false,exportVerified:false}}
    ]);
    eq(s.exportVerified,1,'a re-import confirmation is counted as a confirmation');
    eq(s.imported,1,'a first-time import is counted separately');
    eq(s.duplicateNoOp,1,'and a no-op duplicate is neither');
    eq(s.rejected,0);
  });
  t('BI3 every rejection class FAILS CLOSED and is reported, never absorbed',function(){
    const s=g.evidenceSummarizeImportResults([
      {name:'malformed.json',result:{ok:false,reason:'MALFORMED_JSON'}},
      {name:'altered.json',result:{ok:false,reason:'HASH_MISMATCH'}},
      {name:'conflict.json',result:{ok:false,reason:'DUPLICATE_CONFLICTING_HASH'}},
      {name:'invalid.json',result:{ok:false,reason:'INVALID_PACKAGE'}},
      {name:'newer.json',result:{ok:false,reason:'NEWER_SCHEMA_READ_ONLY'}},
      {name:'alg.json',result:{ok:false,reason:'UNSUPPORTED_ALGORITHM'}}
    ]);
    eq(s.rejected,6,'every invalid package is rejected');
    eq(s.exportVerified,0,'and none of them confirms anything');
    eq(s.imported,0);
    eq(s.failures.length,6,'each rejection is named so none is silently absorbed');
    eq(s.byReason.HASH_MISMATCH,1,'and the reason is preserved');
  });
  t('BI4 a missing or malformed result is treated as a REJECTION, never a success',function(){
    const s=g.evidenceSummarizeImportResults([{name:'x.json'},{name:'y.json',result:null},{name:'z.json',result:'nonsense'}]);
    eq(s.rejected,3,'an absent result cannot count as an import');
    eq(s.byReason.NO_RESULT,3);
    eq(s.exportVerified,0);
  });
  t('BI5 non-JSON files are SKIPPED and REPORTED, never silently dropped',function(){
    eq(g.evidenceIsImportableName('.DS_Store'),false);
    eq(g.evidenceIsImportableName('notes.txt'),false);
    eq(g.evidenceIsImportableName('pkg.json'),true);
    eq(g.evidenceIsImportableName('PKG.JSON'),true,'the extension test is case-insensitive');
    const s=g.evidenceSummarizeImportResults([
      {name:'.DS_Store',skipped:true},{name:'a.json',result:{ok:true,reason:'VERIFIED',imported:true}}
    ]);
    eq(s.skippedNotJson,1,'a folder selection sweeps in other files and must say so');
    eq(s.byReason.SKIPPED_NOT_JSON,1,'silence indistinguishable from success is the EXP-001 defect');
    eq(s.total,2,'and the skipped file still counts toward the total selected');
  });
  t('BI6 an empty selection summarises to zero of everything, not to success',function(){
    const s=g.evidenceSummarizeImportResults([]);
    eq(s.total,0); eq(s.exportVerified,0); eq(s.imported,0); eq(s.rejected,0);
    eq(g.evidenceSummarizeImportResults(null).total,0,'a malformed argument cannot throw');
  });
  t('BI7 the summary is ORDER-INDEPENDENT and equals the sum of individual imports',function(){
    // The claim M-3 has to earn: a batch of N produces exactly what N individual imports produce.
    const results=[
      {name:'a.json',result:{ok:true,reason:'EXPORT_VERIFIED_BY_REIMPORT',exportVerified:true}},
      {name:'b.json',result:{ok:false,reason:'HASH_MISMATCH'}},
      {name:'c.json',result:{ok:true,reason:'VERIFIED',imported:true}},
      {name:'d.json',skipped:true}
    ];
    const batch=g.evidenceSummarizeImportResults(results);
    // the same entries, imported one at a time, then added up
    const singles=results.map(function(r){ return g.evidenceSummarizeImportResults([r]); });
    const summed=singles.reduce(function(a,s){
      return{total:a.total+s.total,imported:a.imported+s.imported,exportVerified:a.exportVerified+s.exportVerified,
        duplicateNoOp:a.duplicateNoOp+s.duplicateNoOp,rejected:a.rejected+s.rejected,skippedNotJson:a.skippedNotJson+s.skippedNotJson};
    },{total:0,imported:0,exportVerified:0,duplicateNoOp:0,rejected:0,skippedNotJson:0});
    eq(batch.total,summed.total,'total');
    eq(batch.exportVerified,summed.exportVerified,'confirmations');
    eq(batch.imported,summed.imported,'imports');
    eq(batch.rejected,summed.rejected,'rejections');
    eq(batch.skippedNotJson,summed.skippedNotJson,'skips');
    const reversed=g.evidenceSummarizeImportResults(results.slice().reverse());
    eq(reversed.exportVerified,batch.exportVerified,'and order cannot change the outcome');
    eq(reversed.rejected,batch.rejected);
  });
  t('BI8 the operator-facing summary prints every category, including the zeroes',function(){
    const txt=g.evidenceImportSummaryText(g.evidenceSummarizeImportResults([
      {name:'a.json',result:{ok:false,reason:'HASH_MISMATCH'}}
    ]));
    ok(txt.indexOf('Export CONFIRMED by re-import: 0')!==-1,
      'zero confirmations must be VISIBLE -- an omitted line reads as "did not happen"');
    ok(txt.indexOf('Rejected:                  1')!==-1,'and rejections are shown');
    ok(txt.indexOf('HASH_MISMATCH')!==-1,'with the reason');
    ok(txt.indexOf('a.json')!==-1,'and the offending filename');
    ok(txt.indexOf('No stored package was overwritten')!==-1,
      'and the operator is told explicitly that a rejection changed nothing');
  });
  t('BI9 batch import never bypasses the EXP-001 decision function',function(){
    // The confirmation decision still lives in exactly one place, reached through the per-file path.
    const src=String(g.evidenceImportPackageObject);
    ok(src.indexOf('evidenceEvaluateExportReimport')!==-1,
      'the single-file path -- which the batch calls -- still routes duplicates through the decision');
    eq(/evidenceEvaluateExportReimport/.test(String(g.evidenceImportFiles)),false,
      'and the batch does NOT reimplement or shortcut that decision itself');
  });
  t('BI10 both import surfaces share ONE handler, so neither can drift to a weaker path',function(){
    const banner=bannerWithAttempts();
    const bannerHandlers=(banner.match(/onchange="([^"]+)"/g)||[]);
    ok(bannerHandlers.length>0,'the banner has import inputs');
    bannerHandlers.forEach(function(h){
      ok(h.indexOf('evidenceHandleImportInputMulti')!==-1,'banner input uses the shared handler: '+h);
    });
    const card=String(g.renderEvidencePlatformDiagnostics);
    ok(card.indexOf('evidenceHandleImportInputMulti')!==-1,
      'the diagnostics card uses the same shared handler');
    ok(String(g.evidenceHandleImportInputMulti).indexOf('evidenceImportFiles')!==-1,
      'and that handler delegates to the batch, which delegates to the per-file path');
  });

  // ══ GROUP 6H — M-5 (D-12 / D-8): IDENTITY IS sourceTradeId, NEVER packageId ═══════════════
  // packageId is `PKG|strategy|YYYYMMDD|n` and n comes from a PER-ORIGIN sequence counter. Two
  // different trades captured at two origins on the same day therefore mint the SAME packageId.
  // That is measured, not theoretical: 79 real identities were found behind 65 packageIds, so
  // packageId-keyed counting undercounted by 14 -- and an undercount reports a SMALLER backlog
  // than exists, which is the dangerous direction.
  function pkg(o){
    return Object.assign({packageId:'PKG|alex_g_sr_v1|20260724|1',sourceTradeId:'AGT|A',
      contentHash:'a'.repeat(64),contentHashProvenance:'OBSERVED',
      identity:{captureOrigin:'http://localhost:8751'},export:{}},o||{});
  }
  function confirmedPkg(o){
    const p=pkg(o); p.export={exportedAt:'2026-08-01T00:00:00.000Z'}; return p;
  }
  t('ID1 two ORIGINS minting the same packageId are two trades, not one',function(){
    const r=g.evidenceReconcileByIdentity([
      pkg({sourceTradeId:'AGT|A',identity:{captureOrigin:'http://localhost:8751'}}),
      pkg({sourceTradeId:'AGT|B',contentHash:'b'.repeat(64),identity:{captureOrigin:'http://localhost:8744'}})
    ]);
    eq(r.uniqueSourceTrades,2,'identity is sourceTradeId -- the shared packageId must not merge them');
    eq(r.packageIdCollisions.length,1,'and the collision itself is REPORTED, not silently resolved');
    eq(r.packageIdCollisions[0].sourceTradeIds.length,2);
    eq(r.distinctOrigins,2,'both origins are recorded (D-12)');
  });
  t('ID2 duplicate PHYSICAL copies cannot inflate the unique-trade count',function(){
    const same=pkg();
    const r=g.evidenceReconcileByIdentity([same,pkg(),pkg()]);
    eq(r.physicalPackages,3,'three physical packages');
    eq(r.uniqueSourceTrades,1,'but ONE source trade');
    eq(r.duplicatePhysicalCopies,2,'and the duplication is stated explicitly');
    eq(r.ambiguousIdentity.length,0,'identical copies are an export instance, not a conflict');
  });
  t('ID3 one identity with CONFLICTING content is ambiguous and fails closed',function(){
    const r=g.evidenceReconcileByIdentity([pkg(),pkg({contentHash:'c'.repeat(64)})]);
    eq(r.ambiguousIdentity.length,1,'two different contents cannot both be this trade');
    eq(r.ambiguousIdentity[0].sourceTradeId,'AGT|A');
    eq(r.uniqueSourceTrades,1,'the identity is still one identity -- the conflict is reported, not resolved');
  });
  t('ID4 a package with NO identity is reported, never silently counted',function(){
    const r=g.evidenceReconcileByIdentity([pkg(),pkg({sourceTradeId:null}),pkg({sourceTradeId:''})]);
    eq(r.missingIdentity.length,2,'both unidentified packages are named');
    eq(r.uniqueSourceTrades,1,'and neither is counted as a trade');
  });
  t('ID5 a source trade is CONFIRMED only when every physical copy agrees',function(){
    eq(g.evidenceReconcileByIdentity([confirmedPkg()]).confirmed,1,'one confirmed copy, confirmed');
    const mixed=g.evidenceReconcileByIdentity([confirmedPkg(),pkg()]);
    eq(mixed.confirmed,0,'a confirmed copy cannot vouch for an unconfirmed sibling');
    eq(mixed.unconfirmed,1);
  });
  t('ID6 captureOrigin is first-class, and its absence is visible',function(){
    const r=g.evidenceReconcileByIdentity([pkg(),pkg({sourceTradeId:'AGT|B',contentHash:'b'.repeat(64),identity:{}})]);
    eq(r.missingOrigin.length,1,'a package with no captureOrigin is reported (D-12)');
    eq(r.missingOrigin[0].sourceTradeId,'AGT|B');
  });
  t('ID7 legacy packages without captureOrigin still VALIDATE (compatibility)',function(){
    // The 220 preserved packages predate the field. Requiring it outright would retroactively
    // invalidate every one of them, which is exactly what must not happen.
    const base=builtPackage();
    delete base.identity.captureOrigin;
    delete base.identity.captureOriginProvenance;
    eq(g.evidenceValidatePackage(base).valid,true,'a package with no captureOrigin key must still validate');
    const withNull=builtPackage();
    withNull.identity.captureOrigin=null;
    eq(g.evidenceValidatePackage(withNull).valid,true,'and an explicit null is tolerated');
    withNull.identity.captureOrigin=42;
    eq(g.evidenceValidatePackage(withNull).valid,false,'but a non-string is an error');
    withNull.identity.captureOrigin='';
    eq(g.evidenceValidatePackage(withNull).valid,false,'and so is an empty string');
  });
  t('ID8 reconciliation cannot throw on malformed input',function(){
    eq(g.evidenceReconcileByIdentity(null).uniqueSourceTrades,0);
    eq(g.evidenceReconcileByIdentity([null,undefined,'x']).missingIdentity.length,3,
      'malformed entries are counted as unidentified, never skipped');
  });

  // ══ GROUP 6I — M-8 (E-4): THE FORWARD-PAPER GATE IS FAIL-CLOSED ══════════════════════════
  // The gate it replaces was a dismissible confirm() wrapped in try{}catch(e){} that FAILED OPEN.
  // These fixtures exist to prove the replacement cannot be talked into passing.
  const CLEAN_RECON={physicalPackages:2,uniqueSourceTrades:2,duplicatePhysicalCopies:0,
    confirmed:2,unconfirmed:0,missingIdentity:[],ambiguousIdentity:[],packageIdCollisions:[],
    missingOrigin:[],unverifiable:[],originCounts:{'http://localhost:8751':2},distinctOrigins:1};
  function facts(o){
    return Object.assign({reconciliation:JSON.parse(JSON.stringify(CLEAN_RECON)),storeRead:'OK',
      hashVerification:{verified:2,mismatched:0,physical:2},campaignC1Intact:true,namedExceptions:[]},o||{});
  }
  const codes=function(v){ return v.blockers.map(function(b){return b.code;}); };

  t('G1 the fully clean state PASSES -- the gate is not merely always-false',function(){
    const v=g.evidenceEvaluateForwardPaperGate(facts());
    eq(v.pass,true,'a gate that can never pass proves nothing: '+JSON.stringify(codes(v)));
    eq(v.blockers.length,0);
  });
  t('G2 EVERY required condition is genuinely required',function(){
    // Each row removes exactly one condition from an otherwise-clean state.
    const cases=[
      ['NO_RECONCILIATION',{reconciliation:null}],
      ['NO_HASH_VERIFICATION',{hashVerification:null}],
      ['CAMPAIGN_C1',{campaignC1Intact:false}],
      ['CAMPAIGN_C1',{campaignC1Intact:'yes'}],
      ['HASH_MISMATCH',{hashVerification:{verified:2,mismatched:1,physical:2}}],
      ['INCOMPLETE_VERIFICATION',{hashVerification:{verified:1,mismatched:0,physical:2}}]
    ];
    cases.forEach(function(c){
      const v=g.evidenceEvaluateForwardPaperGate(facts(c[1]));
      eq(v.pass,false,c[0]+' must block');
      ok(codes(v).indexOf(c[0])!==-1,'expected blocker '+c[0]+', saw '+JSON.stringify(codes(v)));
    });
  });
  t('G3 every M-5 identity defect BLOCKS the gate',function(){
    const rows=[
      ['MISSING_IDENTITY',{missingIdentity:[{index:0,packageId:'PKG|x'}]}],
      ['AMBIGUOUS_IDENTITY',{ambiguousIdentity:[{sourceTradeId:'AGT|A',hashes:['a','b']}]}],
      ['PACKAGE_ID_COLLISION',{packageIdCollisions:[{packageId:'PKG|x',sourceTradeIds:['AGT|A','AGT|B']}]}],
      ['MISSING_ORIGIN',{missingOrigin:[{sourceTradeId:'AGT|A'}]}],
      ['UNVERIFIABLE',{unverifiable:[{sourceTradeId:'AGT|A'}]}],
      ['UNCONFIRMED',{unconfirmed:1,confirmed:1}]
    ];
    rows.forEach(function(r){
      const recon=Object.assign(JSON.parse(JSON.stringify(CLEAN_RECON)),r[1]);
      const v=g.evidenceEvaluateForwardPaperGate(facts({reconciliation:recon}));
      eq(v.pass,false,r[0]+' must block the gate');
      ok(codes(v).indexOf(r[0])!==-1,'expected '+r[0]+', saw '+JSON.stringify(codes(v)));
    });
  });
  t('G4 an EMPTY store passes ONLY when the read is positively confirmed',function(){
    // CORRECTED after Phase B. This fixture originally asserted that an empty corpus can never
    // pass. That was wrong, and testing proved it: the durable evidence profile starts EMPTY, no
    // evidence exists until a trade closes, and no trade can open until the gate passes -- a
    // deadlock. The real hazard was never emptiness; it was a FAILED read returning an empty list
    // and being mistaken for a clean one. That is what is now asserted.
    const empty=Object.assign(JSON.parse(JSON.stringify(CLEAN_RECON)),
      {physicalPackages:0,uniqueSourceTrades:0,confirmed:0,unconfirmed:0});
    const zero={verified:0,mismatched:0,physical:0};
    const okv=g.evidenceEvaluateForwardPaperGate(facts({reconciliation:empty,hashVerification:zero,storeRead:'OK'}));
    eq(okv.pass,true,'a genuinely empty store, positively read, is the safest possible state: '+JSON.stringify(codes(okv)));
    // ...and every way of NOT confirming the read blocks.
    [undefined,null,'','FAILED','ok',0,true].forEach(function(bad){
      const v=g.evidenceEvaluateForwardPaperGate(facts({reconciliation:empty,hashVerification:zero,storeRead:bad}));
      eq(v.pass,false,'storeRead='+JSON.stringify(bad)+' must block');
      ok(codes(v).indexOf('STORE_READ_UNCONFIRMED')!==-1,'saw '+JSON.stringify(codes(v)));
    });
  });
  t('G4b a NON-empty corpus still needs the read confirmed too',function(){
    const v=g.evidenceEvaluateForwardPaperGate(facts({storeRead:undefined}));
    eq(v.pass,false,'the assertion is required regardless of how much evidence was found');
    ok(codes(v).indexOf('STORE_READ_UNCONFIRMED')!==-1);
  });
  t('G4c only the gatherer may assert the read, and only after it succeeded',function(){
    const src=String(g.evidenceGatherForwardPaperFacts);
    const assertIdx=src.indexOf("storeRead='OK'");
    const awaitIdx=src.indexOf('await evidenceListPackages');
    ok(assertIdx!==-1,'the gatherer must assert the read');
    ok(awaitIdx!==-1&&assertIdx>awaitIdx,
      'and must do so only AFTER the awaited read returned -- never before attempting it');
    // the early-return path (read threw) must not carry the assertion
    const early=src.slice(0,awaitIdx===-1?0:src.indexOf('return facts;',awaitIdx));
    void early;
    ok(/catch[\s\S]{0,120}return facts;/.test(src),
      'a read that throws returns facts WITHOUT the assertion, so the gate blocks');
  });
  t('G5 absent facts BLOCK -- the gate never assumes what it was not told',function(){
    eq(g.evidenceEvaluateForwardPaperGate({}).pass,false,'no facts at all');
    eq(g.evidenceEvaluateForwardPaperGate(null).pass,false,'a null fact set');
    eq(g.evidenceEvaluateForwardPaperGate(undefined).pass,false,'an undefined fact set');
    const v=g.evidenceEvaluateForwardPaperGate({});
    ok(codes(v).indexOf('NO_RECONCILIATION')!==-1&&codes(v).indexOf('NO_HASH_VERIFICATION')!==-1
       &&codes(v).indexOf('CAMPAIGN_C1')!==-1,'and it names every missing fact');
  });
  t('G6 a named exception must be SPECIFIC and REASONED, never a blanket bypass',function(){
    const recon=Object.assign(JSON.parse(JSON.stringify(CLEAN_RECON)),{unverifiable:[{sourceTradeId:'AGT|A'}]});
    // a properly named exception excuses exactly its own identity
    const okv=g.evidenceEvaluateForwardPaperGate(facts({reconciliation:recon,
      namedExceptions:[{sourceTradeId:'AGT|A',reason:'captured on a non-secure origin; can never be hashed (D-14)'}]}));
    eq(okv.pass,true,'a specific, reasoned exception is honoured: '+JSON.stringify(codes(okv)));
    eq(okv.namedExceptionCount,1);
    // the WRONG identity does not excuse it
    const wrong=g.evidenceEvaluateForwardPaperGate(facts({reconciliation:recon,
      namedExceptions:[{sourceTradeId:'AGT|SOMETHING_ELSE',reason:'unrelated'}]}));
    eq(wrong.pass,false,'an exception for a different trade excuses nothing');
    // malformed exceptions BLOCK rather than being treated as none
    [[{sourceTradeId:'AGT|A'}],[{reason:'no id'}],['AGT|A'],[{sourceTradeId:'',reason:'x'}],'not-an-array'].forEach(function(bad){
      const v=g.evidenceEvaluateForwardPaperGate(facts({reconciliation:recon,namedExceptions:bad}));
      eq(v.pass,false,'a malformed exception list must BLOCK, never silently mean "no exceptions"');
      ok(codes(v).indexOf('MALFORMED_EXCEPTIONS')!==-1,'saw '+JSON.stringify(codes(v)));
    });
  });
  t('G7 the committed exception list is EMPTY by default',function(){
    eq(Array.isArray(g.EVIDENCE_PREFLIGHT_NAMED_EXCEPTIONS),true);
    eq(g.EVIDENCE_PREFLIGHT_NAMED_EXCEPTIONS.length,0,
      'no exception ships pre-approved -- each one must be added deliberately and reviewably');
  });
  t('G8 turning ON is gated; turning OFF is NEVER gated',function(){
    const src=String(g.toggleAlexGLiveTrading);
    ok(/turningOn/.test(src)&&src.indexOf('evidenceForwardPaperPreflight')!==-1,
      'the ON path must run the preflight');
    const gateIdx=src.indexOf('evidenceForwardPaperPreflight');
    const guard=src.slice(0,gateIdx);
    ok(/if\s*\(\s*turningOn\s*\)/.test(guard),
      'the preflight must sit behind an if(turningOn) guard -- a gate that could trap the operator '+
      'INTO trading would be worse than the one it replaces');
  });
  // Extracts the BALANCED brace block that follows an index. An earlier draft of G9 read a fixed
  // 400-character window instead, which was too wide: it ran past the end of the catch and found
  // the `return;` belonging to the NEXT guard, so deleting the catch's own return left the fixture
  // green. The mutation protocol caught that. A window is not a block.
  function blockAfter(src,from){
    const open=src.indexOf('{',from);
    if(open===-1) return '';
    let d=0;
    for(let i=open;i<src.length;i++){
      if(src[i]==='{') d++;
      else if(src[i]==='}'){ d--; if(d===0) return src.slice(open,i+1); }
    }
    return '';
  }
  t('G9 a preflight that THROWS blocks -- the old code swallowed exactly this',function(){
    const src=String(g.toggleAlexGLiveTrading);
    // The replaced gate was `try{ ...confirm... }catch(e){}` -- an exception meant trading started.
    const i=src.indexOf('evidenceForwardPaperPreflight');
    ok(i!==-1,'the preflight must be called');
    const c=src.indexOf('catch',i);
    ok(c!==-1,'the preflight call must be wrapped in an explicit catch');
    const block=blockAfter(src,c);
    ok(block.length>0,'the catch must have a body');
    ok(/return\s*;/.test(block),
      'the catch body ITSELF must RETURN, never fall through into enabling trading -- the replaced '+
      'gate swallowed its exception and started trading anyway (saw: '+block.slice(0,120)+')');
  });
  t('G9b a FAILING verdict blocks -- the refusal is acted on, not merely computed',function(){
    // Mutation-driven: neutering the verdict guard to if(false) previously survived every fixture,
    // because nothing asserted that the computed verdict was actually OBEYED.
    const src=String(g.toggleAlexGLiveTrading);
    const m=src.match(/if\s*\(\s*!verdict\s*\|\|\s*!verdict\.pass\s*\)/);
    ok(!!m,'the toggle must test the verdict itself -- both a missing verdict and a failing one');
    const block=blockAfter(src,src.indexOf(m[0]));
    ok(/return\s*;/.test(block),'and must RETURN when it does not pass (saw: '+block.slice(0,120)+')');
    // The enabling assignment must come after the guard, and must not be inside it.
    const enable=src.indexOf('alexGAutoTrading.enabled=turningOn');
    ok(enable>src.indexOf(m[0]),'trading is enabled only after the verdict has been obeyed');
    eq(block.indexOf('alexGAutoTrading.enabled'),-1,'and never from inside the refusal branch');
  });
  t('G10 the operator is told exactly why the gate refused',function(){
    const v=g.evidenceEvaluateForwardPaperGate({});
    const txt=g.evidenceForwardPaperGateText(v);
    ok(txt.indexOf('BLOCKED')!==-1||txt.indexOf('blocked')!==-1,'the refusal is explicit');
    codes(v).forEach(function(c){ ok(txt.indexOf(c)!==-1,'blocker '+c+' must appear in the operator text'); });
    ok(g.evidenceForwardPaperGateText({pass:true}).indexOf('PASS')!==-1,'and a pass says so');
  });
  t('G11 the gatherer never DECIDES Campaign C1 -- it reads the repository attestation',function(){
    // The browser holds no copy of C1, so computing a verdict here would be a fabrication. Phase A
    // replaced the hardcoded false with a read of the repository's attestation, evaluated by a
    // function that fails closed. What must never appear is a hardcoded TRUE.
    const src=String(g.evidenceGatherForwardPaperFacts);
    ok(src.indexOf('evidenceLoadCampaignC1Attestation')!==-1,'it must load the repository attestation');
    ok(src.indexOf('evidenceEvaluateCampaignC1Attestation')!==-1,'and evaluate it, never trust it as-read');
    eq(/campaignC1Intact\s*=\s*true/.test(src),false,'and must NEVER hardcode a C1 pass');
    ok(src.indexOf('evidenceVerifyPackageHash')!==-1,'and must independently re-verify each hash');
    ok(src.indexOf('evidenceReconcileByIdentity')!==-1,'and reconcile by identity');
  });
  t('G12 the verified count is keyed on sourceTradeId, so duplicates cannot satisfy the gate',function(){
    // The D-8 failure mode applied to the gate: 2 physical copies of ONE trade must not verify 2.
    const src=String(g.evidenceGatherForwardPaperFacts);
    ok(/verifiedIds\[p\.sourceTradeId\]/.test(src),
      'verification must be keyed on sourceTradeId, never on packageId or a physical count');
    // and the policy compares against uniqueSourceTrades, not physicalPackages
    const recon=Object.assign(JSON.parse(JSON.stringify(CLEAN_RECON)),
      {physicalPackages:4,uniqueSourceTrades:2,duplicatePhysicalCopies:2});
    const v=g.evidenceEvaluateForwardPaperGate(facts({reconciliation:recon,
      hashVerification:{verified:2,mismatched:0,physical:4}}));
    eq(v.pass,true,'two unique trades verified by four physical copies is complete');
    const short=g.evidenceEvaluateForwardPaperGate(facts({reconciliation:recon,
      hashVerification:{verified:4,mismatched:0,physical:4}}));
    eq(short.pass,true,'and an over-count of physical copies cannot create a shortfall');
  });

  // ══ GROUP 6J — PHASE A: CAMPAIGN C1 INTEGRITY ARRIVES FROM THE REPOSITORY ═════════════════
  // The browser cannot establish C1 integrity -- it holds no copy. Phase A supplies the fact from
  // `scripts/mogo_evidence_verify.js --campaign-c1-attest`, which re-hashes all 33 artifacts
  // against their manifest. The browser's job is to REFUSE that attestation unless every condition
  // holds. These fixtures exercise the real evaluator; the attestation shapes below are the real
  // committed shape, with the real committed manifest hash.
  const C1_OK={
    attestationVersion:'mogo.c1-attestation.v1',
    tool:'mogo-evidence-verify/1.0.0 (MOGO-011 Step 4A)',
    generatedAt:'2026-08-11T00:00:00.000Z',
    manifestPath:'docs/campaigns/C1/CAMPAIGN_C1_EVIDENCE_MANIFEST.md',
    manifestSha256:'c23e72e070e4e6e841e9e9cb77952a426743e666600e010c9bb14ca27fcee666',
    artifacts:{total:33,verified:33,missing:0,mismatched:0,unlisted:0},
    totalBytes:13575486,missingFiles:[],mismatchedFiles:[],unlistedFiles:[],verdict:'VERIFIED'};
  const C1_NOW=Date.parse('2026-08-11T01:00:00.000Z');   // one hour after the attestation
  function c1(over){ return Object.assign(JSON.parse(JSON.stringify(C1_OK)),over||{}); }
  const c1r=function(v){ return v.reasons; };

  t('C1A a genuine, fresh attestation for the PINNED manifest is accepted',function(){
    const v=g.evidenceEvaluateCampaignC1Attestation(C1_OK,C1_NOW);
    eq(v.intact,true,'the real committed attestation shape must be accepted: '+JSON.stringify(c1r(v)));
    eq(v.attestation.verified,33,'and its provenance is retained for the record');
    eq(v.attestation.total,33);
    ok(!!v.attestation.tool,'including which tool produced it');
  });
  t('C1B the pinned manifest hash is the anti-substitution link',function(){
    // A friendlier manifest cannot be swapped in: the browser pins the hash of the exact manifest
    // it will accept, so substitution requires editing committed source under review.
    const v=g.evidenceEvaluateCampaignC1Attestation(c1({manifestSha256:'b'.repeat(64)}),C1_NOW);
    eq(v.intact,false,'an attestation for a DIFFERENT manifest must be refused');
    ok(c1r(v).indexOf('MANIFEST_MISMATCH')!==-1);
    eq(g.evidenceEvaluateCampaignC1Attestation(c1({manifestSha256:null}),C1_NOW).intact,false,
      'and a missing manifest hash is refused too');
  });
  t('C1C a MISSING or malformed attestation fails closed',function(){
    [null,undefined,'','not-an-object',[],42].forEach(function(bad){
      const v=g.evidenceEvaluateCampaignC1Attestation(bad,C1_NOW);
      eq(v.intact,false,'a non-attestation must never be intact: '+JSON.stringify(bad));
    });
    eq(g.evidenceEvaluateCampaignC1Attestation(null,C1_NOW).reasons[0],'NO_ATTESTATION');
  });
  t('C1D a FAILED verification is refused, and so is every incomplete count',function(){
    eq(g.evidenceEvaluateCampaignC1Attestation(c1({verdict:'FAILED'}),C1_NOW).intact,false);
    const rows=[
      ['INCOMPLETE_VERIFICATION',{artifacts:{total:33,verified:32,missing:0,mismatched:0,unlisted:0}}],
      ['MISSING_ARTIFACTS',{artifacts:{total:33,verified:33,missing:1,mismatched:0,unlisted:0}}],
      ['MISMATCHED_ARTIFACTS',{artifacts:{total:33,verified:33,missing:0,mismatched:1,unlisted:0}}],
      ['UNLISTED_ARTIFACTS',{artifacts:{total:33,verified:33,missing:0,mismatched:0,unlisted:1}}],
      ['EMPTY_MANIFEST',{artifacts:{total:0,verified:0,missing:0,mismatched:0,unlisted:0}}]
    ];
    rows.forEach(function(r){
      const v=g.evidenceEvaluateCampaignC1Attestation(c1(r[1]),C1_NOW);
      eq(v.intact,false,r[0]+' must refuse');
      ok(c1r(v).indexOf(r[0])!==-1,'expected '+r[0]+', saw '+JSON.stringify(c1r(v)));
    });
  });
  t('C1E an absent count is NOT a zero',function(){
    const v=g.evidenceEvaluateCampaignC1Attestation(c1({artifacts:{total:33,verified:33}}),C1_NOW);
    eq(v.intact,false,'missing/mismatched/unlisted absent must refuse, never read as clean');
    ok(c1r(v).join(',').indexOf('MALFORMED_COUNT_')!==-1,'saw '+JSON.stringify(c1r(v)));
    eq(g.evidenceEvaluateCampaignC1Attestation(c1({artifacts:null}),C1_NOW).intact,false);
  });
  t('C1F a VERIFIED verdict CONTRADICTED by its own detail lists is refused',function(){
    // A verdict that disagrees with its own evidence is trusted less than either side of it.
    ['missingFiles','mismatchedFiles','unlistedFiles'].forEach(function(k){
      const o={}; o[k]=['C1-01-GBP_USD-PACKAGES.json'];
      const v=g.evidenceEvaluateCampaignC1Attestation(c1(o),C1_NOW);
      eq(v.intact,false,k+' non-empty must refuse a VERIFIED verdict');
    });
  });
  t('C1G a STALE attestation is not evidence about the corpus as it stands now',function(){
    const old=Date.parse('2026-08-11T00:00:00.000Z')+25*60*60*1000;   // 25h after generation
    const v=g.evidenceEvaluateCampaignC1Attestation(C1_OK,old);
    eq(v.intact,false,'beyond the max age it must refuse');
    ok(c1r(v).indexOf('STALE_ATTESTATION')!==-1);
    eq(g.evidenceEvaluateCampaignC1Attestation(C1_OK,Date.parse('2026-08-11T23:00:00.000Z')).intact,true,
      'but inside the window it is accepted');
  });
  t('C1H a FUTURE-DATED attestation is refused -- that direction buys unlimited freshness',function(){
    const v=g.evidenceEvaluateCampaignC1Attestation(C1_OK,Date.parse('2026-08-10T00:00:00.000Z'));
    eq(v.intact,false,'an attestation dated well in the future is a broken or forged clock');
    ok(c1r(v).indexOf('FUTURE_DATED_ATTESTATION')!==-1);
    // small skew is tolerated rather than refused
    eq(g.evidenceEvaluateCampaignC1Attestation(C1_OK,Date.parse('2026-08-10T23:58:00.000Z')).intact,true,
      'two minutes of clock skew must not refuse a genuine attestation');
    eq(g.evidenceEvaluateCampaignC1Attestation(c1({generatedAt:'not-a-date'}),C1_NOW).intact,false,
      'and an unparseable timestamp is refused');
  });
  t('C1I the loader turns EVERY failure into a null, never a fabricated fact',function(){
    const src=String(g.evidenceLoadCampaignC1Attestation);
    ok(/return null/.test(src),'a failed fetch yields null');
    ok(/catch\s*\(/.test(src),'and a thrown fetch is caught rather than escaping');
    ok(src.indexOf('res.ok')!==-1,'a non-200 response is not an attestation');
    ok(src.indexOf('EVIDENCE_C1_ATTESTATION_URL')!==-1,'and the URL is the pinned constant');
  });
  t('C1K THE REAL committed attestation is accepted by THE REAL evaluator',function(){
    // Closes the loop end to end: the artifact `scripts/mogo_evidence_verify.js --campaign-c1-attest`
    // actually wrote, evaluated by the function the browser actually runs, against the manifest hash
    // actually pinned in index.html. If any of those three drift apart, this fails.
    //
    // Evaluated at its OWN generatedAt + 1h rather than at wall-clock time, deliberately: staleness
    // is covered by C1G, and a permanent fixture that starts failing 24 hours after a commit would
    // be a clock test wearing a integrity test's clothes.
    let att=null;
    try{ att=JSON.parse(g.__C1_ATTESTATION_TEXT__||''); }catch(e){ att=null; }
    ok(!!att,'docs/campaigns/C1/C1_INTEGRITY_ATTESTATION.json must exist and parse');
    eq(att.manifestSha256,g.EVIDENCE_C1_MANIFEST_SHA256,
      'the committed attestation must describe the manifest index.html pins');
    const v=g.evidenceEvaluateCampaignC1Attestation(att,Date.parse(att.generatedAt)+3600000);
    eq(v.intact,true,'the real attestation must be accepted: '+JSON.stringify(v.reasons));
    eq(att.artifacts.total,33,'Campaign C1 is 33 artifacts');
    eq(att.artifacts.verified,33,'all 33 verified');
    eq(att.artifacts.mismatched,0,'0 mismatched');
    eq(att.artifacts.missing,0,'0 missing');
    eq(att.artifacts.unlisted,0,'0 unlisted');
    eq(att.totalBytes,13575486,'and the byte total the manifest itself declares');
  });
  t('C1J the gate treats a refused attestation exactly as it treats no attestation',function(){
    const refused=g.evidenceEvaluateCampaignC1Attestation(c1({verdict:'FAILED'}),C1_NOW);
    const v=g.evidenceEvaluateForwardPaperGate(facts({campaignC1Intact:refused.intact}));
    eq(v.pass,false,'a refused C1 attestation must block the forward-paper gate');
    ok(codes(v).indexOf('CAMPAIGN_C1')!==-1);
  });

  // ══ GROUP 6K — MOGO-013: THE DURABLE FORWARD OBSERVATION LEDGER ══════════════════════════
  // Financial outcomes were durable while scientific observations were not. These fixtures pin
  // the ledger's contract: what counts as the same observation, what must never be lost, and
  // that retention can never quietly delete history.
  //
  // DISCLOSED, consistent with this suite: IndexedDB does not exist here, so persistence and
  // reload survival are proven in a REAL disposable browser profile (see the milestone report),
  // never against the running campaign. What executes here is every pure rule the ledger obeys.
  function stat(over){
    return Object.assign({signalId:'AGL|alex_g_sr_v1|AUD_JPY|H1|...|1786428000000',setupId:'S1',
      pair:'AUD_JPY',timeframe:'H1',setupType:'A_repeatedReaction',direction:null,
      qualificationTimestamp:1786428000000,firstLiveEvaluationTimestamp:1786453262086,
      signalAgeMinutesAtEvaluation:421.03,status:'IGNORED — STALE SIGNAL',
      reason:'SIGNAL_TOO_OLD_AT_FIRST_EVALUATION',liveEvaluationFinal:true,
      zoneId:'Z1',zoneTouchNumber:4},over||{});
  }
  t('L1 a SUCCESSFUL poll is recorded as an operational observation',function(){
    const p=g.evidenceBuildPollObservation({tickId:'SCAN-1',startedAt:'2026-08-11T13:00:00.000Z',
      finishedAt:'2026-08-11T13:00:02.000Z',outcome:'OK',tradingEnabled:true,evaluationAdvanced:true,
      instrumentsAttempted:12,instrumentsEvaluated:['AUD_JPY','GBP_USD']});
    eq(p.kind,'POLL'); eq(p.outcome,'OK'); eq(p.durationMs,2000);
    eq(p.expectedIntervalMs,g.EVIDENCE_POLL_EXPECTED_INTERVAL_MS,'the expectation is STORED, not assumed later');
    eq(p.schemaVersion,g.EVIDENCE_OBSERVATION_SCHEMA_VERSION);
    ok(p.occurredAt&&p.recordedAt,'occurredAt and recordedAt are distinct fields');
  });
  t('L2 a FAILED poll is recorded too -- gaps are the point',function(){
    const p=g.evidenceBuildPollObservation({tickId:'SCAN-2',startedAt:'2026-08-11T13:01:00.000Z',
      finishedAt:'2026-08-11T13:01:01.000Z',outcome:'ERROR',errorText:'network down',
      instrumentsAttempted:12,instrumentsEvaluated:[]});
    eq(p.outcome,'ERROR'); eq(p.errorText,'network down');
    // and the seam records it from a finally block, so a throwing poll still lands
    const src=String(g.alexGLivePollTick);
    ok(/finally\s*\{/.test(src),'the poll seam must record from finally');
    ok(src.indexOf('evidenceRecordForwardObservations')!==-1,'and must call the ledger');
    ok(/throw e;/.test(src),'while still rethrowing the real error -- observation never swallows it');
  });
  t('L3 a REJECTED setup persists with its reason and rule attribution',function(){
    const e=g.evidenceBuildEvaluationObservation(stat({status:'IGNORED — BEFORE ACTIVATION',
      reason:'CONFIG_BEFORE_ACTIVATION',signalAgeMinutesAtEvaluation:5}),{});
    eq(e.kind,'EVALUATION'); eq(e.status,'IGNORED — BEFORE ACTIVATION');
    eq(e.reason,'CONFIG_BEFORE_ACTIVATION');
    eq(e.derivedActivationCutoffPassed,false);
    eq(e.ruleAttribution,'ALEX_ACTIVATION_CUTOFF');
    eq(e.derivedQualifying,false,'an ignored setup is not qualifying');
  });
  t('L4 a QUALIFYING setup persists and is distinguishable from a rejection',function(){
    const e=g.evidenceBuildEvaluationObservation(stat({status:'QUALIFIED',reason:null,
      liveEvaluationFinal:false}),{});
    eq(e.derivedQualifying,true); eq(e.derivedActivationCutoffPassed,true);
    eq(e.derivedStale,false); eq(e.ruleAttribution,null,'no rejection rule fired');
  });
  t('L5 a STALE setup persists with its age and staleness attribution',function(){
    const e=g.evidenceBuildEvaluationObservation(stat(),{});
    eq(e.derivedStale,true); eq(e.ruleAttribution,'ALEX_SIGNAL_STALENESS');
    eq(e.signalAgeMinutesAtEvaluation,421.03,'the age is recorded exactly as the strategy computed it');
    eq(e.qualificationTimestamp,1786428000000);
    eq(e.firstLiveEvaluationTimestamp,1786453262086);
    ok(e.qualificationAt&&e.firstLiveEvaluationAt,'and both are also stored human-readable');
  });
  t('L6 the HOURLY RE-CREATION MOGO-012 discovered is preserved, not deduped away',function(){
    // The same underlying setup re-recorded an hour later under a new first-evaluation time is a
    // DISTINCT observation of a real, repeated behaviour. Collapsing them would erase exactly the
    // phenomenon the ledger exists to record.
    const a=g.evidenceBuildEvaluationObservation(stat({firstLiveEvaluationTimestamp:1786449662086,
      signalAgeMinutesAtEvaluation:361.10}),{});
    const b=g.evidenceBuildEvaluationObservation(stat({firstLiveEvaluationTimestamp:1786453262086,
      signalAgeMinutesAtEvaluation:421.03}),{});
    const ka=g.evidenceObservationNaturalKey(a),kb=g.evidenceObservationNaturalKey(b);
    ok(ka!==kb,'an hourly re-evaluation must produce a DISTINCT natural key');
    ok(ka.indexOf('EVAL|')===0&&kb.indexOf('EVAL|')===0);
    // ...while a genuine repeat of the SAME observation must collapse
    eq(g.evidenceObservationNaturalKey(a),
       g.evidenceObservationNaturalKey(g.evidenceBuildEvaluationObservation(stat({
         firstLiveEvaluationTimestamp:1786449662086,signalAgeMinutesAtEvaluation:361.10}),{})),
       'the identical observation written twice collapses to one key');
  });
  t('L7 natural keys are deterministic per kind and cannot be null-collided',function(){
    eq(g.evidenceObservationNaturalKey({kind:'POLL',tickId:'T1'}),'POLL|T1');
    eq(g.evidenceObservationNaturalKey({kind:'RETENTION',evictedSeqFrom:1,evictedSeqTo:9}),'RETN|1|9');
    eq(g.evidenceObservationNaturalKey(null),null);
    eq(g.evidenceObservationNaturalKey({kind:'NONSENSE'}),null,'an unknown kind has no key and cannot be written');
    // a record with no key is refused by the writer rather than stored unkeyed
    ok(String(g.evidencePutObservation).indexOf('NO_NATURAL_KEY')!==-1);
  });
  t('L8 duplicate protection is STRUCTURAL, not remembered',function(){
    const src=String(g.evidencePutObservation);
    ok(/\.add\(/.test(src),'observations are add()ed, never put() -- put would overwrite history');
    eq(/\.put\(/.test(src),false,'no put() on the observation store');
    ok(src.indexOf('DUPLICATE_ALREADY_RECORDED')!==-1,
      'a rejected duplicate is reported as already-recorded, not as a failure');
    ok(String(g.evidenceRecordForwardObservations).indexOf('evidencePutObservation')!==-1);
  });
  t('L9 ordering is deterministic and monotonic',function(){
    const src=String(g.evidencePutObservation);
    ok(src.indexOf('evidenceAllocateObservationSeq')!==-1,'every observation takes a sequence number');
    ok(/seq:seq/.test(src),'which is stored on the record');
    // the summarizer orders by seq, never by insertion order or wall clock
    ok(/sort\(function\(a,b\)\{return \(a\.seq\|\|0\)-\(b\.seq\|\|0\);\}\)/.test(String(g.evidenceSummarizeObservations)),
      'poll continuity is computed in seq order');
  });
  t('L10 polling GAPS and missed intervals are derivable from stored records',function(){
    const mk=function(id,at,outcome){ return{kind:'POLL',seq:id,tickId:'T'+id,startedAt:at,
      outcome:outcome||'OK',instrumentsEvaluated:[],failures:[]}; };
    const s=g.evidenceSummarizeObservations([
      mk(1,'2026-08-11T13:00:00.000Z'),
      mk(2,'2026-08-11T13:01:00.000Z'),
      mk(3,'2026-08-11T19:01:00.000Z')          // a six-hour gap, exactly the INC-001 shape
    ]);
    eq(s.polls,3); eq(s.pollsOk,3);
    eq(s.maxGapMs,6*3600000,'the six-hour gap is measured, not inferred');
    eq(s.missedIntervals,359,'and the missed 60s intervals are counted');
    eq(s.gapsWithFailures.length,1,'the gap is reported with its surrounding context');
    eq(s.gapsWithFailures[0].from,'2026-08-11T13:01:00.000Z');
    eq(s.lastSuccessfulPollAt,'2026-08-11T19:01:00.000Z');
  });
  t('L11 API/data failures are associated with the period they occurred in',function(){
    const s=g.evidenceSummarizeObservations([
      {kind:'POLL',seq:1,startedAt:'2026-08-11T13:00:00.000Z',outcome:'ERROR',
       errorText:'broker 503',failures:[{pair:'AUD_JPY',kind:'FETCH'}],instrumentsEvaluated:[]},
      {kind:'POLL',seq:2,startedAt:'2026-08-11T14:00:00.000Z',outcome:'OK',
       failures:[],instrumentsEvaluated:['AUD_JPY']}
    ]);
    eq(s.pollsFailed,1);
    eq(s.gapsWithFailures.length,1,'the gap after a failed poll is surfaced');
    eq(s.gapsWithFailures[0].priorOutcome,'ERROR','with the failing poll attributed to it');
    eq(s.gapsWithFailures[0].priorError,'broker 503');
    eq(s.instrumentsSeen.AUD_JPY,1);
  });
  t('L12 evaluation statistics are derivable for the operations report',function(){
    const s=g.evidenceSummarizeObservations([
      g.evidenceBuildEvaluationObservation(stat(),{}),
      g.evidenceBuildEvaluationObservation(stat({status:'IGNORED — BEFORE ACTIVATION',
        reason:'CONFIG_BEFORE_ACTIVATION',firstLiveEvaluationTimestamp:1}),{}),
      g.evidenceBuildEvaluationObservation(stat({status:'QUALIFIED',reason:null,
        firstLiveEvaluationTimestamp:2}),{})
    ]);
    eq(s.evaluations,3); eq(s.staleEvaluations,1); eq(s.qualifyingEvaluations,1);
    eq(s.evaluationsByReason.SIGNAL_TOO_OLD_AT_FIRST_EVALUATION,1);
    eq(s.evaluationsByReason.CONFIG_BEFORE_ACTIVATION,1);
  });
  t('L13 RETENTION never silently deletes -- the marker is written FIRST',function(){
    const src=String(g.evidenceEnforceObservationRetention);
    const markerIdx=src.indexOf('evidencePutObservation(marker)');
    const deleteIdx=src.indexOf('.delete(');
    ok(markerIdx!==-1,'a RETENTION marker must be written');
    ok(deleteIdx!==-1,'and something must actually be evicted');
    ok(markerIdx<deleteIdx,
      'the marker must be recorded BEFORE the eviction, so a crash between them loses nothing silently');
    ok(/evictedSeqFrom/.test(src)&&/evictedSeqTo/.test(src)&&/evictedCount/.test(src),
      'and it must name exactly what was removed');
    ok(/evictedByKind/.test(src),'broken down by kind');
    ok(src.indexOf('NOT recoverable from this store')!==-1,
      'and state plainly that the evicted range is not recoverable here');
    // Mutation-driven: hardcoding the plan to {evict:true} survived, because L14 tests the PLANNER
    // while nothing asserted the enforcer OBEYS it. A planner nobody consults is decoration.
    ok(/const\s+plan\s*=\s*evidencePlanRetention\(/.test(src),
      'the enforcer must obtain its plan from evidencePlanRetention, never invent one');
    ok(/if\(!plan\.evict\)\s*return/.test(src),
      'and must return without evicting when the plan says not to');
  });
  t('L14 retention is a PLAN before it is an action, and is inspectable',function(){
    eq(g.evidencePlanRetention(10,100,5).evict,false,'under the cap nothing is evicted');
    eq(g.evidencePlanRetention(10,100,5).reason,'UNDER_CAP');
    const p=g.evidencePlanRetention(150,100,5);
    eq(p.evict,true); eq(p.reason,'CAP_EXCEEDED'); ok(p.evictCount>0);
    eq(g.evidencePlanRetention(null).evict,false,'a malformed count cannot trigger eviction');
    eq(g.evidencePlanRetention(undefined).evict,false);
    ok(g.EVIDENCE_OBSERVATION_MAX>=100000,'the cap is generous enough that rollover is rare');
  });
  t('L15 the ledger OBSERVES -- it can never alter a trading decision',function(){
    const seam=String(g.alexGLivePollTick);
    // the ledger call's return value is never read, and it is wrapped so it cannot throw outward
    ok(/try\{\s*evidenceRecordForwardObservations/.test(seam.replace(/\n\s*/g,' ')),
      'the seam call must be wrapped in its own try');
    eq(/=\s*evidenceRecordForwardObservations/.test(seam),false,
      'its return value must never be assigned or consulted');
    eq(/await\s+evidenceRecordForwardObservations/.test(seam),false,
      'and never awaited -- the trading path must not wait on the ledger');
    const rec=String(g.evidenceRecordForwardObservations);
    ok(/catch\(e\)\{/.test(rec),'the recorder swallows its own failures');
    ok(rec.indexOf('evidenceRecordWriteFailure')!==-1,'into the existing write-failure channel');
  });
  t('L15b the seam actually FEEDS the real status ledger, not an empty list',function(){
    // Mutation-driven. Replacing the seam's `statuses:` argument with `[]` silently disabled every
    // evaluation observation -- the ledger's entire scientific purpose -- and SURVIVED every other
    // fixture, because they all test the builders rather than the wiring. A ledger that is wired
    // to nothing passes a builder test perfectly.
    const seam=String(g.alexGLivePollTick).replace(/\n\s*/g,' ');
    const m=seam.match(/statuses\s*:\s*([^}]+?)\}\)/);
    ok(!!m,'the seam must pass a statuses argument');
    const arg=m?m[1]:'';
    ok(arg.indexOf('alexGLiveSetupStatuses')!==-1,
      'the seam must pass the REAL status array the strategy recorded (saw: '+arg.trim().slice(0,80)+')');
    eq(/statuses\s*:\s*\[\s*\]/.test(seam),false,'and must never pass an empty list unconditionally');
    // NO SILENT CAPS at the seam either. A truncated feed loses observations exactly as invisibly
    // as an empty one, and it survived a mutation until this was added.
    eq(/\.slice\(|\.splice\(|\.filter\(/.test(arg),false,
      'the status feed must not be sliced, spliced or filtered on its way to the ledger (saw: '+arg.trim().slice(0,80)+')');
  });
  t('L16 protected strategy functions are NOT referenced by the ledger',function(){
    const all=String(g.evidenceRecordForwardObservations)+String(g.evidenceBuildEvaluationObservation)+
      String(g.evidenceBuildPollObservation)+String(g.evidenceSummarizeObservations);
    ['alexGRecordLiveSetupStatus','alexGIsSetupSignalStale','alexGRunSetupEngine'].forEach(function(fn){
      eq(all.indexOf(fn),-1,'the ledger must not call the protected function '+fn);
    });
  });
  t('L17 pipeline observations REFERENCE authoritative records rather than copying them',function(){
    const p=g.evidenceBuildPipelineObservation({stage:'OPENED',pair:'AUD_JPY',
      sourceTradeId:'AGT|1',tradeId:'T1',packageId:'PKG|x|20260811|1',occurredAt:'2026-08-11T13:00:00.000Z'});
    eq(p.kind,'PIPELINE'); eq(p.stage,'OPENED');
    eq(p.sourceTradeId,'AGT|1'); eq(p.packageId,'PKG|x|20260811|1');
    eq(p.entryPrice,undefined,'no price is copied -- the account and package remain authoritative');
    eq(p.balance,undefined,'no balance is copied');
  });
  t('L18 every observation carries provenance and origin',function(){
    [g.evidenceBuildPollObservation({tickId:'T'}),
     g.evidenceBuildEvaluationObservation(stat(),{}),
     g.evidenceBuildPipelineObservation({stage:'OPENED'})].forEach(function(o){
      eq(o.provenance,'FORWARD_LIVE_OBSERVATION','provenance is explicit');
      eq(o.schemaVersion,g.EVIDENCE_OBSERVATION_SCHEMA_VERSION,'schema version is stamped');
      ok('captureOrigin' in o,'origin is recorded (null offline, real in the browser)');
      ok('appVersion' in o&&'strategyId' in o,'engine and strategy identity are stamped');
    });
  });
  t('L19 malformed input can never throw into the trading path',function(){
    g.evidenceBuildPollObservation(null);
    g.evidenceBuildPollObservation(undefined);
    g.evidenceBuildEvaluationObservation(null,null);
    g.evidenceBuildPipelineObservation(null);
    eq(g.evidenceSummarizeObservations(null).total,0);
    eq(g.evidenceSummarizeObservations([null,undefined,'x']).total,3,'malformed entries are counted, not skipped');
    ok(true,'no builder threw');
  });

  t('E12 the import path routes a known package through the EXP-001 decision function',function(){
    const src=String(g.evidenceImportPackageObject);
    ok(src.indexOf('evidenceEvaluateExportReimport')!==-1,'a duplicate must go through the decision');
    ok(src.indexOf('EXPORT_VERIFIED_BY_REIMPORT')!==-1,'a verified re-import must report itself');
    ok(src.indexOf('evidenceBuildVerifiedExportState')!==-1,'and mark the stored package verified');
    ok(src.indexOf('DUPLICATE_CONFLICTING_HASH')!==-1,'a conflicting duplicate must still be rejected');
  });

  // ══ GROUP 6C — DoD #10: JVM / current_strategy second-strategy demonstration ═══════════
  // Phase 1 requires the platform be demonstrated on ALEX AND one other strategy with no schema
  // change. These exercise the REAL normalization adapter, the REAL builder and the REAL
  // commitPaperLedger seam. Nothing is re-implemented.
  function jvmClosedPosition(over){
    // The genuine JVM shape: id/oPair/dir/lots -- NOT tradeId/pair/direction/positionSize, and
    // no `strategy` field at all. That mismatch is exactly what the adapter exists to bridge.
    const p={id:1754000000001,pair:'EUR/USD',oPair:'EUR_USD',dir:'buy',
      entry:1.1000,stop:1.0950,target:1.1100,riskPips:50,rewardPips:100,ratio:2,
      riskAmount:100,lots:0.2,units:20000,pipValueAtEntry:10,
      openedAt:'2026-08-01T10:00:00.000Z',source:'auto',
      exitPrice:1.1100,pnl:200,result:'Win',closeReason:'TARGET_HIT',
      closedAt:'2026-08-01T12:00:00.000Z'};
    if(over) Object.keys(over).forEach(function(k){ p[k]=over[k]; });
    return p;
  }

  t('J1 a JVM closed position normalizes into exactly one buildable v1 package',function(){
    const norm=g.evidenceNormalizeJvmTrade(jvmClosedPosition());
    ok(norm,'the adapter must accept a real JVM closed position');
    eq(norm.tradeId,'1754000000001','JVM id -> tradeId');
    eq(norm.pair,'EUR_USD','oPair (OANDA form) preferred over the display form');
    eq(norm.direction,'buy','dir -> direction');
    eq(norm.positionSize,0.2,'lots -> positionSize');
    const pkg=g.evidenceBuildPackageFromTrade(norm,
      {packageId:'PKG|current_strategy|20260801|1',strategyId:'current_strategy'});
    ok(g.evidenceValidatePackage(pkg).valid,'the built package must validate: '+
      g.evidenceValidatePackage(pkg).errors.join('; '));
    eq(pkg.objectCounts.positions,1);
    eq(pkg.objectCounts.outcomes,1);
    return 'one valid v1 package from a real JVM position';
  });

  t('J2 identity.strategyId is current_strategy and NEVER alex_g_sr_v1',function(){
    const norm=g.evidenceNormalizeJvmTrade(jvmClosedPosition());
    const pkg=g.evidenceBuildPackageFromTrade(norm,
      {packageId:'PKG|current_strategy|20260801|1',strategyId:'current_strategy'});
    eq(pkg.identity.strategyId,'current_strategy');
    ok(pkg.identity.strategyId!=='alex_g_sr_v1','a JVM trade must never be attributed to ALEX');
    eq(g.getJvmStrategyId(),'current_strategy','the committed JVM identifier is used verbatim');
  });

  t('J2b a missing/invalid strategyId FAILS CLOSED — no silent ALEX default',function(){
    const bare={tradeId:'X1',pair:'EUR_USD'};            // no strategy field anywhere
    throws(function(){ g.evidenceBuildPackageFromTrade(bare,{packageId:'PKG|x|1|1'}); },
      'an unattributable trade must throw, not default to ALEX');
    // and the removed defect must not reappear anywhere in the shipped layer
    ok(!/strategyId:\s*trade\.strategy\s*\|\|\s*'alex_g_sr_v1'/.test(LAYER),
      'the ALEX fallback must not exist in code');
    return 'fails closed on missing identity';
  });

  t('J3 ALEX and JVM packages coexist and remain independently retrievable',function(){
    const alexPkg=builtPackage();                        // strategy alex_g_sr_v1
    const jvmPkg=g.evidenceBuildPackageFromTrade(g.evidenceNormalizeJvmTrade(jvmClosedPosition()),
      {packageId:'PKG|current_strategy|20260801|1',strategyId:'current_strategy'});
    eq(alexPkg.identity.strategyId,'alex_g_sr_v1');
    eq(jvmPkg.identity.strategyId,'current_strategy');
    ok(alexPkg.packageId!==jvmPkg.packageId,'distinct package ids');
    ok(alexPkg.sourceTradeId!==jvmPkg.sourceTradeId,'distinct source trade ids');
    const summary=g.countUnexportedLike([alexPkg,jvmPkg]);
    eq(summary.total,2,'both coexist in one store view');
  });

  t('J4 packageSchemaVersion and structure are IDENTICAL across both strategies',function(){
    const a=builtPackage();
    const j=g.evidenceBuildPackageFromTrade(g.evidenceNormalizeJvmTrade(jvmClosedPosition()),
      {packageId:'PKG|current_strategy|20260801|1',strategyId:'current_strategy'});
    eq(j.packageSchemaVersion,a.packageSchemaVersion,'same schema version');
    eq(Object.keys(j).sort().join(','),Object.keys(a).sort().join(','),'same top-level keys');
    eq(Object.keys(j.objects).sort().join(','),Object.keys(a.objects).sort().join(','),'same objects keys');
    eq(Object.keys(j.identity).sort().join(','),Object.keys(a.identity).sort().join(','),'same identity keys');
    eq(Object.keys(j.objectCounts).sort().join(','),Object.keys(a.objectCounts).sort().join(','),'same count keys');
    return 'schema unchanged — no per-strategy divergence';
  });

  t('J5 sequence allocation is isolated per strategy',function(){
    const src=String(g.evidenceAllocateSequence);
    ok(/'seq\|'\+strategyId\+'\|'\+yyyymmdd/.test(src),
      'the counter key must be namespaced by strategyId, so JVM cannot consume ALEX sequence numbers');
    const persist=String(g.evidencePersistTradePackageResolved||g.evidencePersistTradePackage);
    ok(persist.indexOf('evidenceAllocateSequence(strategyId')!==-1,
      'allocation must use the resolved strategyId');
  });

  t('J6 evidence capture cannot alter paperAccount, journal, balance or closedPositions',function(){
    const src=String(g.evidenceCaptureClosedPaperTrades)+String(g.evidenceCaptureClosedPaperTradesAsync)+
              String(g.evidenceNormalizeJvmTrade);
    eq(src.indexOf('journalEntries'),-1,'must never reference the JVM journal');
    eq(src.indexOf('commitPaperLedger'),-1,'must never re-enter the ledger commit');
    eq(src.indexOf('closePaperPosition'),-1,'must never re-enter the protected close');
    ok(!/paperAccount\.(balance|closedPositions|openPositions)\s*=/.test(src),'must never assign account state');
    ok(!/closedPositions\.(push|splice|unshift|pop|shift)/.test(src),'must never mutate closedPositions');
    ok(src.indexOf('closedPositions.slice')!==-1,'it reads a COPY of closed positions');
  });

  t('J7/J8 closePaperPosition and commitPaperLedger return contracts are unchanged',function(){
    const close=g.getSource('function closePaperPosition');
    ok(close.indexOf('return{closedPos,committed:true}')!==-1,'success contract intact');
    ok(close.indexOf('integrityCompromised:!!committed.integrityCompromised')!==-1,'blocked contract intact');
    eq(close.indexOf('evidenceCapture'),-1,'the PROTECTED close function must contain no evidence code');
    const commit=g.getSource('function commitPaperLedger');
    ok(commit.indexOf('return{ok:true,integrityCompromised:false}')!==-1,'success return unchanged');
    ok(commit.indexOf('return{ok:false,integrityCompromised:true')!==-1,'fatal return unchanged');
    ok(commit.indexOf('return{ok:false,integrityCompromised:false')!==-1,'ordinary rejection return unchanged');
    // the capture call must come AFTER save() and BEFORE the success return, and nowhere else
    ok(commit.indexOf('evidenceCaptureClosedPaperTrades')>commit.indexOf('save();'),
      'capture must follow the successful save');
    ok(commit.indexOf('evidenceCaptureClosedPaperTrades')<commit.indexOf('return{ok:true'),
      'and precede only the success return');
  });

  t('J9 a failed or blocked commit creates NO package',function(){
    const commit=g.getSource('function commitPaperLedger');
    const firstFail=commit.indexOf('return{ok:false');
    const capture=commit.indexOf('evidenceCaptureClosedPaperTrades');
    ok(firstFail<capture,'both failure returns exit before the capture call is ever reached');
    ok(commit.indexOf('return{ok:false,integrityCompromised:true')<capture,'including the fatal branch');
  });

  t('J10 duplicate capture is impossible — non-null sourceTradeId + unique index',function(){
    const norm=g.evidenceNormalizeJvmTrade(jvmClosedPosition());
    ok(norm.tradeId!=null&&norm.tradeId!=='','tradeId must be non-null, or the unique index cannot bind');
    const pkg=g.evidenceBuildPackageFromTrade(norm,
      {packageId:'PKG|current_strategy|20260801|1',strategyId:'current_strategy'});
    eq(pkg.sourceTradeId,'1754000000001','sourceTradeId populated — IndexedDB does not index nulls');
    ok(String(g.evidenceOpenDb).indexOf("createIndex('bySourceTradeId','sourceTradeId',{unique:true})")!==-1,
      'the unique index still enforces one package per trade');
    ok(String(g.evidenceCaptureClosedPaperTradesAsync).indexOf('evidenceHasPackageForTrade')!==-1,
      'and capture checks before persisting');
    // a position with no id cannot be captured at all, rather than becoming a null-keyed duplicate
    eq(g.evidenceNormalizeJvmTrade({oPair:'EUR_USD'}),null,'an id-less position is refused outright');
  });

  t('J11 a throwing capture cannot propagate into the close path',function(){
    const commit=g.getSource('function commitPaperLedger');
    ok(/try\{\s*evidenceCaptureClosedPaperTrades\(\);\s*\}catch\(e\)\{/.test(commit),
      'the capture call must be individually wrapped');
    ok(/catch\(e\)\{[^}]*evidenceRecordWriteFailure\('capture-jvm-seam'/.test(commit),
      'and must record rather than swallow');
    // real execution: no IndexedDB in this harness, so the async path genuinely fails
    let threw=false,ret;
    try{ ret=g.evidenceCaptureClosedPaperTrades(); }catch(e){ threw=true; }
    no(threw,'the capture call must never throw');
    eq(ret,undefined,'and must not return a value the ledger path could block on');
  });

  // ══ GROUP 6D — REPLAY run identity + evidence capture (v12.9.0) ════════════════════════
  // Replay is the only route to a statistically meaningful sample. These exercise the REAL
  // normalizer, the REAL builder and the REAL source of runAlexGReplay/runAlexGReplayUI.
  function replayTrade(over){
    const t={tradeId:'AGT|REPLAY|1', setupId:'AGS|EUR_USD|H1|z1|B_breakRetest|r1',
      strategy:'alex_g_sr_v1', ruleVersion:'alex_g_sr_v1', createdByEngineVersion:'12.9.0',
      pair:'EUR_USD', timeframe:'H1', setupType:'B_breakRetest', setupLabel:'BREAK & RETEST',
      direction:'buy', entry:1.1000, stop:1.0950, target:1.1100, plannedRR:2,
      riskPercent:1, riskAmount:100, pipValue:10, positionSize:0.2,
      balanceBefore:10000, balanceAfter:10200,
      entryTimestamp:Date.UTC(2026,4,1,10,0), exitTimestamp:Date.UTC(2026,4,1,16,0),
      qualificationTimestamp:Date.UTC(2026,4,1,9,0),
      exitPrice:1.1100, result:'Win', resultR:2,
      maePips:5, mfePips:100, maeR:-0.1, mfeR:2,
      ambiguous:false, ambiguousMode:'conservative', stillOpen:false,
      zoneId:'AGZ|z1', zoneLow:1.094, zoneHigh:1.096, zoneCenter:1.095, atrAtEntry:0.0012,
      configurationSnapshot:{ruleVersion:'alex_g_sr_v1'}};
    if(over) Object.keys(over).forEach(function(k){ t[k]=over[k]; });
    return t;
  }
  const RUN={runId:'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
    datasetHash:'0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f',
    // v12.19.0 MOGO-004 L2: the run identity has always carried these two; they are now persisted.
    configHash:'1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c',
    paramsHash:'2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p2p',
    strategyId:'alex_g_sr_v1',
    range:{requestedDays:90,fromUTC:'2026-02-01T00:00:00.000Z',toUTC:'2026-05-01T00:00:00.000Z'}};

  t('R1 a resolved replay trade normalizes onto the common shape',function(){
    const n=g.evidenceNormalizeReplayTrade(replayTrade(),RUN);
    ok(n,'the adapter must accept a real replay trade');
    eq(n.direction,'buy'); eq(n.entry,1.1000); eq(n.result,'Win'); eq(n.resultR,2);
    eq(n.balanceAtEntry,10000,'balanceBefore -> balanceAtEntry');
    eq(n.openedAt,'2026-05-01T10:00:00.000Z','entryTimestamp -> ISO openedAt');
    eq(n.closedAt,'2026-05-01T16:00:00.000Z','exitTimestamp -> ISO closedAt');
    ok(!Object.prototype.hasOwnProperty.call(n,'pnl'),
      'pnl must NOT be reconstructed by subtracting balances — arithmetic on stored values is not an observation');
  });

  t('R2 sourceTradeId is namespaced so live and replay observations cannot collide',function(){
    const n=g.evidenceNormalizeReplayTrade(replayTrade(),RUN);
    ok(n.tradeId.indexOf('REPLAY|')===0,'replay ids must be namespaced');
    ok(n.tradeId.indexOf(String(RUN.runId).slice(0,12))!==-1,'namespaced by runId');
    ok(n.tradeId!=='AGT|REPLAY|1','and must differ from the raw live-style id');
    eq(n.replaySourceTradeId,'AGT|REPLAY|1','the original id is preserved, not discarded');
  });

  t('R3 an UNRESOLVED replay trade produces no package',function(){
    eq(g.evidenceNormalizeReplayTrade(replayTrade({stillOpen:true}),RUN),null,'still-open is not an observation');
    eq(g.evidenceNormalizeReplayTrade(replayTrade({result:null}),RUN),null,'no result is not an observation');
    eq(g.evidenceNormalizeReplayTrade(replayTrade(),null),null,'no run identity -> no capture');
    eq(g.evidenceNormalizeReplayTrade(null,RUN),null);
  });

  t('R4 a replay package carries mode REPLAY, the runId and the dataset hash',function(){
    const n=g.evidenceNormalizeReplayTrade(replayTrade(),RUN);
    const pkg=g.evidenceBuildPackageFromTrade(n,{packageId:'PKG|alex_g_sr_v1|20260501|1',
      strategyId:'alex_g_sr_v1',captureBasis:'REPLAY_RUN',
      // v12.19.0 MOGO-004 L2: a REPLAY package now requires all four per-run identity hashes
      // (PRE-REG-001 §8.1), so this fixture supplies the two that were previously dropped.
      mode:'REPLAY',runId:RUN.runId,datasetHash:RUN.datasetHash,replayDateRange:RUN.range,
      configHash:RUN.configHash,paramsHash:RUN.paramsHash});
    eq(pkg.identity.mode,'REPLAY');
    eq(pkg.identity.runId,RUN.runId);
    eq(pkg.identity.datasetHash,RUN.datasetHash);
    eq(pkg.identity.replayDateRange.fromUTC,'2026-02-01T00:00:00.000Z','ABSOLUTE range, not "N days back from now"');
    eq(pkg.identity.replayDateRange.toUTC,'2026-05-01T00:00:00.000Z');
    ok(g.evidenceValidatePackage(pkg).valid,'must validate: '+g.evidenceValidatePackage(pkg).errors.join('; '));
  });

  t('R5 schema is UNCHANGED — identical key sets across LIVE_PAPER and REPLAY',function(){
    const live=builtPackage();
    const n=g.evidenceNormalizeReplayTrade(replayTrade(),RUN);
    const rep=g.evidenceBuildPackageFromTrade(n,{packageId:'PKG|alex_g_sr_v1|20260501|1',
      strategyId:'alex_g_sr_v1',captureBasis:'REPLAY_RUN',
      mode:'REPLAY',runId:RUN.runId,datasetHash:RUN.datasetHash,replayDateRange:RUN.range,
      configHash:RUN.configHash,paramsHash:RUN.paramsHash});
    eq(rep.packageSchemaVersion,live.packageSchemaVersion,'same schema version');
    eq(Object.keys(rep).sort().join(','),Object.keys(live).sort().join(','),'same top-level keys');
    eq(Object.keys(rep.identity).sort().join(','),Object.keys(live.identity).sort().join(','),
      'identity key sets must match — the additive keys are always present, null for live');
    eq(live.identity.mode,'LIVE_PAPER'); eq(live.identity.runId,null);
    eq(live.identity.datasetHash,null); eq(live.identity.replayDateRange,null);
    // v12.19.0 MOGO-004 L2: required-and-present for LIVE_PAPER evidence, carrying null because a
    // live trade has no replay config or parameter set. The KEY is mandatory; the VALUE is honest.
    ok('configHash' in live.identity,'LIVE_PAPER evidence must carry the configHash key');
    ok('paramsHash' in live.identity,'LIVE_PAPER evidence must carry the paramsHash key');
    eq(live.identity.configHash,null); eq(live.identity.paramsHash,null);
  });

  t('R5b MOGO-004 L2 — a REPLAY package persists configHash and paramsHash',function(){
    const n=g.evidenceNormalizeReplayTrade(replayTrade(),RUN);
    const rep=g.evidenceBuildPackageFromTrade(n,{packageId:'PKG|alex_g_sr_v1|20260501|1',
      strategyId:'alex_g_sr_v1',captureBasis:'REPLAY_RUN',
      mode:'REPLAY',runId:RUN.runId,datasetHash:RUN.datasetHash,replayDateRange:RUN.range,
      configHash:RUN.configHash,paramsHash:RUN.paramsHash});
    // PRE-REG-001 §8.1 requires all four per-run identity hashes. Before v12.19.0 only two of them
    // reached the package, and the other two were unrecoverable once the run returned.
    eq(rep.identity.runId,RUN.runId);
    eq(rep.identity.datasetHash,RUN.datasetHash);
    eq(rep.identity.configHash,RUN.configHash,'configHash must be persisted verbatim');
    eq(rep.identity.paramsHash,RUN.paramsHash,'paramsHash must be persisted verbatim');
    ok(g.evidenceValidatePackage(rep).valid,'a fully identified replay package must validate');
  });

  t('R5c MOGO-004 L2 — the two hashes are recorded, never recomputed, and runId is unaffected',function(){
    // The persistence change must not touch how any hash is DERIVED. runId is still the content
    // hash built by alexGBuildReplayRunIdentity, and the package must not re-derive anything.
    const src=String(g.evidenceBuildPackageFromTrade);
    eq(/evidenceContentHash\s*\(/.test(src),false,'the package builder must never compute a hash');
    const n=g.evidenceNormalizeReplayTrade(replayTrade(),RUN);
    const rep=g.evidenceBuildPackageFromTrade(n,{packageId:'PKG|alex_g_sr_v1|20260501|1',
      strategyId:'alex_g_sr_v1',captureBasis:'REPLAY_RUN',
      mode:'REPLAY',runId:RUN.runId,datasetHash:RUN.datasetHash,replayDateRange:RUN.range,
      configHash:RUN.configHash,paramsHash:RUN.paramsHash});
    eq(rep.identity.runId,RUN.runId,'runId is carried through unchanged, not rebuilt');
  });

  t('R5d MOGO-004 L2 — legacy packages still validate; a regressed REPLAY package does not',function(){
    const n=g.evidenceNormalizeReplayTrade(replayTrade(),RUN);
    const base={packageId:'PKG|alex_g_sr_v1|20260501|1',strategyId:'alex_g_sr_v1',
      captureBasis:'REPLAY_RUN',mode:'REPLAY',runId:RUN.runId,datasetHash:RUN.datasetHash,
      replayDateRange:RUN.range,configHash:RUN.configHash,paramsHash:RUN.paramsHash};
    // A package captured before v12.19.0 omits both keys entirely. RUN-001 (24 packages) and the
    // MOGO-004 pilot (50 packages) are exactly this shape and are already hash-verified.
    const legacy=g.evidenceBuildPackageFromTrade(n,base);
    delete legacy.identity.configHash; delete legacy.identity.paramsHash;
    ok(g.evidenceValidatePackage(legacy).valid,
      'omitting the keys must stay valid -- 74 verified packages depend on this');
    // But a REPLAY package that carries the key and nulls it could only be a capture regression.
    const regressed=g.evidenceBuildPackageFromTrade(n,base);
    regressed.identity.configHash=null;
    const v=g.evidenceValidatePackage(regressed);
    eq(v.valid,false,'a null configHash on a REPLAY package must fail validation');
    ok(v.errors.join(';').indexOf('configHash')!==-1,'the error must name the field');
  });

  t('R6 replay completeness honestly flags money-space non-determinism',function(){
    const c=g.evidenceComputeCompleteness('REPLAY_RUN');
    eq(c.level,'PARTIAL','a replay package must never claim COMPLETE');
    ok(c.missing.some(function(m){ return /money-space/.test(m.field)&&m.reason==='DERIVED'; }),
      'money-space values must be flagged DERIVED with a LIVE_DATA_DEPENDENCY note');
    ok(c.missing.some(function(m){ return m.field==='outcomes[].pnl'&&m.reason==='UNAVAILABLE'; }),
      'pnl must be recorded as UNAVAILABLE rather than reconstructed');
    ok(JSON.stringify(c).indexOf('LIVE_DATA_DEPENDENCY')!==-1,'architecture 7.1 flag present');
  });

  t('R7 the run identity is DETERMINISTIC and content-derived',function(){
    const src=String(g.alexGBuildReplayRunIdentity);
    ok(/runId=await evidenceContentHash/.test(src),'runId must be a content hash, not a random id');
    ['strategyId','pair','fromUTC','toUTC','datasetHash','configHash','paramsHash'].forEach(function(k){
      ok(src.indexOf(k)!==-1,'runId must incorporate '+k);
    });
    eq(src.indexOf('Math.random'),-1,'never random');
    eq(src.indexOf('Date.now()'),-1,'never wall-clock — that would break reproducibility');
  });

  t('R8 the dataset hash covers EVERY candle, not a fingerprint',function(){
    const src=String(g.evidenceReplayDatasetHash);
    ok(/for\(let i=0;i<arr\.length;i\+\+\)/.test(src),'every candle must be walked');
    ok(/c\.o\+','\+c\.h\+','\+c\.l\+','\+c\.c/.test(src),'OHLC must all contribute');
    ok(src.indexOf('evidenceContentHash')!==-1,'hashed with SHA-256');
    ok(/'W','D','H4','H1'/.test(src),'all four timeframes covered');
  });

  t('R9 the capture seam is in a NON-protected function and cannot alter replay output',function(){
    const protectedList=g.getBaselineAlexFunctions();
    ['alexGRunSetupReplay','alexGConstructTrade','alexGWalkOutcome','alexGComputeReplayStats']
      .forEach(function(f){ ok(protectedList.indexOf(f)!==-1,f+' must be PROTECTED'); });
    eq(protectedList.indexOf('runAlexGReplay'),-1,'the identity seam is not protected');
    eq(protectedList.indexOf('runAlexGReplayUI'),-1,'the capture seam is not protected');
    const ui=g.getSource('async function runAlexGReplayUI()');
    // v12.10.0 Unit A added the read-only setups argument; v12.12.0 Unit C1 added the read-only
    // candle arrays. The assertion is UNCHANGED in strength: the call must still be individually
    // wrapped in its own try/catch.
    ok(/try\{ evidenceCaptureReplayTrades\(result\.runIdentity,result\.trades,result\.setups,result\.candlesByTimeframe\); \}catch/.test(ui),
      'capture must be individually wrapped');
    ok(ui.indexOf('evidenceCaptureReplayTrades')>ui.indexOf('alexGReplayStats=result.stats'),
      'capture must run AFTER the replay results are assigned');
    const cap=String(g.evidenceCaptureReplayTrades)+String(g.evidenceCaptureReplayTradesAsync)+
              String(g.evidenceNormalizeReplayTrade);
    ['alexGRunSetupReplay','alexGComputeReplayStats','commitPaperLedger','commitAlexGLedger',
     'paperAccount','alexGAccount','journalEntries'].forEach(function(f){
      eq(cap.indexOf(f),-1,'capture must never reference '+f);
    });
  });

  t('R10 re-running an identical replay is idempotent, not duplicating evidence',function(){
    ok(String(g.evidenceCaptureReplayTradesAsync).indexOf('evidenceHasPackageForTrade')!==-1,
      'already-captured trades must be skipped');
    ok(String(g.evidenceCaptureReplayTradesAsync).indexOf("==='CONSTRAINT'")!==-1,
      'a store-level duplicate must be treated as already-captured, not as a failure');
    // deterministic runId + namespaced id => identical inputs produce identical sourceTradeIds
    const a=g.evidenceNormalizeReplayTrade(replayTrade(),RUN);
    const b=g.evidenceNormalizeReplayTrade(replayTrade(),RUN);
    eq(a.tradeId,b.tradeId,'same run + same trade => same sourceTradeId => unique index blocks a duplicate');
  });

  t('R11 an identity failure degrades the run, it does not break it',function(){
    const src=g.getSource('async function runAlexGReplay(');
    ok(/catch\(e\)\{[\s\S]{0,160}evidenceRecordWriteFailure\('replay-run-identity'/.test(src),
      'identity failure must be recorded');
    ok(src.indexOf('let runIdentity=null')!==-1,'and must default to null rather than throwing');
    ok(src.indexOf('trades,rejected,stats')!==-1,'the run still returns its trades');
    ok(src.indexOf('alexGBuildReplayRunIdentity')>src.indexOf('alexGRunSetupReplay'),
      'identity is computed AFTER the protected engine, so it cannot influence results');
  });

  // ══ GROUP 7 — IMPORT AND RECOVERY ═════════════════════════════════════════════════════
  t('I1 a hash mismatch is REJECTED and never repaired',function(){
    const src=String(g.evidenceImportPackageObject);
    ok(src.indexOf("reason:'HASH_MISMATCH'")!==-1,'a mismatch must be rejected');
    eq(src.indexOf('evidenceFinalizePackage'),-1,'import must NEVER re-hash a package into agreement');
    // An ASSIGNMENT to contentHash (not the === comparison the duplicate check legitimately uses).
    ok(!/\.contentHash\s*=[^=]/.test(src),'import must never rewrite a package hash');
  });
  t('I2 a duplicate packageId with a DIFFERENT hash is rejected, never overwritten',function(){
    const src=String(g.evidenceImportPackageObject);
    ok(src.indexOf("reason:'DUPLICATE_CONFLICTING_HASH'")!==-1);
    // EXP-001: an identical duplicate is no longer a bare no-op -- it is the export verification
    // event. When the hash cannot be checked it degrades to an explicit unverifiable no-op.
    ok(src.indexOf('EXPORT_VERIFIED_BY_REIMPORT')!==-1,'an identical duplicate verifies the export');
    ok(src.indexOf('DUPLICATE_IDENTICAL_UNVERIFIABLE')!==-1,'and degrades honestly when it cannot be verified');
    eq(String(g.evidencePutPackage).indexOf('.put('),-1,'the insert path must use add(), never put()');
  });
  t('I3 an unsupported hash algorithm or schema is rejected',function(){
    const p=builtPackage();
    p.contentHash='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';
    p.contentHashAlgorithm='MD5';
    // The synchronous validator rejects this before any async work is attempted.
    const v=g.evidenceValidatePackage(p);
    no(v.valid,'a hashed package declaring a non-SHA-256 algorithm must be rejected');
    ok(v.errors.join(';').indexOf('contentHashAlgorithm')!==-1,'the rejection must name the algorithm');
    const src=String(g.evidenceImportPackageObject);
    ok(src.indexOf("reason:'UNSUPPORTED_ALGORITHM'")!==-1);
    ok(src.indexOf("reason:'UNSUPPORTED_SCHEMA'")!==-1);
    ok(src.indexOf('NEWER_SCHEMA_READ_ONLY')!==-1,'a newer schema must be read-only, not guessed at');
  });
  t('I4 malformed JSON and unreadable files are rejected without side effects',function(){
    const src=String(g.evidenceImportFile);
    ok(src.indexOf("reason:'MALFORMED_JSON'")!==-1);
    ok(src.indexOf("reason:'READ_FAILED'")!==-1);
  });
  t('I5 import NEVER touches live trading state',function(){
    const src=String(g.evidenceImportPackageObject)+String(g.evidenceImportFile);
    eq(src.indexOf('alexGAccount'),-1,'import must never reference the ALEX account');
    eq(src.indexOf('alexGJournalEntries'),-1,'import must never reference the ALEX journal');
    eq(src.indexOf('paperAccount'),-1,'import must never reference the JVM account');
    eq(src.indexOf('journalEntries'),-1,'import must never reference the JVM journal');
  });
  t('I6 import never advances the tier-(b) sequence counter',function(){
    eq(String(g.evidenceImportPackageObject).indexOf('evidenceAllocateSequence'),-1,
      'a recovered package must not influence the IDs this installation goes on to mint');
  });
  t('I7 unknown fields survive a round-trip and stay inside the hashed content',function(){
    const p=builtPackage();
    p.futureField={a:[1,2,3]};
    const round=JSON.parse(JSON.stringify(p));
    eq(g.evidenceCanonicalize(round),g.evidenceCanonicalize(p),'a JSON round-trip must be canonical-identical');
    ok(g.evidenceCanonicalize(round).indexOf('futureField')!==-1);
  });

  // ══ GROUP 8 — HISTORICAL BACKFILL ═════════════════════════════════════════════════════
  t('F1 backfill is READ-ONLY -- it never writes any existing store',function(){
    const src=String(g.evidenceBackfillFromLocalStorage);
    eq(src.indexOf('localStorage.setItem'),-1,'backfill must not write localStorage');
    eq(src.indexOf('commitAlexGLedger'),-1,'backfill must not commit the ledger');
    eq(src.indexOf('saveAlexG'),-1,'backfill must not save ALEX state');
    ok(src.indexOf('closedPositions')!==-1,'backfill must read the existing closed positions');
  });
  t('F2 backfill mutates no existing record in memory either',function(){
    const acct={balance:10000,openPositions:[],closedPositions:[sampleTrade()]};
    g.setAlexGAccount(acct);
    const before=JSON.stringify(acct);
    g.evidenceBuildPackageFromTrade(acct.closedPositions[0],
      {packageId:'PKG|x|20260720|1',captureBasis:'HISTORICAL_BACKFILL'});
    eq(JSON.stringify(g.getAlexGAccount()),before,'building a package must not modify the source record');
  });
  t('F3 a backfilled package is MINIMAL and says so',function(){
    const p=builtPackage(null,{captureBasis:'HISTORICAL_BACKFILL'});
    eq(p.completenessReport.level,'MINIMAL');
    eq(p.captureBasis,'HISTORICAL_BACKFILL');
    ok(p.completenessReport.missing.some(function(m){ return m.reason==='UNSAFE_TO_RECONSTRUCT'; }),
      'a backfilled gap must be UNSAFE_TO_RECONSTRUCT, not silently absent');
  });
  t('F4 an unstamped historical trade stays honestly unstamped -- nothing is invented',function(){
    const p=g.evidenceBuildPackageFromTrade(
      sampleTrade({strategyProvenance:undefined,ruleVersion:undefined}),
      {packageId:'PKG|x|20260720|1',captureBasis:'HISTORICAL_BACKFILL'});
    eq(p.identity.strategyVersion,'alex_g_sr_v1 (inferred, unstamped)');
    eq(p.identity.strategyVersionProvenance,'DERIVED','an inferred version must never be labelled OBSERVED');
  });
  t('F5 a genuinely stamped trade keeps its real version, marked OBSERVED',function(){
    const p=g.evidenceBuildPackageFromTrade(
      sampleTrade({strategyProvenance:{strategySpecificationVersion:'alex_g_sr_v1_1',implementationVersion:'impl.1'}}),
      {packageId:'PKG|x|20260720|1'});
    eq(p.identity.strategyVersion,'alex_g_sr_v1_1');
    eq(p.identity.strategyVersionProvenance,'OBSERVED');
    eq(p.identity.implementationVersion,'impl.1');
  });
  t('F6 missing fields become explicit nulls -- never a fabricated 0, false or ""',function(){
    const bare={tradeId:'T9',pair:'EUR_USD',strategy:'alex_g_sr_v1'};
    const p=g.evidenceBuildPackageFromTrade(bare,{packageId:'PKG|x|20260720|9',captureBasis:'HISTORICAL_BACKFILL'});
    eq(p.objects.positions[0].entryPrice,null,'an absent entry price must be null, not 0');
    eq(p.objects.outcomes[0].pnl,null,'an absent pnl must be null, not 0');
    eq(p.objects.outcomes[0].ambiguous,null,'an absent flag must be null, not false');
    eq(p.objects.qualifiedSetups.length,0,'no setup evidence must be invented when none exists');
    ok(g.evidenceValidatePackage(p).valid,'a sparse historical package must still be a valid package');
  });

  // ══ GROUP 9 — CAPTURE SEAM AND PROTECTED-PATH SAFETY (ruling C5) ═══════════════════════
  t('P1 alexGCheckLivePositions is confirmed NOT a protected function',function(){
    const protectedList=g.getBaselineAlexFunctions();
    eq(protectedList.indexOf('alexGCheckLivePositions'),-1,'the seam must not be a protected function');
    ok(protectedList.indexOf('alexGCloseLivePosition')!==-1,'the close function IS protected and must stay untouched');
  });
  t('P2 capture is installed AFTER the loop, adjacent to the existing save',function(){
    const fn=String(g.alexGCheckLivePositions);
    const loopEnd=fn.lastIndexOf('}catch(e){}');
    const capture=fn.indexOf('evidenceCaptureClosedTrades');
    const save=fn.indexOf('saveAlexG()');
    ok(capture>loopEnd,'capture must sit after the per-position loop, not inside it');
    ok(capture>save,'capture must follow the existing save');
    ok(capture>fn.lastIndexOf('alexGCloseLivePosition'),'capture must follow every close call');
  });
  t('P3 capture has its OWN try/catch that reports rather than swallowing',function(){
    const fn=String(g.alexGCheckLivePositions);
    ok(/try\{\s*evidenceCaptureClosedTrades\(\);\s*\}catch\(e\)\{[^}]*evidenceRecordWriteFailure/.test(fn),
      'the capture call must be individually wrapped and must record its failure');
  });
  t('P4 the REAL capture call is non-blocking and cannot throw into the trading tick',function(){
    // Genuinely executes the real evidenceCaptureClosedTrades() in a context with NO IndexedDB
    // (this harness has none), which is the harshest realistic failure: the evidence store is
    // completely unavailable. It must still return synchronously, without throwing, and must
    // leave the account untouched.
    g.resetEvidenceRuntime();
    const acct={balance:10000,openPositions:[{tradeId:'OPEN1'}],closedPositions:[sampleTrade()]};
    g.setAlexGAccount(acct);
    const before=JSON.stringify(acct);
    let threw=false,ret;
    try{ ret=g.evidenceCaptureClosedTrades(); }catch(e){ threw=true; }
    no(threw,'the capture call must never throw into alexGCheckLivePositions');
    eq(ret,undefined,'the capture call must not return a value the trading path could block on');
    eq(JSON.stringify(g.getAlexGAccount()),before,'capture must not mutate the account, even while failing');
    ok(String(g.alexGCheckLivePositions).indexOf('try{ evidenceCaptureClosedTrades(); }catch')!==-1,
      'and the shipped seam wraps it in its own try/catch');
  });
  t('P5 the capture path never re-enters the close path or mutates open positions',function(){
    const src=String(g.evidenceCaptureClosedTrades)+String(g.evidenceCaptureClosedTradesAsync)+
              String(g.evidencePersistTradePackage)+String(g.evidenceBuildPackageFromTrade);
    eq(src.indexOf('alexGCloseLivePosition'),-1,'capture must never call the protected close function');
    eq(src.indexOf('openPositions.splice'),-1,'capture must never mutate open positions');
    eq(src.indexOf('commitAlexGLedger'),-1,'capture must never commit the ledger');
    eq(src.indexOf('alexGJournalEntries'),-1,'capture must never touch the journal');
    ok(src.indexOf('closedPositions.slice')!==-1,'capture reads a COPY of already-closed positions');
  });
  t('P6 capture is idempotent per tradeId, enforced by a UNIQUE store index',function(){
    ok(String(g.evidenceCaptureClosedTradesAsync).indexOf('evidenceHasPackageForTrade')!==-1,
      'an already-captured trade must be skipped');
    ok(String(g.evidenceOpenDb).indexOf("createIndex('bySourceTradeId','sourceTradeId',{unique:true})")!==-1,
      'idempotence must be enforced structurally by the store, not only by session memory');
    ok(String(g.evidenceCaptureClosedTradesAsync).indexOf("==='CONSTRAINT'")!==-1,
      'a duplicate rejected by the store must be treated as already-captured, not as a failure');
  });

  // ══ GROUP 10 — STORE CONTRACT (synchronously testable parts) ═══════════════════════════
  t('D1 sequence identifiers come from PERSISTENT IndexedDB state, never process memory',function(){
    const src=String(g.evidenceAllocateSequence);
    ok(src.indexOf("'readwrite'")!==-1,'allocation must be a readwrite transaction');
    ok(src.indexOf('EVIDENCE_STORE_META')!==-1||src.indexOf('meta')!==-1,'allocation must read the persistent meta store');
    ok(src.indexOf('store.get(key)')!==-1,'the counter must be READ from storage');
    ok(src.indexOf('store.put({key,value:next})')!==-1,'the incremented counter must be written back');
    ok(src.indexOf('evidenceTxDone')!==-1,'the allocation transaction must be awaited to completion');
  });
  t('D2 tier-(b) packages are NEVER automatically deleted (ruling C4)',function(){
    const layer=LAYER;
    eq(layer.indexOf('.clear()'),-1,'no evidence code path may clear the package store');
    eq(layer.indexOf('deleteDatabase'),-1,'no evidence code path may drop the database');
    // ── MOGO-013 re-expression, and the change is deliberate rather than convenient. ──
    // This previously asserted `layer.indexOf('.delete(') === -1` -- NO deletion anywhere in the
    // evidence layer. MOGO-013 introduces authorized bounded retention on the OBSERVATIONS store,
    // so a blanket ban is no longer the real policy. The real policy, which is what is asserted
    // now, is narrower where it matters and broader where it counts:
    //
    //   1. a PACKAGE may still never be deleted -- unchanged, and now checked by store rather
    //      than by the mere absence of a substring, so an aliased store handle cannot slip past;
    //   2. the ONLY function permitted to delete anything is the observation-retention function;
    //   3. that function must reference the observations store and must NOT reference the
    //      packages store; and
    //   4. it must write its RETENTION marker BEFORE it deletes -- see BR4.
    //
    // A bare `.delete(` appearing in any other evidence function fails this fixture.
    const deleteFns=[];
    const fnRe=/(?:async\s+)?function\s+(evidence[A-Za-z0-9_]*)\s*\(/g;
    let fm,bounds=[];
    while((fm=fnRe.exec(layer))!==null) bounds.push({name:fm[1],start:fm.index});
    bounds.forEach(function(b,i){
      const end=(i+1<bounds.length)?bounds[i+1].start:layer.length;
      if(layer.slice(b.start,end).indexOf('.delete(')!==-1) deleteFns.push(b.name);
    });
    eq(deleteFns.filter(function(n){ return n!=='evidenceEnforceObservationRetention'; }).length,0,
      'only evidenceEnforceObservationRetention may delete anything (saw: '+deleteFns.join(',')+')');
    const ret=String(g.evidenceEnforceObservationRetention);
    ok(ret.indexOf('EVIDENCE_STORE_OBSERVATIONS')!==-1,'retention must operate on the observations store');
    eq(ret.indexOf('EVIDENCE_STORE_PACKAGES'),-1,'retention must never reference the package store');
    // The only write-back permitted on an existing package is recording an export outcome.
    // Re-expressed for D-2: this previously pinned the literal `existing.export=exportState`, which
    // asserted the wholesale ASSIGNMENT that was itself the defect. The intent -- "no field other
    // than export may be written" -- is now asserted directly and independently of how the value is
    // computed, which makes it strictly stronger than the string it replaced.
    const upd=String(g.evidenceUpdateExportState);
    ok(/existing\.export\s*=/.test(upd),'the export block must be the thing written back');
    const written=(upd.match(/existing\.([A-Za-z_$][A-Za-z0-9_$]*)\s*=/g)||[])
      .map(function(m){ return m.replace(/^existing\./,'').replace(/\s*=$/,''); });
    eq(written.filter(function(f){ return f!=='export'; }).length,0,
      'no field other than export may be written on an existing package (saw: '+written.join(',')+')');
  });

  // ══ GROUP 11 — v12.10.0 UNIT A (CORR-2/3/4/8) ══════════════════════════════════════════
  // Every fixture calls the REAL builder, normalizer, validator and helpers. The governing
  // constraint is that nothing here may retroactively affect a package captured earlier.

  // A package exactly as v12.9.0 produced one: no Unit A keys at all. Used to prove the new
  // validation is opt-in rather than retroactive.
  function preUnitAPackage(){
    const p=builtPackage();
    delete p.identity.strategySpecificationVersion;
    delete p.identity.strategySpecificationVersionProvenance;
    delete p.identity.releaseVersion;
    delete p.identity.releaseVersionProvenance;
    delete p.identity.releaseGatesApplied;
    delete p.identity.releaseGatesAppliedProvenance;
    delete p.objects.qualifiedSetups[0].setupCanonicalName;
    delete p.objects.qualifiedSetups[0].setupAbbreviation;
    p.objects.qualifiedSetups[0].structureRefs.breakCandleRef=null;
    p.objects.qualifiedSetups[0].structureRefs.retestCandleRef=null;
    p.objects.qualifiedSetups[0].structureRefsProvenance={breakCandleRef:'FUTURE_WORK',retestCandleRef:'FUTURE_WORK',penetrationDepth:'FUTURE_WORK'};
    p.objects.outcomes[0].realizedR=null;
    p.objects.outcomes[0].realizedRProvenance='DERIVED_AT_READ_TIME';
    delete p.objects.outcomes[0].realizedRBasis;
    return p;
  }

  // ── CORR-2: specification version vs running release ──
  t('A1 identity carries the specification version AND the release version as separate fields',function(){
    const p=g.evidenceBuildPackageFromTrade(sampleTrade(),
      {packageId:'PKG|x|1',captureBasis:'REPLAY_RUN',strategyId:'alex_g_sr_v1',
       releaseVersion:'alex_g_sr_v1_1',releaseGatesApplied:[]});
    eq(p.identity.strategySpecificationVersion,'alex_g_sr_v1','the specification that classified the trade');
    eq(p.identity.releaseVersion,'alex_g_sr_v1_1','the build it ran inside');
    ok(p.identity.strategySpecificationVersion!==p.identity.releaseVersion,'the two facts must be separable');
  });
  t('A2 strategyVersion is RETAINED unchanged for backward compatibility',function(){
    const p=builtPackage();
    eq(p.identity.strategyVersion,'alex_g_sr_v1','the pre-existing field must not move');
    eq(p.identity.strategyVersion,p.identity.strategySpecificationVersion,'and must agree with the new one');
  });
  t('A3 an EMPTY releaseGatesApplied is an observation; an ABSENT one is UNAVAILABLE',function(){
    const observed=g.evidenceBuildPackageFromTrade(sampleTrade(),
      {packageId:'PKG|x|1',strategyId:'alex_g_sr_v1',releaseGatesApplied:[]});
    ok(Array.isArray(observed.identity.releaseGatesApplied),'an empty list must survive as a list');
    eq(observed.identity.releaseGatesApplied.length,0);
    eq(observed.identity.releaseGatesAppliedProvenance,'OBSERVED','"no gates applied" is a real answer');
    const silent=builtPackage();
    eq(silent.identity.releaseGatesApplied,null,'a caller that says nothing must not be given an empty list');
    eq(silent.identity.releaseGatesAppliedProvenance,'UNAVAILABLE');
  });
  t('A4 an unresolved release version is UNAVAILABLE, never guessed',function(){
    const p=builtPackage();
    eq(p.identity.releaseVersion,null);
    eq(p.identity.releaseVersionProvenance,'UNAVAILABLE');
  });
  t('A5 the replay seam supplies the release identity and an empty gate list',function(){
    const src=String(g.evidenceCaptureReplayTradesAsync);
    ok(src.indexOf('releaseVersion:releaseVersion')!==-1,'the seam must forward the release version');
    ok(src.indexOf('releaseGatesApplied:EVIDENCE_REPLAY_RELEASE_GATES')!==-1,'and the observed gate list');
    eq(g.EVIDENCE_REPLAY_RELEASE_GATES.length,0,'replay consults no release-level gate');
  });
  t('A6 the release identity survives evidencePersistTradePackageResolved',function(){
    const src=String(g.evidencePersistTradePackageResolved);
    ok(src.indexOf('releaseVersion:x.releaseVersion')!==-1,'must be forwarded, not dropped at the persist layer');
    ok(src.indexOf('releaseGatesApplied:x.releaseGatesApplied')!==-1);
  });

  // ── CORR-3: realized R from the actual exit ──
  t('A7 realizedR is computed from the exit for a winner',function(){
    const p=builtPackage();               // entry 1.1000 stop 1.0950 exit 1.1100 buy
    eq(p.objects.outcomes[0].realizedR,2,'(1.1100-1.1000)/0.0050 = 2R');
    eq(p.objects.outcomes[0].realizedRProvenance,'OBSERVED_FROM_EXIT');
  });
  t('A8 realizedR is computed from the exit for a loser',function(){
    const p=builtPackage({exitPrice:1.0950,result:'Loss',resultR:-1});
    eq(p.objects.outcomes[0].realizedR,-1,'a stop-out is exactly -1R');
  });
  t('A9 realizedR respects direction -- a short that falls is a WIN',function(){
    const p=builtPackage({direction:'sell',entry:1.1000,stop:1.1050,exitPrice:1.0900,result:'Win'});
    eq(p.objects.outcomes[0].realizedR,2,'(1.1000-1.0900)/0.0050 = 2R for a sell');
  });
  t('A10 realizedR is NEVER sourced from recordedResultR',function(){
    // recordedResultR is deliberately contradicted by the prices; realizedR must follow the PRICES.
    const p=builtPackage({resultR:99});
    eq(p.objects.outcomes[0].recordedResultR,99,'the engine-recorded value is preserved verbatim');
    eq(p.objects.outcomes[0].realizedR,2,'the observed value must come from the exit, not the record');
    ok(String(g.evidenceComputeRealizedR).indexOf('resultR')===-1,'the helper must not read resultR at all');
  });
  t('A11 realizedR is UNAVAILABLE -- not zero, not recordedResultR -- when inputs are missing',function(){
    const p=builtPackage({exitPrice:null});
    eq(p.objects.outcomes[0].realizedR,null);
    eq(p.objects.outcomes[0].realizedRProvenance,'UNAVAILABLE');
    const r=g.evidenceComputeRealizedR({entry:1.1,exitPrice:1.2,direction:'buy',riskDistance:0});
    eq(r.realizedR,null,'a zero risk distance must not divide');
    eq(r.provenance,'UNAVAILABLE');
  });
  t('A12 realizedRBasis records the inputs, so the number is checkable',function(){
    const b=builtPackage().objects.outcomes[0].realizedRBasis;
    ok(b&&typeof b==='object','the basis must be present');
    eq(b.entryPrice,1.1000); eq(b.exitPrice,1.1100); eq(b.direction,'buy');
    ok(Math.abs(b.riskDistance-0.0050)<1e-12,'risk distance must be the observed one');
    const recomputed=Math.round((((b.exitPrice-b.entryPrice)*1)/b.riskDistance)*1e6)/1e6;
    eq(recomputed,2,'the stored basis must independently reproduce the stored realizedR');
  });
  t('A13 the engine-recorded riskDistance is preferred over re-derived prices',function(){
    const r=g.evidenceComputeRealizedR({entry:1.1,exitPrice:1.11,direction:'buy',riskDistance:0.005,stop:1.0});
    eq(r.basis.riskDistanceSource,'riskDistance');
    eq(r.realizedR,2,'the recorded distance, not |entry-stop|, must govern');
    const f=g.evidenceComputeRealizedR({entry:1.1,exitPrice:1.11,direction:'buy',stop:1.095});
    eq(f.basis.riskDistanceSource,'abs(entry-stop)','and the fallback is honestly labelled');
  });
  t('A14 realizedRProvenance is restricted to the declared vocabulary',function(){
    ok(g.EVIDENCE_REALIZED_R_PROVENANCE.indexOf('OBSERVED_FROM_EXIT')!==-1);
    const p=builtPackage();
    p.objects.outcomes[0].realizedRProvenance='TOTALLY_MADE_UP';
    no(g.evidenceValidatePackage(p).valid,'an undeclared provenance must fail validation');
  });

  // ── CORR-4: break and retest candle references ──
  t('A15 candle refs come from the SETUP RECORD and are marked OBSERVED',function(){
    const setup={setupId:'AGS|x',brokenAtBar:100,brokenAt:1775000000000,qualificationBarIndex:114};
    const norm=g.evidenceNormalizeReplayTrade(
      {tradeId:'AGT|1',setupId:'AGS|x',setupType:'B_breakRetest',result:'Loss',timeframe:'H1',
       entry:1.1,stop:1.105,exitPrice:1.105,direction:'sell',entryTimestamp:1775004000000},
      {runId:'r'.repeat(64),strategyId:'alex_g_sr_v1'},setup);
    eq(norm.brokenAtBar,100,'copied verbatim from the setup record');
    eq(norm.qualificationBarIndex,114);
    const p=g.evidenceBuildPackageFromTrade(norm,{packageId:'PKG|x|1',strategyId:'alex_g_sr_v1',captureBasis:'REPLAY_RUN'});
    const s=p.objects.qualifiedSetups[0];
    eq(s.structureRefs.breakCandleRef.barIndex,100);
    eq(s.structureRefs.breakCandleRef.timestampUTC,new Date(1775000000000).toISOString());
    eq(s.structureRefs.breakCandleRef.timeframe,'H1');
    eq(s.structureRefsProvenance.breakCandleRef,'OBSERVED','recorded by the engine, not computed here');
    eq(s.structureRefsProvenance.retestCandleRef,'OBSERVED');
  });
  t('A16 a Repeated Zone Reaction has NO break cycle -- NOT_APPLICABLE, never UNAVAILABLE',function(){
    const p=builtPackage({setupType:'A_repeatedReaction',setupLabel:'REPEATED ZONE REACTION'});
    const s=p.objects.qualifiedSetups[0];
    eq(s.structureRefs.breakCandleRef,null);
    eq(s.structureRefsProvenance.breakCandleRef,'NOT_APPLICABLE','nothing was lost; there is nothing to record');
    ok(g.EVIDENCE_FIELD_PROVENANCE.indexOf('NOT_APPLICABLE')!==-1,'the token must be declared');
  });
  t('A17 without a setup record the refs stay UNAVAILABLE -- nothing is invented',function(){
    const norm=g.evidenceNormalizeReplayTrade(
      {tradeId:'AGT|1',setupId:'AGS|x',setupType:'B_breakRetest',result:'Loss',timeframe:'H1'},
      {runId:'r'.repeat(64),strategyId:'alex_g_sr_v1'});      // no setup passed
    eq(norm.brokenAtBar,null);
    const p=g.evidenceBuildPackageFromTrade(norm,{packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'});
    eq(p.objects.qualifiedSetups[0].structureRefs.breakCandleRef,null);
    eq(p.objects.qualifiedSetups[0].structureRefsProvenance.breakCandleRef,'UNAVAILABLE');
  });
  t('A18 penetrationDepth remains honestly FUTURE_WORK',function(){
    eq(builtPackage().objects.qualifiedSetups[0].structureRefsProvenance.penetrationDepth,'FUTURE_WORK');
  });
  t('A19 the seam passes setups READ-ONLY and replay still returns its own results',function(){
    const ui=String(g.runAlexGReplayUI);
    // v12.12.0 Unit C1 widened this call with the read-only candle arrays. The assertion keeps its
    // strength: the setup records must still reach the seam.
    ok(ui.indexOf('evidenceCaptureReplayTrades(result.runIdentity,result.trades,result.setups,result.candlesByTimeframe)')!==-1,
       'the seam must receive the setup records');
    ok(ui.indexOf('try{ evidenceCaptureReplayTrades')!==-1,'and must remain inside its own try/catch');
    ok(String(g.runAlexGReplay).indexOf('setups:setupsForPair')!==-1,'replay must return the records it already built');
    const seam=String(g.evidenceCaptureReplayTradesAsync);
    eq(seam.indexOf('setups[s].setupId=null'),-1,'the seam must never write to a setup record');
    ok(seam.indexOf('setupById[String(rec.setupId)]=rec')!==-1,'it may only index them');
  });

  // ── CORR-8: canonical naming ──
  t('A20 one canonical name per category, and the RZR alias is recorded as deprecated',function(){
    eq(g.alexGSetupTypeCanonicalName('A_repeatedReaction'),'Repeated Zone Reaction');
    eq(g.alexGSetupTypeCanonicalName('B_breakRetest'),'Break & Retest');
    eq(g.alexGSetupTypeAbbreviation('A_repeatedReaction'),'RZR');
    eq(g.alexGSetupTypeCanonicalName('something_else'),null,'an unknown type must not be given a name');
    ok(g.ALEX_SETUP_CANONICAL_NAMES.A_repeatedReaction.deprecatedAliases.indexOf('Repeated Reaction')!==-1,
       'the alias that caused the 2026-08-03 confusion must be recorded as deprecated');
  });
  t('A21 canonical naming does NOT alter classification, stored labels or stats grouping',function(){
    const p=builtPackage({setupType:'A_repeatedReaction',setupLabel:'REPEATED ZONE REACTION'});
    const s=p.objects.qualifiedSetups[0];
    eq(s.setupType,'A_repeatedReaction','the protected engine\'s value must be untouched');
    eq(s.setupLabel,'REPEATED ZONE REACTION','the stored display label must be untouched');
    eq(s.setupCanonicalName,'Repeated Zone Reaction','the canonical name is ADDITIVE');
    // alexGComputeReplayStats is PROTECTED and groups by setupLabel -- prove the key is unchanged.
    ok(String(g.alexGComputeReplayStats).indexOf('bySetupType:byGroup(t=>t.setupLabel)')!==-1,
       'stats grouping must still key on the untouched setupLabel');
  });

  // ── Backward compatibility: the existing verified packages must be unaffected ──
  t('A22 a pre-v12.10.0 package still validates, canonicalizes and keeps its hash',function(){
    const old=preUnitAPackage();
    const before=g.evidenceCanonicalize(old);
    const v=g.evidenceValidatePackage(old);
    ok(v.valid,'a package captured before Unit A must still validate: '+v.errors.join('; '));
    eq(g.evidenceCanonicalize(old),before,'canonicalization must be byte-identical for it');
    eq(old.packageSchemaVersion,g.EVIDENCE_PACKAGE_SCHEMA_VERSION,'the schema version must NOT have been bumped');
    // The new keys must be optional, not required.
    ok(!('releaseVersion' in old.identity),'the fixture really is missing the new keys');
    const withNulls=preUnitAPackage(); withNulls.identity.releaseGatesApplied=null;
    ok(g.evidenceValidatePackage(withNulls).valid,'an explicit null must also validate');
    const bad=preUnitAPackage(); bad.identity.releaseGatesApplied='ALEX_V11_001';
    no(g.evidenceValidatePackage(bad).valid,'but a wrongly-typed value must still be caught');
  });

  // ══ GROUP 12 — v12.11.0 UNIT B (CORR-1) RULE ATTRIBUTION ═══════════════════════════════
  // The differential fixtures are the anti-drift mechanism: they drive the mirror and the REAL
  // protected evaluators from the same objects and assert the mirror never contradicts them.

  // A zone/touch pair that genuinely qualifies as B_breakRetest under the protected evaluator.
  function brZone(over){
    const z={id:'AGZ|z1',status:'broken',brokenAtBar:40,brokenAt:1752990000000,
      brokenDirection:'downThroughSupport',touches:[{},{},{},{},{}],low:1.094,high:1.096,center:1.095};
    if(over) Object.keys(over).forEach(function(k){ z[k]=over[k]; });
    return z;
  }
  function brTouch(over){
    const t={reactionId:'AGR|r1',swingType:'high',fromSide:'below',price:1.0955};
    if(over) Object.keys(over).forEach(function(k){ t[k]=over[k]; });
    return t;
  }
  function rzrZone(over){
    const z={id:'AGZ|z2',status:'validated',brokenAtBar:null,brokenAt:null,brokenDirection:null,
      touches:[{},{},{},{}],low:1.094,high:1.096,center:1.095};
    if(over) Object.keys(over).forEach(function(k){ z[k]=over[k]; });
    return z;
  }
  const CFG={maxBarsBetweenBreakAndRetest:50};

  // Runs BOTH the protected evaluator and the mirror from the same inputs and returns both
  // verdicts. alexGSetupState is emptied so the evaluator's own alreadyUsed check is false, and
  // the mirror is told the matching break-cycle count, so the comparison is like-for-like.
  function differential(zone,touch,touchIndex,idx,quality,setupType,cycleCount){
    const prior=g.getAlexGSetupState();
    g.setAlexGSetupState([]);
    let engine;
    try{
      // When the case says this break cycle already produced a setup, the ENGINE must be put in
      // that same state -- otherwise the comparison would be against an engine that never saw the
      // earlier setup, and the "disagreement" would be the fixture's fault, not the mirror's.
      if(setupType==='B_breakRetest'&&typeof cycleCount==='number'&&cycleCount>1){
        const probe=g.alexGEvaluateBreakRetest(zone,touch,touchIndex,idx,CFG);
        const priorSetups=[];
        for(let i=1;i<cycleCount;i++) priorSetups.push({zoneId:zone.id,setupType:'B_breakRetest',breakCycleId:probe.breakCycleId});
        g.setAlexGSetupState(priorSetups);
      }
      engine=(setupType==='B_breakRetest')
        ? g.alexGEvaluateBreakRetest(zone,touch,touchIndex,idx,CFG).qualifies
        : g.alexGEvaluateRepeatedReaction(zone,touch,touchIndex,quality,CFG).qualifies;
    } finally { g.setAlexGSetupState(prior); }
    const rec=g.alexGAttributionRecordFromEngineInputs(zone,touch,touchIndex,idx,quality);
    const mirror=g.alexGBuildRuleAttribution(rec,setupType,CFG,
      {breakCycleSetupCount:(typeof cycleCount==='number'?cycleCount:1)});
    return{engine,mirror,rec};
  }
  function assertNoContradiction(d,label){
    if(d.engine===true&&d.mirror.verdict==='CONTRADICTS_RECORDED_CLASSIFICATION')
      throw new Error(label+': the evaluator QUALIFIED this setup but the mirror contradicted it ('+
        d.mirror.attribution.failedConditionIds.join(',')+')');
    if(d.engine===false&&d.mirror.verdict==='AGREES_WITH_RECORDED_CLASSIFICATION')
      throw new Error(label+': the evaluator REFUSED this setup but the mirror found every condition satisfied');
  }

  t('B1 DIFFERENTIAL -- a qualifying Break & Retest: evaluator and mirror agree exactly',function(){
    const d=differential(brZone(),brTouch(),3,45,'clean','B_breakRetest',1);
    eq(d.engine,true,'the protected evaluator must qualify this setup');
    eq(d.mirror.verdict,'AGREES_WITH_RECORDED_CLASSIFICATION');
    eq(d.mirror.attribution.unverifiedConditionCount,0,'every condition must be knowable here');
    assertNoContradiction(d,'B1');
  });
  t('B2 DIFFERENTIAL -- a qualifying Repeated Zone Reaction: evaluator and mirror agree exactly',function(){
    const d=differential(rzrZone(),brTouch({swingType:'low',fromSide:'above'}),3,60,'clean','A_repeatedReaction');
    eq(d.engine,true);
    eq(d.mirror.verdict,'AGREES_WITH_RECORDED_CLASSIFICATION');
    assertNoContradiction(d,'B2');
  });
  t('B3 DIFFERENTIAL -- every Break & Retest condition falsified in turn',function(){
    const cases=[
      ['touch index too low',      brZone(),                              brTouch(),3-1,45,1,'ALEX_SR_V1_TOUCH_INDEX_MIN'],
      ['zone not broken',          brZone({status:'validated'}),          brTouch(),3,45,1,'ALEX_SR_V1_B_ZONE_STATUS_BROKEN'],
      ['no break recorded',        brZone({brokenAtBar:null,brokenAt:null}),brTouch(),3,45,1,'ALEX_SR_V1_B_BREAK_RECORDED'],
      ['retest on the break bar',  brZone(),                              brTouch(),3,40,1,'ALEX_SR_V1_B_RETEST_STRICTLY_AFTER_BREAK'],
      ['retest too far after',     brZone(),                              brTouch(),3,140,1,'ALEX_SR_V1_B_RETEST_WITHIN_MAX_BARS'],
      ['wrong reaction side',      brZone(),                              brTouch({fromSide:'above'}),3,45,1,'ALEX_SR_V1_B_REACTION_SIDE_MATCHES_BREAK'],
      ['wrong swing type',         brZone(),                              brTouch({swingType:'low'}),3,45,1,'ALEX_SR_V1_B_REACTION_SIDE_MATCHES_BREAK'],
      ['break cycle already used', brZone(),                              brTouch(),3,45,2,'ALEX_SR_V1_B_FIRST_RETEST_IN_BREAK_CYCLE']
    ];
    cases.forEach(function(c){
      const d=differential(c[1],c[2],c[3],c[4],'clean','B_breakRetest',c[5]);
      assertNoContradiction(d,'B3/'+c[0]);
      // The engine refuses every one of these (the break-cycle case is refused by the mirror only,
      // because the evaluator's own alreadyUsed check is state-dependent and was cleared).
      eq(d.engine,false,c[0]+': the evaluator must refuse');
      ok(d.mirror.verdict!=='AGREES_WITH_RECORDED_CLASSIFICATION',
         c[0]+': the mirror must never endorse a setup the evaluator refused');
      // The named condition must be either FAILED or explicitly UNVERIFIABLE. The one honest gap
      // is "no break recorded": a record whose break fields are all null cannot distinguish "the
      // zone was never broken" from "this capture path did not carry the break fields", so the
      // mirror says INDETERMINATE rather than inventing a verdict.
      const named=d.mirror.triggeredConditions.filter(function(x){return x.conditionId===c[6];})[0];
      ok(named,c[0]+': condition '+c[6]+' must be present');
      ok(named.satisfied===false||named.satisfied===null,
         c[0]+': expected '+c[6]+' to fail or be unverifiable, got satisfied='+named.satisfied);
      if(c[6]!=='ALEX_SR_V1_B_BREAK_RECORDED'){
        eq(d.mirror.verdict,'CONTRADICTS_RECORDED_CLASSIFICATION',c[0]+': the mirror must identify a definite failure');
        ok(d.mirror.attribution.failedConditionIds.indexOf(c[6])!==-1,
           c[0]+': expected '+c[6]+', got '+d.mirror.attribution.failedConditionIds.join(','));
      }
    });
  });
  t('B4 DIFFERENTIAL -- every Repeated Zone Reaction condition falsified in turn',function(){
    const cases=[
      ['already-broken zone', rzrZone({status:'broken'}),  3,'clean', 'ALEX_SR_V1_A_ZONE_STATUS_VALIDATED'],
      ['touch index too low', rzrZone(),                   2,'clean', 'ALEX_SR_V1_TOUCH_INDEX_MIN'],
      ['too few zone touches',rzrZone({touches:[{},{},{}]}),3,'clean','ALEX_SR_V1_A_ZONE_TOUCH_COUNT_MIN'],
      ['choppy zone',         rzrZone(),                   3,'choppy','ALEX_SR_V1_A_ZONE_QUALITY_NOT_CHOPPY']
    ];
    cases.forEach(function(c){
      const d=differential(c[1],brTouch({swingType:'low',fromSide:'above'}),c[2],60,c[3],'A_repeatedReaction');
      eq(d.engine,false,c[0]+': the evaluator must refuse');
      assertNoContradiction(d,'B4/'+c[0]);
      eq(d.mirror.verdict,'CONTRADICTS_RECORDED_CLASSIFICATION',c[0]);
      ok(d.mirror.attribution.failedConditionIds.indexOf(c[4])!==-1,
         c[0]+': expected '+c[4]+', got '+d.mirror.attribution.failedConditionIds.join(','));
    });
  });
  t('B5 DIFFERENTIAL -- precedence: a zone that could satisfy BOTH is attributed to the stored type',function(){
    // A broken zone with 4+ touches: Break & Retest qualifies, so alexGClassifyTouch never reaches
    // the RZR branch -- and the RZR evaluator itself refuses a broken zone. Both must hold.
    const z=brZone(),tc=brTouch();
    const b=differential(z,tc,3,45,'clean','B_breakRetest',1);
    const a=differential(z,tc,3,45,'clean','A_repeatedReaction');
    eq(b.engine,true,'Break & Retest must qualify');
    eq(a.engine,false,'Repeated Zone Reaction must refuse the same broken zone');
    eq(b.mirror.verdict,'AGREES_WITH_RECORDED_CLASSIFICATION');
    eq(a.mirror.verdict,'CONTRADICTS_RECORDED_CLASSIFICATION','the mirror must not endorse the branch the engine refused');
    eq(b.mirror.attribution.repeatedReactionEvaluated,false,'a stored B&R means the RZR branch was never reached');
    eq(a.mirror.attribution.precedenceApplied,'B_BREAK_RETEST_EVALUATED_BEFORE_A_REPEATED_ZONE_REACTION');
  });
  t('B6 DIFFERENTIAL -- a sweep over touch index and bars-since-break never contradicts',function(){
    let checked=0;
    for(let ti=1;ti<=5;ti++){
      for(let bars=0;bars<=60;bars+=10){
        const d=differential(brZone(),brTouch(),ti,40+bars,'clean','B_breakRetest',1);
        assertNoContradiction(d,'B6/ti='+ti+',bars='+bars);
        // Where every condition is knowable the two verdicts must be equivalent.
        if(d.mirror.attribution.unverifiedConditionCount===0){
          eq(d.mirror.verdict==='AGREES_WITH_RECORDED_CLASSIFICATION',d.engine,
             'ti='+ti+',bars='+bars+': verdicts must match when nothing is unverifiable');
        }
        checked++;
      }
    }
    ok(checked>=35,'the sweep must actually cover the matrix, covered '+checked);
  });
  t('B7 the record view is the SAME copy alexGCreateSetupRecord performs',function(){
    const src=String(g.alexGCreateSetupRecord),rec=g.alexGAttributionRecordFromEngineInputs(brZone(),brTouch(),3,45,'clean');
    eq(rec.zoneStatusAtQualification,'broken'); eq(rec.zoneTouchNumber,4);
    eq(rec.barsSinceBreak,5); eq(rec.reactionSwingType,'high'); eq(rec.reactionFromSide,'below');
    // Each mapping below is the literal one in the protected creator -- proven against its source.
    ok(src.indexOf('zoneStatusAtQualification:zone.status')!==-1);
    ok(src.indexOf('zoneTouchNumber:touchIndex+1')!==-1);
    ok(src.indexOf('barsSinceBreak:zone.brokenAtBar!=null?idx-zone.brokenAtBar:null')!==-1);
    ok(src.indexOf('reactionFromSide:touch.fromSide,reactionSwingType:touch.swingType')!==-1);
  });
  t('B8 attribution CANNOT influence the evaluators or classification',function(){
    // The protected functions must not reference the attribution layer at all.
    [String(g.alexGEvaluateBreakRetest),String(g.alexGEvaluateRepeatedReaction),
     String(g.alexGClassifyTouch),String(g.alexGCreateSetupRecord),String(g.alexGConstructTrade)]
      .forEach(function(src){
        ['alexGBuildRuleAttribution','ALEX_ATTRIBUTION_CONDITIONS','ruleAttribution',
         'triggeredConditions','alexGAttributionRecordFromEngineInputs'].forEach(function(name){
          eq(src.indexOf(name),-1,'protected code must never reference '+name);
        });
      });
    // And the mirror must not write to anything.
    const m=String(g.alexGBuildRuleAttribution)+String(g.alexGAttributionRecordFromEngineInputs);
    ['alexGSetupState=','alexGZoneState=','alexGAccount','journalEntries','paperAccount',
     'localStorage','commitAlexGLedger'].forEach(function(n){
      eq(m.indexOf(n),-1,'the mirror must never touch '+n);
    });
  });
  t('B9 running the mirror leaves engine state and evaluator output unchanged',function(){
    const z=brZone(),tc=brTouch();
    const before=g.alexGEvaluateBreakRetest(z,tc,3,45,CFG);
    const zBefore=JSON.stringify(z),tBefore=JSON.stringify(tc);
    g.alexGBuildRuleAttribution(g.alexGAttributionRecordFromEngineInputs(z,tc,3,45,'clean'),'B_breakRetest',CFG,{breakCycleSetupCount:1});
    const after=g.alexGEvaluateBreakRetest(z,tc,3,45,CFG);
    eq(after.qualifies,before.qualifies,'the evaluator must return the same answer after attribution ran');
    eq(JSON.stringify(z),zBefore,'the zone must not be mutated');
    eq(JSON.stringify(tc),tBefore,'the touch must not be mutated');
  });
  t('B10 a contradiction FAILS capture safely -- no package is produced',function(){
    // zoneTouchNumber 2 could never have produced a setup; the builder must refuse to write one.
    throws(function(){
      g.evidenceBuildPackageFromTrade(sampleTrade({zoneTouchNumber:2}),
        {packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'});
    },'a contradicted classification must throw rather than emit wrong attribution');
    let msg='';
    try{ g.evidenceBuildPackageFromTrade(sampleTrade({zoneTouchNumber:2}),{packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'}); }
    catch(e){ msg=e.message; }
    ok(msg.indexOf('EVIDENCE_RULE_ATTRIBUTION_MISMATCH')===0,'the failure must be named, not generic: '+msg);
    ok(msg.indexOf('ALEX_SR_V1_TOUCH_INDEX_MIN')!==-1,'and must name the failed condition');
  });
  t('B11 a package asserting a contradiction is rejected by validation',function(){
    const p=builtPackage();
    p.objects.qualifiedSetups[0].ruleAttribution.contradictsEngineClassification=true;
    no(g.evidenceValidatePackage(p).valid,'a stored contradiction must never validate');
  });
  t('B12 ruleIds are stable, canonical and deterministically ordered',function(){
    const rec=g.alexGAttributionRecordFromEngineInputs(brZone(),brTouch(),3,45,'clean');
    const a=g.alexGBuildRuleAttribution(rec,'B_breakRetest',CFG,{breakCycleSetupCount:1});
    eq(a.ruleIds.join('|'),'ALEX_SR_V1_CLASSIFY_PRECEDENCE|ALEX_SR_V1_SETUP_B_BREAK_RETEST',
       'exact canonical order, sorted lexicographically');
    const sorted=a.ruleIds.slice().sort();
    eq(a.ruleIds.join('|'),sorted.join('|'),'order must not depend on declaration order');
    const rzr=g.alexGBuildRuleAttribution(
      g.alexGAttributionRecordFromEngineInputs(rzrZone(),brTouch(),3,60,'clean'),'A_repeatedReaction',CFG,{});
    eq(rzr.ruleIds.join('|'),'ALEX_SR_V1_CLASSIFY_PRECEDENCE|ALEX_SR_V1_SETUP_A_REPEATED_ZONE_REACTION');
  });
  t('B13 rule and condition IDs are semantic -- never labels, positions or generated text',function(){
    const all=[];
    g.getAttributionConditions().forEach(function(c){ all.push(c.conditionId); all.push(c.ruleId); });
    Object.keys(g.ALEX_ATTRIBUTION_RULE_IDS).forEach(function(k){ all.push(g.ALEX_ATTRIBUTION_RULE_IDS[k]); });
    all.forEach(function(id){
      ok(/^ALEX_SR_V1_[A-Z0-9_]+$/.test(id),'not a stable semantic identifier: '+id);
      eq(id.indexOf('BREAK & RETEST'),-1,'must not embed display text');
      eq(id.indexOf('REPEATED ZONE REACTION'),-1,'must not embed display text');
      no(/[0-9]+$/.test(id.replace('ALEX_SR_V1_','')),'must not end in a positional index: '+id);
    });
    // Every condition must point at a declared rule.
    const declared=Object.keys(g.ALEX_ATTRIBUTION_RULE_IDS).map(function(k){return g.ALEX_ATTRIBUTION_RULE_IDS[k];});
    g.getAttributionConditions().forEach(function(c){
      ok(declared.indexOf(c.ruleId)!==-1,c.conditionId+' points at an undeclared rule');
    });
  });
  t('B14 triggeredConditions are complete, structured and deterministic',function(){
    const rec=g.alexGAttributionRecordFromEngineInputs(brZone(),brTouch(),3,45,'clean');
    const a=g.alexGBuildRuleAttribution(rec,'B_breakRetest',CFG,{breakCycleSetupCount:1});
    eq(a.triggeredConditions.length,7,'precedence + six Break & Retest conditions');
    a.triggeredConditions.forEach(function(c){
      ok(typeof c.conditionId==='string'&&c.conditionId.length>0);
      ok(typeof c.ruleId==='string'&&c.ruleId.length>0);
      ok(typeof c.requirement==='string'&&c.requirement.length>0,'each condition must state its requirement');
      ok(c.observed!==undefined&&c.observed!==null,'each condition must record the observed values');
      ok(c.satisfied===true||c.satisfied===false||c.satisfied===null);
      ok(g.EVIDENCE_FIELD_PROVENANCE.indexOf(c.provenance)!==-1,'invalid provenance '+c.provenance);
    });
    const b=g.alexGBuildRuleAttribution(rec,'B_breakRetest',CFG,{breakCycleSetupCount:1});
    eq(JSON.stringify(a),JSON.stringify(b),'identical inputs must produce identical attribution');
    const order=a.triggeredConditions.map(function(c){return c.conditionId;}).join('|');
    eq(order,'ALEX_SR_V1_TOUCH_INDEX_MIN|ALEX_SR_V1_B_ZONE_STATUS_BROKEN|ALEX_SR_V1_B_BREAK_RECORDED|'+
             'ALEX_SR_V1_B_RETEST_STRICTLY_AFTER_BREAK|ALEX_SR_V1_B_RETEST_WITHIN_MAX_BARS|'+
             'ALEX_SR_V1_B_REACTION_SIDE_MATCHES_BREAK|ALEX_SR_V1_B_FIRST_RETEST_IN_BREAK_CYCLE',
       'conditions must appear in the engine\'s own check order');
  });
  t('B14b a record carrying barsSinceBreak but not the raw break fields is NOT a contradiction',function(){
    // This is the shape of every package captured before v12.10.0, and of any capture path not
    // given the setup record. Treating it as a contradiction would fail capture for correctly
    // classified trades -- found by dry-running the mirror over the real RUN-001 packages.
    const a=g.alexGBuildRuleAttribution({zoneTouchNumber:4,zoneStatusAtQualification:'broken',
      barsSinceBreak:14,brokenDirection:'downThroughSupport',brokenAtBar:null,brokenAt:null},
      'B_breakRetest',CFG,{breakCycleSetupCount:1});
    ok(a.verdict!=='CONTRADICTS_RECORDED_CLASSIFICATION','must not contradict: '+a.attribution.failedConditionIds.join(','));
    const c=a.triggeredConditions.filter(function(x){return x.conditionId==='ALEX_SR_V1_B_BREAK_RECORDED';})[0];
    eq(c.satisfied,true);
    eq(c.provenance,'DERIVED_FROM_OBSERVED_FIELDS','an implication must not be labelled OBSERVED');
    // And a package built from such a trade must still be produced.
    const p=g.evidenceBuildPackageFromTrade(sampleTrade({barsSinceBreak:14,zoneStatusAtQualification:'broken',
      brokenDirection:'downThroughSupport',reactionSwingType:'high',reactionFromSide:'below'}),
      {packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'});
    ok(p&&p.objects.qualifiedSetups[0].ruleIds.length>0,'capture must succeed for this shape');
  });
  t('B15 OBSERVED and DERIVED_FROM_OBSERVED_FIELDS are kept distinct',function(){
    const rzr=g.alexGBuildRuleAttribution(
      {zoneStatusAtQualification:'validated',zoneTouchNumber:4,zoneQualityAtQualification:'clean'},
      'A_repeatedReaction',CFG,{});
    const touchCount=rzr.triggeredConditions.filter(function(c){return c.conditionId==='ALEX_SR_V1_A_ZONE_TOUCH_COUNT_MIN';})[0];
    eq(touchCount.provenance,'DERIVED_FROM_OBSERVED_FIELDS','no record stores zone.touches.length');
    const status=rzr.triggeredConditions.filter(function(c){return c.conditionId==='ALEX_SR_V1_A_ZONE_STATUS_VALIDATED';})[0];
    eq(status.provenance,'OBSERVED','a stored field is OBSERVED');
    // With the real count available it becomes a genuine observation.
    const withCount=g.alexGBuildRuleAttribution(
      g.alexGAttributionRecordFromEngineInputs(rzrZone(),brTouch(),3,60,'clean'),'A_repeatedReaction',CFG,{});
    eq(withCount.triggeredConditions.filter(function(c){return c.conditionId==='ALEX_SR_V1_A_ZONE_TOUCH_COUNT_MIN';})[0].provenance,'OBSERVED');
    ok(g.EVIDENCE_FIELD_PROVENANCE.indexOf('DERIVED_FROM_OBSERVED_FIELDS')!==-1,'the token must be declared');
  });
  t('B16 an unverifiable condition is INDETERMINATE, never assumed',function(){
    const a=g.alexGBuildRuleAttribution({zoneTouchNumber:4,zoneStatusAtQualification:'broken',
      brokenAtBar:40,brokenAt:1,barsSinceBreak:5,reactionSwingType:'high',reactionFromSide:'below',
      brokenDirection:'downThroughSupport'},'B_breakRetest',CFG,{});   // no break-cycle count
    eq(a.verdict,'INDETERMINATE');
    eq(a.attribution.unverifiedConditionCount,1);
    const c=a.triggeredConditions.filter(function(x){return x.conditionId==='ALEX_SR_V1_B_FIRST_RETEST_IN_BREAK_CYCLE';})[0];
    eq(c.satisfied,null,'unknown must be null, never an optimistic true');
    eq(c.provenance,'UNAVAILABLE');
  });
  t('B17 a non-ALEX setup gets NOT_APPLICABLE attribution rather than invented rules',function(){
    const a=g.alexGBuildRuleAttribution({},'current_strategy',null,{});
    eq(a.verdict,'NOT_APPLICABLE'); eq(a.ruleIds.length,0); eq(a.triggeredConditions.length,0);
    eq(a.attribution.provenance,'NOT_APPLICABLE');
    const jvm=g.evidenceBuildPackageFromTrade(
      g.evidenceNormalizeJvmTrade({id:7,oPair:'EUR_USD',dir:'long',entry:1.1,stop:1.09,result:'Win'}),
      {packageId:'PKG|current_strategy|20260720|1',strategyId:g.getJvmStrategyId()});
    eq(jvm.objects.qualifiedSetups.length,0,'a JVM trade has no qualified setup to attribute');
  });
  t('B18 the seam counts break-cycle setups read-only and passes them through',function(){
    const seam=String(g.evidenceCaptureReplayTradesAsync);
    ok(seam.indexOf("rec.setupType==='B_breakRetest'&&rec.breakCycleId!=null")!==-1,'the tally must be scoped to B&R cycles');
    // v12.12.0 Unit C1 appended the excursion argument; the cycle count must still be threaded.
    ok(seam.indexOf('evidenceNormalizeReplayTrade(t,run,setup,cycleCount,excursion,marketContext)')!==-1,'and be passed to the normalizer');
    const norm=g.evidenceNormalizeReplayTrade(
      {tradeId:'AGT|1',setupId:'AGS|1',setupType:'B_breakRetest',result:'Loss',timeframe:'H1'},
      {runId:'r'.repeat(64),strategyId:'alex_g_sr_v1'},
      {setupId:'AGS|1',reactionFromSide:'below',reactionSwingType:'high'},1);
    eq(norm.reactionFromSide,'below'); eq(norm.reactionSwingType,'high'); eq(norm.breakCycleSetupCount,1);
  });
  t('B19 a captured package carries complete attribution and stays deterministic',function(){
    const trade=sampleTrade({zoneStatusAtQualification:'broken',brokenDirection:'downThroughSupport',
      brokenAtBar:40,brokenAt:1752990000000,barsSinceBreak:5,qualificationBarIndex:45,
      reactionSwingType:'high',reactionFromSide:'below',breakCycleSetupCount:1,
      configurationSnapshot:{ruleVersion:'alex_g_sr_v1',config:CFG}});
    const opts={packageId:'PKG|alex_g_sr_v1|20260720|1',strategyId:'alex_g_sr_v1',createdAt:'2026-07-20T14:00:01.000Z'};
    const p1=g.evidenceBuildPackageFromTrade(trade,opts),p2=g.evidenceBuildPackageFromTrade(trade,opts);
    const s=p1.objects.qualifiedSetups[0];
    eq(s.ruleIds.join('|'),'ALEX_SR_V1_CLASSIFY_PRECEDENCE|ALEX_SR_V1_SETUP_B_BREAK_RETEST');
    eq(s.triggeredConditions.length,7);
    eq(s.ruleAttribution.unverifiedConditionCount,0,'this record verifies every condition');
    eq(s.ruleAttribution.contradictsEngineClassification,false);
    eq(s.ruleAttribution.mirrorVersion,'alex-attr-1');
    eq(g.evidenceCanonicalize(p1),g.evidenceCanonicalize(p2),'identical inputs must canonicalize identically');
    ok(g.evidenceValidatePackage(p1).valid,'the captured package must validate: '+g.evidenceValidatePackage(p1).errors.join('; '));
  });
  t('B20 a pre-Unit-B package validates without any attribution at all',function(){
    const old=preUnitAPackage();
    delete old.objects.qualifiedSetups[0].ruleIds;
    delete old.objects.qualifiedSetups[0].triggeredConditions;
    delete old.objects.qualifiedSetups[0].ruleAttribution;
    const v=g.evidenceValidatePackage(old);
    ok(v.valid,'attribution must never be required: '+v.errors.join('; '));
    // But a malformed one, if present, is still caught.
    const bad=builtPackage();
    bad.objects.qualifiedSetups[0].triggeredConditions=[{conditionId:'',ruleId:null,satisfied:'yes',provenance:'NOPE'}];
    no(g.evidenceValidatePackage(bad).valid,'a malformed condition must fail validation');
  });
  t('B21 attribution does not move any classification, label or statistic',function(){
    const p=builtPackage();
    const s=p.objects.qualifiedSetups[0];
    eq(s.setupType,'B_breakRetest'); eq(s.setupLabel,'BREAK & RETEST');
    eq(s.setupCanonicalName,'Break & Retest');
    // The protected stats function must remain untouched and unaware of attribution.
    const stats=String(g.alexGComputeReplayStats);
    ['ruleIds','triggeredConditions','ruleAttribution'].forEach(function(n){
      eq(stats.indexOf(n),-1,'the protected stats function must not reference '+n);
    });
    ok(stats.indexOf('bySetupType:byGroup(t=>t.setupLabel)')!==-1,'stats grouping is unchanged');
  });

  // ══ GROUP 13 — v12.12.0 UNIT C1 (CORR-7) EXCURSION TIMING ══════════════════════════════
  // The governing rule: the mirror must reproduce the PROTECTED alexGComputeMAEMFE exactly, and
  // may emit timing only when it does. Fixtures compare against a LIVE call to that function.

  // Candles are {t:Date,o,h,l,c}. Entry is at index 0; the walk examines 1..exit inclusive.
  function candlePath(highs,lows,startMs){
    const base=startMs||Date.UTC(2026,3,1,0,0);
    return highs.map(function(h,i){
      return{t:new Date(base+i*3600000),o:1.1,h:h,l:lows[i],c:1.1};
    });
  }
  const PIP=0.0001;
  function timing(candles,entryIdx,exitIdx,dir,entry,maeP,mfeP,tf){
    return g.evidenceRecomputeExcursionTiming(candles,entryIdx,exitIdx,dir,entry,PIP,tf||'H1',
      maeP,mfeP,candles[entryIdx]?g.getCandleCloseTime(candles,entryIdx,tf||'H1').getTime():null);
  }
  // The authoritative engine values for the same inputs.
  function engineExtremes(candles,entryIdx,exitIdx,dir,entry){
    return g.alexGComputeMAEMFE(candles,entryIdx,exitIdx,dir,entry,PIP);
  }

  t('C1 the mirror reproduces the PROTECTED alexGComputeMAEMFE exactly, then emits timing',function(){
    //                     idx: 0     1     2     3     4
    const c=candlePath([1.1000,1.1010,1.1030,1.1020,1.1015],
                       [1.0990,1.0985,1.0995,1.0970,1.0980]);
    const eng=engineExtremes(c,0,4,'buy',1.1000);
    const r=timing(c,0,4,'buy',1.1000,eng.maePips,eng.mfePips);
    eq(r.agreement.maePipsRecomputed,eng.maePips,'MAE must match the protected function exactly');
    eq(r.agreement.mfePipsRecomputed,eng.mfePips,'MFE must match the protected function exactly');
    eq(r.agreement.matchesEngineExtremes,true);
    eq(r.agreement.status,'AGREES');
    eq(r.provenance,'DERIVED_FROM_OBSERVED_FIELDS','recomputation is never labelled OBSERVED');
    ok(r.timeToMFE&&r.timeToMAE,'timing must be emitted when the mirror agrees');
  });
  t('C2 timing points at the correct bars -- favourable-first path (long)',function(){
    const c=candlePath([1.1000,1.1030,1.1010,1.1005,1.1000],   // MFE at bar 1
                       [1.0990,1.0995,1.0993,1.0960,1.0985]);  // MAE at bar 3
    const eng=engineExtremes(c,0,4,'buy',1.1000);
    const r=timing(c,0,4,'buy',1.1000,eng.maePips,eng.mfePips);
    eq(r.timeToMFE.barIndex,1,'the favourable extreme occurred on bar 1');
    eq(r.timeToMFE.bars,1);
    eq(r.timeToMAE.barIndex,3,'the adverse extreme occurred on bar 3');
    eq(r.timeToMAE.bars,3);
    ok(r.timeToMFE.minutes<r.timeToMAE.minutes,'the favourable extreme came first in time too');
  });
  t('C3 timing points at the correct bars -- adverse-first path (long)',function(){
    const c=candlePath([1.1000,1.1002,1.1004,1.1050,1.1010],   // MFE at bar 3
                       [1.0990,1.0940,1.0995,1.0999,1.0998]);  // MAE at bar 1
    const eng=engineExtremes(c,0,4,'buy',1.1000);
    const r=timing(c,0,4,'buy',1.1000,eng.maePips,eng.mfePips);
    eq(r.timeToMAE.barIndex,1,'the adverse extreme came first');
    eq(r.timeToMFE.barIndex,3);
  });
  t('C4 SHORT trades invert favourable and adverse correctly',function(){
    const c=candlePath([1.1000,1.1005,1.1040,1.1002,1.1001],   // for a sell, highs are ADVERSE -> MAE bar 2
                       [1.0990,1.0950,1.0995,1.0994,1.0996]);  // lows are FAVOURABLE -> MFE bar 1
    const eng=engineExtremes(c,0,4,'sell',1.1000);
    const r=timing(c,0,4,'sell',1.1000,eng.maePips,eng.mfePips);
    eq(r.agreement.matchesEngineExtremes,true);
    eq(r.timeToMFE.barIndex,1,'a sell profits as price falls');
    eq(r.timeToMAE.barIndex,2,'and suffers as price rises');
  });
  t('C5 ties resolve to the FIRST bar, matching the engine\'s strict > comparison',function(){
    const c=candlePath([1.1000,1.1020,1.1020,1.1020,1.1010],   // identical highs on bars 1,2,3
                       [1.0990,1.0980,1.0980,1.0980,1.0985]);  // identical lows too
    const eng=engineExtremes(c,0,4,'buy',1.1000);
    const r=timing(c,0,4,'buy',1.1000,eng.maePips,eng.mfePips);
    eq(r.timeToMFE.barIndex,1,'the first bar reaching the extreme must win the tie');
    eq(r.timeToMAE.barIndex,1);
    ok(String(g.evidenceRecomputeExcursionTiming).indexOf('favMove>mfeP')!==-1,
       'the mirror must use the same strict > comparison as the protected function');
    ok(String(g.alexGComputeMAEMFE).indexOf('favMove>mfeP')!==-1,'and the protected function must still use it');
  });
  t('C6 an extreme of exactly 0 yields NULL timing, never a fabricated bar',function(){
    // A long that never trades above entry: MFE is 0.0 -- the real EUR/USD 14 Jul case.
    const c=candlePath([1.1000,1.0999,1.0998,1.0997,1.0996],
                       [1.0990,1.0985,1.0980,1.0975,1.0970]);
    const eng=engineExtremes(c,0,4,'buy',1.1000);
    eq(eng.mfePips,0,'the engine itself reports MFE 0');
    const r=timing(c,0,4,'buy',1.1000,eng.maePips,eng.mfePips);
    eq(r.agreement.status,'AGREES');
    eq(r.timeToMFE,null,'no bar ever exceeded 0, so no bar can be named');
    ok(r.timeToMAE&&r.timeToMAE.barIndex===4,'the adverse extreme is still timed');
  });
  t('C7 exitPathCandleRefs match the exact traversal, inclusive of the exit bar',function(){
    const c=candlePath([1.1000,1.1010,1.1030,1.1020,1.1015,1.1012],
                       [1.0990,1.0985,1.0995,1.0970,1.0980,1.0975]);
    const eng=engineExtremes(c,1,4,'buy',1.1000);
    const r=timing(c,1,4,'buy',1.1000,eng.maePips,eng.mfePips);
    eq(r.exitPathCandleRefs.map(function(x){return x.barIndex;}).join(','),'2,3,4',
       'the walk runs entryBarIndex+1 .. exitBarIndex inclusive');
    eq(r.agreement.barsExamined,3);
    r.exitPathCandleRefs.forEach(function(x){ ok(typeof x.timestampUTC==='string','each ref must carry a UTC timestamp'); });
    eq(r.exitPathCandleRefs[0].timestampUTC,g.getCandleCloseTime(c,2,'H1').toISOString(),
       'refs must use the engine\'s own candle close time');
  });
  t('C8 a forced MISMATCH omits timing, flags it, and still yields a package',function(){
    const c=candlePath([1.1000,1.1010,1.1030,1.1020,1.1015],
                       [1.0990,1.0985,1.0995,1.0970,1.0980]);
    const eng=engineExtremes(c,0,4,'buy',1.1000);
    const r=timing(c,0,4,'buy',1.1000,eng.maePips+7,eng.mfePips);   // stored value deliberately wrong
    eq(r.timeToMFE,null,'timing must be withheld');
    eq(r.timeToMAE,null);
    eq(r.agreement.status,'UNAVAILABLE');
    eq(r.agreement.reason,'RECOMPUTED_EXTREMES_DIFFER_FROM_ENGINE');
    eq(r.agreement.matchesEngineExtremes,false);
    eq(r.dataQualityFlags.join('|'),'EXCURSION_RECOMPUTATION_MISMATCH','a deterministic, stable code');
    eq(r.agreement.maePipsEngine,eng.maePips+7,'the engine-supplied value is preserved as given');
    eq(r.provenance,'UNAVAILABLE');
    // Capture must still succeed and must not disturb the authoritative stored extremes.
    const p=g.evidenceBuildPackageFromTrade(sampleTrade({excursionTiming:r,maePips:eng.maePips+7,mfePips:eng.mfePips}),
      {packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'});
    const oc=p.objects.outcomes[0];
    eq(oc.timeToMFE,null); eq(oc.excursionAgreement.status,'UNAVAILABLE');
    eq(oc.dataQualityFlags.join('|'),'EXCURSION_RECOMPUTATION_MISMATCH');
    eq(oc.maePips,eng.maePips+7,'the stored engine MAE must be untouched');
    eq(oc.mfePips,eng.mfePips,'the stored engine MFE must be untouched');
    ok(g.evidenceValidatePackage(p).valid,'the package must still validate: '+g.evidenceValidatePackage(p).errors.join('; '));
  });
  t('C9 unusable inputs yield UNAVAILABLE rather than a guess',function(){
    const c=candlePath([1.1000,1.1010],[1.0990,1.0985]);
    eq(timing(c,0,0,'buy',1.1000,0,0).provenance,'UNAVAILABLE','exit at or before entry examines nothing');
    eq(timing(c,0,1,'sideways',1.1000,0,0).provenance,'UNAVAILABLE','an unknown direction is not guessed');
    eq(g.evidenceRecomputeExcursionTiming(null,0,1,'buy',1.1,PIP,'H1',0,0,0).provenance,'UNAVAILABLE');
    eq(g.evidenceRecomputeExcursionTiming(c,0,1,'buy',1.1,0,'H1',0,0,0).provenance,'UNAVAILABLE','a zero pip size must not divide');
  });
  t('C10 timing is emitted through the real capture path and is deterministic',function(){
    const c=candlePath([1.1000,1.1010,1.1030,1.1020,1.1015],
                       [1.0990,1.0985,1.0995,1.0970,1.0980]);
    const eng=engineExtremes(c,0,4,'buy',1.1000);
    const r=timing(c,0,4,'buy',1.1000,eng.maePips,eng.mfePips);
    const trade=sampleTrade({excursionTiming:r,maePips:eng.maePips,mfePips:eng.mfePips});
    const opts={packageId:'PKG|alex_g_sr_v1|20260720|1',strategyId:'alex_g_sr_v1',createdAt:'2026-07-20T14:00:01.000Z'};
    const p1=g.evidenceBuildPackageFromTrade(trade,opts),p2=g.evidenceBuildPackageFromTrade(trade,opts);
    const oc=p1.objects.outcomes[0];
    eq(oc.excursionTimingProvenance,'DERIVED_FROM_OBSERVED_FIELDS');
    eq(oc.excursionAgreement.status,'AGREES');
    eq(oc.timeToMFE.barIndex,2); eq(oc.timeToMAE.barIndex,3);
    eq(oc.exitPathCandleRefs.length,4);
    eq(g.evidenceCanonicalize(p1),g.evidenceCanonicalize(p2),'identical inputs must canonicalize identically');
    ok(g.evidenceValidatePackage(p1).valid,g.evidenceValidatePackage(p1).errors.join('; '));
  });
  t('C11 a capture path without candles records UNAVAILABLE, not zero',function(){
    const oc=builtPackage().objects.outcomes[0];      // no excursionTiming supplied at all
    eq(oc.timeToMFE,null); eq(oc.timeToMAE,null);
    eq(oc.excursionTimingProvenance,'UNAVAILABLE');
    eq(oc.excursionAgreement.status,'UNAVAILABLE');
    eq(oc.excursionAgreement.reason,'NOT_COMPUTED_ON_THIS_CAPTURE_PATH');
    eq(oc.exitPathCandleRefs.length,0);
    eq(oc.dataQualityFlags.length,0,'an absent computation is not a data-quality problem');
  });
  t('C12 the completeness report stops claiming a gap it no longer has',function(){
    const withoutTiming=builtPackage().completenessReport.missing.map(function(m){return m.field;});
    ok(withoutTiming.indexOf('outcomes[].timeToMFE')!==-1,'still declared when timing is absent');
    const c=candlePath([1.1000,1.1030],[1.0990,1.0985]);
    const eng=engineExtremes(c,0,1,'buy',1.1000);
    const r=timing(c,0,1,'buy',1.1000,eng.maePips,eng.mfePips);
    const p=g.evidenceBuildPackageFromTrade(sampleTrade({excursionTiming:r,maePips:eng.maePips,mfePips:eng.mfePips}),
      {packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'});
    const fields=p.completenessReport.missing.map(function(m){return m.field;});
    eq(fields.indexOf('outcomes[].timeToMFE'),-1,'a package carrying timing must not declare it missing');
    ['objects.marketContexts','objects.decisions','identity.commitHash'].forEach(function(f){
      ok(fields.indexOf(f)!==-1,f+' must still be declared -- Unit C1 did not implement it');
    });
    // Order must be unchanged for packages that do NOT carry timing (array order is canonical).
    eq(withoutTiming.slice(0,4).join('|'),
       'objects.marketContexts|objects.decisions|identity.commitHash|outcomes[].timeToMFE');
  });
  t('C13 validation is present-only and rejects unbacked timing',function(){
    const old=preUnitAPackage();
    delete old.objects.outcomes[0].timeToMFE; delete old.objects.outcomes[0].timeToMAE;
    delete old.objects.outcomes[0].excursionTimingProvenance;
    delete old.objects.outcomes[0].excursionAgreement;
    ok(g.evidenceValidatePackage(old).valid,'a pre-Unit-C1 package must still validate: '+g.evidenceValidatePackage(old).errors.join('; '));
    // Timing without a verified agreement is an unbacked claim.
    const bad=builtPackage();
    bad.objects.outcomes[0].timeToMFE={bars:1,minutes:60,barIndex:1,timestampUTC:'2026-04-01T01:00:00.000Z'};
    no(g.evidenceValidatePackage(bad).valid,'timing must not stand without an AGREES agreement');
    const bad2=builtPackage();
    bad2.objects.outcomes[0].excursionAgreement={status:'AGREES',matchesEngineExtremes:false};
    no(g.evidenceValidatePackage(bad2).valid,'AGREES must be backed by matchesEngineExtremes');
    const bad3=builtPackage();
    bad3.objects.outcomes[0].excursionTimingProvenance='INVENTED';
    no(g.evidenceValidatePackage(bad3).valid,'the provenance vocabulary is closed');
  });
  t('C14 Unit C1 cannot influence the engine, and implements no part of Unit C2',function(){
    const m=String(g.evidenceRecomputeExcursionTiming);
    ['alexGSetupState','alexGZoneState','alexGAccount','paperAccount','journalEntries','localStorage',
     'commitAlexGLedger','openPaperPosition','alexGConstructTrade','alexGRunSetupReplay']
      .forEach(function(n){ eq(m.indexOf(n),-1,'the timing helper must never reference '+n); });
    // It must not write the authoritative extremes.
    eq(m.indexOf('maePips='),-1); eq(m.indexOf('mfePips='),-1);
    // The protected function must not know this layer exists.
    ['evidenceRecomputeExcursionTiming','excursionAgreement','timeToMFE']
      .forEach(function(n){ eq(String(g.alexGComputeMAEMFE).indexOf(n),-1,'protected code must not reference '+n); });
    // Unit C2 is NOT started: marketContexts stays empty and no candle window is stored.
    const c=candlePath([1.1000,1.1030],[1.0990,1.0985]);
    const eng=engineExtremes(c,0,1,'buy',1.1000);
    const p=g.evidenceBuildPackageFromTrade(sampleTrade({excursionTiming:timing(c,0,1,'buy',1.1000,eng.maePips,eng.mfePips)}),
      {packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'});
    // v12.13.0: market context is now implemented (Unit C2-M1) but is supplied by the SEAM. A
    // package built without one must still carry an empty array -- Unit C1 never invents context.
    eq(p.objects.marketContexts.length,0,'Unit C1 must not fabricate a market context');
    eq(p.objectCounts.marketContexts,0);
    const refs=p.objects.outcomes[0].exitPathCandleRefs;
    refs.forEach(function(r){
      ['o','h','l','c'].forEach(function(k){ eq(r[k],undefined,'refs must be references, not stored candles'); });
    });
  });
  t('C15 the seam threads the engine\'s own candles, read-only',function(){
    ok(String(g.runAlexGReplay).indexOf('candlesByTimeframe:datasets')!==-1,
       'replay must expose the datasets it already walked');
    const ui=String(g.runAlexGReplayUI);
    ok(ui.indexOf('evidenceCaptureReplayTrades(result.runIdentity,result.trades,result.setups,result.candlesByTimeframe)')!==-1,
       'the seam must receive them');
    ok(ui.indexOf('try{ evidenceCaptureReplayTrades')!==-1,'and stay individually wrapped');
    const seam=String(g.evidenceCaptureReplayTradesAsync);
    ok(seam.indexOf('evidenceRecomputeExcursionTiming(tfCandles')!==-1,'timing must be computed from the threaded candles');
    ok(seam.indexOf('catch(e){ excursion=null;')!==-1,'a timing failure must never cost the package');
    eq(seam.indexOf('tfCandles.push'),-1,'the seam must never mutate the candle arrays');
    eq(seam.indexOf('tfCandles.sort'),-1);
  });

  // ══ GROUP 14 — v12.13.0 UNIT C2-M1 (CORR-6) MARKET CONTEXT + LINEAGE ═══════════════════
  // The window must be a verbatim excerpt of the candles the engine walked, bounded, and loud
  // about anything it dropped. Nothing here may invent, derive or re-fetch a candle.

  function ctxCandles(n,startMs){
    const base=startMs||Date.UTC(2026,3,1,0,0),arr=[];
    for(let i=0;i<n;i++) arr.push({t:new Date(base+i*3600000),o:1.1+i*1e-5,h:1.1005+i*1e-5,l:1.0995+i*1e-5,c:1.1002+i*1e-5});
    return arr;
  }
  function buildCtx(candles,entryIdx,exitIdx,opts){
    return g.evidenceBuildMarketContext(candles,entryIdx,exitIdx,opts||{
      contextId:'CTX|AGT|1',positionId:'AGT|1',instrument:'EUR_USD',timeframe:'H1',datasetHash:'d'.repeat(64)});
  }

  t('X1 the window is the traded path plus bounded pre-entry context, verbatim',function(){
    const c=ctxCandles(200);
    const mc=buildCtx(c,120,150);
    eq(mc.window.entryBarIndex,120); eq(mc.window.exitBarIndex,150);
    eq(mc.window.fromBarIndex,70,'50 bars of pre-entry context by default');
    eq(mc.window.toBarIndex,150,'the window ends on the exit bar');
    eq(mc.window.preEntryBars,50);
    eq(mc.window.candleCount,81); eq(mc.candles.length,81);
    eq(mc.candleProvenance,'OBSERVED');
    eq(mc.scope,'TRADED_WINDOW_OWN_TIMEFRAME');
    // verbatim: values and bar indices must match the source array exactly
    eq(mc.candles[0].barIndex,70);
    eq(mc.candles[0].o,c[70].o); eq(mc.candles[0].h,c[70].h);
    eq(mc.candles[0].l,c[70].l); eq(mc.candles[0].c,c[70].c);
    eq(mc.candles[0].t,c[70].t.toISOString(),'timestamps are serialized, never recomputed');
    eq(mc.candles[80].barIndex,150);
    eq(mc.window.fromUTC,c[70].t.toISOString()); eq(mc.window.toUTC,c[150].t.toISOString());
    eq(mc.window.datasetCandleCount,200);
    eq(mc.datasetHash,'d'.repeat(64),'the excerpt is tied to the run identity');
  });
  t('X2 pre-entry context is clipped at the start of the dataset, not padded',function(){
    const c=ctxCandles(60);
    const mc=buildCtx(c,10,20);
    eq(mc.window.fromBarIndex,0,'there are only 10 bars of history available');
    eq(mc.window.preEntryBars,10,'and the window says so rather than claiming 50');
    eq(mc.window.requestedPreEntryBars,50);
    eq(mc.window.truncated,false,'running out of history is not a truncation');
    eq(mc.window.candleCount,21);
  });
  t('X3 a cap is LOUD -- it names the reason and the bars it dropped',function(){
    const c=ctxCandles(1200);
    const mc=g.evidenceBuildMarketContext(c,300,1000,{preEntryBars:300,maxCandles:600,timeframe:'H1'});
    eq(mc.window.truncated,true);
    ok(mc.window.droppedPreEntryBars>0,'and the drop is counted: '+mc.window.droppedPreEntryBars);
    eq(mc.window.toBarIndex,1000,'the exit bar must survive truncation');
    eq(mc.candles[mc.candles.length-1].barIndex,1000);
    eq(mc.window.fromBarIndex,300,'the cap consumes PRE-ENTRY context only -- never the traded path');
    eq(mc.window.preEntryBars,0,'all pre-entry context was dropped');
    eq(mc.window.pathExceedsMaxCandles,true,'the path alone exceeds the ceiling, and says so');
    eq(mc.window.truncationReason,'PATH_EXCEEDS_MAX_CANDLES');
    eq(mc.window.pathCandleCount,701);
  });
  t('X4 truncation always preserves the entry-to-exit path',function(){
    const c=ctxCandles(1000);
    const mc=g.evidenceBuildMarketContext(c,100,800,{preEntryBars:50,maxCandles:600,timeframe:'H1'});
    eq(mc.window.truncated,true);
    // The path itself is 701 bars -- longer than the cap. It is kept IN FULL and the overrun is
    // declared, because a window that stops before the exit cannot support the outcome.
    eq(mc.window.fromBarIndex,100,'the window starts at the entry bar');
    eq(mc.window.toBarIndex,800);
    eq(mc.candles[0].barIndex,100);
    eq(mc.candles[mc.candles.length-1].barIndex,800);
    eq(mc.window.candleCount,701);
    eq(mc.window.pathExceedsMaxCandles,true);
    eq(mc.window.truncationReason,'PATH_EXCEEDS_MAX_CANDLES');
  });
  t('X5 an unusable window returns null rather than a partial claim',function(){
    const c=ctxCandles(50);
    eq(buildCtx(c,10,9),null,'exit before entry');
    eq(buildCtx(c,10,60),null,'exit outside the dataset');
    eq(g.evidenceBuildMarketContext([],0,1,{}),null,'no candles');
    eq(g.evidenceBuildMarketContext(null,0,1,{}),null);
    const holed=ctxCandles(30); holed[15]=null;
    eq(g.evidenceBuildMarketContext(holed,10,20,{}),null,'a hole makes the window untrustworthy');
  });
  t('X6 higher-timeframe context is DECLARED absent, not silently missing',function(){
    // v12.14.0: the capability now exists (Unit C2-M2), so a window built WITHOUT one reports
    // UNAVAILABLE -- "nothing was supplied on this path" -- rather than the earlier FUTURE_WORK.
    const mc=buildCtx(ctxCandles(100),50,60);
    eq(mc.higherTimeframeContext,null);
    eq(mc.higherTimeframeContextProvenance,'UNAVAILABLE');
    ok(g.EVIDENCE_FIELD_PROVENANCE.indexOf('UNAVAILABLE')!==-1);
  });
  t('X7 a captured package carries the context and counts it',function(){
    const c=ctxCandles(100);
    const mc=buildCtx(c,50,60);
    const p=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:mc}),
      {packageId:'PKG|alex_g_sr_v1|20260720|1',strategyId:'alex_g_sr_v1'});
    eq(p.objects.marketContexts.length,1);
    eq(p.objectCounts.marketContexts,1,'objectCounts must track it');
    eq(p.objects.marketContexts[0].candles.length,61,'50 pre-entry bars + the 11-bar path');
    eq(p.objects.marketContexts[0].window.candleCount,61);
    ok(g.evidenceValidatePackage(p).valid,g.evidenceValidatePackage(p).errors.join('; '));
  });
  t('X8 the completeness report swaps one honest gap for another',function(){
    const without=builtPackage().completenessReport.missing.map(function(m){return m.field;});
    eq(without[0],'objects.marketContexts','the original gap keeps its original position');
    const mc=buildCtx(ctxCandles(100),50,60);
    const withCtx=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:mc}),
      {packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'}).completenessReport.missing.map(function(m){return m.field;});
    eq(withCtx.indexOf('objects.marketContexts'),-1,'a package holding a window must not declare it missing');
    ok(withCtx.indexOf('objects.marketContexts[].higherTimeframeContext')!==-1,
       'but it MUST declare what the window does not cover');
    ok(withCtx.indexOf('objects.decisions')!==-1,'decision chains remain an honest gap');
  });
  t('X9 lineage links every recorded object, and only by identifier',function(){
    const c=ctxCandles(100),mc=buildCtx(c,50,60);
    const p=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:mc,replaySourceTradeId:'AGT|src|1'}),
      {packageId:'PKG|x|1',strategyId:'alex_g_sr_v1',runId:'r'.repeat(64),datasetHash:'d'.repeat(64)});
    const L=p.objects.qualifiedSetups[0].lineage;
    eq(L.runId,'r'.repeat(64)); eq(L.datasetHash,'d'.repeat(64));
    eq(L.setupId,'AGS|EUR_USD|H1|z1|B_breakRetest|r1'); eq(L.candidateId,L.setupId);
    eq(L.zoneId,'AGZ|z1'); eq(L.reactionId,'AGR|r1');
    eq(L.positionId,'AGT|EUR_USD|1'); eq(L.outcomeId,'AGT|EUR_USD|1|outcome');
    eq(L.marketContextId,'CTX|AGT|1','the context is reachable from the setup');
    eq(L.packageId,'PKG|x|1'); eq(L.replaySourceTradeId,'AGT|src|1');
    eq(L.provenance,'OBSERVED','every value is a stored identifier');
    // links only -- never an embedded object graph
    Object.keys(L).forEach(function(k){
      const v=L[k]; ok(v===null||typeof v==='string',k+' must be a string identifier or null');
    });
  });
  t('X10 decision chains are declared absent, never implied',function(){
    const L=g.evidenceBuildLineage({tradeId:'AGT|1'},{});
    eq(L.decisionChainRef,null);
    eq(L.decisionChainProvenance,'FUTURE_WORK','CORR-5 is not implemented and must not look implemented');
    const m=String(g.evidenceBuildLineage)+String(g.evidenceBuildMarketContext);
    ['emitDecisionEvent','decisionEventLog','createDecisionEvent'].forEach(function(n){
      eq(m.indexOf(n),-1,'Unit C2-M1 must not touch the decision bus');
    });
  });
  t('X11 validation is present-only and rejects a silent cap',function(){
    const old=preUnitAPackage();
    ok(g.evidenceValidatePackage(old).valid,'a package with no context must still validate');
    const mc=buildCtx(ctxCandles(100),50,60);
    const p=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:mc}),{packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'});
    const bad1=JSON.parse(JSON.stringify(p));
    bad1.objects.marketContexts[0].window.truncated=true;
    bad1.objects.marketContexts[0].window.truncationReason=null;
    no(g.evidenceValidatePackage(bad1).valid,'a silent cap must be rejected');
    const bad2=JSON.parse(JSON.stringify(p));
    bad2.objects.marketContexts[0].window.candleCount=999;
    no(g.evidenceValidatePackage(bad2).valid,'a miscounted window must be rejected');
    const bad3=JSON.parse(JSON.stringify(p));
    bad3.objects.marketContexts[0].window.droppedPreEntryBars=5;
    no(g.evidenceValidatePackage(bad3).valid,'dropped bars without truncation must be rejected');
    const bad4=JSON.parse(JSON.stringify(p));
    bad4.objects.qualifiedSetups[0].lineage.zoneId={id:'x'};
    no(g.evidenceValidatePackage(bad4).valid,'lineage must be identifiers, not object graphs');
  });
  t('X12 context capture is deterministic and canonically stable',function(){
    const c=ctxCandles(100);
    const a=buildCtx(c,50,60),b=buildCtx(c,50,60);
    eq(JSON.stringify(a),JSON.stringify(b),'identical inputs must produce an identical window');
    const opts={packageId:'PKG|x|1',strategyId:'alex_g_sr_v1',createdAt:'2026-07-20T14:00:01.000Z'};
    const p1=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:a}),opts);
    const p2=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:b}),opts);
    eq(g.evidenceCanonicalize(p1),g.evidenceCanonicalize(p2),'and an identical canonical form');
  });
  t('X13 the seam builds the window from the engine\'s own candles, read-only',function(){
    const seam=String(g.evidenceCaptureReplayTradesAsync);
    ok(seam.indexOf('evidenceBuildMarketContext(tfCandles')!==-1,'the window must come from the threaded candles');
    ok(seam.indexOf('catch(e){ marketContext=null;')!==-1,'a context failure must never cost the package');
    ok(seam.indexOf('evidenceNormalizeReplayTrade(t,run,setup,cycleCount,excursion,marketContext)')!==-1);
    const b=String(g.evidenceBuildMarketContext);
    ['fetch','fetchCandlesRange','localStorage','.push(candles','candles.sort','candles.splice']
      .forEach(function(n){ eq(b.indexOf(n),-1,'the builder must never '+n); });
  });
  t('X14 Unit C2-M1 cannot influence trading, replay output or statistics',function(){
    const m=String(g.evidenceBuildMarketContext)+String(g.evidenceBuildLineage);
    ['alexGSetupState','alexGZoneState','alexGAccount','paperAccount','journalEntries',
     'commitAlexGLedger','openPaperPosition','alexGConstructTrade','alexGRunSetupReplay','alexGComputeReplayStats']
      .forEach(function(n){ eq(m.indexOf(n),-1,'context capture must never reference '+n); });
    // The protected replay functions must not know this layer exists.
    ['evidenceBuildMarketContext','marketContext','lineage']
      .forEach(function(n){ eq(String(g.alexGRunSetupReplay).indexOf(n),-1,'protected replay must not reference '+n); });
    // And a captured window must not alter the trade's own recorded values.
    const mc=buildCtx(ctxCandles(100),50,60);
    const p=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:mc}),{packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'});
    const oc=p.objects.outcomes[0],po=p.objects.positions[0];
    eq(oc.maePips,5); eq(oc.mfePips,100); eq(oc.recordedResultR,2);
    eq(po.entryPrice,1.1000); eq(po.originalStop,1.0950); eq(po.target,1.1100);
    eq(p.objects.qualifiedSetups[0].setupType,'B_breakRetest','classification is untouched');
  });
  t('X15 the window size stays proportionate on a RUN-001-shaped trade',function(){
    const c=ctxCandles(2220);                       // RUN-001's real H1 dataset size
    const mc=buildCtx(c,1000,1030);                 // ~30 bars held, RUN-001's average
    eq(mc.window.candleCount,81,'50 pre-entry + 31 path');
    eq(mc.window.truncated,false);
    const bytes=JSON.stringify(mc).length;
    ok(bytes<20000,'a typical window must stay small; measured '+bytes+' bytes');
  });

  // ══ GROUP 15 — v12.14.0 UNIT C2-M2 HIGHER-TIMEFRAME CONTEXT ════════════════════════════
  // The governing property is NO LOOK-AHEAD: context is what had closed at the entry moment.

  function tfCandlesFor(tf,n,startMs){
    const step={H1:3600000,H4:4*3600000,D:86400000,W:7*86400000}[tf];
    const base=startMs||Date.UTC(2026,0,1,0,0),arr=[];
    for(let i=0;i<n;i++) arr.push({t:new Date(base+i*step),o:1.1,h:1.1010,l:1.0990,c:1.1005});
    return arr;
  }
  function datasets(){
    return{H1:tfCandlesFor('H1',400),H4:tfCandlesFor('H4',120),D:tfCandlesFor('D',60),W:tfCandlesFor('W',20)};
  }
  // The anchor used throughout: the close of H1 bar 200.
  function anchorAt(ds,idx){ return g.getCandleCloseTime(ds.H1,idx||200,'H1').getTime(); }

  t('Y1 higher timeframes are captured in deterministic ascending rank order',function(){
    const ds=datasets();
    const htf=g.evidenceBuildHigherTimeframeContext(ds,'H1',anchorAt(ds),{});
    eq(htf.provenance,'OBSERVED');
    eq(htf.timeframes.map(function(x){return x.timeframe;}).join(','),'H4,D,W',
       'an H1 trade must capture H4, then D, then W');
    eq(htf.timeframes.map(function(x){return x.rank;}).join(','),'2,3,4');
    eq(htf.anchorBasis,'ENTRY_CANDLE_CLOSE');
    htf.timeframes.forEach(function(x){ eq(x.provenance,'OBSERVED'); });
  });
  t('Y2 the rank table mirrors the engine\'s own htfPriority exactly',function(){
    const engine=g.getRulesAlexG().config.htfPriority;
    const mirror=g.EVIDENCE_TIMEFRAME_RANK;
    eq(Object.keys(mirror).sort().join(','),Object.keys(engine).sort().join(','),'same timeframes');
    Object.keys(engine).forEach(function(tf){
      eq(mirror[tf],engine[tf],tf+': the evidence mirror must not drift from RULES_ALEXG.config.htfPriority');
    });
  });
  t('Y3 NO LOOK-AHEAD -- every captured bar closed at or before the anchor',function(){
    const ds=datasets();
    const anchorMs=anchorAt(ds,200);
    const htf=g.evidenceBuildHigherTimeframeContext(ds,'H1',anchorMs,{});
    ok(htf.timeframes.length>0);
    htf.timeframes.forEach(function(x){
      const lastClose=Date.parse(x.window.lastClosedBarCloseUTC);
      ok(lastClose<=anchorMs,x.timeframe+': the last captured bar must have CLOSED by the anchor');
      x.candles.forEach(function(c){
        ok(Date.parse(c.t)<=anchorMs,x.timeframe+': no captured bar may START after the anchor');
      });
      // and it must be the LATEST such bar -- context must not be stale either
      const next=x.window.toBarIndex+1;
      const src=ds[x.timeframe];
      if(next<src.length){
        ok(g.getCandleCloseTime(src,next,x.timeframe).getTime()>anchorMs,
           x.timeframe+': the next bar must genuinely be unclosed at the anchor');
      }
    });
  });
  t('Y4 the bar cap is respected and declared per timeframe',function(){
    const ds=datasets();
    const htf=g.evidenceBuildHigherTimeframeContext(ds,'H1',anchorAt(ds),{barsPerTimeframe:5});
    htf.timeframes.forEach(function(x){
      ok(x.candles.length<=5,x.timeframe+' exceeded the cap');
      eq(x.window.requestedBars,5);
      if(x.window.barsAvailableBeforeAnchor>5){
        eq(x.window.truncated,true,x.timeframe+' must declare truncation');
        eq(x.window.truncationReason,'BARS_PER_TIMEFRAME_CAP');
      }
      eq(x.window.candleCount,x.candles.length);
    });
  });
  t('Y5 candles are verbatim, with their own bar indices',function(){
    const ds=datasets();
    const htf=g.evidenceBuildHigherTimeframeContext(ds,'H1',anchorAt(ds),{barsPerTimeframe:3});
    const h4=htf.timeframes.filter(function(x){return x.timeframe==='H4';})[0];
    const src=ds.H4;
    h4.candles.forEach(function(c){
      eq(c.o,src[c.barIndex].o); eq(c.h,src[c.barIndex].h);
      eq(c.l,src[c.barIndex].l); eq(c.c,src[c.barIndex].c);
      eq(c.t,src[c.barIndex].t.toISOString(),'timestamps are serialized, never recomputed');
    });
    eq(h4.window.fromBarIndex,h4.candles[0].barIndex);
    eq(h4.window.toBarIndex,h4.candles[h4.candles.length-1].barIndex);
    eq(h4.window.datasetCandleCount,src.length);
  });
  t('Y6 a missing or unusable timeframe is OMITTED WITH A REASON, never skipped',function(){
    const ds=datasets(); delete ds.D;
    const htf=g.evidenceBuildHigherTimeframeContext(ds,'H1',anchorAt(ds),{});
    eq(htf.timeframes.map(function(x){return x.timeframe;}).join(','),'H4,W');
    const om=htf.omittedTimeframes.filter(function(x){return x.timeframe==='D';})[0];
    ok(om,'the missing timeframe must be recorded');
    eq(om.reason,'DATASET_UNAVAILABLE');
    // a dataset whose first bar closes after the anchor has nothing closed yet
    const late=datasets();
    late.W=tfCandlesFor('W',5,Date.UTC(2027,0,1));
    const htf2=g.evidenceBuildHigherTimeframeContext(late,'H1',anchorAt(late),{});
    eq(htf2.omittedTimeframes.filter(function(x){return x.timeframe==='W';})[0].reason,'NO_CLOSED_BAR_AT_ANCHOR');
  });
  t('Y7 a trade on the highest timeframe reports NOT_APPLICABLE, not a gap',function(){
    const ds=datasets();
    const htf=g.evidenceBuildHigherTimeframeContext(ds,'W',anchorAt(ds),{});
    eq(htf.provenance,'NOT_APPLICABLE');
    eq(htf.unavailableReason,'TRADE_IS_ON_THE_HIGHEST_TIMEFRAME');
    eq(htf.timeframes.length,0);
    // a D trade still has W above it
    eq(g.evidenceBuildHigherTimeframeContext(ds,'D',anchorAt(ds),{}).timeframes.map(function(x){return x.timeframe;}).join(','),'W');
  });
  t('Y8 unusable inputs are UNAVAILABLE with a named reason, never fabricated',function(){
    const ds=datasets();
    eq(g.evidenceBuildHigherTimeframeContext(null,'H1',1,{}).unavailableReason,'NO_DATASETS_SUPPLIED');
    eq(g.evidenceBuildHigherTimeframeContext(ds,'H1',null,{}).unavailableReason,'NO_ANCHOR_TIMESTAMP');
    eq(g.evidenceBuildHigherTimeframeContext(ds,'M5',anchorAt(ds),{}).unavailableReason,'UNKNOWN_TRADE_TIMEFRAME');
    const empty=g.evidenceBuildHigherTimeframeContext({H4:[],D:[],W:[]},'H1',anchorAt(ds),{});
    eq(empty.provenance,'UNAVAILABLE');
    eq(empty.unavailableReason,'NO_HIGHER_TIMEFRAME_DATA_AT_ANCHOR');
    eq(empty.omittedTimeframes.length,3,'each absent timeframe is still named');
  });
  t('Y9 the context rides inside the market-context object and reaches the package',function(){
    const ds=datasets();
    const htf=g.evidenceBuildHigherTimeframeContext(ds,'H1',anchorAt(ds),{barsPerTimeframe:4});
    const mc=g.evidenceBuildMarketContext(ds.H1,190,200,{contextId:'CTX|1',positionId:'AGT|1',
      instrument:'EUR_USD',timeframe:'H1',datasetHash:'d'.repeat(64),higherTimeframeContext:htf});
    eq(mc.higherTimeframeContextProvenance,'OBSERVED');
    eq(mc.higherTimeframeContext.timeframes.length,3);
    const p=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:mc}),{packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'});
    const stored=p.objects.marketContexts[0].higherTimeframeContext;
    eq(stored.timeframes.map(function(x){return x.timeframe;}).join(','),'H4,D,W');
    const v=g.evidenceValidatePackage(p);
    ok(v.valid,'a context-bearing package must validate: '+v.errors.join('; '));
  });
  t('Y10 validation REJECTS look-ahead in captured context',function(){
    const ds=datasets();
    const htf=g.evidenceBuildHigherTimeframeContext(ds,'H1',anchorAt(ds),{barsPerTimeframe:4});
    const mc=g.evidenceBuildMarketContext(ds.H1,190,200,{contextId:'CTX|1',timeframe:'H1',higherTimeframeContext:htf});
    const p=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:mc}),{packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'});
    ok(g.evidenceValidatePackage(p).valid,'baseline must be valid');
    // a bar that closes after the anchor is hindsight, not context
    const bad=JSON.parse(JSON.stringify(p));
    const tf0=bad.objects.marketContexts[0].higherTimeframeContext.timeframes[0];
    tf0.window.lastClosedBarCloseUTC=new Date(Date.parse(bad.objects.marketContexts[0].higherTimeframeContext.anchorUTC)+3600000).toISOString();
    const r1=g.evidenceValidatePackage(bad);
    no(r1.valid,'a window ending after its anchor must be rejected');
    ok(r1.errors.join(' ').indexOf('look-ahead')!==-1,'and must say why: '+r1.errors.join('; '));
    const bad2=JSON.parse(JSON.stringify(p));
    const tf1=bad2.objects.marketContexts[0].higherTimeframeContext.timeframes[0];
    tf1.candles[tf1.candles.length-1].t=new Date(Date.parse(bad2.objects.marketContexts[0].higherTimeframeContext.anchorUTC)+7200000).toISOString();
    no(g.evidenceValidatePackage(bad2).valid,'a candle starting after the anchor must be rejected');
  });
  t('Y11 validation rejects malformed or silently-capped context',function(){
    const ds=datasets();
    const htf=g.evidenceBuildHigherTimeframeContext(ds,'H1',anchorAt(ds),{barsPerTimeframe:4});
    const mc=g.evidenceBuildMarketContext(ds.H1,190,200,{contextId:'CTX|1',timeframe:'H1',higherTimeframeContext:htf});
    const p=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:mc}),{packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'});
    const miscount=JSON.parse(JSON.stringify(p));
    miscount.objects.marketContexts[0].higherTimeframeContext.timeframes[0].window.candleCount=99;
    no(g.evidenceValidatePackage(miscount).valid,'a miscounted timeframe window must be rejected');
    const silent=JSON.parse(JSON.stringify(p));
    const w=silent.objects.marketContexts[0].higherTimeframeContext.timeframes[0].window;
    w.truncated=true; w.truncationReason=null;
    no(g.evidenceValidatePackage(silent).valid,'a silent cap must be rejected');
    const nameless=JSON.parse(JSON.stringify(p));
    nameless.objects.marketContexts[0].higherTimeframeContext.omittedTimeframes=[{timeframe:'D'}];
    no(g.evidenceValidatePackage(nameless).valid,'an omission without a reason must be rejected');
    const badProv=JSON.parse(JSON.stringify(p));
    badProv.objects.marketContexts[0].higherTimeframeContext.provenance='MADE_UP';
    no(g.evidenceValidatePackage(badProv).valid,'the provenance vocabulary is closed');
  });
  t('Y12 the completeness report sheds the gap only when context is really captured',function(){
    const ds=datasets();
    const mcNoHtf=g.evidenceBuildMarketContext(ds.H1,190,200,{contextId:'CTX|1',timeframe:'H1'});
    const without=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:mcNoHtf}),
      {packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'}).completenessReport.missing.map(function(m){return m.field;});
    ok(without.indexOf('objects.marketContexts[].higherTimeframeContext')!==-1,
       'a window without higher-timeframe context must still declare the gap');
    const htf=g.evidenceBuildHigherTimeframeContext(ds,'H1',anchorAt(ds),{barsPerTimeframe:4});
    const mc=g.evidenceBuildMarketContext(ds.H1,190,200,{contextId:'CTX|1',timeframe:'H1',higherTimeframeContext:htf});
    const withCtx=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:mc}),
      {packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'}).completenessReport.missing.map(function(m){return m.field;});
    eq(withCtx.indexOf('objects.marketContexts[].higherTimeframeContext'),-1,'a captured context sheds the gap');
    ok(withCtx.indexOf('objects.decisions')!==-1,'decision chains remain an honest gap');
    // and the original ordering for a package with no window at all is untouched
    eq(builtPackage().completenessReport.missing[0].field,'objects.marketContexts');
  });
  t('Y13 context capture is deterministic and canonically stable',function(){
    const ds=datasets();
    const a=g.evidenceBuildHigherTimeframeContext(ds,'H1',anchorAt(ds),{barsPerTimeframe:6});
    const b=g.evidenceBuildHigherTimeframeContext(ds,'H1',anchorAt(ds),{barsPerTimeframe:6});
    eq(JSON.stringify(a),JSON.stringify(b),'identical inputs must produce identical context');
    const opts={packageId:'PKG|x|1',strategyId:'alex_g_sr_v1',createdAt:'2026-07-20T14:00:01.000Z'};
    const mkPkg=function(htf){
      const mc=g.evidenceBuildMarketContext(ds.H1,190,200,{contextId:'CTX|1',timeframe:'H1',higherTimeframeContext:htf});
      return g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:mc}),opts);
    };
    eq(g.evidenceCanonicalize(mkPkg(a)),g.evidenceCanonicalize(mkPkg(b)),'and identical canonical output');
  });
  t('Y14 payload growth is bounded and measured',function(){
    const ds=datasets();
    const htf=g.evidenceBuildHigherTimeframeContext(ds,'H1',anchorAt(ds),{});   // default 20 bars
    const total=htf.timeframes.reduce(function(n,x){return n+x.candles.length;},0);
    ok(total<=60,'three timeframes x 20 bars is the ceiling, measured '+total);
    const bytes=JSON.stringify(htf).length;
    ok(bytes<12000,'higher-timeframe context must stay small; measured '+bytes+' bytes');
    const mc=g.evidenceBuildMarketContext(ds.H1,150,200,{contextId:'CTX|1',timeframe:'H1',higherTimeframeContext:htf});
    const p=g.evidenceBuildPackageFromTrade(sampleTrade({marketContext:mc}),{packageId:'PKG|x|1',strategyId:'alex_g_sr_v1'});
    const pkgBytes=JSON.stringify(p).length;
    ok(pkgBytes<40000,'a full context-bearing package must stay well under 40 KB; measured '+pkgBytes+' bytes');
  });
  t('Y15 C2-M2 cannot influence trading, replay output or statistics',function(){
    const m=String(g.evidenceBuildHigherTimeframeContext);
    ['alexGSetupState','alexGZoneState','alexGAccount','paperAccount','journalEntries','localStorage',
     'commitAlexGLedger','openPaperPosition','alexGConstructTrade','alexGRunSetupReplay','alexGComputeReplayStats','fetch']
      .forEach(function(n){ eq(m.indexOf(n),-1,'higher-timeframe capture must never reference '+n); });
    eq(m.indexOf('.push(cs['),-1,'it must never mutate a dataset');
    ['evidenceBuildHigherTimeframeContext','higherTimeframeContext']
      .forEach(function(n){ eq(String(g.alexGRunSetupReplay).indexOf(n),-1,'protected replay must not reference '+n); });
    // the seam anchors on the entry timestamp, not on "now"
    const seam=String(g.evidenceCaptureReplayTradesAsync);
    ok(seam.indexOf('evidenceBuildHigherTimeframeContext(candlesByTimeframe,t.timeframe')!==-1);
    ok(seam.indexOf('t.entryTimestamp')!==-1,'the anchor must be the trade\'s own entry timestamp');
    eq(seam.indexOf('Date.now()'),-1,'context must never be anchored on wall-clock time');
  });

  // ══ GROUP 16 — v12.15.0 TRADE INTEGRITY & QUARANTINE ═══════════════════════════════════
  // Rule-based, not identifier-based: the seeded record is caught by invariants, and a genuine
  // trade must survive every one of them untouched.

  // A genuine ALEX trade, shaped exactly as the engine records one.
  function genuineTrade(over){
    const t={tradeId:'AGT|AGS|alex_g_sr_v1|EUR_USD|H1|AGZ|AGC|EUR_USD|H1|low|1774616400000|v1775134800000|A_repeatedReaction|AGR|EUR_USD|H1|low|1775430000000',
      strategy:'alex_g_sr_v1',pair:'EUR_USD',timeframe:'H1',direction:'buy',
      entry:1.15070,stop:1.14992,target:1.15226,exitPrice:1.15226,
      result:'Win',resultR:2,pnl:198,maePips:0,mfePips:21.8,
      openedAt:'2026-04-06T02:00:00.000Z',closedAt:'2026-04-06T03:00:00.000Z',
      isDeveloperTrade:false,tradeSource:'AUTO'};
    if(over) Object.keys(over).forEach(function(k){ t[k]=over[k]; });
    return t;
  }
  // The record forensics recovered from storage on 2026-08-02.
  function seededTrade(over){
    const t={tradeId:'AGT|MANUAL-B|1785634676564',signalId:'SIG|MANUAL-B|1',
      setupId:'AGS|EUR_USD|H1|zB|B_breakRetest|rB',strategy:'alex_g_sr_v1',
      pair:'EUR_USD',timeframe:'H1',direction:'buy',setupLabel:'BREAK & RETEST',
      entry:1.1,stop:1.095,target:1.11,exitPrice:1.11,plannedRR:2,
      result:'Win',resultR:2,pnl:200,maePips:0,mfePips:0,
      openedAt:'2026-08-02T01:37:56.564Z',closedAt:'2026-08-02T01:37:56.564Z',
      isDeveloperTrade:false,tradeSource:'AUTO',exitDetectionSource:'live_snapshot'};
    if(over) Object.keys(over).forEach(function(k){ t[k]=over[k]; });
    return t;
  }

  t('Q1 a genuine trade passes every integrity rule untouched',function(){
    const v=g.evaluateTradeIntegrity(genuineTrade(),'alex_g_sr_v1');
    eq(v.status,'CLEAN','a real trade must never be quarantined: '+JSON.stringify(v.violations));
    eq(v.violations.length,0);
    ok(v.rulesEvaluated.length>=5,'every applicable rule must actually run');
    // a genuine LOSS must also pass
    const loss=g.evaluateTradeIntegrity(genuineTrade({result:'Loss',resultR:-1,pnl:-99,
      exitPrice:1.14992,maePips:16,mfePips:0}),'alex_g_sr_v1');
    eq(loss.status,'CLEAN',JSON.stringify(loss.violations));
  });
  t('Q2 the seeded record is QUARANTINED, by rules rather than by its id',function(){
    const v=g.evaluateTradeIntegrity(seededTrade(),'alex_g_sr_v1');
    eq(v.status,'QUARANTINED');
    const ids=v.violations.map(function(x){return x.ruleId;}).sort();
    ok(ids.indexOf('TI_WIN_REQUIRES_FAVOURABLE_EXCURSION')!==-1,'the impossible excursion must be caught');
    ok(ids.indexOf('TI_NONZERO_LIFETIME')!==-1,'the zero-duration lifetime must be caught');
    ok(ids.indexOf('TI_TRADE_ID_ENGINE_MINTED')!==-1,'the hand-written id must be caught');
    // and it is caught EVEN IF the id is disguised as a genuine one -- rules, not identifiers
    const disguised=seededTrade({tradeId:genuineTrade().tradeId});
    const v2=g.evaluateTradeIntegrity(disguised,'alex_g_sr_v1');
    eq(v2.status,'QUARANTINED','a convincing id must not rescue an impossible trade');
    ok(v2.violations.some(function(x){return x.ruleId==='TI_WIN_REQUIRES_FAVOURABLE_EXCURSION';}));
  });
  t('Q3 each invariant catches its own impossibility independently',function(){
    const cases=[
      ['win with zero MFE',      genuineTrade({result:'Win',mfePips:0}),                 'TI_WIN_REQUIRES_FAVOURABLE_EXCURSION'],
      ['loss with zero MAE',     genuineTrade({result:'Loss',exitPrice:1.14992,maePips:0,mfePips:5}),'TI_LOSS_REQUIRES_ADVERSE_EXCURSION'],
      ['zero lifetime',          genuineTrade({closedAt:'2026-04-06T02:00:00.000Z'}),    'TI_NONZERO_LIFETIME'],
      ['win exiting adversely',  genuineTrade({result:'Win',exitPrice:1.14000}),         'TI_RESULT_CONSISTENT_WITH_EXIT'],
      ['hand-written id',        genuineTrade({tradeId:'AGT|MANUAL-Z|1'}),               'TI_TRADE_ID_ENGINE_MINTED']
    ];
    cases.forEach(function(c){
      const v=g.evaluateTradeIntegrity(c[1],'alex_g_sr_v1');
      eq(v.status,'QUARANTINED',c[0]+' must quarantine');
      ok(v.violations.some(function(x){return x.ruleId===c[2];}),
         c[0]+': expected '+c[2]+', got '+v.violations.map(function(x){return x.ruleId;}).join(','));
    });
  });
  t('Q4 rules are UNIVERSAL -- a future strategy inherits them with no code change',function(){
    const universal=g.getTradeIntegrityRules().filter(function(r){return r.appliesTo==='*';});
    ok(universal.length>=4,'most rules must be strategy-agnostic, found '+universal.length);
    // An unregistered strategy still gets the universal protection...
    const tjr=g.evaluateTradeIntegrity({strategy:'tjr_session_v1',result:'Win',entry:1.1,stop:1.09,
      target:1.12,exitPrice:1.12,mfePips:0,maePips:3,
      openedAt:'2026-08-01T10:00:00.000Z',closedAt:'2026-08-01T12:00:00.000Z',tradeId:'TJR|1'},'tjr_session_v1');
    eq(tjr.status,'QUARANTINED','an impossible TJR trade must be caught by the universal rules');
    ok(tjr.violations.some(function(x){return x.ruleId==='TI_WIN_REQUIRES_FAVOURABLE_EXCURSION';}));
    // ...but a strategy-specific id rule only applies where a profile declares one.
    ok(tjr.rulesSkipped.indexOf('TI_TRADE_ID_ENGINE_MINTED')!==-1,
       'the id-format rule must be skipped for a strategy with no declared profile, not guessed at');
    ok(g.getTradeIntegrityProfiles().alex_g_sr_v1.tradeIdPattern instanceof RegExp);
  });
  t('Q5 quarantine NEVER deletes or rewrites the record',function(){
    const rec=seededTrade();
    const before=JSON.stringify(rec);
    g.evaluateTradeIntegrity(rec,'alex_g_sr_v1');
    g.tradeIntegrityIsQuarantined(rec,'alex_g_sr_v1');
    const list=[genuineTrade(),rec];
    const filtered=g.tradeIntegrityFilterForStatistics(list,'alex_g_sr_v1');
    eq(JSON.stringify(rec),before,'the record must be byte-identical after evaluation');
    eq(list.length,2,'the source collection must not shrink');
    eq(filtered.length,1,'only the statistics view excludes it');
    ok(list.indexOf(rec)!==-1,'the quarantined record stays in the account');
    // the layer must contain no delete/write path at all
    const src=String(g.evaluateTradeIntegrity)+String(g.tradeIntegrityFilterForStatistics)+String(g.tradeIntegrityReport);
    ['localStorage','.splice(','delete ','commitAlexGLedger','saveAlexG'].forEach(function(n){
      eq(src.indexOf(n),-1,'the integrity layer must never '+n);
    });
  });
  t('Q6 the investigator report preserves and explains every exclusion',function(){
    const rep=g.tradeIntegrityReport([genuineTrade(),seededTrade()],'alex_g_sr_v1');
    eq(rep.evaluated,2); eq(rep.quarantined,1);
    const row=rep.rows[0];
    eq(row.tradeId,'AGT|MANUAL-B|1785634676564');
    eq(row.preserved,true,'the report must state the record is preserved');
    eq(row.pnl,200,'its P&L must be recoverable for the correction arithmetic');
    ok(row.violations.length>=3,'every violated rule must be listed');
    row.violations.forEach(function(v){
      ok(v.ruleId&&v.requirement&&v.expectation&&v.detail,'each violation must explain itself');
      ok(v.observed&&typeof v.observed==='object','and cite what it observed');
    });
  });
  t('Q7 statistics, dashboard and journal all exclude quarantined records',function(){
    const panel=g.getSource('function renderAlexGLivePanel()');
    ok(panel.indexOf('tradeIntegrityFilterForStatistics(closedAll')!==-1,'the live panel must filter');
    ok(panel.indexOf('quarantinedPnl')!==-1,'and must net quarantined P&L out of the displayed figure');
    ok(panel.indexOf('QUARANTINED')!==-1,'while still badging the record in the table');
    ok(g.appSource.indexOf('const closed=tradeIntegrityFilterForStatistics(closedVisible,entry.manifest.id);')!==-1,
       'the dashboard must filter for EVERY registered strategy, keyed on manifest id');
    ok(g.appSource.indexOf('const statRecords=tradeIntegrityFilterForStatistics(records);')!==-1,
       'the journal summary must filter');
    ok(g.appSource.indexOf('quarantined, excluded from these figures')!==-1,
       'and must disclose how many it excluded');
  });
  t('Q8 replay evidence and protected logic are untouched by this layer',function(){
    const protectedList=g.getBaselineAlexFunctions();
    ['alexGCloseLivePosition','alexGUpdatePositionExcursionAndCheckExit','alexGComputeReplayStats',
     'alexGConstructTrade','alexGRunSetupReplay'].forEach(function(f){
      ok(protectedList.indexOf(f)!==-1,f+' must still be protected');
      ['evaluateTradeIntegrity','tradeIntegrityFilterForStatistics','TRADE_INTEGRITY_RULES']
        .forEach(function(n){ eq(String(g[f]||'').indexOf(n),-1,f+' must not reference '+n); });
    });
    // replay statistics must not be routed through the integrity filter
    eq(String(g.alexGComputeReplayStats).indexOf('tradeIntegrity'),-1,
       'replay statistics must be computed from replay trades exactly as before');
    // and an Evidence Package must be unaffected by evaluation
    const p=builtPackage();
    const before=g.evidenceCanonicalize(p);
    g.evaluateTradeIntegrity({strategy:'alex_g_sr_v1',result:'Win',mfePips:0},'alex_g_sr_v1');
    eq(g.evidenceCanonicalize(p),before,'evaluating integrity must not touch evidence');
  });
  t('Q9 evaluation is deterministic and fails safe',function(){
    const rec=seededTrade();
    eq(JSON.stringify(g.evaluateTradeIntegrity(rec,'alex_g_sr_v1')),
       JSON.stringify(g.evaluateTradeIntegrity(rec,'alex_g_sr_v1')),'same input, same verdict');
    // insufficient data must not quarantine -- absence of evidence is not evidence of forgery
    eq(g.evaluateTradeIntegrity({strategy:'alex_g_sr_v1',result:'Win',
      tradeId:genuineTrade().tradeId}, 'alex_g_sr_v1').status,'CLEAN',
      'a record lacking the fields a rule needs must not be quarantined');
    eq(g.evaluateTradeIntegrity(null,'alex_g_sr_v1').status,'CLEAN');
    eq(g.evaluateTradeIntegrity(undefined).status,'CLEAN');
    eq(g.tradeIntegrityFilterForStatistics(null,'alex_g_sr_v1').length,0);
  });

  // ══ GROUP 17 — v12.16.0 IMMUTABLE TRADE LEDGER & DERIVED ACCOUNT STATE ═════════════════
  // Every figure must be reproducible from starting balance + ledger + quarantined events.

  function ledgerTrade(over){
    const t={tradeId:'AGT|AGS|alex_g_sr_v1|EUR_USD|H1|AGZ|AGC|EUR_USD|H1|low|1774616400000|v1775134800000|A_repeatedReaction|AGR|EUR_USD|H1|low|1775430000000',
      strategy:'alex_g_sr_v1',pair:'EUR_USD',timeframe:'H1',direction:'buy',
      entry:1.15,stop:1.1450,target:1.1600,exitPrice:1.1600,result:'Win',resultR:2,pnl:200,
      riskAmount:100,maePips:2,mfePips:50,
      openedAt:'2026-04-06T02:00:00.000Z',closedAt:'2026-04-06T03:00:00.000Z',
      isDeveloperTrade:false,tradeSource:'AUTO'};
    if(over) Object.keys(over).forEach(function(k){ t[k]=over[k]; });
    return t;
  }
  function lossTrade(over){
    return ledgerTrade(Object.assign({tradeId:ledgerTrade().tradeId+'|L',result:'Loss',resultR:-1,
      pnl:-100,exitPrice:1.1450,maePips:52,mfePips:1,
      closedAt:'2026-04-07T03:00:00.000Z'},over||{}));
  }

  t('L1 an account is rebuilt from starting balance + ledger alone',function(){
    const d=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',
      records:[ledgerTrade(),lossTrade()]});
    eq(d.schemaVersion,'mogo.trade-ledger.v1');
    eq(d.startingBalance,10000);
    eq(d.balance,10100,'10000 + 200 - 100, derived, never read from a stored total');
    eq(d.realizedPnl,100);
    eq(d.wins,1); eq(d.losses,1); eq(d.decided,2); eq(d.winRate,50);
    eq(d.grossWin,200); eq(d.grossLoss,100); eq(d.profitFactor,2);
    eq(d.derivation.method,'DERIVED_FROM_LEDGER');
    eq(d.eventCounts.included,2); eq(d.eventCounts.excluded,0);
  });
  t('L2 reconstruction is deterministic and order-independent',function(){
    const a=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',
      records:[ledgerTrade(),lossTrade()]});
    const b=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',
      records:[lossTrade(),ledgerTrade()]});   // supplied in the opposite order
    eq(JSON.stringify(a),JSON.stringify(b),'the ledger sorts chronologically, so input order cannot matter');
    const c=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',
      records:[ledgerTrade(),lossTrade()]});
    eq(JSON.stringify(a),JSON.stringify(c),'same inputs must always produce the same account');
  });
  t('L3 quarantined events are EXCLUDED from every figure but PRESERVED in full',function(){
    const seeded=seededTrade();
    const d=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',
      records:[ledgerTrade(),seeded]});
    eq(d.balance,10200,'only the genuine +200 is counted');
    eq(d.wins,1,'the seeded Win must not inflate the win count');
    eq(d.decided,1);
    eq(d.eventCounts.quarantined,1);
    eq(d.excludedEvents.length,1,'and it is still carried in the ledger');
    const ex=d.excludedEvents[0];
    eq(ex.tradeId,'AGT|MANUAL-B|1785634676564');
    eq(ex.pnl,200,'its P&L is preserved -- that is what explains a stored-balance divergence');
    ok(ex.integrityViolations.length>=3,'with the rules it violated');
  });
  t('L4 reconciliation explains a stored balance that includes an excluded trade',function(){
    const d=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',
      records:[seededTrade()]});
    eq(d.balance,10000,'the ledger says nothing genuine happened');
    // this is the real INC-005 situation: storage says 10200
    const rec=g.ledgerReconcileBalance(10200,d);
    eq(rec.status,'EXPLAINED_BY_EXCLUSIONS');
    eq(rec.storedBalance,10200); eq(rec.derivedBalance,10000);
    eq(rec.delta,200); eq(rec.excludedPnl,200); eq(rec.unexplainedDelta,0);
    ok(rec.explanation.indexOf('excluded')!==-1);
  });
  t('L5 an UNEXPLAINED divergence is reported, not absorbed',function(){
    const d=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',
      records:[ledgerTrade()]});
    eq(d.balance,10200);
    const rec=g.ledgerReconcileBalance(10500,d);   // stored total moved for no ledger reason
    eq(rec.status,'UNEXPLAINED_DELTA');
    eq(rec.delta,300); eq(rec.unexplainedDelta,300);
    eq(g.ledgerReconcileBalance(10200,d).status,'MATCHES');
    eq(g.ledgerReconcileBalance(null,d).status,'UNAVAILABLE');
  });
  t('L6 the ledger architecture is strategy-agnostic (JVM field names differ)',function(){
    // JVM records name the id, pair and direction differently. Mapped verbatim by adapter.
    const jvm=[{id:7,oPair:'EUR_USD',dir:'long',pnl:150,riskAmount:100,result:'Win',resultR:1.5,
      entry:1.1,stop:1.09,exitPrice:1.115,maePips:3,mfePips:60,
      openedAt:'2026-05-01T10:00:00.000Z',closedAt:'2026-05-01T14:00:00.000Z'}];
    const d=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'current_strategy',records:jvm});
    eq(d.balance,10150); eq(d.wins,1); eq(d.eventCounts.included,1);
    const ev=g.ledgerBuildEvents(jvm,'current_strategy')[0];
    eq(ev.tradeId,'7'); eq(ev.pair,'EUR_USD'); eq(ev.direction,'long');
    eq(ev.ledgerEventId,'current_strategy|7');
    // an unknown future strategy falls back to canonical names rather than failing
    const future=g.ledgerBuildEvents([{tradeId:'X|1',pair:'GBP_USD',direction:'sell',pnl:10,
      result:'Win',closedAt:'2026-05-02T00:00:00.000Z'}],'crt_v1')[0];
    eq(future.tradeId,'X|1'); eq(future.strategyId,'crt_v1');
  });
  t('L7 the ledger never mutates its source records',function(){
    const recs=[ledgerTrade(),seededTrade()];
    const before=JSON.stringify(recs);
    g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',records:recs});
    g.ledgerBuildEvents(recs,'alex_g_sr_v1');
    eq(JSON.stringify(recs),before,'derivation must be read-only over the account');
    const src=String(g.ledgerDeriveAccountState)+String(g.ledgerBuildEvents)+String(g.ledgerNormalizeEvent);
    ['localStorage','commitAlexGLedger','saveAlexG','.splice(','delete ','alexGAccount.balance=']
      .forEach(function(n){ eq(src.indexOf(n),-1,'the ledger layer must never '+n); });
  });
  t('L8 R-space reuses the SHIPPED equity engine rather than a second implementation',function(){
    const d=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',
      records:[ledgerTrade(),lossTrade()]});
    eq(d.derivation.rSpaceEngine,'alexGComputeEquityStats (shipped, unmodified)');
    eq(d.netR,1,'+2R then -1R');
    eq(d.expectancyR,0.5);
    ok(d.maxDrawdownR>=1,'the drawdown comes from the same chronological walk');
    ok(String(g.ledgerDeriveAccountState).indexOf('alexGComputeEquityStats')!==-1,
       'it must call the shipped engine, not re-derive equity');
  });
  t('L9 missing data is counted, never guessed',function(){
    const noPnl=ledgerTrade({pnl:null,tradeId:'AGT|AGS|alex_g_sr_v1|X|1'});
    const d=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',records:[noPnl]});
    eq(d.eventCounts.pnlUnavailable,1,'the gap is reported');
    eq(d.balance,10000,'and never filled in with an invented number');
    eq(d.wins,1,'the outcome is still counted where it IS known');
    const empty=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',records:[]});
    eq(empty.balance,10000); eq(empty.winRate,null); eq(empty.decided,0);
    eq(g.ledgerDeriveAccountState({}).balance,0,'no inputs must not throw');
  });
  t('L10 developer test trades are excluded by default and preserved',function(){
    const dev=ledgerTrade({tradeId:'AGT|TEST|1',isDeveloperTrade:true,pnl:500});
    const d=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',
      records:[ledgerTrade(),dev]});
    eq(d.balance,10200,'a test trade must not move a derived balance');
    eq(d.eventCounts.developerTrades,1);
    eq(d.excludedEvents.length,1);
    const withDev=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',
      records:[ledgerTrade(),dev],includeDeveloperTrades:true});
    eq(withDev.balance,10700,'an investigator can opt them back in');
  });
  t('L11 the ledger cannot influence trading or replay',function(){
    const protectedList=g.getBaselineAlexFunctions();
    ['alexGCloseLivePosition','alexGConstructTrade','alexGRunSetupReplay','alexGComputeReplayStats']
      .forEach(function(f){
        ok(protectedList.indexOf(f)!==-1,f+' must still be protected');
        ['ledgerDeriveAccountState','ledgerReconcileBalance','TRADE_LEDGER_ADAPTERS']
          .forEach(function(n){ eq(String(g[f]||'').indexOf(n),-1,f+' must not reference '+n); });
      });
    const p=builtPackage();
    const before=g.evidenceCanonicalize(p);
    g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',records:[ledgerTrade()]});
    eq(g.evidenceCanonicalize(p),before,'deriving an account must not touch evidence');
  });

  // ══ GROUP 18 — v12.17.0 LEDGER RECONCILIATION DIAGNOSTICS ══════════════════════════════
  // Diagnostics only: read both views, write neither, and classify every difference as exactly
  // one of three verdicts with the responsible ledger events named.

  t('R1 every field MATCHES when the stored total agrees with the ledger',function(){
    const rep=g.ledgerBuildReconciliationReport({strategyId:'alex_g_sr_v1',startingBalance:10000,
      records:[ledgerTrade(),lossTrade()],storedBalance:10100});
    eq(rep.schemaVersion,'mogo.ledger-reconciliation.v1');
    eq(rep.overall,'MATCHES');
    eq(rep.statusCounts.UNEXPLAINED_DELTA,0);
    rep.fields.forEach(function(f){
      eq(f.status,'MATCHES',f.field+' should match: stored '+f.storedValue+' vs derived '+f.derivedValue);
      ok(f.explanation&&f.explanation.length,'every row must explain itself');
    });
    ok(rep.fields.length>=8,'balance, P&L, wins, losses, decided, win rate, netR and drawdown');
  });
  t('R2 the INC-005 case classifies as EXPLAINED_BY_EXCLUSIONS on every affected field',function(){
    const rep=g.ledgerBuildReconciliationReport({strategyId:'alex_g_sr_v1',startingBalance:10000,
      records:[seededTrade()],storedBalance:10200});
    eq(rep.overall,'EXPLAINED_BY_EXCLUSIONS');
    const bal=rep.fields.filter(function(f){return f.field==='balance';})[0];
    eq(bal.storedValue,10200); eq(bal.derivedValue,10000); eq(bal.difference,200);
    eq(bal.status,'EXPLAINED_BY_EXCLUSIONS');
    ok(bal.explanation.indexOf('excluded')!==-1);
    eq(bal.responsibleTradeIds.join(','),'AGT|MANUAL-B|1785634676564','the row must name the record');
    const wins=rep.fields.filter(function(f){return f.field==='wins';})[0];
    eq(wins.storedValue,1,'the stored view counted the seeded win');
    eq(wins.derivedValue,0,'the ledger does not');
    eq(wins.status,'EXPLAINED_BY_EXCLUSIONS');
  });
  t('R3 an UNEXPLAINED_DELTA is reported and never absorbed',function(){
    const rep=g.ledgerBuildReconciliationReport({strategyId:'alex_g_sr_v1',startingBalance:10000,
      records:[ledgerTrade()],storedBalance:10500});      // 300 the ledger cannot account for
    eq(rep.overall,'UNEXPLAINED_DELTA');
    const bal=rep.fields.filter(function(f){return f.field==='balance';})[0];
    eq(bal.status,'UNEXPLAINED_DELTA');
    eq(bal.difference,300);
    ok(bal.explanation.indexOf('cannot account')!==-1,'and says so plainly');
  });
  t('R4 every verdict comes from the declared three-value vocabulary',function(){
    eq(g.getLedgerReconciliationStatuses().join('|'),'MATCHES|EXPLAINED_BY_EXCLUSIONS|UNEXPLAINED_DELTA');
    [[10100,'MATCHES'],[10300,'EXPLAINED_BY_EXCLUSIONS'],[99999,'UNEXPLAINED_DELTA']].forEach(function(c){
      const rep=g.ledgerBuildReconciliationReport({strategyId:'alex_g_sr_v1',startingBalance:10000,
        records:[ledgerTrade(),lossTrade(),seededTrade()],storedBalance:c[0]});
      const bal=rep.fields.filter(function(f){return f.field==='balance';})[0];
      eq(bal.status,c[1],'stored '+c[0]);
      ok(g.getLedgerReconciliationStatuses().indexOf(bal.status)!==-1);
    });
  });
  t('R5 every difference drills down to the ledger events responsible',function(){
    const rep=g.ledgerBuildReconciliationReport({strategyId:'alex_g_sr_v1',startingBalance:10000,
      records:[ledgerTrade(),seededTrade()],storedBalance:10400});
    const drill=g.ledgerReconciliationDrillDown(rep,'balance');
    eq(drill.field,'balance');
    eq(drill.status,'EXPLAINED_BY_EXCLUSIONS');
    eq(drill.events.length,1,'the responsible event must be reachable from the row');
    eq(drill.events[0].tradeId,'AGT|MANUAL-B|1785634676564');
    eq(drill.events[0].pnl,200,'with its P&L');
    ok(drill.events[0].integrityViolations.length>=3,'and the rules it violated');
    eq(g.ledgerReconciliationDrillDown(rep,'nosuchfield'),null);
    eq(g.ledgerReconciliationDrillDown(null,'balance'),null);
  });
  t('R6 excluded events are preserved in the report, never dropped',function(){
    const rep=g.ledgerBuildReconciliationReport({strategyId:'alex_g_sr_v1',startingBalance:10000,
      records:[ledgerTrade(),seededTrade()],storedBalance:10400});
    eq(rep.excludedEvents.length,1);
    eq(rep.generatedFrom.ledgerEvents.excluded,1);
    eq(rep.generatedFrom.ledgerEvents.included,1);
    eq(rep.readOnly,true,'the report must declare itself read-only');
  });
  t('R7 diagnostics replace NO stored total and write nothing',function(){
    const src=String(g.ledgerBuildReconciliationReport)+String(g.renderLedgerReconciliation)+
              String(g.ledgerReconciliationDrillDown)+String(g.ledgerReconciliationSources);
    ['localStorage','commitAlexGLedger','saveAlexG','alexGAccount.balance=','paperAccount.balance=',
     '.splice(','delete ','openPaperPosition','alexGCloseLivePosition'].forEach(function(n){
      eq(src.indexOf(n),-1,'the diagnostics view must never '+n);
    });
    // and running it leaves the accounts untouched
    const acct={balance:10200,closedPositions:[seededTrade()],openPositions:[]};
    const before=JSON.stringify(acct);
    g.ledgerBuildReconciliationReport({strategyId:'alex_g_sr_v1',startingBalance:10000,
      records:acct.closedPositions,storedBalance:acct.balance});
    eq(JSON.stringify(acct),before,'the account must be byte-identical after reconciliation');
  });
  t('R8 the view covers every strategy and is wired into Diagnostics',function(){
    const sources=String(g.ledgerReconciliationSources);
    ok(sources.indexOf('alex_g_sr_v1')!==-1&&sources.indexOf('current_strategy')!==-1,
       'both live strategies must be reconciled');
    ok(g.appSource.indexOf("renderLedgerReconciliation();}")!==-1,
       'the Diagnostics panel must refresh the view when opened');
    // appSource is the <script> body only, so the card's markup lives outside it; assert the
    // renderer targets the card element instead, which is what actually couples them.
    ok(String(g.renderLedgerReconciliation).indexOf("getElementById('ledgerReconciliationCard')")!==-1,
       'the renderer must target the Diagnostics card');
    ok(g.appSource.indexOf('Diagnostics only — read-only')!==-1,
       'the view must state that it replaces nothing');
  });
  t('R9 reconciliation is deterministic and degrades safely',function(){
    const args={strategyId:'alex_g_sr_v1',startingBalance:10000,
      records:[ledgerTrade(),seededTrade()],storedBalance:10400};
    eq(JSON.stringify(g.ledgerBuildReconciliationReport(args)),
       JSON.stringify(g.ledgerBuildReconciliationReport(args)),'same inputs, same report');
    const noStored=g.ledgerBuildReconciliationReport({strategyId:'alex_g_sr_v1',startingBalance:10000,
      records:[ledgerTrade()]});
    eq(noStored.fields.filter(function(f){return f.field==='balance';})[0].status,'MATCHES',
       'an absent stored value must not manufacture a delta');
    const empty=g.ledgerBuildReconciliationReport({});
    ok(empty.fields.length>=8,'an empty account still produces a full report');
    eq(empty.overall,'MATCHES');
  });

  // ══ GROUP 19 — v12.18.0 REPORTING AUTHORITY TRANSITION ═════════════════════════════════
  // Reporting only, behind a flag that defaults OFF. Sizing, replay and evidence untouched.

  t('A1 the flag defaults OFF, for every strategy',function(){
    const f=g.getReportingAuthorityFlag();
    eq(f.enabled,false,'the master switch must ship OFF');
    Object.keys(f.byStrategy).forEach(function(k){
      eq(f.byStrategy[k],false,k+' must ship OFF');
    });
    eq(g.ledgerReportingAuthorityEnabled('alex_g_sr_v1'),false);
    eq(g.ledgerReportingAuthorityEnabled('current_strategy'),false);
    eq(g.ledgerReportingAuthorityEnabled(null),false);
    ok(f.blockers&&f.blockers.current_strategy,'JVM must record WHY it is not yet eligible');
  });
  t('A2 with the flag OFF the stored value is returned unchanged',function(){
    const r=g.ledgerReportingFigures('alex_g_sr_v1',10200,10000,[seededTrade()]);
    eq(r.authoritative,false);
    eq(r.source,'STORED');
    eq(r.balance,10200,'the stored balance must pass through untouched');
    eq(r.derived,null,'and no derivation is even performed');
  });
  t('A3 with the flag ON the ledger becomes the reported figure',function(){
    const f=g.getReportingAuthorityFlag();
    const prev={enabled:f.enabled,alex:f.byStrategy.alex_g_sr_v1};
    try{
      f.enabled=true; f.byStrategy.alex_g_sr_v1=true;
      eq(g.ledgerReportingAuthorityEnabled('alex_g_sr_v1'),true);
      eq(g.ledgerReportingAuthorityEnabled('current_strategy'),false,'other strategies stay off');
      const r=g.ledgerReportingFigures('alex_g_sr_v1',10200,10000,[seededTrade()]);
      eq(r.authoritative,true); eq(r.source,'LEDGER_DERIVED');
      eq(r.balance,10000,'the seeded record no longer inflates the reported balance');
      eq(r.realizedPnl,0);
      ok(r.derived&&r.derived.excludedEvents.length===1,'and the excluded record is still carried');
    } finally { f.enabled=prev.enabled; f.byStrategy.alex_g_sr_v1=prev.alex; }
  });
  t('A4 the master switch alone cannot enable a strategy',function(){
    const f=g.getReportingAuthorityFlag();
    const prev=f.enabled;
    try{
      f.enabled=true;                       // per-strategy flags remain false
      eq(g.ledgerReportingAuthorityEnabled('alex_g_sr_v1'),false,'both switches are required');
    } finally { f.enabled=prev; }
  });
  t('A5 a derivation failure falls back to the stored value, never to nothing',function(){
    const f=g.getReportingAuthorityFlag();
    const prev={enabled:f.enabled,alex:f.byStrategy.alex_g_sr_v1};
    try{
      f.enabled=true; f.byStrategy.alex_g_sr_v1=true;
      // records that cannot be derived from must not blank the display
      const r=g.ledgerReportingFigures('alex_g_sr_v1',10200,10000,null);
      ok(r.balance===10200||r.balance===10000,'a figure must always be produced');
      ok(typeof r.balance==='number','and it must be a number, never null');
    } finally { f.enabled=prev.enabled; f.byStrategy.alex_g_sr_v1=prev.alex; }
  });
  t('A6 POSITION SIZING is untouched by the flag',function(){
    // sizing reads the STORED balance through the protected constructor; the flag cannot reach it
    const protectedList=g.getBaselineAlexFunctions();
    ok(protectedList.indexOf('alexGConstructLivePosition')!==-1,'trade construction must stay protected');
    ['ledgerReportingFigures','ledgerReportingAuthorityEnabled','LEDGER_REPORTING_AUTHORITY']
      .forEach(function(n){
        eq(String(g.alexGConstructLivePosition||'').indexOf(n),-1,'sizing must not reference '+n);
      });
    ok(g.appSource.indexOf('alexGConstructLivePosition(setup,datasets,ba,RULES_ALEXG.config,alexGAccount.balance')!==-1,
       'the sizing call must still pass the STORED balance');
    const layer=String(g.ledgerReportingFigures)+String(g.ledgerReportingAuthorityEnabled);
    ['riskAmount','positionSize','openPaperPosition','alexGConstructLivePosition']
      .forEach(function(n){ eq(layer.indexOf(n),-1,'the reporting layer must never reference '+n); });
  });
  t('A7 the reporting layer writes nothing',function(){
    const layer=String(g.ledgerReportingFigures)+String(g.ledgerReportingAuthorityEnabled);
    ['localStorage','commitAlexGLedger','saveAlexG','alexGAccount.balance=','paperAccount.balance=',
     '.splice(','delete '].forEach(function(n){
      eq(layer.indexOf(n),-1,'the reporting layer must never '+n);
    });
    const acct={balance:10200,closedPositions:[seededTrade()],openPositions:[]};
    const before=JSON.stringify(acct);
    g.ledgerReportingFigures('alex_g_sr_v1',acct.balance,10000,acct.closedPositions);
    eq(JSON.stringify(acct),before,'accounts must be byte-identical afterwards');
  });
  t('A8 display seams route through the resolver and disclose the source',function(){
    const panel=g.getSource('function renderAlexGLivePanel()');
    ok(panel.indexOf("ledgerReportingFigures('alex_g_sr_v1'")!==-1,'the live panel must ask the resolver');
    ok(panel.indexOf('ledger-derived')!==-1,'and must label a derived figure as derived');
    ok(panel.indexOf('reporting.authoritative?reporting.realizedPnl')!==-1,'P&L must follow the same switch');
    ok(g.appSource.indexOf('ledgerReportingFigures(entry.manifest.id,account.balance,10000,closedVisible)')!==-1,
       'the dashboard must route every registered strategy through it');
  });
  t('A9 Diagnostics reconciliation remains available and unaffected',function(){
    ok(typeof g.ledgerBuildReconciliationReport==='function','reconciliation must remain permanent');
    const rep=g.ledgerBuildReconciliationReport({strategyId:'alex_g_sr_v1',startingBalance:10000,
      records:[seededTrade()],storedBalance:10200});
    eq(rep.overall,'EXPLAINED_BY_EXCLUSIONS','and must keep reconciling derived against stored');
    eq(rep.readOnly,true);
    const f=g.getReportingAuthorityFlag();
    const prev={enabled:f.enabled,alex:f.byStrategy.alex_g_sr_v1};
    try{
      f.enabled=true; f.byStrategy.alex_g_sr_v1=true;
      const rep2=g.ledgerBuildReconciliationReport({strategyId:'alex_g_sr_v1',startingBalance:10000,
        records:[seededTrade()],storedBalance:10200});
      eq(JSON.stringify(rep2),JSON.stringify(rep),'the flag must not change what reconciliation reports');
    } finally { f.enabled=prev.enabled; f.byStrategy.alex_g_sr_v1=prev.alex; }
  });
  t('A10 replay and evidence are untouched by the transition',function(){
    eq(String(g.alexGComputeReplayStats).indexOf('ledgerReporting'),-1,'replay stats must not consult the flag');
    const p=builtPackage();
    const before=g.evidenceCanonicalize(p);
    g.ledgerReportingFigures('alex_g_sr_v1',10200,10000,[seededTrade()]);
    eq(g.evidenceCanonicalize(p),before,'reporting must not touch evidence');
  });

  return out;
}
