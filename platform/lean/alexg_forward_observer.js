// Disabled, standalone, read-only selector. Deliberately not loaded by index.html.
const MOGO_LEAN_FORWARD_OBSERVER_DEFAULT_ENABLED=false;
function alexGObserveNewLeanBreakRetest(input){
  const refuse=code=>{const e=new Error(code);e.code=code;throw e;};
  if(!input||input.enabled!==true) refuse('REFUSE_OBSERVER_DISABLED');
  const before=input.beforeSetups,after=input.afterSetups;
  if(!Array.isArray(before)||!Array.isArray(after)||before===after) refuse('REFUSE_OBSERVER_SNAPSHOTS');
  const identity=s=>{if(!s||typeof s.setupId!=='string'||!s.setupId) refuse('REFUSE_OBSERVER_SETUP_IDENTITY');return s.setupId;};
  const seen=new Set();before.forEach(s=>{const id=identity(s);if(seen.has(id)) refuse('REFUSE_OBSERVER_DUPLICATE_IDENTITY');seen.add(id);});
  const ids=new Set(),found=[];after.forEach(s=>{const id=identity(s);if(ids.has(id)) refuse('REFUSE_OBSERVER_DUPLICATE_IDENTITY');ids.add(id);if(!seen.has(id)&&s.setupType==='B_breakRetest') found.push(s);});
  if(!found.length) return null;
  if(found.length!==1) refuse('REFUSE_OBSERVER_AMBIGUOUS_NEW_SETUP');
  return found[0];
}

// Builds only the explicit argument object accepted by alexGBuildLeanZoneRequestV2.
// It does not call that emitter and therefore cannot export on its own.
function alexGBuildObservedLeanEmitterInput(input){
  const refuse=code=>{const e=new Error(code);e.code=code;throw e;};
  if(!input||input.enabled!==true) refuse('REFUSE_OBSERVER_HANDOFF_DISABLED');
  const setup=input.observedSetup;
  if(!setup||setup.setupType!=='B_breakRetest'||typeof setup.setupId!=='string'||!setup.setupId)
    refuse('REFUSE_OBSERVER_HANDOFF_SETUP');
  if(!Array.isArray(input.afterSetups)||input.afterSetups.indexOf(setup)<0)
    refuse('REFUSE_OBSERVER_HANDOFF_PROVENANCE');
  if(!input.zone||input.zone.id!==setup.zoneId) refuse('REFUSE_OBSERVER_HANDOFF_ZONE');
  if(!Array.isArray(input.bars)||input.bars.length<2) refuse('REFUSE_OBSERVER_HANDOFF_BARS');
  if(!input.retestTouch||input.retestTouch.reactionId!==setup.reactionId)
    refuse('REFUSE_OBSERVER_HANDOFF_RETEST');
  for(const key of ['identity','versions','dataset','config'])
    if(!input[key]||typeof input[key]!=='object') refuse('REFUSE_OBSERVER_HANDOFF_METADATA');
  return {enabled:true,setup,zone:input.zone,bars:input.bars,setupCandles:input.bars,
    retestTouch:input.retestTouch,identity:input.identity,versions:input.versions,
    dataset:input.dataset,config:input.config};
}

