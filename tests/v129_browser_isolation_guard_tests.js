// INC-001 load-integrity correction + INC-004 browser-isolation guards (v12.8.1).
//
// Two groups of fixtures:
//   L*  — INC-001 behaviour, executed against the REAL loadSaved()/loadAlexGSaved()/
//         loadAlexV2Saved()/save()/saveAlexGRest()/savePaperAccountGuarded()/
//         saveAlexGAccountGuarded() from index.html, driven through a controllable
//         localStorage stub. Nothing is re-implemented here.
//   G*  — INC-004 repository-level isolation guards: static assertions over the real shipped
//         source of index.html, tests/, and scripts/.
//
// ⚠️ HONEST LIMIT, stated here and in docs/KNOWN_ISSUES.md: the G* guards can only constrain what
// the REPOSITORY contains. INC-004 was caused by ad-hoc inline JavaScript issued at the tool layer
// — a storage-clearing call typed directly into a live tab — which no repository fixture can
// intercept. These guards prevent a committed regression; they do not and cannot prevent an agent
// from repeating the incident by hand. That control is procedural — see docs/TESTING.md.
//
// NOTE ON SELF-SCANNING: the forbidden constructs are assembled at runtime from fragments (see
// GROUP G), so this file contains none of them as literals and can therefore scan its own source
// alongside the others. A guard forced to exempt itself would have a hole in exactly the wrong place.
function runBrowserIsolationGuardFixtures(g){
  const out=[];
  function t(name,fn){
    try{ const d=fn(); out.push({name,pass:true,detail:d||''}); }
    catch(e){ out.push({name,pass:false,detail:(e&&e.message)?e.message:String(e)}); }
  }
  function eq(a,b,m){ if(a!==b) throw new Error((m||'')+' expected '+JSON.stringify(b)+', got '+JSON.stringify(a)); }
  function ok(v,m){ if(!v) throw new Error(m||'expected truthy'); }
  function no(v,m){ if(v) throw new Error(m||'expected falsy'); }

  const SRC=g.appSource||'';
  const SHELL=g.shellSource||'';
  const V128=g.v128Source||'';
  const V129=g.v129Source||'';

  // ══ GROUP L — INC-001 LOAD INTEGRITY (real functions, real behaviour) ═══════════════════

  t('L1 a corrupt key no longer suppresses the keys after it',function(){
    g.resetStorage({
      fxhub_scan:'{"NOT VALID JSON',                       // corrupt, FIRST in load order
      fxhub_journal:JSON.stringify([{tradeId:'J1'}]),
      fxhub_paper:JSON.stringify({balance:12345,openPositions:[],closedPositions:[{tradeId:'P1'}]}),
      fxhub_paper_version:'7'
    });
    g.resetLoadFailures();
    g.loadSaved();
    eq(g.getJournalEntries().length,1,'the journal must still load even though an earlier key was corrupt');
    eq(g.getPaperAccount().balance,12345,'the paper account must still load');
    eq(g.getPaperAccountKnownVersion(),7,'the version must still load');
  });

  t('L2 the corrupt key itself is recorded as a load failure',function(){
    g.resetStorage({fxhub_scan:'{"NOT VALID JSON'});
    g.resetLoadFailures();
    g.loadSaved();
    ok(g.storageKeyBlockedFromWrite('fxhub_scan'),'a present-but-unreadable key must be recorded');
    ok(g.storageLoadFailureKeys().indexOf('fxhub_scan')!==-1);
  });

  t('L3 an ABSENT key is not a failure and stays writable',function(){
    g.resetStorage({});                                    // nothing stored at all
    g.resetLoadFailures();
    g.loadSaved();
    eq(g.storageLoadFailureKeys().length,0,'absent keys must not be treated as failures');
    no(g.storageKeyBlockedFromWrite('fxhub_scan'),'a fresh install must be able to write normally');
  });

  t('L4 THE INCIDENT ITSELF: save() can no longer overwrite an unreadable key',function(){
    const realScan='{"CORRUPT BUT REAL USER DATA';
    g.resetStorage({fxhub_scan:realScan});
    g.resetLoadFailures();
    g.loadSaved();                                          // fxhub_scan fails to parse
    g.setScanData({wiped:true});                            // in-memory default/garbage
    g.saveJvm();                                            // the write that used to destroy data
    eq(g.rawStorage().fxhub_scan,realScan,'the stored bytes MUST be untouched — this is INC-001');
  });

  t('L5 keys that DID load correctly are still written normally',function(){
    g.resetStorage({fxhub_scan:'{"NOT VALID JSON',fxhub_alerts:JSON.stringify([{a:1}])});
    g.resetLoadFailures();
    g.loadSaved();
    g.setAlertLog([{a:1},{a:2}]);
    g.saveJvm();
    eq(JSON.parse(g.rawStorage().fxhub_alerts).length,2,'a healthy key must still persist — the fix must not freeze all writes');
    eq(g.rawStorage().fxhub_scan,'{"NOT VALID JSON','while the unreadable key stays protected');
  });

  t('L6 ALEX: a corrupt zones key no longer suppresses setups',function(){
    g.resetStorage({
      fxhub_alexg_zones:'{BROKEN',
      fxhub_alexg_setups:JSON.stringify([{setupId:'S1'},{setupId:'S2'}])
    });
    g.resetLoadFailures();
    g.loadAlexGSaved();
    eq(g.getAlexGSetupState().length,2,'setups must load even though zones was corrupt');
    ok(g.storageKeyBlockedFromWrite('fxhub_alexg_zones'));
  });

  t('L7 saveAlexGRest() cannot overwrite an unreadable ALEX key',function(){
    const realZones='{BROKEN BUT REAL';
    g.resetStorage({fxhub_alexg_zones:realZones});
    g.resetLoadFailures();
    g.loadAlexGSaved();
    g.setAlexGZoneState({wiped:true});
    g.saveAlexGRest();
    eq(g.rawStorage().fxhub_alexg_zones,realZones,'stored zone bytes must be untouched');
  });

  t('L8 JVM LEDGER: a commit is BLOCKED when the account key was unreadable',function(){
    const realPaper='{CORRUPT BUT REAL LEDGER';
    g.resetStorage({fxhub_paper:realPaper,fxhub_paper_version:'3'});
    g.resetLoadFailures();
    g.loadSaved();
    const r=g.savePaperAccountGuarded();
    no(r.ok,'the commit must be refused');
    eq(r.reason,'LOAD_INTEGRITY_BLOCKED');
    eq(r.integrityCompromised,false,'refusing to write is not an integrity compromise');
    eq(g.rawStorage().fxhub_paper,realPaper,'the real stored ledger must be untouched');
  });

  t('L9 ALEX LEDGER: a commit is BLOCKED when the account key was unreadable',function(){
    const realAcct='{CORRUPT BUT REAL ALEX LEDGER';
    g.resetStorage({fxhub_alexg_account:realAcct,fxhub_alexg_account_version:'5'});
    g.resetLoadFailures();
    g.loadAlexGSaved();
    const r=g.saveAlexGAccountGuarded();
    no(r.ok);
    eq(r.reason,'LOAD_INTEGRITY_BLOCKED');
    eq(g.rawStorage().fxhub_alexg_account,realAcct,'the real stored ALEX ledger must be untouched');
  });

  t('L10 a healthy ledger still commits normally — the guard is not a freeze',function(){
    g.resetStorage({
      fxhub_alexg_account:JSON.stringify({balance:10000,openPositions:[],closedPositions:[]}),
      fxhub_alexg_account_version:'2',
      fxhub_alexg_journal:JSON.stringify([])
    });
    g.resetLoadFailures();
    g.loadAlexGSaved();
    const r=g.saveAlexGAccountGuarded();
    ok(r.ok,'a clean load must still permit a normal commit');
    eq(JSON.parse(g.rawStorage().fxhub_alexg_account_version),3,'the version must advance normally');
  });

  t('L11 the missing-version hole is closed by the same guard',function(){
    // account present but unreadable AND no version key: 0 > 0 is false, so the pre-existing
    // staleness guard alone would have let a default account overwrite real data.
    const realAcct='{CORRUPT BUT REAL';
    g.resetStorage({fxhub_alexg_account:realAcct});          // deliberately no version key
    g.resetLoadFailures();
    g.setAlexGAccountKnownVersion(0);                        // as on a genuine fresh page load
    g.loadAlexGSaved();
    eq(g.getAlexGAccountKnownVersion(),0,'an absent version key must leave the session at version 0');
    const r=g.saveAlexGAccountGuarded();
    no(r.ok,'the load-integrity guard must catch what the version guard cannot');
    eq(r.reason,'LOAD_INTEGRITY_BLOCKED');
    eq(g.rawStorage().fxhub_alexg_account,realAcct);
  });

  t('L12 a load failure is reported loudly, never silently',function(){
    g.resetStorage({fxhub_alexg_account:'{BROKEN'});
    g.resetLoadFailures();
    g.clearEngineErrors();
    g.loadAlexGSaved();
    const alex=g.getAlexGEngineErrors(),paper=g.getPaperEngineErrors();
    ok(alex.length>0,'the ALEX engine-error channel must carry the failure');
    ok(paper.length>0,'the paper engine-error channel must carry it too');
    ok(/STORAGE LOAD FAILURE/.test(alex[0].message),'the message must name the failure plainly');
    ok(/will NOT overwrite/i.test(alex[0].message),'and must tell the operator their data is preserved');
  });

  t('L13 ALEX v2 loader is isolated per key as well',function(){
    g.resetStorage({
      fxhub_alexv2_account:'{BROKEN',
      fxhub_alexv2_journal:JSON.stringify([{id:1},{id:2},{id:3}])
    });
    g.resetLoadFailures();
    g.loadAlexV2Saved();
    eq(g.getAlexV2JournalEntries().length,3,'a later v2 key must still load');
    ok(g.storageKeyBlockedFromWrite('fxhub_alexv2_account'));
  });

  t('L14 a storage read that THROWS is handled like an unreadable value',function(){
    g.resetStorage({fxhub_scan:'{}'});
    g.resetLoadFailures();
    g.setGetItemThrowing(true);
    let threw=false;
    try{ g.loadSaved(); }catch(e){ threw=true; }
    g.setGetItemThrowing(false);
    no(threw,'loadSaved() must never throw outward');
    ok(g.storageLoadFailureKeys().length>0,'every key that could not be read must be protected');
  });

  // ══ GROUP G — INC-004 REPOSITORY-LEVEL ISOLATION GUARDS ════════════════════════════════

  // The forbidden constructs are assembled at RUNTIME from fragments, so this guard file itself
  // contains none of them as literals. That means it can legitimately scan its own source too --
  // a guard that had to exempt itself would be a guard with a hole in exactly the wrong place.
  const CLEAR_LS   = 'localStorage'+'.'+'clear';
  const CLEAR_SS   = 'sessionStorage'+'.'+'clear';
  const DROP_IDB   = 'indexedDB'+'.'+'deleteDatabase';
  const OPERATOR_PROFILE_PATH = 'Application Support/Google/'+'Chrome/'+'Profile';

  t('G1 no committed source performs a destructive browser-storage call',function(){
    [['index.html',SRC],['tests/v128 suite',V128],['tests/v129 suite',V129],['scripts launcher',SHELL]]
      .forEach(function(pair){
        const name=pair[0],body=pair[1];
        eq(body.indexOf(CLEAR_LS+'('),-1,name+' must not clear localStorage');
        eq(body.indexOf(CLEAR_SS+'('),-1,name+' must not clear sessionStorage');
        eq(body.indexOf(DROP_IDB+'('),-1,name+' must not drop an IndexedDB database');
      });
  });

  t('G2 no committed file targets the operator Chrome profile directory',function(){
    // Prose ABOUT the incident is welcome and necessary; a PATH pointing at the operator's real
    // profile is not. This guard forbids the path, never the discussion.
    [['index.html',SRC],['launcher',SHELL],['v128',V128],['v129',V129]].forEach(function(pair){
      eq(pair[1].indexOf(OPERATOR_PROFILE_PATH),-1,
        pair[0]+' must not reference the operator Chrome profile directory');
    });
    // The launcher may name the operator Chrome root — but only in order to REFUSE it.
    ok(/fail "profile root resolves inside the operator's Chrome directory/.test(SHELL),
      'the launcher must name the operator Chrome root only to reject it');
  });

  t('G3 the isolation launcher exists and is a real shell script',function(){
    ok(SHELL.length>0,'scripts/browser_test_profile.sh must exist');
    ok(SHELL.indexOf('#!/usr/bin/env bash')===0,'it must be an executable bash script');
    ok(/set -euo pipefail/.test(SHELL),'it must abort on any error or unset variable');
  });

  t('G4 the launcher uses a disposable --user-data-dir and never the default profile',function(){
    ok(/--user-data-dir=/.test(SHELL),'Chrome must be launched with an explicit user-data-dir');
    ok(/PROFILE_DIR=/.test(SHELL),'the profile directory must be computed, not fixed');
    ok(/mkdir -p "\$PROFILE_DIR"/.test(SHELL),'the profile must be created fresh');
  });

  t('G5 the launcher FAILS CLOSED and never falls back to the operator profile',function(){
    ok(/fail\(\)/.test(SHELL),'it must define a failure path');
    ok(/exit 1/.test(SHELL),'failure must exit non-zero');
    ok(/OPERATOR_CHROME/.test(SHELL),'it must know where the operator profile lives in order to refuse it');
    ok(/refusing to reuse/.test(SHELL),'it must refuse to reuse an existing profile directory');
    ok(!/\|\|\s*true/.test(SHELL),'no guard may be swallowed with "|| true"');
  });

  t('G6 the launcher requires an EXPLICIT origin and never infers one',function(){
    ok(/--origin is required/.test(SHELL),'the origin must be mandatory');
    ok(/never be inferred/.test(SHELL),'and explicitly documented as never inferred — INC-004 root cause');
    ok(SHELL.indexOf('launch.json')!==-1,'the launcher must name the config file that must NOT be trusted');
  });

  t('G7 the launcher records the four required pre-test facts',function(){
    ['test_profile_path','test_origin','is_operator_profile','pre_clear_inventory'].forEach(function(k){
      ok(SHELL.indexOf(k)!==-1,'the isolation manifest must record '+k);
    });
  });

  t('G8 the launcher verifies the new profile is genuinely empty before use',function(){
    ok(/is not empty/.test(SHELL),'it must assert emptiness');
    ok(/already contains browser storage/.test(SHELL),'and refuse a profile that already holds storage');
  });

  t('G9 the Browser Testing Policy mandates the isolated profile',function(){
    const policy=g.testingDoc||'';
    ok(policy.indexOf('browser_test_profile.sh')!==-1,'TESTING.md must name the launcher');
    ok(/INC-004/.test(policy),'TESTING.md must reference the incident that created the rule');
    ok(/never/i.test(policy)&&/operator/i.test(policy),'TESTING.md must state the never-touch-operator-profile rule');
  });

  t('G10 the incident is recorded in the incident log with its proven cause',function(){
    const inc=g.incidentsDoc||'';
    ok(/INC-004/.test(inc),'INCIDENTS.md must contain INC-004');
    ok(/localhost:8744/.test(inc),'it must name the origin that was cleared');
    ok(/localStorage\.clear/.test(inc),'it must name the destructive call');
    ok(/Profile 2/.test(inc),'it must name the profile that was used');
  });

  t('G11 the limitation of these guards is disclosed, not implied away',function(){
    const known=g.knownIssuesDoc||'';
    ok(/INC-004/.test(known),'KNOWN_ISSUES.md must carry the disclosure');
    ok(/tool layer|inline/i.test(known),'it must state that inline tool-layer scripts are not interceptable');
  });

  t('G12 INC-001 protection is wired into BOTH guarded ledger savers',function(){
    ok(/function savePaperAccountGuarded\(\)\{[\s\S]{0,1600}?LOAD_INTEGRITY_BLOCKED/.test(SRC),
      'the JVM guarded saver must carry the load-integrity block');
    ok(/function saveAlexGAccountGuarded\(\)\{[\s\S]{0,1600}?LOAD_INTEGRITY_BLOCKED/.test(SRC),
      'the ALEX guarded saver must carry it too');
    ok(SRC.indexOf('function persistStorageKey(')!==-1,'the guarded write helper must exist');
    ok(!/function save\(\)\{[\s\S]{0,700}?localStorage\.setItem/.test(SRC),
      'the unguarded JVM save() must no longer call localStorage.setItem directly');
  });

  return out;
}
