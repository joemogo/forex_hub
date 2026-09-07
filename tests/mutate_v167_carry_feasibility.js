const fs=require('fs'),cp=require('child_process'),path=require('path');
const SRC=path.resolve(__dirname,'..','index.html');
const original=fs.readFileSync(SRC,'utf8');
const M=[
 ['C1  the naive isFinite guard restored (a missing rate becomes 0% -> "no markup")',
  'if(L===null||S===null) return{ok:false','if(!isFinite(L)||!isFinite(S)) return{ok:false'],
 ['C2  markup sign flipped',            'const markup=-(L+S);','const markup=(L+S);'],
 ['C3  differential uses the SUM instead of the difference',
  'const differential=(L-S)/2;','const differential=(L+S)/2;'],
 ['C4  bestRate takes the LONG side unconditionally',
  'const bestRate=Math.max(L,S);','const bestRate=L;'],
 ['C5  the death condition tests the DIFFERENTIAL rather than what you actually receive',
  'paysNothingEitherWay:(bestRate<=0)','paysNothingEitherWay:(differential<=0)'],
 ['C6  the death flag fires on an EMPTY book (no data reported as a finding)',
  'everyInstrumentCostsMoneyEitherWay:(n>0&&payingAnything.length===0)',
  'everyInstrumentCostsMoneyEitherWay:(payingAnything.length===0)'],
 ['C7  ranking by differential rather than by receivable rate',
  'rows.sort(function(a,b){ return b.bestRate-a.bestRate; });',
  'rows.sort(function(a,b){ return b.differential-a.differential; });'],
 ['C8  instruments without a financing block silently dropped',
  "if(!name||!f){ skipped.push({instrument:name||'?',reason:'NO_FINANCING_BLOCK'}); return; }",
  'if(!name||!f){ return; }'],
 ['C9  a zero differential divides instead of reporting null',
  'markupShareOfDifferential:(Math.abs(differential)>1e-9)?(markup/Math.abs(differential)):null,',
  'markupShareOfDifferential:(markup/Math.abs(differential)),'],
 ['C10 strings no longer parsed (OANDA returns decimal strings)',
  "if(typeof v==='string'){","if(false){"],
 ['C11 the read-only / death-condition disclosure deleted',
  'THE DEATH CONDITION IS EXPLICIT','The death condition is implied'],
 ['C12 median markup taken from the unsorted list',
  'const markups=rows.map(function(r){ return r.markup; }).sort(function(a,b){ return a-b; });',
  'const markups=rows.map(function(r){ return r.markup; });'],
];
let caught=0;const surv=[];
for(const [n,f,r] of M){
  if(!original.includes(f)){ console.log('SKIP (anchor) '+n); continue; }
  fs.writeFileSync(SRC,original.replace(f,r));
  let failed=false;
  try{ cp.execSync('node '+path.resolve(__dirname,'v167_carry_feasibility_tests.js'),{stdio:'pipe'}); }catch(e){ failed=true; }
  if(failed){ caught++; console.log('CAUGHT   '+n); } else { surv.push(n); console.log('SURVIVED '+n); }
}
fs.writeFileSync(SRC,original);
console.log('\ncaught '+caught+'  survived '+surv.length+'  of '+M.length);
if(surv.length){ console.log('\nSURVIVORS:'); surv.forEach(s=>console.log('  - '+s)); process.exit(1); }
console.log('PASS -- all '+caught+' mutations caught');
