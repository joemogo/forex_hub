// MOGO v12.65.0 -- fixtures for the time-of-day segmentation arm (tod_session_v1).
//
// THESE FIXTURES RUN AGAINST index.html ITSELF, not against a scratch copy of the arm. The block is
// extracted from the shipped file between its own header marker and the CRT arm that follows it, so
// a fixture cannot keep passing while the code that actually ships drifts away from it. If the
// markers ever stop matching, the suite reports a RUNNER ERROR rather than silently testing nothing.
//
// The arm is measured in PIPS PER SESSION and has NO R-MULTIPLE -- it has no stop, so there is no
// risk to divide by. Fixtures GUARD-1..2d exist to keep that disclosure attached to the evidence.
const fs=require('fs'),vm=require('vm'),path=require('path');
const ROOT=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
const START='// TIME-OF-DAY SESSION SEGMENTATION (tod_session_v1)';
const END="const CRT_STRATEGY_ID='crt_v1';";
const i0=html.indexOf(START),i1=html.indexOf(END);
if(i0<0||i1<0||i1<=i0){
  console.log('RUNNER ERROR: could not locate the tod_session_v1 block in index.html');
  process.exit(1);
}
// Slice from the START of the marker's own line to the CRT constant. An earlier version walked
// backwards looking for the banner rule and broke the moment another block was inserted above this
// one -- it began mid-function and the suite died with "Illegal return statement" rather than
// reporting anything useful. An explicit line boundary cannot drift that way.
const src=html.slice(html.lastIndexOf('\n',i0)+1,i1);
const ctx={Intl:Intl,Date:Date,Math:Math,isFinite:isFinite,parseInt:parseInt,console:console,
  String:String,Array:Array,Object:Object,JSON:JSON,Number:Number,document:undefined};
vm.createContext(ctx);
const EXPORTS=['RULES_TOD','TOD_STRATEGY_ID','TOD_VERSION','todOffsetMinutesAt','todLocalToUtcMs',
  'todLocalDateAt','todSessionWindows','todPriceWindow','todSummarize','todRunArms','todCompareArms',
  'todBuildReplayPackage','todAssembleReport','todSidakAlpha','TOD_PRIMARY_PAIR'];
try{ vm.runInContext(src+'\n;globalThis.__X={'+EXPORTS.map(function(n){return n+':'+n;}).join(',')+'};',ctx); }
catch(e){ console.log('RUNNER ERROR: '+(e&&e.message)); process.exit(1); }
const G=ctx.__X;

let pass=0,fail=0;const failures=[];
function t(name,fn){
  try{ fn(); pass++; console.log('PASS -- '+name); }
  catch(e){ fail++; failures.push(name+': '+e.message); console.log('FAIL -- '+name+' :: '+e.message); }
}
function eq(a,b,m){ if(a!==b) throw new Error((m||'')+' expected '+b+' got '+a); }
function near(a,b,tol,m){ if(!(Math.abs(a-b)<=tol)) throw new Error((m||'')+' expected ~'+b+' got '+a); }
function ok(c,m){ if(!c) throw new Error(m||'expected truthy'); }

const CFG=G.RULES_TOD.config;
const PIP=0.0001;

// Build an M15 series spanning [fromISO,toISO) with a price function of index.
function series(fromISO,toISO,priceFn){
  const out=[];const start=Date.parse(fromISO),end=Date.parse(toISO);
  let i=0;
  for(let t=start;t<end;t+=15*60000){ out.push({t:new Date(t),c:priceFn?priceFn(i,t):1.1000,o:1.1,h:1.1,l:1.1}); i++; }
  return out;
}

// ── TZ-1..TZ-6: DST correctness. This is where the arm dies silently if it is wrong. ──

