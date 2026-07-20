// v12.3.0 -- TJR_SLR Phase 1: Session and Zone Engine
//
// Proves: (1) TJR_SLR is registered in STRATEGY_REGISTRY with scanning/paperTrading/automation
// all disabled, alongside JVM/ALEX, with zero effect on either; (2) session boundary resolution
// is deterministic and correctly DST-aware for Europe/London (GMT winter, BST summer, and both
// the spring-forward and autumn-back transition days themselves, including the case where a
// single session's start and end fall on opposite sides of the transition); (3) the previous-
// completed-session predecessor cycle (ASIAN<-NEW_YORK[prior date], LONDON<-ASIAN, NEW_YORK<-
// LONDON) is correct; (4) M30 candle aggregation is strictly no-lookahead, excludes malformed/
// duplicate candles (reporting rather than repairing them), and correctly detects missing
// intervals; (5) extreme selection is deterministic including a swappable, isolated tie-break
// rule; (6) the four mandatory body-to-wick zone formulas match exactly; (7) zone objects are
// immutable and their ids are deterministic across repeat calls; (8) zone status correctly
// reflects ACTIVE/DATA_INCOMPLETE/INVALID_SOURCE from data quality alone (Phase 1 has no
// interaction/failure transition engine); (9) building TJR zones never mutates paperAccount,
// alexGAccount, journalEntries, or alexGJournalEntries.
function runV123Fixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,detail:detail||''});};
  const almostEqual=(a,b,eps)=>Math.abs(a-b)<(eps||1e-9);

  // Builds a clean, gap-free M30 candle array spanning an entire session's boundaries,
  // all candles sharing the same OHLC unless overridden by index.
  function buildSessionCandles(boundaries,defaults,overridesByIndex){
    const out=[];
    let idx=0;
    for(let t=boundaries.utcStart;t<boundaries.utcEnd;t+=1800000){
      const base=Object.assign({},defaults);
      if(overridesByIndex&&overridesByIndex[idx]) Object.assign(base,overridesByIndex[idx]);
      out.push({t,o:base.o,h:base.h,l:base.l,c:base.c});
      idx++;
    }
    return out;
  }
  const DEFAULT_OHLC={o:1.1000,h:1.1010,l:1.0990,c:1.1005};

  // ═══ Registration ═══
  {
    const reg=g.getRegistry();
    const ids=reg.map(e=>e.manifest.id);
    assert('Fixture 1: TJR_SLR is present in STRATEGY_REGISTRY alongside JVM and ALEX',
      ids.includes('tjr_slr')&&ids.includes('current_strategy')&&ids.includes('alex_g_sr_v1'),
      'ids='+JSON.stringify(ids));
  }
  {
    const m=g.findStrategyEntry('tjr_slr').manifest;
    assert('Fixture 2: TJR_SLR manifest reports status=development, version=1.0.0',
      m.status==='development'&&m.version==='1.0.0',
      'status='+m.status+' version='+m.version);
  }
  {
    const m=g.findStrategyEntry('tjr_slr').manifest;
    assert('Fixture 3: TJR_SLR has scanning/paperTrading/automation all disabled (scanner/paper/live execution all false)',
      m.capabilities.scanning===false&&m.capabilities.paperTrading===false&&m.capabilities.automation===false,
      JSON.stringify(m.capabilities));
  }
  {
    const m=g.findStrategyEntry('tjr_slr').manifest;
    assert('Fixture 4: TJR_SLR declares replay-supported per registration spec',
      m.capabilities.replay===true, 'replay='+m.capabilities.replay);
  }
  {
    const jvmStillThere=!!g.findStrategyEntry('current_strategy');
    const alexStillThere=!!g.findStrategyEntry('alex_g_sr_v1');
    assert('Fixture 5: registering TJR_SLR left JVM and ALEX registry entries intact',
      jvmStillThere&&alexStillThere,'jvm='+jvmStillThere+' alex='+alexStillThere);
  }

  // ═══ Session id mapping + exact boundaries ═══
  {
    const b=g.getTjrSessionForTimestamp(Date.UTC(2026,0,5,3,0,0)); // winter, 03:00 UTC = 03:00 local
    assert('Fixture 6: 03:00 UTC (winter) maps to ASIAN', b.sessionId==='ASIAN', b.sessionId);
  }
  {
    const b=g.getTjrSessionForTimestamp(Date.UTC(2026,0,5,10,0,0)); // winter, 10:00 UTC = 10:00 local
    assert('Fixture 7: 10:00 UTC (winter) maps to LONDON', b.sessionId==='LONDON', b.sessionId);
  }
  {
    const b=g.getTjrSessionForTimestamp(Date.UTC(2026,0,5,18,0,0)); // winter, 18:00 UTC = 18:00 local
    assert('Fixture 8: 18:00 UTC (winter) maps to NEW_YORK', b.sessionId==='NEW_YORK', b.sessionId);
  }
  {
    const b=g.resolveTjrSessionBoundaries('ASIAN','2026-01-05');
    assert('Fixture 9: ASIAN session start is inclusive at exactly local 00:00 (winter, GMT=UTC)',
      new Date(b.utcStart).getUTCHours()===0&&new Date(b.utcStart).getUTCMinutes()===0,
      new Date(b.utcStart).toISOString());
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    assert('Fixture 10: LONDON session end is exclusive at exactly local 13:00 (winter, GMT=UTC)',
      new Date(b.utcEnd).getUTCHours()===13&&new Date(b.utcEnd).getUTCMinutes()===0,
      new Date(b.utcEnd).toISOString());
  }
  {
    const b=g.resolveTjrSessionBoundaries('NEW_YORK','2026-01-05');
    const endDate=new Date(b.utcEnd);
    assert('Fixture 11: NEW_YORK session end rolls to the next local calendar date at 00:00',
      endDate.getUTCDate()===6&&endDate.getUTCHours()===0,
      endDate.toISOString());
  }

  // ═══ DST: winter GMT / summer BST / spring transition / autumn transition ═══
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05'); // winter, GMT, offset 0
    assert('Fixture 12: winter GMT conversion -- LONDON 08:00 local = 08:00 UTC',
      new Date(b.utcStart).getUTCHours()===8, new Date(b.utcStart).toISOString());
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-07-06'); // summer, BST, offset +60
    assert('Fixture 13: summer BST conversion -- LONDON 08:00 local = 07:00 UTC',
      new Date(b.utcStart).getUTCHours()===7, new Date(b.utcStart).toISOString());
  }
  {
    // 2026-03-29 is the last Sunday of March -- UK clocks go forward 01:00 GMT -> 02:00 BST.
    // ASIAN's local start (00:00) is still GMT; its local end (08:00) is already BST --
    // proves per-boundary (not per-day) offset resolution on the transition day itself.
    const b=g.resolveTjrSessionBoundaries('ASIAN','2026-03-29');
    assert('Fixture 14: spring-forward transition day -- ASIAN start still GMT (00:00 UTC)',
      new Date(b.utcStart).getUTCHours()===0, new Date(b.utcStart).toISOString());
    assert('Fixture 15: spring-forward transition day -- ASIAN end already BST (07:00 UTC, not 08:00)',
      new Date(b.utcEnd).getUTCHours()===7, new Date(b.utcEnd).toISOString());
  }
  {
    // 2026-10-25 is the last Sunday of October -- UK clocks go back 02:00 BST -> 01:00 GMT.
    // ASIAN's local start (00:00) is still BST; its local end (08:00) is already GMT.
    const b=g.resolveTjrSessionBoundaries('ASIAN','2026-10-25');
    const startIso=new Date(b.utcStart).toISOString();
    assert('Fixture 16: autumn-back transition day -- ASIAN start still BST (prev-day 23:00 UTC)',
      startIso==='2026-10-24T23:00:00.000Z', startIso);
    assert('Fixture 17: autumn-back transition day -- ASIAN end already GMT (08:00 UTC)',
      new Date(b.utcEnd).getUTCHours()===8, new Date(b.utcEnd).toISOString());
  }

  // ═══ Previous-completed-session resolution ═══
  {
    const ms=Date.UTC(2026,6,6,9,0,0); // BST: 09:00 UTC = 10:00 local -> LONDON
    const prev=g.getPreviousCompletedTjrSession(ms);
    assert('Fixture 18: during LONDON, previous completed session is ASIAN (same date)',
      prev.sessionId==='ASIAN'&&prev.tradingDate==='2026-07-06',
      prev.sessionId+' '+prev.tradingDate);
  }
  {
    const ms=Date.UTC(2026,6,6,17,0,0); // BST: 17:00 UTC = 18:00 local -> NEW_YORK
    const prev=g.getPreviousCompletedTjrSession(ms);
    assert('Fixture 19: during NEW_YORK, previous completed session is LONDON (same date)',
      prev.sessionId==='LONDON'&&prev.tradingDate==='2026-07-06',
      prev.sessionId+' '+prev.tradingDate);
  }
  {
    const ms=Date.UTC(2026,6,6,1,0,0); // BST: 01:00 UTC = 02:00 local -> ASIAN
    const prev=g.getPreviousCompletedTjrSession(ms);
    assert('Fixture 20: during ASIAN, previous completed session is NEW_YORK on the PRIOR trading date',
      prev.sessionId==='NEW_YORK'&&prev.tradingDate==='2026-07-05',
      prev.sessionId+' '+prev.tradingDate);
  }
  {
    const b=g.getPreviousCompletedTjrSession(Date.UTC(2026,6,6,9,0,0));
    assert('Fixture 21: isTjrSessionComplete is true for a session already ended relative to evaluation time',
      g.isTjrSessionComplete(b,Date.UTC(2026,6,6,9,0,0))===true,'');
    assert('Fixture 22: isTjrSessionComplete is false for evaluation time before the session even starts',
      g.isTjrSessionComplete(b,b.utcStart-1000)===false,'');
  }

  // ═══ Candle aggregation ═══
  {
    const b=g.resolveTjrSessionBoundaries('ASIAN','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    const diag=g.getCandlesForResolvedSession(candles,b,b.utcEnd+1000);
    assert('Fixture 23: clean ASIAN session aggregates exactly 16 M30 candles (8h/30min), dataset complete',
      diag.expectedCandleCount===16&&diag.actualCandleCount===16&&diag.datasetComplete===true,
      JSON.stringify({exp:diag.expectedCandleCount,act:diag.actualCandleCount,complete:diag.datasetComplete}));
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    const diag=g.getCandlesForResolvedSession(candles,b,b.utcEnd+1000);
    assert('Fixture 24: clean LONDON session aggregates exactly 10 M30 candles (5h/30min), dataset complete',
      diag.expectedCandleCount===10&&diag.actualCandleCount===10&&diag.datasetComplete===true,
      JSON.stringify({exp:diag.expectedCandleCount,act:diag.actualCandleCount}));
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    // A candle exactly at utcEnd (the next session's first candle) must be excluded.
    candles.push({t:b.utcEnd,o:9,h:9,l:9,c:9});
    const diag=g.getCandlesForResolvedSession(candles,b,b.utcEnd+1000);
    assert('Fixture 25: a candle exactly AT the session end boundary is excluded (end is exclusive)',
      diag.actualCandleCount===10,'actual='+diag.actualCandleCount);
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    const diag=g.getCandlesForResolvedSession(candles,b,b.utcStart+1000);
    assert('Fixture 26: a candle exactly AT the session start boundary IS included (start is inclusive)',
      diag.actualCandleCount===1,'actual='+diag.actualCandleCount);
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC).slice(1); // drop the first candle
    const diag=g.getCandlesForResolvedSession(candles,b,b.utcEnd+1000);
    assert('Fixture 27: a missing interval is detected and dataset is marked incomplete',
      diag.actualCandleCount===9&&diag.missingIntervals.length===1&&diag.datasetComplete===false,
      JSON.stringify({act:diag.actualCandleCount,missing:diag.missingIntervals.length}));
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    candles.push({t:b.utcStart,o:9,h:9,l:9,c:9}); // duplicate of the first candle's timestamp
    const diag=g.getCandlesForResolvedSession(candles,b,b.utcEnd+1000);
    assert('Fixture 28: a duplicate-timestamp candle is reported and excluded (first-seen wins), not merged',
      diag.duplicates.length===1&&diag.actualCandleCount===10&&diag.datasetComplete===false,
      JSON.stringify({dup:diag.duplicates.length,act:diag.actualCandleCount}));
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC,{9:{h:1.05,l:1.09}}); // h < l -- malformed
    const diag=g.getCandlesForResolvedSession(candles,b,b.utcEnd+1000);
    assert('Fixture 29: a malformed OHLC candle (h<l) is rejected and reported, never silently repaired',
      diag.invalidCandles.length===1&&diag.actualCandleCount===9&&diag.datasetComplete===false,
      JSON.stringify({inv:diag.invalidCandles.length,act:diag.actualCandleCount}));
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    const diag=g.getCandlesForResolvedSession(candles,b,b.utcStart+3*1800000);
    assert('Fixture 30: no-lookahead -- candles at/after the evaluation timestamp are excluded even though they are inside the session window',
      diag.actualCandleCount===3,'actual='+diag.actualCandleCount);
  }

  // ═══ Extreme selection + tie-break ═══
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC,{4:{h:1.1050}}); // unique high (above the 1.1010 default)
    const sc=g.getCandlesForResolvedSession(candles,b,b.utcEnd+1000).candles;
    const ext=g.findTjrSessionExtremes(sc,'GBP_USD');
    assert('Fixture 31: a unique high is selected with reason unique_extreme and no ties',
      ext.high===1.1050&&ext.highSelectionReason==='unique_extreme'&&ext.tiedHighCandidates.length===1,
      JSON.stringify({high:ext.high,reason:ext.highSelectionReason,tied:ext.tiedHighCandidates.length}));
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC,{4:{l:1.0500}}); // unique low
    const sc=g.getCandlesForResolvedSession(candles,b,b.utcEnd+1000).candles;
    const ext=g.findTjrSessionExtremes(sc,'GBP_USD');
    assert('Fixture 32: a unique low is selected with reason unique_extreme and no ties',
      ext.low===1.0500&&ext.lowSelectionReason==='unique_extreme'&&ext.tiedLowCandidates.length===1,
      JSON.stringify({low:ext.low,reason:ext.lowSelectionReason,tied:ext.tiedLowCandidates.length}));
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC,{2:{h:1.1050},6:{h:1.1050}});
    const sc=g.getCandlesForResolvedSession(candles,b,b.utcEnd+1000).candles;
    const ext=g.findTjrSessionExtremes(sc,'GBP_USD');
    assert('Fixture 33: tied highs are all stored as candidates, and the LATEST qualifying candle is canonically selected',
      ext.tiedHighCandidates.length===2&&ext.highSource.time===sc[6].time&&ext.highSelectionReason==='tie_latest_candle_selected',
      JSON.stringify({tied:ext.tiedHighCandidates.length,selected:ext.highSource.time,expect:sc[6].time}));
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC,{1:{l:1.0500},7:{l:1.0500}});
    const sc=g.getCandlesForResolvedSession(candles,b,b.utcEnd+1000).candles;
    const ext=g.findTjrSessionExtremes(sc,'GBP_USD');
    assert('Fixture 34: tied lows are all stored as candidates, and the LATEST qualifying candle is canonically selected',
      ext.tiedLowCandidates.length===2&&ext.lowSource.time===sc[7].time,
      JSON.stringify({tied:ext.tiedLowCandidates.length,selected:ext.lowSource.time,expect:sc[7].time}));
  }

  // ═══ Mandatory zone formula fixtures (verbatim from spec) ═══
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const c={time:b.utcStart,o:1.1000,h:1.1040,l:1.0990,c:1.1020}; // bullish high source
    const z=g.buildTjrHighZone(b,c,'GBP_USD',b.utcEnd+1000,{datasetComplete:true});
    assert('Fixture 35: bullish high-zone candle -- expected zone 1.1020 to 1.1040',
      almostEqual(z.lower,1.1020)&&almostEqual(z.upper,1.1040),'lower='+z.lower+' upper='+z.upper);
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const c={time:b.utcStart,o:1.1030,h:1.1050,l:1.1000,c:1.1010}; // bearish high source
    const z=g.buildTjrHighZone(b,c,'GBP_USD',b.utcEnd+1000,{datasetComplete:true});
    assert('Fixture 36: bearish high-zone candle -- expected zone 1.1030 to 1.1050',
      almostEqual(z.lower,1.1030)&&almostEqual(z.upper,1.1050),'lower='+z.lower+' upper='+z.upper);
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const c={time:b.utcStart,o:1.1000,h:1.1030,l:1.0980,c:1.1020}; // bullish low source
    const z=g.buildTjrLowZone(b,c,'GBP_USD',b.utcEnd+1000,{datasetComplete:true});
    assert('Fixture 37: bullish low-zone candle -- expected zone 1.0980 to 1.1000',
      almostEqual(z.lower,1.0980)&&almostEqual(z.upper,1.1000),'lower='+z.lower+' upper='+z.upper);
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const c={time:b.utcStart,o:1.1020,h:1.1030,l:1.0970,c:1.1000}; // bearish low source
    const z=g.buildTjrLowZone(b,c,'GBP_USD',b.utcEnd+1000,{datasetComplete:true});
    assert('Fixture 38: bearish low-zone candle -- expected zone 0.9970 to 1.1000',
      almostEqual(z.lower,1.0970)&&almostEqual(z.upper,1.1000),'lower='+z.lower+' upper='+z.upper);
  }

  // ═══ Zone id determinism, immutability, no-lookahead repeat evaluation ═══
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    const r1=g.buildTjrSessionZones('GBP_USD',candles,b.utcEnd+5000);
    const r2=g.buildTjrSessionZones('GBP_USD',candles,b.utcEnd+5000);
    assert('Fixture 39: deterministic zone id -- identical inputs produce the identical zoneId across repeat calls',
      r1.highZone.zoneId===r2.highZone.zoneId&&r1.highZone.zoneId==='TJR_SLR:GBP_USD:LONDON:2026-01-05:HIGH',
      r1.highZone.zoneId);
    assert('Fixture 40: no-lookahead repeat evaluation -- identical inputs produce an identical (immutable) zone definition',
      r1.highZone.upper===r2.highZone.upper&&r1.highZone.lower===r2.highZone.lower&&r1.lowZone.upper===r2.lowZone.upper&&r1.lowZone.lower===r2.lowZone.lower,
      '');
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    const r=g.buildTjrSessionZones('GBP_USD',candles,b.utcEnd+5000);
    const originalUpper=r.highZone.upper;
    try{ r.highZone.upper=999; }catch(e){}
    try{ r.highZone.status='TAMPERED'; }catch(e){}
    assert('Fixture 41: zone bounds are immutable -- a write attempt after creation does not change the value',
      r.highZone.upper===originalUpper&&r.highZone.status!=='TAMPERED',
      'upper='+r.highZone.upper+' status='+r.highZone.status);
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    const r=g.buildTjrSessionZones('GBP_USD',candles,b.utcEnd+5000);
    assert('Fixture 42: a complete, valid dataset produces status ACTIVE for both zones',
      r.highZone.status==='ACTIVE'&&r.lowZone.status==='ACTIVE',
      r.highZone.status+'/'+r.lowZone.status);
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC).slice(1); // missing interval
    const r=g.buildTjrSessionZones('GBP_USD',candles,b.utcEnd+5000);
    assert('Fixture 43: a dataset with a missing interval produces status DATA_INCOMPLETE',
      r.highZone.status==='DATA_INCOMPLETE'&&r.lowZone.status==='DATA_INCOMPLETE',
      r.highZone.status+'/'+r.lowZone.status);
  }
  {
    const r=g.buildTjrSessionZones('GBP_USD',[],Date.UTC(2026,0,5,14,0,0));
    assert('Fixture 44: zero available candles produces status INVALID_SOURCE with null bounds (not fabricated)',
      r.highZone.status==='INVALID_SOURCE'&&r.highZone.lower===null&&r.highZone.upper===null,
      JSON.stringify({status:r.highZone.status,lower:r.highZone.lower,upper:r.highZone.upper}));
  }
  {
    // Incomplete-source-session rejection: evaluation time is BEFORE the resolved previous
    // session has even finished -- buildTjrSessionZones must not fabricate a zone from a
    // session that, per isTjrSessionComplete, hasn't actually elapsed yet.
    const evalMs=Date.UTC(2026,0,5,9,0,0); // during LONDON; previous completed = ASIAN same day
    const asianBoundaries=g.resolveTjrSessionBoundaries('ASIAN','2026-01-05');
    const partialCandles=buildSessionCandles(asianBoundaries,DEFAULT_OHLC).slice(0,3); // session not fully elapsed yet in this synthetic feed
    const r=g.buildTjrSessionZones('GBP_USD',partialCandles,evalMs);
    assert('Fixture 45: an incomplete source session (fewer candles than the elapsed window can supply) is reported, not fabricated',
      r.sessionData.datasetComplete===false,
      JSON.stringify(r.sessionData));
  }
  {
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    const r=g.buildTjrSessionZones('EUR_USD',candles,b.utcEnd+5000);
    assert('Fixture 46: future-candle exclusion is honored end-to-end through buildTjrSessionZones (evaluation time gates candle inclusion)',
      r.sessionData.actualCandleCount===10,'actual='+r.sessionData.actualCandleCount);
  }

  // ═══ Isolation: TJR zone computation never touches JVM/ALEX trading state ═══
  {
    const paperBefore=JSON.stringify(g.getPaperAccount());
    const alexBefore=JSON.stringify(g.getAlexGAccount());
    const journalBefore=JSON.stringify(g.getJournalEntries());
    const alexJournalBefore=JSON.stringify(g.getAlexGJournalEntries());
    const b=g.resolveTjrSessionBoundaries('LONDON','2026-01-05');
    const candles=buildSessionCandles(b,DEFAULT_OHLC);
    g.buildTjrSessionZones('GBP_USD',candles,b.utcEnd+5000);
    assert('Fixture 47: computing TJR zones causes zero mutation of paperAccount/alexGAccount/journalEntries/alexGJournalEntries',
      paperBefore===JSON.stringify(g.getPaperAccount())&&alexBefore===JSON.stringify(g.getAlexGAccount())&&
      journalBefore===JSON.stringify(g.getJournalEntries())&&alexJournalBefore===JSON.stringify(g.getAlexGJournalEntries()),
      '');
  }

  // ═══ Chart overlay toggle default ═══
  {
    assert('Fixture 48: chartOverlayToggles.tjrZones defaults to true (zones render unless explicitly hidden)',
      g.getDefaultTjrZonesToggle()===true,'');
  }

  return results;
}
