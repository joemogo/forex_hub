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
      reactionId:'AGR|r1',zoneTouchNumber:3,zoneStrength:4,zoneQualityAtQualification:'A',
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

  t('E12 the import path routes a known package through the EXP-001 decision function',function(){
    const src=String(g.evidenceImportPackageObject);
    ok(src.indexOf('evidenceEvaluateExportReimport')!==-1,'a duplicate must go through the decision');
    ok(src.indexOf('EXPORT_VERIFIED_BY_REIMPORT')!==-1,'a verified re-import must report itself');
    ok(src.indexOf('evidenceBuildVerifiedExportState')!==-1,'and mark the stored package verified');
    ok(src.indexOf('DUPLICATE_CONFLICTING_HASH')!==-1,'a conflicting duplicate must still be rejected');
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
    eq(layer.indexOf('.delete('),-1,'no evidence code path may delete a stored package');
    eq(layer.indexOf('.clear()'),-1,'no evidence code path may clear the package store');
    eq(layer.indexOf('deleteDatabase'),-1,'no evidence code path may drop the database');
    // The only write-back permitted on an existing package is recording an export outcome.
    ok(String(g.evidenceUpdateExportState).indexOf('existing.export=exportState')!==-1);
  });

  return out;
}
