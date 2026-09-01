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
module.exports={alexGObserveNewLeanBreakRetest,MOGO_LEAN_FORWARD_OBSERVER_DEFAULT_ENABLED};
