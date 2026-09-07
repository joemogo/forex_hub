// Mutation harness for tod_session_v1. A fixture is not evidence until breaking the mechanism it
// claims to protect makes it fail. Each entry below is a deliberate, plausible defect.
const fs=require('fs'),cp=require('child_process');
const SRC=require('path').resolve(__dirname,'..','index.html');
const original=fs.readFileSync(SRC,'utf8');

const MUTATIONS=[
 // ANCHORED ON THE FUNCTION SIGNATURE, not on its return line. The return line
 // `return Math.round((asUTC-ms)/60000);` is BYTE-IDENTICAL in getNYOffsetMinutes earlier in
 // index.html, so a naive first-occurrence replace mutated that unrelated function instead and the
 // mutation "survived" while tod's own DST handling was never touched. The harness was wrong, not
 // the coverage.
 ['M1  NY offset hardcoded to -5 (ignores DST)',
  'function todOffsetMinutesAt(tz,ms){','function todOffsetMinutesAt(tz,ms){ return -300;'],

// M2 (single-pass local->UTC) and M3 (advancing from the session start rather than local noon) were
// tested and are EQUIVALENT MUTANTS for this arm's configured session times: equiv.js scans
// 2014-2026 and finds ZERO differences at 08:30/17:00 New York and 08:00/16:30 London, because all
// four are far from local midnight where the correction bites. They are recorded here rather than
// listed as survivors, and the two-pass conversion is KEPT because a future window near midnight
// would need it. M3b below is the same edit made dangerously, and it is a real, killable defect.

 ['M4  LOOK-AHEAD: exit taken from the last candle in the series, not the window',
  'const first=inWin[0],last=inWin[inWin.length-1];',
  'const first=inWin[0],last={t:0,c:candles[candles.length-1].c};'],

 ['M5  window start boundary exclusive (t>start rather than >=)',
  'if(t>=win.startUtc&&t<=win.endUtc) inWin.push({t:t,c:c.c});',
  'if(t>win.startUtc&&t<=win.endUtc) inWin.push({t:t,c:c.c});'],

 ['M6  window end boundary inclusive of the next bar',
  'if(t>=win.startUtc&&t<=win.endUtc) inWin.push({t:t,c:c.c});',
  'if(t>=win.startUtc&&t<=win.endUtc+900000) inWin.push({t:t,c:c.c});'],

 ['M7  the too-few-candles guard removed',
  'if(inWin.length<cfg.minSessionCandles) return{ok:false,reason:\'TOO_FEW_CANDLES\',count:inWin.length};','/*dropped*/'],

 ['M8  the START_GAP guard removed',
  'if(slip>cfg.maxStartSlipMinutes) return{ok:false,reason:\'START_GAP\',slipMinutes:slip};','/*dropped*/'],

 ['M9  population SD (/n) instead of sample SD (/(n-1))',
  'const d=x-mean; return a+d*d; },0)/(n-1);','const d=x-mean; return a+d*d; },0)/n;'],

 ['M10 n=1 reports a fake zero error bar instead of null',
  'let se=null,ciLo=null,ciHi=null,t=null;\n  if(n>1){','let se=0,ciLo=null,ciHi=null,t=null;\n  if(n>1){'],

 ['M11 winShare counts GROSS wins, ignoring the spread',
  'const wins=net.filter(function(x){return x>0;}).length;',
  'const wins=obs.filter(function(o){return o.grossPips>0;}).length;'],

 ['M12 the spread is charged against the MEAN rather than per observation',
  'const net=obs.map(function(o){ return o.grossPips-sp; });',
  'const net=obs.map(function(o){ return o.grossPips; });'],

 ['M13 complement entry taken from the session ENTRY rather than its EXIT (breaks tiling)',
  'entry:a.exit,exit:b.entry,\n      grossPips:(b.entry-a.exit)/pip',
  'entry:a.entry,exit:b.entry,\n      grossPips:(b.entry-a.entry)/pip'],

 ['M14 complement rebuilt from raw windows and re-priced (the ORIGINAL defect: weekend legs vanish)',
  `for(let i=0;i<prim.priced.length-1;i++){
    const a=prim.priced[i],b=prim.priced[i+1];
    comp.push({ok:true,dayKey:a.dayKey+'~'+b.dayKey,
      startUtc:a.endUtc,endUtc:b.startUtc,entry:a.exit,exit:b.entry,
      grossPips:(b.entry-a.exit)/pip,grossPct:((b.entry-a.exit)/a.exit)*100,
      complementGapHours:(b.startUtc-a.endUtc)/3600000});
  }`,
  `for(let i=0;i<prim.wins.length-1;i++){
    const w={dayKey:prim.wins[i].dayKey+'~',startUtc:prim.wins[i].endUtc,endUtc:prim.wins[i+1].startUtc};
    const p=todPriceWindow(candles,w,c,pip);
    if(p.ok){ p.complementGapHours=(w.endUtc-w.startUtc)/3600000; comp.push(p); }
  }`],

 ['M3b window enumeration anchored near local midnight (skips a day every spring forward)',
  'const nextNoon=todLocalToUtcMs(sess.tz,cur.y,cur.mo,cur.d,12,0)+86400000;',
  'const nextNoon=todLocalToUtcMs(sess.tz,cur.y,cur.mo,cur.d,23,30)+86400000;'],

 ['M15 pooled SE as a plain sum instead of root-sum-of-squares',
  'const se=Math.sqrt(p.sePips*p.sePips+q.sePips*q.sePips);','const se=p.sePips+q.sePips;'],

 ['M16 directionAsPredicted tests the LEVEL rather than the DIFFERENCE',
  'directionAsPredicted:diff>0','directionAsPredicted:p.meanPips>0'],

 ['M17 refusals silently swallowed rather than counted',
  'if(p.ok) priced.push(p); else bump(p.reason);','if(p.ok) priced.push(p);'],

 ['M18 the HEADER no-stop / risk-denominator disclosure deleted',
  'It has NO STOP AND NO TARGET.','It has a stop and a target.'],

 ['M19 the HEADER replay_compare caveat deleted',
  'DOES NOT APPLY to it unchanged.','applies to it unchanged.'],

 ['M21 the PACKAGE no-R disclosure deleted',
  "'NO R-MULTIPLE EXISTS IN THIS PACKAGE.","'Trades in this package."],

 ['M22 the PACKAGE replay_compare disclosure deleted',
  "'scripts/replay_compare.py DOES NOT APPLY to this package","'scripts/replay_compare.py applies to this package"],

 ['M23 observations gain a realizedR field derived from an invented risk',
  'grossPips:ob.grossPips,grossPct:ob.grossPct,','grossPips:ob.grossPips,grossPct:ob.grossPct,realizedR:ob.grossPips/20,'],

 ['M24 the secondary window exported as source-stated provenance',
  "windowProvenance:sess?sess.provenance:'CONTROL -- complement of the primary window',",
  "windowProvenance:'SOURCE_STATED',"],

 ['M25 EUR/USD counted among the exploratory pairs (inflating k and losing the pre-registration)',
  "const exploratory=ok.filter(function(r){ return r.pair!==TOD_PRIMARY_PAIR; });",
  "const exploratory=ok.slice();"],

 ['M26 Sidak correction replaced by a flat 0.05',
  'return 1-Math.pow(1-a,1/n);','return a;'],

 ['M20 the secondary window relabelled as source-stated',
  "provenance:'MOGO CHOICE -- window UNKNOWN in sources'","provenance:'SOURCE_STATED (Breedon/Ranaldo 2013)'"],
];

