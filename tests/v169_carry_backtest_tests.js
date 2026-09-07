// MOGO v12.68.0 -- fixtures for the carry backtest (carry_g10_v1).
//
// Extracted from index.html itself, between the arm's banner and the carry feasibility diagnostic
// that follows it, so a fixture cannot stay green while the shipped code drifts.
const fs=require('fs'),vm=require('vm'),path=require('path');
const html=fs.readFileSync(path.resolve(__dirname,'..','index.html'),'utf8');
const S='// CARRY BACKTEST (carry_g10_v1)';
const E='// CARRY FEASIBILITY DIAGNOSTIC';
const i0=html.indexOf(S),i1=html.indexOf(E);
if(i0<0||i1<0||i1<=i0){ console.log('RUNNER ERROR: could not locate carry_g10_v1 in index.html'); process.exit(1); }
const src=html.slice(html.lastIndexOf('\n',i0)+1,html.lastIndexOf('\n',i1)+1);
const ctx={Math,isFinite,isNaN,Date,Object,Array,console,String,Number,Infinity,JSON,
  document:undefined,fetch:undefined,cfg:undefined};
vm.createContext(ctx);
const EX=['RULES_CARRY','CARRY_STRATEGY_ID','carryRateOn','carrySplitPair','carryNetAnnual',
 'carryWalkInstrument','carryIsoDate','carryMaxDrawdown','carrySelectBasket','carrySummarize',
 'carryWalkBasket','carryCompareArms','carryG10Universe','CARRY_POLICY_RATES',
 'carryBarsForYears','CARRY_TRADING_DAYS_PER_YEAR'];
try{ vm.runInContext(src+'\n;globalThis.__X={'+EX.map(function(n){return n+':'+n;}).join(',')+'};',ctx); }
catch(e){ console.log('RUNNER ERROR: '+(e&&e.message)); process.exit(1); }
const G=ctx.__X;

let pass=0,fail=0;
function t(n,f){try{f();pass++;console.log('PASS -- '+n);}catch(e){fail++;console.log('FAIL -- '+n+' :: '+e.message);}}
function eq(a,b,m){if(a!==b)throw new Error((m||'')+' expected '+JSON.stringify(b)+' got '+JSON.stringify(a));}
function near(a,b,tol,m){if(!(Math.abs(a-b)<=(tol||1e-9)))throw new Error((m||'')+' expected ~'+b+' got '+a);}
function ok(c,m){if(!c)throw new Error(m||'falsy');}

// A rate table where the RANKING CHANGES over time -- essential for the look-ahead fixtures.
const R={
  AUD:[['2020-01-01',5.0],['2023-01-01',1.0]],   // high then low
  JPY:[['2020-01-01',0.0],['2023-01-01',0.0]],
  USD:[['2020-01-01',0.0],['2023-01-01',5.0]],   // low then high
  CHF:[['2020-01-01',0.0]],
  NZD:[['2020-01-01',3.0]],
  GBP:[['2020-01-01',1.0]],
  CAD:[['2020-01-01',2.5]],
};
const CFG=G.RULES_CARRY.config;

