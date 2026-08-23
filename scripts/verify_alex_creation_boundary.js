// ══════════════════════════════════════════════════════════════════════════════════════════
// MOGO — executable verification of the ALEX **creation** boundary (D3C mutation M2)
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// WHY THIS EXISTS
//
// D3C placed the canonical geometry contract at ALEX's execution boundary. The gate sits AFTER
// `await fetchBidAsk(setup.pair)` inside async alexGAttemptOpenLivePosition, and the canonical JXA
// fixture runner cannot resolve a real await -- the same documented limitation that applies to
// closePaperPosition and alexGCloseLivePosition. So deleting that gate broke no fixture: mutation
// M2 survived the entire 2,513-fixture gate. Node resolves awaits natively, which is the whole
// difference. Nothing here is browser-specific; the missing capability was only await resolution.
//
// THIS IS ENGINE-LEVEL VERIFICATION, NOT BROWSER-RUNTIME VERIFICATION. It executes the real
// application code in a real JavaScript engine. It does NOT exercise a real browser, real network
// latency, real localStorage, or real timing. Do not describe D3C as browser-runtime verified on
// the strength of this file.
//
// ISOLATION (INC-004)
//
// No browser, no Chrome profile, no origin, no server, no network, no real storage. index.html is
// read READ-ONLY and is NEVER written -- the M2 mutation below is applied to an in-memory copy of
// the extracted script body, so a crashed or interrupted run cannot leave a mutated file behind.
// localStorage is an in-memory object; fetch() rejects; fetchBidAsk is stubbed to a fixed quote.
// INC-004's domain is not entered at all rather than being carefully navigated.
//
// It drives the REAL, UNMODIFIED async alexGAttemptOpenLivePosition and the REAL, PROTECTED,
// UNMODIFIED alexGConstructLivePosition. No application logic is reimplemented here; a
// reimplementation would prove only that the copy agrees with itself.
//
// USAGE
//   node scripts/verify_alex_creation_boundary.js              # the two controls
//   node scripts/verify_alex_creation_boundary.js --selftest   # controls + prove they can FAIL
//
// --selftest is the part that makes a green run mean something. It neutralises the D3C creation
// guard in memory and requires the negative control to fail. A verification that cannot fail is
// not evidence (CLAUDE.md).
//
// Exit 0 = everything behaved as required. Exit 1 = a control or the selftest failed.
// ══════════════════════════════════════════════════════════════════════════════════════════
'use strict';
const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..');
const INDEX = path.join(REPO, 'index.html');

// The exact source of the D3C creation gate. If this string ever stops matching, the gate has been
// edited or removed and this harness must FAIL LOUDLY rather than silently verify nothing.
const GATE_SRC = '  if(__d3cGeom.state!==TRADE_GEOMETRY.VALID){';
const GATE_MUT = '  if(false){ // M2 mutation -- creation-boundary geometry enforcement neutralised';

function loadAppCode(){
  const html = fs.readFileSync(INDEX, 'utf8');       // READ-ONLY. Never written.
  const m = html.match(/<script>([\s\S]*)<\/script>/);
  if (!m) throw new Error('Could not find <script> body in index.html');
  return m[1];
}

