// Self-contained runner for the MOGO-017 Step 2A (forward PAPER execution observability)
// fixture suite. Reads index.html directly and extracts its <script> body itself, following the
// same pattern as run_v126_phase2c_wave1_tests.js -- whose harness this deliberately mirrors,
// because that suite already drives the real engine all the way to a genuine TRADE OPENED.
//
// Run from the project root:
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v017_step2a_pipeline_observability_tests.js
// or simply:
//   tests/run_all.sh   (discovers and runs this automatically)
ObjC.import('Foundation');
function readFile(path){
  const s=$.NSString.stringWithContentsOfFileEncodingError(path,$.NSUTF8StringEncoding,null);
  return ObjC.unwrap(s);
}
function extractScriptBody(html){
  const m=html.match(/<script>([\s\S]*)<\/script>/);
  if(!m) throw new Error('Could not find <script>...</script> body in index.html -- run this from the project root.');
  return m[1];
}
const html=readFile('./index.html');
const appCode=extractScriptBody(html);
const testCode=readFile('./tests/v017_step2a_pipeline_observability_tests.js');

const elMap={};
function makeClassList(){
  const classes=new Set();
  return{
    add:function(c){classes.add(c);},
    remove:function(c){classes.delete(c);},
    toggle:function(c,force){ if(force===undefined){ if(classes.has(c)) classes.delete(c); else classes.add(c); } else if(force) classes.add(c); else classes.delete(c); },
    contains:function(c){return classes.has(c);}
  };
}
function makeStub(){
  return {innerHTML:'',textContent:'',value:'',className:'',style:{},options:[{value:'All'}],width:100,height:100,disabled:false,checked:false,
    classList:makeClassList(),
    getContext:function(){return{clearRect:function(){},beginPath:function(){},moveTo:function(){},lineTo:function(){},stroke:function(){},fillRect:function(){},save:function(){},restore:function(){},setLineDash:function(){},arc:function(){},fill:function(){},closePath:function(){},fillText:function(){},measureText:function(){return{width:0};}};},
    appendChild:function(){},addEventListener:function(){},focus:function(){},setSelectionRange:function(){},
    getBoundingClientRect:function(){return{top:0,left:0,width:0,height:0};}};
}
const lsStore={};
globalThis.document={
  getElementById:function(id){ if(!elMap[id]) elMap[id]=makeStub(); return elMap[id]; },
  querySelector:function(){return null;},
  querySelectorAll:function(){return [];},
  createElement:function(){return makeStub();},
  addEventListener:function(){},
  body:{appendChild:function(){},removeChild:function(){}},
  activeElement:null
};
globalThis.window={devicePixelRatio:1};
globalThis.localStorage={
  getItem:function(k){return Object.prototype.hasOwnProperty.call(lsStore,k)?lsStore[k]:null;},
  setItem:function(k,v){lsStore[k]=v;},
  removeItem:function(k){delete lsStore[k];},
  __keys:function(){return Object.keys(lsStore);},
  __clear:function(){Object.keys(lsStore).forEach(k=>delete lsStore[k]);},
  __isTestStub:function(){return true;}
};
// §18.38: the same in-memory IndexedDB the paper-trading e2e runner installs. Without it the
// evidence platform fails every write here too, so the ALEX capture seam could not be observed
// at all -- which is exactly why its JVM twin had three fixtures and it had none.
(function installMemoryIndexedDB(){
  // §18.37: the FIRST version of this stub DEADLOCKED every evidence write, and the runner comment
  // claiming "the platform captures successfully" was false -- it wrote no artifact because it
  // never COMPLETED. DB.transaction fired `oncomplete` on a microtask at CREATION time, while
  // production attaches its handler later, in evidenceTxDone(tx), after awaiting the request. By
  // then the completion had already fired with oncomplete === null and the promise never settled:
  // evidencePersistTradePackage never returned once in 75 seam calls, and the in-flight flag
  // latched true after the first close. Replacing "no store" with "a store I wrote" traded one
  // blind spot for a worse one, because this one asserted it was working.
  //
  // `oncomplete` is now an ACCESSOR: completion is recorded, and a handler attached AFTER the fact
  // still fires. Completion waits for every request issued on the transaction to settle.
  function req(tx){
    const r={onsuccess:null,onerror:null,result:undefined,error:null};
    if(tx) tx._pending++;
    return r;
  }
  // §18.38 (L3): a failed request now ABORTS its transaction. The previous version called onerror
  // and then still completed the transaction, so evidenceReq's reject path and evidenceTxDone's
  // onerror/onabort paths were DEAD CODE in all 34 suites -- a real quota or disk write failure
  // would have been reported as success and evidenceRecordWriteFailure would never have fired.
  function fire(r,value,err,tx){
    Promise.resolve().then(function(){
      if(err){
        r.error=err;
        if(r.onerror) r.onerror({target:r});
        if(tx){ tx._pending--; tx._fail(err); }
        return;
      }
      r.result=value; if(r.onsuccess) r.onsuccess({target:r});
      if(tx){ tx._pending--; if(tx._pending<=0) tx._settle(); }
    });
  }
  function Store(name,keyPath){ this.name=name; this.keyPath=keyPath; this.rows=new Map(); this.indexes={}; }
  Store.prototype.keyOf=function(v){ return this.keyPath?v[this.keyPath]:undefined; };
  Store.prototype.createIndex=function(n,kp,opts){ this.indexes[n]={keyPath:kp,unique:!!(opts&&opts.unique)}; return {}; };
  function StoreHandle(store,tx){ this.s=store; this.tx=tx; }
  // The ONE semantic production depends on: add() rejects a duplicate key, and a UNIQUE index
  // rejects a duplicate indexed value. The import path's "never overwrite" contract and the
  // duplicate-package protection are both built on exactly this.
  // §18.38 (L1): the previous signature was `function(names)` -- the MODE was ignored entirely, so
  // add/put/delete succeeded on a readonly transaction. In a browser that throws ReadOnlyError and
  // no evidence package is ever stored, which means EVCAP.1/2/3 were passing on a behaviour a real
  // IndexedDB does not have.
  function assertWritable(h){
    if(h.tx&&h.tx._mode!=='readwrite'){
      throw Object.assign(new Error('ReadOnlyError: transaction is '+h.tx._mode),{name:'ReadOnlyError'});
    }
  }
  StoreHandle.prototype.add=function(v){
    assertWritable(this);
    const r=req(this.tx), k=this.s.keyOf(v), s=this.s;
    let dup=this.s.rows.has(k);
    if(!dup){
      Object.keys(s.indexes).forEach(function(n){
        const ix=s.indexes[n]; if(!ix.unique||dup) return;
        const kp=ix.keyPath; if(!kp) return;
        s.rows.forEach(function(row){ if(!dup&&row&&row[kp]!==undefined&&row[kp]===v[kp]) dup=true; });
      });
    }
    if(dup) fire(r,null,Object.assign(new Error('ConstraintError'),{name:'ConstraintError'}),this.tx);
    else { this.s.rows.set(k,v); fire(r,k,null,this.tx); }
    return r;
  };
  StoreHandle.prototype.put=function(v){ assertWritable(this); const r=req(this.tx); this.s.rows.set(this.s.keyOf(v),v); fire(r,this.s.keyOf(v),null,this.tx); return r; };
  StoreHandle.prototype.get=function(k){ const r=req(this.tx); fire(r,this.s.rows.get(k),null,this.tx); return r; };
  StoreHandle.prototype.getAll=function(range,count){
    const r=req(this.tx);
    let vals=Array.from(this.s.rows.values());
    if(range&&typeof range.includes==='function') vals=vals.filter(function(v){ return range.includes(v); });
    if(typeof count==='number') vals=vals.slice(0,count);
    fire(r,vals,null,this.tx); return r;
  };
  StoreHandle.prototype.delete=function(k){ assertWritable(this); const r=req(this.tx); this.s.rows.delete(k); fire(r,undefined,null,this.tx); return r; };
  StoreHandle.prototype.count=function(){ const r=req(this.tx); fire(r,this.s.rows.size,null,this.tx); return r; };
  StoreHandle.prototype.clear=function(){ assertWritable(this); const r=req(this.tx); this.s.rows.clear(); fire(r,undefined,null,this.tx); return r; };
  StoreHandle.prototype.openCursor=function(){
    const r=req(this.tx), rows=Array.from(this.s.rows.values()), tx=this.tx;
    let i=0;
    function step(){
      if(i>=rows.length){ fire(r,null,null,tx); return; }
      const value=rows[i++];
      const cursor={value:value,continue:function(){ tx._pending++; Promise.resolve().then(step); },
        delete:function(){ return {onsuccess:null,onerror:null}; }};
      fire(r,cursor,null,tx);
    }
    step();
    return r;
  };
  StoreHandle.prototype.index=function(n){
    const s=this.s, tx=this.tx, kp=(s.indexes[n]&&s.indexes[n].keyPath)||null;
    return {
      get:function(k){ const r=req(tx); let hit;
        s.rows.forEach(function(v){ if(hit===undefined&&kp&&v&&v[kp]===k) hit=v; });
        fire(r,hit,null,tx); return r; },
      // §18.38 (L4): range and count were both IGNORED, and production depends on them:
      // index('bySeq').getAll(IDBKeyRange.lowerBound(0), plan.evictCount). Rows are also ordered by
      // the index key, as a real index is -- insertion order is not the same thing.
      getAll:function(range,count){
        const r=req(tx);
        let vals=Array.from(s.rows.values());
        if(kp) vals=vals.slice().sort(function(a,b){ return a[kp]<b[kp]?-1:(a[kp]>b[kp]?1:0); });
        if(range&&typeof range.includes==='function'&&kp) vals=vals.filter(function(v){ return range.includes(v[kp]); });
        if(typeof count==='number') vals=vals.slice(0,count);
        fire(r,vals,null,tx); return r;
      },
      openCursor:function(){ const r=req(tx); fire(r,null,null,tx); return r; }
    };
  };
  function DB(){ this.stores={}; }
  Object.defineProperty(DB.prototype,'objectStoreNames',{get:function(){
    const self=this; return {contains:function(n){ return !!self.stores[n]; }};
  }});
  DB.prototype.createObjectStore=function(name,opts){
    const st=new Store(name,opts&&opts.keyPath); this.stores[name]=st; return st;
  };
  DB.prototype.transaction=function(names,mode){
    const self=this;
    const tx={_pending:0,_done:false,_oncomplete:null,onerror:null,onabort:null,error:null,
      _scope:(Array.isArray(names)?names:[names]),_mode:mode||'readonly',
      _fail:function(err){
        if(tx._done) return;
        tx._done=true; tx.error=err;
        if(tx.onerror) tx.onerror({target:tx});
        if(tx.onabort) tx.onabort({target:tx});
      },
      objectStore:function(n){
        // §18.38 (L2): this checked only that the store EXISTS, while the comment above it claimed
        // it enforced the transaction's SCOPE. It did not -- a comment stronger than the code
        // beneath it, in my own harness. A real IndexedDB throws NotFoundError for a store outside
        // the scope named at transaction() time, and production reading `packages` from a
        // [meta]-scoped transaction would take the export banner and reconciliation down with it.
        if(!self.stores[n]) throw Object.assign(new Error('NotFoundError: no object store named '+n),{name:'NotFoundError'});
        if(tx._scope.indexOf(n)===-1) throw Object.assign(new Error('NotFoundError: '+n+' is outside this transaction scope'),{name:'NotFoundError'});
        return new StoreHandle(self.stores[n],tx);
      },
      abort:function(){ tx._done=true; if(tx.onabort) tx.onabort({target:tx}); },
      _settle:function(){
        if(tx._done) return;
        tx._done=true;
        if(tx._oncomplete) tx._oncomplete({target:tx});
      }};
    Object.defineProperty(tx,'oncomplete',{
      get:function(){ return tx._oncomplete; },
      set:function(fn){
        tx._oncomplete=fn;
        // Attached AFTER completion -- which is exactly what evidenceTxDone does. Fire anyway.
        if(tx._done&&fn) Promise.resolve().then(function(){ fn({target:tx}); });
      }
    });
    // A transaction with no requests still completes.
    Promise.resolve().then(function(){ if(tx._pending<=0) tx._settle(); });
    return tx;
  };
  DB.prototype.close=function(){};
  const db=new DB();
  globalThis.indexedDB={
    // §18.38: marked, so 2A.43 can assert what it actually means -- that this process never touches
    // the operator's real evidence store -- rather than asserting the harness has no store at all.
    __isTestStub:function(){ return true; },
    open:function(){
      const r={onsuccess:null,onerror:null,onupgradeneeded:null,result:undefined,error:null};
      Promise.resolve().then(function(){
        r.result=db;
        if(r.onupgradeneeded) r.onupgradeneeded({target:r,oldVersion:0});
        if(r.onsuccess) r.onsuccess({target:r});
      });
      return r;
    },
    deleteDatabase:function(){ const r={onsuccess:null,onerror:null}; Promise.resolve().then(function(){ if(r.onsuccess) r.onsuccess({target:r}); }); return r; }
  };
  // Production calls IDBKeyRange for observation retention; without it that path throws.
  globalThis.IDBKeyRange={
    upperBound:function(v,open){ return {includes:function(x){ return open?x<v:x<=v; }}; },
    lowerBound:function(v,open){ return {includes:function(x){ return open?x>v:x>=v; }}; },
    bound:function(a,b){ return {includes:function(x){ return x>=a&&x<=b; }}; },
    only:function(v){ return {includes:function(x){ return x===v; }}; }
  };
})();

