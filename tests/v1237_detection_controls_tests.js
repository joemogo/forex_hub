// MOGO-021 — DETECTION-SURFACE CONTROLS (v12.3.7).
//
// WHAT THIS SUITE IS
// The MOGO-021 detection-surface coverage audit ran 117 behaviour-changing mutations across the
// signal / AOI / confluence / session / bias surface. 64 killed ZERO fixtures out of 1,440, and
// 61 of those were genuinely uncovered trading rules -- rules that are CORRECT, but that could
// have been changed, weakened or deleted with the whole repository staying green. This suite is
// pure test debt repayment: it adds fixtures and touches no production line, so it changes no
// behaviour and crosses no governance boundary.
//
// THE RULE EVERY FIXTURE HERE IS BUILT UNDER
//     THE CANDLES ARE CONSTRUCTED. THE VERDICT IS NOT.
// Each fixture supplies ordinary inputs -- a price series, a clock, a bias table, a live fill --
// and then reports whatever the frozen function decides. Nothing here stubs, wraps, overrides or
// forces a protected function's outcome, and no threshold, weight or rule is altered to make a
// fixture pass. ALERT_THRESHOLD, WEIGHTS, RULES and RULES_ALEXG are READ (through live
// accessors) and never assigned.
//
// EVERY NEGATIVE CONTROL SITS ONE VARIABLE AWAY FROM A PROVEN POSITIVE CONTROL
// The audit's own worst finding was exclusion fixtures asserting silence against a flat series
// that could never have produced a signal at all -- assertions that would have passed with the
// rule deleted outright. So in this suite every "must not fire" case is paired, IN THE SAME
// FIXTURE, with a "does fire" case differing by exactly one input: one bias cell, one candle
// high, one neighbour's high, one live ask, one touch. Both halves are asserted together. If the
// positive half ever stops firing, the negative half stops proving anything and the fixture
// fails rather than passing for the wrong reason.
//
// FLOATING-POINT BOUNDARIES ARE PROVEN, NOT ASSUMED
// Several fixtures assert behaviour AT a threshold (a wick ratio of exactly 0.55, a body ratio
// of exactly 0.12) -- the only way to kill a `>` -> `>=` boundary flip. Decimal FX prices do not
// generally divide to exact decimals in binary floating point, so those candles were chosen by
// search and each fixture re-proves the exact identity (`ratio === 0.55`) at run time before
// asserting the verdict. If a future engine ever computes those divisions differently, the
// fixture fails loudly instead of silently degrading into a non-boundary test.
//
// SECTION MAP (the audit's own severity order)
//   S1  BIAS-BLOCK-*    the counter-trend block -- RULES.entry "Never enter against confirmed
//                       top-down bias". Had no control of any kind, on either side.
//   S2  RR-*            the 1.99 minimum reward-to-risk in evaluateLiveTrigger.
//   S3  THRESH-*        ALERT_THRESHOLD (55) and the reachable-score lattice.
//   S4  AOI3-*          the AOI 3-touch rule ("fewer than 3 = no AOI, move on").
//   S5  PATTERN-*       wick 0.55, doji 0.12, engulf swallow count, engulf colour requirement,
//                       MSB close-beyond requirement.
//   S6  SESSION-*       getSession window edges.
//   S7  BIASTAB-*       the getBias table.
//   S8  CONFITEM-*      scoreConfluence ITEM-level state/points (AOI sidedness, bias weights).
//   S9  SWING-*         findSwingPoints strictness and that swing HIGHS are reported at all.
//   S10 ZONEROLE-*      alexGZoneRole's documented inclusive boundary.
//   S11 ENTRYDELAY-*    RULES_ALEXG.config.maxLiveEntryDelayPips (5.0).
function runV1237DetectionControlFixtures(g){
  const out=[];
  async function t(name,fn){
    try{ const d=await fn(); out.push({name,pass:true,detail:d||''}); }
    catch(e){ out.push({name,pass:false,detail:(e&&e.message)?e.message:String(e)}); }
  }
  function eq(a,b,m){ if(a!==b) throw new Error((m||'')+' -- expected '+JSON.stringify(b)+', got '+JSON.stringify(a)); }
  function ok(v,m){ if(!v) throw new Error(m||'expected truthy'); }
  function near(a,b,tol,m){ if(!(Math.abs(a-b)<=tol)) throw new Error((m||'')+' -- expected '+b+' +/- '+tol+', got '+a); }
  function bar(o,h,l,c){ return{o:o,h:h,l:l,c:c}; }
  function typesOf(sigs){ return sigs.map(function(s){return s.type+':'+s.dir;}).join(','); }
  function findSig(sigs,type,dir){ return sigs.filter(function(s){return s.type===type&&s.dir===dir;})[0]||null; }
  function itemBy(items,label){ return items.filter(function(i){return i.label===label;})[0]||null; }
  // scoreConfluence relabels the engulf/session items with live values, so items are also
  // addressable by position -- the order is bias, AOI, wick, engulf, session, MSB.
  const IDX={bias:0,aoi:1,wick:2,engulf:3,session:4,msb:5};

  // ── SERIES BUILDERS ────────────────────────────────────────────────────────────────────────

  // A gently, MONOTONICALLY rising filler. Monotonic is the point: findSwingPoints can find no
  // swing high (every right-hand neighbour is higher) and no swing low (every left-hand
  // neighbour is lower), so computeAOI returns no zones and the AOI term of every score built on
  // this filler is a provable ZERO rather than an accident. Each fixture that depends on that
  // asserts it directly rather than trusting this comment.
  function risingFiller(n,start,step){
    const bars=[];
    for(let k=0;k<n;k++){ const b=start+k*step; bars.push(bar(b,b+0.00010,b-0.00010,b+0.00005)); }
    return bars;
  }

  // THE S1/S3 SERIES. 60 M15 bars -- exactly the count evaluateLiveTrigger requests, so the
  // response classifies COMPLETE under ADR-011 and evaluation is not suppressed.
  //
  // The last three bars are an ordinary bullish reversal at the low of the move: a bearish bar
  // fully swallowed by the next bar's body, which also prints a new high and leaves a long lower
  // wick. The frozen scorer values that, with NO bias credit at all, at exactly 55 -- wick 15 +
  // engulf 20 + session 10 + MSB 10 -- which is exactly ALERT_THRESHOLD. That is deliberate and
  // is what lets a counter-trend fixture reach the entry-trigger gate at all: with the bias term
  // withheld the setup still clears the confluence gate on its own merits, so anything that
  // blocks it afterwards is provably the bias rule and not the score.
  //
  // prev2High is the ONE variable the S3 pair moves: raising it to 1.10030 makes prev.h > prev2.h
  // false, which removes the MSB term and drops the same series to 45.
  function reversalM15(prev2High){
    const bars=risingFiller(57,1.09800,0.00003);
    bars.push(bar(1.09995,prev2High===undefined?1.10020:prev2High,1.09990,1.10015)); // prev2
    bars.push(bar(1.10025,1.10028,1.10005,1.10010));                                  // prev : bearish, inside
    bars.push(bar(1.10000,1.10040,1.09900,1.10030));                                  // last : engulfs it, new high, long lower wick
    return bars;
  }
  const BULLISH_TABLE={weekly:'Bullish',daily:'Bullish',fh:'Bullish',bucket:'Active watch'};
  const BEARISH_TABLE={weekly:'Bearish',daily:'Bearish',fh:'Bearish',bucket:'Active watch'};

  // 60 flat "plateau" bars with named bars marked out by a lower low or a higher high, so a
  // swing cluster of an EXACT touch count can be built. Every plateau bar shares one high and
  // one low, which is precisely why none of them is itself a swing point: findSwingPoints
  // disqualifies on `>=` / `<=`, so an equal neighbour is never a swing.
  function shelfSeries(plateau,marks,last){
    const bars=[];
    for(let i=0;i<60;i++) bars.push(bar(plateau.o,plateau.h,plateau.l,plateau.c));
    marks.forEach(function(m){
      bars[m.idx]=bar(plateau.o,m.h!=null?m.h:plateau.h,m.l!=null?m.l:plateau.l,plateau.c);
    });
    if(last) bars[59]=bar(last.o,last.h,last.l,last.c);
    return bars;
  }
  const PLATEAU_S4={o:1.10300,h:1.10500,l:1.10200,c:1.10300};
  // Marks are 7 bars apart, which is 2*lookback+1 for the lookback of 3 findAOIs uses -- so each
  // marked bar's confirmation window is clean and each touch is counted exactly once.
  const TOUCH_3=[{idx:5,l:1.09500},{idx:12,l:1.09500},{idx:19,l:1.09500}];
  const TOUCH_2=[{idx:26,l:1.09900},{idx:33,l:1.09900}];

  // 12 identical quiet bars in front of a short, fully specified tail. Under 20 bars computeAOI
  // returns no zones at all, so these pattern fixtures see the pattern rules and nothing else.
  function quiet(tail){
    const bars=[];
    for(let k=0;k<12;k++) bars.push(bar(1.10100,1.10150,1.10050,1.10100));
    return bars.concat(tail);
  }

  return (async function(){

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S1 — THE COUNTER-TREND BLOCK
  // RULES.entry: "Never enter against confirmed top-down bias — no counter-trend trades."
  // The audit found this rule had NO control of any kind, on either side: detectSignals could be
  // made to stamp biasMatch:true on every signal, and evaluateLiveTrigger's requirement that the
  // entry trigger match bias could be deleted outright, with 1,440 fixtures staying green.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  await t('BIAS-BLOCK-1 detectSignals stamps biasMatch from the REAL bias table, not a constant',async function(){
    const bars=reversalM15();
    // POSITIVE CONTROL: aligned table. The signal exists AND is marked as matching bias.
    g.resetScanData(); g.setScanData('EUR/USD',BULLISH_TABLE);
    const aligned=g.detectSignals(bars,'EUR_USD');
    const upA=findSig(aligned,'engulf','buy');
    ok(upA,'the constructed series must actually produce a bullish engulf signal -- otherwise everything below is vacuous');
    eq(upA.biasMatch,true,'with a 3/3 Bullish table, a bullish engulf MUST be marked biasMatch');
    // NEGATIVE CONTROL: the SAME candles, one variable away -- the bias table is flipped.
    g.resetScanData(); g.setScanData('EUR/USD',BEARISH_TABLE);
    const against=g.detectSignals(bars,'EUR_USD');
    const upB=findSig(against,'engulf','buy');
    ok(upB,'the same candles still produce the same bullish engulf -- only the table changed');
    eq(upB.biasMatch,false,'against a 3/3 Bearish table that same bullish signal must NOT be marked biasMatch');
    // and the counter-trend read is symmetric: nothing bullish is matched, nothing is invented.
    eq(against.filter(function(s){return s.dir==='buy'&&s.biasMatch;}).length,0,
      'no buy-side signal may be marked as matching a Bearish bias');
    return 'same candles, Bullish table -> biasMatch=true; Bearish table -> biasMatch=false; signals present in both ('+typesOf(against)+')';
  });

  await t('BIAS-BLOCK-2 POSITIVE CONTROL: with bias ALIGNED the frozen live trigger FIRES of its own accord',async function(){
    g.setCfg(); g.resetPairData(); g.resetStructuralAOICache();
    g.setM15Bars(reversalM15());
    g.setBidAsk(1.10025,1.10035);
    g.resetScanData(); g.setScanData('EUR/USD',BULLISH_TABLE);
    const v=await g.evaluateLiveTrigger('EUR_USD');
    eq(v.fires,true,'the aligned case must fire -- without it the counter-trend fixture below proves nothing: '+JSON.stringify(v));
    eq(v.dir,'buy','and take the bullish side');
    ok(v.stop<v.entry&&v.target>v.entry,'stop below entry, target above -- the trade is coherent');
    ok(v.ratio>=1.99,'and the strategy accepted its own R:R: '+v.ratio);
    eq(v.confluence,80,'the frozen scorer rates the ALIGNED setup at 80 (bias 25 + wick 15 + engulf 20 + session 10 + MSB 10)');
    return 'fires=true dir=buy entry='+v.entry+' stop='+v.stop.toFixed(5)+' target='+v.target.toFixed(5)+' R:R='+v.ratio.toFixed(2)+' confluence='+v.confluence;
  });

  await t('BIAS-BLOCK-3 THE RULE: a counter-trend trigger is REFUSED, and refused BY THE BIAS RULE',async function(){
    g.setCfg(); g.resetPairData(); g.resetStructuralAOICache();
    g.setM15Bars(reversalM15());
    g.setBidAsk(1.10025,1.10035);
    // ONE variable away from BIAS-BLOCK-2: the top-down table, and nothing else.
    g.resetScanData(); g.setScanData('EUR/USD',BEARISH_TABLE);
    const v=await g.evaluateLiveTrigger('EUR_USD');
    eq(v.fires,false,'a bullish trigger against a confirmed Bearish top-down bias must NOT fire');
    // The refusal must come from the BIAS rule. Asserting only fires===false would also pass if
    // the setup had simply scored too low -- which is how a counter-trend block can look present
    // while being entirely absent.
    eq(v.reason,'No engulfing trigger yet',
      'the refusal must be the entry-trigger/bias gate, not some earlier gate');
    ok(v.conf,'a rejected verdict still carries the score it computed');
    ok(v.conf.total>=g.ALERT_THRESHOLD(),
      'and that score CLEARED the confluence gate ('+v.conf.total+' >= '+g.ALERT_THRESHOLD()+
      ') -- so the block is provably the bias rule, not a low score');
    eq(v.conf.total,55,'with the bias term withheld the same setup scores exactly 55: wick 15 + engulf 20 + session 10 + MSB 10');
    eq(v.conf.direction,'long','the scorer still reads the setup as a long -- it is the ENTRY that is blocked, not the read');
    return 'confluence '+v.conf.total+' cleared the '+g.ALERT_THRESHOLD()+' gate, then the counter-trend rule refused it: "'+v.reason+'"';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S2 — MINIMUM REWARD-TO-RISK (1.99)
  // RULES.risk: "Minimum 1:2 R:R must be mappable before entering — if not, skip the trade."
  // The live fill is the variable the R:R gate actually reacts to: stop comes from the daily AOI
  // shelf and target from the daily AOI ceiling, both frozen for these two fixtures, so moving
  // the ask by half a pip is the single input that moves the ratio across the boundary.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  // Solves for the live ask that makes the frozen formula produce a chosen ratio, from the AOI
  // levels the frozen AOI engine itself derived. It does not compute the verdict -- evaluateLiveTrigger
  // does, from its own stop/target/ratio arithmetic, and the fixtures assert what it says.
  function askForRatio(ratio){
    const aoi=g.findAOIs(g.structuralCandles(120));
    const stop=aoi.support-g.pipSize('EUR_USD')*7;
    return{ask:(aoi.resistance+ratio*stop)/(1+ratio),support:aoi.support,resistance:aoi.resistance,stop:stop};
  }

  await t('RR-2 a setup just OVER the 1.99 minimum is accepted, and the strategy states the ratio it accepted',async function(){
    g.setCfg(); g.resetPairData(); g.resetStructuralAOICache();
    g.setM15Bars(reversalM15());
    g.resetScanData(); g.setScanData('EUR/USD',BULLISH_TABLE);
    const s=askForRatio(2.00);
    g.setBidAsk(s.ask-0.0002,s.ask);
    const v=await g.evaluateLiveTrigger('EUR_USD');
    eq(v.fires,true,'a ratio just above the minimum must be accepted: '+JSON.stringify(v));
    near(v.ratio,2.00,0.005,'and the accepted ratio is the one that was constructed');
    ok(v.ratio>=1.99,'it is at or above the frozen minimum');
    return 'support='+s.support.toFixed(5)+' resistance='+s.resistance.toFixed(5)+' ask='+s.ask.toFixed(5)+' -> R:R '+v.ratio.toFixed(4)+' ACCEPTED';
  });

  await t('RR-1 a setup just UNDER the 1.99 minimum is refused, with an R:R reason -- one half-pip away from RR-2',async function(){
    g.setCfg(); g.resetPairData(); g.resetStructuralAOICache();
    g.setM15Bars(reversalM15());
    g.resetScanData(); g.setScanData('EUR/USD',BULLISH_TABLE);
    const s=askForRatio(1.98);
    g.setBidAsk(s.ask-0.0002,s.ask);
    const v=await g.evaluateLiveTrigger('EUR_USD');
    eq(v.fires,false,'a ratio below the minimum must be refused');
    eq(v.reason,'R:R only 1.98:1','and the reason must name R:R and the ratio it computed');
    // The refusal is the R:R gate and nothing else: the identical series fires in RR-2 with an ask
    // half a pip lower, and the score is untouched.
    ok(v.conf&&v.conf.total>=g.ALERT_THRESHOLD(),'the score still cleared its own gate ('+(v.conf&&v.conf.total)+')');
    const over=askForRatio(2.00);
    ok(Math.abs(over.ask-s.ask)<0.0001,
      'the accepted and refused cases differ by less than one pip of live fill: '+
      over.ask.toFixed(5)+' vs '+s.ask.toFixed(5));
    return 'ask='+s.ask.toFixed(5)+' -> "'+v.reason+'" REFUSED, while '+over.ask.toFixed(5)+' fires';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S3 — ALERT_THRESHOLD (55)
  // ══════════════════════════════════════════════════════════════════════════════════════════

  await t('THRESH-1 the frozen scorer produces EXACTLY 55 on the S1 series, from the components claimed',async function(){
    g.resetScanData(); g.setScanData('EUR/USD',BEARISH_TABLE);
    const c=g.scoreConfluence(reversalM15(),'EUR_USD','long');
    const W=g.WEIGHTS();
    eq(c.total,55,'exactly the threshold value');
    eq(c.items[IDX.bias].state,'miss','bias withheld (the table is Bearish, the read is long)');
    eq(c.items[IDX.bias].pts,0,'and contributes nothing');
    eq(c.items[IDX.aoi].state,'miss','no AOI: the monotonic filler is provably swing-free');
    eq(c.items[IDX.aoi].pts,0,'so the AOI term is a proven zero, not an assumed one');
    eq(c.items[IDX.wick].state,'hit','a long lower wick');
    eq(c.items[IDX.wick].pts,W.wick,'at its full frozen weight');
    eq(c.items[IDX.engulf].state,'hit','a one-candle engulf');
    eq(c.items[IDX.engulf].pts,W.engulf,'at its full frozen weight');
    eq(c.items[IDX.session].state,'hit','a priority session');
    eq(c.items[IDX.session].pts,W.session,'at its full frozen weight');
    eq(c.items[IDX.msb].state,'hit','and a market-structure break');
    eq(c.items[IDX.msb].pts,W.msb,'at its full frozen weight');
    eq(W.wick+W.engulf+W.session+W.msb,55,'those four frozen weights sum to exactly the threshold');
    return '55 = wick '+W.wick+' + engulf '+W.engulf+' + session '+W.session+' + MSB '+W.msb+', bias 0, AOI 0';
  });

  await t('THRESH-2 the gate ADMITS exactly 55 and REFUSES the same series one candle-high later',async function(){
    g.setCfg(); g.resetPairData(); g.resetScanData(); g.setScanData('EUR/USD',BEARISH_TABLE);
    // ADMITTED at 55: the verdict gets past the confluence gate and is stopped by a LATER gate.
    g.resetStructuralAOICache(); g.setM15Bars(reversalM15()); g.setBidAsk(1.10025,1.10035);
    const at55=await g.evaluateLiveTrigger('EUR_USD');
    ok(at55.conf,'the verdict must carry the score it computed: '+JSON.stringify(at55));
    eq(at55.conf.total,55,'precondition: the series scores exactly the threshold');
    ok(at55.reason!=='Confluence below threshold',
      'a score of exactly '+g.ALERT_THRESHOLD()+' must NOT be refused by the confluence gate -- it was refused by: "'+at55.reason+'"');
    // REFUSED below it. ONE variable: prev2's high rises 1 pip, prev.h > prev2.h stops holding,
    // the MSB term disappears and the same series scores 45.
    g.resetStructuralAOICache(); g.setM15Bars(reversalM15(1.10030));
    const below=await g.evaluateLiveTrigger('EUR_USD');
    eq(below.conf.total,45,'with MSB removed the same series scores 45');
    eq(below.fires,false,'and must not fire');
    eq(below.reason,'Confluence below threshold','refused BY the confluence gate this time');
    return '55 admitted (stopped later by "'+at55.reason+'"); 45 refused by the gate itself';
  });

  await t('THRESH-3 the reachable-score lattice: 55 exists, 54 and 56 do NOT',async function(){
    // Confluence totals are sums drawn from the frozen WEIGHTS, so only certain values are
    // reachable at all. This enumerates the SUPERSET of every attainable total from the real
    // constant (some combinations are geometrically impossible, which only makes the superset
    // larger, never smaller -- so "not in this set" is a proof of unreachability).
    //
    // WHY THIS FIXTURE EXISTS: it is the honest record of an UNKILLABLE mutation. Lowering
    // ALERT_THRESHOLD from 55 to 54 changes the gate's verdict only for a total of exactly 54,
    // and no input can produce 54, so 55->54 is an equivalent mutant under the frozen weights,
    // not a coverage gap. Raising it to 56 is NOT equivalent, because 55 is reachable and is
    // asserted in THRESH-2. This fixture also pins the weights themselves: change any one of
    // them and 54 or 56 becomes reachable and this fails.
    const W=g.WEIGHTS();
    const dims=[
      [0,W.bias2,W.bias3],
      [0,W.aoi],
      [0,Math.round(W.wick*0.5),W.wick],
      [0,W.engulf],
      [0,Math.round(W.session*0.5),W.session],
      [0,W.msb]
    ];
    let sums=[0];
    dims.forEach(function(d){
      const next=[];
      sums.forEach(function(s){ d.forEach(function(v){ next.push(s+v); }); });
      sums=next;
    });
    const reachable={};
    sums.forEach(function(s){ reachable[Math.min(s,100)]=true; });
    ok(reachable[55],'55 must be reachable -- THRESH-1 reaches it for real');
    ok(!reachable[54],'54 must be unreachable, which is why ALERT_THRESHOLD 55->54 cannot be killed by any fixture');
    ok(!reachable[56],'56 must be unreachable too');
    eq(g.ALERT_THRESHOLD(),55,'and the frozen threshold sits on a reachable value');
    return Object.keys(reachable).length+' distinct totals reachable from the frozen weights; 54 and 56 are not among them';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S4 — THE AOI 3-TOUCH RULE
  // RULES.entry: "AOI validation: minimum 3 touches/reactions — fewer than 3 = no AOI, move on."
  // ══════════════════════════════════════════════════════════════════════════════════════════

  await t('AOI3-0 PRECONDITION: both candidate levels are genuine, detected swing structure',async function(){
    // Without this, "the 2-touch level was not returned" could mean the engine never saw it --
    // which would make the whole section vacuous. It saw it. It discarded it BY COUNT.
    const bars=shelfSeries(PLATEAU_S4,TOUCH_3.concat(TOUCH_2));
    const sw=g.findSwingPoints(bars,3);
    eq(sw.swingLows.length,5,'five real swing lows are detected');
    eq(sw.swingLows.filter(function(p){return Math.abs(p-1.09500)<1e-9;}).length,3,'three of them at 1.09500');
    eq(sw.swingLows.filter(function(p){return Math.abs(p-1.09900)<1e-9;}).length,2,'and two at 1.09900');
    eq(sw.swingHighs.length,0,'the flat plateau produces no swing highs, so nothing competes on the other side');
    return 'detected swing lows: 3 x 1.09500, 2 x 1.09900';
  });

  await t('AOI3-1 a 3-touch level IS an AOI and a 2-touch level is NOT -- even though 2-touch is nearer',async function(){
    const bars=shelfSeries(PLATEAU_S4,TOUCH_3.concat(TOUCH_2));
    const aoi=g.computeAOI(bars,100,3);
    ok(aoi.support!=null,'a support AOI must be found at all');
    near(aoi.support,1.09500,1e-9,'the returned support is the 3-touch level');
    ok(Math.abs(aoi.support-1.09900)>0.001,
      'and is NOT the 2-touch level -- which sits NEARER current price and would be preferred by the '+
      'nearest-zone sort if the touch rule were relaxed at all');
    return 'support='+aoi.support.toFixed(5)+' (3 touches); the nearer 2-touch level at 1.09900 was discarded';
  });

  await t('AOI3-2 computeAOIWithTouches reports the real count, and it is exactly 3',async function(){
    const bars=shelfSeries(PLATEAU_S4,TOUCH_3.concat(TOUCH_2));
    const wt=g.computeAOIWithTouches(bars,100,3);
    near(wt.support,1.09500,1e-9,'same level as computeAOI');
    eq(wt.supportTouches,3,'and exactly three touches, not a placeholder or a bare boolean');
    eq(wt.resistanceTouches,0,'with no resistance zone, the count is zero rather than fabricated');
    return 'supportTouches=3 at '+wt.support.toFixed(5);
  });

  await t('AOI3-3 THE CONTROL: adding a THIRD touch to the 2-touch level promotes it -- one bar away',async function(){
    // The decisive control. If the rule counted anything other than touches, adding one more
    // touch at 1.09900 could not change the answer. It does: the level flips.
    const before=g.computeAOI(shelfSeries(PLATEAU_S4,TOUCH_3.concat(TOUCH_2)),100,3);
    const promoted=TOUCH_2.concat([{idx:40,l:1.09900}]);
    const after=g.computeAOIWithTouches(shelfSeries(PLATEAU_S4,TOUCH_3.concat(promoted)),100,3);
    near(before.support,1.09500,1e-9,'before: the far 3-touch level');
    near(after.support,1.09900,1e-9,'after ONE extra touch: the nearer level qualifies and wins the nearest-zone sort');
    eq(after.supportTouches,3,'and now reports three touches of its own');
    return '1.09900 with 2 touches -> discarded; with 3 touches -> returned. Nothing else changed.';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S5 — PATTERN THRESHOLDS
  // Every fixture below passes an explicit bias override of '—', so the pattern rules are tested
  // in isolation from the bias table entirely.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  await t('PATTERN-WICK-1 rejection wick at EXACTLY 0.55 of range is NOT a wick; one tick more is',async function(){
    // Boundary candles found by search so the division is exact in binary floating point.
    // At-boundary: l=1.09900 h=1.10240 max(o,c)=1.10053 -> upper wick / range === 0.55 exactly.
    const at=quiet([bar(1.10053,1.10240,1.09900,1.09993)]);
    const atLast=at[at.length-1];
    const atRatio=(atLast.h-Math.max(atLast.o,atLast.c))/(atLast.h-atLast.l);
    eq(atRatio,0.55,'PRECONDITION: the at-boundary candle divides to exactly 0.55 in this engine');
    const atSigs=g.detectSignals(at,'EUR_USD','—');
    eq(findSig(atSigs,'wick','sell'),null,'the rule is strictly greater-than: exactly 0.55 is NOT a rejection wick');
    // POSITIVE CONTROL, one tick of the body away: max(o,c) 1.10053 -> 1.10052.
    const over=quiet([bar(1.10052,1.10240,1.09900,1.09993)]);
    const overLast=over[over.length-1];
    const overRatio=(overLast.h-Math.max(overLast.o,overLast.c))/(overLast.h-overLast.l);
    ok(overRatio>0.55,'the control candle is genuinely over the line: '+overRatio);
    const overSig=findSig(g.detectSignals(over,'EUR_USD','—'),'wick','sell');
    ok(overSig,'one tick past the boundary a rejection wick IS reported');
    eq(overSig.dir,'sell','an UPPER wick is a sell-side rejection');
    return 'ratio 0.55 -> silent; ratio '+overRatio.toFixed(6)+' -> "'+overSig.label+'"';
  });

  await t('PATTERN-WICK-2 a wick just UNDER the line stays silent',async function(){
    const under=quiet([bar(1.10054,1.10240,1.09900,1.09993)]);
    const uLast=under[under.length-1];
    const uRatio=(uLast.h-Math.max(uLast.o,uLast.c))/(uLast.h-uLast.l);
    ok(uRatio<0.55&&uRatio>0.50,'the candle sits just under the line, inside the range a loosened threshold would admit: '+uRatio);
    eq(findSig(g.detectSignals(under,'EUR_USD','—'),'wick','sell'),null,'and is not reported');
    return 'ratio '+uRatio.toFixed(6)+' -> silent';
  });

  await t('PATTERN-WICK-3 the LOWER wick carries its own 0.55 boundary, tested at the edge in its own right',async function(){
    // The two wick sides are separate lines of code with separate comparisons. A boundary proven
    // only on the upper side leaves the lower one free to be loosened, so the mirror is tested at
    // its own exact edge rather than merely "somewhere over the line".
    const at=quiet([bar(1.10087,1.10240,1.09900,1.10147)]);
    const aL=at[at.length-1];
    const aRatio=(Math.min(aL.o,aL.c)-aL.l)/(aL.h-aL.l);
    eq(aRatio,0.55,'PRECONDITION: the at-boundary candle divides to exactly 0.55 on the LOWER side');
    eq(findSig(g.detectSignals(at,'EUR_USD','—'),'wick','buy'),null,
      'exactly 0.55 is NOT a lower rejection wick either -- the mirror is strict too');
    // POSITIVE CONTROL, one tick of the body away.
    const over=quiet([bar(1.10088,1.10240,1.09900,1.10147)]);
    const oL=over[over.length-1];
    const oRatio=(Math.min(oL.o,oL.c)-oL.l)/(oL.h-oL.l);
    ok(oRatio>0.55,'the control candle is genuinely over the line: '+oRatio);
    const sig=findSig(g.detectSignals(over,'EUR_USD','—'),'wick','buy');
    ok(sig,'one tick past the boundary a lower rejection wick IS reported');
    eq(sig.dir,'buy','a LOWER wick is a buy-side rejection');
    return 'lower ratio 0.55 -> silent; ratio '+oRatio.toFixed(6)+' -> "'+sig.label+'"';
  });

  await t('PATTERN-DOJI-1 a body of EXACTLY 0.12 of range is NOT a doji; a smaller body is',async function(){
    // Boundary candle found by search: l=1.09500 h=1.09925 o=1.09806 c=1.09857 -> body/range === 0.12.
    const at=quiet([bar(1.09806,1.09925,1.09500,1.09857)]);
    const aL=at[at.length-1];
    eq(Math.abs(aL.c-aL.o)/(aL.h-aL.l),0.12,'PRECONDITION: the at-boundary candle divides to exactly 0.12');
    const atSigs=g.detectSignals(at,'EUR_USD','—');
    eq(findSig(atSigs,'doji','neutral'),null,'the rule is strictly less-than: exactly 0.12 is NOT a doji');
    ok(atSigs.length>0,'and the candle is NOT silent for other reasons -- it still reports '+typesOf(atSigs)+
      ', so this is a targeted absence, not a dead input');
    // POSITIVE CONTROL, one variable away: the open rises 5 ticks, shrinking the body to 0.108.
    const under=quiet([bar(1.09811,1.09925,1.09500,1.09857)]);
    const uL=under[under.length-1];
    const uRatio=Math.abs(uL.c-uL.o)/(uL.h-uL.l);
    ok(uRatio<0.12&&uRatio>0.10,'the control body sits under the line but inside the range a tightened threshold would reject: '+uRatio);
    const dj=findSig(g.detectSignals(under,'EUR_USD','—'),'doji','neutral');
    ok(dj,'and IS reported as a doji');
    eq(dj.dir,'neutral','a doji is directionless');
    return 'body 0.12 -> not a doji (other signals still present: '+typesOf(atSigs)+'); body '+uRatio.toFixed(5)+' -> doji';
  });

  await t('PATTERN-DOJI-2 a body just OVER the line stays silent',async function(){
    const over=quiet([bar(1.09801,1.09925,1.09500,1.09857)]);
    const oL=over[over.length-1];
    const oRatio=Math.abs(oL.c-oL.o)/(oL.h-oL.l);
    ok(oRatio>0.12&&oRatio<0.15,'inside the range a loosened threshold would admit: '+oRatio);
    eq(findSig(g.detectSignals(over,'EUR_USD','—'),'doji','neutral'),null,'and is not a doji');
    return 'body '+oRatio.toFixed(5)+' -> silent';
  });

  await t('PATTERN-ENGULF-1 ONE swallowed candle is an engulf; ZERO is not -- one tick of the prior low apart',async function(){
    const pos=quiet([bar(1.10060,1.10080,1.10040,1.10070),
                     bar(1.10050,1.10055,1.10005,1.10010),
                     bar(1.10000,1.10070,1.09990,1.10060)]);
    const sig=findSig(g.detectSignals(pos,'EUR_USD','—'),'engulf','buy');
    ok(sig,'a body that fully swallows exactly one opposite-coloured candle IS a bullish engulf');
    eq(sig.count,1,'and the count reported is exactly one');
    eq(typesOf(g.detectSignals(pos,'EUR_USD','—')),'engulf:buy','with no other pattern muddying the case');
    // NEGATIVE CONTROL: the swallowed candle's LOW drops one pip below the engulfing body's open,
    // so it is no longer contained. Nothing else moves.
    const neg=quiet([bar(1.10060,1.10080,1.10040,1.10070),
                     bar(1.10050,1.10055,1.09995,1.10010),
                     bar(1.10000,1.10070,1.09990,1.10060)]);
    eq(findSig(g.detectSignals(neg,'EUR_USD','—'),'engulf','buy'),null,
      'a candle that swallows NOTHING is not an engulf');
    return 'swallow count 1 -> reported; swallow count 0 -> silent (prior low 1.10005 -> 1.09995)';
  });

  await t('PATTERN-ENGULF-2 a bullish engulf REQUIRES the swallowed candle to be bearish',async function(){
    // Same containment, same geometry -- only the swallowed candle's COLOUR is flipped, by
    // swapping its open and close. The bar it engulfs is still entirely inside the body.
    const bearishPrev=quiet([bar(1.10060,1.10080,1.10040,1.10070),
                             bar(1.10050,1.10055,1.10005,1.10010),
                             bar(1.10000,1.10070,1.09990,1.10060)]);
    const bullishPrev=quiet([bar(1.10060,1.10080,1.10040,1.10070),
                             bar(1.10010,1.10055,1.10005,1.10050),
                             bar(1.10000,1.10070,1.09990,1.10060)]);
    ok(findSig(g.detectSignals(bearishPrev,'EUR_USD','—'),'engulf','buy'),
      'POSITIVE CONTROL: with a bearish prior candle it is an engulf');
    eq(findSig(g.detectSignals(bullishPrev,'EUR_USD','—'),'engulf','buy'),null,
      'with a BULLISH prior candle -- same highs, same lows, same containment -- it is not');
    return 'prior candle 1.10050->1.10010 (bearish) engulfs; 1.10010->1.10050 (bullish) does not';
  });

  await t('PATTERN-ENGULF-3 the bearish engulf is the exact mirror, colour requirement included',async function(){
    const pos=quiet([bar(1.09990,1.10080,1.09980,1.10070),
                     bar(1.10010,1.10055,1.10005,1.10050),
                     bar(1.10060,1.10070,1.09990,1.10000)]);
    const sig=findSig(g.detectSignals(pos,'EUR_USD','—'),'engulf','sell');
    ok(sig,'a bearish body swallowing one bullish candle IS a bearish engulf');
    eq(sig.count,1,'count exactly one');
    eq(typesOf(g.detectSignals(pos,'EUR_USD','—')),'engulf:sell','and nothing else fires');
    const neg=quiet([bar(1.09990,1.10080,1.09980,1.10070),
                     bar(1.10050,1.10055,1.10005,1.10010),
                     bar(1.10060,1.10070,1.09990,1.10000)]);
    eq(findSig(g.detectSignals(neg,'EUR_USD','—'),'engulf','sell'),null,
      'with a BEARISH prior candle -- same containment -- it is not');
    return 'mirror confirmed: bullish prior engulfed -> sell signal; bearish prior -> silent';
  });

  await t('PATTERN-MSB-1 a bullish MSB REQUIRES the close beyond the level, not just the high',async function(){
    // POSITIVE CONTROL: three ascending highs and a bullish close.
    const pos=quiet([bar(1.10020,1.10040,1.10000,1.10030),
                     bar(1.10030,1.10060,1.10000,1.10040),
                     bar(1.10020,1.10080,1.10010,1.10070)]);
    const sig=findSig(g.detectSignals(pos,'EUR_USD','—'),'msb','buy');
    ok(sig,'ascending highs with a bullish close IS a bullish market-structure break');
    eq(typesOf(g.detectSignals(pos,'EUR_USD','—')),'msb:buy','and nothing else fires');
    // NEGATIVE CONTROL: the SAME three highs and the SAME low. Only the open and close swap, so
    // the level is still taken out intraday but the candle closes back below its open.
    const neg=quiet([bar(1.10020,1.10040,1.10000,1.10030),
                     bar(1.10030,1.10060,1.10000,1.10040),
                     bar(1.10070,1.10080,1.10010,1.10020)]);
    const negSigs=g.detectSignals(neg,'EUR_USD','—');
    eq(findSig(negSigs,'msb','buy'),null,'without a bullish CLOSE it is not a break');
    eq(negSigs.length,0,'and nothing else is reported in its place: '+typesOf(negSigs));
    return 'same highs 1.10040 < 1.10060 < 1.10080; bullish close -> MSB, bearish close -> nothing';
  });

  await t('PATTERN-MSB-2 the bearish MSB is the exact mirror, close requirement included',async function(){
    const pos=quiet([bar(1.10060,1.10070,1.10040,1.10050),
                     bar(1.10050,1.10065,1.10020,1.10030),
                     bar(1.10060,1.10070,1.10000,1.10010)]);
    ok(findSig(g.detectSignals(pos,'EUR_USD','—'),'msb','sell'),'descending lows with a bearish close IS a bearish break');
    eq(typesOf(g.detectSignals(pos,'EUR_USD','—')),'msb:sell','and nothing else fires');
    const neg=quiet([bar(1.10060,1.10070,1.10040,1.10050),
                     bar(1.10050,1.10065,1.10020,1.10030),
                     bar(1.10010,1.10070,1.10000,1.10060)]);
    const negSigs=g.detectSignals(neg,'EUR_USD','—');
    eq(findSig(negSigs,'msb','sell'),null,'without a bearish CLOSE it is not a break');
    eq(negSigs.length,0,'and nothing else is reported in its place: '+typesOf(negSigs));
    return 'same lows 1.10040 > 1.10020 > 1.10000; bearish close -> MSB, bullish close -> nothing';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S6 — getSession WINDOW EDGES
  //
  // DISCREPANCY RECORDED, DELIBERATELY NOT "FIXED": the coverage audit's recipe for this section
  // asked for 21:00 UTC -> active===false. That is NOT what the frozen function does. The New
  // York branch runs from 1200 to 2100 MINUTES (20:00 to 35:00 UTC, i.e. to the end of the day),
  // so Off-hours is 00:00-07:59 only and 21:00 is inside New York. These fixtures assert the
  // frozen behaviour, not the recipe -- a fixture written to the recipe would have been wrong and
  // would have demanded a production change to satisfy it.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  await t('SESSION-1 the Off-hours / London edge is 08:00 UTC to the minute',async function(){
    const before=g.getSession(g.utc(2026,7,10,7,59));
    const after=g.getSession(g.utc(2026,7,10,8,0));
    eq(before.name,'Off-hours','07:59 is off-hours');
    eq(before.active,false,'and inactive');
    eq(before.priority,false,'and not priority');
    eq(after.name,'London','08:00 opens London');
    eq(after.active,true,'active');
    eq(after.priority,true,'and a priority window');
    return '07:59 Off-hours(inactive) | 08:00 London(priority)';
  });

  await t('SESSION-2 the London / Overlap edge is 12:00 UTC to the minute',async function(){
    eq(g.getSession(g.utc(2026,7,10,11,59)).name,'London','11:59 is still London');
    eq(g.getSession(g.utc(2026,7,10,12,0)).name,'London/NY Overlap','12:00 opens the overlap');
    eq(g.getSession(g.utc(2026,7,10,12,0)).priority,true,'which is a priority window');
    return '11:59 London | 12:00 London/NY Overlap';
  });

  await t('SESSION-3 the Overlap / London edge is 16:00 UTC to the minute',async function(){
    eq(g.getSession(g.utc(2026,7,10,15,59)).name,'London/NY Overlap','15:59 is still the overlap');
    eq(g.getSession(g.utc(2026,7,10,16,0)).name,'London','16:00 returns to London');
    return '15:59 London/NY Overlap | 16:00 London';
  });

  await t('SESSION-4 the priority window ends at 20:00 UTC to the minute',async function(){
    const last=g.getSession(g.utc(2026,7,10,19,59));
    const first=g.getSession(g.utc(2026,7,10,20,0));
    eq(last.name,'London','19:59 is the last London minute');
    eq(last.priority,true,'and it is still priority');
    eq(first.name,'New York','20:00 opens New York');
    eq(first.priority,false,'which is explicitly NOT priority');
    eq(first.active,true,'but is active -- worth half the session weight, not zero');
    return '19:59 London(priority=true) | 20:00 New York(priority=false, active=true)';
  });

  await t('SESSION-5 21:00 UTC is New York and ACTIVE -- the frozen window runs to end of day',async function(){
    const s=g.getSession(g.utc(2026,7,10,21,0));
    eq(s.name,'New York','21:00 is New York');
    eq(s.active,true,'and still active');
    eq(s.priority,false,'though not priority');
    const midnight=g.getSession(g.utc(2026,7,10,23,59));
    eq(midnight.name,'New York','23:59 is the last New York minute of the day');
    eq(g.getSession(g.utc(2026,7,10,0,0)).name,'Off-hours','and 00:00 falls back to off-hours');
    return '21:00 New York(active) | 23:59 New York | 00:00 Off-hours';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S7 — THE getBias TABLE
  // ══════════════════════════════════════════════════════════════════════════════════════════

  await t('BIASTAB-1 a SINGLE directional timeframe sets the bias -- the previously unprotected rule',async function(){
    eq(g.getBias({weekly:'Bullish',daily:'—',fh:'—'}),'Bullish','one Bullish, two blank -> Bullish');
    eq(g.getBias({weekly:'Bearish',daily:'—',fh:'—'}),'Bearish','one Bearish, two blank -> Bearish');
    eq(g.getBias({weekly:'—',daily:'Bullish',fh:'—'}),'Bullish','position in the table does not matter');
    eq(g.getBias({weekly:'—',daily:'—',fh:'Bearish'}),'Bearish','nor does which timeframe it is');
    return 'a lone directional timeframe carries the bias, from any slot';
  });

  await t('BIASTAB-2 one against one is Split, not a winner',async function(){
    eq(g.getBias({weekly:'Bullish',daily:'Bearish',fh:'—'}),'Split','1-1 with a blank -> Split');
    eq(g.getBias({weekly:'Bearish',daily:'Bullish',fh:'—'}),'Split','and the order does not break the tie');
    return '1-1 -> Split, either way round';
  });

  await t('BIASTAB-3 an empty table is em-dash, never a direction',async function(){
    eq(g.getBias({weekly:'—',daily:'—',fh:'—'}),'—','nothing set -> no bias');
    eq(g.getBias({weekly:'Ranging',daily:'Ranging',fh:'Ranging'}),'—','and non-directional values are not counted as direction');
    return 'empty and non-directional tables both -> "—"';
  });

  await t('BIASTAB-4 a majority wins and a sweep wins, and the score reflects the difference',async function(){
    eq(g.getBias({weekly:'Bullish',daily:'Bullish',fh:'Bearish'}),'Bullish','2-1 -> the majority');
    eq(g.getBias({weekly:'Bullish',daily:'Bullish',fh:'Bullish'}),'Bullish','3-0 -> the same direction');
    eq(g.getScore({weekly:'Bullish',daily:'Bullish',fh:'Bearish'}),2,'but 2-1 scores 2');
    eq(g.getScore({weekly:'Bullish',daily:'Bullish',fh:'Bullish'}),3,'and 3-0 scores 3 -- the A-grade the rules single out');
    return '2-1 Bullish(score 2) | 3-0 Bullish(score 3)';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S8 — scoreConfluence ITEM-LEVEL STATE AND POINTS
  // Asserting only `total` cannot see AOI credited to the wrong side, or one weight swapped for
  // another that happens to sum the same. These fixtures assert the item.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  const PLATEAU_S8={o:1.09800,h:1.09900,l:1.09700,c:1.09800};
  // A support shelf with the close resting ON it, and no resistance structure at all.
  const SUP_SERIES=shelfSeries(PLATEAU_S8,TOUCH_3,{o:1.09600,h:1.09610,l:1.09550,c:1.09560});
  // The mirror: a resistance ceiling with the close resting under it, and no support structure.
  const RES_SERIES=shelfSeries(PLATEAU_S8,[{idx:5,h:1.10200},{idx:12,h:1.10200},{idx:19,h:1.10200}],
                               {o:1.10100,h:1.10150,l:1.10090,c:1.10140});
  // Off-hours and a blank bias, so every item except AOI is a proven zero and the total IS the
  // AOI term. sessionAt/score/bias are scoreConfluence's own documented overrides -- ordinary
  // inputs, not a stub of anything.
  const NEUTRAL={score:0,bias:'—',sessionAt:g.utc(2026,7,10,3,0)};

  await t('CONFITEM-0 the frozen WEIGHTS table itself, pinned to its literal values',async function(){
    // WHY THIS FIXTURE EXISTS, in its own words: every other fixture in this section expresses
    // intent by comparing an item's points against WEIGHTS.<term>. That is the right way to say
    // "credited at its full weight" -- and it is exactly why those fixtures CANNOT see a weight
    // change: they read the same constant they assert against, so they stay true whatever the
    // number becomes. Mutation testing caught precisely that (WEIGHTS.aoi 20 -> 15 survived the
    // entire gate). One fixture therefore has to pin the literals, and this is it.
    const W=g.WEIGHTS();
    eq(W.bias3,25,'3/3 top-down alignment');
    eq(W.bias2,15,'2/3 alignment, deliberately worth less');
    eq(W.aoi,20,'AOI zone touch');
    eq(W.wick,15,'rejection wick');
    eq(W.engulf,20,'engulfing entry trigger');
    eq(W.session,10,'priority session');
    eq(W.msb,10,'market-structure break');
    // The strongest single reading -- 3/3 bias plus every other term -- is exactly 100, which is
    // why the Math.min(total,100) clamp never actually clips a real score. Change any weight and
    // either this identity or the clamp's meaning breaks.
    eq(W.bias3+W.aoi+W.wick+W.engulf+W.session+W.msb,100,
      'the best attainable confluence is exactly 100, so the 100 cap is a guard and not a clip');
    ok(W.bias3>W.bias2,'and 3/3 is genuinely worth more than 2/3');
    return 'bias3 25, bias2 15, aoi 20, wick 15, engulf 20, session 10, msb 10; max attainable = 100';
  });

  await t('CONFITEM-1 a LONG at a support AOI gets the AOI item HIT at its full weight',async function(){
    const aoi=g.findAOIs(SUP_SERIES);
    near(aoi.support,1.09500,1e-9,'PRECONDITION: the series really does carry a 3-touch support');
    eq(aoi.resistance,null,'and carries no resistance, so the sides cannot be confused by accident');
    const c=g.scoreConfluence(SUP_SERIES,'EUR_USD','long',NEUTRAL);
    eq(c.items[IDX.aoi].state,'hit','a long resting on support is an AOI hit');
    eq(c.items[IDX.aoi].pts,g.WEIGHTS().aoi,'credited at the full frozen AOI weight');
    eq(c.total,g.WEIGHTS().aoi,'and with every other term withheld the total IS the AOI weight');
    return 'long at support -> AOI hit, '+c.items[IDX.aoi].pts+' pts, total '+c.total;
  });

  await t('CONFITEM-2 the SAME candle taken SHORT at that support gets the AOI item MISS',async function(){
    const c=g.scoreConfluence(SUP_SERIES,'EUR_USD','short',NEUTRAL);
    eq(c.items[IDX.aoi].state,'miss','support does not credit a short');
    eq(c.items[IDX.aoi].pts,0,'and pays nothing');
    eq(c.total,0,'the whole score collapses to zero -- AOI was the only term available');
    return 'same candle, short -> AOI miss, total 0 (long scored '+g.WEIGHTS().aoi+')';
  });

  await t('CONFITEM-3 the mirror: a SHORT at a resistance AOI hits, the LONG misses',async function(){
    const aoi=g.findAOIs(RES_SERIES);
    near(aoi.resistance,1.10200,1e-9,'PRECONDITION: a 3-touch resistance exists');
    eq(aoi.support,null,'and no support');
    const s=g.scoreConfluence(RES_SERIES,'EUR_USD','short',NEUTRAL);
    const l=g.scoreConfluence(RES_SERIES,'EUR_USD','long',NEUTRAL);
    eq(s.items[IDX.aoi].state,'hit','short at resistance -> hit');
    eq(s.items[IDX.aoi].pts,g.WEIGHTS().aoi,'at full weight');
    eq(l.items[IDX.aoi].state,'miss','long at resistance -> miss');
    eq(l.total,0,'and scores nothing');
    return 'resistance credits the short ('+s.total+') and not the long ('+l.total+') -- the exact inverse of CONFITEM-1/2';
  });

  await t('CONFITEM-4 the bias item carries the RIGHT label and the RIGHT weight for 3/3 and 2/3',async function(){
    const W=g.WEIGHTS();
    const three=g.scoreConfluence(SUP_SERIES,'EUR_USD','long',{score:3,bias:'Bullish',sessionAt:NEUTRAL.sessionAt});
    eq(three.items[IDX.bias].label,'Bias 3/3 aligned','a 3/3 aligned table is labelled as such');
    eq(three.items[IDX.bias].state,'hit','and is a hit');
    eq(three.items[IDX.bias].pts,W.bias3,'paid at the bias3 weight');
    eq(three.total,W.bias3+W.aoi,'total = bias3 + AOI, nothing else');
    const two=g.scoreConfluence(SUP_SERIES,'EUR_USD','long',{score:2,bias:'Bullish',sessionAt:NEUTRAL.sessionAt});
    eq(two.items[IDX.bias].label,'Bias 2/3 aligned','a 2/3 table is labelled separately');
    eq(two.items[IDX.bias].pts,W.bias2,'and paid at the LOWER bias2 weight');
    ok(W.bias3>W.bias2,'the two weights are genuinely different ('+W.bias3+' vs '+W.bias2+'), so the labels cannot be swapped unnoticed');
    return '3/3 -> '+W.bias3+' pts, 2/3 -> '+W.bias2+' pts, totals '+three.total+' / '+two.total;
  });

  await t('CONFITEM-5 a bias pointing the OTHER way pays nothing, however strong it is',async function(){
    const against=g.scoreConfluence(SUP_SERIES,'EUR_USD','long',{score:3,bias:'Bearish',sessionAt:NEUTRAL.sessionAt});
    eq(against.items[IDX.bias].label,'Bias alignment','an unaligned bias is not labelled as aligned');
    eq(against.items[IDX.bias].state,'miss','it is a miss');
    eq(against.items[IDX.bias].pts,0,'and pays zero even at a 3/3 strength');
    eq(against.total,g.WEIGHTS().aoi,'so the total falls back to the AOI term alone');
    // A 3/3 table that is merely Split is also unaligned, and must not creep in through score.
    const split=g.scoreConfluence(SUP_SERIES,'EUR_USD','long',{score:3,bias:'Split',sessionAt:NEUTRAL.sessionAt});
    eq(split.items[IDX.bias].pts,0,'a Split bias pays nothing regardless of score');
    return 'Bearish@3 -> 0 pts; Split@3 -> 0 pts; Bullish@3 -> '+g.WEIGHTS().bias3+' pts';
  });

  await t('CONFITEM-6 the session item pays full, half and nothing at the three real session states',async function(){
    const W=g.WEIGHTS();
    const off=g.scoreConfluence(SUP_SERIES,'EUR_USD','long',{score:0,bias:'—',sessionAt:g.utc(2026,7,10,3,0)});
    const ny=g.scoreConfluence(SUP_SERIES,'EUR_USD','long',{score:0,bias:'—',sessionAt:g.utc(2026,7,10,20,30)});
    const pri=g.scoreConfluence(SUP_SERIES,'EUR_USD','long',{score:0,bias:'—',sessionAt:g.utc(2026,7,10,13,0)});
    eq(off.items[IDX.session].label,'Off-hours','03:00 is off-hours');
    eq(off.items[IDX.session].pts,0,'paying nothing');
    eq(ny.items[IDX.session].state,'partial','20:30 New York is active but not priority');
    eq(ny.items[IDX.session].pts,Math.round(W.session*0.5),'paying half the session weight');
    eq(pri.items[IDX.session].state,'hit','13:00 is a priority window');
    eq(pri.items[IDX.session].pts,W.session,'paying the full session weight');
    return 'off '+off.items[IDX.session].pts+' | active '+ny.items[IDX.session].pts+' | priority '+pri.items[IDX.session].pts;
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S9 — SWING DETECTION
  // ══════════════════════════════════════════════════════════════════════════════════════════

  // 20 bars, flat, with one candidate peak at index 10 and one dip at index 15. neighbourHigh is
  // the ONE variable: at 1.10500 it EQUALS the peak, at 1.10490 it is one pip below it.
  function swingSeries(neighbourHigh){
    const bars=[];
    for(let i=0;i<20;i++) bars.push(bar(1.10150,1.10200,1.10100,1.10150));
    bars[9]=bar(1.10150,neighbourHigh,1.10100,1.10150);
    bars[10]=bar(1.10150,1.10500,1.10100,1.10150);
    bars[15]=bar(1.10150,1.10200,1.10000,1.10150);
    return bars;
  }

  await t('SWING-1 a bar whose high EQUALS its neighbour’s is NOT a swing high',async function(){
    const tied=g.findSwingPoints(swingSeries(1.10500),3);
    eq(tied.swingHighs.length,0,'with an equal-high neighbour, neither bar qualifies -- the rule is not strictly greater');
    // POSITIVE CONTROL, one pip away: the neighbour drops to 1.10490 and the peak stands alone.
    const clear=g.findSwingPoints(swingSeries(1.10490),3);
    eq(clear.swingHighs.length,1,'one pip lower and the peak IS a swing high');
    near(clear.swingHighs[0],1.10500,1e-9,'at exactly the peak price');
    return 'neighbour 1.10500 (equal) -> 0 swing highs; neighbour 1.10490 -> 1 swing high at 1.10500';
  });

  await t('SWING-2 swing HIGHS are reported at all, alongside swing lows, and both are exact',async function(){
    // The audit found findSwingPoints could be made blind to highs entirely with nothing failing.
    const sw=g.findSwingPoints(swingSeries(1.10490),3);
    eq(sw.swingHighs.length,1,'exactly one swing high');
    near(sw.swingHighs[0],1.10500,1e-9,'reported at its own price, not the neighbour’s');
    eq(sw.swingLows.length,1,'exactly one swing low');
    near(sw.swingLows[0],1.10000,1e-9,'likewise at its own price');
    ok(sw.swingHighs[0]>sw.swingLows[0],'and the two are not the same value, so neither list can be standing in for the other');
    return 'swingHighs=[1.10500] swingLows=[1.10000]';
  });

  await t('SWING-3 an equal LOW is likewise not a swing low -- the rule is symmetric',async function(){
    function lowSeries(neighbourLow){
      const bars=[];
      for(let i=0;i<20;i++) bars.push(bar(1.10150,1.10200,1.10100,1.10150));
      bars[14]=bar(1.10150,1.10200,neighbourLow,1.10150);
      bars[15]=bar(1.10150,1.10200,1.10000,1.10150);
      return bars;
    }
    eq(g.findSwingPoints(lowSeries(1.10000),3).swingLows.length,0,'an equal-low neighbour disqualifies both');
    const clear=g.findSwingPoints(lowSeries(1.10010),3);
    eq(clear.swingLows.length,1,'one pip higher and the dip IS a swing low');
    near(clear.swingLows[0],1.10000,1e-9,'at exactly the dip price');
    return 'neighbour 1.10000 (equal) -> 0 swing lows; neighbour 1.10010 -> 1 swing low at 1.10000';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S10 — alexGZoneRole AT THE EXACT EDGE
  // The documented boundary is INCLUSIVE on both sides: a price sitting exactly on a zone edge is
  // still inside the zone. Neither edge had any fixture at any value.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  await t('ZONEROLE-1 a price exactly ON either zone edge is INSIDE the zone',async function(){
    const z={low:1.1000,high:1.1020};
    eq(g.alexGZoneRole(z,1.1020),'inside','exactly on the upper edge is inside, not above');
    eq(g.alexGZoneRole(z,1.1000),'inside','exactly on the lower edge is inside, not below');
    eq(g.alexGZoneRole(z,1.1010),'inside','and the middle is inside, as the control');
    return 'both edges and the middle all read "inside"';
  });

  await t('ZONEROLE-2 one tick beyond either edge flips the role, so "inside" is not a constant',async function(){
    const z={low:1.1000,high:1.1020};
    eq(g.alexGZoneRole(z,1.10201),'support','above the zone, the zone acts as support');
    eq(g.alexGZoneRole(z,1.09999),'resistance','below the zone, it acts as resistance');
    // and the pairing with ZONEROLE-1 is what makes the edges meaningful: 1.10200 vs 1.10201 is a
    // single tick and changes the answer.
    eq(g.alexGZoneRole(z,1.1020),'inside','while the edge itself stays inside');
    return '1.10201 support | 1.10200 inside | 1.10000 inside | 1.09999 resistance';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S11 — maxLiveEntryDelayPips (5.0)
  // The live-fill distance gate: a setup is REJECTED rather than chased when the actual fill has
  // moved too far from the setup's own qualificationClose. Uses the REAL frozen RULES_ALEXG.config
  // -- the fixture never supplies a config of its own, so the constant under test is the real one.
  //
  // NO PAPER TRADE IS PERSISTED. alexGConstructLivePosition is the pure decision core: it RETURNS
  // a position record and writes nothing to any account, journal or store. The ALEX state is reset
  // to empty before each call and nothing is ever committed.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  function alexDataset(){
    const bars=[];
    for(let i=0;i<40;i++){ const b=1.09900+i*0.00002; bars.push(bar(b,b+0.00030,b-0.00030,b+0.00010)); }
    return{H1:bars};
  }
  function alexSetup(){
    return{
      strategy:'alex_g_sr_v1',ruleVersion:'alex_g_sr_v1',pair:'EUR_USD',timeframe:'H1',
      setupId:'FIX-ENTRYDELAY',setupType:'A_repeatedReaction',setupLabel:'Repeated reaction',
      zoneRoleAtQualification:'support',zoneLow:1.09900,zoneHigh:1.09960,zoneCenter:1.09930,
      qualificationBarIndex:39,qualificationClose:1.10000,
      qualificationTimestamp:'2026-08-10T13:00:00.000Z',zoneId:'Z1',reactionId:'R1',
      zoneTouchNumber:3,zoneStrength:3,zoneQualityAtQualification:'validated',
      session:'London',dayOfWeek:'Mon',hourOfDay:13,trendContext:'up'
    };
  }
  function constructAt(ask){
    g.resetAlexG();
    return g.alexGConstructLivePosition(alexSetup(),alexDataset(),{bid:ask-0.0002,ask:ask},
      g.ALEXG_CONFIG(),10000,{});
  }

  await t('ENTRYDELAY-1 a live fill exactly 5.0 pips from the signal is ACCEPTED',async function(){
    eq(g.ALEXG_CONFIG().maxLiveEntryDelayPips,5,'PRECONDITION: the frozen limit is 5 pips');
    const r=constructAt(1.10050); // qualificationClose 1.10000 -> 5.0 pips
    eq(r.status,'TRADE OPENED','a fill exactly at the limit is not "too far": '+r.status+' / '+r.reason);
    eq(r.direction,'buy','a support-role repeated reaction is a buy');
    ok(r.position.entryDelayPips<=5,'and the recorded delay is at the limit, not past it: '+r.position.entryDelayPips);
    ok(r.position.stop<r.position.entry&&r.position.target>r.position.entry,'the constructed trade is coherent');
    return 'ask 1.10050 -> delay '+r.position.entryDelayPips.toFixed(4)+' pips -> '+r.status;
  });

  await t('ENTRYDELAY-2 one tick further -- 5.1 pips -- is REJECTED, never chased',async function(){
    const r=constructAt(1.10051); // one tick beyond: 5.1 pips
    eq(r.status,'BLOCKED — ENTRY MOVED','a fill past the limit must be blocked');
    eq(r.reason,'ENTRY_MOVED_TOO_FAR_FROM_SIGNAL','with the reason that names the rule');
    eq(r.direction,'buy','the direction is still resolved and reported, so the block is not a parse failure');
    // The pairing is the whole point: ENTRYDELAY-1 opens on the tick below this one.
    const accepted=constructAt(1.10050);
    eq(accepted.status,'TRADE OPENED','and one tick lower still opens -- the two differ by 0.1 pip');
    return 'ask 1.10051 -> '+r.reason+'; ask 1.10050 -> '+accepted.status;
  });

  await t('ENTRYDELAY-3 a fill AT the signal price is accepted, so the gate is a distance and not a coin-flip',async function(){
    const r=constructAt(1.10000);
    eq(r.status,'TRADE OPENED','a fill at the qualification close is obviously accepted');
    near(r.position.entryDelayPips,0,1e-6,'with a delay of zero');
    eq(r.position.entry,1.10000,'and the entry recorded is the actual live fill');
    return 'ask 1.10000 -> delay 0 pips -> TRADE OPENED';
  });

  return out;
  })();
}