// ── a fresh sandbox per run, so one scenario cannot leak state into the next ────────────────
function buildSandbox(appCode){
  const elMap = {};
  const mkList = () => { const c = new Set(); return {add:x=>c.add(x),remove:x=>c.delete(x),
    toggle:(x,f)=>{ if(f===undefined){ c.has(x)?c.delete(x):c.add(x); } else if(f) c.add(x); else c.delete(x); },
    contains:x=>c.has(x)}; };
  const mkEl = () => ({innerHTML:'',textContent:'',value:'',className:'',style:{},
    options:[{value:'All'}],width:100,height:100,disabled:false,checked:false,classList:mkList(),
    getContext:()=>({clearRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillRect(){},
      save(){},restore(){},setLineDash(){},arc(){},fill(){},closePath(){},fillText(){},
      measureText:()=>({width:0})}),
    appendChild(){},addEventListener(){},focus(){},setSelectionRange(){},
    getBoundingClientRect:()=>({top:0,left:0,width:0,height:0})});
  const ls = {};
  globalThis.document = { getElementById:id=>(elMap[id]||(elMap[id]=mkEl())), querySelector:()=>null,
    querySelectorAll:()=>[], createElement:()=>mkEl(), addEventListener(){},
    body:{appendChild(){},removeChild(){}}, activeElement:null };
  globalThis.window = { devicePixelRatio:1 };
  globalThis.localStorage = { getItem:k=>Object.prototype.hasOwnProperty.call(ls,k)?ls[k]:null,
    setItem:(k,v)=>{ls[k]=v;}, removeItem:k=>{delete ls[k];},
    __keys:()=>Object.keys(ls), __clear:()=>Object.keys(ls).forEach(k=>delete ls[k]) };
  // No network of any kind. Anything reaching for one fails loudly rather than silently.
  globalThis.fetch = () => Promise.reject(new Error('no network in the creation-boundary harness'));
  globalThis.alert = () => {}; globalThis.confirm = () => true;
  globalThis.Blob = function(p,o){ return {parts:p,opts:o}; };
  globalThis.URL = { createObjectURL:()=>'blob:stub', revokeObjectURL(){} };
  let tid = 0;
  globalThis.setTimeout = () => ++tid; globalThis.clearTimeout = () => {};
  globalThis.setInterval = () => ++tid; globalThis.clearInterval = () => {};
  globalThis.ResizeObserver = function(){ return {observe(){},disconnect(){}}; };
  globalThis.LightweightCharts = { LineStyle:{Solid:0,Dashed:1,Dotted:2}, CrosshairMode:{Normal:0} };
  globalThis.Notification = undefined;

  const g = {};
  new Function('g', appCode + '\n' +
    'g.attempt=function(a,b,c,d){return alexGAttemptOpenLivePosition(a,b,c,d);};' +
    'g.construct=function(s,d,ba){return alexGConstructLivePosition(s,d,ba,RULES_ALEXG.config,alexGAccount.balance,{});};' +
    'g.stubBidAsk=function(fn){ fetchBidAsk=fn; };' +
    'g.stubCandles=function(fn){ alexGFetchExecutableCandles=fn; };' +
    'g.openPositions=function(){return alexGAccount.openPositions;};' +
    'g.reset=function(){ alexGAccount={balance:10000,startingBalance:10000,openPositions:[],closedPositions:[]};' +
    '  alexGJournalEntries=[]; alexGAutoTrading={enabled:false,tradedToday:{},log:[],activatedAt:null,tradedSignals:{}};' +
    '  alexGAccountKnownVersion=0; localStorage.__clear(); };' +
    'g.geometryFailures=function(){ return getDecisionEvents().filter(function(e){' +
    '  return e.reasonCode==="RISK_GEOMETRY_CONTRACT_VIOLATION"; }); };' +
    'g.MIN_RISK_PIPS=MIN_RISK_PIPS; g.pipSize=pipSize;'
  )(g);
  g.stubBidAsk(async () => ({bid:1.09999, ask:1.10001}));  // THE await THAT BLOCKS THE JXA RUNNER
  g.stubCandles(async () => null);                          // creation never needs these
  return g;
}

// ── scenarios ──────────────────────────────────────────────────────────────────────────────
// Flat H1 candles: calcATR reads c.h/c.l/c.c, so a constant half-range gives an exact chosen ATR.
const candles = half => Array.from({length:60}, (_,i) => {
  const b = 1.10000; return {t:1750000000+i*3600, o:b, h:b+half, l:b-half, c:b, v:100};
});
const mkSetup = (zoneLow, tag) => ({
  strategy:'alex_g_sr_v1', ruleVersion:'alex_g_sr_v1', pair:'EUR_USD', timeframe:'H1',
  setupId:'AGS|alex_g_sr_v1|EUR_USD|H1|AGZ|'+tag+'|A_repeatedReaction|AGR|'+tag,
  setupType:'A_repeatedReaction', setupLabel:'Repeated Zone Reaction',
  zoneRoleAtQualification:'support', qualificationBarIndex:59, qualificationClose:1.10000,
  qualificationTimestamp:1750216000000, zoneId:'AGZ|'+tag, reactionId:'AGR|'+tag,
  zoneTouchNumber:3, zoneStrength:3, zoneQualityAtQualification:'good',
  zoneLow:zoneLow, zoneHigh:1.10000, zoneCenter:(zoneLow+1.10000)/2, configurationSnapshot:null
});
// POSITIVE: ~12.6 pips. Historically representative -- the preserved corpus' tightest real ALEX
// risk distances are 5.027 (replay) and 7.262 (forward) pips.
const POS = { setup: mkSetup(1.09880,'POS'), datasets: {H1:candles(0.00010)} };
// NEGATIVE: ~0.65 pips. Reachable, not contrived: the REAL protected constructor returns
// TRADE OPENED for it, because its own stop check tests only the SIDE, never the distance.
const NEG = { setup: mkSetup(1.09995,'NEG'), datasets: {H1:candles(0.00001)} };

