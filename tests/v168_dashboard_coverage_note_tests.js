// MOGO v12.67.0 -- fixtures for the dashboard coverage note.
//
// Extracted from index.html itself so a fixture cannot stay green while the shipped code drifts.
const fs=require('fs'),vm=require('vm'),path=require('path');
const html=fs.readFileSync(path.resolve(__dirname,'..','index.html'),'utf8');
const S='// PURE. What the dashboard tile says about the set its figure was computed on.';
const E='function renderDashboard(){';
const i0=html.indexOf(S),i1=html.indexOf(E);
if(i0<0||i1<0||i1<=i0){ console.log('RUNNER ERROR: could not locate dashCoverageNote in index.html'); process.exit(1); }
const src=html.slice(i0,i1);
const ctx={Math,isFinite,console,String,Number,Object};
vm.createContext(ctx);
try{ vm.runInContext(src+'\n;globalThis.__X={dashCoverageNote:dashCoverageNote};',ctx); }
catch(e){ console.log('RUNNER ERROR: '+(e&&e.message)); process.exit(1); }
const G=ctx.__X;

let pass=0,fail=0;
function t(n,f){try{f();pass++;console.log('PASS -- '+n);}catch(e){fail++;console.log('FAIL -- '+n+' :: '+e.message);}}
function eq(a,b,m){if(a!==b)throw new Error((m||'')+' expected '+JSON.stringify(b)+' got '+JSON.stringify(a));}
function ok(c,m){if(!c)throw new Error(m||'falsy');}

t('NOTE-1 a clean book states the denominator and claims no exclusion',function(){
  const r=G.dashCoverageNote(43,0);
  eq(r.text,'43 closed'); eq(r.hasExclusion,false); eq(r.title,'');
});
t('NOTE-2 THE JVM CASE: two clean trades with one quarantined record says so',function(){
  // The exact situation on the operator's dashboard: three closed records, one seeded and
  // quarantined, leaving two real losses and a 0% win rate. The tile previously said only "0%".
  const r=G.dashCoverageNote(2,1);
  eq(r.text,'2 closed · 1 excluded');
  eq(r.hasExclusion,true);
  ok(/integrity rule/.test(r.title),'the tooltip must say WHY the record was excluded');
  ok(/preserved/.test(r.title),'the tooltip must say the record still exists');
});
t('NOTE-3 an empty book is stated, not hidden',function(){
  const r=G.dashCoverageNote(0,0);
  eq(r.text,'0 closed'); eq(r.hasExclusion,false);
});
t('NOTE-4 zero clean trades with exclusions still reports both numbers',function(){
  const r=G.dashCoverageNote(0,3);
  eq(r.text,'0 closed · 3 excluded'); eq(r.hasExclusion,true);
});
t('NOTE-5 an UNKNOWN denominator makes NO claim rather than a fabricated zero',function(){
  // "0 closed" when the count is unknown is a lie the tile must never tell.
  [null,undefined,NaN,-1,'5',{},[]].forEach(function(v){
    const r=G.dashCoverageNote(v,1);
    eq(r.text,'','input '+JSON.stringify(v)+' must produce no claim');
    eq(r.closedCount,null);
  });
});
t('NOTE-6 a non-numeric or negative exclusion count is treated as none, never as text',function(){
  [null,undefined,NaN,-2,'x'].forEach(function(v){
    const r=G.dashCoverageNote(10,v);
    eq(r.text,'10 closed','exclusion input '+JSON.stringify(v)); eq(r.hasExclusion,false);
  });
});
t('NOTE-7 fractional counts are floored, never rendered with decimals',function(){
  const r=G.dashCoverageNote(2.9,1.7);
  eq(r.text,'2 closed · 1 excluded');
});
t('NOTE-8 the note never asserts an exclusion that was not reported',function(){
  for(let c=0;c<20;c++){
    const r=G.dashCoverageNote(c,0);
    ok(!/excluded/.test(r.text),'a clean book must not mention exclusions');
    eq(r.hasExclusion,false);
  }
});
console.log('FIXTURES: '+pass+'/'+(pass+fail));
process.exit(fail?1:0);
