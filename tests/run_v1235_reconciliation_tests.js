// MOGO-021 — paper-ledger reconciliation: the ledger-MUTATING path.
//
// WHY THIS SUITE EXISTS
// MOGO-021 covers ledger/account state and reconciliation. `applyPaperReconciliation()` is the one
// function in the JVM paper ledger that RESTORES a trade and MOVES THE BALANCE outside the normal
// open/close lifecycle. The v11.0 release note states that fixtures cover it -- specifically
// "applying a reconciliation restores exactly once, updates balance exactly once, and is audited",
// "the same tradeId can never be reconciled twice", and "an incomplete journal record is skipped
// rather than reconstructed".
//
// No such fixtures exist. `applyPaperReconciliation` and `computeReconciliationPreview` are
// referenced by NO file in the repository, and by no test file in ANY commit reachable from the
// current history. The reporting side (computePaperLedgerIntegrity, ledgerReconcileBalance,
// ledgerBuildReconciliationReport) IS covered; the mutating side never was. This suite closes
// that gap and tests exactly the guarantees the release note claims.
//
// NOTHING REAL IS PERSISTED. localStorage is an in-memory stub, journalEntries/paperAccount are
// fixture values, and no paper trade is opened or closed through the live engine. The rollback
// case is driven through the REAL optimistic-concurrency guard (by advancing the persisted
// version), not by stubbing the save.
//
// PROTECTED FUNCTIONS ARE CALLED, NEVER MODIFIED: pipSize and the ledger commit path are used
// as-is. No strategy rule, threshold or weight is touched.
//
// Run from the project root:
//   osascript -l JavaScript tests/run_v1235_reconciliation_tests.js
// or simply:  tests/run_all.sh
ObjC.import('Foundation');
function readFile(path){
  const s=$.NSString.stringWithContentsOfFileEncodingError(path,$.NSUTF8StringEncoding,null);
  const v=ObjC.unwrap(s); return v==null?'':v;
}
function extractScriptBody(html){
  const m=html.match(/<script>([\s\S]*)<\/script>/);
  if(!m) throw new Error('Could not find <script>...</script> body in index.html -- run from project root.');
  return m[1];
}
const appCode=extractScriptBody(readFile('./index.html'));

const elMap={};
function makeClassList(){
  const c=new Set();
  return{add:x=>c.add(x),remove:x=>c.delete(x),contains:x=>c.has(x),
    toggle:(x,f)=>{ if(f===undefined){ c.has(x)?c.delete(x):c.add(x); } else if(f) c.add(x); else c.delete(x); }};
}
function makeStub(){
  return {innerHTML:'',textContent:'',value:'',className:'',style:{},options:[{value:'All'}],
    width:100,height:100,disabled:false,checked:false,classList:makeClassList(),
    getContext:()=>({clearRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillRect(){},save(){},restore(){},setLineDash(){},arc(){},fill(){},closePath(){},fillText(){},measureText:()=>({width:0})}),
    appendChild(){},addEventListener(){},focus(){},setSelectionRange(){},click(){},files:[],
    getBoundingClientRect:()=>({top:0,left:0,width:0,height:0})};
}
const lsStore={};
globalThis.document={
  getElementById:id=>{ if(!elMap[id]) elMap[id]=makeStub(); return elMap[id]; },
  querySelector:()=>null,querySelectorAll:()=>[],createElement:()=>makeStub(),
  addEventListener(){},visibilityState:'visible',
  body:{appendChild(){},removeChild(){}},activeElement:null
};
globalThis.window={devicePixelRatio:1};
globalThis.localStorage={
  getItem:k=>Object.prototype.hasOwnProperty.call(lsStore,k)?lsStore[k]:null,
  setItem:(k,v)=>{lsStore[k]=String(v);},removeItem:k=>{delete lsStore[k];}
};
globalThis.alert=()=>{};globalThis.confirm=()=>true;
globalThis.Blob=function(p,o){return{parts:p,opts:o};};
globalThis.URL={createObjectURL:()=>'blob:stub',revokeObjectURL(){}};
let __t=0;
globalThis.setTimeout=()=>++__t;globalThis.clearTimeout=()=>{};
globalThis.setInterval=()=>++__t;globalThis.clearInterval=()=>{};
globalThis.ResizeObserver=function(){return{observe(){},disconnect(){}};};
globalThis.LightweightCharts={LineStyle:{Solid:0,Dashed:1,Dotted:2},CrosshairMode:{Normal:0}};
globalThis.Notification=undefined;
globalThis.indexedDB=undefined;
globalThis.fetch=function(){ return Promise.reject(new Error('no network in this suite')); };

