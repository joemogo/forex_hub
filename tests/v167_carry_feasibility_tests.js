// MOGO v12.66.0 -- fixtures for the carry feasibility diagnostic.
//
// RUNS AGAINST index.html ITSELF, not a scratch copy: the block is extracted from the shipped file
// between its own banner and the time-of-day arm that follows it, so a fixture cannot stay green
// while the code that actually ships drifts away from it.
const fs=require('fs'),vm=require('vm'),path=require('path');
const ROOT=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
const S='// CARRY FEASIBILITY DIAGNOSTIC';
const E='// TIME-OF-DAY SESSION SEGMENTATION (tod_session_v1)';
const i0=html.indexOf(S),i1=html.indexOf(E);
if(i0<0||i1<0||i1<=i0){ console.log('RUNNER ERROR: could not locate the carry block in index.html'); process.exit(1); }
const src=html.slice(html.lastIndexOf('// \u2550',i0)>=0?html.lastIndexOf('// \u2550',i0):i0, html.lastIndexOf('// \u2550',i1));
const ctx={Math,isFinite,parseFloat,Array,Object,console,String,Number,Infinity,NaN,JSON,Date,
  document:undefined,fetch:undefined,cfg:undefined};
vm.createContext(ctx);
const EX=['carryDecompose','carryAnalyzeAll','carryFmtRate','carryToRate','CARRY_DIAG_VERSION'];
try{ vm.runInContext(src+'\n;globalThis.__X={'+EX.map(function(n){return n+':'+n;}).join(',')+'};',ctx); }
catch(e){ console.log('RUNNER ERROR: '+(e&&e.message)); process.exit(1); }
const G=ctx.__X;

let pass=0,fail=0;const F=[];
function t(n,f){try{f();pass++;console.log('PASS -- '+n);}catch(e){fail++;F.push(n+': '+e.message);console.log('FAIL -- '+n+' :: '+e.message);}}
function eq(a,b,m){if(a!==b)throw new Error((m||'')+' expected '+b+' got '+a);}
function near(a,b,tol,m){if(!(Math.abs(a-b)<=(tol||1e-9)))throw new Error((m||'')+' expected ~'+b+' got '+a);}
function ok(c,m){if(!c)throw new Error(m||'falsy');}

// ── DEC: the decomposition, hand-computed ──
t('DEC-1 a ZERO-markup pair recovers the differential exactly',function(){
  // fair market: rates equal and opposite. long +2%, short -2% -> d=2%, m=0
  const r=G.carryDecompose(0.02,-0.02);
  ok(r.ok); near(r.differential,0.02); near(r.markup,0); near(r.bestRate,0.02);
  eq(r.bestSide,'LONG'); eq(r.paysNothingEitherWay,false);
});
t('DEC-2 a markup is exactly what the two rates FAIL to sum to',function(){
  // true d=2%, broker keeps 1% round trip: long = 2-0.5 = 1.5, short = -2-0.5 = -2.5
  const r=G.carryDecompose(0.015,-0.025);
  near(r.differential,0.02,1e-12,'differential'); near(r.markup,0.01,1e-12,'markup');
  near(r.bestRate,0.015); near(r.markupShareOfDifferential,0.5);
});
t('DEC-3 THE DEATH CONDITION: markup exceeding the differential makes both sides negative',function(){
  // true d=0.5%, markup 2%: long = 0.5-1 = -0.5, short = -0.5-1 = -1.5
  const r=G.carryDecompose(-0.005,-0.015);
  near(r.differential,0.005); near(r.markup,0.02);
  eq(r.paysNothingEitherWay,true,'both sides negative must be flagged');
  near(r.bestRate,-0.005);
});
t('DEC-4 the SHORT side is selected when it pays more',function(){
  const r=G.carryDecompose(-0.03,0.01);
  eq(r.bestSide,'SHORT'); near(r.bestRate,0.01); near(r.differential,-0.02);
});
t('DEC-5 rates arriving as STRINGS (OANDA returns decimal strings) are parsed',function(){
  const r=G.carryDecompose('0.0150','-0.0250');
  ok(r.ok); near(r.differential,0.02,1e-12); near(r.markup,0.01,1e-12);
});
t('DEC-6 a missing rate REFUSES rather than defaulting to zero',function(){
  // A zero here would read as "no markup" -- the most flattering possible lie.
  // Every one of these coerces to a NUMBER under naive isFinite(): null->0, ''->0, true->1, []->0.
  [[null,-0.02],[0.02,undefined],['abc',-0.02],[NaN,0],['',0.01],[true,-0.02],[[],0.01],
   [Infinity,0],[{},0.01],[0.02,'  ']].forEach(function(p){
    const r=G.carryDecompose(p[0],p[1]);
    eq(r.ok,false,'inputs '+JSON.stringify(p)+' must refuse');
    eq(r.markup,undefined,'a refused decomposition must not report a markup');
  });
});
t('DEC-7 a zero differential reports NULL share, not a division blow-up',function(){
  const r=G.carryDecompose(-0.01,-0.01);   // d=0, m=0.02
  near(r.differential,0); near(r.markup,0.02);
  eq(r.markupShareOfDifferential,null,'no differential means no share to report');
  eq(r.paysNothingEitherWay,true);
});
t('DEC-8 the identity holds for random inputs: long+short === -markup, long-short === 2*diff',function(){
  let seed=7;const rnd=function(){seed=(seed*1103515245+12345)%2147483648;return seed/2147483648-0.5;};
  for(let i=0;i<500;i++){
    const L=rnd()*0.2,S=rnd()*0.2;
    const r=G.carryDecompose(L,S);
    near(L+S,-r.markup,1e-12,'sum identity'); near(L-S,2*r.differential,1e-12,'difference identity');
    near(Math.max(L,S),r.bestRate,1e-12);
  }
});

