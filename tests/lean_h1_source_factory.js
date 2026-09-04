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
function extract(script){
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
  return {names,constants,functions};
}
function sourceFactory(script){
  const extracted=extract(script);
  const program=new vm.Script(extracted.constants+'\nlet alexGZoneState={};let alexGSetupState=[];let alexGLastEvaluatedCloseTime={};\n'+extracted.functions);
  return Object.freeze({names:Object.freeze(extracted.names),create(){
    const realm=vm.createContext({Date});
    program.runInContext(realm);
    return realm;
  }});
}
// Test-only candidate-worker prototype.  Unlike create(), attempts execute in a
// fresh IIFE lexical environment in one already-created VM context.
function buildLexicalAttemptFactory(script){
  const extracted=extract(script), names=extracted.names;
  const returned=names.concat(['RULES_ALEXG','APP_VERSION','STRATEGY_ALEXG']).join(',');
  const source='(function(){\n'+extracted.constants+'\nlet alexGZoneState={};let alexGSetupState=[];let alexGLastEvaluatedCloseTime={};\n'+
    extracted.functions+'\nreturn {'+returned+',state:{alexGZoneState,alexGSetupState,alexGLastEvaluatedCloseTime}};\n})()';
  const program=new vm.Script(source,{filename:'lean_h1_lexical_attempt.generated.js'});
  const dateLimit=8640000000000000;
  function copyFrames(wireFrames){
    const copied={};
    for(const key of ['H1','H4','D','W']){
      const rows=wireFrames&&wireFrames[key];
      if(!Array.isArray(rows)) throw new TypeError('wire frame '+key+' must be an array');
      copied[key]=rows.map((row,index)=>{
        if(!row||!Number.isSafeInteger(row.t)||Math.abs(row.t)>dateLimit)
          throw new RangeError('invalid wire timestamp '+key+'['+index+']');
        // The wire contract owns only scalar OHLC and a numeric timestamp.
        return {o:row.o,h:row.h,l:row.l,c:row.c,t:new Date(row.t)};
      });
    }
    return copied;
  }
  return Object.freeze({names:Object.freeze(names.slice()),source,create(realm){
    if(!vm.isContext(realm)) throw new TypeError('candidate worker realm required');
    return program.runInContext(realm);
  },run(realm,pair,wireFrames){
    const attempt=program.runInContext(realm);
    return attempt.alexGRunSetupEngine(pair,copyFrames(wireFrames));
  },copyFrames});
}
module.exports=sourceFactory;
module.exports.extract=extract;
module.exports.buildLexicalAttemptFactory=buildLexicalAttemptFactory;
