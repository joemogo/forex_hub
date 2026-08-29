// G-2 — per-sweep trade-eligibility validity (MOGO-024).
//
// THE DEFECT THESE FIXTURES PIN. runAutoTopDownScan() is the only writer of
// scanData[pair].weekly/daily/fh/bucket -- the trade-eligibility state -- and it runs solely on
// autoScanTimer, which toggleAutoScan() clears when Auto Scan is switched off. checkAutoTrades()
// runs in a different loop (scanAll) on a different cadence and reads that state every sweep. So
// with Auto Trading ON and Auto Scan OFF, an arbitrarily old 'Active watch' plus an arbitrarily
// old W/D/H4 snapshot went on authorising real paper entries indefinitely. The same hole opened
// for a single pair whose top-down refresh threw mid-sweep.
//
// WHAT IS ASSERTED, AND WHAT IS NOT. runAutoTopDownScan() is async and the JXA harness cannot
// resolve a genuine await -- the same permanent, documented limitation recorded for runDiagnostics()
// in v12.1.1 and for simulateTrueMTFReplay() in v12.1.2. These fixtures therefore drive the real,
// unmodified synchronous pieces (the lifecycle helpers, htfSnapshotOf, htfAlignmentPasses) in the
// exact order the production sweep drives them, and a separate source-order assertion proves the
// production sweep really does call them that way. That last fixture is what kills the
// "delete the production wiring but keep the helpers" mutation, which every behavioural fixture
// here would otherwise survive.
//
// NO THRESHOLD IS TESTED because none exists. The only question asked anywhere below is whether a
// COMPLETE refresh for this pair finished in the CURRENT generation.
function runG2Fixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,detail:detail||''});};

  const PAIR='EUR/USD';
  const OP='EUR_USD';
  const OTHER='GBP/USD';
  const OTHER_OP='GBP_USD';

  // An aligned, otherwise fully qualifying snapshot. If freshness were not enforced, this is
  // exactly the shape that would authorise a trade.
  function alignedScanData(){
    return {
      'EUR/USD':{weekly:'Bullish',daily:'Bullish',fh:'Bullish',bucket:'Active watch',grade:'A',
                 notes:'Auto-scanned 1 Jan, 00:00'},
      'GBP/USD':{weekly:'Bullish',daily:'Bullish',fh:'Bullish',bucket:'Active watch',grade:'A',
                 notes:'Auto-scanned 1 Jan, 00:00'}
    };
  }
  // Reproduces runAutoTopDownScan()'s success path ordering for one pair.
  function sweepSucceeds(pairs){
    const gen=g.beginGen();
    pairs.forEach(p=>g.markInProgress(p,gen));
    pairs.forEach(p=>g.markFresh(p,gen));
    return gen;
  }

  // ── G2.1 — a failed refresh must block a stale Active watch ──────────────────────────────
  (function(){
    g.resetEligibility();
    g.setScanData(alignedScanData());
    const gen0=sweepSucceeds([PAIR]);
    const before=g.htfSnapshotOf(OP);
    assert('G2.1 precondition: a completed sweep DOES yield a snapshot',
      before!==null && before.weekly==='Bullish', JSON.stringify(before));

    // New sweep begins; this pair's refresh throws.
    const gen1=g.beginGen();
    g.markInProgress(PAIR,gen1);
    g.markFailed(PAIR,gen1);

    const snap=g.htfSnapshotOf(OP);
    assert('G2.1 failed refresh yields NO snapshot (stale Active watch cannot authorise)',
      snap===null, String(snap));
    // The refusal must be attributable, not incidental.
    const gate=g.htfAlignmentPasses(snap);
    assert('G2.1 refusal is attributable to a missing current-sweep snapshot',
      gate && gate.pass===false && gate.code==='HTF_SNAPSHOT_MISSING',
      gate?gate.code:'no gate result');
    assert('G2.1 the stale bucket itself is deliberately NOT cleared (display/diagnostics intact)',
      g.getScanData()[PAIR].bucket==='Active watch', g.getScanData()[PAIR].bucket);
    assert('G2.1 status is reported as FAILED, not merely absent',
      g.statusOf(PAIR)==='FAILED', g.statusOf(PAIR));
    assert('G2.1 generations advanced', gen1===gen0+1, gen0+' -> '+gen1);
  })();

  // ── G2.2 — POSITIVE CONTROL: a successful refresh must keep trading normal ───────────────
  // Without this, every assertion above is satisfied by a function that returns null forever.
  (function(){
    g.resetEligibility();
    g.setScanData(alignedScanData());
    sweepSucceeds([PAIR]);
    const snap=g.htfSnapshotOf(OP);
    assert('G2.2 successful refresh yields a complete snapshot',
      snap!==null && snap.weekly==='Bullish' && snap.daily==='Bullish' && snap.fh==='Bullish',
      JSON.stringify(snap));
    const gate=g.htfAlignmentPasses(snap);
    assert('G2.2 the protected HTF gate PASSES on a fresh aligned snapshot',
      gate && gate.pass===true, gate?gate.code||'pass':'no gate result');
    assert('G2.2 status is FRESH', g.statusOf(PAIR)==='FRESH', g.statusOf(PAIR));
  })();

  // ── G2.3 — failure then recovery: no permanent disablement ───────────────────────────────
  (function(){
    g.resetEligibility();
    g.setScanData(alignedScanData());
    const gen1=g.beginGen(); g.markInProgress(PAIR,gen1); g.markFailed(PAIR,gen1);
    assert('G2.3 blocked after the failing sweep', g.htfSnapshotOf(OP)===null,'');
    sweepSucceeds([PAIR]);
    const snap=g.htfSnapshotOf(OP);
    assert('G2.3 a later COMPLETE sweep restores eligibility',
      snap!==null && g.statusOf(PAIR)==='FRESH', g.statusOf(PAIR));
    assert('G2.3 and the gate passes again', g.htfAlignmentPasses(snap).pass===true,'');
    // Direct recovery, WITHOUT the intervening IN_PROGRESS mark. sweepSucceeds() above overwrites
    // the FAILED entry with IN_PROGRESS before marking FRESH, so it cannot see a jvmMarkEligibilityFresh
    // that refuses to overwrite a FAILED pair -- mutation M5 survived precisely there. This asserts
    // the clearing property itself rather than a sequence that happens to avoid needing it.
    g.resetEligibility();
    const genF=g.beginGen(); g.markFailed(PAIR,genF);
    g.markFresh(PAIR,genF);
    assert('G2.3 marking FRESH clears a FAILED pair (no sticky failure)',
      g.statusOf(PAIR)==='FRESH' && g.htfSnapshotOf(OP)!==null, g.statusOf(PAIR));
  })();

  // ── G2.4 — partial write: a mixed old/new snapshot must be rejected ──────────────────────
  (function(){
    g.resetEligibility();
    const sd=alignedScanData();
    g.setScanData(sd);
    sweepSucceeds([PAIR]);                       // a good prior sweep exists
    // New sweep: weekly and daily are rewritten, then the refresh dies before fh/bucket.
    const gen=g.beginGen();
    g.markInProgress(PAIR,gen);
    sd[PAIR].weekly='Bearish';
    sd[PAIR].daily='Bearish';
    g.setScanData(sd);
    assert('G2.4 a half-written snapshot is rejected while IN_PROGRESS',
      g.htfSnapshotOf(OP)===null, String(g.statusOf(PAIR)));
    g.markFailed(PAIR,gen);
    assert('G2.4 and remains rejected once the sweep records the failure',
      g.htfSnapshotOf(OP)===null,'');
    assert('G2.4 the mixed state was never marked FRESH',
      g.statusOf(PAIR)!=='FRESH', g.statusOf(PAIR));
  })();

  // ── G2.5 — a snapshot from sweep N cannot authorise during sweep N+1 ─────────────────────
  (function(){
    g.resetEligibility();
    g.setScanData(alignedScanData());
    sweepSucceeds([PAIR]);
    assert('G2.5 valid during its own generation', g.htfSnapshotOf(OP)!==null,'');
    g.beginGen();                                 // N+1 starts; this pair is never refreshed
    assert('G2.5 the SAME scanData is refused in the next generation',
      g.htfSnapshotOf(OP)===null,'');
    assert('G2.5 reported as PRIOR_GENERATION rather than FAILED',
      g.statusOf(PAIR)==='PRIOR_GENERATION', g.statusOf(PAIR));
  })();

  // ── G2.6 — older persisted state with no validity metadata fails closed ──────────────────
  // This is the reload case: fxhub_scan rehydrates, the ephemeral map does not.
  (function(){
    g.resetEligibility();
    g.setScanData(alignedScanData());
    assert('G2.6 rehydrated scanData cannot authorise before any sweep completes',
      g.htfSnapshotOf(OP)===null,'');
    assert('G2.6 status is UNKNOWN, not silently valid',
      g.statusOf(PAIR)==='UNKNOWN', g.statusOf(PAIR));
    sweepSucceeds([PAIR]);
    assert('G2.6 one complete sweep makes it usable', g.htfSnapshotOf(OP)!==null,'');
  })();

  // ── G2.7 — discriminator: the block must be about FRESHNESS, not the bucket value ────────
  (function(){
    g.resetEligibility();
    const sd=alignedScanData();
    sd[PAIR].bucket='Ranging / no break';
    g.setScanData(sd);
    sweepSucceeds([PAIR]);
    const snap=g.htfSnapshotOf(OP);
    assert('G2.7 a non-eligible bucket still yields a snapshot when the refresh SUCCEEDED',
      snap!==null, 'freshness and bucket are independent concerns');
    assert('G2.7 the HTF gate is indifferent to the bucket value',
      g.htfAlignmentPasses(snap).pass===true,'');
    // Proves G2.1 is not passing merely because something about the pair is unusual.
    const gen=g.beginGen(); g.markInProgress(PAIR,gen); g.markFailed(PAIR,gen);
    assert('G2.7 and the SAME pair is blocked once its refresh fails',
      g.htfSnapshotOf(OP)===null,'');
  })();

  // ── G2.8 — Auto Scan OFF: the reported toggle combination ────────────────────────────────
  // The original G-2 mechanism, now closed at its source.
  (function(){
    g.resetEligibility();
    g.setScanData(alignedScanData());
    sweepSucceeds([PAIR]);
    assert('G2.8 eligible while the refresh source is running', g.htfSnapshotOf(OP)!==null,'');
    g.toggleAutoScan(false);
    assert('G2.8 switching Auto Scan OFF invalidates eligibility immediately',
      g.htfSnapshotOf(OP)===null, g.statusOf(PAIR));
    assert('G2.8 Auto Scan really is off', g.getAutoScan().enabled===false,'');
    assert('G2.8 reported as PRIOR_GENERATION (the state can no longer be refreshed)',
      g.statusOf(PAIR)==='PRIOR_GENERATION', g.statusOf(PAIR));
  })();

  // ── G2.9 — multi-pair isolation: one failure must not disable the sweep ──────────────────
  // The control against the over-correction "invalidate everything on any error".
  (function(){
    g.resetEligibility();
    g.setScanData(alignedScanData());
    const gen=g.beginGen();
    g.markInProgress(PAIR,gen); g.markInProgress(OTHER,gen);
    g.markFailed(PAIR,gen);                       // one pair throws
    g.markFresh(OTHER,gen);                       // the other completes
    assert('G2.9 the failing pair is blocked', g.htfSnapshotOf(OP)===null, g.statusOf(PAIR));
    assert('G2.9 the succeeding pair REMAINS eligible',
      g.htfSnapshotOf(OTHER_OP)!==null, g.statusOf(OTHER));
    assert('G2.9 one error does not disable the whole sweep',
      g.statusOf(OTHER)==='FRESH' && g.statusOf(PAIR)==='FAILED',
      g.statusOf(PAIR)+' / '+g.statusOf(OTHER));
  })();

  // ── G2.10 — the production sweep is actually wired to the lifecycle ──────────────────────
  // Every fixture above drives the helpers directly, so all of them survive deleting the calls
  // from runAutoTopDownScan(). This asserts the real source, in order.
  (function(){
    const src=g.getAppSource?g.getAppSource():null;
    if(src===null){ assert('G2.10 source available for the wiring check',false,'no source bridge'); return; }
    const fn=src.slice(src.indexOf('async function runAutoTopDownScan()'));
    const body=fn.slice(0,fn.indexOf('\nfunction ')>0?fn.indexOf('\nfunction '):20000);
    const iBegin=body.indexOf('jvmBeginEligibilityGeneration()');
    const iProg=body.indexOf('jvmMarkEligibilityInProgress');
    const iFresh=body.indexOf('jvmMarkEligibilityFresh');
    const iFail=body.indexOf('jvmMarkEligibilityFailed');
    assert('G2.10 the sweep begins a generation',iBegin>-1,'');
    assert('G2.10 the sweep marks pairs IN_PROGRESS',iProg>-1,'');
    assert('G2.10 the sweep marks FRESH on success',iFresh>-1,'');
    assert('G2.10 the sweep marks FAILED on throw',iFail>-1,'');
    assert('G2.10 invalidation precedes any per-pair marking',
      iBegin>-1 && iProg>-1 && iBegin<iProg, iBegin+' < '+iProg);
    assert('G2.10 IN_PROGRESS precedes FRESH (never marked valid before the sweep runs)',
      iProg>-1 && iFresh>-1 && iProg<iFresh, iProg+' < '+iFresh);
    // htfSnapshotOf must consult the predicate, or the gate is decorative.
    assert('G2.10 htfSnapshotOf consults jvmEligibilityIsCurrent',
      src.indexOf('if(!jvmEligibilityIsCurrent(sk)) return null;')>-1,'');
    assert('G2.10 toggleAutoScan invalidates when switching off',
      src.indexOf('jvmInvalidateAllEligibility();')>-1,'');
    // A per-pair failure must mark THAT pair, never invalidate the sweep. The behavioural
    // multi-pair control (G2.9) drives the helpers directly and therefore cannot see a mutation
    // inside the production catch block -- M7 survived there. Asserted on the real source.
    const iCatch=body.indexOf('Auto-scan FAILED');
    const tail=iCatch>-1?body.slice(iCatch,iCatch+700):'';
    assert('G2.10 the per-pair catch marks only that pair FAILED',
      tail.indexOf('jvmMarkEligibilityFailed(pair')>-1, tail?'catch block found':'catch block NOT found');
    assert('G2.10 the per-pair catch does NOT invalidate every pair',
      tail.indexOf('jvmInvalidateAllEligibility')===-1,
      'one instrument failing must not disable the sweep');
  })();

  return results;
}
