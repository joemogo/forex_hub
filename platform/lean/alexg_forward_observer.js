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
module.exports={alexGObserveNewLeanBreakRetest,alexGBuildObservedLeanEmitterInput,MOGO_LEAN_FORWARD_OBSERVER_DEFAULT_ENABLED};