t('TZ-1 NY offset is -5h in January',function(){
  eq(G.todOffsetMinutesAt('America/New_York',Date.UTC(2025,0,15,12,0)),-300);
});
t('TZ-2 NY offset is -4h in July',function(){
  eq(G.todOffsetMinutesAt('America/New_York',Date.UTC(2025,6,15,12,0)),-240);
});
t('TZ-3 London offset is 0 in January, +60 in July',function(){
  eq(G.todOffsetMinutesAt('Europe/London',Date.UTC(2025,0,15,12,0)),0);
  eq(G.todOffsetMinutesAt('Europe/London',Date.UTC(2025,6,15,12,0)),60);
});
t('TZ-4 08:30 NY maps to 13:30 UTC in winter and 12:30 UTC in summer',function(){
  eq(G.todLocalToUtcMs('America/New_York',2025,1,15,8,30),Date.UTC(2025,0,15,13,30));
  eq(G.todLocalToUtcMs('America/New_York',2025,7,15,8,30),Date.UTC(2025,6,15,12,30));
});
t('TZ-5 the US/EU DST desync window is handled (2025-03-17: US on DST, UK not)',function(){
  // 2025: US springs forward 09 Mar, UK 30 Mar. On 17 Mar NY is -4 while London is still +0,
  // a 4h gap instead of the usual 5h. A fixed-offset implementation gets one of these wrong.
  eq(G.todOffsetMinutesAt('America/New_York',Date.UTC(2025,2,17,12,0)),-240);
  eq(G.todOffsetMinutesAt('Europe/London',Date.UTC(2025,2,17,12,0)),0);
  eq(G.todLocalToUtcMs('America/New_York',2025,3,17,8,30),Date.UTC(2025,2,17,12,30));
  eq(G.todLocalToUtcMs('Europe/London',2025,3,17,8,0),Date.UTC(2025,2,17,8,0));
});
t('TZ-6b NO DAY IS SKIPPED across a spring-forward transition',function(){
  // The noon anchor in todSessionWindows is a deliberate safety choice, and this is what it buys.
  // An anchor near local midnight (23:30, say) lands on the far side of the transition and skips a
  // whole calendar day EVERY spring forward -- silently dropping ~1 session a year per zone from
  // the sample. Proven reachable: over 2014-2026 a 23:30 anchor skips a day on every US and UK
  // spring-forward date. Asserted as a dense, gapless day sequence rather than a count, so it fails
  // for the right reason.
  const w=G.todSessionWindows(CFG.primary,Date.UTC(2025,2,5,0,0),Date.UTC(2025,2,14,23,59));
  const keys=w.map(function(x){return x.dayKey;});
  eq(keys.join(','),'2025-03-05,2025-03-06,2025-03-07,2025-03-08,2025-03-09,2025-03-10,2025-03-11,2025-03-12,2025-03-13,2025-03-14',
    'the spring-forward week must be dense');
  const wl=G.todSessionWindows(CFG.secondary,Date.UTC(2025,2,26,0,0),Date.UTC(2025,3,2,23,59));
  eq(wl.map(function(x){return x.dayKey;}).join(','),
    '2025-03-26,2025-03-27,2025-03-28,2025-03-29,2025-03-30,2025-03-31,2025-04-01,2025-04-02',
    'the UK spring-forward week must be dense');
});
t('TZ-6 spring-forward day still yields exactly one window, not zero or two',function(){
  const w=G.todSessionWindows(CFG.primary,Date.UTC(2025,2,9,0,0),Date.UTC(2025,2,9,23,59));
  eq(w.length,1,'windows on 2025-03-09');
  eq(w[0].dayKey,'2025-03-09');
});

// ── WIN-1..WIN-4: window enumeration ──

t('WIN-1 one window per local calendar day',function(){
  const w=G.todSessionWindows(CFG.primary,Date.UTC(2025,5,2,0,0),Date.UTC(2025,5,6,23,59));
  eq(w.length,5,'Mon-Fri');
});
t('WIN-2 windows are ordered and non-overlapping',function(){
  const w=G.todSessionWindows(CFG.primary,Date.UTC(2025,5,2,0,0),Date.UTC(2025,5,20,23,59));
  for(let i=1;i<w.length;i++) ok(w[i].startUtc>w[i-1].endUtc,'window '+i+' overlaps previous');
});
t('WIN-3 the US window is 8.5 hours long',function(){
  const w=G.todSessionWindows(CFG.primary,Date.UTC(2025,5,2,0,0),Date.UTC(2025,5,2,23,59));
  near((w[0].endUtc-w[0].startUtc)/3600000,8.5,1e-9);
});
t('WIN-4 an empty or inverted range yields nothing',function(){
  eq(G.todSessionWindows(CFG.primary,Date.UTC(2025,5,5),Date.UTC(2025,5,1)).length,0);
  eq(G.todSessionWindows(null,0,1e12).length,0);
});

