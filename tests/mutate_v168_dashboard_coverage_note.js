const fs=require('fs'),cp=require('child_process'),path=require('path');
const SRC=path.resolve(__dirname,'..','index.html');
const original=fs.readFileSync(SRC,'utf8');
const M=[
 ['D1  an unknown denominator renders as "0 closed" (the lie the guard exists to stop)',
  "if(c===null) return{text:'',title:'',hasExclusion:false,closedCount:null,quarantinedCount:q};",
  "if(c===null) return{text:'0 closed',title:'',hasExclusion:false,closedCount:0,quarantinedCount:q};"],
 ['D2  a negative closed count accepted',
  '&&isFinite(closedCount)&&closedCount>=0)?Math.floor(closedCount):null;',
  '&&isFinite(closedCount))?Math.floor(closedCount):null;'],
 ['D3  strings accepted as counts',
  "const c=(typeof closedCount==='number'","const c=(true"],
 ['D4  the exclusion clause dropped entirely',
  "text:c+' closed \\u00b7 '+q+' excluded',","text:c+' closed',"],
 ['D5  hasExclusion always false',              'hasExclusion:true,closedCount:c,quarantinedCount:q};','hasExclusion:false,closedCount:c,quarantinedCount:q};'],
 ['D6  the tooltip no longer says why the record was excluded',
  "q+' closed record(s) failed a trade-integrity rule and are excluded from this figure and '+",
  "q+' records not shown. '+"],
 ['D7  the tooltip no longer says the record is preserved',
  "'from the P&L. They are preserved and inspectable in the journal.'","'from the P&L.'"],
 ['D8  counts not floored (decimals leak into the UI)','Math.floor(quarantinedCount):0;','quarantinedCount:0;'],
 ['D9  a clean book still claims an exclusion',
  "if(!q) return{text:c+' closed',title:'',hasExclusion:false,closedCount:c,quarantinedCount:0};",
  "if(!q) return{text:c+' closed \\u00b7 0 excluded',title:'',hasExclusion:true,closedCount:c,quarantinedCount:0};"],
];
let caught=0;const surv=[];
for(const [n,f,r] of M){
  if(!original.includes(f)){ console.log('SKIP (anchor) '+n); continue; }
  fs.writeFileSync(SRC,original.replace(f,r));
  let failed=false;
  try{ cp.execSync('node '+path.resolve(__dirname,'v168_dashboard_coverage_note_tests.js'),{stdio:'pipe'}); }catch(e){ failed=true; }
  if(failed){caught++;console.log('CAUGHT   '+n);} else {surv.push(n);console.log('SURVIVED '+n);}
}
fs.writeFileSync(SRC,original);
console.log('\ncaught '+caught+'  survived '+surv.length+'  of '+M.length);
if(surv.length){ console.log('\nSURVIVORS:'); surv.forEach(s=>console.log('  - '+s)); process.exit(1); }
console.log('PASS -- all '+caught+' mutations caught');
