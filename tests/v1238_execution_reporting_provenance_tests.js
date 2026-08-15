// v12.3.8 EXECUTION-REPORTING PROVENANCE (MOGO tranche D).
//
// Closes a measured mutation-coverage gap on the paper-trade execution REPORTING surface:
// record classification (classifyJvmJournalRecord and its render call site), per-trade manual
// notes (the real saveTiNotes -> setTradeNote -> tradeNotes -> getTradeNote -> rendered panel
// round trip, keyed 'JVMJ|<id>' / 'ALEXJ|<id>' in fxhub_trade_notes), and the export/evidence
// surface (evidenceNormalizeJvmTrade -> evidenceBuildPackageFromTrade outcome fields,
// replayDiagCsvEscape as reached through the real exportReplayDiagnosticsCSV(), and the
// evaluator-version parity verdict on both the rendered surface and the export payload).
//
// Every fixture here asserts against a FIXTURE-CHOSEN LITERAL -- never a value re-derived the
// way the production code derives it, never the source text of a function, never a comparison
// of two outputs of the same computation. Each was individually mutation-proven: the
// corresponding defect was applied to a scratch copy of index.html and the fixture was
// confirmed to FAIL.
function runExecutionReportingProvenanceFixtures(g){
  const results=[];
  // Details are flattened to one line and capped: several fixtures below report raw CSV text,
  // whose embedded newlines would otherwise split a single fixture result across many lines and
  // make run_all.sh's per-fixture PASS/FAIL line counting harder to read.
  const flat=d=>String(d==null?'':d).replace(/\r?\n/g,'\\n').slice(0,200);
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,method:'execution',detail:flat(detail)});};
  const note=(name,method,detail)=>{results.push({name,pass:null,method,detail:flat(detail)});};

  function seedClean(){
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setJournalEntries([]);
    g.setAlexGAccount({balance:10000,openPositions:[],closedPositions:[]});
    g.setAlexGJournalEntries([]);
    g.setPaperResetHistory([]);
    g.setTradeNotes({});
    g.resetPaperVersionGuard();
    g.resetAlexGVersionGuard();
    g.clearLocalStorage();
    g.clearLastDownload();
    g.clearReplayParityDemo();
  }

  // A raw JVM journal record in the exact shape buildJVMJournalOpenRecord() writes.
  function jvmRaw(over){
    return Object.assign({
      journalEntryId:'JVMJ|'+(over&&over.tradeId!=null?over.tradeId:7001),
      tradeId:7001,strategy:'current_strategy',strategyId:'current_strategy',strategyLabel:'JVM',
      tradeSource:'AUTO',source:'auto',
      pair:'GBP/USD',timeframe:'M15',direction:'buy',
      entry:1.1000,stop:1.0950,target:1.1100,plannedRR:2,
      riskPercent:1,riskAmount:100,positionSize:0.2,
      openedAt:'2026-08-01T10:00:00.000Z',status:'OPEN'
    },over||{});
  }

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // N1 / N3 -- RECORD CLASSIFICATION
  // ══════════════════════════════════════════════════════════════════════════════════════════

  // ── N1: an OPEN position must NEVER be classified as a closed-account trade. ──
  // The two verdicts are distinct FIXTURE-CHOSEN string literals ('Active position' /
  // 'Closed account trade'), asserted directly rather than compared to JVM_RECORD_CLASS (which
  // would re-derive the answer the way the code does).
  {
    seedClean();
    const raw=jvmRaw({tradeId:7001});
    g.setPaperAccount({balance:10000,openPositions:[{id:7001,oPair:'GBP_USD'}],closedPositions:[]});
    g.setJournalEntries([raw]);
    const r=g.normalizeJournalRecord(raw,'current_strategy');
    const cls=g.classifyJvmJournalRecord(r);
    // The second conjunct was a TAUTOLOGY given the first (§18.12): if cls === 'Active position'
    // then cls !== 'Closed account trade' is necessarily true and can never contribute a failure.
    // Dropped rather than left in place looking like extra rigour.
    assert('N1.1: a journal record whose tradeId is in paperAccount.openPositions classifies as the literal "Active position"',
      cls==='Active position','cls='+JSON.stringify(cls));
  }

  // ── N1 positive control: the CLOSED case really does produce the other literal, so N1.1 is
  //    not passing merely because the classifier always returns 'Active position'. ──
  {
    seedClean();
    const raw=jvmRaw({tradeId:7002,status:'CLOSED',result:'Win',pnl:200,closedAt:'2026-08-01T14:00:00.000Z'});
    g.setPaperAccount({balance:10200,openPositions:[],closedPositions:[{id:7002,oPair:'GBP_USD',result:'Win',pnl:200}]});
    g.setJournalEntries([raw]);
    const r=g.normalizeJournalRecord(raw,'current_strategy');
    const cls=g.classifyJvmJournalRecord(r);
    assert('N1.2 (positive control): a record whose tradeId is in paperAccount.closedPositions classifies as the literal "Closed account trade"',
      cls==='Closed account trade','cls='+JSON.stringify(cls));
  }

  // ── N1: open and closed must not be conflated when BOTH exist at once. A mutation that
  //    routes the open branch into the closed verdict makes the two rows indistinguishable. ──
  {
    seedClean();
    const openRaw=jvmRaw({tradeId:7011});
    const closedRaw=jvmRaw({tradeId:7012,status:'CLOSED',result:'Loss',pnl:-100,closedAt:'2026-08-01T14:00:00.000Z'});
    g.setPaperAccount({balance:9900,openPositions:[{id:7011,oPair:'GBP_USD'}],closedPositions:[{id:7012,oPair:'GBP_USD',result:'Loss',pnl:-100}]});
    g.setJournalEntries([openRaw,closedRaw]);
    const a=g.classifyJvmJournalRecord(g.normalizeJournalRecord(openRaw,'current_strategy'));
    const b=g.classifyJvmJournalRecord(g.normalizeJournalRecord(closedRaw,'current_strategy'));
    assert('N1.3: with one open and one closed position in the same account, the open record reads "Active position" and the closed record reads "Closed account trade" -- the two are never collapsed onto one verdict',
      a==='Active position'&&b==='Closed account trade','open='+JSON.stringify(a)+' closed='+JSON.stringify(b));
  }

  // ── N1 wiring: the classifier's verdict actually reaches rendered HTML. renderPaperMiniJournal()
  //    is the ONLY surface that renders it, and the whole real path runs here:
  //    getFilteredJournalRecords -> classifyJvmJournalRecord -> jvmClassBadgeClass -> innerHTML.
  //
  //    DISCLOSED: see the FINDING note below -- renderPaperMiniJournal() asks
  //    getFilteredJournalRecords for strategy 'JVM' (a display LABEL), but that function has
  //    matched on strategyId since v12.3.2, and real JVM records carry strategyId
  //    'current_strategy'. Two otherwise-identical records for the SAME open position are
  //    seeded below, one under each identifier, so this fixture measures the badge wiring
  //    rather than the filter defect, and keeps measuring it if the filter is later corrected.
  {
    seedClean();
    const asLabel=jvmRaw({tradeId:7003,strategyId:'JVM'});
    const asId=jvmRaw({tradeId:7003,strategyId:'current_strategy'});
    g.setPaperAccount({balance:10000,openPositions:[{id:7003,oPair:'GBP_USD'}],closedPositions:[]});
    g.setJournalEntries([asLabel,asId]);
    g.renderPaperMiniJournal();
    const h=String(g.elHtml('paperMiniJournal'));
    assert('N1.4 (wiring): renderPaperMiniJournal() writes the exact badge markup <span class="jvm-class-badge jvm-class-active" title="Account relationship">Active position</span> for an open position, renders at least one row, and never emits the closed-account badge',
      h.indexOf('<span class="jvm-class-badge jvm-class-active" title="Account relationship">Active position</span>')!==-1
      &&h.indexOf('No trades yet')===-1
      &&h.indexOf('Closed account trade')===-1,
      'html='+h.slice(0,220));
  }

  // ── N3: a developer trade must keep its DEV_TEST marking. The record below ALSO has a live
  //    open position under the same tradeId, so if the developer check is removed the record
  //    falls through to "Active position" -- the assertion pins the literal "Developer test". ──
  {
    seedClean();
    const raw=jvmRaw({tradeId:7004,isDeveloperTrade:true});
    g.setPaperAccount({balance:10000,openPositions:[{id:7004,oPair:'GBP_USD'}],closedPositions:[]});
    g.setJournalEntries([raw]);
    const cls=g.classifyJvmJournalRecord(g.normalizeJournalRecord(raw,'current_strategy'));
    assert('N3.1: a record flagged isDeveloperTrade classifies as the literal "Developer test" even when a live open position shares its tradeId -- the developer marking is never lost to the account lookup',
      cls==='Developer test','cls='+JSON.stringify(cls));
  }

  // ── N3: the same, for a developer record whose tradeId is in closedPositions, and for one
  //    that is orphaned entirely -- three different fall-through destinations, one verdict. ──
  {
    seedClean();
    const closedDev=jvmRaw({tradeId:7005,isDeveloperTrade:true,status:'CLOSED',result:'Win',pnl:50,closedAt:'2026-08-01T14:00:00.000Z'});
    const orphanDev=jvmRaw({tradeId:7006,isDeveloperTrade:true,status:'CLOSED',result:'Loss',pnl:-50,closedAt:'2026-08-01T14:00:00.000Z'});
    g.setPaperAccount({balance:10000,openPositions:[],closedPositions:[{id:7005,oPair:'GBP_USD',result:'Win',pnl:50}]});
    g.setJournalEntries([closedDev,orphanDev]);
    const a=g.classifyJvmJournalRecord(g.normalizeJournalRecord(closedDev,'current_strategy'));
    const b=g.classifyJvmJournalRecord(g.normalizeJournalRecord(orphanDev,'current_strategy'));
    assert('N3.2: developer records classify as "Developer test" whether their tradeId is in closedPositions or orphaned -- never "Closed account trade" and never "Journal only"',
      a==='Developer test'&&b==='Developer test','closedDev='+JSON.stringify(a)+' orphanDev='+JSON.stringify(b));
  }

  // ── N3 positive control: the SAME record without the developer flag classifies elsewhere, so
  //    N3.1/N3.2 cannot be passing because everything is called "Developer test". ──
  {
    seedClean();
    const raw=jvmRaw({tradeId:7007,isDeveloperTrade:false});
    g.setPaperAccount({balance:10000,openPositions:[{id:7007,oPair:'GBP_USD'}],closedPositions:[]});
    g.setJournalEntries([raw]);
    const cls=g.classifyJvmJournalRecord(g.normalizeJournalRecord(raw,'current_strategy'));
    assert('N3.3 (positive control): the identical record WITHOUT isDeveloperTrade classifies as "Active position", proving the developer verdict is driven by the flag and not returned unconditionally',
      cls==='Active position','cls='+JSON.stringify(cls));
  }

  // ── N3 wiring: the developer verdict reaches rendered HTML with its own badge class.
  //    Same disclosed dual-identifier seeding as N1.4 above. ──
  {
    seedClean();
    const asLabel=jvmRaw({tradeId:7008,strategyId:'JVM',isDeveloperTrade:true});
    const asId=jvmRaw({tradeId:7008,strategyId:'current_strategy',isDeveloperTrade:true});
    g.setPaperAccount({balance:10000,openPositions:[{id:7008,oPair:'GBP_USD'}],closedPositions:[]});
    g.setJournalEntries([asLabel,asId]);
    g.renderPaperMiniJournal();
    const h=String(g.elHtml('paperMiniJournal'));
    assert('N3.4 (wiring): renderPaperMiniJournal() writes the exact badge markup <span class="jvm-class-badge jvm-class-devtest" title="Account relationship">Developer test</span> for a developer trade sharing a tradeId with a live open position, and never the "Active position" badge',
      h.indexOf('<span class="jvm-class-badge jvm-class-devtest" title="Account relationship">Developer test</span>')!==-1
      &&h.indexOf('No trades yet')===-1
      &&h.indexOf('>Active position<')===-1,
      'html='+h.slice(0,220));
  }

  // ── 🔴 THE PRODUCTION DEFECT THIS TRANCHE FOUND, NOW FIXED AND PINNED (§18.11) ──────────────
  // Both mini-journals rendered "No trades yet." for EVERY real trade. v12.3.2 correctly made
  // strategyId the ownership key in getFilteredJournalRecords, but these call sites kept passing
  // the display LABEL ('JVM' / 'ALEX'), and no record's strategyId is ever 'JVM' or 'ALEX' -- they
  // are 'current_strategy' and 'alex_g_sr_v1'. The filter matched nothing, permanently. That also
  // took down the account-relationship badge surface, which is the ONLY place the operator ever
  // sees classifyJvmJournalRecord's verdict. Fixed at the CALLER: re-admitting labels inside the
  // filter would undo v12.3.2's deliberate correction.
  {
    seedClean();
    // ONLY the real strategyId is seeded -- no label-shaped duplicate. Before the fix this
    // rendered the empty state; the record is otherwise entirely ordinary.
    g.setPaperAccount({balance:10000,openPositions:[{id:7101,oPair:'GBP_USD'}],closedPositions:[]});
    g.setJournalEntries([jvmRaw({tradeId:7101,strategyId:'current_strategy'})]);
    assert('MiniJournal.1: PRECONDITION -- a real JVM record carries strategyId "current_strategy", never the display label "JVM"',
      g.getFilteredJournalRecords({strategy:'current_strategy'}).length===1
      &&g.getFilteredJournalRecords({strategy:'JVM'}).length===0,
      'byId='+g.getFilteredJournalRecords({strategy:'current_strategy'}).length+
      ' byLabel='+g.getFilteredJournalRecords({strategy:'JVM'}).length);
    g.renderPaperMiniJournal();
    const mj=String(g.elHtml('paperMiniJournal'));
    assert('MiniJournal.2: renderPaperMiniJournal() renders the real trade instead of the empty state -- the label is resolved to its registry id',
      mj.indexOf('No trades yet')===-1&&mj.indexOf('7101')!==-1,'html='+mj.slice(0,200));
    // The summary is written with textContent, NOT innerHTML, so it must be read with elText.
    // An earlier draft of this fixture ORed the two readers together with a defensive ternary and
    // printed the elHtml value in its failure message -- it passed, but the message showed an empty
    // string, which is exactly the kind of assertion whose evidence cannot be checked at a glance.
    assert('MiniJournal.3: and the summary counts it, so the row is genuinely in the filtered set rather than merely present in the markup',
      String(g.elText('paperMiniJournalSummary')).indexOf('1 trade')!==-1,
      'summary='+String(g.elText('paperMiniJournalSummary')));
    // ALEX arm -- the same defect, the same fix, driven through the shared renderer.
    seedClean();
    g.setAlexGJournalEntries([{journalEntryId:'ALEXJ|7102',tradeId:'AGT|7102',strategyId:'alex_g_sr_v1',
      status:'CLOSED',pair:'GBP/USD',direction:'buy',result:'Win',resultR:2,pnl:200,
      openedAt:'2026-08-01T00:00:00.000Z',closedAt:'2026-08-01T01:00:00.000Z'}]);
    g.renderMiniJournal('alexMiniJournal','alexMiniJournalSummary','ALEX');
    const amj=String(g.elHtml('alexMiniJournal'));
    assert('MiniJournal.4: the ALEX mini-journal renders its real trade too -- the shared renderer resolves the label for every strategy, not just JVM',
      amj.indexOf('No trades yet')===-1&&amj.indexOf('7102')!==-1,'html='+amj.slice(0,200));
    // NEGATIVE CONTROL: an unknown label must NOT silently fall back to showing everything.
    // Passing a label no strategy owns has to render nothing, or the fix would have turned the
    // filter into a no-op -- which would be a worse defect than the one it replaced.
    seedClean();
    g.setPaperAccount({balance:10000,openPositions:[{id:7103,oPair:'GBP_USD'}],closedPositions:[]});
    g.setJournalEntries([jvmRaw({tradeId:7103,strategyId:'current_strategy'})]);
    g.renderMiniJournal('alexMiniJournal','alexMiniJournalSummary','NO_SUCH_STRATEGY');
    assert('MiniJournal.5: NEGATIVE CONTROL -- an unrecognised label still filters to nothing, so the fix resolved the label rather than disabling the filter',
      String(g.elHtml('alexMiniJournal')).indexOf('7103')===-1,
      'html='+String(g.elHtml('alexMiniJournal')).slice(0,200));

    // ── §18.12: TWO DEFECTS IN THE §18.11 FIX ITSELF, found by independent adversarial
    //    verification. MiniJournal.5 above was the negative control that was SUPPOSED to exclude
    //    "fixed by disabling the filter" -- and it missed the real version of that failure,
    //    because it only ever tested a TRUTHY unknown label.
    //
    // (a) FAILING OPEN. getFilteredJournalRecords skips the strategy filter entirely when the
    //     value is falsy or 'All'. So '', null, undefined and 'All' did not mean "no match" --
    //     they meant NO FILTER, leaking every strategy's trades into a strategy-specific panel.
    seedClean();
    g.setPaperAccount({balance:10000,openPositions:[{id:7104,oPair:'GBP_USD'}],closedPositions:[]});
    g.setJournalEntries([jvmRaw({tradeId:7104,strategyId:'current_strategy'})]);
    const leakCases=[['empty string',''],['null',null],['undefined',undefined],['the All sentinel','All']];
    let leaked=[];
    leakCases.forEach(function(c){
      g.renderMiniJournal('alexMiniJournal','alexMiniJournalSummary',c[1]);
      if(String(g.elHtml('alexMiniJournal')).indexOf('7104')!==-1) leaked.push(c[0]);
    });
    assert('MiniJournal.6: a falsy or "All" strategy argument must FAIL CLOSED -- it renders nothing, rather than disabling the filter and leaking every strategy\'s trades into a strategy-specific panel',
      leaked.length===0,'leaked for: '+(leaked.join(', ')||'(none)'));
    // (b) RENAME FRAGILITY. The first version of this fix resolved a hardcoded display LABEL
    //     through findStrategyEntryByLabel -- the lookup this codebase marks LEGACY COMPATIBILITY
    //     ONLY, "not for new code", precisely because a renamed label stops resolving. Renaming
    //     the label is a pure display-metadata edit, exactly what ADR-006 says labels are for, and
    //     it silently restored the original "No trades yet. for every real trade" defect in full.
    seedClean();
    g.setPaperAccount({balance:10000,openPositions:[{id:7105,oPair:'GBP_USD'}],closedPositions:[]});
    g.setJournalEntries([jvmRaw({tradeId:7105,strategyId:'current_strategy'})]);
    const originalLabel=g.JVM_MANIFEST.label;
    g.JVM_MANIFEST.label='JVM Strategy';                 // the rename ADR-006 explicitly permits
    g.renderPaperMiniJournal();
    const renamedHtml=String(g.elHtml('paperMiniJournal'));
    g.JVM_MANIFEST.label=originalLabel;                  // restored before asserting, so a failure
                                                         // here cannot poison later fixtures
    assert('MiniJournal.7: renaming JVM_MANIFEST.label -- pure display metadata -- does NOT break the panel, because the call site resolves the registry ID and never the label',
      renamedHtml.indexOf('No trades yet')===-1&&renamedHtml.indexOf('7105')!==-1,
      'html='+renamedHtml.slice(0,200));
    assert('MiniJournal.8: PRECONDITION -- the label really was renamed during MiniJournal.7, and is restored afterwards, so that fixture measured a genuine rename',
      originalLabel==='JVM'&&g.JVM_MANIFEST.label==='JVM',
      'original='+String(originalLabel)+' now='+String(g.JVM_MANIFEST.label));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // Q1 / Q2 -- TRADE NOTES (driven through the REAL save-and-read path)
  // ══════════════════════════════════════════════════════════════════════════════════════════
  // saveTiNotes(journalEntryId) is the literal onclick target of the Save Note button rendered
  // by renderTiNotes(). It reads the textarea, calls setTradeNote(), and re-renders the panel.
  // Nothing below calls setTradeNote() directly.

  function seedTwoJvmTrades(){
    seedClean();
    const a=jvmRaw({tradeId:8001,journalEntryId:'JVMJ|8001',status:'CLOSED',result:'Win',pnl:200,resultR:2,closedAt:'2026-08-01T14:00:00.000Z'});
    const b=jvmRaw({tradeId:8002,journalEntryId:'JVMJ|8002',pair:'EUR/USD',status:'CLOSED',result:'Loss',pnl:-100,resultR:-1,closedAt:'2026-08-02T14:00:00.000Z'});
    g.setPaperAccount({balance:10100,openPositions:[],closedPositions:[
      {id:8001,oPair:'GBP_USD',result:'Win',pnl:200},{id:8002,oPair:'EUR_USD',result:'Loss',pnl:-100}]});
    g.setJournalEntries([a,b]);
    return{a,b};
  }
  function saveNoteThroughUi(journalEntryId,text){
    g.setElValue('tiNotesArea',text);
    g.saveTiNotes(journalEntryId);
  }

  // ── Q1: a saved note must associate back to the trade it was saved against. ──
  {
    seedTwoJvmTrades();
    saveNoteThroughUi('JVMJ|8001','NOTE-ALPHA-4417');
    const n=g.getTradeNote('JVMJ|8001');
    assert('Q1.1: a note saved through the real Save Note path (saveTiNotes -> setTradeNote) reads back from getTradeNote(\'JVMJ|8001\') with the exact text "NOTE-ALPHA-4417"',
      !!n&&n.text==='NOTE-ALPHA-4417','note='+JSON.stringify(n));
    assert('Q1.2: the note is stored in tradeNotes under the trade\'s own key \'JVMJ|8001\' -- the store\'s key set is exactly ["JVMJ|8001"], not a shared or anonymous key',
      JSON.stringify(Object.keys(g.getTradeNotes()))==='["JVMJ|8001"]','keys='+JSON.stringify(Object.keys(g.getTradeNotes())));
  }

  // ── Q1: the saved note must come back on the rendered Trade Inspector panel for that trade. ──
  {
    seedTwoJvmTrades();
    g.renderTradeInspectorPanel('JVMJ|8001');
    const before=String(g.elHtml('tradeInspectorPanelBody'));
    saveNoteThroughUi('JVMJ|8001','NOTE-BRAVO-9052');
    const after=String(g.elHtml('tradeInspectorPanelBody'));
    assert('Q1.3: after saving through the real path, the Trade Inspector panel for JVMJ|8001 renders the literal "NOTE-BRAVO-9052" and no longer says "Not saved yet" -- the note round-trips all the way back to the screen',
      before.indexOf('Not saved yet')!==-1&&after.indexOf('NOTE-BRAVO-9052')!==-1&&after.indexOf('Not saved yet')===-1,
      'beforeHadPlaceholder='+(before.indexOf('Not saved yet')!==-1)+' afterHasNote='+(after.indexOf('NOTE-BRAVO-9052')!==-1));
  }

  // ── Q2: two trades, two notes. Each must read back its OWN note. A single shared key makes
  //    both reads return the same text (or, for a per-call anonymous key, neither). ──
  {
    seedTwoJvmTrades();
    saveNoteThroughUi('JVMJ|8001','NOTE-FIRST-1111');
    saveNoteThroughUi('JVMJ|8002','NOTE-SECOND-2222');
    const n1=g.getTradeNote('JVMJ|8001');
    const n2=g.getTradeNote('JVMJ|8002');
    assert('Q2.1: with a note saved against each of two trades, JVMJ|8001 reads back "NOTE-FIRST-1111" and JVMJ|8002 reads back "NOTE-SECOND-2222" -- saving the second never overwrites or replaces the first',
      !!n1&&!!n2&&n1.text==='NOTE-FIRST-1111'&&n2.text==='NOTE-SECOND-2222',
      'n1='+JSON.stringify(n1&&n1.text)+' n2='+JSON.stringify(n2&&n2.text));
    assert('Q2.2: tradeNotes holds exactly two distinct keys after two saves against two different trades -- notes are not collapsed onto one shared key',
      JSON.stringify(Object.keys(g.getTradeNotes()).sort())==='["JVMJ|8001","JVMJ|8002"]',
      'keys='+JSON.stringify(Object.keys(g.getTradeNotes())));
  }

  // ── Q2: the cross-contamination check on the SCREEN -- trade 8002's panel must never show
  //    trade 8001's note. This is the failure the user would actually see. ──
  {
    seedTwoJvmTrades();
    saveNoteThroughUi('JVMJ|8001','NOTE-MINE-3141');
    g.renderTradeInspectorPanel('JVMJ|8002');
    const other=String(g.elHtml('tradeInspectorPanelBody'));
    g.renderTradeInspectorPanel('JVMJ|8001');
    const own=String(g.elHtml('tradeInspectorPanelBody'));
    assert('Q2.3: a note saved on JVMJ|8001 renders on JVMJ|8001\'s panel and is ABSENT from JVMJ|8002\'s panel (which still reads "Not saved yet") -- a note never surfaces on another trade',
      own.indexOf('NOTE-MINE-3141')!==-1&&other.indexOf('NOTE-MINE-3141')===-1&&other.indexOf('Not saved yet')!==-1,
      'ownHas='+(own.indexOf('NOTE-MINE-3141')!==-1)+' otherHas='+(other.indexOf('NOTE-MINE-3141')!==-1));
  }

  // ── EXTENDED SWEEP: the 'JVMJ|' / 'ALEXJ|' prefix is the only thing separating a JVM trade
  //    from an ALEX trade that minted the SAME numeric id. A note on one must never appear on
  //    the other. (paperNextTradeId and alexGTradeId are proven disjoint elsewhere, but the
  //    NOTE store is keyed by journalEntryId, so this is its own end-to-end claim.) ──
  {
    seedClean();
    const jvm=jvmRaw({tradeId:9001,journalEntryId:'JVMJ|9001',status:'CLOSED',result:'Win',pnl:150,closedAt:'2026-08-03T14:00:00.000Z'});
    g.setPaperAccount({balance:10150,openPositions:[],closedPositions:[{id:9001,oPair:'GBP_USD',result:'Win',pnl:150}]});
    g.setJournalEntries([jvm]);
    g.setAlexGJournalEntries([{
      journalEntryId:'ALEXJ|9001',tradeId:9001,strategy:'alex_g_sr_v1',strategyId:'alex_g_sr_v1',strategyLabel:'ALEX',
      pair:'EUR/USD',timeframe:'H1',direction:'sell',entry:1.0800,stop:1.0850,target:1.0700,
      openedAt:'2026-08-03T09:00:00.000Z',closedAt:'2026-08-03T15:00:00.000Z',status:'CLOSED',result:'Loss',pnl:-80
    }]);
    saveNoteThroughUi('JVMJ|9001','NOTE-JVM-ONLY-5150');
    const alexNote=g.getTradeNote('ALEXJ|9001');
    const jvmNote=g.getTradeNote('JVMJ|9001');
    g.renderTradeInspectorPanel('ALEXJ|9001');
    const alexPanel=String(g.elHtml('tradeInspectorPanelBody'));
    assert('Q2.4 (extended): a JVM trade and an ALEX trade sharing numeric id 9001 keep separate notes -- getTradeNote(\'JVMJ|9001\') is "NOTE-JVM-ONLY-5150" while getTradeNote(\'ALEXJ|9001\') is null and the ALEX panel renders "Not saved yet"',
      !!jvmNote&&jvmNote.text==='NOTE-JVM-ONLY-5150'&&alexNote===null&&alexPanel.indexOf('NOTE-JVM-ONLY-5150')===-1&&alexPanel.indexOf('Not saved yet')!==-1,
      'jvm='+JSON.stringify(jvmNote&&jvmNote.text)+' alex='+JSON.stringify(alexNote));
  }

  // ── EXTENDED SWEEP: the association must survive persistence. The note store is a separate
  //    localStorage key (fxhub_trade_notes); a reload must restore each note against its own
  //    trade, not against the first/last one. ──
  {
    seedTwoJvmTrades();
    saveNoteThroughUi('JVMJ|8001','NOTE-PERSIST-A-7001');
    saveNoteThroughUi('JVMJ|8002','NOTE-PERSIST-B-7002');
    const rawStore=g.getLocalStorageItem('fxhub_trade_notes');
    let parsed=null; try{ parsed=JSON.parse(rawStore); }catch(e){}
    assert('Q1.4 (extended): fxhub_trade_notes persists each note under its own \'JVMJ|<id>\' key -- parsed["JVMJ|8001"].text is "NOTE-PERSIST-A-7001" and parsed["JVMJ|8002"].text is "NOTE-PERSIST-B-7002"',
      !!parsed&&parsed['JVMJ|8001']&&parsed['JVMJ|8001'].text==='NOTE-PERSIST-A-7001'
      &&parsed['JVMJ|8002']&&parsed['JVMJ|8002'].text==='NOTE-PERSIST-B-7002',
      'stored='+String(rawStore).slice(0,180));
    // Simulate a reload: drop the in-memory store, load it back from the same storage.
    g.setTradeNotes({});
    g.loadSaved();
    const n1=g.getTradeNote('JVMJ|8001'),n2=g.getTradeNote('JVMJ|8002');
    assert('Q2.5 (extended): after a reload (loadSaved) each note is still bound to its own trade -- JVMJ|8001 reads "NOTE-PERSIST-A-7001" and JVMJ|8002 reads "NOTE-PERSIST-B-7002"',
      !!n1&&n1.text==='NOTE-PERSIST-A-7001'&&!!n2&&n2.text==='NOTE-PERSIST-B-7002',
      'n1='+JSON.stringify(n1&&n1.text)+' n2='+JSON.stringify(n2&&n2.text));
  }

  // ── EXTENDED SWEEP: clearing one trade's note must not clear another's. ──
  {
    seedTwoJvmTrades();
    saveNoteThroughUi('JVMJ|8001','NOTE-KEEPME-6060');
    saveNoteThroughUi('JVMJ|8002','NOTE-DELETEME-6061');
    saveNoteThroughUi('JVMJ|8002','');   // the real clear path: empty textarea -> delete
    const kept=g.getTradeNote('JVMJ|8001'),gone=g.getTradeNote('JVMJ|8002');
    assert('Q2.6 (extended): clearing JVMJ|8002\'s note removes only that trade\'s entry -- JVMJ|8002 reads null while JVMJ|8001 still reads "NOTE-KEEPME-6060"',
      gone===null&&!!kept&&kept.text==='NOTE-KEEPME-6060',
      'kept='+JSON.stringify(kept&&kept.text)+' gone='+JSON.stringify(gone));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // U3 -- CLOSED JVM EVIDENCE RECORD MUST CARRY ITS RESULT AND P&L
  // ══════════════════════════════════════════════════════════════════════════════════════════

  function jvmClosedPosition(over){
    return Object.assign({
      id:7101,oPair:'GBP_USD',pair:'GBP/USD',dir:'buy',
      entry:1.10000,stop:1.09500,target:1.11000,ratio:2,
      riskAmount:100,lots:0.2,pipValueAtEntry:10,
      openedAt:'2026-08-01T10:00:00.000Z',
      exitPrice:1.11000,closedAt:'2026-08-01T14:00:00.000Z',
      result:'Win',pnl:200.25,closeReason:'TAKE_PROFIT'
    },over||{});
  }

  {
    seedClean();
    const norm=g.evidenceNormalizeJvmTrade(jvmClosedPosition());
    assert('U3.1: evidenceNormalizeJvmTrade carries the closed position\'s outcome verbatim -- result "Win", pnl 200.25, exitPrice 1.11, closedAt "2026-08-01T14:00:00.000Z"',
      !!norm&&norm.result==='Win'&&norm.pnl===200.25&&norm.exitPrice===1.11&&norm.closedAt==='2026-08-01T14:00:00.000Z',
      'norm='+JSON.stringify(norm));
  }

  // A LOSING close, with a negative P&L -- proves the value is COPIED, not defaulted, and that
  // U3.1 is not passing off a hard-coded 'Win'/positive number.
  {
    seedClean();
    const norm=g.evidenceNormalizeJvmTrade(jvmClosedPosition({id:7102,result:'Loss',pnl:-137.5,exitPrice:1.09500,closeReason:'STOP_LOSS'}));
    assert('U3.2 (positive control): a losing close normalises to result "Loss" and pnl -137.5 -- the outcome fields track the position, they are not fixed values',
      !!norm&&norm.result==='Loss'&&norm.pnl===-137.5,'norm='+JSON.stringify(norm));
  }

  // ── U3 wiring: the outcome must survive into the evidence PACKAGE, which is what actually
  //    gets hashed, exported and audited. evidenceCaptureClosedPaperTradesAsync's only
  //    per-trade work is evidenceNormalizeJvmTrade -> evidencePersistTradePackage, and the
  //    package is built by evidenceBuildPackageFromTrade; that build is fully synchronous and
  //    is driven for real here. ──
  {
    seedClean();
    const norm=g.evidenceNormalizeJvmTrade(jvmClosedPosition());
    let pkg=null,err=null;
    try{ pkg=g.evidenceBuildPackageFromTrade(norm,{strategyId:g.EVIDENCE_JVM_STRATEGY_ID,captureBasis:'LIVE_CLOSE'}); }catch(e){ err=e; }
    const o=pkg&&pkg.objects&&pkg.objects.outcomes&&pkg.objects.outcomes[0];
    assert('U3.3 (wiring): the evidence package built from a closed JVM trade records exitReasonCode "Win", pnl 200.25 and exitPrice 1.11 on its outcome object -- the result and P&L reach the artefact that is hashed and exported',
      !!o&&o.exitReasonCode==='Win'&&o.pnl===200.25&&o.exitPrice===1.11,
      err?('threw: '+err.message):('outcome='+JSON.stringify(o&&{exitReasonCode:o.exitReasonCode,pnl:o.pnl,exitPrice:o.exitPrice})));
  }

  {
    seedClean();
    const norm=g.evidenceNormalizeJvmTrade(jvmClosedPosition({id:7103,result:'Loss',pnl:-137.5,exitPrice:1.09500,closeReason:'STOP_LOSS'}));
    let pkg=null,err=null;
    try{ pkg=g.evidenceBuildPackageFromTrade(norm,{strategyId:g.EVIDENCE_JVM_STRATEGY_ID,captureBasis:'LIVE_CLOSE'}); }catch(e){ err=e; }
    const o=pkg&&pkg.objects&&pkg.objects.outcomes&&pkg.objects.outcomes[0];
    assert('U3.4 (wiring, positive control): the evidence package for a losing close records exitReasonCode "Loss" and pnl -137.5, and its sourceTradeId is the string "7103"',
      !!o&&o.exitReasonCode==='Loss'&&o.pnl===-137.5&&pkg.sourceTradeId==='7103',
      err?('threw: '+err.message):('outcome='+JSON.stringify(o&&{exitReasonCode:o.exitReasonCode,pnl:o.pnl})+' sourceTradeId='+JSON.stringify(pkg&&pkg.sourceTradeId)));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // U4 -- CSV ESCAPING (asserted as EXACT output strings, through the real export path)
  // ══════════════════════════════════════════════════════════════════════════════════════════

  function fakeDiag(over){
    return Object.assign({
      requestedStartTs:1000,requestedEndTs:9000,actualFirstEvaluatedTs:1500,actualLastEvaluatedTs:8500,
      weeklyLoaded:30,dailyLoaded:60,h4Loaded:200,m15Loaded:300,
      m15DecisionCandlesProcessed:100,missingCandles:2,invalidCandles:0,
      sessionFilteredCandles:3,weekdayFilteredCandles:5,
      funnel:{rawDecisionPointsEvaluated:100,directionalBiasCandidates:40,structuralAoisIdentified:20,
        aoiTouchObservations:10,rejectionWickObservations:8,engulfingPatternObservations:6,msbObservations:4,
        candidatesReachingMinConfluence:12,candidatesPassingMinRR:5,candidatesPassingSession:15,
        candidatesPassingWeekday:18,finalValidSignals:3},
      rejectionTotals:{insufficient_confluence:1},
      rejectedCandidates:[],
      nearMisses:[],
      evaluatorVersion:g.SETUP_EVALUATOR_VERSION
    },over||{});
  }
  // renderReplayDiagnostics(diag,runInfo) is what assigns replayDiagLastRunInfo, which is the
  // ONLY input exportReplayDiagnosticsCSV() reads. Driving the export therefore has to go
  // through the render first -- exactly as the UI does.
  function exportCsvFor(diag){
    g.clearLastDownload();
    g.renderReplayDiagnostics(diag,{diag:diag});
    g.exportReplayDiagnosticsCSV();
    const d=g.getLastDownload();
    return d?d.text:null;
  }

  // ── U4: a rejected-candidate field containing BOTH a comma and a double quote. The assertion
  //    is the exact escaped row, chosen by this fixture, not re-derived. ──
  {
    seedClean();
    const csv=exportCsvFor(fakeDiag({rejectedCandidates:[{
      timestamp:'2026-08-01T10:00:00Z',pair:'EUR/USD,"X"',direction:'buy',strategy:'JVM',
      confluence:40,primaryRejection:'Insufficient confluence',primaryRejectionId:'insufficient_confluence',
      secondaryRejections:[]}]}));
    const expected='2026-08-01T10:00:00Z,"EUR/USD,""X""",buy,JVM,40,Insufficient confluence,';
    assert('U4.1: exporting a rejected candidate whose pair field is the literal EUR/USD,"X" produces the exact CSV row 2026-08-01T10:00:00Z,"EUR/USD,""X""",buy,JVM,40,Insufficient confluence, -- the comma-and-quote field is wrapped and its quotes doubled',
      !!csv&&csv.indexOf(expected)!==-1,'csvTail='+String(csv).slice(-260));
  }

  // ── EXTENDED SWEEP: every OTHER rejected-candidate field that can carry a delimiter.
  //    primaryRejection is free text; secondaryRejections are joined with '; ' into ONE field,
  //    so a comma inside any element must still be escaped at the joined level. ──
  {
    seedClean();
    const csv=exportCsvFor(fakeDiag({rejectedCandidates:[{
      timestamp:'2026-08-02T11:30:00Z',pair:'GBP/USD',direction:'sell',strategy:'JVM',
      confluence:60,primaryRejection:'Rejected: confluence, R:R',primaryRejectionId:'minimum_rr_not_met',
      secondaryRejections:['Outside session, London','Weekday gate']}]}));
    const expected='2026-08-02T11:30:00Z,GBP/USD,sell,JVM,60,"Rejected: confluence, R:R","Outside session, London; Weekday gate"';
    assert('U4.2 (extended): a comma inside primaryRejection AND inside a secondaryRejections element both survive -- the exact row 2026-08-02T11:30:00Z,GBP/USD,sell,JVM,60,"Rejected: confluence, R:R","Outside session, London; Weekday gate" is emitted',
      !!csv&&csv.indexOf(expected)!==-1,'csvTail='+String(csv).slice(-260));
  }

  // ── EXTENDED SWEEP: the near-misses block is a second, independently-built row set. ──
  {
    seedClean();
    const csv=exportCsvFor(fakeDiag({nearMisses:[{
      timestamp:'2026-08-03T08:00:00Z',pair:'USD/JPY',direction:'buy',strategy:'JVM',
      observedConfluence:50,requiredConfluence:55,failedGate:'Confluence, minimum "hard" gate',
      whatWasRequired:'5 more confluence point(s)'}]}));
    const expected='2026-08-03T08:00:00Z,USD/JPY,buy,JVM,50,55,"Confluence, minimum ""hard"" gate"';
    assert('U4.3 (extended): the near-misses section escapes its own fields -- a failedGate of Confluence, minimum "hard" gate emits the exact row 2026-08-03T08:00:00Z,USD/JPY,buy,JVM,50,55,"Confluence, minimum ""hard"" gate"',
      !!csv&&csv.indexOf(expected)!==-1,'csvTail='+String(csv).slice(-260));
  }

  // ── EXTENDED SWEEP: the evaluator/coverage/funnel key-value block is built by a DIFFERENT
  //    code path (Object.entries -> rows) than the two tables above, and its values are also
  //    escapable strings. A replay evaluator identifier carrying a comma is the realistic case. ──
  {
    seedClean();
    const csv=exportCsvFor(fakeDiag({evaluatorVersion:'full-breakdown-v1,beta "rc2"'}));
    const expected='evaluator,replayEvaluatorVersion,"full-breakdown-v1,beta ""rc2"""';
    assert('U4.4 (extended): the evaluator metadata block escapes too -- a replay evaluator version of full-breakdown-v1,beta "rc2" emits the exact row evaluator,replayEvaluatorVersion,"full-breakdown-v1,beta ""rc2"""',
      !!csv&&csv.indexOf(expected)!==-1,'csvHead='+String(csv).slice(0,300));
  }

  // ── U4: the escaper's exact contract, field by field, against literals this fixture chose. ──
  {
    seedClean();
    const cases=[
      ['plain','plain'],
      ['a,b','"a,b"'],
      ['say "hi"','"say ""hi"""'],
      ['line1\nline2','"line1\nline2"'],
      ['both, "q"','"both, ""q"""'],
      [null,''],
      [undefined,'']
    ];
    const bad=cases.filter(c=>g.replayDiagCsvEscape(c[0])!==c[1])
      .map(c=>JSON.stringify(c[0])+'->'+JSON.stringify(g.replayDiagCsvEscape(c[0]))+' expected '+JSON.stringify(c[1]));
    assert('U4.5: replayDiagCsvEscape returns exactly: plain->plain, a,b->"a,b", say "hi"->"say ""hi""", an embedded newline is wrapped, both, "q"->"both, ""q""", and null/undefined->the empty string',
      bad.length===0,bad.join(' | '));
  }

  // ── U4: a value with NO delimiter must NOT be wrapped -- otherwise "escaping present" could
  //    be satisfied by quoting everything, which corrupts the export in the other direction. ──
  {
    seedClean();
    const csv=exportCsvFor(fakeDiag({rejectedCandidates:[{
      timestamp:'2026-08-04T09:00:00Z',pair:'AUD/USD',direction:'buy',strategy:'JVM',
      confluence:70,primaryRejection:'Outside approved session',primaryRejectionId:'outside_session',
      secondaryRejections:[]}]}));
    const expected='2026-08-04T09:00:00Z,AUD/USD,buy,JVM,70,Outside approved session,';
    assert('U4.6: a row whose fields contain no comma/quote/newline is emitted completely unquoted -- exactly 2026-08-04T09:00:00Z,AUD/USD,buy,JVM,70,Outside approved session,',
      !!csv&&csv.indexOf(expected)!==-1&&csv.indexOf('"AUD/USD"')===-1,'csvTail='+String(csv).slice(-200));
  }

  // ══════════════════════════════════════════════════════════════════════════════════════════
  // U5 -- EVALUATOR-VERSION PARITY MUST BE ABLE TO REPORT MISMATCH
  // ══════════════════════════════════════════════════════════════════════════════════════════
  // Note on the assertion: "MISMATCH" contains the substring "MATCH", so the MATCH verdict is
  // pinned on '>PARITY: MATCH<' (the badge's own closing boundary), never on 'MATCH' alone.

  {
    seedClean();
    const diag=fakeDiag({evaluatorVersion:'replay-evaluator-vDIVERGED-0001'});
    g.renderReplayDiagnostics(diag,{diag:diag});
    const h=String(g.elHtml('mtfDiagEvaluatorParity'));
    assert('U5.1: when the replay evaluator identifier is replay-evaluator-vDIVERGED-0001 and the live one is not, the parity line renders "PARITY: MISMATCH" and does NOT render the ">PARITY: MATCH<" badge',
      h.indexOf('PARITY: MISMATCH')!==-1&&h.indexOf('>PARITY: MATCH<')===-1
      &&h.indexOf('replay-evaluator-vDIVERGED-0001')!==-1,
      'html='+h.slice(0,240));
  }

  {
    seedClean();
    const diag=fakeDiag();   // evaluatorVersion === the live SETUP_EVALUATOR_VERSION
    g.renderReplayDiagnostics(diag,{diag:diag});
    const h=String(g.elHtml('mtfDiagEvaluatorParity'));
    assert('U5.2 (positive control): when live and replay evaluator identifiers agree, the parity line renders the ">PARITY: MATCH<" badge and never the MISMATCH warning -- so U5.1 is not passing because the surface always warns',
      h.indexOf('>PARITY: MATCH<')!==-1&&h.indexOf('PARITY: MISMATCH')===-1,'html='+h.slice(0,240));
  }

  {
    seedClean();
    const diag=fakeDiag({evaluatorVersion:'replay-evaluator-vDIVERGED-0002'});
    g.renderReplayDiagnostics(diag,{diag:diag});
    const payload=g.replayDiagBuildExportPayload();
    assert('U5.3: the export payload\'s evaluatorMetadata.parity is the literal "MISMATCH" when the replay evaluator is replay-evaluator-vDIVERGED-0002, and replayEvaluatorVersion records that identifier verbatim',
      !!payload&&payload.evaluatorMetadata.parity==='MISMATCH'
      &&payload.evaluatorMetadata.replayEvaluatorVersion==='replay-evaluator-vDIVERGED-0002',
      'meta='+JSON.stringify(payload&&payload.evaluatorMetadata));
  }

  {
    seedClean();
    const diag=fakeDiag();
    g.renderReplayDiagnostics(diag,{diag:diag});
    const payload=g.replayDiagBuildExportPayload();
    assert('U5.4 (positive control): the export payload\'s evaluatorMetadata.parity is the literal "MATCH" when the two evaluator identifiers agree',
      !!payload&&payload.evaluatorMetadata.parity==='MATCH','meta='+JSON.stringify(payload&&payload.evaluatorMetadata));
  }

  {
    seedClean();
    const csv=exportCsvFor(fakeDiag({evaluatorVersion:'replay-evaluator-vDIVERGED-0003'}));
    assert('U5.5: the exported CSV carries the parity verdict downstream -- it contains the exact row "evaluator,parity,MISMATCH" and not "evaluator,parity,MATCH"',
      !!csv&&csv.indexOf('evaluator,parity,MISMATCH')!==-1&&csv.indexOf('evaluator,parity,MATCH\n')===-1,
      'csvHead='+String(csv).slice(0,300));
  }

  seedClean();
  return results;
}