// ── ALL: the book ──
const book=function(){return [
  {name:'USD_TRY',financing:{longRate:'-0.4200',shortRate:'0.3600',financingDaysOfWeek:[1,2,3,4,5]}},
  {name:'EUR_USD',financing:{longRate:'-0.0310',shortRate:'0.0110'}},
  {name:'AUD_JPY',financing:{longRate:'0.0180',shortRate:'-0.0380'}},
  {name:'GBP_CHF',financing:{longRate:'-0.0090',shortRate:'-0.0110'}},
];};
t('ALL-1 ranked by what the account would ACTUALLY receive, not by the differential',function(){
  const a=G.carryAnalyzeAll(book());
  eq(a.count,4);
  eq(a.rows[0].instrument,'USD_TRY');   // bestRate 0.36
  near(a.rows[0].bestRate,0.36,1e-12); eq(a.rows[0].bestSide,'SHORT');
  ok(a.rows[0].bestRate>=a.rows[1].bestRate&&a.rows[1].bestRate>=a.rows[2].bestRate,'must be sorted');
});
t('ALL-2 counts how many instruments pay ANYTHING at all',function(){
  const a=G.carryAnalyzeAll(book());
  eq(a.instrumentsPayingSomething,3);   // TRY, EURUSD(short .011), AUDJPY(long .018); GBP_CHF pays neither
  eq(a.everyInstrumentCostsMoneyEitherWay,false);
});
t('ALL-3 THE VERDICT FIRES when every instrument costs money either way',function(){
  const dead=[{name:'A',financing:{longRate:-0.01,shortRate:-0.02}},
              {name:'B',financing:{longRate:-0.005,shortRate:-0.03}}];
  const a=G.carryAnalyzeAll(dead);
  eq(a.instrumentsPayingSomething,0);
  eq(a.everyInstrumentCostsMoneyEitherWay,true,'this is the flag the whole diagnostic exists for');
});
t('ALL-4 an instrument with NO financing block is SKIPPED and REPORTED, never silently dropped',function(){
  const a=G.carryAnalyzeAll([{name:'X'},{name:'Y',financing:{longRate:0.01,shortRate:-0.01}}]);
  eq(a.count,1); eq(a.skipped.length,1); eq(a.skipped[0].instrument,'X');
});
t('ALL-5 an empty book does NOT fire the death verdict',function(){
  // No data is not the same finding as no carry, and must never be reported as one.
  const a=G.carryAnalyzeAll([]);
  eq(a.count,0); eq(a.everyInstrumentCostsMoneyEitherWay,false,'zero instruments is not a verdict');
  eq(a.bestInstrument,null); eq(a.medianMarkup,null);
});
t('ALL-6 the median markup is a real MEDIAN, not the middle of the bestRate ranking',function(){
  // Rows are sorted by bestRate BEFORE markups are read off, so a median taken without re-sorting
  // returns the middle of the WRONG ordering. The earlier version of this fixture used markups
  // whose middle element was identical either way, so it could not fail. This book is built so the
  // two answers differ: markups in bestRate order are [.10,.01,.02,.03,.04] (middle .02) while the
  // true median is .03.
  const b=[
    {name:'A',financing:{longRate:0.30,shortRate:-0.40}},   // bestRate .30  markup .10
    {name:'B',financing:{longRate:0.20,shortRate:-0.21}},   // bestRate .20  markup .01
    {name:'C',financing:{longRate:0.10,shortRate:-0.12}},   // bestRate .10  markup .02
    {name:'D',financing:{longRate:0.05,shortRate:-0.08}},   // bestRate .05  markup .03
    {name:'E',financing:{longRate:0.01,shortRate:-0.05}},   // bestRate .01  markup .04
  ];
  const a=G.carryAnalyzeAll(b);
  eq(a.rows.map(function(r){return r.instrument;}).join(''),'ABCDE','precondition: bestRate order');
  near(a.rows.map(function(r){return r.markup;})[2],0.02,1e-9,'precondition: unsorted middle is .02');
  near(a.medianMarkup,0.03,1e-9,'the median must be .03, not the .02 sitting in the middle');
});
t('ALL-7 financingDaysOfWeek is carried through when present, null when absent',function(){
  const a=G.carryAnalyzeAll(book());
  const try_=a.rows.filter(r=>r.instrument==='USD_TRY')[0];
  const eur=a.rows.filter(r=>r.instrument==='EUR_USD')[0];
  eq(try_.financingDaysOfWeek,5); eq(eur.financingDaysOfWeek,null);
});
t('GUARD-1 the file states this is read-only and that the markup can kill the idea',function(){
  const flat=src.replace(/\n\/\/\s?/g,' ');
  ok(/READ-ONLY/.test(flat),'read-only disclosure missing');
  ok(/DEATH CONDITION IS EXPLICIT/.test(flat),'death-condition disclosure missing');
  ok(/INTERBANK/.test(flat),'the interbank-vs-retail caveat is missing');
});
console.log('FIXTURES: '+pass+'/'+(pass+fail));
process.exit(fail?1:0);