t('RATE-1 the step function returns the last change at or before the date',function(){
  eq(G.carryRateOn(R,'AUD','2020-06-01'),5.0);
  eq(G.carryRateOn(R,'AUD','2022-12-31'),5.0);
  eq(G.carryRateOn(R,'AUD','2023-01-01'),1.0,'the change date itself takes the NEW rate');
  eq(G.carryRateOn(R,'AUD','2026-01-01'),1.0);
});
t('RATE-2 a date BEFORE the series returns null, never the first value',function(){
  // Extrapolating backwards would invent a rate that was never in force.
  eq(G.carryRateOn(R,'AUD','2019-12-31'),null);
  eq(G.carryRateOn(R,'ZZZ','2020-06-01'),null);
  eq(G.carryRateOn(R,'AUD',null),null);
  eq(G.carryRateOn(null,'AUD','2020-06-01'),null);
});
t('PAIR-1 malformed instrument names REFUSE rather than guess',function(){
  eq(G.carrySplitPair('AUD_JPY').base,'AUD');
  eq(G.carrySplitPair('AUD/JPY').quote,'JPY');
  [null,undefined,'','AUDJPY','A_B','AUD_JP_Y',123,{}].forEach(function(v){
    eq(G.carrySplitPair(v),null,'input '+JSON.stringify(v)+' must refuse');
  });
});
t('NET-1 THE MARKUP IS CHARGED ON BOTH SIDES, not only the losing one',function(){
  // AUD 5%, JPY 0% on 2020-06-01. Gap +5%. Markup 2% round trip -> 1% charged either way.
  const lng=G.carryNetAnnual(R,'AUD_JPY','LONG','2020-06-01',0.02,CFG);
  const sht=G.carryNetAnnual(R,'AUD_JPY','SHORT','2020-06-01',0.02,CFG);
  near(lng,0.05-0.01,1e-12,'long');
  near(sht,-0.05-0.01,1e-12,'short');
  near(lng+sht,-0.02,1e-12,'the two sides must sum to MINUS the round-trip markup');
});
t('NET-2 a missing rate yields null, never a zero-rate assumption',function(){
  eq(G.carryNetAnnual(R,'AUD_JPY','LONG','2019-01-01',0.02,CFG),null);
  eq(G.carryNetAnnual(R,'AUD_ZZZ','LONG','2020-06-01',0.02,CFG),null);
});
t('NET-3 a missing or negative markup falls back to the measured median, not to zero',function(){
  [null,undefined,NaN,-0.01,'x'].forEach(function(v){
    const n=G.carryNetAnnual(R,'AUD_JPY','LONG','2020-06-01',v,CFG);
    near(n,0.05-CFG.defaultMarkupAnnual/2,1e-12,'markup input '+JSON.stringify(v));
  });
});
// ---- the look-ahead guard ----
t('SEL-1 THE BASKET IS CHOSEN BY THE RATES IN FORCE ON THAT DATE, NOT TODAY\'S',function(){
  // In 2020 AUD yields 5% and USD 0%: long AUD/USD. By 2023 that has REVERSED.
  // A selector that read the latest rates would pick the same basket on both dates.
  const uni=['AUD_USD'];
  const early=G.carrySelectBasket(R,uni,'2020-06-01',{},CFG);
  const late =G.carrySelectBasket(R,uni,'2024-06-01',{},CFG);
  eq(early.length,1); eq(late.length,1);
  eq(early[0].direction,'LONG','2020: AUD is the high-yielder');
  eq(late[0].direction,'SHORT','2024: USD is -- the direction MUST flip');
});
t('SEL-2 pairs below the minimum net carry are not held at all',function(){
  // CHF and JPY are both 0%: gap zero, so net is negative once the markup is charged.
  eq(G.carrySelectBasket(R,['CHF_JPY'],'2020-06-01',{},CFG).length,0);
});
t('SEL-3 ranked by net carry, best first, and capped at maxPositions',function(){
  // The universe must have DISTINCT carries or ranking cannot be tested. An earlier version used
  // three pairs whose gaps were all identical (5%), so sorting ascending or descending gave the
  // same answer and a reversed-sort mutation survived. Gaps here are 5%, 3% and 1%.
  const cfg=Object.assign({},CFG,{maxPositions:2});
  // THREE pairs must clear the carry floor for the CAP to bind at 2 -- otherwise removing the cap
  // changes nothing and a cap-removal mutation survives. Gaps 5%, 3%, 2.5% all clear it; GBP's 1%
  // does not (1% minus the 1.095% half-markup is negative), so it tests the floor as well.
  const sel=G.carrySelectBasket(R,['GBP_JPY','AUD_JPY','NZD_JPY','CAD_JPY'],'2020-06-01',{},cfg);
  eq(sel.length,2,'must respect the cap');
  eq(sel[0].pair,'AUD_JPY','the BEST carry must be held first');
  eq(sel[1].pair,'NZD_JPY');
  ok(!sel.some(function(x){return x.pair==='GBP_JPY';}),'below the floor: must not be held');
  ok(!sel.some(function(x){return x.pair==='CAD_JPY';}),'clears the floor but ranks third: the cap must drop it');
  ok(sel[0].netAnnual>sel[1].netAnnual,'strictly ranked');
});
t('SEL-4 a pair with no rate data is skipped, not defaulted',function(){
  eq(G.carrySelectBasket(R,['AUD_ZZZ'],'2020-06-01',{},CFG).length,0);
});
// ---- the walk ----
function bars(from,days,startPx,dailyPct){
  const out=[];let px=startPx;const t0=Date.parse(from);
  for(let i=0;i<days;i++){ out.push({t:new Date(t0+i*86400000),c:px}); px*=(1+dailyPct); }
  return out;
}
t('WALK-1 a flat price earns exactly the net carry, compounded',function(){
  const b=bars('2020-06-01',101,1.0,0);           // 100 daily steps, price unchanged
  const w=G.carryWalkInstrument(b,'AUD_JPY','LONG',R,0.02,CFG);
  eq(w.days.length,100);
  const expected=Math.pow(1+0.04/365,100);        // net 4%/yr, 1 calendar day per step
  near(w.equity,expected,1e-9);
  near(w.priceTotal,0,1e-12,'no price contribution on a flat series');
});
t('WALK-2 CARRY ACCRUES ON CALENDAR DAYS: a 3-day gap accrues 3 days, not 1',function(){
  const b=[{t:new Date('2020-06-05T00:00:00Z'),c:1},{t:new Date('2020-06-08T00:00:00Z'),c:1}];
  const w=G.carryWalkInstrument(b,'AUD_JPY','LONG',R,0.02,CFG);
  eq(w.days.length,1);
  near(w.days[0].carry,0.04*3/365,1e-12,'a Friday-to-Monday bar gap must accrue three days');
});
t('WALK-3 SHORT flips BOTH the price return and the carry',function(){
  const b=bars('2020-06-01',2,1.0,0.01);
  const L=G.carryWalkInstrument(b,'AUD_JPY','LONG',R,0.02,CFG);
  const S=G.carryWalkInstrument(b,'AUD_JPY','SHORT',R,0.02,CFG);
  near(L.priceTotal,-S.priceTotal,1e-12,'price must invert');
  ok(L.days[0].netAnnual>0&&S.days[0].netAnnual<0,'carry must invert in sign');
});
t('WALK-4 NO LOOK-AHEAD: the rate used is the one in force on the PREVIOUS bar',function(){
  // A bar spanning the 2023-01-01 rate change must use the OLD rate for that day's accrual.
  const b=[{t:new Date('2022-12-31T00:00:00Z'),c:1},{t:new Date('2023-01-02T00:00:00Z'),c:1}];
  const w=G.carryWalkInstrument(b,'AUD_JPY','LONG',R,0.02,CFG);
  near(w.days[0].netAnnual,0.05-0.01,1e-12,'must use the 5% rate in force on 2022-12-31');
});
t('WALK-5 bars before any rate exists are SKIPPED and counted, not treated as zero carry',function(){
  const b=bars('2019-01-01',5,1.0,0);
  const w=G.carryWalkInstrument(b,'AUD_JPY','LONG',R,0.02,CFG);
  eq(w.days.length,0); eq(w.skipped,4);
});
t('DD-1 max drawdown, hand-computed',function(){
  near(G.carryMaxDrawdown([1,1.5,0.9,1.2,0.6]),(1.5-0.6)/1.5,1e-12);
  near(G.carryMaxDrawdown([1,1.1,1.2]),0,1e-12,'a monotonic rise has no drawdown');
  eq(G.carryMaxDrawdown([]),null);
  eq(G.carryMaxDrawdown(null),null);
});
// ---- the control ----
t('CTRL-1 the reversed control flips every position',function(){
  const s={'AUD_USD':bars('2020-06-01',60,1.0,0)};
  const a=G.carryWalkBasket(s,R,{},CFG,false);
  const b=G.carryWalkBasket(s,R,{},CFG,true);
  ok(a.rebalances.length&&b.rebalances.length);
  eq(a.rebalances[0].held[0],'AUD_USD:LONG');
  eq(b.rebalances[0].held[0],'AUD_USD:SHORT','the control must hold the opposite side');
});
t('CTRL-2 on a FLAT price the control loses roughly what the basket earns',function(){
  // With no price move, reversing turns +gap into -gap, and BOTH still pay the markup.
  const s={'AUD_USD':bars('2020-06-01',200,1.0,0)};
  const a=G.carryWalkBasket(s,R,{'AUD_USD':0.02},CFG,false);
  const b=G.carryWalkBasket(s,R,{'AUD_USD':0.02},CFG,true);
  ok(a.days[a.days.length-1].equity>1,'basket earns');
  ok(b.days[b.days.length-1].equity<1,'control loses');
});
t('CTRL-3 BOTH ARMS POSITIVE is detected -- that is a price trend, not carry',function(){
  // A strong uptrend big enough to overwhelm the reversed carry would lift both arms.
  const cmp=G.carryCompareArms({days:[{equity:1.2,carry:0.01,price:0.19}]},
                               {days:[{equity:1.1,carry:-0.01,price:0.11}]});
  eq(cmp.bothPositive,true,'this is the shape the control exists to expose');
  eq(cmp.beatsReversedControl,true);
});
t('CTRL-5 THE REAL RUN: positive, beats its control, and still a FAIL on drawdown',function(){
  // Reproduces the operator's 2026-09-07 result exactly: +21.35% over 22.5 years (+0.86%/yr)
  // against a 40.1% worst fall. It satisfies all three of the original conditions, and the
  // pre-registration ALSO said a positive mean with a 30% drawdown is a fail. The first version of
  // the verdict checked only the three and printed "Meets the pre-registered conditions."
  const basket={days:[{equity:1.0,carry:0,price:0},{equity:1.8,carry:0.43,price:-0.13},
                      {equity:1.078,carry:0,price:0},{equity:1.2135,carry:0,price:0}]};
  const control={days:[{equity:1.0,carry:0,price:0},{equity:0.4567,carry:-0.80,price:0.13}]};
  const cmp=G.carryCompareArms(basket,control,G.RULES_CARRY.config);
  eq(cmp.basketPositive,true,'the basket did make money');
  eq(cmp.beatsReversedControl,true,'and it did beat its control');
  eq(cmp.bothPositive,false,'and it is not a price trend');
  ok(cmp.basket.maxDrawdown>0.30,'but the drawdown is over the limit, got '+cmp.basket.maxDrawdown);
  eq(cmp.drawdownAcceptable,false,'THIS is the condition that fails, and it must be reported');
});
t('CTRL-6 the same shape with a tolerable drawdown passes all four',function(){
  const basket={days:[{equity:1.0,carry:0,price:0},{equity:1.1,carry:0.1,price:0},
                      {equity:0.95,carry:0,price:0},{equity:1.25,carry:0,price:0}]};
  const control={days:[{equity:1.0,carry:0,price:0},{equity:0.8,carry:-0.1,price:0}]};
  const cmp=G.carryCompareArms(basket,control,G.RULES_CARRY.config);
  ok(cmp.basket.maxDrawdown<=0.30,'precondition: drawdown within limit');
  eq(cmp.drawdownAcceptable,true);
  eq(cmp.basketPositive&&cmp.beatsReversedControl&&!cmp.bothPositive&&cmp.drawdownAcceptable,true);
});
t('CTRL-7 a null drawdown is NOT treated as acceptable',function(){
  // An unmeasurable drawdown must not silently pass the condition.
  const cmp=G.carryCompareArms({days:[{equity:1.5,carry:0.5,price:0}]},
                               {days:[{equity:0.7,carry:-0.5,price:0}]},G.RULES_CARRY.config);
  ok(cmp.basket.maxDrawdown!=null,'this path does produce a drawdown');
  const cmp2=G.carryCompareArms({days:[{equity:null,carry:0,price:0}]},
                                {days:[{equity:0.7,carry:-0.5,price:0}]},G.RULES_CARRY.config);
  eq(cmp2.drawdownAcceptable,false,'no measurable drawdown must not pass');
});
t('CTRL-4 an empty run refuses to compare rather than reporting zeros',function(){
  eq(G.carryCompareArms({days:[]},{days:[]}).comparable,false);
});
t('SUM-1 summary figures, hand-checked',function(){
  const days=[{equity:1.1,carry:0.05,price:0.05},{equity:1.21,carry:0.05,price:0.06}];
  const s=G.carrySummarize(days,'x');
  near(s.totalReturn,0.21,1e-12);
  near(s.carryContribution,0.10,1e-12);
  near(s.priceContribution,0.11,1e-12);
  eq(s.n,2);
});
t('RATES-1 the EMBEDDED BIS table is present, complete and sane',function(){
  const R2=G.CARRY_POLICY_RATES;
  ['USD','EUR','JPY','GBP','AUD','NZD','CAD','CHF','SEK','NOK'].forEach(function(c){
    ok(R2[c]&&R2[c].length>5,c+' must have a real series, got '+((R2[c]||[]).length));
  });
  // Known history. If the embedded table ever drifts from BIS, these break.
  near(G.carryRateOn(R2,'USD','2023-09-01'),5.375,1e-9,'USD at the 2023 peak');
  near(G.carryRateOn(R2,'USD','2021-06-01'),0.125,1e-9,'USD at the zero bound');
  near(G.carryRateOn(R2,'JPY','2019-06-01'),-0.1,1e-9,'JPY negative-rate years');
  near(G.carryRateOn(R2,'CHF','2015-06-01'),-0.75,1e-9,'CHF deeply negative');
  // The NaN bug collapsed these three to a single bogus point.
  ['CAD','GBP','NOK'].forEach(function(c){
    ok(R2[c].length>20,c+' has only '+R2[c].length+' points -- the NaN defect is back');
  });
});
t('BARS-1 the Years box is sized in TRADING days, so it returns the range it promises',function(){
  // 15 years x 365 asked for 5,515 daily bars, which is ~22 years of trading days -- the operator
  // asked for 15 and the panel reported 22.5. Sized correctly, 15 years is ~3,820 bars.
  eq(G.CARRY_TRADING_DAYS_PER_YEAR,252);
  eq(G.carryBarsForYears(15),15*252+40);
  ok(G.carryBarsForYears(15)/252<16,'15 years must request under 16 years of trading days');
  ok(G.carryBarsForYears(15)<5000,'a calendar-day sizing would exceed 5,500');
});
t('BARS-2 a bad or missing year count falls back to a sane default and is capped',function(){
  [null,undefined,NaN,0,-5,'x',{}].forEach(function(v){ eq(G.carryBarsForYears(v),10*252+40,'input '+JSON.stringify(v)); });
  eq(G.carryBarsForYears(500),9000,'must respect the hard cap');
});
t('GUARD-1 the header states the pre-registered pass conditions and the risk-premium caveat',function(){
  const flat=src.replace(/\n\/\/\s?/g,' ');
  ok(/PRE-REGISTERED BEFORE ANY RESULT WAS SEEN/.test(flat),'pre-registration missing');
  ok(/RISK PREMIUM, not an inefficiency/.test(flat),'risk-premium caveat missing');
  ok(/supposed\* to lose badly sometimes/.test(flat)||/supposed to lose badly/.test(flat),'drawdown warning missing');
  ok(/BIS/.test(flat),'BIS attribution missing');
});
console.log('FIXTURES: '+pass+'/'+(pass+fail));
process.exit(fail?1:0);