// ── PRICE-1..PRICE-6: pricing one window ──

t('PRICE-1 a clean rising session prices to the right pip count',function(){
  // 2025-06-02, US session 12:30-21:00 UTC (summer, -4). Rise 0.0001 per M15 bar.
  const s=series('2025-06-02T12:30:00Z','2025-06-02T21:15:00Z',function(i){ return 1.1000+i*0.0001; });
  const w=G.todSessionWindows(CFG.primary,Date.UTC(2025,5,2,0,0),Date.UTC(2025,5,2,23,59))[0];
  const p=G.todPriceWindow(s,w,CFG,PIP);
  ok(p.ok,'should price: '+p.reason);
  // 34 bars in 8.5h; first close at 12:30 (i=0) .. last at or before 21:00 (i=34)
  eq(p.candles,35);
  near(p.grossPips,34,1e-6);
});
t('PRICE-2 NO LOOK-AHEAD: bars after the window end cannot change the result',function(){
  const base=series('2025-06-02T12:30:00Z','2025-06-02T21:15:00Z',function(i){ return 1.1000+i*0.0001; });
  const w=G.todSessionWindows(CFG.primary,Date.UTC(2025,5,2,0,0),Date.UTC(2025,5,2,23,59))[0];
  const a=G.todPriceWindow(base,w,CFG,PIP);
  const poisoned=base.concat(series('2025-06-02T21:15:00Z','2025-06-03T02:00:00Z',function(){ return 9.9999; }));
  const b=G.todPriceWindow(poisoned,w,CFG,PIP);
  eq(b.grossPips,a.grossPips,'a bar after the close changed the session return');
  eq(b.exit,a.exit);
});
t('PRICE-3 NO LOOK-BEHIND: bars before the window start cannot change the result',function(){
  const base=series('2025-06-02T12:30:00Z','2025-06-02T21:15:00Z',function(i){ return 1.1000+i*0.0001; });
  const w=G.todSessionWindows(CFG.primary,Date.UTC(2025,5,2,0,0),Date.UTC(2025,5,2,23,59))[0];
  const a=G.todPriceWindow(base,w,CFG,PIP);
  const pre=series('2025-06-02T06:00:00Z','2025-06-02T12:30:00Z',function(){ return 0.0001; });
  const b=G.todPriceWindow(pre.concat(base),w,CFG,PIP);
  eq(b.grossPips,a.grossPips);
  eq(b.entry,a.entry);
});
t('PRICE-4 a session with too few candles REFUSES rather than returning a number',function(){
  const s=series('2025-06-02T12:30:00Z','2025-06-02T13:15:00Z',function(){ return 1.1; }); // 3 bars
  const w=G.todSessionWindows(CFG.primary,Date.UTC(2025,5,2,0,0),Date.UTC(2025,5,2,23,59))[0];
  const p=G.todPriceWindow(s,w,CFG,PIP);
  eq(p.ok,false); eq(p.reason,'TOO_FEW_CANDLES');
});
t('PRICE-5 a session missing its first two hours REFUSES (START_GAP)',function(){
  const s=series('2025-06-02T15:00:00Z','2025-06-02T21:15:00Z',function(){ return 1.1; });
  const w=G.todSessionWindows(CFG.primary,Date.UTC(2025,5,2,0,0),Date.UTC(2025,5,2,23,59))[0];
  const p=G.todPriceWindow(s,w,CFG,PIP);
  eq(p.ok,false); eq(p.reason,'START_GAP');
});
t('PRICE-6 a flat session is exactly zero, not a rounding artefact',function(){
  const s=series('2025-06-02T12:30:00Z','2025-06-02T21:15:00Z',function(){ return 1.1000; });
  const w=G.todSessionWindows(CFG.primary,Date.UTC(2025,5,2,0,0),Date.UTC(2025,5,2,23,59))[0];
  const p=G.todPriceWindow(s,w,CFG,PIP);
  eq(p.grossPips,0);
});

