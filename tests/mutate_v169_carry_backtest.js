const fs=require('fs'),cp=require('child_process'),path=require('path');
const SRC=path.resolve(__dirname,'..','index.html');
const original=fs.readFileSync(SRC,'utf8');
const M=[
 ['K1  markup charged only to the LONG side (overstates every short result)',
  'return signed-(m/2);',"return (direction==='SHORT')?signed:(signed-(m/2));"],
 ['K2  markup not charged at all',                'return signed-(m/2);','return signed;'],
 ['K3  markup charged at full rather than half',  'return signed-(m/2);','return signed-m;'],
 ['K4  SHORT does not invert the carry sign',
  "const signed=(direction==='SHORT')?-gap:gap;",'const signed=gap;'],
 ['K5  SHORT does not invert the PRICE return',
  "const price=(direction==='SHORT')?-raw:raw;",'const price=raw;'],
 ['K6  a missing rate becomes zero instead of skipping the bar',
  'if(rb===null||rq===null) return null;','if(rb===null||rq===null) return 0;'],
 ['K7  rates extrapolated backwards before the series starts',
  'if(d<s[0][0]) return null;','if(d<s[0][0]) return s[0][1];'],
 ['K8  LOOK-AHEAD: accrual uses the CURRENT bar\'s date rather than the previous one',
  'const net=carryNetAnnual(rates,pair,direction,prevDate,markupAnnual,c);',
  'const net=carryNetAnnual(rates,pair,direction,curDate,markupAnnual,c);'],
 ['K9  carry accrues per BAR rather than per calendar day (under-accrues weekends)',
  'const carry=net*(calDays/c.dayCountBasis);','const carry=net*(1/c.dayCountBasis);'],
 ['K10 LOOK-AHEAD: the basket is selected from the LATEST rates, not the date\'s',
  'const lng=carryNetAnnual(rates,pair,\'LONG\',d,mk,c);\n    const sht=carryNetAnnual(rates,pair,\'SHORT\',d,mk,c);',
  "const lng=carryNetAnnual(rates,pair,'LONG','2099-01-01',mk,c);\n    const sht=carryNetAnnual(rates,pair,'SHORT','2099-01-01',mk,c);"],
 ['K11 the minimum-carry floor removed (holds positions the spread eats)',
  'if(net>=c.minNetCarryAnnual) cand.push','if(true) cand.push'],
 ['K12 the position cap removed',                 'return cand.slice(0,c.maxPositions);','return cand;'],
 ['K13 basket ranked ascending (holds the WORST carry)',
  'cand.sort(function(a,b){ return b.netAnnual-a.netAnnual; });',
  'cand.sort(function(a,b){ return a.netAnnual-b.netAnnual; });'],
 ['K14 the reversed control does not actually reverse',
  "return{pair:h.pair,direction:(h.direction==='LONG')?'SHORT':'LONG',netAnnual:h.netAnnual}; });",
  'return{pair:h.pair,direction:h.direction,netAnnual:h.netAnnual}; });'],
 ['K15 drawdown measured from the START rather than the running peak',
  'if(v>peak) peak=v;','if(peak===-Infinity) peak=v;'],
 ['K16 drawdown always reported as zero',         'if(dd>worst) worst=dd;','if(false) worst=dd;'],
 ['K17 bothPositive never fires (a price trend would read as a carry result)',
  'bothPositive:(b.totalReturn>0&&r.totalReturn>0),','bothPositive:false,'],
 ['K18 a malformed pair name is guessed rather than refused',
  "if(p.length!==2||p[0].length!==3||p[1].length!==3) return null;",'if(p.length<2) return null;'],
 ['K19 the pre-registration disclosure deleted',
  // Anchored on text unique to the ARM'S HEADER. The changelog entry quotes the same phrase and
  // sits earlier in the file, so a first-occurrence replace mutated the changelog and the mutation
  // "survived" while the disclosure it guards was never touched.
  'BEFORE ANY RESULT WAS SEEN (docs:','before anything (docs:'],
 ['K20 the risk-premium / drawdown warning deleted',
  'not an inefficiency -- payment for holding','not a premium -- payment for holding'],
 ['K21 the embedded BIS rate table silently corrupted (USD peak wrong)',
  '["2023-07-27",5.375]','["2023-07-27",1.375]'],
 ['K22 the NaN defect reintroduced: CAD collapsed to one point',
  '"CAD":[','"CAD":[["2005-01-03",2.5]],"CAD_DEAD":['],
];
let caught=0;const surv=[];
for(const [n,f,r] of M){
  if(!original.includes(f)){ console.log('SKIP (anchor) '+n); continue; }
  fs.writeFileSync(SRC,original.replace(f,r));
  let failed=false;
  try{ cp.execSync('node '+path.resolve(__dirname,'v169_carry_backtest_tests.js'),{stdio:'pipe'}); }catch(e){ failed=true; }
  if(failed){caught++;console.log('CAUGHT   '+n);} else {surv.push(n);console.log('SURVIVED '+n);}
}
fs.writeFileSync(SRC,original);
console.log('\ncaught '+caught+'  survived '+surv.length+'  of '+M.length);
if(surv.length){ console.log('\nSURVIVORS:'); surv.forEach(s=>console.log('  - '+s)); process.exit(1); }
console.log('PASS -- all '+caught+' mutations caught');
