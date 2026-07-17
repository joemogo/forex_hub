// v12.1.3 -- Security Baseline: escaping fixes, Manual Lock, and the confirmation/lock guards
// added to every credential-change, automation-toggle, destructive, and Manual-Review-approval
// action. Every function under test here is fully synchronous, so (unlike the v12.1.2 Replay
// engine) this suite drives the real, unmodified functions end to end -- no separable-piece
// workaround needed. See docs/SECURITY.md for the full disclosure this suite backs.
function runV1213Fixtures(g){
  const results=[];
  const assert=(name,cond,detail)=>{results.push({name,pass:!!cond,detail:detail||''});};
  const deepEq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);

  // ── escapeHtml / renderAlertLog ──
  (function(){
    const payload='<script>alert(1)</script>';
    g.setAlertLog([{type:'manual_review',pair:payload,pct:50,time:'12:00',sigs:[payload]}]);
    g.renderAlertLog();
    const html1=g.getElementHtml('alertLog');
    assert('renderAlertLog escapes pair/sigs in manual_review branch',
      html1.indexOf('<script>alert(1)</script>')===-1 && html1.indexOf('&lt;script&gt;')!==-1,
      html1.slice(0,200));

    g.setAlertLog([{type:'auto',pair:payload,pct:75,time:'13:00',direction:'long',inSession:true,sigs:[payload]}]);
    g.renderAlertLog();
    const html2=g.getElementHtml('alertLog');
    assert('renderAlertLog escapes pair/sigs in normal alert branch',
      html2.indexOf('<script>alert(1)</script>')===-1 && html2.indexOf('&lt;script&gt;')!==-1,
      html2.slice(0,200));

    g.setAlertLog([]);
    g.renderAlertLog();
    assert('renderAlertLog empty-state unaffected',
      g.getElementHtml('alertLog').indexOf('No alerts yet')!==-1,'');
  })();

  // ── inspectorRows ──
  (function(){
    const payload='<img src=x onerror=alert(1)>';
    const html=g.inspectorRows([['<b>Label</b>',payload]]);
    assert('inspectorRows escapes both label and val',
      html.indexOf('<img src=x')===-1 && html.indexOf('&lt;img src=x')!==-1 && html.indexOf('&lt;b&gt;Label&lt;/b&gt;')!==-1,
      html.slice(0,200));
  })();

  // ── inspectorRows via renderTradeInspectorContent: badges must NOT be double-escaped, and
  //    a hostile r.pair must still come out escaped (it now flows through inspectorRows) ──
  (function(){
    const rec={strategyLabel:'JVM',isDeveloperTrade:false,pair:'<script>x</script>',timeframe:'M15',
      setupLabel:'Test',direction:'buy',status:'Closed',tradeSource:'auto',tradeId:'t1',
      entry:1.1,openedAt:null,riskPercent:1,riskAmount:100,positionSize:1,plannedRR:2,
      stop:1.09,howStopWasCalculated:'x',target:1.12,howTargetWasCalculated:'x',
      maePips:1,mfePips:1,maeR:0.1,mfeR:0.1,exitPrice:1.12,result:'Win',resultR:2,pnl:200,
      closedAt:null,exitDetectionSource:'x',durationMs:1000,whyQualified:'x',
      howEntryWasCalculated:'x',whyClosed:'x',isLegacyManual:false,_raw:{}};
    const html=g.renderTradeInspectorContent(rec,'tradeInspectorCard');
    assert('renderTradeInspectorContent: Strategy badge renders as real markup, not escaped text',
      html.indexOf('<span class="badge"')!==-1, html.slice(0,300));
    assert('renderTradeInspectorContent: hostile pair value is escaped',
      html.indexOf('<script>x</script>')===-1 && html.indexOf('&lt;script&gt;x&lt;/script&gt;')!==-1,
      '');
  })();

  // ── Manual Lock: baseline + mechanism ──
  assert('mogoLock starts unlocked', g.isLocked()===false, '');

  (function(){
    g.mogoLockNow();
    assert('mogoLockNow sets locked=true', g.isLocked()===true, '');
    assert('mogoLockNow persists fxhub_lock=1', g.getAllLocalStorageKeys().indexOf('fxhub_lock')!==-1 && g.getLocalStorageItem('fxhub_lock')==='1', '');
    assert('overlay shown while locked', g.getOverlayDisplay()==='flex', g.getOverlayDisplay());

    g.mogoUnlock();
    assert('mogoUnlock sets locked=false', g.isLocked()===false, '');
    assert('mogoUnlock removes fxhub_lock key', g.getAllLocalStorageKeys().indexOf('fxhub_lock')===-1, '');
    assert('overlay hidden while unlocked', g.getOverlayDisplay()==='none', g.getOverlayDisplay());
  })();

  (function(){
    g.setLocked(false);
    assert('mogoLockBlocked returns false when unlocked', g.mogoLockBlocked()===false, '');
    g.setLocked(true);
    assert('mogoLockBlocked returns true when locked', g.mogoLockBlocked()===true, '');
    g.setLocked(false);
  })();

  // ── Guarded actions: each must be a true no-op while locked ──
  (function(){
    g.setAutoTrading({enabled:false});
    g.setElementChecked('autoTradeToggle',true); // user just clicked the checkbox on
    g.setLocked(true);
    g.toggleAutoTrading();
    assert('toggleAutoTrading blocked while locked leaves autoTrading.enabled false', g.getAutoTrading().enabled===false, JSON.stringify(g.getAutoTrading()));
    assert('toggleAutoTrading blocked while locked reverts the checkbox', g.getElementChecked('autoTradeToggle')===false, '');
    g.setLocked(false);
    g.setElementChecked('autoTradeToggle',true);
    g.setConfirmReturn(true);
    g.toggleAutoTrading();
    assert('toggleAutoTrading proceeds when unlocked and confirmed', g.getAutoTrading().enabled===true, JSON.stringify(g.getAutoTrading()));
    g.setAutoTrading({enabled:false});
  })();

  (function(){
    g.setAlexGAutoTrading({enabled:false,tradedSignals:{},tradedToday:{},log:[]});
    g.setLocked(true);
    g.toggleAlexGLiveTrading();
    assert('toggleAlexGLiveTrading blocked while locked', g.getAlexGAutoTrading().enabled===false, '');
    g.setLocked(false);
  })();

  (function(){
    g.setCfg({key:'realkey',accountId:'real-acct',env:'practice'});
    g.setElementValue('apiKey','realkey');
    g.setElementValue('accountId','real-acct');
    g.setLocked(true);
    g.disconnect();
    assert('disconnect blocked while locked leaves cfg intact', g.getCfg().key==='realkey'&&g.getCfg().accountId==='real-acct', JSON.stringify(g.getCfg()));
    g.setLocked(false);
    g.disconnect();
    assert('disconnect clears cfg when unlocked', g.getCfg().key===''&&g.getCfg().accountId==='', JSON.stringify(g.getCfg()));
    assert('disconnect clears the apiKey DOM field', g.getElementValue('apiKey')==='', '');
    assert('disconnect clears the accountId DOM field (v12.1.3 fix -- previously left populated)', g.getElementValue('accountId')==='', '');
  })();

  // ── Reconciliation: OANDA token is never persisted; Anthropic key IS persisted by design.
  //    These are deliberately different, disclosed behaviors -- not a contradiction -- and this
  //    suite must prove both directly rather than asserting a single blanket "no key in storage"
  //    claim that would be false for the Anthropic key. See docs/SECURITY.md. ──
  (function(){
    const secretOandaKey='OANDA-SECRET-TOKEN-'+Math.random();
    const secretOandaAcct='999-999-99999999-999';
    g.setCfg({key:secretOandaKey,accountId:secretOandaAcct,env:'practice'});
    g.setElementValue('apiKey',secretOandaKey);
    g.setElementValue('accountId',secretOandaAcct);
    const allValues=g.getAllLocalStorageKeys().map(k=>g.getLocalStorageItem(k)).join('\n');
    assert('OANDA token never appears in any localStorage value', allValues.indexOf(secretOandaKey)===-1, '');
    assert('OANDA account ID never appears in any localStorage value', allValues.indexOf(secretOandaAcct)===-1, '');
    g.setCfg({key:'',accountId:'',env:'practice'});
  })();

  (function(){
    const secretAiKey='sk-ant-SECRET-'+Math.random();
    g.setAiChat({key:'',model:'',messages:[]});
    g.setElementValue('aiKeyInput',secretAiKey);
    g.setConfirmReturn(true);
    g.saveAiKey();
    assert('saveAiKey DOES persist the Anthropic key to fxhub_ai_key (disclosed, by-design difference from the OANDA token)',
      g.getLocalStorageItem('fxhub_ai_key')===secretAiKey, '');
    assert('saveAiKey also sets it in memory (aiChat.key)', g.getAiChat().key===secretAiKey, '');
    g.clearAiKey();
    assert('clearAiKey removes it from localStorage', g.getLocalStorageItem('fxhub_ai_key')===null, '');
    assert('clearAiKey removes it from memory', g.getAiChat().key==='', '');
  })();

  (function(){
    g.setAiChat({key:'',model:'',messages:[]});
    g.setElementValue('aiKeyInput','sk-ant-realkey');
    g.setLocked(true);
    g.saveAiKey();
    assert('saveAiKey blocked while locked', g.getAiChat().key==='', '');
    g.setLocked(false);
    g.setElementValue('aiKeyInput','sk-ant-realkey');
    g.saveAiKey();
    assert('saveAiKey proceeds when unlocked', g.getAiChat().key==='sk-ant-realkey', '');
    g.setLocked(true);
    g.clearAiKey();
    assert('clearAiKey blocked while locked', g.getAiChat().key==='sk-ant-realkey', '');
    g.setLocked(false);
    g.clearAiKey();
    assert('clearAiKey proceeds when unlocked', g.getAiChat().key==='', '');
  })();

  (function(){
    g.setJournalEntries([{id:'j1',pair:'EUR_USD'}]);
    g.setLocked(true);
    g.deleteEntry('j1');
    assert('deleteEntry blocked while locked', g.getJournalEntries().length===1, '');
    g.setLocked(false);
    g.setConfirmReturn(true);
    g.deleteEntry('j1');
    assert('deleteEntry proceeds when unlocked+confirmed', g.getJournalEntries().length===0, '');
    assert('deleteEntry confirm text discloses permanence (v12.1.3 strengthened text)',
      /permanently|cannot be undone/i.test(g.getLastConfirmMessage()), g.getLastConfirmMessage());
  })();

  (function(){
    const snap=JSON.stringify(g.getPaperAccount());
    g.setLocked(true);
    g.confirmPaperResetAccountOnly();
    assert('confirmPaperResetAccountOnly blocked while locked', JSON.stringify(g.getPaperAccount())===snap, '');
    g.confirmPaperResetFull();
    assert('confirmPaperResetFull blocked while locked', JSON.stringify(g.getPaperAccount())===snap, '');
    g.clearTestTradesPaper();
    assert('clearTestTradesPaper blocked while locked', JSON.stringify(g.getPaperAccount())===snap, '');
    g.confirmPaperReconciliationUI('nonexistent-trade-id');
    assert('confirmPaperReconciliationUI blocked while locked', JSON.stringify(g.getPaperAccount())===snap, '');
    g.setLocked(false);
  })();

  (function(){
    const snap=JSON.stringify(g.getAlexGAccount());
    g.setLocked(true);
    g.resetAlexGLiveAccount();
    assert('resetAlexGLiveAccount blocked while locked', JSON.stringify(g.getAlexGAccount())===snap, '');
    g.setLocked(false);
  })();

  (function(){
    const before=g.getPaperAccount().balance;
    g.setElementValue('paperBalanceInput','99999');
    g.setLocked(true);
    g.setPaperBalance();
    assert('setPaperBalance blocked while locked', g.getPaperAccount().balance===before, '');
    g.setLocked(false);
    g.setConfirmReturn(true);
    g.setPaperBalance();
    assert('setPaperBalance proceeds when unlocked+confirmed', g.getPaperAccount().balance===99999, '');
  })();

  (function(){
    g.setAiChat({key:'',model:'',messages:[{role:'user',content:'hi'}]});
    g.setLocked(true);
    g.setConfirmReturn(true);
    g.clearAiChat();
    assert('clearAiChat blocked while locked', g.getAiChat().messages.length===1, '');
    g.setLocked(false);
    g.clearAiChat();
    assert('clearAiChat proceeds when unlocked+confirmed', g.getAiChat().messages.length===0, '');
  })();

  (function(){
    g.setManualReviewCandidates({'EUR_USD':{state:'MANUAL REVIEW ELIGIBLE',breakdown:{},isFriday:false}});
    g.setLocked(true);
    const r=g.approveManualReviewTrade('EUR_USD');
    assert('approveManualReviewTrade blocked while locked returns ok:false', r&&r.ok===false, JSON.stringify(r));
    assert('approveManualReviewTrade blocked while locked leaves the candidate untouched',
      g.getManualReviewCandidates()['EUR_USD'].state==='MANUAL REVIEW ELIGIBLE', '');
    g.setLocked(false);
  })();

  // ── Locking/unlocking itself never mutates trading state (privacy barrier, not a data op) ──
  (function(){
    const paperBefore=JSON.stringify(g.getPaperAccount());
    const journalBefore=JSON.stringify(g.getJournalEntries());
    const alexBefore=JSON.stringify(g.getAlexGAccount());
    g.mogoLockNow();g.mogoUnlock();g.mogoLockNow();g.mogoUnlock();
    assert('lock/unlock cycling never mutates paperAccount', JSON.stringify(g.getPaperAccount())===paperBefore, '');
    assert('lock/unlock cycling never mutates journalEntries', JSON.stringify(g.getJournalEntries())===journalBefore, '');
    assert('lock/unlock cycling never mutates alexGAccount', JSON.stringify(g.getAlexGAccount())===alexBefore, '');
  })();

  return results;
}