// ── STAT-1..STAT-5: the statistics, hand-computed ──

t('STAT-1 mean and SE against hand-computed values',function(){
  const obs=[{grossPips:10,grossPct:0.1},{grossPips:-4,grossPct:-0.04},
             {grossPips:6,grossPct:0.06},{grossPips:0,grossPct:0}];
  // mean = 12/4 = 3. deviations 7,-7,3,-3 -> squares 49,49,9,9 = 116; var=116/3=38.667
  // se = sqrt(38.667/4) = sqrt(9.6667) = 3.10913
  const s=G.todSummarize(obs,0);
  eq(s.n,4); near(s.meanPips,3,1e-9); near(s.sePips,3.109126,1e-5);
  near(s.tStat,3/3.109126,1e-5);
});
t('STAT-2 the spread is charged ONCE PER OBSERVATION, shifting the mean by exactly the spread',function(){
  const obs=[{grossPips:10,grossPct:0},{grossPips:-4,grossPct:0},{grossPips:6,grossPct:0},{grossPips:0,grossPct:0}];
  const gross=G.todSummarize(obs,0),net=G.todSummarize(obs,1.5);
  near(net.meanPips,gross.meanPips-1.5,1e-9,'net mean must be gross mean minus one spread');
  near(net.sePips,gross.sePips,1e-9,'a constant cost cannot change the standard error');
});
t('STAT-3 n=1 reports the mean but NO error bar rather than a fake zero',function(){
  const s=G.todSummarize([{grossPips:5,grossPct:0}],0);
  eq(s.n,1); near(s.meanPips,5,1e-9); eq(s.sePips,null); eq(s.tStat,null);
});
t('STAT-4 n=0 returns nulls, never 0%',function(){
  const s=G.todSummarize([],0);
  eq(s.n,0); eq(s.meanPips,null); eq(s.winShare,null);
});
t('STAT-5 winShare counts NET wins, not gross',function(){
  const obs=[{grossPips:1,grossPct:0},{grossPips:1,grossPct:0},{grossPips:5,grossPct:0},{grossPips:5,grossPct:0}];
  eq(G.todSummarize(obs,0).winShare,1);
  eq(G.todSummarize(obs,2).winShare,0.5,'a 2-pip spread must turn the 1-pip winners into losers');
});

// ── ARM-1..ARM-5: the control ──

// A weekday-only M15 series, the way real FX data actually arrives: no Saturday or Sunday bars.
function fxSeries(fromISO,toISO,stepFn){
  const out=[];let px=1.1000;
  for(let t=Date.parse(fromISO);t<Date.parse(toISO);t+=15*60000){
    const d=new Date(t),dow=d.getUTCDay();
    if(dow===6||dow===0) continue;                      // no weekend bars
    px+=(stepFn?stepFn(d):0);
    out.push({t:d,c:px});
  }
  return out;
}