globalThis.fetch=function(){return Promise.reject(new Error('no network'));};
globalThis.alert=function(){};
globalThis.confirm=function(){return true;};
globalThis.Blob=function(parts,opts){return{parts,opts};};
globalThis.URL={createObjectURL:function(){return 'blob:stub';},revokeObjectURL:function(){}};
let __fakeTimerId=0;
globalThis.setTimeout=function(){return ++__fakeTimerId;};globalThis.clearTimeout=function(){};
globalThis.setInterval=function(){return ++__fakeTimerId;};globalThis.clearInterval=function(){};
globalThis.ResizeObserver=function(){return{observe:function(){},disconnect:function(){}};};
globalThis.LightweightCharts={LineStyle:{Solid:0,Dashed:1,Dotted:2},CrosshairMode:{Normal:0}};
globalThis.Notification=undefined;

// ── MOGO-002.8A DETERMINISM FIX ──────────────────────────────────────────────
// ALEX v1.1 adds a Monday-Wednesday entry-eligibility gate (ALEX_V11_001), which is
// evaluated against the live wall clock. Every fixture below that opens a real trade
// end-to-end would therefore PASS Mon/Tue/Wed and FAIL Thu/Fri/Sat/Sun with no code
// change whatsoever -- a date-dependent regression suite.
//
// This suite exists to verify DECISION-EVENT EMISSION, not day-of-week eligibility
// (which has its own dedicated coverage in v127_alex_v11_release_tests.js, fixtures
// B1-B13). Pinning the clock to a fixed eligible Monday keeps every assertion below
// testing exactly what it was written to test, deterministically, on any day.
//
// NOT A PRODUCTION CHANGE: this pins the clock for this test process only. Zero
// assertions are modified. Zero production code is modified.
const __PINNED_NOW=Date.UTC(2026,0,5,12,0,0); // Monday 2026-01-05 12:00 UTC
const __RealDate=Date;
function __PinnedDate(){
  if(arguments.length===0) return new __RealDate(__PINNED_NOW);
  if(arguments.length===1) return new __RealDate(arguments[0]);
  return new __RealDate(arguments[0],arguments[1],arguments[2]||1,arguments[3]||0,arguments[4]||0,arguments[5]||0,arguments[6]||0);
}
__PinnedDate.now=function(){return __PINNED_NOW;};
__PinnedDate.parse=__RealDate.parse;
__PinnedDate.UTC=__RealDate.UTC;
__PinnedDate.prototype=__RealDate.prototype;
globalThis.Date=__PinnedDate;

