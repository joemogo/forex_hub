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
      const output=observed===null?null:alexGObserveAndBuildLeanExport({...input,enabled:true,beforeSetups:baseline},deps);
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
const MOGO_LEAN_FORWARD_OBSERVER_API=Object.freeze({alexGObserveNewLeanBreakRetest,
  alexGBuildObservedLeanEmitterInput,alexGObserveAndBuildLeanExport,
  alexGCreateDelayedLeanExportSession,MOGO_LEAN_FORWARD_OBSERVER_DEFAULT_ENABLED,
  MOGO_LEAN_FORWARD_OBSERVER_SESSION_MAX_SNAPSHOT_SETUPS});
if(typeof module!=='undefined'&&module.exports) module.exports=MOGO_LEAN_FORWARD_OBSERVER_API;
if(typeof globalThis!=='undefined') globalThis.MogoLeanForwardObserver=MOGO_LEAN_FORWARD_OBSERVER_API;