let caught=0,survived=0;const survivors=[];
for(const [name,find,replace] of MUTATIONS){
  if(!original.includes(find)){ console.log('SKIP (anchor not found) '+name); continue; }
  fs.writeFileSync(SRC,original.replace(find,replace));
  let failed=false,out='';
  try{ cp.execSync('node '+require('path').resolve(__dirname,'v166_tod_session_tests.js'),{stdio:'pipe',cwd:require('path').resolve(__dirname,'..')}); }
  catch(e){ failed=true; out=(e.stdout||'').toString(); }
  if(failed){ caught++; const m=null;
    const killers=m?m[1].trim().split('\n').map(s=>s.trim().replace(/^- /,'').split(':')[0]).slice(0,3).join(', '):'?';
    console.log('CAUGHT   '+name+'\n           killed by: '+killers);
  } else { survived++; survivors.push(name); console.log('SURVIVED '+name); }
}
fs.writeFileSync(SRC,original);
console.log('\ncaught '+caught+'  survived '+survived+'  of '+MUTATIONS.length);
if(survivors.length){ console.log('\nSURVIVORS (each is an untested mechanism):'); survivors.forEach(s=>console.log('  - '+s)); }
// THE GATE MUST BE ABLE TO FAIL. Without this the harness printed its survivors and exited 0, so
// run_all.sh's `if ! node ...` could never trip and a surviving mutation would scroll past green.
if(survivors.length){
  console.log('\nFAIL -- '+survivors.length+' mutation(s) survived: the fixtures do not cover them.');
  process.exit(1);
}
console.log('PASS -- all '+caught+' mutations of tod_session_v1 were caught by tests/v166_tod_session_tests.js');
