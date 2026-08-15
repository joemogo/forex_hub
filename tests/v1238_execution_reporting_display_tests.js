// ══════════════════════════════════════════════════════════════════════════════════════════
// v12.3.8 — EXECUTION REPORTING DISPLAY FIXTURES
//
// THE RENDERED DISPLAY SURFACE: what the operator actually SEES about a real executed trade.
//
// Every fixture below follows one shape:
//     seed isolated in-memory state  ->  call the REAL render function  ->  read the element's
//     innerHTML back out of the stubbed DOM  ->  assert an EXACT rendered string that was
//     computed BY HAND in this file.
//
// RULES THIS FILE OBEYS (each of these anti-patterns has previously produced a fixture that
// passed while the behaviour it claimed to protect was broken):
//   * NO source-text assertions. Nothing here calls getSource() or matches function bodies.
//     A fixture that reads code instead of running it survives every behavioural mutation and
//     dies on cosmetic edits -- it is anti-evidence.
//   * NO self-consistency. A rendered figure is never compared against the same figure
//     recomputed the way the renderer computes it.
//   * NO tautology. Nothing asserts a builtin, or a value this file just wrote unchanged.
//   * NO "covered but wired to nothing". Formatters (fmtRMult/fmtPipsVal/fmtDuration) are
//     never called directly -- they are asserted THROUGH the renderer that must reach them,
//     so deleting the call site fails the fixture too.
//   * NO presence-only / length-only assertions where a sign or an order could be wrong. A
//     flipped sign is still a number and a swapped pair of tiles is still two tiles, so the
//     ACTUAL VALUE of each is asserted.
//
// NO REAL PAPER TRADE IS PERSISTED BY THIS SUITE. All state is in-memory; localStorage and
// fetch are stubs; the process has no access to any real saved data.
// ══════════════════════════════════════════════════════════════════════════════════════════
function runExecutionReportingDisplayFixtures(g){
  const results=[];
  const assert=(name,desc,cond,detail)=>{results.push({name,desc,pass:!!cond,detail:detail||''});};
  const note=(name,desc,detail)=>{results.push({name,desc,pass:null,detail:detail||''});};

  // ── read-back helpers (pure string surgery over rendered HTML -- they never recompute
  //    anything the app computes) ──

  // Value of the stat tile whose <div class="stat-lbl"> is exactly `label`.
  // Both renderPaper()'s tiles and alexGLiveStatCard()'s tiles emit
  //   <div class="stat-val"...>VALUE</div><div class="stat-lbl">LABEL</div>
  function statVal(html,label){
    if(html==null) return null;
    const marker='<div class="stat-lbl">'+label+'</div>';
    const i=html.indexOf(marker);
    if(i<0) return null;
    const before=html.slice(0,i);
    const j=before.lastIndexOf('</div>');
    if(j<0) return null;
    const k=before.lastIndexOf('>',j-1);
    if(k<0) return null;
    return before.slice(k+1,j);
  }
  // The <tr> chunk that contains `token`.
  function rowWith(html,token){
    if(html==null) return null;
    const rows=html.split('<tr>');
    for(let i=1;i<rows.length;i++){ if(rows[i].indexOf(token)!==-1) return rows[i]; }
    return null;
  }
  function rowCount(html){ return html==null?0:html.split('<tr>').length-1-1; } // minus the header <tr>
  // Text of the nth <td> in a row chunk (0-based).
  function cells(rowHtml){
    if(rowHtml==null) return [];
    const out=[];
    const re=/<td[^>]*>([\s\S]*?)<\/td>/g;
    let m;
    while((m=re.exec(rowHtml))!==null) out.push(m[1]);
    return out;
  }
  // Value of the Trade-Inspector row whose label span is exactly `label`.
  // inspectorRows() emits:
  //   <span style="color:var(--text2);font-size:12px">LABEL</span><span style="font-size:12px;text-align:right">VALUE</span>
  function inspectorVal(html,label){
    if(html==null) return null;
    const marker='<span style="color:var(--text2);font-size:12px">'+label+'</span>';
    const i=html.indexOf(marker);
    if(i<0) return null;
    const rest=html.slice(i+marker.length);
    const open='<span style="font-size:12px;text-align:right">';
    if(rest.indexOf(open)!==0) return null;
    const after=rest.slice(open.length);
    const j=after.indexOf('</span>');
    return j<0?null:after.slice(0,j);
  }
  // The compliance checklist row whose title is exactly `title`:
  //   <div class="sc-checklist-title">TITLE</div><div class="sc-checklist-sub">DETAIL</div></div>
  //   <span class="sc-status-pill CLASS">LABEL</span>
  function complianceRow(html,title){
    if(html==null) return null;
    const marker='<div class="sc-checklist-title">'+title+'</div>';
    const i=html.indexOf(marker);
    if(i<0) return null;
    const rest=html.slice(i+marker.length);
    const subOpen='<div class="sc-checklist-sub">';
    if(rest.indexOf(subOpen)!==0) return null;
    const afterSub=rest.slice(subOpen.length);
    const dEnd=afterSub.indexOf('</div>');
    const detail=dEnd<0?null:afterSub.slice(0,dEnd);
    const pillOpen='<span class="sc-status-pill ';
    const p=rest.indexOf(pillOpen);
    if(p<0) return null;
    const afterPill=rest.slice(p+pillOpen.length);
    const q=afterPill.indexOf('">');
    const cls=q<0?null:afterPill.slice(0,q);
    const labEnd=afterPill.indexOf('</span>');
    const label=(q<0||labEnd<0)?null:afterPill.slice(q+2,labEnd);
    return{detail:detail,cls:cls,label:label};
  }
  // The .journal-entry chunk that contains `token` (mini-journal / journal-tab rows).
  function entryWith(html,token){
    if(html==null) return null;
    const parts=html.split('<div class="journal-entry"');
    for(let i=1;i<parts.length;i++){ if(parts[i].indexOf(token)!==-1) return parts[i]; }
    return null;
  }

  function resetAll(){
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setAlexGAccount({balance:10000,startingBalance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGJournalEntries([]);
    g.setPaperResetHistory([]);
    g.setTradeNotes({});
    g.setHideTestTradesPaper(false);
    g.setHideTestTradesAlex(false);
    g.setAlexGLiveSetupStatuses([]);
    g.resetJournalFilters();
    g.clearLocalStorage();
    ['paper-stats','paper-open','paper-closed','paperMiniJournal','paperMiniJournalSummary',
     'alexgLiveStats','alexgLiveClosedTable','alexMiniJournal','alexMiniJournalSummary',
     'journal-list','journal-summary','tradeInspectorPanelBody','tiFullRecordCard',
     'paperTradeInspectorCard'].forEach(g.clearEl);
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // SECTION 1 — JVM PAPER PANEL (renderPaper -> #paper-stats, #paper-closed)
  //
  // HAND-COMPUTED DATASET. Four closed JVM positions, every one with riskAmount $100:
  //   #1 EUR_USD buy  Win         pnl +250  -> Result R +2.50R  PnL +$250.00  source auto -> AUTO
  //   #2 GBP_USD sell Loss        pnl -250  -> Result R -2.50R  PnL -$250.00  no source  -> MANUAL
  //   #3 USD_JPY buy  Win         pnl +100  -> Result R +1.00R  PnL +$100.00  dev trade  -> TEST
  //   #4 AUD_USD buy  Break even  pnl    0  -> Result R +0.00R  PnL   +$0.00  source auto -> AUTO
  // Wins (result==='Win') = 2 of 4 closed  ->  win rate 50%, label "Win rate (4)".
  // Balance 10100 with startBal 10000      ->  Total P&L "+$100.00", Balance "$10100.00".
  // #1 ran 10:00 -> 10:45 (45 min)         ->  Duration "45m".
  // #2 ran 09:00 -> 12:00 (3 h)            ->  Duration "3.0h".
  // ══════════════════════════════════════════════════════════════════════════════════════
  function seedJvmPanel(){
    resetAll();
    g.setPaperAccount({
      balance:10100,
      openPositions:[],
      closedPositions:[
        {id:1,pair:'EUR_USD',oPair:'EUR_USD',dir:'buy',entry:1.10000,stop:1.09800,target:1.10400,
         exitPrice:1.10500,ratio:2.0,riskAmount:100,lots:0.5,pnl:250,result:'Win',source:'auto',
         isDeveloperTrade:false,openedAt:'2026-08-01T10:00:00Z',closedAt:'2026-08-01T10:45:00Z'},
        {id:2,pair:'GBP_USD',oPair:'GBP_USD',dir:'sell',entry:1.25000,stop:1.25200,target:1.24600,
         exitPrice:1.25500,ratio:2.0,riskAmount:100,lots:0.5,pnl:-250,result:'Loss',
         isDeveloperTrade:false,openedAt:'2026-08-01T09:00:00Z',closedAt:'2026-08-01T12:00:00Z'},
        {id:3,pair:'USD_JPY',oPair:'USD_JPY',dir:'buy',entry:150.000,stop:149.800,target:150.400,
         exitPrice:150.100,ratio:2.0,riskAmount:100,lots:0.5,pnl:100,result:'Win',source:'manual',
         isDeveloperTrade:true,openedAt:'2026-08-01T08:00:00Z',closedAt:'2026-08-01T08:30:00Z'},
        {id:4,pair:'AUD_USD',oPair:'AUD_USD',dir:'buy',entry:0.65000,stop:0.64800,target:0.65400,
         exitPrice:0.65000,ratio:2.0,riskAmount:100,lots:0.5,pnl:0,result:'Break even',source:'auto',
         isDeveloperTrade:false,openedAt:'2026-08-01T07:00:00Z',closedAt:'2026-08-01T07:20:00Z'}
      ]
    });
    g.renderPaper();
  }

  try{
    seedJvmPanel();
    const stats=g.elHtml('paper-stats');
    const closed=g.elHtml('paper-closed');

    // J1 -- the win COUNT must not treat "Break even" as a Win. 2 of 4 -> 50%, not 3 of 4 -> 75%.
    assert('J1','JVM paper stats count only result==="Win" as a win -- a Break-even close renders 50% (2/4), never 75%',
      statVal(stats,'Win rate (4)')==='50%' && stats.indexOf('75%')===-1,
      'rendered win-rate tile = '+JSON.stringify(statVal(stats,'Win rate (4)')));

    // J2 -- the win RATE is a percentage, not a per-mille. 50%, not 500%.
    assert('J2','JVM paper stats render the win rate as exactly "50%" for 2 wins in 4 closed trades -- not 500%',
      statVal(stats,'Win rate (4)')==='50%' && stats.indexOf('500%')===-1,
      'rendered win-rate tile = '+JSON.stringify(statVal(stats,'Win rate (4)')));

    // J3 -- "Total P&L" is balance MINUS the starting balance, not the raw balance.
    assert('J3','JVM "Total P&L" tile renders +$100.00 (balance 10100 less the 10000 start), not the raw balance +$10100.00',
      statVal(stats,'Total P&L')==='+$100.00' && statVal(stats,'Balance')==='$10100.00',
      'Total P&L tile = '+JSON.stringify(statVal(stats,'Total P&L'))+', Balance tile = '+JSON.stringify(statVal(stats,'Balance')));

    // J4 -- the starting balance really is 10000. If it were 0 the same tile would read +$10100.00.
    assert('J4','JVM starting balance of 10000 is what "Total P&L" subtracts -- a zeroed start would render +$10100.00 instead of +$100.00',
      statVal(stats,'Total P&L')==='+$100.00',
      'Total P&L tile = '+JSON.stringify(statVal(stats,'Total P&L')));

    // J5 -- closed-table "Result R" carries the trade's own sign. A LOSS reads -2.50R.
    const rowLoss=rowWith(closed,'GBP_USD');
    const rowWin=rowWith(closed,'EUR_USD');
    // (fmtCurrency renders a negative as "$-250.00" -- the sign sits after the dollar sign.)
    assert('J5','JVM closed table renders Result R with the trade\'s own sign: the -$250 loss reads "-2.50R" and the +$250 win reads "+2.50R"',
      cells(rowLoss)[9]==='-2.50R' && cells(rowWin)[9]==='+2.50R' &&
      cells(rowLoss)[10]==='$-250.00' && cells(rowWin)[10]==='+$250.00',
      'loss Result R = '+JSON.stringify(cells(rowLoss)[9])+', win Result R = '+JSON.stringify(cells(rowWin)[9]));

    // J6 -- every closed trade is listed, not just the first. All four rows, each by its own value.
    assert('J6','JVM closed table lists all four closed trades -- the 4th row (AUD_USD, +0.00R) is rendered, not truncated away',
      rowCount(closed)===4 &&
      cells(rowWith(closed,'AUD_USD'))[9]==='+0.00R' &&
      cells(rowWith(closed,'USD_JPY'))[9]==='+1.00R' &&
      cells(rowWith(closed,'GBP_USD'))[9]==='-2.50R' &&
      cells(rowWith(closed,'EUR_USD'))[9]==='+2.50R',
      'rows rendered = '+rowCount(closed));

    // J7 -- with the display filter OFF (its default), a developer TEST trade is still shown.
    assert('J7','JVM closed table shows developer test trades while hideTestTradesPaper is false -- the USD_JPY TEST row renders with its own +1.00R',
      rowWith(closed,'USD_JPY')!==null && cells(rowWith(closed,'USD_JPY'))[9]==='+1.00R' &&
      statVal(stats,'Win rate (4)')==='50%',
      'USD_JPY row present = '+(rowWith(closed,'USD_JPY')!==null));

    // J8 -- the trade-source column reports the trade's real provenance, not a constant.
    assert('J8','JVM closed table renders the real trade source per row: AUTO for an auto trade, MANUAL for a manual one, TEST for a developer trade',
      cells(rowWith(closed,'EUR_USD'))[17]==='AUTO' &&
      cells(rowWith(closed,'GBP_USD'))[17]==='MANUAL' &&
      cells(rowWith(closed,'USD_JPY'))[17]==='TEST',
      'sources = '+JSON.stringify([cells(rowWith(closed,'EUR_USD'))[17],cells(rowWith(closed,'GBP_USD'))[17],cells(rowWith(closed,'USD_JPY'))[17]]));

    // R3 (through renderPaper) -- fmtDuration must render minutes/hours at real scale.
    // 45 minutes is "45m"; 3 hours is "3.0h". A 60x error renders "45.0h" / "180.0h".
    assert('R3a','fmtDuration reached through the JVM closed table renders 2 700 000 ms as "45m" and 10 800 000 ms as "3.0h" -- not 60x larger',
      cells(rowWith(closed,'EUR_USD'))[13]==='45m' && cells(rowWith(closed,'GBP_USD'))[13]==='3.0h',
      'durations = '+JSON.stringify([cells(rowWith(closed,'EUR_USD'))[13],cells(rowWith(closed,'GBP_USD'))[13]]));

    // R1 (through renderPaper) -- fmtRMult must not sign-flip.
    assert('R1a','fmtRMult reached through the JVM closed table renders a losing trade as "-2.50R" and a winning trade as "+2.50R"',
      cells(rowWith(closed,'GBP_USD'))[9]==='-2.50R' && cells(rowWith(closed,'EUR_USD'))[9]==='+2.50R',
      'R values = '+JSON.stringify([cells(rowWith(closed,'GBP_USD'))[9],cells(rowWith(closed,'EUR_USD'))[9]]));
  }catch(e){
    assert('SECTION-1','JVM paper panel fixtures executed without throwing',false,String(e&&e.message||e));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // SECTION 2 — ALEX LIVE PANEL (renderAlexGLivePanel -> #alexgLiveStats,
  //                              renderAlexGLiveClosedTable -> #alexgLiveClosedTable)
  //
  // HAND-COMPUTED DATASET. Starting balance 10000. Four stored closed positions; the fourth
  // carries a hand-written trade id ('AGT|MANUAL-B|9') that the ALEX engine cannot mint, so
  // TI_TRADE_ID_ENGINE_MINTED quarantines it. Nothing else violates any integrity rule.
  //
  //   T1 EUR_USD buy  Win   entry 1.10000 stop 1.09800 exit 1.10600 -> realized R +3.0  pnl +300
  //   T2 GBP_USD buy  Loss  entry 1.20000 stop 1.19800 exit 1.19800 -> realized R -1.0  pnl -100
  //   T3 USD_CHF sell Loss  entry 1.30000 stop 1.30200 exit 1.30200 -> realized R -1.0  pnl -100
  //   T4 AUD_USD buy  Win   QUARANTINED                             -> realized R +5.0  pnl +500
  //
  //   Statistics run over T1..T3 only:
  //     Closed positions = 3      Wins = 1      Losses = 2      Win rate = round(1/3*100) = 33%
  //     Net R (realized) = +3.0 -1.0 -1.0 = "+1.00R"
  //   Equity walk is chronological by closedAt (T2 -> T3 -> T1):
  //     equity -1 (peak 0, dd 1) -> -2 (dd 2) -> +1 (new peak, dd 0)
  //     Current drawdown = "0.00R"        Max drawdown = "2.00R"      <- deliberately different
  //   Stored balance includes the quarantined trade: 10000+300-100-100+500 = 10600
  //     Alex balance tile = "$10600.00"
  //     P&L tile nets the quarantined +500 back out: 10600-10000-500 = "+$100.00"
  // ══════════════════════════════════════════════════════════════════════════════════════
  const AGID='AGT|AGS|alex_g_sr_v1|';
  function alexClosed(){
    return [
      {tradeId:AGID+'EUR_USD|1',pair:'EUR_USD',timeframe:'15M',setupLabel:'Support bounce',direction:'buy',
       entry:1.10000,stop:1.09800,target:1.10600,exitPrice:1.10600,result:'Win',resultR:3,pnl:300,
       maePips:4,mfePips:60,plannedRR:3,riskAmount:100,positionSize:0.5,
       openedAt:'2026-08-03T09:00:00Z',closedAt:'2026-08-03T12:00:00Z',
       exitDetectionSource:'live_snapshot',ambiguous:false,isDeveloperTrade:false},
      {tradeId:AGID+'GBP_USD|2',pair:'GBP_USD',timeframe:'15M',setupLabel:'Support bounce',direction:'buy',
       entry:1.20000,stop:1.19800,target:1.20600,exitPrice:1.19800,result:'Loss',resultR:-1,pnl:-100,
       maePips:20,mfePips:3,plannedRR:3,riskAmount:100,positionSize:0.5,
       openedAt:'2026-08-01T09:00:00Z',closedAt:'2026-08-01T12:00:00Z',
       exitDetectionSource:'historical_candle',ambiguous:false,isDeveloperTrade:false},
      {tradeId:AGID+'USD_CHF|3',pair:'USD_CHF',timeframe:'1H',setupLabel:'Resistance rejection',direction:'sell',
       entry:1.30000,stop:1.30200,target:1.29400,exitPrice:1.30200,result:'Loss',resultR:-1,pnl:-100,
       maePips:20,mfePips:2,plannedRR:3,riskAmount:100,positionSize:0.5,
       openedAt:'2026-08-02T09:00:00Z',closedAt:'2026-08-02T12:00:00Z',
       exitDetectionSource:'developer_test',ambiguous:true,isDeveloperTrade:false},
      {tradeId:'AGT|MANUAL-B|9',pair:'AUD_USD',timeframe:'15M',setupLabel:'zB rB',direction:'buy',
       entry:1.40000,stop:1.39800,target:1.41000,exitPrice:1.41000,result:'Win',resultR:5,pnl:500,
       maePips:3,mfePips:100,plannedRR:5,riskAmount:100,positionSize:0.5,
       openedAt:'2026-08-04T09:00:00Z',closedAt:'2026-08-04T12:00:00Z',
       exitDetectionSource:'historical_candle',ambiguous:false,isDeveloperTrade:false}
    ];
  }
  function seedAlexPanel(){
    resetAll();
    g.setAlexGAccount({balance:10600,startingBalance:10000,openPositions:[],closedPositions:alexClosed()});
    g.renderAlexGLivePanel();
  }

  try{
    seedAlexPanel();
    const st=g.elHtml('alexgLiveStats');
    const tbl=g.elHtml('alexgLiveClosedTable');

    // K1 -- the "Win rate" tile reports the WIN rate. 1 win of 3 decided = 33%; the loss rate is 67%.
    assert('K1','ALEX "Win rate" tile renders 33% for 1 win in 3 decided trades -- not the 67% loss rate',
      statVal(st,'Win rate')==='33%' && st.indexOf('67%')===-1,
      'Win rate tile = '+JSON.stringify(statVal(st,'Win rate'))+', Wins tile = '+JSON.stringify(statVal(st,'Wins'))+', Losses tile = '+JSON.stringify(statVal(st,'Losses')));

    // K4 -- "Max drawdown" is the worst peak-to-trough over the whole curve (2.00R), which this
    //       dataset deliberately makes DIFFERENT from the current drawdown (0.00R).
    assert('K4','ALEX "Max drawdown" tile renders the worst peak-to-trough 2.00R while "Current drawdown" renders 0.00R -- the two tiles are not the same figure',
      statVal(st,'Max drawdown')==='2.00R' && statVal(st,'Current drawdown')==='0.00R',
      'Max = '+JSON.stringify(statVal(st,'Max drawdown'))+', Current = '+JSON.stringify(statVal(st,'Current drawdown')));

    // K2 -- the displayed P&L nets the quarantined trade's +$500 back out of the stored balance.
    assert('K2','ALEX "P&L" tile renders +$100.00 -- the quarantined trade\'s +$500 is netted out of the stored 10600 balance, which itself still renders as $10600.00',
      statVal(st,'P&L')==='+$100.00' && statVal(st,'Alex balance')==='$10600.00',
      'P&L tile = '+JSON.stringify(statVal(st,'P&L'))+', balance tile = '+JSON.stringify(statVal(st,'Alex balance')));

    // K3 -- quarantined records are excluded from EVERY panel statistic. This is the real
    //       behavioural replacement for the source-text fixture that previously "covered" it.
    assert('K3','ALEX panel statistics exclude the quarantined trade: Closed positions 3 (not 4), Wins 1 (not 2), Win rate 33% (not 50%), Net R +1.00R (not +6.00R)',
      statVal(st,'Closed positions')==='3' && statVal(st,'Wins')==='1' &&
      statVal(st,'Losses')==='2' && statVal(st,'Win rate')==='33%' &&
      statVal(st,'Net R (realized)')==='+1.00R',
      'closed='+JSON.stringify(statVal(st,'Closed positions'))+' wins='+JSON.stringify(statVal(st,'Wins'))+
      ' netR='+JSON.stringify(statVal(st,'Net R (realized)')));

    // L1 -- the quarantined record is still LISTED, and it carries the red QUARANTINED badge.
    //       Excluded from the statistics, never hidden from an investigator.
    const rowQ=rowWith(tbl,'1.41000');
    const rowT1=rowWith(tbl,'1.10600');
    assert('L1','ALEX closed table renders the QUARANTINED badge on the quarantined row only -- the clean EUR_USD row carries no such badge',
      rowQ!==null && rowQ.indexOf('>QUARANTINED</span>')!==-1 &&
      rowT1!==null && rowT1.indexOf('QUARANTINED')===-1,
      'quarantined row badged = '+(rowQ?rowQ.indexOf('>QUARANTINED</span>')!==-1:'row missing'));

    // L3 -- closed-table "Result R" carries the trade's own sign.
    assert('L3','ALEX closed table renders Result R with the trade\'s own sign: the winning row reads "+3.00R" and each losing row reads "-1.00R"',
      cells(rowT1)[9]==='+3.00R' && cells(rowWith(tbl,'1.19800'))[9]==='-1.00R' &&
      cells(rowT1)[10]==='+$300.00',
      'win R = '+JSON.stringify(cells(rowT1)[9])+', loss R = '+JSON.stringify(cells(rowWith(tbl,'1.19800'))[9]));

    // L4 -- the ambiguous-exit warning is rendered on the ambiguous row and nowhere else.
    const rowAmb=rowWith(tbl,'1.30200');
    assert('L4','ALEX closed table renders the "⚠ AMBIGUOUS" exit warning on the ambiguous USD_CHF row and not on the unambiguous EUR_USD row',
      rowAmb!==null && cells(rowAmb)[16].indexOf('⚠ AMBIGUOUS')!==-1 &&
      cells(rowT1)[16].indexOf('AMBIGUOUS')===-1,
      'ambiguous cell = '+JSON.stringify(rowAmb?cells(rowAmb)[16]:null));

    // L5 -- exit provenance is the trade's own recorded source, not a constant "Historical candle".
    assert('L5','ALEX closed table renders each trade\'s real exit provenance: "Live snapshot", "Historical candle" and "Developer test" -- never one constant label',
      cells(rowT1)[16]==='Live snapshot' &&
      cells(rowWith(tbl,'1.19800'))[16]==='Historical candle' &&
      cells(rowAmb)[16].indexOf('Developer test')===0,
      'provenance cells = '+JSON.stringify([cells(rowT1)[16],cells(rowWith(tbl,'1.19800'))[16],cells(rowAmb)[16]]));

    // R1 (through the ALEX table) -- fmtRMult must not sign-flip here either.
    assert('R1b','fmtRMult reached through the ALEX closed table renders "-1.00R" for a losing trade and "+3.00R" for a winning one',
      cells(rowWith(tbl,'1.19800'))[9]==='-1.00R' && cells(rowT1)[9]==='+3.00R',
      'R values = '+JSON.stringify([cells(rowWith(tbl,'1.19800'))[9],cells(rowT1)[9]]));
  }catch(e){
    assert('SECTION-2','ALEX live panel fixtures executed without throwing',false,String(e&&e.message||e));
  }

  // L2 -- the closed table is not truncated to a handful of rows. Its own dataset: seven clean
  //       closed trades, and the SEVENTH is asserted by its own exit price and Result R.
  try{
    resetAll();
    const many=[];
    for(let i=1;i<=7;i++){
      const exit=1.10000+i*0.001;              // 1.10100 .. 1.10700, each row uniquely findable
      many.push({tradeId:AGID+'EUR_USD|'+i,pair:'EUR_USD',timeframe:'15M',setupLabel:'Support bounce',
        direction:'buy',entry:1.10000,stop:1.09800,target:1.11000,exitPrice:exit,result:'Win',
        resultR:i/2,pnl:i*50,maePips:2,mfePips:20+i,plannedRR:5,riskAmount:100,positionSize:0.5,
        openedAt:'2026-08-0'+i+'T09:00:00Z',closedAt:'2026-08-0'+i+'T12:00:00Z',
        exitDetectionSource:'historical_candle',ambiguous:false,isDeveloperTrade:false});
    }
    g.setAlexGAccount({balance:11400,startingBalance:10000,openPositions:[],closedPositions:many});
    g.renderAlexGLiveClosedTable();
    const t7=g.elHtml('alexgLiveClosedTable');
    const r7=rowWith(t7,'1.10700');
    assert('L2','ALEX closed table lists all seven closed trades -- the 7th row renders with its own exit 1.10700 and Result R "+3.50R", not truncated away',
      rowCount(t7)===7 && r7!==null && cells(r7)[9]==='+3.50R' && cells(r7)[5]==='1.10700',
      'rows rendered = '+rowCount(t7)+', 7th Result R = '+JSON.stringify(r7?cells(r7)[9]:null));
  }catch(e){
    assert('L2','ALEX closed table lists all seven closed trades',false,String(e&&e.message||e));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // SECTION 3 — MINI-JOURNALS AND THE JOURNAL TAB
  //
  // REACHABILITY FIRST. Building this section surfaced the reason every mini-journal mutation
  // had survived: the mutated code was UNREACHABLE. renderPaperMiniJournal() filtered on the
  // display label 'JVM' (and renderMiniJournal() on 'ALEX'), but since v12.3.2
  // getFilteredJournalRecords() matches filters.strategy against r.strategyId -- the stable
  // registry id, 'current_strategy'/'alex_g_sr_v1' -- so no real record ever matched and both
  // mini-journals rendered "No trades yet." permanently. That was fixed at the call sites in
  // v12.26.0 (§18.11). M0 below is the regression fixture for that fix, and every fixture in
  // this section now drives PRODUCTION-SHAPED records (strategyId 'current_strategy' /
  // 'alex_g_sr_v1') -- the exact records the engines actually mint. If the mini-journals ever
  // go blank again, M0 fails first and M1-M5 fail with it.
  // ══════════════════════════════════════════════════════════════════════════════════════
  try{
    resetAll();
    g.setJournalEntries([
      {journalEntryId:'JVMJ|701',tradeId:701,strategy:'current_strategy',strategyId:'current_strategy',
       strategyLabel:'JVM',tradeSource:'AUTO',pair:'EUR_USD',direction:'buy',status:'CLOSED',
       result:'Win',resultR:2.5,pnl:250,riskAmount:100,entry:1.1,stop:1.098,target:1.104,
       openedAt:'2026-08-01T10:00:00Z',closedAt:'2026-08-01T10:45:00Z'}
    ]);
    g.renderPaperMiniJournal();
    const mj=g.elHtml('paperMiniJournal');
    // M0 -- a record shaped exactly as buildJVMJournalOpenRecord() mints it (strategyId
    //       'current_strategy', strategyLabel 'JVM') must actually REACH the JVM mini-journal.
    assert('M0','JVM mini-journal renders a production-shaped record (strategyId "current_strategy") instead of the "No trades yet." empty state -- the v12.26.0 §18.11 label/id regression stays closed',
      mj.indexOf('No trades yet.')===-1 && mj.indexOf('EUR_USD')!==-1 &&
      g.elText('paperMiniJournalSummary')==='1 trade · 1W/0L',
      'rendered summary = '+JSON.stringify(g.elText('paperMiniJournalSummary')));
  }catch(e){
    assert('M0','JVM mini-journal renders a production-shaped record',false,String(e&&e.message||e));
  }

  // HAND-COMPUTED MINI-JOURNAL DATASET (four JVM rows, one of them an OPEN position that the
  // live paperAccount still holds, so its class badge must read "Active position"):
  //   #701 EUR_USD Win   resultR +2.5 -> "+2.50R"
  //   #702 GBP_USD Loss  resultR -2.5 -> "-2.50R"
  //   #703 USD_JPY Win   resultR +1.0 -> "+1.00R"
  //   #704 AUD_USD OPEN  (held in paperAccount.openPositions)
  //   summary: 4 records, 3 closed, 2 wins, 1 loss -> "4 trades · 2W/1L"
  function miniRecords(sid){
    return [
      {journalEntryId:'JVMJ|701',tradeId:701,strategy:sid,strategyId:sid,strategyLabel:'JVM',
       tradeSource:'AUTO',pair:'EUR_USD',direction:'buy',status:'CLOSED',result:'Win',resultR:2.5,
       pnl:250,riskAmount:100,openedAt:'2026-08-04T10:00:00Z',closedAt:'2026-08-04T10:45:00Z'},
      {journalEntryId:'JVMJ|702',tradeId:702,strategy:sid,strategyId:sid,strategyLabel:'JVM',
       tradeSource:'AUTO',pair:'GBP_USD',direction:'sell',status:'CLOSED',result:'Loss',resultR:-2.5,
       pnl:-250,riskAmount:100,openedAt:'2026-08-03T10:00:00Z',closedAt:'2026-08-03T10:45:00Z'},
      {journalEntryId:'JVMJ|703',tradeId:703,strategy:sid,strategyId:sid,strategyLabel:'JVM',
       tradeSource:'AUTO',pair:'USD_JPY',direction:'buy',status:'CLOSED',result:'Win',resultR:1.0,
       pnl:100,riskAmount:100,openedAt:'2026-08-02T10:00:00Z',closedAt:'2026-08-02T10:45:00Z'},
      {journalEntryId:'JVMJ|704',tradeId:704,strategy:sid,strategyId:sid,strategyLabel:'JVM',
       tradeSource:'AUTO',pair:'AUD_USD',direction:'buy',status:'OPEN',result:null,resultR:null,
       pnl:null,riskAmount:100,openedAt:'2026-08-01T10:00:00Z',closedAt:null}
    ];
  }

  try{
    resetAll();
    g.setPaperAccount({balance:10100,openPositions:[{id:704,pair:'AUD_USD',oPair:'AUD_USD'}],closedPositions:[]});
    g.setJournalEntries(miniRecords('current_strategy'));
    g.renderPaperMiniJournal();
    const mj=g.elHtml('paperMiniJournal');
    const sum=g.elText('paperMiniJournalSummary');

    // M1 -- the class badge is the record's REAL account relationship, not a constant.
    //       #704 is held open by paperAccount, so it is an "Active position", not a "Manual entry".
    const eOpen=entryWith(mj,'AUD_USD');
    const eWin=entryWith(mj,'EUR_USD');
    assert('M1','JVM mini-journal badges the still-open #704 as "Active position" -- every row is not labelled "Manual entry"',
      eOpen!==null && eOpen.indexOf('>Active position</span>')!==-1 && mj.indexOf('Manual entry')===-1,
      'badge present = '+(eOpen?eOpen.indexOf('>Active position</span>')!==-1:'row missing'));

    // M2 -- the result label is rendered on each row.
    assert('M2','JVM mini-journal renders each row\'s result label: "Win" on #701, "Loss" on #702, and the "OPEN" status on the unresolved #704',
      eWin!==null && eWin.indexOf('>Win</span>')!==-1 &&
      entryWith(mj,'GBP_USD').indexOf('>Loss</span>')!==-1 &&
      eOpen.indexOf('>OPEN</span>')!==-1,
      'labels found = '+JSON.stringify([eWin?eWin.indexOf('>Win</span>')!==-1:null,eOpen.indexOf('>OPEN</span>')!==-1]));

    // M3 -- per-row R carries the record's own sign.
    assert('M3','JVM mini-journal renders per-row R with the record\'s own sign: "-2.50R" on the loss and "+2.50R" on the win',
      entryWith(mj,'GBP_USD').indexOf('<span>-2.50R</span>')!==-1 &&
      eWin.indexOf('<span>+2.50R</span>')!==-1,
      'row R strings present = '+JSON.stringify([entryWith(mj,'GBP_USD').indexOf('<span>-2.50R</span>')!==-1,eWin.indexOf('<span>+2.50R</span>')!==-1]));

    // M4 -- the W/L summary counts wins as wins.
    assert('M4','JVM mini-journal summary renders "4 trades · 2W/1L" -- wins counted as wins, not losses counted as wins',
      sum==='4 trades · 2W/1L',
      'summary = '+JSON.stringify(sum));

    // M8 (mini-journal half) -- Win renders green and Loss renders red, not inverted.
    assert('M8a','JVM mini-journal colours the "Win" label var(--green) and the "Loss" label var(--red) -- not inverted',
      eWin.indexOf('<span style="color:var(--green);font-weight:600">Win</span>')!==-1 &&
      entryWith(mj,'GBP_USD').indexOf('<span style="color:var(--red);font-weight:600">Loss</span>')!==-1,
      'colour spans present');
  }catch(e){
    assert('SECTION-3A','JVM mini-journal fixtures executed without throwing',false,String(e&&e.message||e));
  }

  // M5 -- the SHARED mini-journal (renderMiniJournal, reached through renderAlexGLiveClosedTable)
  //       has its own W/L summary. Three ALEX records: 2 wins, 1 loss -> "3 trades · 2W/1L".
  try{
    resetAll();
    g.setAlexGAccount({balance:10600,startingBalance:10000,openPositions:[],closedPositions:alexClosed()});
    g.setAlexGJournalEntries([
      {journalEntryId:'ALEXJ|A1',tradeId:'A1',strategy:'alex_g_sr_v1',strategyId:'alex_g_sr_v1',strategyLabel:'ALEX',
       tradeSource:'AUTO',pair:'EUR_USD',timeframe:'15M',setupLabel:'Support bounce',direction:'buy',
       status:'CLOSED',result:'Win',resultR:3,pnl:300,riskAmount:100,
       openedAt:'2026-08-03T09:00:00Z',closedAt:'2026-08-03T12:00:00Z'},
      {journalEntryId:'ALEXJ|A2',tradeId:'A2',strategy:'alex_g_sr_v1',strategyId:'alex_g_sr_v1',strategyLabel:'ALEX',
       tradeSource:'AUTO',pair:'GBP_USD',timeframe:'15M',setupLabel:'Support bounce',direction:'buy',
       status:'CLOSED',result:'Loss',resultR:-1,pnl:-100,riskAmount:100,
       openedAt:'2026-08-01T09:00:00Z',closedAt:'2026-08-01T12:00:00Z'},
      {journalEntryId:'ALEXJ|A3',tradeId:'A3',strategy:'alex_g_sr_v1',strategyId:'alex_g_sr_v1',strategyLabel:'ALEX',
       tradeSource:'AUTO',pair:'USD_CHF',timeframe:'1H',setupLabel:'Resistance rejection',direction:'sell',
       status:'CLOSED',result:'Win',resultR:2,pnl:200,riskAmount:100,
       openedAt:'2026-08-02T09:00:00Z',closedAt:'2026-08-02T12:00:00Z'}
    ]);
    g.renderAlexGLiveClosedTable();   // the wired path: the closed table renders, then calls renderMiniJournal
    const sum=g.elText('alexMiniJournalSummary');
    const list=g.elHtml('alexMiniJournal');
    assert('M5','Shared mini-journal summary (reached through renderAlexGLiveClosedTable) renders "3 trades · 2W/1L" -- wins counted as wins',
      sum==='3 trades · 2W/1L' &&
      entryWith(list,'GBP_USD').indexOf('<span>-1.00R</span>')!==-1,
      'summary = '+JSON.stringify(sum));
  }catch(e){
    assert('M5','Shared mini-journal summary renders 2W/1L',false,String(e&&e.message||e));
  }

  // M6/M7/M8 -- the unified Journal tab (renderJournal -> renderJournalRecordRows -> #journal-list).
  // This path is reached with production-shaped records: the default 'All' filter does not hit
  // the strategyId/label mismatch above.
  try{
    resetAll();
    g.setJournalEntries(miniRecords('current_strategy'));
    g.renderJournal();
    const list=g.elHtml('journal-list');
    const eWin=entryWith(list,'EUR_USD');
    const eLoss=entryWith(list,'GBP_USD');

    // M6 -- the result label is rendered on each Journal-tab row.
    assert('M6','Journal tab renders each row\'s result label -- "Win" on #701, "Loss" on #702, "OPEN" on the unresolved #704',
      eWin!==null && eWin.indexOf('>Win</span>')!==-1 &&
      eLoss.indexOf('>Loss</span>')!==-1 &&
      entryWith(list,'AUD_USD').indexOf('>OPEN</span>')!==-1,
      'labels rendered');

    // M7 -- Journal-tab per-row R carries the record's own sign.
    assert('M7','Journal tab renders per-row R with the record\'s own sign: "-2.50R" on the loss and "+2.50R" on the win',
      eLoss.indexOf('<span>-2.50R</span>')!==-1 && eWin.indexOf('<span>+2.50R</span>')!==-1,
      'row R strings present');

    // M8 -- Win green / Loss red, not inverted.
    assert('M8b','Journal tab colours the "Win" label var(--green) and the "Loss" label var(--red) -- not inverted',
      eWin.indexOf('<span style="color:var(--green);font-weight:600">Win</span>')!==-1 &&
      eLoss.indexOf('<span style="color:var(--red);font-weight:600">Loss</span>')!==-1,
      'colour spans present');
  }catch(e){
    assert('SECTION-3C','Journal tab fixtures executed without throwing',false,String(e&&e.message||e));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════
  // SECTION 4 — TRADE INSPECTOR (renderTradeInspectorPanel -> #tradeInspectorPanelBody and,
  //             through it, renderTiMetrics / renderTiCompliance / renderTiTimeline plus
  //             renderTradeInspectorContent -> #tiFullRecordCard)
  //
  // HAND-COMPUTED RECORD. One closed JVM loss:
  //   entry 1.10000  stop 1.09800  exit 1.09500  riskAmount $100  plannedRR 1.5
  //   pnl -250  resultR -2.5  maePips 12.3  mfePips 40  opened 10:00 closed 10:45
  //   closeReason 'STOP_LOSS'    exitDetectionSource 'historical_candle'
  // Expected rendered values:
  //   Exit section   -> Result R "-2.50R"   PnL "-$250.00"   Close reason "STOP_LOSS"
  //                     Exit detected "historical_candle"
  //   Metrics tiles  -> MAE "12.3p"  MFE "40.0p"  Result R "-2.50R"  PnL "-$250.00"  Duration "45m"
  //   Compliance     -> "Minimum 1:2 reward-to-risk" is a FAIL at 1.50:1
  //   Timeline       -> "Trade closed (Loss)"
  // ══════════════════════════════════════════════════════════════════════════════════════
  try{
    resetAll();
    g.setJournalEntries([{
      journalEntryId:'JVMJ|801',tradeId:801,strategy:'current_strategy',strategyId:'current_strategy',
      strategyLabel:'JVM',tradeSource:'AUTO',isDeveloperTrade:false,
      pair:'EUR_USD',timeframe:'15M',setupType:null,setupLabel:null,direction:'buy',
      entry:1.10000,stop:1.09800,target:1.10400,plannedRR:1.5,riskPercent:1.0,riskAmount:100,positionSize:0.5,
      openedAt:'2026-08-01T10:00:00Z',closedAt:'2026-08-01T10:45:00Z',exitPrice:1.09500,
      result:'Loss',resultR:-2.5,pnl:-250,maePips:12.3,mfePips:40,maeR:null,mfeR:null,
      status:'CLOSED',exitDetectionSource:'historical_candle',closeReason:'STOP_LOSS',durationMs:2700000
    }]);
    g.renderTradeInspectorPanel('JVMJ|801');
    const panel=g.elHtml('tradeInspectorPanelBody');
    const full=g.elHtml('tiFullRecordCard');

    // P1 -- the Exit section's PnL carries the trade's own sign.
    assert('P1','Trade Inspector Exit section renders PnL "$-250.00" and Result R "-2.50R" for a losing trade -- signs not flipped',
      inspectorVal(full,'PnL')==='$-250.00' && inspectorVal(full,'Result R')==='-2.50R',
      'PnL row = '+JSON.stringify(inspectorVal(full,'PnL'))+', Result R row = '+JSON.stringify(inspectorVal(full,'Result R')));

    // P2 -- "Close reason" and "Exit detected" are two distinct fields with two distinct values.
    assert('P2','Trade Inspector renders "Close reason" as STOP_LOSS and "Exit detected" as historical_candle -- the close reason is not the exit-detection source',
      inspectorVal(full,'Close reason')==='STOP_LOSS' &&
      inspectorVal(full,'Exit detected')==='historical_candle',
      'Close reason = '+JSON.stringify(inspectorVal(full,'Close reason'))+', Exit detected = '+JSON.stringify(inspectorVal(full,'Exit detected')));

    // P3 -- the MAE and MFE tiles are not swapped.
    assert('P3','Trade Inspector metrics render MAE "12.3p" and MFE "40.0p" in their own tiles -- the two excursions are not swapped',
      statVal(panel,'MAE')==='12.3p' && statVal(panel,'MFE')==='40.0p',
      'MAE tile = '+JSON.stringify(statVal(panel,'MAE'))+', MFE tile = '+JSON.stringify(statVal(panel,'MFE')));

    // P4 -- the PnL tile shows the P&L, not the risk amount.
    assert('P4','Trade Inspector PnL tile renders "$-250.00" (the realized P&L), not "+$100.00" (the risk amount)',
      statVal(panel,'PnL')==='$-250.00' && statVal(panel,'Result R')==='-2.50R',
      'PnL tile = '+JSON.stringify(statVal(panel,'PnL')));

    // P5 -- the 1:2 R:R compliance check really fails at 1.50:1.
    const rr=complianceRow(panel,'Minimum 1:2 reward-to-risk');
    assert('P5','Trade Inspector strategy compliance renders the "Minimum 1:2 reward-to-risk" check as Fail at 1.50:1 -- the check does not always pass',
      rr!==null && rr.detail==='1.50:1 planned' && rr.cls==='fail' && rr.label==='Fail',
      'compliance row = '+JSON.stringify(rr));

    // P6 -- the timeline's close event names the result.
    assert('P6','Trade Inspector decision timeline renders the close event as "Trade closed (Loss)" -- the result is not dropped from the label',
      panel.indexOf('<div class="ti-timeline-label">Trade closed (Loss)</div>')!==-1,
      'timeline close label present');

    // R1 (through the Trade Inspector) -- fmtRMult, sign intact.
    assert('R1c','fmtRMult reached through the Trade Inspector metrics tile renders "-2.50R" for a -2.5R trade',
      statVal(panel,'Result R')==='-2.50R',
      'Result R tile = '+JSON.stringify(statVal(panel,'Result R')));

    // R3 (through the Trade Inspector) -- fmtDuration, real scale.
    assert('R3b','fmtDuration reached through the Trade Inspector renders 2 700 000 ms as "45m" in both the metrics tile and the Timeline row',
      statVal(panel,'Duration')==='45m' && inspectorVal(full,'Duration')==='45m',
      'Duration tile = '+JSON.stringify(statVal(panel,'Duration'))+', Duration row = '+JSON.stringify(inspectorVal(full,'Duration')));

    // R4 (through the Trade Inspector) -- fmtPipsVal, sign intact.
    assert('R4','fmtPipsVal reached through the Trade Inspector renders MAE "12.3p" and MFE "40.0p" -- signs not flipped to "-12.3p"/"-40.0p"',
      statVal(panel,'MAE')==='12.3p' && statVal(panel,'MFE')==='40.0p' &&
      inspectorVal(full,'MAE')==='12.3p' && inspectorVal(full,'MFE')==='40.0p',
      'MAE/MFE tiles = '+JSON.stringify([statVal(panel,'MAE'),statVal(panel,'MFE')])+
      ', MAE/MFE rows = '+JSON.stringify([inspectorVal(full,'MAE'),inspectorVal(full,'MFE')]));
  }catch(e){
    assert('SECTION-4','Trade Inspector fixtures executed without throwing',false,String(e&&e.message||e));
  }

  resetAll();
  return results;
}