const results=[];
const g={record:(id,desc,pass,detail)=>results.push({id,desc,pass,detail:detail||''})};
g.ls=lsStore;

const wrapped=new Function('g', appCode + '\n' + 'return (function(){\n' +
  // ── fixture ledger: two complete orphans and one incomplete, none explained by a reset ──
  '  function completeOrphan(id,pnl){ return {tradeId:id,pair:"EUR/USD",direction:"buy",entry:1.1000,stop:1.0950,\n' +
  '    target:1.1100,openedAt:"2026-08-03T10:00:00.000Z",closedAt:"2026-08-03T14:00:00.000Z",result:"Win",\n' +
  '    pnl:pnl,exitPrice:1.1100,riskAmount:100,positionSize:0.2,status:"CLOSED",source:"auto"}; }\n' +
  '  function resetLedger(){\n' +
  '    paperAccount={balance:10000,openPositions:[],closedPositions:[]};\n' +
  '    paperResetHistory=[];\n' +
  '    paperReconciliationAudit=[];\n' +
  '    paperAccountKnownVersion=0;\n' +
  '    journalEntries=[completeOrphan("T-1",200),completeOrphan("T-2",50),\n' +
  '      {tradeId:"T-3",pair:"EUR/USD",direction:"buy",entry:1.1,stop:1.095,target:1.11,\n' +
  '       openedAt:"2026-08-03T10:00:00.000Z",closedAt:"2026-08-03T14:00:00.000Z",result:"Win",\n' +
  '       pnl:null,exitPrice:null,riskAmount:null,positionSize:null,status:"CLOSED",source:"auto"}];\n' +
  '    delete g.ls["fxhub_paper_version"]; delete g.ls["fxhub_paper"]; delete g.ls["fxhub_journal"];\n' +
  '  }\n' +
  '  resetLedger();\n' +
  // ── the integrity report must see them as unexplained orphans in the first place ──
  '  const integ=computePaperLedgerIntegrity();\n' +
  '  g.record("RECON-1","the three fixture trades are classified as unexplained post-reset orphans",\n' +
  '    integ.newlyOrphanedAfterReset.length===3,"orphans="+integ.newlyOrphanedAfterReset.length);\n' +
  '  g.record("RECON-2","a recorded reset AFTER the trade removes it from that list (the classifier is not blind)",\n' +
  '    (function(){ paperResetHistory=[{resetAt:"2026-08-04T00:00:00.000Z"}];\n' +
  '      const n=computePaperLedgerIntegrity().newlyOrphanedAfterReset.length; paperResetHistory=[]; return n===0; })(),\n' +
  '    "reset-explained orphans are excluded");\n' +
  // ── PREVIEW is read-only ──
  '  const accountBefore=JSON.stringify(paperAccount), auditBefore=JSON.stringify(paperReconciliationAudit);\n' +
  '  const pv=computeReconciliationPreview(["T-1"]);\n' +
  '  g.record("RECON-3","preview selects ONLY the tradeId asked for",\n' +
  '    pv.items.length===1&&pv.items[0].tradeId==="T-1","items="+pv.items.map(function(i){return i.tradeId;}).join(","));\n' +
  '  g.record("RECON-4","preview projects the balance as current + that trade\\u2019s stored pnl",\n' +
  '    pv.currentBalance===10000&&pv.projectedBalance===10200,"current="+pv.currentBalance+" projected="+pv.projectedBalance);\n' +
  '  g.record("RECON-5","preview mutates NOTHING -- not the account, not the audit trail",\n' +
  '    JSON.stringify(paperAccount)===accountBefore&&JSON.stringify(paperReconciliationAudit)===auditBefore,"both unchanged");\n' +
  '  const pvIncomplete=computeReconciliationPreview(["T-3"]);\n' +
  '  g.record("RECON-6","a record missing required fields is SKIPPED with a reason, never reconstructed",\n' +
  '    pvIncomplete.items.length===0&&pvIncomplete.skipped.length===1&&/Missing/.test(pvIncomplete.skipped[0].reason),\n' +
  '    "reason="+String((pvIncomplete.skipped[0]||{}).reason).slice(0,50));\n' +
  '  const pvUnknown=computeReconciliationPreview(["NOT-AN-ORPHAN"]);\n' +
  '  g.record("RECON-7","a tradeId that is not a proven orphan yields nothing -- arbitrary trades cannot be injected",\n' +
  '    pvUnknown.items.length===0&&pvUnknown.skipped.length===0,"items=0 skipped=0");\n' +
  // ── APPLY: the mutation ──
  '  const applied=applyPaperReconciliation(["T-1"]);\n' +
  '  g.record("RECON-8","apply restores exactly one closed position",\n' +
  '    applied.applied.length===1&&paperAccount.closedPositions.length===1&&paperAccount.closedPositions[0].id==="T-1",\n' +
  '    "applied="+applied.applied.join(",")+" closed="+paperAccount.closedPositions.length);\n' +
  '  g.record("RECON-9","the balance moves by the STORED pnl exactly -- never recalculated from prices",\n' +
  '    paperAccount.balance===10200,"balance="+paperAccount.balance+" (10000 + stored 200)");\n' +
  '  g.record("RECON-10","the restored trade is tagged source=reconciled, distinguishable from a real fill",\n' +
  '    paperAccount.closedPositions[0].source==="reconciled","source="+paperAccount.closedPositions[0].source);\n' +
  '  g.record("RECON-11","the restored pnl and result are the journal\\u2019s own stored values",\n' +
  '    paperAccount.closedPositions[0].pnl===200&&paperAccount.closedPositions[0].result==="Win",\n' +
  '    "pnl="+paperAccount.closedPositions[0].pnl+" result="+paperAccount.closedPositions[0].result);\n' +
  '  const a0=paperReconciliationAudit[0]||{};\n' +
  '  g.record("RECON-12","the restore is audited with action, pnl applied, and before/after balance",\n' +
  '    paperReconciliationAudit.length===1&&a0.action==="restore"&&a0.tradeId==="T-1"&&\n' +
  '    a0.pnlApplied===200&&a0.balanceBefore===10000&&a0.balanceAfter===10200,\n' +
  '    JSON.stringify({action:a0.action,before:a0.balanceBefore,after:a0.balanceAfter}));\n' +
  // ── double-apply protection, the guarantee the release note names ──
  '  const again=applyPaperReconciliation(["T-1"]);\n' +
  '  g.record("RECON-13","the SAME tradeId can never be reconciled twice -- no second position, no second credit",\n' +
  '    again.applied.length===0&&paperAccount.closedPositions.length===1&&paperAccount.balance===10200&&\n' +
  '    paperReconciliationAudit.length===1,\n' +
  '    "applied="+again.applied.length+" closed="+paperAccount.closedPositions.length+" balance="+paperAccount.balance);\n' +
  // Two independent defences, and they fire in different situations. PRIMARY: a restored trade is
  // no longer an unexplained orphan, so it is never a candidate again. SECONDARY: the audit trail,
  // which is what catches the case where the restored position later disappears from the account
  // again -- exactly the JOURNAL_ONLY loss this whole tool exists to repair.
  '  g.record("RECON-14","PRIMARY defence: a restored trade is no longer an orphan, so it cannot be re-selected",\n' +
  '    computePaperLedgerIntegrity().newlyOrphanedAfterReset.every(function(r){return r.tradeId!=="T-1";})&&\n' +
  '    again.skipped.length===0,"no longer a candidate at all");\n' +
  '  paperAccount.closedPositions=paperAccount.closedPositions.filter(function(p){return p.id!=="T-1";});\n' +
  '  const orphanedAgain=computeReconciliationPreview(["T-1"]);\n' +
  '  g.record("RECON-14b","SECONDARY defence: if the restored position is LOST again, the audit trail still blocks a second credit",\n' +
  '    orphanedAgain.items.length===0&&orphanedAgain.skipped.length===1&&/Already reconciled/.test(orphanedAgain.skipped[0].reason),\n' +
  '    "reason="+String((orphanedAgain.skipped[0]||{}).reason).slice(0,42));\n' +
  '  const doubleCredit=applyPaperReconciliation(["T-1"]);\n' +
  '  g.record("RECON-14c","and apply honours that -- the balance is never credited twice for one trade",\n' +
  '    doubleCredit.applied.length===0&&paperAccount.balance===10200,"balance="+paperAccount.balance);\n' +
  // ── incomplete records are never restored even when explicitly requested ──
  '  const inc=applyPaperReconciliation(["T-3"]);\n' +
  '  g.record("RECON-15","an incomplete record is never restored by apply either",\n' +
  '    inc.applied.length===0&&!paperAccount.closedPositions.some(function(p){return p.id==="T-3";}),"T-3 not restored");\n' +
  // ── batch: only the requested ids move ──
  '  resetLedger();\n' +
  '  const batch=applyPaperReconciliation(["T-1","T-2"]);\n' +
  '  g.record("RECON-16","a two-trade reconciliation credits both, once each",\n' +
  '    batch.applied.length===2&&paperAccount.balance===10250&&paperReconciliationAudit.length===2,\n' +
  '    "balance="+paperAccount.balance+" (10000 + 200 + 50) audit="+paperReconciliationAudit.length);\n' +
  '  resetLedger();\n' +
  '  applyPaperReconciliation(["T-2"]);\n' +
  '  g.record("RECON-17","reconciling one orphan leaves the other untouched and still orphaned",\n' +
  '    paperAccount.balance===10050&&computePaperLedgerIntegrity().newlyOrphanedAfterReset.some(function(r){return r.tradeId==="T-1";}),\n' +
  '    "balance="+paperAccount.balance+", T-1 still orphaned");\n' +
  // ── ROLLBACK through the REAL optimistic-concurrency guard ──
  '  resetLedger();\n' +
  '  g.ls["fxhub_paper_version"]="999";\n' +   // storage is newer than this session -> STALE_VERSION
  '  const blocked=applyPaperReconciliation(["T-1"]);\n' +
  '  g.record("RECON-18","a blocked commit reports blocked with a reason rather than claiming success",\n' +
  '    blocked.blocked===true&&blocked.applied.length===0&&typeof blocked.reason==="string"&&blocked.reason.length>0,\n' +
  '    "blocked="+blocked.blocked+" reason="+String(blocked.reason).slice(0,48));\n' +
  '  g.record("RECON-19","and the account is ROLLED BACK -- no position, no balance change, from a failed commit",\n' +
  '    paperAccount.balance===10000&&paperAccount.closedPositions.length===0,\n' +
  '    "balance="+paperAccount.balance+" closed="+paperAccount.closedPositions.length);\n' +
  '  g.record("RECON-20","the audit trail is rolled back too -- no orphaned audit row for a trade that was not restored",\n' +
  '    paperReconciliationAudit.length===0,"audit="+paperReconciliationAudit.length);\n' +
  '  g.record("RECON-21","the trade remains a visible orphan after the failed attempt, not silently lost",\n' +
  '    computePaperLedgerIntegrity().newlyOrphanedAfterReset.some(function(r){return r.tradeId==="T-1";}),"still flagged");\n' +
  // ── the balance-difference diagnostic agrees with the restore ──
  '  resetLedger();\n' +
  '  applyPaperReconciliation(["T-1"]);\n' +
  '  const post=computePaperLedgerIntegrity();\n' +
  '  g.record("RECON-22","after a successful restore the ledger reconciles -- expected and actual balance agree",\n' +
  '    post.balanceDifference===0,"difference="+post.balanceDifference+" expected="+post.expectedBalance+" actual="+post.actualBalance);\n' +
  '  return g;\n})();'
);

try{
  wrapped(g);
  let pass=0,fail=0;
  results.forEach(function(r){
    if(r.pass){pass++;console.log('PASS -- '+r.id+': '+r.desc+(r.detail?'  ['+r.detail+']':''));}
    else{fail++;console.log('FAIL -- '+r.id+': '+r.desc+(r.detail?'  ['+r.detail+']':''));}
  });
  console.log('---');
  console.log(results.length+' fixtures, '+pass+' PASS, '+fail+' FAIL');
}catch(e){
  console.log('EXECUTION ERROR: '+(e&&e.message?e.message:String(e)));
  console.log('---');
  console.log(results.length+' fixtures, 0 PASS, '+(results.length||1)+' FAIL');
}