t('ARM-1 a pure US-session drift shows in primary and NOT in the complement',function(){
  // Rises strictly INSIDE the session. The 12:30 bar itself does not rise: it is the session's
  // entry AND the complement's exit, so a rise stamped on it belongs to neither leg.
  const s=fxSeries('2025-06-02T00:00:00Z','2025-06-27T00:00:00Z',function(d){
    const h=d.getUTCHours()+d.getUTCMinutes()/60;
    return (h>12.5&&h<=21)?0.0001:0;
  });
  const r=G.todRunArms(s,CFG,PIP);
  ok(r.primary.n>=15,'expected ~19 weekday sessions, got '+r.primary.n);
  ok(r.primary.meanPips>30,'primary mean should be strongly positive, got '+r.primary.meanPips);
  near(r.complement.meanPips,0,1e-6,'complement should be flat, got '+r.complement.meanPips);
  const c=G.todCompareArms(r);
  ok(c.comparable); ok(c.directionAsPredicted);
});
t('ARM-1b THE TWO LEGS TILE: session + complement equals the whole move, no gap and no overlap',function(){
  // The invariant that proves neither leg double-counts the boundary bar. If the complement's exit
  // and the session's entry ever drift apart, price movement is either counted twice or lost, and
  // every figure this arm reports would be wrong in a way no mean or t-stat could reveal.
  const s=fxSeries('2025-06-02T00:00:00Z','2025-06-27T00:00:00Z',function(d){
    return (d.getTime()%(7*15*60000)===0)?0.0003:0.0001;   // irregular, so tiling cannot pass by luck
  });
  const r=G.todRunArms(s,CFG,PIP);
  const prim=r.primary.observations,comp=r.complement.observations;
  ok(prim.length>3&&comp.length>2,'need several of each');
  for(let i=0;i<comp.length;i++){
    // complement i runs from the end of session i to the start of session i+1
    eq(comp[i].entry,prim[i].exit,'complement '+i+' must start at the session exit price');
    eq(comp[i].exit,prim[i+1].entry,'complement '+i+' must end at the next session entry price');
  }
});
t('ARM-2 THE CONTROL EARNS ITS KEEP: a uniform all-day trend shows in BOTH arms',function(){
  // This is the fixture that makes the measurement mean something. A pair that simply drifts up
  // produces a positive session mean for a reason that has nothing to do with time of day.
  const s=fxSeries('2025-06-02T00:00:00Z','2025-06-27T00:00:00Z',function(){ return 0.0001; });
  const r=G.todRunArms(s,CFG,PIP);
  ok(r.primary.meanPips>0,'primary positive under uniform drift');
  ok(r.complement.meanPips>0,'complement MUST also be positive under uniform drift -- if it is not, the control is broken');
});
t('ARM-3 the complement records its gap hours so weekend legs can be excluded',function(){
  const s=fxSeries('2025-06-02T00:00:00Z','2025-06-20T00:00:00Z',function(){ return 0; });
  const r=G.todRunArms(s,CFG,PIP);
  ok(r.complement.observations.length>0);
  const gaps=r.complement.observations.map(function(o){return o.complementGapHours;});
  ok(gaps.every(function(g){return typeof g==='number'&&g>0;}),'every complement leg needs a gap');
  ok(gaps.some(function(g){return g>40;}),'at least one weekend leg expected');
});
t('ARM-4 refusals are counted, never silently dropped',function(){
  const s=series('2025-06-02T12:30:00Z','2025-06-02T13:00:00Z',function(){ return 1.1; });
  const r=G.todRunArms(s,CFG,PIP);
  const total=Object.keys(r.refusals).reduce(function(a,k){return a+r.refusals[k];},0);
  ok(total>0,'a series too short to price anything must report refusals');
});
t('ARM-5 empty input is handled without throwing',function(){
  const r=G.todRunArms([],CFG,PIP);
  eq(r.primary,null); ok(r.warnings.indexOf('NO_DATA')>=0);
});

// ── CMP-1..CMP-3 ──

t('CMP-1 the difference SE is the pooled one',function(){
  const r={primary:{n:100,meanPips:5,sePips:3},complement:{n:100,meanPips:1,sePips:4}};
  const c=G.todCompareArms(r);
  near(c.diffPips,4,1e-9); near(c.seDiffPips,5,1e-9); near(c.z,0.8,1e-9);
});
t('CMP-2 an insufficient sample refuses to compare',function(){
  eq(G.todCompareArms({primary:{n:0},complement:{n:5}}).comparable,false);
});
t('CMP-3 direction is reported against the PREDICTION, not against zero',function(){
  const c=G.todCompareArms({primary:{n:9,meanPips:-1,sePips:1},complement:{n:9,meanPips:-5,sePips:1}});
  ok(c.directionAsPredicted,'primary above complement is the prediction even when both are negative');
});

// ── GUARD-1/2: the disclosures that must not silently disappear ──