async function runControls(g){
  const out = {};

  g.reset();
  await g.attempt(POS.setup, POS.datasets, {}, 'verify-pos');
  const posOpen = g.openPositions();
  out.positive = { pass: posOpen.length === 1 && posOpen[0].status === 'open',
                   detail: 'openPositions=' + posOpen.length +
                     (posOpen[0] ? ' tradeId=' + posOpen[0].tradeId : '') };

  // Precondition: the negative control must be testing something the real engine can actually
  // produce. Without this, a "refused" result could just mean the setup never constructed.
  g.reset();
  const pre = g.construct(NEG.setup, NEG.datasets, {bid:1.09999, ask:1.10001});
  const risk = pre.position ? (pre.position.entry - pre.position.stop)/g.pipSize('EUR_USD') : null;
  out.precondition = { pass: pre.status === 'TRADE OPENED' && risk !== null && risk > 0 && risk < g.MIN_RISK_PIPS,
                       detail: 'ctor=' + pre.status + ' riskPips=' + (risk===null?'n/a':risk.toFixed(3)) +
                               ' floor=' + g.MIN_RISK_PIPS };

  g.reset();
  await g.attempt(NEG.setup, NEG.datasets, {}, 'verify-neg');
  const negOpen = g.openPositions();
  out.negative = { pass: negOpen.length === 0,
    detail: 'openPositions=' + negOpen.length + (negOpen.length
      ? ' *** ENTERED ACTIVE STATE *** ' + JSON.stringify({entry:negOpen[0].entry, stop:negOpen[0].stop,
          lots:negOpen[0].positionSize, units:Math.round(negOpen[0].positionSize*100000)}) : '') };

  const evs = g.geometryFailures();
  out.recorded = { pass: evs.length === 1 && evs[0].eventType === 'TRADE_OPEN_FAILED',
    detail: 'RISK_GEOMETRY_CONTRACT_VIOLATION events=' + evs.length +
            (evs[0] ? ' type=' + evs[0].eventType + ' reason=' + evs[0].reasonText : '') };
  return out;
}

const LABELS = {
  positive:    'POSITIVE CONTROL — historically representative ALEX geometry (~12.6 pips) reaches ACTIVE through the REAL async creation path',
  precondition:'PRECONDITION — the REAL protected alexGConstructLivePosition still returns TRADE OPENED for the sub-floor case, so the negative control tests a reachable geometry',
  negative:    'NEGATIVE CONTROL — sub-minimum-risk geometry (~0.65 pips) is REFUSED before entering ACTIVE state',
  recorded:    'NEGATIVE CONTROL — and the refusal is RECORDED under the registered reason code, not silently dropped'
};

(async function main(){
  const selftest = process.argv.includes('--selftest');
  const appCode = loadAppCode();

  if (appCode.split(GATE_SRC).length - 1 !== 1) {
    console.error('FAIL: the D3C creation gate was not found exactly once in index.html.');
    console.error('      Expected: ' + GATE_SRC.trim());
    console.error('      The gate has been edited or removed -- this harness refuses to report a');
    console.error('      pass it cannot justify.');
    process.exit(1);
  }

  let bad = 0;
  const res = await runControls(buildSandbox(appCode));
  for (const k of ['positive','precondition','negative','recorded']) {
    console.log((res[k].pass ? 'PASS' : 'FAIL') + ' -- ' + LABELS[k] + ' (' + res[k].detail + ')');
    if (!res[k].pass) bad++;
  }

  if (selftest) {
    console.log('');
    console.log('--- SELFTEST: mutation M2, creation-boundary enforcement neutralised (in memory) ---');
    // In MEMORY only. index.html is never written, so an interrupted run cannot leave a mutated
    // working tree behind -- the failure mode of doing this by hand.
    const mutated = appCode.replace(GATE_SRC, GATE_MUT);
    const mres = await runControls(buildSandbox(mutated));
    const killed = !mres.negative.pass;
    const posHeld = mres.positive.pass;
    console.log((killed ? 'PASS' : 'FAIL') + ' -- M2 KILLED: neutralising the creation guard makes ' +
      'the negative control fail (' + mres.negative.detail + ')');
    console.log((posHeld ? 'PASS' : 'FAIL') + ' -- and the POSITIVE control still holds under the ' +
      'mutation, so the kill is specific rather than the harness simply breaking (' +
      mres.positive.detail + ')');
    if (!killed) bad++;
    if (!posHeld) bad++;
  }

  console.log('---');
  console.log(bad === 0
    ? 'ALEX CREATION-BOUNDARY VERIFICATION: PASS' + (selftest ? ' (controls + M2 selftest)' : ' (controls only; add --selftest to prove they can fail)')
    : 'ALEX CREATION-BOUNDARY VERIFICATION: FAIL (' + bad + ' check(s))');
  process.exit(bad === 0 ? 0 : 1);
})().catch(e => { console.error('HARNESS ERROR: ' + ((e && e.stack) || e)); process.exit(2); });
