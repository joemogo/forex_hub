// MOGO-002.8A — ALEX v1.1 Release fixture suite.
//
// Verifies the v1.1 release against its stated success criteria:
//   version identity, historical preservation, open-position continuity,
//   Monday-Wednesday eligibility, realized R, chronological equity,
//   current vs maximum drawdown, configured starting balance,
//   dead-config omission, no duplicate trades, and journal integrity.
//
// Every fixture calls the REAL functions from index.html -- none is re-implemented.
function runAlexV11ReleaseFixtures(g){
  const out=[];
  function t(name,fn){
    try{ const d=fn(); out.push({name,pass:true,detail:d||''}); }
    catch(e){ out.push({name,pass:false,detail:(e&&e.message)?e.message:String(e)}); }
  }
  function eq(a,b,m){ if(a!==b) throw new Error((m||'')+' expected '+JSON.stringify(b)+', got '+JSON.stringify(a)); }
  function ok(v,m){ if(!v) throw new Error(m||'expected truthy'); }
  function close(a,b,tol,m){ if(Math.abs(a-b)>(tol||1e-9)) throw new Error((m||'')+' expected ~'+b+', got '+a); }

  // Monday 2026-01-05, Tue 06, Wed 07, Thu 08, Fri 09, Sat 10, Sun 11 (all UTC)
  const MON=Date.UTC(2026,0,5,12,0,0), TUE=Date.UTC(2026,0,6,12,0,0), WED=Date.UTC(2026,0,7,12,0,0);
  const THU=Date.UTC(2026,0,8,12,0,0), FRI=Date.UTC(2026,0,9,12,0,0);
  const SAT=Date.UTC(2026,0,10,12,0,0), SUN=Date.UTC(2026,0,11,12,0,0);

  // ── A. VERSION IDENTITY ───────────────────────────────────────────────────
  t('A1 v1.1 rule version constant is alex_g_sr_v1_1',function(){
    eq(g.getAlexV11RuleVersion(),'alex_g_sr_v1_1');
  });
  t('A2 v1.1 declares inheritance from v1.0',function(){
    const v=g.getRulesAlexGV11();
    eq(v.inheritsFrom,'alex_g_sr_v1');
    eq(v.engineParametersUnchangedFrom,'alex_g_sr_v1');
  });
  t('A3 RULES_ALEXG (protected) still reports alex_g_sr_v1',function(){
    eq(g.getRulesAlexG().ruleVersion,'alex_g_sr_v1');
  });
  t('A4 provenance stamp carries the v1.1 release version',function(){
    const r=g.alexGStrategyVersionReference();
    eq(r.strategyVersion,'alex_g_sr_v1_1');
  });
  t('A5 specification version remains v1.0 (engine params unchanged)',function(){
    const r=g.alexGStrategyVersionReference();
    eq(r.strategySpecificationVersion,'alex_g_sr_v1','a v1.1 release must not claim a new SPEC version while engine params are identical');
  });
  t('A6 a newly stamped trade carries strategyVersion v1.1',function(){
    const pos=g.alexGStampTradeProvenance({tradeId:'AGT|X',entry:1,stop:0.9});
    eq(pos.strategyProvenance.strategyVersion,'alex_g_sr_v1_1');
  });
  t('A7 stamping never overwrites an existing stamp (v1.0 trade stays v1.0)',function(){
    const legacy={tradeId:'AGT|OLD',strategyProvenance:{strategySpecificationVersion:'alex_g_sr_v1',
      implementationVersion:'alex_g_sr_v1.impl.1',ruleSetHash:'h',configurationHash:'c'}};
    g.alexGStampTradeProvenance(legacy);
    eq(legacy.strategyProvenance.strategyVersion,undefined,'a pre-v1.1 trade must never be back-filled with a v1.1 version');
  });
  t('A8 rule registry is complete and every entry is well-formed',function(){
    const reg=g.getRulesAlexGV11().ruleRegistry;
    ok(reg.length>=25,'expected the full active-rule registry, got '+reg.length);
    reg.forEach(function(r){
      ok(r.ruleId&&r.name&&r.origin&&r.evidence&&r.versionIntroduced,'incomplete registry row: '+JSON.stringify(r));
      ok(typeof r.enabled==='boolean','enabled must be boolean: '+r.ruleId);
      ok(['Alex Explicit','MOGO Operationalization','Existing MOGO Design'].indexOf(r.origin)>=0,
         'illegal origin on '+r.ruleId+': '+r.origin);
    });
    return reg.length+' rules';
  });
  t('A9 the five v1.1 rules are registered against v1.1',function(){
    const reg=g.getRulesAlexGV11().ruleRegistry;
    ['ALEX_V11_001','ALEX_V11_002','ALEX_V11_003','ALEX_V11_004','ALEX_V11_005'].forEach(function(id){
      const r=reg.filter(function(x){return x.ruleId===id;})[0];
      ok(r,'missing '+id);
      eq(r.versionIntroduced,'alex_g_sr_v1_1',id+' versionIntroduced');
    });
  });
  t('A10 deferred rules are recorded, not silently dropped',function(){
    const d=g.getRulesAlexGV11().deferredRules;
    ok(d.length>=5,'expected the deferred list');
    ['AXR-011','AXR-020','AXR-021','AXR-030','AXR-081'].forEach(function(id){
      ok(d.filter(function(x){return x.ruleId===id;}).length===1,'missing deferred '+id);
    });
  });

  // ── B. MONDAY-WEDNESDAY ELIGIBILITY (ALEX_V11_001) ────────────────────────
  t('B1 Monday is eligible',function(){ eq(g.alexGV11EntryDayEligible(MON),true); });
  t('B2 Tuesday is eligible',function(){ eq(g.alexGV11EntryDayEligible(TUE),true); });
  t('B3 Wednesday is eligible',function(){ eq(g.alexGV11EntryDayEligible(WED),true); });
  t('B4 Thursday is NOT eligible',function(){ eq(g.alexGV11EntryDayEligible(THU),false); });
  t('B5 Friday is NOT eligible',function(){ eq(g.alexGV11EntryDayEligible(FRI),false); });
  t('B6 Saturday is NOT eligible',function(){ eq(g.alexGV11EntryDayEligible(SAT),false); });
  t('B7 Sunday is NOT eligible',function(){ eq(g.alexGV11EntryDayEligible(SUN),false); });
  t('B8 the rule uses UTC, not local time',function(){
    // 2026-01-08T00:30Z is Thursday UTC. Must be rejected regardless of host timezone.
    eq(g.alexGV11EntryDayEligible(Date.UTC(2026,0,8,0,30,0)),false);
    // 2026-01-07T23:30Z is still Wednesday UTC.
    eq(g.alexGV11EntryDayEligible(Date.UTC(2026,0,7,23,30,0)),true);
  });
  t('B9 disabling the rule allows every day (fail-open, never blocks)',function(){
    const off={v11Config:{entryDayRuleEnabled:false,entryDaysOfWeekUTC:[1,2,3]}};
    [MON,THU,SAT,SUN].forEach(function(d){ eq(g.alexGV11EntryDayEligible(d,off),true); });
  });
  t('B10 an unreadable timestamp never blocks a trade',function(){
    eq(g.alexGV11EntryDayEligible(NaN),true);
    eq(g.alexGV11EntryDayEligible(undefined),true);
  });
  t('B11 an empty allowed-days list never blocks a trade',function(){
    const empty={v11Config:{entryDayRuleEnabled:true,entryDaysOfWeekUTC:[]}};
    eq(g.alexGV11EntryDayEligible(THU,empty),true);
  });
  t('B12 configured days are exactly Mon/Tue/Wed',function(){
    const d=g.getRulesAlexGV11().v11Config.entryDaysOfWeekUTC;
    eq(JSON.stringify(d),JSON.stringify([1,2,3]));
  });
  t('B13 the v1.1 gate agrees with the pre-existing isPreferredTradingDay',function(){
    [MON,TUE,WED,THU,FRI,SAT,SUN].forEach(function(ms){
      eq(g.alexGV11EntryDayEligible(ms),g.isPreferredTradingDay(new Date(ms)),
         'divergence at '+new Date(ms).toUTCString());
    });
  });

  // ── C. REALIZED R (ALEX_V11_002) ──────────────────────────────────────────
  t('C1 a buy that reaches exactly 2R reports 2.00R',function(){
    close(g.alexGRealizedR({direction:'buy',entry:1.1000,stop:1.0900,exitPrice:1.1200}),2.0,1e-9);
  });
  t('C2 a buy stopped out reports -1.00R',function(){
    close(g.alexGRealizedR({direction:'buy',entry:1.1000,stop:1.0900,exitPrice:1.0900}),-1.0,1e-9);
  });
  t('C3 a sell that reaches 2R reports 2.00R',function(){
    close(g.alexGRealizedR({direction:'sell',entry:1.1000,stop:1.1100,exitPrice:1.0800}),2.0,1e-9);
  });
  t('C4 a sell stopped out reports -1.00R',function(){
    close(g.alexGRealizedR({direction:'sell',entry:1.1000,stop:1.1100,exitPrice:1.1100}),-1.0,1e-9);
  });
  t('C5 REALIZED R DIFFERS FROM plannedRR when the exit slipped',function(){
    // The v1.0 defect: resultR was a fixed +plannedRR regardless of the actual exit.
    const slipped={direction:'buy',entry:1.1000,stop:1.0900,exitPrice:1.1180,result:'Win',resultR:2.0};
    const r=g.alexGRealizedR(slipped);
    close(r,1.8,1e-9,'realized R must reflect the actual exit');
    ok(r!==slipped.resultR,'realized R must not simply echo the frozen plannedRR');
  });
  t('C6 a partial-loss exit is reported honestly',function(){
    close(g.alexGRealizedR({direction:'buy',entry:1.1000,stop:1.0900,exitPrice:1.0950}),-0.5,1e-9);
  });
  t('C7 zero risk distance returns null rather than Infinity',function(){
    eq(g.alexGRealizedR({direction:'buy',entry:1.1,stop:1.1,exitPrice:1.2}),null);
  });
  t('C8 missing or non-numeric fields return null',function(){
    eq(g.alexGRealizedR(null),null);
    eq(g.alexGRealizedR({}),null);
    eq(g.alexGRealizedR({direction:'buy',entry:1.1,stop:1.0}),null);
    eq(g.alexGRealizedR({direction:'buy',entry:'x',stop:1.0,exitPrice:1.2}),null);
  });
  t('C9 realized R never mutates the trade record',function(){
    const rec={direction:'buy',entry:1.1,stop:1.09,exitPrice:1.12,result:'Win',resultR:2.0};
    const snapshot=JSON.stringify(rec);
    g.alexGRealizedR(rec);
    eq(JSON.stringify(rec),snapshot,'record must be read-only to the calculation');
  });

  // ── D. EQUITY, DRAWDOWN, ORDERING (ALEX_V11_003) ──────────────────────────
  function trade(id,closedAt,result,entry,stop,exitPrice,dir){
    return{tradeId:id,closedAt:closedAt,result:result,direction:dir||'buy',
           entry:entry,stop:stop,exitPrice:exitPrice,resultR:(result==='Win'?2:-1)};
  }
  // Chronological curve: +2, -1, -1, +2  => equity 2,1,0,2 ; peak 2 ; maxDD 2 ; currentDD 0
  const CURVE=[
    trade('T1','2026-01-05T10:00:00Z','Win' ,1.1,1.09,1.12),
    trade('T2','2026-01-06T10:00:00Z','Loss',1.1,1.09,1.09),
    trade('T3','2026-01-07T10:00:00Z','Loss',1.1,1.09,1.09),
    trade('T4','2026-01-08T10:00:00Z','Win' ,1.1,1.09,1.12)
  ];
  t('D1 equity is walked chronologically even when stored newest-first',function(){
    const newestFirst=CURVE.slice().reverse(); // how closedPositions is actually stored
    const a=g.alexGComputeEquityStats(newestFirst);
    const b=g.alexGComputeEquityStats(CURVE.slice());
    eq(a.maxDrawdownR,b.maxDrawdownR,'storage order must not change the curve');
    eq(a.currentDrawdownR,b.currentDrawdownR);
    close(a.netR,b.netR,1e-9);
  });
  t('D2 maximum drawdown is computed correctly',function(){
    const s=g.alexGComputeEquityStats(CURVE.slice());
    close(s.maxDrawdownR,2.0,1e-9,'peak 2 -> trough 0');
  });
  t('D3 current drawdown is distinct from maximum drawdown',function(){
    const s=g.alexGComputeEquityStats(CURVE.slice());
    close(s.currentDrawdownR,0.0,1e-9,'curve recovered to its peak');
    ok(s.currentDrawdownR!==s.maxDrawdownR,'the two measures must not be the same number here');
  });
  t('D4 current drawdown is non-zero while below the peak',function(){
    const s=g.alexGComputeEquityStats(CURVE.slice(0,3)); // +2,-1,-1 -> equity 0, peak 2
    close(s.currentDrawdownR,2.0,1e-9);
    close(s.maxDrawdownR,2.0,1e-9);
  });
  t('D5 net R uses realized values, not frozen plannedRR',function(){
    const slipped=[trade('S1','2026-01-05T10:00:00Z','Win',1.1000,1.0900,1.1180)];
    const s=g.alexGComputeEquityStats(slipped);
    close(s.netR,1.8,1e-9,'realized');
    close(s.netPlannedR,2.0,1e-9,'legacy planned figure retained for comparison');
  });
  t('D6 undecided trades are excluded from the curve',function(){
    const mixed=CURVE.concat([{tradeId:'OPEN',result:null,closedAt:null}]);
    const s=g.alexGComputeEquityStats(mixed);
    eq(s.decidedCount,4);
  });
  t('D7 wins and losses are counted correctly',function(){
    const s=g.alexGComputeEquityStats(CURVE.slice());
    eq(s.wins,2); eq(s.losses,2);
  });
  t('D8 an empty account produces zeroes, never NaN',function(){
    const s=g.alexGComputeEquityStats([]);
    eq(s.decidedCount,0); eq(s.netR,0); eq(s.currentDrawdownR,0); eq(s.maxDrawdownR,0);
    ok(!isNaN(s.netR)&&!isNaN(s.maxDrawdownR));
  });
  t('D9 a legacy trade lacking price fields still contributes via resultR',function(){
    const legacy=[{tradeId:'L1',closedAt:'2026-01-05T10:00:00Z',result:'Win',resultR:2.0}];
    const s=g.alexGComputeEquityStats(legacy);
    close(s.netR,2.0,1e-9,'falls back to the stored resultR when prices are absent');
    eq(s.realizedCount,0,'and reports that it could not compute a realized value');
  });
  t('D10 equity stats never mutate the input array or its records',function(){
    const input=CURVE.slice();
    const snapshot=JSON.stringify(input);
    g.alexGComputeEquityStats(input);
    eq(JSON.stringify(input),snapshot);
  });

  // ── E. STARTING BALANCE (ALEX_V11_004) ────────────────────────────────────
  t('E1 configured starting balance is 10000',function(){
    eq(g.getRulesAlexGV11().v11Config.startingBalance,10000);
  });
  t('E2 alexGStartingBalance reads the account value when present',function(){
    const acct=g.getAlexGAccount();
    const prev=acct.startingBalance;
    acct.startingBalance=25000;
    try{ eq(g.alexGStartingBalance(),25000); }
    finally{ acct.startingBalance=prev; }
  });
  t('E3 a pre-v1.1 account without startingBalance falls back to config',function(){
    const acct=g.getAlexGAccount();
    const prev=acct.startingBalance;
    delete acct.startingBalance;
    try{ eq(g.alexGStartingBalance(),10000); }
    finally{ acct.startingBalance=prev; }
  });
  t('E4 default account is seeded with startingBalance',function(){
    eq(g.getAlexGAccount().startingBalance,10000);
  });

  // ── F. DEAD CONFIGURATION (reconciliation R-1..R-4) ────────────────────────
  t('F1 v1.1 does not re-declare the four dead v1.0 keys',function(){
    const c=g.getRulesAlexGV11().v11Config;
    ['zoneTimeframes','requireWick','minWickRatio','maxZoneAgeBars'].forEach(function(k){
      ok(!(k in c),'v1.1 must not re-declare dead key '+k);
    });
  });
  t('F2 the protected v1.0 config still contains them (untouched)',function(){
    const c=g.getRulesAlexG().config;
    ['zoneTimeframes','requireWick','minWickRatio','maxZoneAgeBars'].forEach(function(k){
      ok(k in c,'v1.0 protected config must be unchanged; missing '+k);
    });
  });

  // ── G. ENGINE PARAMETERS UNCHANGED (preservation criteria) ────────────────
  t('G1 stop, target and risk parameters are byte-identical to v1.0',function(){
    const c=g.getRulesAlexG().config;
    eq(c.stopATRBuffer,0.25); eq(c.minRR,2.0); eq(c.riskPercent,1.0);
  });
  t('G2 zone, touch and BOS parameters are unchanged',function(){
    const c=g.getRulesAlexG().config;
    eq(c.zoneClusterATRMultiplier,0.5); eq(c.atrPeriod,14);
    eq(c.rejectionConfirmWithinBars,1); eq(c.rejectionDisplacementATRMultiplier,0.25);
    eq(c.breakConfirmationCloses,1); eq(c.maxPenetrationsBeforeChoppyFlag,3);
    eq(c.choppyLookbackBars,50); eq(c.maxBarsBetweenBreakAndRetest,50);
  });
  t('G3 entry sequencing parameters are unchanged',function(){
    const c=g.getRulesAlexG().config;
    eq(c.maxLiveEntryDelayPips,5);
    eq(JSON.stringify(c.maxLiveSignalAgeMinutes),JSON.stringify({H1:60,H4:240,D:1440,W:10080}));
  });
  t('G4 REAL protected setup evaluators still qualify identically',function(){
    const cfg=g.getRulesAlexG().config;
    const zone={status:'validated',touches:[1,2,3,4],id:'Z'};
    eq(g.alexGEvaluateRepeatedReaction(zone,{},3,'clean',cfg).qualifies,true);
    eq(g.alexGEvaluateRepeatedReaction(zone,{},2,'clean',cfg).qualifies,false,'touchIndex<3 must still reject');
    eq(g.alexGEvaluateRepeatedReaction(zone,{},3,'choppy',cfg).qualifies,false,'choppy must still reject');
    eq(g.alexGEvaluateRepeatedReaction({status:'broken',touches:[1,2,3,4]},{},3,'clean',cfg).qualifies,false);
  });
  t('G5 REAL protected direction logic is unchanged',function(){
    eq(g.alexGDetermineTradeDirection({setupType:'A_repeatedReaction',zoneRoleAtQualification:'support'}).direction,'buy');
    eq(g.alexGDetermineTradeDirection({setupType:'A_repeatedReaction',zoneRoleAtQualification:'resistance'}).direction,'sell');
    eq(g.alexGDetermineTradeDirection({setupType:'B_breakRetest',brokenDirection:'downThroughSupport'}).direction,'sell');
    eq(g.alexGDetermineTradeDirection({setupType:'B_breakRetest',brokenDirection:'upThroughResistance'}).direction,'buy');
    eq(g.alexGDetermineTradeDirection({setupType:'A_repeatedReaction',zoneRoleAtQualification:'inside'}).direction,null);
  });
  t('G6 REAL protected zone-role logic is unchanged',function(){
    const z={low:1.1,high:1.2};
    eq(g.alexGZoneRole(z,1.25),'support');
    eq(g.alexGZoneRole(z,1.05),'resistance');
    eq(g.alexGZoneRole(z,1.15),'inside');
  });

  // ── H. HISTORICAL PRESERVATION ────────────────────────────────────────────
  t('H1 a v1.0 closed trade is not rewritten by any v1.1 calculation',function(){
    const v10={tradeId:'AGT|OLD1',closedAt:'2026-01-05T10:00:00Z',result:'Win',resultR:2.0,
      direction:'buy',entry:1.1,stop:1.09,exitPrice:1.1180,
      strategyProvenance:{strategySpecificationVersion:'alex_g_sr_v1',implementationVersion:'alex_g_sr_v1.impl.1',
        ruleSetHash:'h',configurationHash:'c'}};
    const snapshot=JSON.stringify(v10);
    g.alexGComputeEquityStats([v10]);
    g.alexGRealizedR(v10);
    g.alexGClassifyTradeProvenance(v10);
    eq(JSON.stringify(v10),snapshot,'a historical record must be byte-identical after v1.1 reporting');
  });
  t('H2 a v1.0 trade is still classified VERSIONED (not downgraded)',function(){
    const v10={strategyProvenance:{strategySpecificationVersion:'alex_g_sr_v1',
      implementationVersion:'alex_g_sr_v1.impl.1',ruleSetHash:'h',configurationHash:'c'}};
    eq(g.alexGClassifyTradeProvenance(v10),'VERSIONED');
  });
  t('H3 a legacy unversioned trade is still LEGACY_UNVERSIONED',function(){
    eq(g.alexGClassifyTradeProvenance({tradeId:'ANCIENT'}),'LEGACY_UNVERSIONED');
  });
  t('H4 mixed v1.0/v1.1 history is reported as MIXED, never averaged silently',function(){
    const mix=[
      {strategyProvenance:{strategySpecificationVersion:'alex_g_sr_v1',implementationVersion:'alex_g_sr_v1.impl.1',ruleSetHash:'h',configurationHash:'c'}},
      {tradeId:'ANCIENT'}
    ];
    const s=g.alexGProvenanceSummary(mix);
    eq(s.mixed,true);
    eq(s.reportable,'MIXED_VERSION');
  });
  t('H5 v1.1 reporting works on a history containing BOTH versions',function(){
    const both=[
      {tradeId:'V10',closedAt:'2026-01-05T10:00:00Z',result:'Win',resultR:2.0,direction:'buy',entry:1.1,stop:1.09,exitPrice:1.12},
      {tradeId:'V11',closedAt:'2026-01-06T10:00:00Z',result:'Loss',resultR:-1,direction:'buy',entry:1.2,stop:1.19,exitPrice:1.19,
       strategyProvenance:{strategyVersion:'alex_g_sr_v1_1'}}
    ];
    const s=g.alexGComputeEquityStats(both);
    eq(s.decidedCount,2);
    close(s.netR,1.0,1e-9);
  });

  // ── I. NO DUPLICATE TRADES ────────────────────────────────────────────────
  t('I1 the v1.1 gate does not alter duplicate-signal identity',function(){
    const setup={setupId:'AGS|alex_g_sr_v1|EUR_USD|H1|Z|A_repeatedReaction|R1'};
    eq(g.alexGLiveSignalId(setup),g.alexGLiveSignalId(setup),'signal id must stay deterministic');
  });
  t('I2 trade id derivation is unchanged by v1.1',function(){
    eq(g.alexGTradeId('AGS|X'),'AGT|AGS|X');
  });
  t('I3 the entry-day gate is pure -- calling it twice cannot open two trades',function(){
    const a=g.alexGV11EntryDayEligible(MON), b=g.alexGV11EntryDayEligible(MON);
    eq(a,b); eq(a,true);
  });

  // ── J. ENGINE / RELEASE WIRING ────────────────────────────────────────────
  t('J1 APP_VERSION is at or beyond the v1.1 release engine',function(){
    // Asserts the release FLOOR, not an exact patch -- v1.1 remains the active
    // strategy version across 12.7.x patch releases (e.g. 12.7.1 MOGO-002.8B).
    const v=g.getAppVersion().split('.').map(Number);
    ok(v[0]>12||(v[0]===12&&(v[1]>7||(v[1]===7&&v[2]>=0))),'expected >= 12.7.0, got '+g.getAppVersion());
    eq(g.getAlexV11IntroducedInEngine(),'12.7.0','v1.1 was introduced in 12.7.0');
  });
  t('J2 the release records the engine version it was introduced in',function(){
    eq(g.getRulesAlexGV11().ruleVersion,'alex_g_sr_v1_1');
    eq(g.getAlexV11IntroducedInEngine(),'12.7.0');
  });
  t('J3 provenance stamping still cannot throw and block a trade',function(){
    const frozen=Object.freeze({tradeId:'AGT|FROZEN'});
    const r=g.alexGStampTradeProvenance(frozen); // must swallow the write error
    ok(r===frozen,'must return the position rather than propagate');
  });


  // ── K. MOGO-002.8B SETUP-LEVEL EXECUTION POLICY ───────────────────────────
  t('K1 Break & Retest is PERMITTED to open',function(){
    eq(g.alexGV11SetupTypePermitted('B_breakRetest'),true,'B&R must continue exactly as today');
  });
  t('K2 Repeated Zone Reaction is SUSPENDED from opening',function(){
    eq(g.alexGV11SetupTypePermitted('A_repeatedReaction'),false);
  });
  t('K3 DEV_TEST is unaffected by the suspension',function(){
    eq(g.alexGV11SetupTypePermitted('DEV_TEST'),true);
  });
  t('K4 suspension is reversible by the single config boolean',function(){
    const off={v11Config:{setupSuspensionEnabled:false,suspendedSetupTypes:['A_repeatedReaction']}};
    eq(g.alexGV11SetupTypePermitted('A_repeatedReaction',off),true,'flipping one boolean restores RZR');
    eq(g.alexGV11SetupTypePermitted('B_breakRetest',off),true);
  });
  t('K5 fails OPEN on an unrecognised setup type',function(){
    eq(g.alexGV11SetupTypePermitted('SOME_FUTURE_TYPE'),true);
  });
  t('K6 fails OPEN on a missing/blank setup type',function(){
    eq(g.alexGV11SetupTypePermitted(null),true);
    eq(g.alexGV11SetupTypePermitted(undefined),true);
    eq(g.alexGV11SetupTypePermitted(''),true);
  });
  t('K7 fails OPEN on an empty suspension list',function(){
    const empty={v11Config:{setupSuspensionEnabled:true,suspendedSetupTypes:[]}};
    eq(g.alexGV11SetupTypePermitted('A_repeatedReaction',empty),true);
  });
  t('K8 the gate is pure -- it never mutates the config',function(){
    const before=JSON.stringify(g.getRulesAlexGV11().v11Config);
    g.alexGV11SetupTypePermitted('A_repeatedReaction');
    g.alexGV11SetupTypePermitted('B_breakRetest');
    eq(JSON.stringify(g.getRulesAlexGV11().v11Config),before);
  });
  t('K9 execution policy is exactly: B&R active, RZR suspended',function(){
    const c=g.getRulesAlexGV11().v11Config;
    eq(c.setupSuspensionEnabled,true);
    eq(JSON.stringify(c.suspendedSetupTypes),JSON.stringify(['A_repeatedReaction']));
    ok(c.suspendedSetupTypes.indexOf('B_breakRetest')<0,'B&R must never be suspended');
  });
  t('K10 the suspension window is recorded (period comparison stays valid)',function(){
    const w=g.getRulesAlexGV11().v11Config.setupSuspensionWindow;
    ok(w&&w.startedAt,'startedAt is required');
    eq(w.endedAt,null,'still suspended');
    eq(w.authority,'MOGO-002.8B');
    ok(w.reason&&w.reason.length>20,'a reason must be recorded');
  });
  t('K11 SETUP_SUSPENDED_FOR_RESEARCH is a REGISTERED reason code',function(){
    const r=g.getReasonCodeRegistry()['SETUP_SUSPENDED_FOR_RESEARCH'];
    ok(r,'unregistered -> emitDecisionEvent would REJECT the event and the suppression would be silent');
    eq(r.code,'SETUP_SUSPENDED_FOR_RESEARCH');
    eq(r.category,'CONFIG');
  });
  t('K12 CONFIG_ENTRY_DAY_NOT_ELIGIBLE is registered (v1.1 defect fix)',function(){
    const r=g.getReasonCodeRegistry()['CONFIG_ENTRY_DAY_NOT_ELIGIBLE'];
    ok(r,'the v1.1 entry-day gate used this code before it was registered, so its events were dropped');
    eq(r.category,'CONFIG');
  });
  t('K13 a suspension decision event VALIDATES and is retained',function(){
    const before=g.getDecisionEvents().length;
    g.emitDecisionEvent({eventType:'CANDIDATE_REJECTED',strategyId:'alex_g_sr_v1',
      source:'test',stage:'SETUP_EXECUTION_POLICY',decision:'REJECTED',
      reasonCode:'SETUP_SUSPENDED_FOR_RESEARCH',evidenceCompleteness:'COMPLETE'});
    ok(g.getDecisionEvents().length===before+1,'event must be retained, not validation-rejected');
  });
  t('K14 an entry-day decision event VALIDATES and is retained',function(){
    const before=g.getDecisionEvents().length;
    g.emitDecisionEvent({eventType:'CANDIDATE_REJECTED',strategyId:'alex_g_sr_v1',
      source:'test',stage:'ENTRY_DAY_ELIGIBILITY',decision:'REJECTED',
      reasonCode:'CONFIG_ENTRY_DAY_NOT_ELIGIBLE',evidenceCompleteness:'COMPLETE'});
    ok(g.getDecisionEvents().length===before+1);
  });
  t('K15 ALEX_V11_006 is registered against v1.1',function(){
    const r=g.getRulesAlexGV11().ruleRegistry.filter(function(x){return x.ruleId==='ALEX_V11_006';})[0];
    ok(r,'missing ALEX_V11_006');
    eq(r.versionIntroduced,'alex_g_sr_v1_1');
    eq(r.enabled,true);
  });
  t('K16 rule version is UNCHANGED -- operational suspension, not a rule change',function(){
    eq(g.getAlexV11RuleVersion(),'alex_g_sr_v1_1');
    eq(g.getRulesAlexG().ruleVersion,'alex_g_sr_v1');
  });
  t('K17 engine parameters are untouched by the suspension',function(){
    const c=g.getRulesAlexG().config;
    eq(c.stopATRBuffer,0.25); eq(c.minRR,2.0); eq(c.riskPercent,1.0);
    eq(c.rejectionConfirmWithinBars,1); eq(c.maxBarsBetweenBreakAndRetest,50);
  });
  t('K18 REAL protected RZR qualifier still QUALIFIES setups (detection unaffected)',function(){
    const cfg=g.getRulesAlexG().config;
    const zone={status:'validated',touches:[1,2,3,4],id:'Z'};
    eq(g.alexGEvaluateRepeatedReaction(zone,{},3,'clean',cfg).qualifies,true,
       'RZR must still be DETECTED and CLASSIFIED -- only the trade-open is withheld');
  });
  t('K19 REAL protected B&R qualifier is unchanged',function(){
    const cfg=g.getRulesAlexG().config;
    const zone={status:'broken',brokenAtBar:10,brokenAt:1000,brokenDirection:'downThroughSupport',id:'Z2',touches:[1,2,3,4]};
    const r=g.alexGEvaluateBreakRetest(zone,{swingType:'high',fromSide:'below'},3,11,cfg);
    eq(r.qualifies,true,'B&R qualification must be byte-identical in behaviour');
  });
  t('K20 direction resolution is unchanged for BOTH setup types',function(){
    eq(g.alexGDetermineTradeDirection({setupType:'A_repeatedReaction',zoneRoleAtQualification:'support'}).direction,'buy');
    eq(g.alexGDetermineTradeDirection({setupType:'B_breakRetest',brokenDirection:'downThroughSupport'}).direction,'sell');
  });
  t('K21 exit path never consults setupType (open RZR trades close normally)',function(){
    const pos={direction:'buy',entry:1.1000,stop:1.0900,target:1.1200,pair:'EUR_USD',
      setupType:'A_repeatedReaction',mfePips:0,maePips:0};
    const r=g.alexGUpdatePositionExcursionAndCheckExit(pos,{bid:1.0899,ask:1.0901});
    eq(r.hitStop,true,'a suspended-type position must still be closable');
  });
  t('K22 realized R still computes for a suspended-type historical trade',function(){
    close(g.alexGRealizedR({direction:'buy',entry:1.1,stop:1.09,exitPrice:1.12,
      setupType:'A_repeatedReaction'}),2.0,1e-9);
  });
  t('K23 historical RZR trades still count in equity stats',function(){
    const hist=[{tradeId:'H1',closedAt:'2026-01-05T10:00:00Z',result:'Loss',resultR:-1,
      direction:'buy',entry:1.1,stop:1.09,exitPrice:1.09,setupType:'A_repeatedReaction'}];
    const s=g.alexGComputeEquityStats(hist);
    eq(s.decidedCount,1,'historical RZR trades must remain in analytics');
    close(s.netR,-1.0,1e-9);
  });

  return out;
}