t('GUARD-1 the HEADER COMMENT carries the no-stop / no-risk-denominator disclosure',function(){
  // Scoped to the header block deliberately. An earlier version of this fixture searched the WHOLE
  // file, and once the same phrase appeared in the manifest and the package disclosures it passed
  // even with the header disclosure deleted -- three copies made the test unable to fail. Each
  // place that must carry the warning is now checked where it lives.
  const header=src.slice(0,src.indexOf('const TOD_STRATEGY_ID')).replace(/\n\/\/\s?/g,' ');
  ok(/NO STOP AND NO TARGET/.test(header),'the header no-stop disclosure is missing');
  ok(/NO RISK DENOMINATOR/.test(header),'the header risk-denominator disclosure is missing');
  ok(/replay_compare\.py[^.]{0,60}DOES NOT APPLY/.test(header),'the header replay_compare caveat is missing');
});
t('GUARD-2 the EXPORTED PACKAGE itself warns that no R exists and replay_compare does not apply',function(){
  // Behaviour, not prose: this is what a downstream reader actually receives.
  const s2=fxSeries('2025-06-02T00:00:00Z','2025-06-27T00:00:00Z',function(){ return 0.0001; });
  const r=G.todRunArms(s2,CFG,PIP);
  const pkg=G.todBuildReplayPackage([{pair:'EUR_USD',timeframe:'M15',arms:r}],CFG,{stamp:0});
  const d=(pkg.disclosures||[]).join(' | ');
  ok(/NO R-MULTIPLE EXISTS/.test(d),'the package must state no R exists');
  ok(/replay_compare\.py DOES NOT APPLY/.test(d),'the package must state replay_compare does not apply');
  ok(/not assessed/.test(d),'the package must carry the paper-trading readiness statement');
  eq(pkg.evidenceKind,'SESSION_RETURN_OBSERVATIONS');
  eq(pkg.captureBasis,'REPLAY_RUN');
});
t('GUARD-2b NO observation carries an R field that could be averaged against real R-multiples',function(){
  const s2=fxSeries('2025-06-02T00:00:00Z','2025-06-27T00:00:00Z',function(){ return 0.0001; });
  const r=G.todRunArms(s2,CFG,PIP);
  const pkg=G.todBuildReplayPackage([{pair:'EUR_USD',timeframe:'M15',arms:r}],CFG,{stamp:0});
  ok(pkg.observations.length>0,'need observations');
  pkg.observations.forEach(function(o){
    Object.keys(o).forEach(function(k){
      ok(!/^realized|(^|[^a-z])r$|rMultiple|plannedR/i.test(k),'observation carries an R-shaped field: '+k);
    });
  });
});
t('GUARD-2c every observation is labelled with the provenance of its window',function(){
  const s2=fxSeries('2025-06-02T00:00:00Z','2025-06-27T00:00:00Z',function(){ return 0.0001; });
  const r=G.todRunArms(s2,CFG,PIP);
  const pkg=G.todBuildReplayPackage([{pair:'EUR_USD',timeframe:'M15',arms:r}],CFG,{stamp:0});
  const prim=pkg.observations.filter(function(o){return o.arm==='PRIMARY_SESSION';});
  const sec=pkg.observations.filter(function(o){return o.arm==='SECONDARY_SESSION';});
  ok(prim.length&&sec.length,'need both arms');
  ok(/SOURCE_STATED/.test(prim[0].windowProvenance),'primary must be labelled source-stated');
  ok(/MOGO CHOICE/.test(sec[0].windowProvenance),'secondary must be labelled a MOGO choice');
});
t('GUARD-2d the pre-registered pair is EUR/USD and the rest are Sidak-corrected',function(){
  const s2=fxSeries('2025-06-02T00:00:00Z','2025-06-27T00:00:00Z',function(){ return 0.0001; });
  const r=G.todRunArms(s2,CFG,PIP);
  const rep=G.todAssembleReport([{pair:'EUR_USD',arms:r},{pair:'GBP_USD',arms:r},{pair:'USD_JPY',arms:r}]);
  eq(rep.preRegisteredPair,'EUR_USD');
  eq(rep.preRegistered.pair,'EUR_USD');
  eq(rep.exploratoryK,2,'EUR/USD must not be counted among the exploratory pairs');
  near(rep.exploratorySidakAlpha,1-Math.pow(0.95,1/2),1e-9);
  ok(rep.exploratorySidakAlpha<0.05,'the corrected alpha must be stricter than 0.05');
});
t('GUARD-3 the primary window is labelled SOURCE_STATED and the secondary is not',function(){
  eq(/SOURCE_STATED/.test(CFG.primary.provenance),true);
  eq(/MOGO CHOICE/.test(CFG.secondary.provenance),true);
});

console.log('FIXTURES: '+pass+'/'+(pass+fail));
process.exit(fail?1:0);