const g={};
const wrapped = new Function('g',
  appCode + '\n' + testCode + '\n' +
  // -- ALEX execution path under test (real, unmodified) --
  'g.alexGEvaluatePairForLiveSetups=alexGEvaluatePairForLiveSetups;' +
  // §18.34 F4: the position constructor, so a fixture can drive the tradeId duplicate guard
  // directly rather than trying to reproduce a full second qualification.
  'g.alexGConstructLivePosition=alexGConstructLivePosition;' +
  'g.alexGAttemptOpenLivePosition=alexGAttemptOpenLivePosition;' +
  'g.alexGConstructLivePosition=alexGConstructLivePosition;' +   // PROTECTED -- called, never edited
  'g.alexGCheckLivePositions=alexGCheckLivePositions;' +
  // §18.38 B1: the ALEX evidence-capture seam had NO behavioural coverage while its JVM twin had
  // three fixtures. ALEX is the arm actually running live paper trades, so its audit-capture path
  // -- the deliverable of this milestone -- could stop producing packages with the whole gate green.
  'g.evidenceListPackages=evidenceListPackages;' +
  'g.alexGLiveSignalId=alexGLiveSignalId;' +
  // -- MOGO-017 Step 2A instrumentation under test --
  'g.alexGRecordPipelineStage=alexGRecordPipelineStage;' +
  'g.drainPipeline=alexGDrainPipelineObservations;' +
  'g.pipelineBufferLength=function(){return alexGPipelineObservationBuffer.length;};' +
  'g.getPipelineBufferMax=function(){return EVIDENCE_PIPELINE_BUFFER_MAX;};' +
  'g.fillPipelineBufferToCap=function(){' +
  '  alexGPipelineObservationBuffer=[];' +
  '  for(var i=0;i<EVIDENCE_PIPELINE_BUFFER_MAX;i++) alexGPipelineObservationBuffer.push({kind:"PIPELINE",stage:"FILLER"});' +
  '};' +
  // -- MOGO-013 observation schema (real, unmodified) --
  'g.evidenceBuildPipelineObservation=evidenceBuildPipelineObservation;' +
  'g.evidenceObservationNaturalKey=evidenceObservationNaturalKey;' +
  'g.getObservationKinds=function(){return EVIDENCE_OBSERVATION_KINDS.slice();};' +
  // The durable writer is COUNTED, never allowed to run: this process has no IndexedDB, and the
  // isolation fixtures assert the count stayed at zero. Wrapping it here is what turns "it cannot
  // have written anything" from an argument into a measurement.
  'var __obsWriteAttempts=0;' +
  'var __realEvidencePutObservation=evidencePutObservation;' +
  'evidencePutObservation=function(){ __obsWriteAttempts++; return Promise.resolve({ok:false,reason:"TEST_HARNESS_NO_STORE"}); };' +
  'g.getObservationWriteAttempts=function(){return __obsWriteAttempts;};' +
  'void __realEvidencePutObservation;' +
  // -- Decision Event Bus (real, unmodified) --
  'g.emitDecisionEvent=emitDecisionEvent;' +
  'g.getDecisionEvents=getDecisionEvents;' +
  'g.clearDecisionEvents=clearDecisionEvents;' +
  // -- state get/set (ALEX) --
  'g.getAlexGSetupState=function(){return alexGSetupState;};g.setAlexGSetupState=function(v){alexGSetupState=v;};' +
  'g.getAlexGZoneState=function(){return alexGZoneState;};g.setAlexGZoneState=function(v){alexGZoneState=v;};' +
  'g.getAlexGLastEvaluatedCloseTime=function(){return alexGLastEvaluatedCloseTime;};g.setAlexGLastEvaluatedCloseTime=function(v){alexGLastEvaluatedCloseTime=v;};' +
  'g.getAlexGLiveSetupStatuses=function(){return alexGLiveSetupStatuses;};g.resetLiveDecisionState=function(){alexGResetLiveDecisionState();};g.setAlexGLiveSetupStatuses=function(v){alexGLiveSetupStatuses=v;};' +
  'g.getAlexGAccount=function(){return alexGAccount;};g.setAlexGAccount=function(v){alexGAccount=v;};' +
  'g.getAlexGJournalEntries=function(){return alexGJournalEntries;};g.setAlexGJournalEntries=function(v){alexGJournalEntries=v;};' +
  'g.getAlexGAutoTrading=function(){return alexGAutoTrading;};g.setAlexGAutoTrading=function(v){alexGAutoTrading=v;};' +
  'g.setAlexGAccountKnownVersion=function(v){alexGAccountKnownVersion=v;};' +
  // -- localStorage helpers --
  'g.clearLocalStorage=function(){localStorage.__clear();};' +
  // ── DETERMINISM, carried over verbatim from the v126 runner and for the same reasons ──
  // MOGO-002.8B suspends A_repeatedReaction from opening LIVE paper positions. Every fixture
  // here that opens a trade end to end builds an A_repeatedReaction setup, so all of them would
  // be correctly withheld by that gate. This suite exists to verify OBSERVABILITY, not setup
  // execution policy (covered by v127 fixtures K1-K23). Disabling the suspension for THIS TEST
  // PROCESS ONLY keeps every assertion testing what it was written to test.
  //
  // NOT A PRODUCTION CHANGE and NOT a weakening of the gate: the production default remains
  // setupSuspensionEnabled:true, asserted by v127 fixture K9. Zero production code is modified.
  'RULES_ALEXG_V11.v11Config.setupSuspensionEnabled=false;' +
  'return runStep2APipelineObservabilityFixtures(g);'
);
wrapped(g).then(function(results){
  results.forEach(r=>{
    const tag = r.pass===null ? 'NOTE' : (r.pass?'PASS':'FAIL');
    console.log(tag+' -- '+r.name+(r.detail?' ('+r.detail+')':''));
  });
  const executed=results.filter(r=>r.pass!==null);
  const failCount=executed.filter(r=>!r.pass).length;
  console.log('---');
  console.log(failCount===0?('ALL MOGO-017 STEP 2A PIPELINE OBSERVABILITY FIXTURES PASSED ('+executed.length+' executed)'):('FAILURES: '+failCount+'/'+executed.length));
}).catch(function(e){
  console.log('RUNNER ERROR: '+(e&&e.message?e.message:String(e)));
  if(e&&e.stack) console.log(e.stack);
});
