// v12.38 — AGGREGATE AND DERIVED STATISTICS coverage (MOGO execution-reporting mutation tranche C).
//
// WHY THIS SUITE EXISTS. A mutation re-score of the paper-trade execution REPORTING surface found
// that the numbers which SUMMARISE many trades at once — win rate, profit factor, expectancy,
// drawdown, R-multiples, average excursion, win/loss counts — could each be broken in an
// individually plausible way with the entire 1,801-fixture gate staying green. Those figures are
// what a human reads to decide whether a strategy is survivable, so a silently wrong one is worse
// than a missing one.
//
// THE TWO RULES THIS SUITE OBEYS, because this surface is unusually good at defeating tests:
//
//   1. NO SELF-CONSISTENCY. Nothing below recomputes a statistic the way the production code
//      computes it and then compares the two. Every expectation is a HAND-DERIVED LITERAL, and
//      the arithmetic that produces it is written out in the fixture description so a reader can
//      check the number without running anything.
//
//   2. NO SYMMETRIC DATA. Every dataset is deliberately lopsided (3 wins / 1 loss, unequal
//      R multiples, unequal MAE values, unequal streak lengths). A balanced dataset makes
//      "wins" and "losses" interchangeable and a sign flip invisible — the exact blind spot that
//      let a reported win rate be swapped for the loss rate, and a reported win count be swapped
//      for the loss count, without any existing fixture noticing.
//
// Nothing here touches real storage, opens a real position, or persists a paper trade: every
// function under test is a pure reader that is handed a literal array.
//
// alexGComputeReplayStats is PROTECTED (regression-baseline.json). It is CALLED and its OUTPUT is
// asserted; it is never edited, wrapped or re-implemented here.
function runV1238ExecutionReportingStatsFixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,method:'execution',detail:detail||''});};
  const near=(a,b)=>(typeof a==='number')&&isFinite(a)&&Math.abs(a-b)<1e-9;

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP G — computeGroupTradeStats (Manual Review performance groups)
  // ════════════════════════════════════════════════════════════════════════════════════════
  //
  // DATASET GA. Five journal records at a constant $100 risk: four CLOSED, one still OPEN.
  //
  //   #1 CLOSED Win   pnl +250  -> +2.5R   maePips  3
  //   #2 CLOSED Loss  pnl -100  -> -1.0R   maePips 15
  //   #3 CLOSED Win   pnl +150  -> +1.5R   maePips  8
  //   #4 CLOSED Win   pnl  +50  -> +0.5R   maePips 10
  //   #5 OPEN         pnl null            maePips 100  (must contribute to NOTHING but openCount)
  //
  // HAND-COMPUTED TRUTH:
  //   resolved      = 4 CLOSED (the OPEN record is not resolved)
  //   winRate       = 3 wins / 4 resolved            = 75%
  //   R multiples   = +2.5, -1.0, +1.5, +0.5 ; net   = +3.5R
  //   expectancy    = 3.5R / 4 trades = 0.875        -> 0.88 after toFixed(2)
  //   equity walk   = 2.5 -> 1.5 -> 3.0 -> 3.5 ; peak 2.5 then trough 1.5
  //   max drawdown  = 2.5 - 1.5                      = 1.00R
  //   gross win     = 250 + 150 + 50                 = 450
  //   gross loss    = |-100|                         = 100
  //   profit factor = 450 / 100                      = 4.50
  //   avg MAE       = (3 + 15 + 8 + 10) / 4 = 36 / 4 = 9 pips   (the SUM is 36 — a different number)
  //
  // The lopsidedness is the point: 3-vs-1 wins, a 4.5 profit factor whose reciprocal is 0.222,
  // and a mean MAE of 9 against a sum of 36. There is no mutation of this function that leaves
  // every one of those numbers where it is.
  const grpRec=function(o){
    const base={status:'CLOSED',result:'Win',riskAmount:100,pnl:100,maePips:0,mfePips:40,
      confluenceSnapshotAtApproval:70,strategy:'current_strategy',entrySource:'MANUAL_REVIEW',
      openedAt:'2026-08-01T00:00:00.000Z',closedAt:'2026-08-01T01:00:00.000Z'};
    if(o) Object.keys(o).forEach(function(k){ base[k]=o[k]; });
    return base;
  };
  const GA=[
    grpRec({result:'Win', pnl: 250, maePips: 3, closedAt:'2026-08-01T01:00:00.000Z'}),
    grpRec({result:'Loss',pnl:-100, maePips:15, closedAt:'2026-08-02T01:00:00.000Z'}),
    grpRec({result:'Win', pnl: 150, maePips: 8, closedAt:'2026-08-03T01:00:00.000Z'}),
    grpRec({result:'Win', pnl:  50, maePips:10, closedAt:'2026-08-04T01:00:00.000Z'}),
    grpRec({status:'OPEN',result:null,pnl:null,maePips:100,closedAt:null})
  ];
  const gs=g.computeGroupTradeStats(GA);

  assert('ERS.G7: computeGroupTradeStats counts 4 RESOLVED out of 5 records — the still-OPEN trade raises openCount to 1 and total to 5, and is not resolved',
    gs.resolvedCount===4&&gs.openCount===1&&gs.total===5,
    JSON.stringify({resolved:gs.resolvedCount,open:gs.openCount,total:gs.total}));

  assert('ERS.G1: win rate is 3 wins over the 4 RESOLVED trades = 75% — dividing by all 5 records instead would report 60%',
    gs.winRate===75,'winRate='+gs.winRate);

  assert('ERS.G2: profit factor is gross win 450 (250+150+50) over gross loss 100 = 4.50 — the inverse would be 0.22',
    near(gs.profitFactor,4.5),'profitFactor='+gs.profitFactor);

  assert('ERS.G3: expectancy is the MEAN R, +3.5R over 4 trades = 0.875 -> 0.88 — reporting the net instead would say 3.50',
    gs.expectancyR===0.88&&gs.avgR===0.88,
    JSON.stringify({expectancyR:gs.expectancyR,avgR:gs.avgR}));

  assert('ERS.G5: R multiples keep the sign of P&L — +250/-100/+150/+50 at $100 risk give +2.5/-1.0/+1.5/+0.5, so expectancy is +0.88 and drawdown 1.00R; a sign flip would give -0.88 and 3.50R',
    gs.expectancyR===0.88&&near(gs.maxDrawdownR,1),
    JSON.stringify({expectancyR:gs.expectancyR,maxDrawdownR:gs.maxDrawdownR}));

  assert('ERS.G4: max drawdown ACCUMULATES to 1.00R — the curve peaks at +2.5R, the -1.0R trade drops it to +1.5R, and 2.5-1.5 = 1.00R rather than 0',
    near(gs.maxDrawdownR,1),'maxDrawdownR='+gs.maxDrawdownR);

  assert('ERS.G6: average MAE is the MEAN of the 4 resolved trades, (3+15+8+10)/4 = 9 pips — the sum is 36, a different number',
    near(gs.avgMAE,9),'avgMAE='+gs.avgMAE);

  // POSITIVE CONTROL for ERS.G7/G1/G6: flip the same OPEN record to a CLOSED Loss and every one of
  // those figures MOVES. This proves the assertions above are reading the exclusion, not a constant
  // that happens to match.
  const GA_CTL=GA.slice(0,4).concat([grpRec({status:'CLOSED',result:'Loss',pnl:-100,maePips:100,
    closedAt:'2026-08-05T01:00:00.000Z'})]);
  const gsCtl=g.computeGroupTradeStats(GA_CTL);
  // 5 resolved, 3 wins -> 60%; MAE mean (3+15+8+10+100)/5 = 136/5 = 27.2
  assert('ERS.G0 (positive control): turning that OPEN record into a CLOSED Loss moves resolved 4->5, win rate 75%->60% and avg MAE 9->27.2 pips — the exclusion assertions above are observing real behaviour',
    gsCtl.resolvedCount===5&&gsCtl.openCount===0&&gsCtl.winRate===60&&near(gsCtl.avgMAE,27.2),
    JSON.stringify({resolved:gsCtl.resolvedCount,winRate:gsCtl.winRate,avgMAE:gsCtl.avgMAE}));

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP S — computeReplayStats (TRUE MTF replay report)
  // ════════════════════════════════════════════════════════════════════════════════════════
  //
  // This engine books a Win as +ratio R and a Loss as exactly -1R, and its profit factor divides
  // gross win R by the COUNT of losses.
  //
  // DATASET SA, in order:
  //   #1 Win  ratio 2.5      -> +2.5R
  //   #2 Win  ratio 1.5      -> +1.5R
  //   #3 Loss               -> -1.0R
  //   #4 Win  ratio 3.5      -> +3.5R
  //   #5 Loss               -> -1.0R
  //   #6 "Still open at end of replay window"      (valid, but not decided)
  //   #7 Win ratio 100, lookaheadPass:false        (LOOKAHEAD-INVALIDATED — must not be reported)
  //
  // HAND-COMPUTED TRUTH:
  //   totalTrades 7, validTrades 6, invalidatedTrades 1, decided 5, wins 3, losses 2
  //   win rate      = 3 / 5                              = 60%
  //   expectancy    = (2.5 + 1.5 - 1 + 3.5 - 1) / 5 = 5.5 / 5 = 1.10
  //                   (over VALID 6 it would be 0.9167; over ALL 7 it would be 0.7857)
  //   gross win     = 2.5 + 1.5 + 3.5                    = 7.5R
  //   loss count    = 2
  //   profit factor = 7.5 / 2                            = 3.75   (inverse 0.2667)
  //   streaks       = W,W,L,W,L  -> longest WIN run 2, longest LOSS run 1  (deliberately unequal)
  const mtf=function(o){
    const base={result:'Win',ratio:2,lookaheadPass:true,ambiguous:false,maePips:5,mfePips:20,
      pair:'EUR_USD',session:'London',dayOfWeek:2,fingerprint:'fp',regimeTags:[],decisionTs:0};
    if(o) Object.keys(o).forEach(function(k){ base[k]=o[k]; });
    return base;
  };
  const SA=[
    mtf({result:'Win', ratio:2.5}),
    mtf({result:'Win', ratio:1.5}),
    mtf({result:'Loss',ratio:1}),
    mtf({result:'Win', ratio:3.5}),
    mtf({result:'Loss',ratio:1}),
    mtf({result:'Still open at end of replay window',ratio:9}),
    mtf({result:'Win', ratio:100, lookaheadPass:false})
  ];
  const ms=g.computeReplayStats(SA);

  assert('ERS.S1: replay expectancy divides by the 5 DECIDED trades — 5.5R/5 = 1.10; dividing by the 6 valid trades would give 0.917 and by all 7 would give 0.786',
    near(ms.expectancyR,1.1)&&ms.decided===5,
    JSON.stringify({expectancyR:ms.expectancyR,decided:ms.decided,valid:ms.validTrades,total:ms.totalTrades}));

  assert('ERS.S2: replay profit factor is gross win 7.5R (2.5+1.5+3.5) over 2 losses = 3.75 — the inverse would be 0.27',
    near(ms.profitFactor,3.75),'profitFactor='+ms.profitFactor);

  assert('ERS.S3: the lookahead-invalidated +100R Win is EXCLUDED from every reported figure — 7 trades in, 6 valid, 1 invalidated, 5 decided, 3 wins, 60% win rate, 3.75 profit factor',
    ms.totalTrades===7&&ms.validTrades===6&&ms.invalidatedTrades===1&&ms.decided===5&&
    ms.wins===3&&ms.winRate===60&&near(ms.profitFactor,3.75),
    JSON.stringify({total:ms.totalTrades,valid:ms.validTrades,invalidated:ms.invalidatedTrades,
      decided:ms.decided,wins:ms.wins,winRate:ms.winRate,pf:ms.profitFactor}));

  // POSITIVE CONTROL for ERS.S3: the SAME trade with lookaheadPass:true changes the report
  // dramatically — 4 wins of 6 decided (67%), profit factor (7.5+100)/2 = 53.75. If the exclusion
  // assertion above were vacuous, this control could not distinguish the two runs.
  const SA_CTL=SA.slice(0,6).concat([mtf({result:'Win',ratio:100,lookaheadPass:true})]);
  const msCtl=g.computeReplayStats(SA_CTL);
  assert('ERS.S0 (positive control): admitting that same +100R trade moves decided 5->6, win rate 60%->67% and profit factor 3.75->53.75 — the lookahead exclusion above is a real, observed filter',
    msCtl.decided===6&&msCtl.wins===4&&msCtl.winRate===67&&near(msCtl.profitFactor,53.75)&&
    msCtl.invalidatedTrades===0,
    JSON.stringify({decided:msCtl.decided,wins:msCtl.wins,winRate:msCtl.winRate,pf:msCtl.profitFactor}));

  assert('ERS.S4: the W,W,L,W,L sequence has a longest WIN run of 2 and a longest LOSS run of 1 — the two are deliberately unequal, so a max-win-streak that actually tracked the loss run would report 1',
    ms.maxConsecutiveWins===2&&ms.maxConsecutiveLosses===1,
    JSON.stringify({maxWin:ms.maxConsecutiveWins,maxLoss:ms.maxConsecutiveLosses}));

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP T — alexGComputeReplayStats  (PROTECTED: called and observed, never modified)
  // ════════════════════════════════════════════════════════════════════════════════════════
  //
  // This engine books each decided trade at its OWN resultR (not a fixed -1 on a loss), and its
  // profit factor divides gross win R by the ABSOLUTE gross loss R.
  //
  // DATASET TA:
  //   #1 Win  resultR +2.5
  //   #2 Win  resultR +1.5
  //   #3 Loss resultR -2.0
  //   #4 Win  resultR +3.5
  //   #5 Win  resultR +100, lookaheadPass:false   (LOOKAHEAD-INVALIDATED)
  //
  // HAND-COMPUTED TRUTH:
  //   decided 4, wins 3, losses 1
  //   win rate      = 3 / 4                = 75%      (the LOSS rate is 25% — a different number)
  //   net R         = 2.5 + 1.5 - 2 + 3.5  = +5.5R
  //   expectancy    = 5.5 / 4              = 1.375
  //   gross win     = 2.5 + 1.5 + 3.5      = 7.5R
  //   |gross loss|  = 2.0R
  //   profit factor = 7.5 / 2              = 3.75      (inverse 0.2667)
  const ag=function(o){
    const base={tradeId:'AG',result:'Win',resultR:2,lookaheadPass:true,stillOpen:false,
      maePips:5,mfePips:20,direction:'buy',pair:'EUR_USD',timeframe:'H1',setupLabel:'A',
      session:'London',dayOfWeek:2,trendContext:'up',zoneTouchNumber:3,
      distanceToPsych500Pips:12,distanceToPsych100Pips:4,barsHeld:5,calendarHours:5};
    if(o) Object.keys(o).forEach(function(k){ base[k]=o[k]; });
    return base;
  };
  const TA=[
    ag({tradeId:'T1',result:'Win', resultR:2.5}),
    ag({tradeId:'T2',result:'Win', resultR:1.5}),
    ag({tradeId:'T3',result:'Loss',resultR:-2}),
    ag({tradeId:'T4',result:'Win', resultR:3.5}),
    ag({tradeId:'T5',result:'Win', resultR:100,lookaheadPass:false})
  ];
  const ts=g.alexGComputeReplayStats(TA);

  assert('ERS.T1: the ALEX replay report states the WIN rate, 3 wins of 4 decided = 75% — the loss rate for this deliberately lopsided set is 25%',
    ts.winRate===75&&ts.wins===3&&ts.losses===1,
    JSON.stringify({winRate:ts.winRate,wins:ts.wins,losses:ts.losses}));

  assert('ERS.T2: ALEX replay profit factor is gross win 7.5R (2.5+1.5+3.5) over absolute gross loss 2.0R = 3.75 — the inverse would be 0.27',
    near(ts.profitFactor,3.75),'profitFactor='+ts.profitFactor);

  assert('ERS.T4: the lookahead-invalidated +100R Win is EXCLUDED — 5 trades in, 4 valid, 1 invalidated, 4 decided, 3 wins, net +5.5R, expectancy 1.375',
    ts.totalTrades===5&&ts.validTrades===4&&ts.invalidatedTrades===1&&ts.decided===4&&
    ts.wins===3&&near(ts.netR,5.5)&&near(ts.expectancyR,1.375),
    JSON.stringify({total:ts.totalTrades,valid:ts.validTrades,invalidated:ts.invalidatedTrades,
      decided:ts.decided,wins:ts.wins,netR:ts.netR,expectancyR:ts.expectancyR}));

  // POSITIVE CONTROL for ERS.T4.
  const TA_CTL=TA.slice(0,4).concat([ag({tradeId:'T5',result:'Win',resultR:100,lookaheadPass:true})]);
  const tsCtl=g.alexGComputeReplayStats(TA_CTL);
  assert('ERS.T0 (positive control): admitting that same +100R trade moves wins 3->4, win rate 75%->80% and net R +5.5->+105.5 — the ALEX lookahead exclusion above is a real, observed filter',
    tsCtl.wins===4&&tsCtl.winRate===80&&near(tsCtl.netR,105.5)&&tsCtl.invalidatedTrades===0,
    JSON.stringify({wins:tsCtl.wins,winRate:tsCtl.winRate,netR:tsCtl.netR}));

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP H — computeCanonicalPerformance (the one canonical performance calculation)
  // ════════════════════════════════════════════════════════════════════════════════════════
  //
  // DATASET HA at a constant $100 risk:
  //   Win  pnl +250 (resultR +2.5) · Loss pnl -200 (-2.0) · Win pnl +150 (+1.5) · Win pnl +350 (+3.5)
  //
  // HAND-COMPUTED TRUTH:
  //   gross profit  = 250 + 150 + 350 = 750
  //   gross loss    = |-200|          = 200
  //   profit factor = 750 / 200       = 3.75          (inverse 0.2667)
  //   net P&L       = 750 - 200       = +550.00       (a sign flip reports -550.00)
  //   net R         = 2.5 - 2 + 1.5 + 3.5 = +5.5R ; average R = 5.5/4 = 1.375 -> 1.38
  //   win rate      = 3 / 4           = 75%
  const canon=function(o){
    const base={result:'Win',pnl:250,resultR:2.5,riskAmount:100};
    if(o) Object.keys(o).forEach(function(k){ base[k]=o[k]; });
    return base;
  };
  const HA=[
    canon({result:'Win', pnl: 250,resultR: 2.5}),
    canon({result:'Loss',pnl:-200,resultR:-2}),
    canon({result:'Win', pnl: 150,resultR: 1.5}),
    canon({result:'Win', pnl: 350,resultR: 3.5})
  ];
  const hs=g.computeCanonicalPerformance(HA);

  assert('ERS.H3: canonical profit factor is gross profit 750 (250+150+350) over gross loss 200 = 3.75 — the inverse would be 0.27',
    near(hs.profitFactor,3.75)&&near(hs.grossProfit,750)&&near(hs.grossLoss,200),
    JSON.stringify({pf:hs.profitFactor,grossProfit:hs.grossProfit,grossLoss:hs.grossLoss}));

  assert('ERS.H5: canonical net P&L is +550.00 (750 won minus 200 lost) and is POSITIVE — a sign flip would report -550.00 on an account that actually made money',
    hs.netPnl===550&&hs.netPnl>0&&hs.wins===3&&hs.losses===1&&hs.winRate===75,
    JSON.stringify({netPnl:hs.netPnl,wins:hs.wins,losses:hs.losses,winRate:hs.winRate}));

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP E — ledgerDeriveAccountState (the account rebuilt from the immutable ledger)
  // ════════════════════════════════════════════════════════════════════════════════════════
  //
  // DATASET EA — four clean ALEX trades on a $10,000 starting balance, ordered by closedAt:
  //   06 Apr  Win  +$300    balance 10,300   (running peak)
  //   07 Apr  Loss -$200    balance 10,100   <- trough, $200 below the peak
  //   08 Apr  Win  +$150    balance 10,250
  //   09 Apr  Win  +$400    balance 10,650   (new peak)
  //
  // HAND-COMPUTED TRUTH:
  //   wins 3, losses 1, decided 4
  //   win rate           = 3 / 4                  = 75%   (the LOSS rate is 25% — asymmetric on purpose)
  //   realized P&L       = 300 - 200 + 150 + 400  = +650
  //   balance            = 10,000 + 650           = 10,650
  //   gross win / loss   = 850 / 200 ; profit factor 4.25
  //   max money drawdown = 10,300 peak - 10,100 trough = $200   (never 0)
  const LEDGER_ID='AGT|AGS|alex_g_sr_v1|EUR_USD|H1|AGZ|AGC|EUR_USD|H1|low|1774616400000|'+
    'v1775134800000|A_repeatedReaction|AGR|EUR_USD|H1|low|1775430000000';
  const ledWin=function(sfx,pnl,r,closedAt){
    return{tradeId:LEDGER_ID+'|'+sfx,strategy:'alex_g_sr_v1',pair:'EUR_USD',timeframe:'H1',
      direction:'buy',entry:1.15,stop:1.1450,target:1.1600,exitPrice:1.1600,
      result:'Win',resultR:r,pnl:pnl,riskAmount:100,maePips:2,mfePips:50,
      openedAt:'2026-04-06T02:00:00.000Z',closedAt:closedAt,isDeveloperTrade:false,tradeSource:'AUTO'};
  };
  const ledLoss=function(sfx,pnl,r,closedAt){
    return{tradeId:LEDGER_ID+'|'+sfx,strategy:'alex_g_sr_v1',pair:'EUR_USD',timeframe:'H1',
      direction:'buy',entry:1.15,stop:1.1450,target:1.1600,exitPrice:1.1450,
      result:'Loss',resultR:r,pnl:pnl,riskAmount:100,maePips:52,mfePips:1,
      openedAt:'2026-04-06T02:00:00.000Z',closedAt:closedAt,isDeveloperTrade:false,tradeSource:'AUTO'};
  };
  const EA=[
    ledWin ('W1', 300, 3,'2026-04-06T03:00:00.000Z'),
    ledLoss('L1',-200,-2,'2026-04-07T03:00:00.000Z'),
    ledWin ('W2', 150, 1.5,'2026-04-08T03:00:00.000Z'),
    ledWin ('W3', 400, 4,'2026-04-09T03:00:00.000Z')
  ];
  const es=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',records:EA});

  assert('ERS.E1: the derived account states the WIN rate — 3 wins of 4 decided = 75% on an asymmetric 3-1 ledger, where the loss rate is 25%',
    es.winRate===75&&es.wins===3&&es.losses===1&&es.decided===4&&es.eventCounts.excluded===0,
    JSON.stringify({winRate:es.winRate,wins:es.wins,losses:es.losses,excluded:es.eventCounts.excluded}));

  assert('ERS.E3: money drawdown ACCUMULATES to $200 — the balance peaks at $10,300, the -$200 trade drops it to $10,100, and it recovers to $10,650 (derived balance, gross 850/200, PF 4.25)',
    near(es.maxDrawdownMoney,200)&&near(es.balance,10650)&&near(es.realizedPnl,650)&&
    near(es.grossWin,850)&&near(es.grossLoss,200)&&near(es.profitFactor,4.25),
    JSON.stringify({maxDD:es.maxDrawdownMoney,balance:es.balance,realizedPnl:es.realizedPnl,pf:es.profitFactor}));

  // POSITIVE CONTROL for ERS.E3: a ledger that only rises has NO drawdown, so $200 above is being
  // read off the curve rather than matching a constant.
  const EA_UP=[ledWin('U1',300,3,'2026-04-06T03:00:00.000Z'),
               ledWin('U2',150,1.5,'2026-04-07T03:00:00.000Z')];
  const esUp=g.ledgerDeriveAccountState({startingBalance:10000,strategyId:'alex_g_sr_v1',records:EA_UP});
  assert('ERS.E0 (positive control): a ledger of two wins and no losses reports $0 money drawdown, a 100% win rate and a $10,450 balance — both figures above track the data, not a constant',
    near(esUp.maxDrawdownMoney,0)&&esUp.winRate===100&&near(esUp.balance,10450)&&esUp.losses===0,
    JSON.stringify({maxDD:esUp.maxDrawdownMoney,winRate:esUp.winRate,balance:esUp.balance}));

  // ════════════════════════════════════════════════════════════════════════════════════════
  // GROUP D — alexGComputeEquityStats (the chronological R equity walk)
  // ════════════════════════════════════════════════════════════════════════════════════════
  //
  // DATASET DA, chronological: Win +2.5R, Loss -2.0R, Win +1.5R, Win +3.5R.
  //   wins 3, losses 1  (3-1 ON PURPOSE: on a 2-2 or 1-1 set, counting losses instead of wins
  //                      returns the SAME number and the defect is invisible)
  //   equity walk = 2.5 -> 0.5 -> 2.0 -> 5.5 ; peak 2.5 then trough 0.5
  //   net R = +5.5R ; max drawdown = 2.5 - 0.5 = 2.0R ; final equity = +5.5R
  const eqT=function(id,r,when){
    return{tradeId:id,result:r>0?'Win':'Loss',resultR:r,closedAt:when};
  };
  const ds=g.alexGComputeEquityStats([
    eqT('Q1', 2.5,'2026-08-01T00:00:00.000Z'),
    eqT('Q2',-2,  '2026-08-02T00:00:00.000Z'),
    eqT('Q3', 1.5,'2026-08-03T00:00:00.000Z'),
    eqT('Q4', 3.5,'2026-08-04T00:00:00.000Z')
  ]);
  assert('ERS.D6: the equity report counts 3 WINS and 1 LOSS on a deliberately 3-1 set — counting losses as the win figure would report 1, and net R is +5.5R with a 2.0R max drawdown',
    ds.wins===3&&ds.losses===1&&ds.decidedCount===4&&near(ds.netR,5.5)&&
    near(ds.maxDrawdownR,2)&&near(ds.finalEquityR,5.5),
    JSON.stringify({wins:ds.wins,losses:ds.losses,netR:ds.netR,maxDD:ds.maxDrawdownR}));

  // POSITIVE CONTROL for ERS.D6: reverse the lopsidedness (1 win, 3 losses) and the two counts
  // must swap. A win count that tracked losses would report 3 here and 1 above — this pair pins
  // the mapping in both directions.
  const dsInv=g.alexGComputeEquityStats([
    eqT('R1', 2.5,'2026-08-01T00:00:00.000Z'),
    eqT('R2',-2,  '2026-08-02T00:00:00.000Z'),
    eqT('R3',-1.5,'2026-08-03T00:00:00.000Z'),
    eqT('R4',-3.5,'2026-08-04T00:00:00.000Z')
  ]);
  assert('ERS.D0 (positive control): the mirrored 1-win/3-loss set reports wins 1 and losses 3 — the counts follow the data in both directions, so ERS.D6 is not matching a constant',
    dsInv.wins===1&&dsInv.losses===3&&near(dsInv.netR,-4.5),
    JSON.stringify({wins:dsInv.wins,losses:dsInv.losses,netR:dsInv.netR}));

  return results;
}
