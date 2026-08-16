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

  // ── 🔴 §18.31: the SHORT side of the entry trigger had NO fixture anywhere in the repository ──
  // RR-1/RR-2 above exercise only the BUY leg. Independent verification proved the consequence:
  // changing the BUY stop buffer from pip*7 to pip*6 kills RR-1/RR-2, while the identical change
  // on the SELL leg killed ZERO of 2,222 fixtures. One quadrant of two, on the arithmetic that
  // sets the actual stop price of a live short.
  //
  // A falling series with a bearish engulfing reversal at the high, so detectSignals reports a
  // SHORT; the bid is then solved so the frozen formula lands exactly on the ratio wanted.
  function fallingFiller(n,start,step){
    const bars=[];
    for(let k=0;k<n;k++){ const b=start-k*step; bars.push(bar(b,b+0.00010,b-0.00010,b-0.00005)); }
    return bars;
  }
  function bearReversalM15(){
    const bars=fallingFiller(57,1.10200,0.00003);
    bars.push(bar(1.10035,1.10045,1.10010,1.10030));   // prev2
    bars.push(bar(1.10005,1.10028,1.10002,1.10020));   // prev : bullish, inside
    bars.push(bar(1.10030,1.10130,1.09990,1.10000));   // last : engulfs it, new LOW, long upper wick
    return bars;
  }
  // Mirror of askForRatio. Short: stop = resistance + 7 pips, target = support, entry = bid.
  //   ratio = (bid - support) / (stop - bid)  =>  bid = (support + ratio*stop) / (1 + ratio)
  function bidForRatio(ratio){
    const aoi=g.findAOIs(g.structuralCandles(120));
    const stop=aoi.resistance+g.pipSize('EUR_USD')*7;
    return{bid:(aoi.support+ratio*stop)/(1+ratio),support:aoi.support,resistance:aoi.resistance,stop:stop};
  }

  await t('RR-SHORT.1 the SELL leg fires, and its stop sits exactly 7 pips ABOVE the resistance AOI',async function(){
    g.setCfg(); g.resetPairData(); g.resetStructuralAOICache();
    g.setM15Bars(bearReversalM15());
    g.resetScanData(); g.setScanData('EUR/USD',BEARISH_TABLE);
    const s=bidForRatio(2.00);
    g.setBidAsk(s.bid,s.bid+0.0002);
    const v=await g.evaluateLiveTrigger('EUR_USD');
    eq(v.fires,true,'the short must actually fire, or nothing below is being observed: '+JSON.stringify(v));
    eq(v.dir,'sell','and it must be the SELL leg, not the buy one: '+JSON.stringify(v));
    near(v.stop,s.resistance+g.pipSize('EUR_USD')*7,1e-9,
      'the short stop is the resistance AOI plus exactly 7 pips of buffer; a 6-pip buffer moves the real stop of a live short');
    return 'resistance='+s.resistance.toFixed(5)+' stop='+v.stop.toFixed(5)+' ratio='+v.ratio.toFixed(4);
  });

  await t('RR-SHORT.2 the SELL leg refuses just UNDER the 1.99 minimum, one half-pip from RR-SHORT.1',async function(){
    g.setCfg(); g.resetPairData(); g.resetStructuralAOICache();
    g.setM15Bars(bearReversalM15());
    g.resetScanData(); g.setScanData('EUR/USD',BEARISH_TABLE);
    const s=bidForRatio(1.98);
    g.setBidAsk(s.bid,s.bid+0.0002);
    const v=await g.evaluateLiveTrigger('EUR_USD');
    eq(v.fires,false,'a short ratio below the minimum must be refused');
    eq(v.reason,'R:R only 1.98:1','and the reason must name R:R and the ratio it computed on the SHORT side');
    const over=bidForRatio(2.00);
    ok(Math.abs(over.bid-s.bid)<0.0001,
      'the accepted and refused shorts differ by less than one pip of live fill: '+over.bid.toFixed(5)+' vs '+s.bid.toFixed(5));
    return 'bid='+s.bid.toFixed(5)+' -> "'+v.reason+'" REFUSED';
  });

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

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S12 — THE ALEX FROZEN ZONE ENGINE'S OWN RULES
  //
  // WHAT WAS MISSING. The organic ALEX fixtures elsewhere in this repository (v126, v017,
  // run_v1236) do drive real candles end to end, and they do catch total blindness -- deleting
  // the engine kills 39 of them. But they assert only that A SETUP WAS PRODUCED AND A TRADE
  // OPENED. They never assert WHICH zone, at WHAT price, from WHICH touch, in WHICH direction.
  // That is exactly why an audit could invert the BREAK DIRECTION -- the field that decides
  // whether a break-and-retest is bought or sold -- and watch 1,514 fixtures stay green: the
  // scenario still yielded *a* setup. S12 asserts the zone and the setup themselves.
  //
  // HOW THE SERIES ARE BUILT, AND WHY IT IS STILL THE ENGINE THAT DECIDES.
  // Every S12 series is made of bars whose range is EXACTLY T = 2^-10 = 0.0009765625 price
  // units, with every close falling inside the following bar's own range. That makes each bar's
  // true range exactly T, so the frozen calcATR() -- which averages 14 true ranges -- returns
  // exactly T, with no floating-point residue at all (T and every partial sum k*T for k<=14 are
  // exact binary fractions, and 14T/14 is exact). Two things follow, and both are properties of
  // the ENGINE'S OWN arithmetic, not of anything the fixtures impose:
  //   * the reaction-displacement threshold is exactly 0.25*T = 2^-12, so a candle can be placed
  //     EXACTLY ON it -- the only way to kill a `>=` -> `>` flip on that comparison; and
  //   * the zone-cluster grouping tolerance is exactly 0.5*T, so cluster membership is decidable
  //     by hand and the resulting zone boundaries are exact, assertable numbers.
  // Everything after that is the frozen engine's: which bars are swings, which reactions
  // qualify, where the zone's edges lock, how many touches it counts, when it breaks, which way
  // it broke, and what setup (if any) that produces. The fixtures report those verdicts.
  //
  // A swing anchor here is a bar whose low dips below its six neighbours (or whose high rises
  // above them). The engine's own swing test is STRICT on both sides, so two bars sharing a low
  // are neither of them a swing -- that is used deliberately to place wick-only penetrations
  // that are provably not reactions.
  //
  // NO PAPER TRADE IS PERSISTED ANYWHERE IN S12. alexGConstructLivePosition is the pure decision
  // core: it RETURNS a position and writes to no account, journal, ledger or store. ALEX state
  // is reset before each call and nothing is ever committed.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  const T=0.0009765625;            // 2^-10 -- the exact bar range every S12 series uses
  const ATR_EXACT=T;               // therefore the engine's own 14-period ATR, exactly
  const DISP_THRESHOLD=0.25*T;     // 2^-12 -- rejectionDisplacementATRMultiplier * ATR, exactly
  const SHELF_LOW=1.09840;         // the "shelf" every low-cluster series rests on
  const SHELF_CLOSE=1.09880;       // inside every bar's range in those series, so every TR is T
  const SHELF_HIGH=1.09960;        // the mirror shelf for the high-cluster (resistance) series
  const SHELF_CLOSE_HI=1.09930;
  const H1_MS=3600000;
  const SERIES_T0=Date.UTC(2026,0,5,0,0,0); // a Monday; irrelevant to every S12 verdict, since
                                            // the zone engine has no session or day gate at all

  // A bar pinned by its LOW: range exactly T, close supplied.
  function loBar(low,close){ return{o:close,h:low+T,l:low,c:close}; }
  // A bar pinned by its HIGH: range exactly T, close supplied.
  function hiBar(high,close){ return{o:close,h:high,l:high-T,c:close}; }
  // Stamps real candle times on a bar list. barOffset lets the SAME market bar keep the SAME
  // timestamp when a rolling window drops an older candle -- which is what makes the re-run
  // fixtures a genuine simulation of live polling rather than a relabelling exercise.
  function h1(bars,barOffset){
    const off=barOffset||0;
    return bars.map(function(b,i){ return{o:b.o,h:b.h,l:b.l,c:b.c,t:new Date(SERIES_T0+(off+i)*H1_MS)}; });
  }
  function runEngine(bars){ return g.alexGRunSetupEngine('EUR_USD',{H1:bars,H4:[],D:[],W:[]}); }
  function onlyZone(res){
    const zs=res.zones.H1.validatedZones;
    if(zs.length!==1) throw new Error('expected exactly one validated zone, got '+zs.length);
    return zs[0];
  }
  function touchSummary(z){
    return z.touches.map(function(t){ return t.barIndex+'@'+t.price+'/'+t.swingType+'/'+t.fromSide; }).join(' ');
  }

  // ── THE SUPPORT SERIES ────────────────────────────────────────────────────────────────────
  // A flat shelf at 1.09840/1.0993765625 with four dips beneath it, 8 bars apart. Three of them
  // (1.09800, 1.09810, 1.09790) are the reactions that validate a zone; the fourth is the return
  // that can qualify as a setup. fourthLow is the ONE variable the A10 pair moves.
  function supportSeries(fourthLow,n){
    const bars=[];
    const len=n||50;
    for(let i=0;i<len;i++) bars.push(loBar(SHELF_LOW,SHELF_CLOSE));
    bars[20]=loBar(1.09800,SHELF_CLOSE);
    bars[28]=loBar(1.09810,SHELF_CLOSE);
    bars[36]=loBar(1.09790,SHELF_CLOSE);
    if(fourthLow!=null) bars[44]=loBar(fourthLow,SHELF_CLOSE);
    // The qualification bar carries a DIFFERENT close from its predecessor, so "this candle's
    // close" and "the previous candle's close" are distinguishable values.
    if(len>47) bars[47]=loBar(SHELF_LOW,1.09890);
    return h1(bars);
  }

  await t('ZONE-Z1-1 the validated zone IS the three reactions -- exact edges, exact centre, exact touches',async function(){
    g.resetAlexGZoneEngine();
    const bars=supportSeries(null,44);
    const z=onlyZone(runEngine(bars));
    // PRECONDITION, from the engine's own ATR function, not from this fixture's arithmetic.
    eq(g.calcATR(bars.slice(0,37),14),ATR_EXACT,'the engine’s own 14-period ATR at the validating anchor');
    // The zone's edges are the extremes of the three reactions -- not the shelf, not the centre
    // of mass, not a widened band.
    eq(z.low,1.09790,'zone LOW is the lowest of the three reactions');
    eq(z.high,1.09810,'zone HIGH is the highest of the three reactions');
    eq(z.center,1.09800,'zone CENTRE is the midpoint of those two edges');
    eq(z.touches.length,3,'exactly three touches -- the shelf bars are not reactions');
    eq(z.zoneStrength,'valid','three touches is the "valid" tier, by name');
    eq(z.status,'validated','and it is validated, not broken');
    eq(z.quality,'clean','with no wick-only penetration recorded');
    eq(z.brokenDirection,null,'and no break direction, because it has not broken');
    eq(z.formedAtBar,37,'formed at the validating reaction’s own confirmation bar');
    // Each touch is the swing bar itself, at the swing bar's own price, approached from above.
    eq(touchSummary(z),'20@1.098/low/above 28@1.0981/low/above 36@1.0979/low/above',
      'every touch names its own bar, its own price, its own swing type and its own approach side');
    return 'zone [1.09790,1.09810] c=1.09800 touches=3 valid/validated/clean';
  });

  await t('ZONE-Z1-2 the 4th touch is admitted at EXACTLY the zone’s upper edge -- one tick higher and it is not',async function(){
    // POSITIVE: a reaction whose price sits exactly ON zone.high is inside the zone.
    g.resetAlexGZoneEngine();
    const onEdge=runEngine(supportSeries(1.09810));
    const ze=onlyZone(onEdge);
    eq(ze.high,1.09810,'PRECONDITION: the reaction price and the zone edge are the same number');
    eq(ze.touches.length,4,'a reaction exactly on the edge IS counted');
    eq(ze.touches[3].price,1.09810,'at its own price');
    eq(ze.touches[3].barIndex,44,'from its own bar');
    eq(ze.zoneStrength,'strong','four touches is the "strong" tier');
    eq(onEdge.setups.length,1,'and it produces exactly one setup');
    // NEGATIVE, ONE TICK AWAY: the same series with that fourth dip a single pip higher, so it
    // falls OUTSIDE the locked zone. The engine gives it its own cluster instead of a touch.
    g.resetAlexGZoneEngine();
    const above=runEngine(supportSeries(1.09811));
    const za=onlyZone(above);
    eq(za.touches.length,3,'one pip above the edge is not a touch of this zone');
    eq(za.zoneStrength,'valid','so the zone stays at three touches');
    eq(above.setups.length,0,'and no setup is produced at all');
    eq(above.zones.H1.provisionalClusters.length,1,'the refused reaction started its own cluster instead');
    return 'low 1.09810 (== zone.high) -> 4 touches, strong, 1 setup | low 1.09811 -> 3 touches, valid, 0 setups';
  });

  await t('ZONE-Z1-3 the setup names the exact touch, the exact close and the exact direction it was built from',async function(){
    g.resetAlexGZoneEngine();
    const res=runEngine(supportSeries(1.09810));
    eq(res.setups.length,1,'PRECONDITION: exactly one setup');
    const s=res.setups[0];
    eq(s.setupType,'A_repeatedReaction','a 4th reaction into an unbroken zone is a repeated reaction');
    eq(s.setupLabel,'REPEATED ZONE REACTION','under its user-facing label');
    eq(s.zoneTouchNumber,4,'it is the FOURTH touch, counted from the zone’s own tally');
    eq(s.reactionSwingType,'low','built from a swing LOW');
    eq(s.reactionFromSide,'above','approached from above the zone');
    eq(s.reactionPrice,1.09810,'at the reaction’s own price');
    eq(s.zoneLow,1.09790,'carrying the zone’s own low');
    eq(s.zoneHigh,1.09810,'and its own high');
    eq(s.zoneCenter,1.09800,'and its own centre');
    eq(s.zoneStrength,'strong','and the strength tier as of qualification');
    eq(s.zoneQualityAtQualification,'clean','and the corrected quality as of qualification');
    eq(s.zoneStatusAtQualification,'validated','from a zone that is still validated');
    eq(s.zoneRoleAtQualification,'support','acting as SUPPORT, because price has been above it');
    eq(s.brokenDirection,null,'with no break direction, since it never broke');
    eq(g.alexGDetermineTradeDirection(s).direction,'buy','so the frozen direction function makes it a BUY');
    return 'A_repeatedReaction touch#4 @1.09810 zone[1.09790,1.09810] role=support -> buy';
  });

  await t('ZONE-Z1-4 qualificationClose is THIS candle’s close, not the previous candle’s',async function(){
    g.resetAlexGZoneEngine();
    const bars=supportSeries(1.09810);
    const s=runEngine(bars)[ 'setups' ][0];
    eq(s.qualificationBarIndex,47,'the setup qualified on bar 47');
    // The two candidate values are DIFFERENT numbers, which is the only thing that makes this
    // assertion capable of failing.
    ok(bars[47].c!==bars[46].c,'PRECONDITION: bar 47 and bar 46 close at different prices ('+bars[47].c+' vs '+bars[46].c+')');
    eq(s.qualificationClose,bars[47].c,'qualificationClose is bar 47’s own close');
    eq(s.qualificationClose,1.09890,'which is 1.09890');
    eq(s.qualificationTimestamp,new Date(SERIES_T0+48*H1_MS).getTime(),'stamped at bar 47’s own close time');
    return 'qualificationBarIndex=47 close=1.09890 (bar 46 closed 1.09880)';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // Z2 — THE REACTION-DISPLACEMENT THRESHOLD, ORGANICALLY
  // The third reaction's confirmation candle is placed at 0.24x, 0.25x and 0.26x the engine's
  // OWN ATR above the anchor. Only its high moves between the three series.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  function displacementSeries(multiple){
    const bars=[];
    for(let i=0;i<46;i++) bars.push(loBar(SHELF_LOW,SHELF_CLOSE));
    bars[20]=loBar(1.09800,SHELF_CLOSE);
    bars[28]=loBar(1.09810,SHELF_CLOSE);
    bars[36]=loBar(1.09790,SHELF_CLOSE);
    // The single confirmation candle of the third reaction. Its LOW stays above the anchor's
    // (so the anchor is still a swing low); only its HIGH -- the displacement -- moves.
    bars[37]={o:1.09800,h:1.09790+multiple*ATR_EXACT,l:1.09791,c:1.09800};
    return h1(bars);
  }

  await t('ZONE-Z2-0 PRECONDITION: the 0.25x series really does sit EXACTLY on the threshold',async function(){
    // A boundary fixture that is only NEAR the boundary cannot kill a >= -> > flip, so the
    // identity is re-proved at run time rather than assumed. These are the fixture's own inputs
    // being checked, not the engine's verdict -- the verdict is asserted in ZONE-Z2-1.
    const bars=displacementSeries(0.25);
    const atr=g.calcATR(bars.slice(0,37),14);
    eq(atr,ATR_EXACT,'the engine’s own ATR at the third anchor is exactly 2^-10');
    eq(g.ALEXG_CONFIG().rejectionDisplacementATRMultiplier,0.25,'and the frozen multiplier is 0.25');
    const displacement=bars[37].h-bars[36].l;
    eq(displacement,0.25*atr,'so the constructed displacement is EXACTLY 0.25 * ATR, bit for bit');
    eq(displacement,DISP_THRESHOLD,'= 2^-12 = 0.000244140625');
    ok(displacementSeries(0.24)[37].h-bars[36].l<displacement,'the 0.24x series sits strictly below it');
    ok(displacementSeries(0.26)[37].h-bars[36].l>displacement,'and the 0.26x series strictly above');
    return 'ATR=2^-10 exactly; displacement at 0.25x = 2^-12 exactly';
  });

  await t('ZONE-Z2-1 a reaction displacing 0.25x ATR qualifies; 0.24x does not -- and nothing else changed',async function(){
    const seen={};
    [0.24,0.25,0.26].forEach(function(m){
      g.resetAlexGZoneEngine();
      const res=runEngine(displacementSeries(m));
      seen[m]={zones:res.zones.H1.validatedZones.length,
               clusters:res.zones.H1.provisionalClusters.map(function(c){return c.reactions.length;}).join(',')};
    });
    // NEGATIVE half: below the threshold the third reaction is silently not counted.
    eq(seen[0.24].zones,0,'0.24x ATR: NO zone is validated');
    eq(seen[0.24].clusters,'2','and the cluster is left holding exactly TWO accepted reactions');
    // POSITIVE half, one input away: the same series with only that candle's high raised to the
    // threshold. Two reactions already qualified, so the negative half is provably a rejection
    // of the third reaction and not a series that could never have produced anything.
    eq(seen[0.25].zones,1,'0.25x ATR -- exactly AT the threshold: the zone IS validated');
    eq(seen[0.25].clusters,'','with no cluster left over');
    eq(seen[0.26].zones,1,'0.26x ATR: likewise validated');
    return '0.24x -> 0 zones (cluster stuck at 2 reactions) | 0.25x -> 1 zone | 0.26x -> 1 zone';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // Z3 — BREAK CONFIRMATION, AND THE SAME-INTERACTION RULE
  // ══════════════════════════════════════════════════════════════════════════════════════════

  // The support zone from Z1, then three candles closing INSIDE it (so the zone never gets a
  // role from them), then bar 42 -- the one variable. Bar 42 always wicks below the zone; only
  // its CLOSE decides whether that is a confirmed break or a wick.
  function breakConfirmSeries(closeBeyond){
    const bars=[];
    for(let i=0;i<48;i++) bars.push(loBar(SHELF_LOW,SHELF_CLOSE));
    bars[20]=loBar(1.09800,SHELF_CLOSE);
    bars[28]=loBar(1.09810,SHELF_CLOSE);
    bars[36]=loBar(1.09790,SHELF_CLOSE);
    for(let i=39;i<48;i++) bars[i]=loBar(1.09795,1.09800); // closes inside [1.09790,1.09810]
    bars[42]={o:1.09750,h:1.09700+T,l:1.09700,c:closeBeyond?1.09750:1.09800};
    return h1(bars);
  }

  await t('ZONE-Z3-1 ONE close beyond a support zone breaks it; ZERO closes leaves it validated',async function(){
    // POSITIVE: exactly one candle closes below the zone.
    g.resetAlexGZoneEngine();
    const broke=onlyZone(runEngine(breakConfirmSeries(true)));
    eq(g.ALEXG_CONFIG().breakConfirmationCloses,1,'PRECONDITION: the frozen requirement is 1 close');
    eq(broke.status,'broken','one confirming close breaks the zone');
    eq(broke.brokenAtBar,42,'on that candle, not a later one');
    eq(broke.brokenAt,new Date(SERIES_T0+43*H1_MS).getTime(),'stamped at that candle’s own close time');
    eq(broke.brokenDirection,'downThroughSupport','downward, through support');
    eq(broke.consecutiveBreakCloses,1,'after exactly one consecutive breaking close');
    eq(broke.penetrationEvents.length,0,'a confirmed break is not recorded as a wick penetration');
    // NEGATIVE, ONE NUMBER AWAY: the same candle, same low, same wick -- it just closes back
    // inside the zone instead of below it.
    g.resetAlexGZoneEngine();
    const held=onlyZone(runEngine(breakConfirmSeries(false)));
    eq(held.status,'validated','with zero closes beyond it the zone is NOT broken');
    eq(held.brokenAtBar,null,'no break bar');
    eq(held.brokenDirection,null,'no break direction');
    eq(held.penetrationEvents.length,1,'the same wick is recorded as a penetration instead');
    eq(held.penetrationEvents[0].startBarIndex,42,'on the same bar 42');
    return 'close 1.09750 -> broken@42 downThroughSupport | close 1.09800 -> validated, 1 penetration@42';
  });

  // ── THE RE-RUN SERIES ─────────────────────────────────────────────────────────────────────
  // alexGRunSetupEngine is re-run over a rolling window on EVERY live poll, and alexGZoneState
  // persists between those runs -- so the same market interaction is re-offered to the engine
  // over and over, at a bar index that SHIFTS by one every time a new candle closes. The
  // same-interaction rule is what stops one reaction becoming many touches. These two fixtures
  // deliberately do NOT reset the engine between runs, because not resetting is the real
  // behaviour under test.
  //
  // (The audit's literal recipe -- "two swing lows 3 bars apart" -- is not constructible: with
  // the engine's lookback of 3, a swing low at bar j REQUIRES candles[j+1..j+3].l > candles[j].l,
  // while a swing low at bar j+3 requires the opposite. Two same-type swings can never be within
  // the lookback of each other inside ONE candle array, so the rule is only reachable across
  // runs. That is what these fixtures exercise.)
  function reRunBars(len){
    const bars=[];
    for(let i=0;i<len;i++) bars.push(loBar(SHELF_LOW,SHELF_CLOSE));
    bars[20]=loBar(1.09800,SHELF_CLOSE);
    bars[28]=loBar(1.09810,SHELF_CLOSE);
    bars[36]=loBar(1.09790,SHELF_CLOSE);
    bars[44]=loBar(1.09810,SHELF_CLOSE);
    if(len>56) bars[52]=loBar(1.09805,SHELF_CLOSE); // a genuinely NEW, later interaction
    return bars;
  }
  function liveZone(){ return g.alexGZoneStateFor('EUR_USD','H1').validatedZones[0]; }

  await t('ZONE-Z3-2 re-running the engine over the SAME window does not re-count the same reactions',async function(){
    g.resetAlexGZoneEngine();
    runEngine(h1(reRunBars(50)));
    eq(liveZone().touches.length,4,'PRECONDITION: the first run counts four touches');
    // Poll again with no new candle -- exactly what happens between bar closes.
    runEngine(h1(reRunBars(50)));
    eq(liveZone().touches.length,4,'a second pass over the same candles still counts FOUR touches');
    eq(liveZone().touches.map(function(x){return x.barIndex;}).join(','),'20,28,36,44','the same four bars');
    eq(g.alexGSetupStateAll().length,1,'and still exactly one setup record');
    // POSITIVE CONTROL, in the same fixture: the third pass sees a window extended by eight
    // candles containing a genuinely NEW interaction. It IS admitted -- so the two assertions
    // above are the dedup rule working, not the engine having stopped looking.
    runEngine(h1(reRunBars(58)));
    eq(liveZone().touches.length,5,'a genuinely new reaction on the extended window IS admitted');
    eq(liveZone().touches[4].barIndex,52,'at its own bar');
    eq(g.alexGSetupStateAll().length,2,'producing a second setup record');
    return 'run1=4 touches, re-run=4, extended run=5 (new touch@52)';
  });

  await t('ZONE-Z3-3 a reaction re-offered at a SHIFTED bar index is still one interaction, not two',async function(){
    g.resetAlexGZoneEngine();
    runEngine(h1(reRunBars(50)));
    eq(liveZone().touches.map(function(x){return x.barIndex;}).join(','),'20,28,36,44',
      'PRECONDITION: four touches at bars 20/28/36/44');
    // The rolling window drops its oldest candle and gains newer ones. Every surviving bar keeps
    // its own market timestamp, but its INDEX is now one lower -- so the four already-counted
    // interactions come back as anchors at bars 19/27/35/43.
    const shifted=h1(reRunBars(58).slice(1),1);
    runEngine(shifted);
    eq(liveZone().touches.length,5,'the four shifted repeats are still four touches, not eight');
    eq(liveZone().touches.map(function(x){return x.barIndex;}).join(','),'20,28,36,44,51',
      'the original four keep their original bars, and only the new interaction is added');
    // POSITIVE CONTROL, same window, same run: the interaction eight bars past the last touch is
    // NOT the same interaction and IS admitted -- so the four above were refused by the
    // same-interaction rule, not by the engine refusing everything on a second pass.
    eq(liveZone().touches[4].price,1.09805,'at the new interaction’s own price');
    eq(liveZone().zoneStrength,'strong','and the zone tally moved by exactly one');
    return 'shifted re-run: anchors at 19/27/35/43 deduped; the new one at 51 admitted -> 5 touches';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // Z4 — THE CHOPPY BOUNDARY
  // Each "episode" is a PAIR of adjacent bars sharing one low beneath the zone and closing back
  // above it. Sharing a low is what makes them provably not reactions (the engine's swing test
  // is strict), and adjacency is what makes the pair ONE penetration episode. A shelf bar
  // between episodes ends the episode. Only the NUMBER of episodes changes between the two runs.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  function choppySeries(episodes){
    const bars=[];
    for(let i=0;i<58;i++) bars.push(loBar(SHELF_LOW,SHELF_CLOSE));
    bars[20]=loBar(1.09800,SHELF_CLOSE);
    bars[28]=loBar(1.09810,SHELF_CLOSE);
    bars[36]=loBar(1.09790,SHELF_CLOSE);
    [40,43,46].slice(0,episodes).forEach(function(start){
      bars[start]=loBar(1.09750,1.09820);   // wicks below zone.low, closes back above zone.high
      bars[start+1]=loBar(1.09750,1.09820); // shares the low, so neither bar is a swing
    });
    bars[52]=loBar(1.09810,SHELF_CLOSE);    // the 4th reaction, well clear of every wick bar
    return h1(bars);
  }

  await t('ZONE-Z4-1 two wick-only penetrations leave a zone CLEAN; the third makes it CHOPPY',async function(){
    eq(g.ALEXG_CONFIG().maxPenetrationsBeforeChoppyFlag,3,'PRECONDITION: the frozen threshold is 3');
    eq(g.ALEXG_CONFIG().choppyLookbackBars,50,'inside a 50-bar lookback');
    g.resetAlexGZoneEngine();
    const two=onlyZone(runEngine(choppySeries(2)));
    eq(two.penetrationEvents.map(function(p){return p.startBarIndex;}).join(','),'40,43',
      'two episodes are recorded, one per pair, at the bar each began');
    eq(two.quality,'clean','two is below the threshold: CLEAN');
    // ONE EPISODE AWAY: the identical series with a third pair.
    g.resetAlexGZoneEngine();
    const three=onlyZone(runEngine(choppySeries(3)));
    eq(three.penetrationEvents.map(function(p){return p.startBarIndex;}).join(','),'40,43,46',
      'three episodes, still one per pair -- an adjacent repeat is not a second episode');
    eq(three.quality,'choppy','three is AT the threshold: CHOPPY');
    eq(three.status,'validated','and it is a quality flag, not a break -- the zone is still validated');
    eq(three.low,1.09790,'with its boundaries untouched');
    eq(three.high,1.09810,'on both edges');
    return '2 episodes [40,43] -> clean | 3 episodes [40,43,46] -> choppy';
  });

  await t('ZONE-Z4-2 a choppy zone is REFUSED a repeated-reaction setup -- and the clean one gets it',async function(){
    // POSITIVE CONTROL: two episodes, so the same 4th reaction on the same zone qualifies.
    g.resetAlexGZoneEngine();
    const clean=runEngine(choppySeries(2));
    eq(onlyZone(clean).touches.length,4,'PRECONDITION: a genuine 4th touch was accepted');
    eq(clean.setups.length,1,'a clean zone’s 4th reaction IS a setup');
    eq(clean.setups[0].setupType,'A_repeatedReaction','a repeated zone reaction');
    eq(clean.setups[0].zoneQualityAtQualification,'clean','recorded as clean');
    eq(onlyZone(clean).touches[3].setupEligibility,'A_repeatedReaction','and the touch is marked eligible');
    // NEGATIVE, ONE EPISODE AWAY: the identical 4th reaction on the identical zone, refused.
    g.resetAlexGZoneEngine();
    const choppy=runEngine(choppySeries(3));
    eq(onlyZone(choppy).touches.length,4,'the SAME 4th touch is still accepted as a touch');
    eq(choppy.setups.length,0,'but the choppy zone produces NO setup');
    eq(onlyZone(choppy).touches[3].setupEligibility,null,'and the touch is explicitly marked ineligible');
    return '2 episodes -> 1 A_repeatedReaction setup | 3 episodes -> same 4th touch, 0 setups';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // Z5 — BREAK DIRECTION
  // The highest-severity gap the audit found: brokenDirection drives alexGDetermineTradeDirection
  // for every break-and-retest, so inverting it buys where the strategy should sell. These two
  // series are mirror images -- a support zone broken DOWNWARD and retested from below, and a
  // resistance zone broken UPWARD and retested from above -- and each asserts the direction the
  // frozen engine actually produced, all the way through to a constructed (never persisted) trade.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  // Support zone [1.09790,1.09810]; three candles close inside it (so the zone's role is never
  // written by them and must be INFERRED backwards when the break arrives); bar 42 closes below;
  // bar 50 rallies back into the zone as a swing HIGH -- the retest, from below.
  function breakDownRetestSeries(){
    const bars=[];
    for(let i=0;i<54;i++) bars.push(loBar(SHELF_LOW,SHELF_CLOSE));
    bars[20]=loBar(1.09800,SHELF_CLOSE);
    bars[28]=loBar(1.09810,SHELF_CLOSE);
    bars[36]=loBar(1.09790,SHELF_CLOSE);
    bars[39]=loBar(1.09795,1.09800); bars[40]=loBar(1.09795,1.09800); bars[41]=loBar(1.09795,1.09800);
    for(let i=42;i<54;i++) bars[i]=loBar(1.09700,1.09750); // below the zone, closing below it
    bars[50]={o:1.09750,h:1.09805,l:1.09805-T,c:1.09750};  // the retest: a swing HIGH into the zone
    return h1(bars);
  }
  // The mirror. Resistance zone [1.09990,1.10010] built from three swing HIGHS with price below
  // it throughout; bar 42 closes above; bar 50 dips back into the zone as a swing LOW -- the
  // retest, from above.
  function breakUpRetestSeries(){
    const bars=[];
    for(let i=0;i<54;i++) bars.push(hiBar(SHELF_HIGH,SHELF_CLOSE_HI));
    bars[20]=hiBar(1.10000,SHELF_CLOSE_HI);
    bars[28]=hiBar(1.10010,SHELF_CLOSE_HI);
    bars[36]=hiBar(1.09990,SHELF_CLOSE_HI);
    for(let i=42;i<54;i++) bars[i]=hiBar(1.10100,1.10050); // above the zone, closing above it
    bars[50]={o:1.10050,h:1.10000+T,l:1.10000,c:1.10050};  // the retest: a swing LOW into the zone
    return h1(bars);
  }
  // Constructs (and never persists) the live position the frozen gate would actually open, with
  // the fill placed at the setup's own qualification close so no entry-delay or R:R gate is what
  // is being measured. alexGConstructLivePosition writes to no account, journal or ledger.
  function constructFromSetup(setup,bars){
    g.resetAlexG();
    const q=setup.qualificationClose;
    return g.alexGConstructLivePosition(setup,{H1:bars},{bid:q,ask:q},g.ALEXG_CONFIG(),10000,{});
  }

  await t('ZONE-Z5-1 a support zone broken DOWNWARD is retested from below and the trade is a SELL',async function(){
    g.resetAlexGZoneEngine();
    const bars=breakDownRetestSeries();
    const res=runEngine(bars);
    const z=onlyZone(res);
    eq(z.low,1.09790,'PRECONDITION: the zone is the same [1.09790,1.09810] support zone');
    eq(z.high,1.09810,'on both edges');
    eq(z.status,'broken','it broke');
    eq(z.brokenAtBar,42,'on bar 42');
    eq(z.brokenDirection,'downThroughSupport','DOWNWARD, through support');
    eq(res.setups.length,1,'and exactly one setup followed');
    const s=res.setups[0];
    eq(s.setupType,'B_breakRetest','a break and retest');
    eq(s.setupLabel,'BREAK & RETEST','under its user-facing label');
    eq(s.reactionSwingType,'high','the retest is a swing HIGH');
    eq(s.reactionFromSide,'below','approached from BELOW the broken zone');
    eq(s.reactionPrice,1.09805,'at its own price, back inside the old zone');
    eq(s.zoneTouchNumber,4,'as the zone’s fourth touch');
    eq(s.brokenDirection,'downThroughSupport','carrying the break direction onto the setup record');
    eq(s.barsSinceBreak,11,'eleven bars after the break');
    eq(g.alexGDetermineTradeDirection(s).direction,'sell','so the frozen direction function makes it a SELL');
    const pos=constructFromSetup(s,bars);
    eq(pos.status,'TRADE OPENED','and the frozen live gate constructs it: '+pos.status+' / '+pos.reason);
    eq(pos.direction,'sell','as a SELL');
    ok(pos.position.stop>pos.position.entry,'with the stop ABOVE entry, as a sell must have');
    ok(pos.position.target<pos.position.entry,'and the target below it');
    return 'broken@42 downThroughSupport -> retest high/below @1.09805 -> SELL (stop '+pos.position.stop.toFixed(5)+' > entry '+pos.position.entry.toFixed(5)+')';
  });

  await t('ZONE-Z5-2 the MIRROR: a resistance zone broken UPWARD is retested from above and the trade is a BUY',async function(){
    g.resetAlexGZoneEngine();
    const bars=breakUpRetestSeries();
    const res=runEngine(bars);
    const z=onlyZone(res);
    eq(z.low,1.09990,'PRECONDITION: a resistance zone at [1.09990,1.10010]');
    eq(z.high,1.10010,'on both edges');
    eq(z.touches[0].swingType,'high','built from swing HIGHS');
    eq(z.touches[0].fromSide,'below','approached from below throughout');
    eq(z.status,'broken','it broke');
    eq(z.brokenAtBar,42,'on bar 42');
    eq(z.brokenDirection,'upThroughResistance','UPWARD, through resistance');
    eq(res.setups.length,1,'and exactly one setup followed');
    const s=res.setups[0];
    eq(s.setupType,'B_breakRetest','a break and retest');
    eq(s.reactionSwingType,'low','the retest is a swing LOW');
    eq(s.reactionFromSide,'above','approached from ABOVE the broken zone');
    eq(s.reactionPrice,1.10000,'at its own price, back inside the old zone');
    eq(s.brokenDirection,'upThroughResistance','carrying the break direction onto the setup record');
    eq(g.alexGDetermineTradeDirection(s).direction,'buy','so the frozen direction function makes it a BUY');
    const pos=constructFromSetup(s,bars);
    eq(pos.status,'TRADE OPENED','and the frozen live gate constructs it: '+pos.status+' / '+pos.reason);
    eq(pos.direction,'buy','as a BUY');
    ok(pos.position.stop<pos.position.entry,'with the stop BELOW entry, as a buy must have');
    ok(pos.position.target>pos.position.entry,'and the target above it');
    return 'broken@42 upThroughResistance -> retest low/above @1.10000 -> BUY (stop '+pos.position.stop.toFixed(5)+' < entry '+pos.position.entry.toFixed(5)+')';
  });

  await t('ZONE-Z5-3 the two breaks never agree: each direction follows its OWN break, and they are opposite',async function(){
    g.resetAlexGZoneEngine();
    const down=runEngine(breakDownRetestSeries());
    g.resetAlexGZoneEngine();
    const up=runEngine(breakUpRetestSeries());
    eq(down.setups.length,1,'PRECONDITION: both series produced a setup');
    eq(up.setups.length,1,'both');
    const dDir=g.alexGDetermineTradeDirection(down.setups[0]).direction;
    const uDir=g.alexGDetermineTradeDirection(up.setups[0]).direction;
    eq(dDir,'sell','the downward break sells');
    eq(uDir,'buy','the upward break buys');
    ok(dDir!==uDir,'and the two are opposite -- neither is a constant');
    eq(down.setups[0].brokenDirection,'downThroughSupport','each carrying its own break direction');
    eq(up.setups[0].brokenDirection,'upThroughResistance','on its own record');
    // The retest geometry is likewise mirrored, so a single swapped field cannot satisfy both.
    eq(down.setups[0].reactionSwingType+'/'+down.setups[0].reactionFromSide,'high/below','down: high from below');
    eq(up.setups[0].reactionSwingType+'/'+up.setups[0].reactionFromSide,'low/above','up: low from above');
    return 'downThroughSupport -> sell (high/below) | upThroughResistance -> buy (low/above)';
  });

  await t('ZONE-Z5-4 a zone whose role was never written is still classified from its OWN history',async function(){
    // The three candles before the break close INSIDE the zone, so lastKnownRole is still null
    // when bar 42 arrives -- the engine must infer the prior role by looking strictly backward.
    // If it cannot, the break is not classified at all and the zone silently never breaks.
    g.resetAlexGZoneEngine();
    const partial=breakConfirmSeries(false); // identical series, wick only, no confirming close
    const held=onlyZone(runEngine(partial));
    eq(held.lastKnownRole,null,'PRECONDITION: no candle ever closed outside the zone after it formed');
    eq(held.penetrationEvents.length,1,'yet the wick beneath it IS still classified -- as a support-side penetration');
    eq(held.penetrationEvents[0].startBarIndex,42,'on bar 42');
    // POSITIVE half, one number away: the same bar closing below instead of inside.
    g.resetAlexGZoneEngine();
    const broke=onlyZone(runEngine(breakConfirmSeries(true)));
    eq(broke.brokenDirection,'downThroughSupport','and the same inference classifies the confirmed break as downward');
    eq(broke.brokenAtBar,42,'on the same bar 42');
    return 'role never written; wick@42 still classified support-side; the confirming close breaks downThroughSupport';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // Z6 — alexGCheckSwingAt / alexGAssignCluster UNIT BOUNDARIES
  // These two functions are the engine's entire input surface: everything above depends on them
  // reporting swings at all, at the right edges, and never merging a high cluster with a low one.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  // 14 flat bars with one bar's high raised and one bar's low dropped.
  function swingAtSeries(){
    const bars=[];
    for(let i=0;i<14;i++) bars.push(loBar(1.09840,SHELF_CLOSE));
    bars[6]={o:SHELF_CLOSE,h:1.10000,l:1.09840,c:SHELF_CLOSE};  // a lone higher high
    bars[10]=loBar(1.09700,SHELF_CLOSE);                        // a lone lower low
    return bars;
  }

  await t('ZONE-Z6-1 alexGCheckSwingAt reports a swing HIGH at all -- with a swing LOW as its control',async function(){
    const bars=swingAtSeries();
    eq(g.alexGCheckSwingAt(bars,6,3),'high','the lone higher high IS reported as a swing high');
    eq(g.alexGCheckSwingAt(bars,10,3),'low','and the lone lower low as a swing low');
    // The two answers are different words for different bars, so neither can be standing in for
    // the other, and an ordinary bar is neither.
    eq(g.alexGCheckSwingAt(bars,8,3),null,'an ordinary bar between them is neither');
    return 'bar 6 -> high | bar 8 -> null | bar 10 -> low';
  });

  await t('ZONE-Z6-2 the lookback-edge guard sits exactly at centerIdx-lookback<0, not one bar later',async function(){
    // A dip at exactly index 3 has exactly `lookback` candles on its left -- the earliest bar
    // that can be evaluated at all. It must be evaluated.
    const bars=[];
    for(let i=0;i<10;i++) bars.push(loBar(1.09840,SHELF_CLOSE));
    bars[3]=loBar(1.09700,SHELF_CLOSE);
    eq(g.alexGCheckSwingAt(bars,3,3),'low','a swing at exactly index==lookback IS evaluated and reported');
    // NEGATIVE, one bar away: index 2 genuinely has too little history on its left.
    const shifted=[];
    for(let i=0;i<10;i++) shifted.push(loBar(1.09840,SHELF_CLOSE));
    shifted[2]=loBar(1.09700,SHELF_CLOSE);
    eq(g.alexGCheckSwingAt(shifted,2,3),null,'the identical dip one bar earlier is refused for want of history');
    // ...and the same guard at the right-hand edge, for the same reason.
    const tail=[];
    for(let i=0;i<10;i++) tail.push(loBar(1.09840,SHELF_CLOSE));
    tail[6]=loBar(1.09700,SHELF_CLOSE);
    eq(g.alexGCheckSwingAt(tail,6,3),'low','index 6 of a 10-bar array has exactly 3 candles to its right, and IS evaluated');
    eq(g.alexGCheckSwingAt(tail,7,3),null,'index 7 does not, and is refused');
    return 'idx 2 -> null | idx 3 -> low | idx 6 -> low | idx 7 -> null';
  });

  await t('ZONE-Z6-3 cluster grouping is INCLUSIVE at exactly the tolerance, exclusive one tick past it',async function(){
    const center=1.09800, tol=DISP_THRESHOLD; // 2^-12: an exact binary fraction, so the boundary is exact
    const cluster={id:'AGC|fixture',swingType:'low',center:center,createdAtCloseTimeMs:1};
    const atEdge=center+tol;
    eq(Math.abs(atEdge-center),tol,'PRECONDITION: the candidate price is EXACTLY one tolerance away, bit for bit');
    eq(g.alexGAssignCluster([cluster],'low',atEdge,tol),cluster,'a price exactly at the tolerance IS assigned');
    // NEGATIVE, one representable tick away (2^-52 at this magnitude).
    const past=atEdge+Math.pow(2,-52);
    ok(Math.abs(past-center)>tol,'PRECONDITION: one tick further is strictly beyond the tolerance');
    eq(g.alexGAssignCluster([cluster],'low',past,tol),null,'and it is refused');
    return 'centre+tolerance -> assigned; centre+tolerance+1ulp -> null';
  });

  await t('ZONE-Z6-4 a swing HIGH is never assigned to a swing-LOW cluster, however close the price',async function(){
    const center=1.09800, tol=DISP_THRESHOLD;
    const lowCluster={id:'AGC|low',swingType:'low',center:center,createdAtCloseTimeMs:1};
    // POSITIVE CONTROL: the identical price, identical cluster, identical tolerance -- matching type.
    eq(g.alexGAssignCluster([lowCluster],'low',center,tol),lowCluster,'a swing low at the exact centre IS assigned');
    // NEGATIVE, ONE VARIABLE AWAY: only the swing type differs.
    eq(g.alexGAssignCluster([lowCluster],'high',center,tol),null,'a swing HIGH at the exact same price is NOT');
    // and symmetrically.
    const highCluster={id:'AGC|high',swingType:'high',center:center,createdAtCloseTimeMs:1};
    eq(g.alexGAssignCluster([highCluster],'high',center,tol),highCluster,'a swing high joins a high cluster');
    eq(g.alexGAssignCluster([highCluster],'low',center,tol),null,'and a swing low does not');
    // With BOTH clusters present at the same centre, each type still picks its own.
    eq(g.alexGAssignCluster([lowCluster,highCluster],'high',center,tol),highCluster,'with both offered, a high picks the high cluster');
    eq(g.alexGAssignCluster([lowCluster,highCluster],'low',center,tol),lowCluster,'and a low picks the low cluster');
    return 'same price, same tolerance: type match -> assigned, type mismatch -> null, both ways';
  });

  await t('ZONE-Z6-5 alexGFindSwingPoints -- the array-wide twin -- is strict on both sides and reports highs',async function(){
    // The parallel copy of findSwingPoints used by the ALEX trend-context pass. It has never had
    // a fixture of its own, so it could diverge from its twin silently.
    function twinSeries(neighbourHigh,neighbourLow){
      const bars=[];
      for(let i=0;i<20;i++) bars.push(bar(1.09880,1.09960,1.09840,1.09880));
      bars[9]=bar(1.09880,neighbourHigh,1.09840,1.09880);
      bars[10]=bar(1.09880,1.10000,1.09840,1.09880); // the candidate high
      bars[14]=bar(1.09880,1.09960,neighbourLow,1.09880);
      bars[15]=bar(1.09880,1.09960,1.09700,1.09880); // the candidate low
      return bars;
    }
    const clear=g.alexGFindSwingPoints(twinSeries(1.09960,1.09840),3);
    eq(clear.swingHighs.length,1,'a lone higher high IS reported');
    eq(clear.swingHighs[0].price,1.10000,'at its own price');
    eq(clear.swingHighs[0].barIndex,10,'and its own bar');
    eq(clear.swingLows.length,1,'and a lone lower low likewise');
    eq(clear.swingLows[0].price,1.09700,'at its own price');
    eq(clear.swingLows[0].barIndex,15,'and its own bar');
    // NEGATIVE, one variable each: a neighbour that EQUALS the candidate disqualifies it -- the
    // rule is strict, not "greater than or equal".
    eq(g.alexGFindSwingPoints(twinSeries(1.10000,1.09840),3).swingHighs.length,0,'an equal-high neighbour disqualifies the high');
    eq(g.alexGFindSwingPoints(twinSeries(1.09960,1.09700),3).swingLows.length,0,'an equal-low neighbour disqualifies the low');
    // ...and each negative leaves the OTHER side intact, so neither is silence for the wrong reason.
    eq(g.alexGFindSwingPoints(twinSeries(1.10000,1.09840),3).swingLows.length,1,'while the low is still found');
    eq(g.alexGFindSwingPoints(twinSeries(1.09960,1.09700),3).swingHighs.length,1,'and the high still found');
    return 'clear -> 1 high@1.10000/bar10 + 1 low@1.09700/bar15; equal neighbour -> that side drops to 0, the other unchanged';
  });

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // S13 — THE OTHER TWO COPIES OF THE COUNTER-TREND RULE
  //
  // RULES.entry: "Never enter against confirmed top-down bias -- no counter-trend trades."
  // The predicate that enforces it, `s.type==='engulf' && s.dir===dir && s.biasMatch`, is
  // written out THREE times in index.html. S1 above covers the live one, inside
  // evaluateLiveTrigger. The other two -- inside evaluateSetupFullBreakdownCore (which is what
  // Manual Review and the setup-breakdown UI show a human) and inside simulateTrueMTFReplay
  // (which is what every historical research result is computed from, in TWO places: the main
  // gate and the Thursday/Friday diagnostic capture) -- had no control at all. Deleting
  // `&&s.biasMatch` from any of them left all 1,534 fixtures green, so the three copies could
  // drift apart silently and the research path could start counting trades the live path would
  // never take.
  //
  // Every fixture below holds the top-down bias FIXED and unmistakably Bearish, and moves only
  // the direction of the M15 trigger. That is the one-variable pairing: identical bias,
  // identical structural AOI, identical thresholds -- a with-trend trigger that is accepted, and
  // a counter-trend trigger that is refused, differing only in which way the candles point.
  //
  // NO TRADE IS PERSISTED. simulateTrueMTFReplay is a pure historical simulator: it RETURNS
  // {trades,diag} and writes to no account, journal, ledger or store.
  // ══════════════════════════════════════════════════════════════════════════════════════════

  const S13_MON=new Date('2026-06-08T13:00:00Z'); // a real Monday, inside the London/NY overlap

  function breakdownInput(bias){
    const candles=reversalM15(); // the SAME bullish reversal the S1 fixtures use
    return{
      oPair:'EUR_USD',candles:candles,decisionCandle:candles[candles.length-1],
      decisionTs:Date.parse(S13_MON),
      weeklyBias:bias,dailyBias:bias,h4Bias:bias,
      // A structural AOI wide enough that the R:R gate is not what decides anything here.
      structSupport:1.09950,structResistance:1.10500,
      structSupportSrc:'Daily',structResistanceSrc:'Daily',
      sessionAt:S13_MON,weekdayDate:S13_MON
    };
  }
  function gateOf(b,id){ return b.gates.filter(function(x){return x.id===id;})[0]; }

  await t('CTREND-BREAKDOWN-1 the setup breakdown REFUSES a counter-trend engulf -- and accepts the identical one with bias aligned',async function(){
    // POSITIVE CONTROL: bias aligned with the trigger. Every hard gate passes.
    const aligned=g.evaluateSetupFullBreakdownCore(breakdownInput('Bullish'));
    eq(aligned.direction,'buy','PRECONDITION: the breakdown reads the series as a buy');
    eq(aligned.overallBias,'Bullish','with a Bullish top-down bias');
    eq(gateOf(aligned,'confirmation').pass,true,'the directional-confirmation gate PASSES');
    eq(gateOf(aligned,'confirmation').observed,'Bullish engulf (1)','naming the engulf it accepted');
    eq(aligned.failedGates.length,0,'and nothing else fails either: '+JSON.stringify(aligned.failedGates.map(function(x){return x.id;})));
    // NEGATIVE, ONE VARIABLE AWAY: the same candles, the same AOI, the same clock -- the top-down
    // bias table is flipped and nothing else.
    const against=g.evaluateSetupFullBreakdownCore(breakdownInput('Bearish'));
    eq(against.direction,'buy','the SAME series is still read as a buy -- the read is not what changed');
    eq(against.overallBias,'Bearish','against a Bearish top-down bias');
    eq(against.score,aligned.score,'with the same 3/3 alignment score, so the strength of the bias is unchanged');
    eq(gateOf(against,'confirmation').pass,false,'now the directional-confirmation gate REFUSES it');
    eq(gateOf(against,'confirmation').observed,'no qualifying engulf','because no engulf matching bias exists');
    // The refusal is the BIAS rule, not a low score or a missing pattern: the confluence gate
    // still passes on its own merits, and the engulf is still present in the signal list.
    eq(gateOf(against,'min_confluence').pass,true,'the confluence gate still passes ('+against.confluence+'%)');
    ok(against.confluence>=g.ALERT_THRESHOLD(),'at or above the frozen threshold');
    ok(against.signals.some(function(s){return s.type==='engulf'&&s.dir==='buy';}),
      'and the bullish engulf is STILL detected -- it is only refused as a trigger');
    eq(against.signals.filter(function(s){return s.type==='engulf'&&s.dir==='buy';})[0].biasMatch,false,
      'marked as not matching bias');
    eq(against.failedGates.map(function(x){return x.id;}).join(','),'confirmation',
      'and confirmation is the ONLY gate that fails -- the block is provably the counter-trend rule');
    return 'Bullish table -> confirmation PASS, 0 failed gates | Bearish table -> confirmation FAIL, and it is the only failure (confluence '+against.confluence+'%)';
  });

  // ── THE REPLAY DATASETS ───────────────────────────────────────────────────────────────────
  // One fixed, unmistakably Bearish top-down picture, used unchanged by every replay fixture:
  //   * Weekly and H4 decline steadily -- the frozen calcBiasFromCandles reads both as Bearish.
  //   * Daily oscillates for 100 candles (giving the frozen 3-touch AOI engine a genuine,
  //     repeatedly-touched resistance shelf at 1.12000) and then declines for 30, which is what
  //     makes its own bias Bearish. Both facts are asserted, from the frozen functions, before
  //     any replay verdict is read.
  // Only the M15 trigger direction ever changes between runs.
  const S13_DAY=86400000, S13_HR=3600000;
  function s13Bar(o,h,l,c,t){ return{o:o,h:h,l:l,c:c,t:t}; }
  function s13Daily(n,startMs){
    const a=[];
    for(let i=0;i<n;i++){
      const t=new Date(startMs+i*S13_DAY);
      if(i<n-30){
        const ph=i%10;
        if(ph===5) a.push(s13Bar(1.11700,1.12000,1.11500,1.11700,t));      // the repeated peak
        else if(ph===0) a.push(s13Bar(1.10200,1.10500,1.09900,1.10200,t)); // the repeated trough
        else a.push(s13Bar(1.11000,1.11200,1.10800,1.11000,t));
      } else {
        const h=1.11200-(i-(n-30))*0.00100;                                // the closing downtrend
        a.push(s13Bar(h-0.0005,h,h-0.00400,h-0.00300,t));
      }
    }
    return a;
  }
  function s13Declining(n,startMs,stepMs,start,step){
    const a=[];
    for(let i=0;i<n;i++){ const b=start-i*step; a.push(s13Bar(b,b+0.00100,b-0.00100,b-0.00050,new Date(startMs+i*stepMs))); }
    return a;
  }
  const S13_WEEKLY=s13Declining(70,Date.UTC(2025,1,8),7*S13_DAY,1.19000,0.00100);
  const S13_DAILY=s13Daily(130,Date.UTC(2026,1,10));
  const S13_H4=s13Declining(200,Date.UTC(2026,4,12),4*S13_HR,1.12000,0.00020);
  // A 16-bar M15 cycle whose last three bars are a complete reversal trigger -- rejection wick,
  // engulf and market-structure break together. 'buy' prints the bullish version, 'sell' the
  // exact mirror of it. Nothing else differs between the two.
  function s13M15(direction,n,startMs){
    const a=[];
    for(let i=0;i<n;i++){
      const t=new Date(startMs+i*15*60000), k=i%16;
      if(k<13){
        if(direction==='buy'){ const b=1.09800+k*0.00003; a.push(s13Bar(b,b+0.00010,b-0.00010,b+0.00005,t)); }
        else { const b=1.10200-k*0.00003; a.push(s13Bar(b,b+0.00010,b-0.00010,b-0.00005,t)); }
      } else if(k===13){
        a.push(direction==='buy'?s13Bar(1.09995,1.10020,1.09990,1.10015,t):s13Bar(1.10005,1.10010,1.09980,1.09985,t));
      } else if(k===14){
        a.push(direction==='buy'?s13Bar(1.10025,1.10028,1.10005,1.10010,t):s13Bar(1.09975,1.09995,1.09972,1.09990,t));
      } else {
        a.push(direction==='buy'?s13Bar(1.10000,1.10040,1.09900,1.10030,t):s13Bar(1.10000,1.10100,1.09960,1.09970,t));
      }
    }
    return a;
  }
  const S13_WIN_MONWED=Date.UTC(2026,5,6,0,0,0); // Saturday start -- the evaluated bars run Mon-Wed on
  const S13_WIN_THUFRI=Date.UTC(2026,5,10,0,0,0); // Wednesday start -- the evaluated bars are Thu/Fri on
  async function replay(direction,windowStart){
    return await g.simulateTrueMTFReplay('EUR_USD',
      {weekly:S13_WEEKLY,daily:S13_DAILY,h4:S13_H4,m15:s13M15(direction,700,windowStart)},{});
  }
  function monWedRows(diag){ return diag.rejectedCandidates.filter(function(c){return c.weekday==='Mon-Wed';}); }
  function thuFriRows(diag){ return diag.rejectedCandidates.filter(function(c){return c.weekday==='Thu'||c.weekday==='Fri';}); }
  function noConfirmation(rows){ return rows.filter(function(c){return c.primaryRejectionId==='no_acceptable_confirmation';}); }
  function uniq(rows,field){ return Array.from(new Set(rows.map(function(c){return c[field];}))).join('|'); }

  await t('CTREND-REPLAY-0 PRECONDITION: the replay datasets really are Bearish, with a real 3-touch AOI',async function(){
    // Read from the frozen bias and AOI functions themselves -- these are the inputs the two
    // replay fixtures below depend on, so if they ever stop holding, those fixtures stop
    // proving anything and this one says so first.
    eq(g.calcBiasFromCandles(S13_WEEKLY),'Bearish','the weekly dataset reads Bearish');
    eq(g.calcBiasFromCandles(S13_DAILY),'Bearish','the daily dataset reads Bearish');
    eq(g.calcBiasFromCandles(S13_H4),'Bearish','the H4 dataset reads Bearish');
    eq(g.getScore({weekly:'Bearish',daily:'Bearish',fh:'Bearish'}),3,'so the top-down alignment score is 3/3');
    eq(g.getBias({weekly:'Bearish',daily:'Bearish',fh:'Bearish'}),'Bearish','and the overall bias is Bearish');
    const aoi=g.computeAOIWithTouches(S13_DAILY,100,3);
    eq(aoi.resistance,1.12,'the frozen AOI engine finds a resistance shelf at 1.12000');
    eq(aoi.resistanceTouches,7,'from seven genuine touches, well past the 3-touch minimum');
    return 'W/D/H4 all Bearish (3/3); daily AOI resistance 1.12000 with 7 touches';
  });

  await t('CTREND-REPLAY-1 the historical replay REFUSES counter-trend triggers -- and takes the with-trend one',async function(){
    // POSITIVE CONTROL: the trigger points the same way as the fixed Bearish bias.
    const withTrend=await replay('sell',S13_WIN_MONWED);
    ok(!withTrend.error,'PRECONDITION: the with-trend replay ran: '+withTrend.error);
    eq(withTrend.trades.length,1,'it takes a trade');
    eq(withTrend.trades[0].direction,'sell','on the bias side');
    eq(withTrend.diag.rejectionTotals.no_acceptable_confirmation,undefined,
      'and NOTHING is ever rejected for want of an acceptable confirmation');
    // NEGATIVE, ONE VARIABLE AWAY: the mirrored M15 trigger. Same bias, same AOI, same clock.
    const counter=await replay('buy',S13_WIN_MONWED);
    eq(counter.trades.length,0,'the mirrored, counter-trend trigger takes NO trade at all');
    const refused=noConfirmation(monWedRows(counter.diag));
    eq(refused.length,9,'nine Mon-Wed candidates are refused specifically at the confirmation gate');
    eq(uniq(refused,'direction'),'buy','every one of them read as a buy');
    eq(uniq(refused,'engulfing'),'none','with no acceptable engulf');
    // ...yet the bullish pattern was fully present on those very bars: rejectionWick and msb are
    // recorded on the SAME rejected rows, and they are two thirds of the same three-candle
    // reversal that carries the engulf. The funnel's engulf-observation counters (written from
    // their own lines, never from this gate) counted the engulfs anyway.
    eq(uniq(refused,'rejectionWick'),'Rejection wick (lower)','while the bullish rejection wick WAS observed on those bars');
    eq(uniq(refused,'msb'),'MSB bullish','and the bullish market-structure break too');
    eq(counter.diag.funnel.engulfingPatternObservations,18,
      'and the engulf-observation counters -- written from their own lines, not from this gate -- counted eighteen');
    ok(counter.diag.funnel.candidatesReachingMinConfluence>0,
      'candidates did clear the confluence gate first ('+counter.diag.funnel.candidatesReachingMinConfluence+'), so the refusal is not a low score');
    return 'with-trend: 1 trade, 0 confirmation rejections | counter-trend: 0 trades, 9 refused at confirmation despite 18 engulfs observed';
  });

  await t('CTREND-REPLAY-2 the Thursday/Friday diagnostic capture applies the SAME counter-trend rule',async function(){
    // A separate, third copy of the predicate, in the branch that records what a Thu/Fri setup
    // would have been. It never opens a trade, but it is what a human reads when deciding
    // whether a Thu/Fri setup was worth a manual entry -- so it must agree with the live rule.
    // POSITIVE CONTROL: a with-trend trigger on a Thu/Fri window IS recorded as a real engulf.
    const withTrend=await replay('sell',S13_WIN_THUFRI);
    const wtRows=thuFriRows(withTrend.diag);
    ok(wtRows.length>0,'PRECONDITION: the Thu/Fri diagnostic branch was actually reached ('+wtRows.length+' rows)');
    eq(uniq(wtRows,'direction'),'sell','every captured row read as a sell, with the bias');
    ok(wtRows.some(function(c){return c.engulfing==='Bearish engulf (1)';}),
      'and at least one records the engulf BY NAME -- the capture does see engulfs');
    eq(noConfirmation(wtRows).length,0,'none of them is refused for want of an acceptable confirmation');
    // NEGATIVE, ONE VARIABLE AWAY: the mirrored trigger over the same window.
    const counter=await replay('buy',S13_WIN_THUFRI);
    const ctRows=thuFriRows(counter.diag);
    ok(ctRows.length>0,'the same branch is reached ('+ctRows.length+' rows)');
    eq(uniq(ctRows,'engulfing'),'none','but NOT ONE row records an acceptable engulf');
    const ctRefused=noConfirmation(ctRows);
    eq(ctRefused.length,3,'three of them name the confirmation gate as their primary failure');
    eq(uniq(ctRefused,'direction'),'buy','all of them counter-trend buys');
    // The pattern was there: the same replay's bias-free observation counter saw the engulfs.
    ok(counter.diag.funnel.engulfingPatternObservations>0,
      'while the bias-free observation counter still saw '+counter.diag.funnel.engulfingPatternObservations+' engulfs');
    eq(counter.trades.length,0,'and no trade was taken');
    return 'Thu/Fri capture: with-trend records "Bearish engulf (1)"; counter-trend records "none" on every row, 3 named at the confirmation gate';
  });

  // ══ S14 — the rules that survived even the first detection-controls pass ═══════════════════
  // A clean single-process re-score of the 53 originally-uncovered mutations against this suite
  // found these still killing nothing. (The first re-score I ran was invalid: two driver processes
  // shared one working copy, so every result was attributed to its neighbour -- a perfect
  // off-by-one shift. Discarded and re-run serially.)

  await t('AOI4-1 the clustering TOLERANCE is what makes three separated touches one zone -- shrink it and the zone disappears',async function(){
    // The rule under test is `tolerance = max(range*0.04, currentPrice*0.001)`. Three touches
    // spread across 10 pips are ONE zone at the real tolerance (~11 pips here). They are three
    // separate 1-touch levels at a hundredth of it, and nothing reaches the 3-touch bar.
    const SPREAD=[{idx:5,l:1.09500},{idx:12,l:1.09550},{idx:19,l:1.09600}];
    const spread=g.computeAOIWithTouches(shelfSeries(PLATEAU_S4,SPREAD),100,3);
    // PRECONDITION: the tolerance really is the ~11-pip figure, and the spread really is inside it.
    near(spread.band,1.10300*0.001,1e-9,'PRECONDITION: tolerance is the currentPrice*0.001 floor, not the range term');
    ok(0.00100<spread.band,'PRECONDITION: the 10-pip spread of the three touches fits inside it');
    ok(spread.support!=null,'the three SEPARATED touches are grouped into one real zone');
    eq(spread.supportTouches,3,'and counted as three touches of that one zone');
    ok(spread.support>1.09500&&spread.support<1.09600,
      'the zone sits between the outermost touches ('+spread.support.toFixed(5)+'), proving they were merged rather than one being picked');
    // POSITIVE CONTROL, one variable away: identical touches cluster at ANY tolerance, so they
    // could never discriminate. The spread is the whole point of the fixture.
    const tight=g.computeAOIWithTouches(shelfSeries(PLATEAU_S4,TOUCH_3),100,3);
    eq(tight.supportTouches,3,'CONTROL: three touches at the SAME price also make a zone -- but would do so at any tolerance');
    near(tight.support,1.09500,1e-9,'and sit exactly on their shared price');
    return 'band='+spread.band.toFixed(5)+'; 3 touches spread over 10 pips merge to '+spread.support.toFixed(5);
  });

  await t('DS-AOI-1 detectSignals raises the AOI touch badge when price is AT the zone -- and not when it is away from it',async function(){
    // aoiSigTol = max(band, pipSize*12). The badge is the only thing that tells the operator the
    // engine believes price is at structure; it could be deleted outright with the gate silent.
    const at=g.detectSignals(shelfSeries(PLATEAU_S4,TOUCH_3,{o:1.09560,h:1.09600,l:1.09540,c:1.09550}),'EUR_USD');
    const atAoi=at.filter(function(s){return s.type==='aoi';});
    ok(atAoi.length>0,'an AOI signal is raised at all');
    ok(atAoi.some(function(s){return s.dir==='buy'&&s.label==='AOI support touch';}),
      'and it is the SUPPORT touch, on the buy side: '+typesOf(at));
    // NEGATIVE, ONE VARIABLE AWAY: the identical series, only the final close moved off the zone.
    const away=g.detectSignals(shelfSeries(PLATEAU_S4,TOUCH_3),'EUR_USD');
    const awayAoi=away.filter(function(s){return s.type==='aoi'&&s.dir==='buy';});
    eq(awayAoi.length,0,'with the close back up at the plateau, no support-touch badge is raised: '+typesOf(away));
    return 'close 1.09550 at the 1.09500 zone -> "AOI support touch"; close 1.10300 -> none';
  });

  await t('SC-WICK-1 the PARTIAL wick credit has its own threshold, distinct from the full one',async function(){
    // scoreConfluence gives half the wick weight at dnW/range > 0.35 ("Wick forming") and the full
    // weight only at > 0.55 with a small body. The partial threshold had no control of any kind.
    const partialItem=function(c){ return c.items.filter(function(i){return i.label==='Wick forming';})[0]; };
    const hitItem=function(c){ return c.items.filter(function(i){return i.label==='Rejection wick'&&i.state==='hit';})[0]; };
    // ratio 0.40: above the partial threshold, below the full one.
    const above=g.scoreConfluence(quiet([bar(1.10040,1.10100,1.10000,1.10090)]),'EUR_USD','long');
    ok(partialItem(above),'a 0.40 lower wick earns the PARTIAL credit');
    eq(partialItem(above).state,'partial','recorded as partial, not as a full hit');
    eq(partialItem(above).pts,Math.round(g.WEIGHTS().wick*0.5),'worth exactly half the wick weight');
    ok(!hitItem(above),'and NOT the full rejection-wick credit');
    // NEGATIVE, ONE VARIABLE AWAY: ratio 0.30 -- the same candle with the low raised 10 points.
    const below=g.scoreConfluence(quiet([bar(1.10040,1.10100,1.10010,1.10090)]),'EUR_USD','long');
    ok(!partialItem(below),'a 0.30 lower wick earns nothing');
    ok(below.total<above.total,'and scores strictly lower ('+below.total+' < '+above.total+')');
    // The SHORT side reads the OPPOSITE wick -- the same 0.40 lower wick must earn a long nothing.
    const shortSide=g.scoreConfluence(quiet([bar(1.10040,1.10100,1.10000,1.10090)]),'EUR_USD','short');
    ok(!partialItem(shortSide),'the same candle gives a SHORT no partial credit -- the rule is sided');
    return 'dnW/range 0.40 -> "Wick forming" ('+partialItem(above).pts+' pts); 0.30 -> nothing; short side -> nothing';
  });

  // The H1-master-clock orchestrator catches up every newly-closed H4/D/W candle after each H1
  // candle. The whole higher-timeframe half of the engine could be skipped, or its boundary
  // flipped by one candle, with the entire repository green.
  const HTF_T0=Date.UTC(2026,0,5,0,0,0);   // a Monday; the zone engine has no session/day gate
  const HR=3600000;
  function htfBar(t,low){ return{o:low+0.00050,h:low+0.00100,l:low,c:low+0.00050,t:new Date(t)}; }
  function htfH1(){ const a=[]; for(let i=0;i<8;i++) a.push(htfBar(HTF_T0+i*HR,1.09800+i*0.00010)); return a; }
  // H4 closes land at T0+4h and T0+8h -- the second EXACTLY on the last H1 candle's close.
  function htfH4(){ return [htfBar(HTF_T0,1.09700),htfBar(HTF_T0+4*HR,1.09750),htfBar(HTF_T0+8*HR,1.09720)]; }

  await t('PRECEDENCE-1 the two setup types are MUTUALLY EXCLUSIVE on zone status -- which is why their order is safe',async function(){
    // Swapping the order in which alexGClassifySetup evaluates break-retest and repeated-reaction
    // kills nothing, and no fixture can honestly make it kill anything: the two predicates gate on
    // OPPOSITE zone statuses, so no zone can ever satisfy both and the order cannot change an
    // outcome. That makes the swap a semantically equivalent mutation, not an uncovered rule.
    //
    // What IS worth pinning is the invariant that makes it equivalent. If either status guard were
    // ever relaxed, precedence would start deciding real setups silently -- and this fixture is
    // what would notice.
    const cfg=g.ALEXG_CONFIG();
    const validated={id:'Z1',status:'validated',touches:[1,2,3,4],brokenAtBar:null,brokenAt:null,brokenDirection:null};
    const broken={id:'Z2',status:'broken',touches:[1,2,3,4],brokenAtBar:10,brokenAt:1000,brokenDirection:'downThroughSupport'};
    const retestTouch={swingType:'high',fromSide:'below'};
    // A validated zone: repeated-reaction is available, break-retest is refused outright.
    eq(g.alexGEvaluateRepeatedReaction(validated,retestTouch,3,'clean',cfg).qualifies,true,
      'PRECONDITION: a clean validated zone on its 4th reaction DOES qualify as a repeated reaction');
    eq(g.alexGEvaluateBreakRetest(validated,retestTouch,3,11,cfg).qualifies,false,
      'and the very same zone can NEVER qualify as a break-retest -- it was never broken');
    // A broken zone: the mirror image.
    eq(g.alexGEvaluateBreakRetest(broken,retestTouch,3,11,cfg).qualifies,true,
      'PRECONDITION: a broken zone retested in the right direction DOES qualify as a break-retest');
    eq(g.alexGEvaluateRepeatedReaction(broken,retestTouch,3,'clean',cfg).qualifies,false,
      'and the same broken zone can NEVER qualify as a repeated reaction -- the status guard forbids it');
    return 'validated -> repeated only; broken -> break-retest only. No zone satisfies both, so evaluation order cannot decide anything.';
  });

  await t('DUPE-1 re-running the engine over the same bars does NOT record the same setup twice',async function(){
    // alexGRunSetupEngine is re-run over a rolling window on EVERY live poll, so the same
    // historical setup is re-derived every tick. The guard in alexGCreateSetupRecord is the only
    // thing stopping alexGSetupState from growing without bound and presenting the SAME setup as
    // a fresh one over and over -- which downstream is a duplicate trade, not a cosmetic problem.
    g.resetAlexGZoneEngine();
    const first=runEngine(supportSeries(1.09810));
    eq(first.setups.length,1,'PRECONDITION: the series really does produce one setup');
    const afterFirst=g.alexGSetupStateAll().length;
    eq(afterFirst,1,'PRECONDITION: and exactly one is recorded');
    const firstId=g.alexGSetupStateAll()[0].setupId;
    // Re-run over the SAME bars WITHOUT resetting -- exactly what the next live poll does.
    runEngine(supportSeries(1.09810));
    eq(g.alexGSetupStateAll().length,afterFirst,
      'a second identical pass records nothing new ('+g.alexGSetupStateAll().length+' setups)');
    eq(g.alexGSetupStateAll()[0].setupId,firstId,'and the one that is there is the ORIGINAL record, not a rewrite');
    // A third pass, to prove it is a guard rather than an alternating quirk.
    runEngine(supportSeries(1.09810));
    eq(g.alexGSetupStateAll().length,afterFirst,'and a third pass still records nothing new');

    // ── AND NOW THE GUARD ITSELF ──────────────────────────────────────────────────────────────
    // The three assertions above are TRUE but do NOT exercise the duplicate guard: disabling
    // `if(alexGSetupState.some(s=>s.setupId===setupId)) return null;` leaves every one of them
    // passing, because re-running the engine never reaches alexGCreateSetupRecord a second time
    // for the same touch -- an upstream mechanism already prevents that. Asserting only through
    // the engine would report this rule as covered while the guard could be deleted outright.
    // (Found by mutation, not by reading: the first version of this fixture stopped here.)
    //
    // So the guard is driven DIRECTLY, with the real zone and the real touch the engine just
    // produced -- the exact inputs that generate the exact setupId already in state.
    const bars=supportSeries(1.09810);
    const zone=onlyZone(first);
    const touch=zone.touches[3];
    const cfg=g.ALEXG_CONFIG();
    const before=g.alexGSetupStateAll().length;
    const dupe=g.alexGCreateSetupRecord('EUR_USD','H1',zone,touch,3,'A_repeatedReaction',{},
      'clean',bars,touch.barIndex,cfg);
    eq(dupe,null,'creating a record for a setupId already in state returns null');
    eq(g.alexGSetupStateAll().length,before,'and records nothing -- the state does not grow');
    // POSITIVE CONTROL: the guard is keyed on setup IDENTITY, not "refuse everything". The same
    // call against a fresh state DOES record, so the null above is the guard and not a dead path.
    g.resetAlexGZoneEngine();
    const accepted=g.alexGCreateSetupRecord('EUR_USD','H1',zone,touch,3,'A_repeatedReaction',{},
      'clean',bars,touch.barIndex,cfg);
    ok(accepted,'the identical call against empty state DOES create a record');
    eq(g.alexGSetupStateAll().length,1,'and records exactly one');
    eq(accepted.setupId,firstId,'with the very same setupId the guard was rejecting a moment ago');
    return 'engine idempotent over the same window; direct duplicate call -> null and no growth; same call on empty state -> records '+firstId;
  });

  await t('HTF-1 the engine actually evaluates the HIGHER timeframes, not just H1',async function(){
    g.resetAlexGZoneEngine();
    g.alexGRunSetupEngine('EUR_USD',{H1:htfH1(),H4:htfH4(),D:[],W:[]});
    const seen=g.alexGLastEvaluatedFor('EUR_USD');
    ok(seen,'the engine records what it evaluated');
    ok(seen.H1!=null,'PRECONDITION: H1 was evaluated -- otherwise nothing ran at all');
    ok(seen.H4!=null,'H4 was evaluated too: the higher-timeframe catch-up is not a no-op');
    const st=g.alexGZoneStateAll('EUR_USD');
    ok(st&&st.H4,'and H4 has its own zone state, built from H4 candles');
    // NEGATIVE, ONE VARIABLE AWAY: the same H1 series with no H4 data records no H4 evaluation.
    g.resetAlexGZoneEngine();
    g.alexGRunSetupEngine('EUR_USD',{H1:htfH1(),H4:[],D:[],W:[]});
    eq(g.alexGLastEvaluatedFor('EUR_USD').H4,undefined,
      'with an empty H4 dataset nothing is recorded -- so the assertion above tracks real H4 work');
    return 'H4 evaluated with data, not evaluated without it';
  });

  await t('HTF-2 an HTF candle closing EXACTLY on the H1 close is consumed in that step, not left behind',async function(){
    // `closeTimes[tf][ptr+1] <= h1CloseTs`. Drop the `=` and a higher-timeframe candle that closes
    // on the very same instant as the H1 candle is skipped -- so the engine trades an H1 bar while
    // its H4 structure is one candle stale, permanently, at every aligned boundary.
    g.resetAlexGZoneEngine();
    g.alexGRunSetupEngine('EUR_USD',{H1:htfH1(),H4:htfH4(),D:[],W:[]});
    const seen=g.alexGLastEvaluatedFor('EUR_USD');
    eq(seen.H1,HTF_T0+8*HR,'PRECONDITION: the last H1 candle closes at T0+8h');
    eq(seen.H4,HTF_T0+8*HR,
      'and the H4 candle closing at exactly T0+8h was consumed in that same step -- an exclusive '+
      'boundary would leave H4 stuck at T0+4h');
    return 'H1 close T0+8h; H4 caught up to T0+8h (inclusive boundary proven)';
  });

  await t('CLUST-NEAR-1 a swing joins the NEAREST eligible cluster, not the first one in the list',async function(){
    // alexGAssignCluster scans for the minimum distance. Collapse that scan to "take eligible[0]"
    // and a swing silently joins whichever zone happens to sit earlier in the array -- the wrong
    // zone, with the wrong touch count, feeding the wrong setup.
    const TOL=0.00100;
    const clusters=[
      {id:'Z-far', swingType:'low',center:1.10090,createdAtCloseTimeMs:1000},
      {id:'Z-near',swingType:'low',center:1.10005,createdAtCloseTimeMs:2000}
    ];
    const chosen=g.alexGAssignCluster(clusters,'low',1.10000,TOL);
    ok(chosen,'a cluster must be chosen at all');
    eq(chosen.id,'Z-near','the NEARER cluster wins, even though it is second in the array and created LATER');
    // PRECONDITION: both really were eligible -- otherwise "nearest" was never exercised.
    ok(Math.abs(1.10000-clusters[0].center)<=TOL&&Math.abs(1.10000-clusters[1].center)<=TOL,
      'PRECONDITION: both clusters are inside the grouping tolerance, so the choice is genuinely between them');
    // CONTROL: reverse the array. A first-not-nearest rule would flip the answer; the real rule cannot.
    const reversed=g.alexGAssignCluster([clusters[1],clusters[0]],'low',1.10000,TOL);
    eq(reversed.id,'Z-near','and the same cluster wins with the array order reversed -- order is not the rule');
    // And the documented tie-break still applies when the distances are genuinely equal. The tie
    // is built from IDENTICAL centres rather than two centres equidistant either side of the
    // price: 1.10050-1.10000 and 1.10000-1.09950 are NOT equal in binary floating point, so that
    // "tie" is really a nearest-wins case and would prove nothing about the cascade.
    const tie=g.alexGAssignCluster([
      {id:'Z-b',swingType:'low',center:1.10050,createdAtCloseTimeMs:2000},
      {id:'Z-a',swingType:'low',center:1.10050,createdAtCloseTimeMs:1000}
    ],'low',1.10000,TOL);
    eq(tie.id,'Z-a','on an exact distance tie the EARLIER-created cluster wins, per the frozen cascade');
    // ...and the id tie-break below it, when even the creation times match.
    const tie2=g.alexGAssignCluster([
      {id:'Z-z',swingType:'low',center:1.10050,createdAtCloseTimeMs:1000},
      {id:'Z-a',swingType:'low',center:1.10050,createdAtCloseTimeMs:1000}
    ],'low',1.10000,TOL);
    eq(tie2.id,'Z-a','and on an exact creation-time tie the lower cluster id wins');
    return 'nearest wins in both array orders; exact tie falls to the earlier createdAtCloseTimeMs';
  });

  await t('SAMEINT-1 the same-interaction window is INCLUSIVE at exactly maxBarGap',async function(){
    // `<=` vs `<`. One bar of difference decides whether two swing anchors are ONE interaction or
    // two -- which decides the touch count, which decides whether a zone reaches its setup bar.
    const GAP=3;
    const A={swingType:'low',barIndex:10};
    eq(g.alexGIsSameInteraction(A,{swingType:'low',barIndex:13},GAP),true,
      'exactly maxBarGap apart is ONE interaction -- the boundary is inclusive');
    eq(g.alexGIsSameInteraction(A,{swingType:'low',barIndex:14},GAP),false,
      'one bar further apart is TWO interactions');
    eq(g.alexGIsSameInteraction(A,{swingType:'low',barIndex:10},GAP),true,'the same bar is trivially one');
    // And the type check is real, not incidental to the distance.
    eq(g.alexGIsSameInteraction(A,{swingType:'high',barIndex:11},GAP),false,
      'a swing HIGH one bar away is never the same interaction as a swing LOW');
    return 'gap 3 -> same; gap 4 -> different; opposite swingType -> never same';
  });

  await t('MINUSABLE-1 the usable-candle floor is exactly 10 -- ten is usable, nine is not',async function(){
    const C=g.MARKET_DATA_COMPLETENESS();
    eq(g.MARKET_DATA_MIN_USABLE_CANDLES(),10,'PRECONDITION: the floor really is 10');
    eq(g.marketDataClassify(10,10,10),C.COMPLETE,'exactly ten usable candles, count met -> COMPLETE');
    eq(g.marketDataClassify(20,15,10),C.PARTIAL,'exactly ten usable but short of the request -> PARTIAL');
    eq(g.marketDataClassify(10,10,9),C.UNAVAILABLE,'nine usable -> UNAVAILABLE, whatever else arrived');
    eq(g.marketDataClassify(10,10,0),C.UNAVAILABLE,'zero usable -> UNAVAILABLE');
    // The rule that matters most: short data is never rounded UP to COMPLETE.
    eq(g.marketDataClassify(220,219,219),C.PARTIAL,'one candle short of the request is PARTIAL, not COMPLETE');
    return 'floor=10; 10 usable+count met -> COMPLETE, 9 -> UNAVAILABLE, 219/220 -> PARTIAL';
  });

  await t('ELT-MIN-1 the live trigger needs 25 M15 candles -- twenty-five works, twenty-four is "No data"',async function(){
    // The guard could be raised to any value and nothing objected, silently starving the trigger
    // on every pair whose history is merely adequate rather than generous.
    const base=reversalM15();
    ok(base.length>=25,'PRECONDITION: the working series has at least 25 bars ('+base.length+')');
    const setup=function(bars){
      g.setCfg(); g.resetPairData(); g.resetStructuralAOICache();
      g.setM15Bars(bars); g.setBidAsk(1.10025,1.10035);
      g.resetScanData(); g.setScanData('EUR/USD',BULLISH_TABLE);
    };
    setup(base.slice(-24));
    const short=await g.evaluateLiveTrigger('EUR_USD');
    eq(short.fires,false,'24 candles cannot fire');
    eq(short.reason,'No data','and the refusal names the data floor, not some later gate');
    // POSITIVE CONTROL, ONE BAR AWAY: the same series with its 25th bar restored must get PAST
    // the data floor. Without this the fixture would pass with the floor deleted entirely.
    setup(base.slice(-25));
    const okv=await g.evaluateLiveTrigger('EUR_USD');
    ok(okv.reason!=='No data','25 candles clear the data floor (reason now: '+okv.reason+')');
    return '24 -> "No data"; 25 -> past the floor. Exactly one bar apart.';
  });

  await t('FSP-EDGE-1 the swing window checks the OUTERMOST neighbour too -- the bar exactly `lookback` away',async function(){
    // `for(k=1;k<=lookback;k++)`. Drop the `=` and the neighbour at exactly the lookback distance
    // stops being consulted, so a bar with a lower low three bars out is still reported as a swing
    // low. Every zone, cluster and AOI downstream is built on these points.
    const mk=function(lows){ return lows.map(function(l){ return bar(l+0.00050,l+0.00100,l,l+0.00050); }); };
    //          idx:    0        1        2        3(candidate) 4        5        6        7
    const DISQUALIFIED=[1.09900,1.10200,1.10100,1.10000,     1.10100,1.10200,1.10300,1.10400];
    const sp=g.findSwingPoints(mk(DISQUALIFIED),3);
    ok(sp.swingLows.indexOf(1.10000)===-1,
      'the candidate is NOT a swing low: the bar exactly 3 back is lower ('+JSON.stringify(sp.swingLows)+')');
    // POSITIVE CONTROL, ONE VARIABLE AWAY: raise that single outermost bar above the candidate.
    const QUALIFIED=DISQUALIFIED.slice(); QUALIFIED[0]=1.10300;
    const sp2=g.findSwingPoints(mk(QUALIFIED),3);
    ok(sp2.swingLows.indexOf(1.10000)!==-1,
      'and IS a swing low once that one outermost bar is raised -- so the series really can produce one ('+JSON.stringify(sp2.swingLows)+')');
    return 'idx0 low 1.09900 -> candidate rejected; idx0 low 1.10300 -> candidate accepted. Only the bar at exactly lookback distance changed.';
  });

  await t('SC-WICK-2 the partial threshold is EXCLUSIVE at exactly 0.35, not inclusive',async function(){
    // Decimal FX prices do not generally divide to exact binary fractions, so the boundary candle
    // is found by search and the exact identity is re-proved here before anything is asserted.
    // Without this the fixture would silently degrade into a non-boundary test.
    let found=null;
    for(let lo=1.10000;lo<1.10500&&!found;lo+=0.00001){
      for(let r=0.00020;r<0.00300;r+=0.00001){
        const h=lo+r, minoc=lo+r*0.35;
        if((minoc-lo)/(h-lo)===0.35){ found={lo:lo,h:h,minoc:minoc,r:r}; break; }
      }
    }
    ok(found,'a candle whose dnW/range is EXACTLY 0.35 in floating point must exist for this test to mean anything');
    const at=bar(found.minoc,found.h,found.lo,found.minoc+(found.h-found.minoc)*0.5);
    const dnW=Math.min(at.o,at.c)-at.l, range=at.h-at.l;
    eq(dnW/range,0.35,'the constructed candle really does sit exactly ON the threshold');
    const c=g.scoreConfluence(quiet([at]),'EUR_USD','long');
    ok(!c.items.filter(function(i){return i.label==='Wick forming';})[0],
      'exactly 0.35 earns NOTHING -- the comparison is strictly greater-than');
    return 'dnW/range === 0.35 exactly -> no partial credit (exclusive boundary proven, not assumed)';
  });

  return out;
  })();
}