// Complete in-memory composition seam. The reviewed emitter must be supplied as
// a dependency; this module neither imports nor discovers application state.
function alexGObserveAndBuildLeanExport(input,deps){
  const refuse=code=>{const e=new Error(code);e.code=code;throw e;};
  if(!input||input.enabled!==true) refuse('REFUSE_OBSERVER_EXPORT_DISABLED');
  if(!deps||typeof deps.emitLeanZoneRequestV2!=='function')
    refuse('REFUSE_OBSERVER_EXPORT_DEPENDENCY');
  const observedSetup=alexGObserveNewLeanBreakRetest({enabled:true,
    beforeSetups:input.beforeSetups,afterSetups:input.afterSetups});
  if(observedSetup===null) return null;
  const emitterInput=alexGBuildObservedLeanEmitterInput({...input,enabled:true,observedSetup});
  return deps.emitLeanZoneRequestV2(emitterInput,deps.emitterDeps);
}
// Disabled, bounded caller-owned polling state.  This is intentionally only a
// convenience around the explicit observer/emitter seam above: it neither
// proves that a setup came from the engine nor that supplied snapshots are live.
const MOGO_LEAN_FORWARD_OBSERVER_SESSION_MAX_SNAPSHOT_SETUPS=1024;
function alexGCreateDelayedLeanExportSession(deps,options){
  const refuse=code=>{const e=new Error(code);e.code=code;throw e;};
  const requested=options&&options.maxSnapshotSetups;
  if(requested!==undefined&&(!Number.isInteger(requested)||requested<1||requested>MOGO_LEAN_FORWARD_OBSERVER_SESSION_MAX_SNAPSHOT_SETUPS))
    refuse('REFUSE_OBSERVER_SESSION_LIMIT');
  const limit=requested===undefined?MOGO_LEAN_FORWARD_OBSERVER_SESSION_MAX_SNAPSHOT_SETUPS:requested;
  let baseline=null,pending=null;
  const pendingFields=['pair','timeframe','reactionId','breakCycleId','brokenDirection','qualificationTimestamp'];
  const snapshot=items=>{
    if(!Array.isArray(items)||items.length>limit) refuse('REFUSE_OBSERVER_SESSION_SNAPSHOT_LIMIT');
    const ids=new Set();
    return items.map(setup=>{
      if(!setup||typeof setup.setupId!=='string'||!setup.setupId) refuse('REFUSE_OBSERVER_SETUP_IDENTITY');
      if(ids.has(setup.setupId)) refuse('REFUSE_OBSERVER_DUPLICATE_IDENTITY');
      ids.add(setup.setupId);
      // Copy only selector/pending identity facts; never retain caller records.
      const copy={setupId:setup.setupId,setupType:setup.setupType};
      pendingFields.forEach(key=>{if(Object.prototype.hasOwnProperty.call(setup,key)) copy[key]=setup[key];});
      return copy;
    });
  };
  const samePending=(setup,fingerprint)=>pendingFields.every(key=>{
    const had=Object.prototype.hasOwnProperty.call(fingerprint,key);
    return had===Object.prototype.hasOwnProperty.call(setup,key)&&(!had||setup[key]===fingerprint[key]);
  });
  const run=input=>{
    // Disabled calls deliberately do not validate, emit, or change the baseline.
    if(!input||input.enabled!==true) return null;
    const current=snapshot(input.afterSetups);
    if(baseline===null){ baseline=current; return null; }
    let observed;
    if(pending){
      const currentPending=input.afterSetups.find(setup=>setup&&setup.setupId===pending.setupId);
      if(!currentPending){
        const replacement=input.afterSetups.find(setup=>setup&&setup.setupType==='B_breakRetest');
        refuse(replacement?'REFUSE_OBSERVER_PENDING_SUBSTITUTION':'REFUSE_OBSERVER_PENDING_MISSING');
      }
      if(currentPending.setupType!=='B_breakRetest'||!samePending(currentPending,pending))
        refuse('REFUSE_OBSERVER_PENDING_IDENTITY');
    }
    observed=alexGObserveNewLeanBreakRetest({enabled:true,beforeSetups:baseline,afterSetups:input.afterSetups});
    if(pending){
      if(observed===null) refuse('REFUSE_OBSERVER_PENDING_MISSING');
      if(observed.setupId!==pending.setupId) refuse('REFUSE_OBSERVER_PENDING_SUBSTITUTION');
    }
    try{
      // The optional resolver is for the engine-capture adapter below.  It is
      // invoked only after the selector chose the exact engine-owned setup.
      // Existing callers retain the original explicit handoff fields.
      const resolved=observed!==null&&typeof input.resolveObserved==='function'
        ?input.resolveObserved(observed):input;
      const output=observed===null?null:alexGObserveAndBuildLeanExport({...resolved,enabled:true,beforeSetups:baseline},deps);
      baseline=current; pending=null;
      return output;
    }catch(error){
      if(error&&error.code==='REFUSE_QUALIFICATION_INDEX'&&observed){
        pending=snapshot([observed])[0];
        return null;
      }
      throw error;
    }
  };
  return Object.freeze({run});
}
// Disabled, standalone synchronous adapter.  It calls a deliberately supplied
// engine with one internally selected timeframe array and derives every setup,
// zone and touch handoff fact from that returned result. It retains bounded
// copied OHLC facts for the preceding accepted window, never caller objects.
// The supplied engine is H1-master-clock driven.  Higher timeframes cannot be
// captured here because this adapter intentionally supplies no H1 surrogate.
// Provenance is relative to the explicitly trusted synchronous engine dependency;
// this does not certify feed freshness, engine-state isolation or global novelty.
// Deliberate invocation may change that engine's own state; this adapter adds no trading calls.
const MOGO_LEAN_FORWARD_OBSERVER_ENGINE_CAPTURE_TIMEFRAMES=Object.freeze(['H1']);
function alexGCreateSynchronousLeanEngineExportSession(deps,options){
  const refuse=code=>{const e=new Error(code);e.code=code;throw e;};
  if(!deps||typeof deps.runLeanSetupEngine!=='function'||typeof deps.emitLeanZoneRequestV2!=='function')
    refuse('REFUSE_OBSERVER_CAPTURE_DEPENDENCY');
  const delayed=alexGCreateDelayedLeanExportSession({emitLeanZoneRequestV2:deps.emitLeanZoneRequestV2,
    emitterDeps:deps.emitterDeps},options);
  let pinned=null,acceptedEndpointUtcMs=null,acceptedClosedBars=new Map(),acceptedTimestamps=null;
  const forbidden=['afterSetups','beforeSetups','zone','retestTouch','bars','setupCandles','resolveObserved'];
  const run=input=>{
    // Disabled calls do not invoke the engine or establish capture identity.
    if(!input||input.enabled!==true) return null;
    forbidden.forEach(key=>{if(Object.prototype.hasOwnProperty.call(input,key)) refuse('REFUSE_OBSERVER_CAPTURE_CALLER_STATE');});
    const pair=input.pair,timeframe=input.timeframe,candles=input.candles;
    if(typeof pair!=='string'||!pair||MOGO_LEAN_FORWARD_OBSERVER_ENGINE_CAPTURE_TIMEFRAMES.indexOf(timeframe)<0||!Array.isArray(candles)||candles.length<2||candles.length>10000)
      refuse('REFUSE_OBSERVER_CAPTURE_INPUT');
    // This is ordering/provenance validation only, not a wall-clock freshness
    // claim.  Equal endpoints remain allowed so a pending export can retry.
    let endpointUtcMs;
    const timestamps=[];
    for(let index=0;index<candles.length;index++){
      const candle=candles[index];
      const timestamp=candle&&candle.t;
      const utcMs=timestamp instanceof Date?timestamp.getTime():timestamp;
      if(!Number.isSafeInteger(utcMs)||(index>0&&utcMs<=endpointUtcMs))
        refuse('REFUSE_OBSERVER_CAPTURE_CANDLE_TIMESTAMPS');
      endpointUtcMs=utcMs;
      timestamps.push(utcMs);
    }
    if(acceptedEndpointUtcMs!==null&&endpointUtcMs<acceptedEndpointUtcMs)
      refuse('REFUSE_OBSERVER_CAPTURE_STALE_SNAPSHOT');
    if(pinned&& (pinned.pair!==pair||pinned.timeframe!==timeframe)) refuse('REFUSE_OBSERVER_CAPTURE_IDENTITY');
    // A new window must retain an exact suffix of the accepted window through
    // its endpoint. Permit leading warmup eviction, never insertion/deletion
    // within overlap or silent priming after a disconnected snapshot.
    if(acceptedTimestamps!==null){
      const start=acceptedTimestamps.indexOf(timestamps[0]);
      if(start<0) refuse('REFUSE_OBSERVER_CAPTURE_DISCONTINUITY');
      const overlap=acceptedTimestamps.length-start;
      if(timestamps.length<overlap||acceptedTimestamps.slice(start).some((t,i)=>t!==timestamps[i]))
        refuse('REFUSE_OBSERVER_CAPTURE_DISCONTINUITY');
    }
    // Deliberately conservative H1-only policy: without a verified market
    // calendar, any gap (including a possible market closure) is unsupported.
    // Do not synthesize candles, skip the gap, or reset the session automatically.
    if(timestamps.some((t,i)=>i>0&&t-timestamps[i-1]!==3600000))
      refuse('REFUSE_OBSERVER_CAPTURE_UNSUPPORTED_GAP');
    // The final candle is the engine's unclosed sentinel: allow it to update
    // until a successor arrives. Compare all overlapping previously closed
    // candles by timestamp, not array offset (warmup eviction shifts indices).
    // This bounded window check is not a complete feed continuity certificate.
    const closedBars=new Map();
    for(let index=0;index<candles.length;index++){
      const candle=candles[index],utcMs=candle.t instanceof Date?candle.t.getTime():candle.t;
      const facts=['o','h','l','c'].map(key=>candle[key]);
      if(!facts.every(value=>typeof value==='number'&&Number.isFinite(value)))
        refuse('REFUSE_OBSERVER_CAPTURE_CANDLE_VALUES');
      const prior=acceptedClosedBars.get(utcMs);
      if(prior&&facts.some((value,i)=>value!==prior[i]))
        refuse('REFUSE_OBSERVER_CAPTURE_REVISED_HISTORY');
      if(index<candles.length-1) closedBars.set(utcMs,facts);
    }
    const frames={H1:[],H4:[],D:[],W:[]}; frames[timeframe]=candles;
    const result=deps.runLeanSetupEngine(pair,frames);
    if(!result||typeof result!=='object'||typeof result.then==='function'||!Array.isArray(result.setups)||!result.zones||typeof result.zones!=='object')
      refuse('REFUSE_OBSERVER_CAPTURE_ENGINE_RESULT');
    // Refuse rather than silently mixing a foreign engine snapshot into the
    // delayed baseline.  The adapter owns one pinned pair/timeframe only.
    result.setups.forEach(setup=>{
      if(!setup||setup.pair!==pair||setup.timeframe!==timeframe)
        refuse('REFUSE_OBSERVER_CAPTURE_ENGINE_IDENTITY');
    });
    const timeframeZones=result.zones[timeframe];
    if(!timeframeZones||!Array.isArray(timeframeZones.validatedZones)) refuse('REFUSE_OBSERVER_CAPTURE_ENGINE_RESULT');
    const identity=input.identity&&typeof input.identity==='object'?{...input.identity,pair,timeframe}:{pair,timeframe};
    const handoff={enabled:true,afterSetups:result.setups,identity,versions:input.versions,dataset:input.dataset,config:input.config,
      resolveObserved:setup=>{
        const zones=timeframeZones.validatedZones.filter(item=>item&&item.id===setup.zoneId);
        if(zones.length!==1) refuse('REFUSE_OBSERVER_CAPTURE_ZONE');
        const zone=zones[0];
        const touches=Array.isArray(zone.touches)?zone.touches.filter(item=>item&&item.reactionId===setup.reactionId):[];
        if(touches.length!==1) refuse('REFUSE_OBSERVER_CAPTURE_RETEST');
        const retestTouch=touches[0];
        return {afterSetups:result.setups,zone,bars:candles,retestTouch,identity,versions:input.versions,
          dataset:input.dataset,config:input.config};
      }};
    const output=delayed.run(handoff);
    if(!pinned) pinned=Object.freeze({pair,timeframe});
    acceptedEndpointUtcMs=endpointUtcMs;
    acceptedClosedBars=closedBars;
    acceptedTimestamps=timestamps;
    return output;
  };
  return Object.freeze({run});
}
const MOGO_LEAN_FORWARD_OBSERVER_API=Object.freeze({alexGObserveNewLeanBreakRetest,
  alexGBuildObservedLeanEmitterInput,alexGObserveAndBuildLeanExport,
  alexGCreateDelayedLeanExportSession,MOGO_LEAN_FORWARD_OBSERVER_DEFAULT_ENABLED,
  MOGO_LEAN_FORWARD_OBSERVER_SESSION_MAX_SNAPSHOT_SETUPS,
  MOGO_LEAN_FORWARD_OBSERVER_ENGINE_CAPTURE_TIMEFRAMES,
  alexGCreateSynchronousLeanEngineExportSession});
if(typeof module!=='undefined'&&module.exports) module.exports=MOGO_LEAN_FORWARD_OBSERVER_API;
if(typeof globalThis!=='undefined') globalThis.MogoLeanForwardObserver=MOGO_LEAN_FORWARD_OBSERVER_API;
