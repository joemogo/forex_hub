// Test-only source extraction for the reviewed index.html layout, not a JS parser
// or production loader. No full-app evaluation, IO, or shared engine state.
'use strict';
const vm=require('vm');
const HELPERS=['getCandleCloseTime','precomputeCloseTimes','calcATR','pipSize','getSession','isPreferredTradingDay','snapshotAlexGConfig'];
function uniqueMatch(source,pattern,label){
  const matches=[...source.matchAll(pattern)];
  if(matches.length!==1) throw new Error('source declaration missing or ambiguous: '+label);
  return matches[0][0];
}
function functionSource(source,name){
  // Reviewed declarations are one line, or end with a column-zero brace.
  return uniqueMatch(source,new RegExp('^function '+name+'\\([^\\n]*\\{(?:[^\\n]*\\}[^\\n]*$|[\\s\\S]*?^\\})','gm'),name);
}
module.exports=function sourceFactory(script){
  const start=script.indexOf('function alexGFindSwingPoints(');
  const end=script.indexOf('// MOGO_LEAN_PRODUCTION_EMITTER_SEAM_START');
  if(start<0||end<=start) throw new Error('engine source boundary missing');
  const phaseNames=[...script.slice(start,end).matchAll(/^function (\w+)\(/gm)].map(m=>m[1]);
  if(phaseNames.length!==29) throw new Error('engine declaration inventory changed');
  const names=[...phaseNames,...HELPERS];
  const functions=names.map(name=>functionSource(script,name)).join('\n');
  const constants=[
    uniqueMatch(script,/^const RULES_ALEXG=\{[\s\S]*?^\};/gm,'RULES_ALEXG'),
    uniqueMatch(script,/^const APP_VERSION='[^'\n]*';$/gm,'APP_VERSION'),
    uniqueMatch(script,/^const STRATEGY_ALEXG='[^'\n]*';$/gm,'STRATEGY_ALEXG')
  ].join('\n');
  const program=new vm.Script(constants+'\nlet alexGZoneState={};let alexGSetupState=[];let alexGLastEvaluatedCloseTime={};\n'+functions);
  return Object.freeze({names:Object.freeze(names),create(){
    const realm=vm.createContext({Date});
    program.runInContext(realm);
    return realm;
  }});
};
