# MOGO-011 — REPOSITORY CONFIGURATION REPORT

**Objective:** allow a bare `git push` to target `origin/mogo-main`, without weakening any repository safety guarantee.
**Status:** **applied and verified — nothing pushed, no history touched, no tracked file changed**
**Date:** 2026-08-08
**Repository:** `/Users/joemogollon/Desktop/Forex Hub` · branch `main` · HEAD `7b2c0aa940d185995305e45a209edf063050e10b`

---

## 1. The problem, precisely

The local branch is `main`; its upstream is `origin/mogo-main`. The names differ.

`push.default` was **unset in every scope**, so Git used its built-in default, `simple`. Under
`simple`, a bare `git push` pushes the current branch to its upstream **only when the two branch
names match**. They do not, so Git refused:

```
fatal: The upstream branch of your current branch does not match
the name of your current branch.  To push to the upstream branch
on the remote, use

    git push origin HEAD:mogo-main
```

Every push therefore required an explicit refspec — the friction this change removes.

---

## 2. Previous configuration

### System — `/Library/Developer/CommandLineTools/usr/share/git-core/gitconfig`
```
credential.helper=osxkeychain
init.defaultbranch=main
```

### Global — `/Users/joemogollon/.gitconfig`
```
user.name=Joe Mogollon
user.email=joemogollon025@gmail.com
```

### Repository — `.git/config`
```
core.repositoryformatversion=0
core.filemode=true
core.bare=false
core.logallrefupdates=true
core.ignorecase=true
core.precomposeunicode=true
user.name=Joe Mogollon
extensions.worktreeconfig=true
remote.origin.url=https://github.com/joemogo/forex_hub.git
remote.origin.fetch=+refs/heads/*:refs/remotes/origin/*
branch.main.remote=origin
branch.main.merge=refs/heads/mogo-main
```

### Relevant absences, confirmed before the change

| Setting | State |
|---|---|
| `push.default` | **unset in system, global and local** → built-in `simple` |
| `remote.origin.push` | **unset** — no push refspec configured |
| Worktree config (`.git/config.worktree`) | **does not exist**, despite `extensions.worktreeconfig=true` |

---

## 3. New configuration

**Exactly one setting was added, at repository scope:**

```bash
git config --local push.default upstream
```

`.git/config` gains one line:

```
push.default=upstream
```

**Nothing else was added, changed or removed** in any scope. The global and system files are
byte-unchanged.

---

## 4. Why this is the smallest safe change

`simple` is defined as `upstream` **plus** a guard that the local and remote branch names match.
The name guard is the only thing failing here. Switching to `upstream` removes exactly that one
check and alters nothing else about push routing — there is no smaller delta available, because
Git offers no per-branch `push.default`.

### Alternatives considered and rejected

| Option | Verdict |
|---|---|
| `remote.origin.push = refs/heads/main:refs/heads/mogo-main` | **Rejected.** A configured push refspec applies to `git push origin` from **any** branch, so a bare push while standing on `mogo-003-phase-1-evidence-platform` would silently push `main`. Broader and more surprising than the problem. |
| `push.default = current` | **Rejected — actively dangerous here.** It pushes to a remote branch of the *same name*, and `origin/main` **exists as a separate branch** at `abfc7634…`, distinct from `origin/mogo-main` at `c50f95c…`. This would have pushed MOGO work onto the wrong branch. |
| `push.default = matching` | **Rejected.** Pushes every branch whose name matches a remote branch — the legacy behaviour Git abandoned precisely because it publishes work nobody asked to publish. |
| Rename local `main` → `mogo-main` | **Rejected.** Makes names match, but renames a ref that a linked worktree and existing tooling refer to. A larger change than the problem warrants. |
| Leave as-is, always use an explicit refspec | Safe, and it is the status quo the objective asks to improve. Retained as the rollback position. |

---

## 5. Why it cannot alter history or remote state

Verified **before** applying:

1. **`push.default` is a routing preference, not an action.** It is consulted only when a push is
   invoked, to decide *which refspec* an argument-less `git push` implies. It rewrites no object,
   creates no commit, moves no local ref, and deletes nothing.
2. **It cannot force-push.** It does not imply `--force`, `--force-with-lease` or `--delete`. A
   non-fast-forward push is still rejected by the remote.
3. **It cannot create a remote branch by surprise.** `upstream` can only target a branch already
   configured as the upstream — here `refs/heads/mogo-main`, which exists. This is precisely the
   property `current` lacks.
4. **`--local` scope confines it to this repository.** It is written to `.git/config`, which is
   **not a tracked file** and is not part of any commit boundary. No other repository on this
   machine is affected; `push.default` remains unset globally.
5. **It affects only branches that have an upstream.** The other two local branches have none, so a
   bare `git push` from either still refuses rather than guessing.

### The one behavioural difference, stated plainly

`upstream` drops the name-match guard. If a future branch is configured to track a
differently-named remote branch, a bare `git push` will push there **without** the warning `simple`
would have raised. For `main → origin/mogo-main` that is exactly the intent; it is recorded here so
it is a known property rather than a surprise.

---

## 6. Verification commands and results

All five requested checks were run **after** applying the change.

### 6.1 `git branch -vv`

```
+ claude/gracious-cohen-bd8041       4fb117e (…/.claude/worktrees/gracious-cohen-bd8041) Add canonical repository test runner (tests/run_all.sh)
* main                               7b2c0aa [origin/mogo-main: ahead 1] MOGO-011 Step 2: retry, lease and dead-letter handling
  mogo-003-phase-1-evidence-platform c638629 Market Data Completeness Contract (ADR-011)
```

`main` tracks `origin/mogo-main`, ahead 1. The other two branches have **no upstream** and are
therefore untouched by this setting.

### 6.2 `git remote -v`

```
origin	https://github.com/joemogo/forex_hub.git (fetch)
origin	https://github.com/joemogo/forex_hub.git (push)
```

**One remote only.** No second remote exists to be affected.

### 6.3 `git config --list --show-origin`

```
file:/Library/Developer/CommandLineTools/usr/share/git-core/gitconfig	credential.helper=osxkeychain
file:/Library/Developer/CommandLineTools/usr/share/git-core/gitconfig	init.defaultbranch=main
file:/Users/joemogollon/.gitconfig	user.name=Joe Mogollon
file:/Users/joemogollon/.gitconfig	user.email=joemogollon025@gmail.com
file:.git/config	core.repositoryformatversion=0
file:.git/config	core.filemode=true
file:.git/config	core.bare=false
file:.git/config	core.logallrefupdates=true
file:.git/config	core.ignorecase=true
file:.git/config	core.precomposeunicode=true
file:.git/config	user.name=Joe Mogollon
file:.git/config	extensions.worktreeconfig=true
file:.git/config	remote.origin.url=https://github.com/joemogo/forex_hub.git
file:.git/config	remote.origin.fetch=+refs/heads/*:refs/remotes/origin/*
file:.git/config	branch.main.remote=origin
file:.git/config	branch.main.merge=refs/heads/mogo-main
file:.git/config	push.default=upstream          <-- THE ONLY ADDITION
```

Every other line is identical to the pre-change listing. The addition is in `.git/config`, the
repository-local file, which is untracked by design.

### 6.4 `git status`

```
On branch main
Your branch is ahead of 'origin/mogo-main' by 1 commit.
  (use "git push" to publish your local commits)

Untracked files:
  … 22 MOGO report / notebook / legacy documents …

nothing added to commit but untracked files present
```

Two things to note: the hint now reads **`use "git push"`** rather than an explicit refspec, and
**no tracked file is modified** — the working tree contains only the same 22 untracked documents
that were there before.

### 6.5 `git push --dry-run --verbose`

```
Pushing to https://github.com/joemogo/forex_hub.git
To https://github.com/joemogo/forex_hub.git
   c50f95c..7b2c0aa  main -> mogo-main
exit=0
```

- **`main -> mogo-main`** — the bare push now resolves to the authoritative branch.
- **`c50f95c..7b2c0aa`** — two-dot range with no `+` prefix and no `forced update` marker, i.e. a
  **fast-forward**. Nothing would be rewritten.
- **Exactly one ref update.** No other branch appears.

---

## 7. Confirmations

| # | Claim | Evidence |
|---|---|---|
| 1 | `git push` now targets `origin/mogo-main` | dry-run prints `main -> mogo-main`, exit 0 |
| 2 | No other remotes affected | `git remote -v` shows exactly one remote, `origin` |
| 3 | No other branches affected | the other two local branches have **no upstream**; the dry-run lists one ref update; `origin/evidence-platform-v12.19` and `origin/main` are untouched |
| 4 | No tracked files changed | `git status --porcelain` excluding untracked = **0** |
| 5 | Working tree clean | 0 tracked modifications; only the 22 pre-existing untracked documents |
| 6 | No history modified | HEAD still `7b2c0aa940d185995305e45a209edf063050e10b`; no commit created, no amend, no rebase, no reset |
| 7 | **No network mutation** | `git ls-remote origin refs/heads/mogo-main` after the dry-run still returns **`c50f95ca839fd41f75e56f93997d82928261f0b3`** — the remote is unmoved |
| 8 | Nothing pushed | remote is 1 commit behind local, as before |

**On the dry-run and the network.** `git push --dry-run` does open a connection and negotiate with
the remote — that is a network *read*. It performs no ref update and transfers no objects, and the
post-run `ls-remote` above proves the remote branch is still at the pre-existing commit. This was
the only network contact made.

---

## 8. Rollback procedure

The change is a single key in a single untracked file, and is reversible in one command.

**Full rollback — restore the built-in `simple` behaviour:**

```bash
git config --local --unset push.default
```

Verify:

```bash
git config --local --get push.default      # expect: no output, exit 1
git push --dry-run                          # expect: the original "does not match" fatal
```

After rollback, pushes again require the explicit form:

```bash
git push origin HEAD:mogo-main
```

**Nothing else is required.** No commit to revert, no ref to restore, no remote state to repair —
the change never touched any of them. A manual edit to `.git/config` removing the
`push.default = upstream` line under `[push]` is equivalent.

---

## 9. Recommendation

**Keep the change.** It is the minimum viable fix, it is repository-scoped, it is reversible with
one command, and it removed a real source of friction that had already contributed to a
publish-time mistake risk in this milestone.

Two further points, offered rather than acted on — both would change more than the objective asked
for, and neither is needed:

1. **The underlying oddity is the `main` → `mogo-main` name mismatch**, not the push setting.
   `origin/main` exists as a *different* branch at `abfc7634…`, so the local `main` is arguably
   misnamed for what it tracks. Renaming the local branch to `mogo-main` would make the names agree
   and let `simple` work unmodified — the cleanest end state, but it touches a ref that a linked
   worktree and existing tooling reference. **Recommend raising it as a separate governed decision**,
   alongside the branch-naming policy already carried as an open repository-wide item.
2. **`user.name` is set redundantly in `.git/config`** as well as globally. Harmless — the values
   agree — but it is what caused the earlier identity gap: a local `user.name` with no local
   `user.email` made Git auto-derive the email. Now that the global email is set the effective
   identity resolves correctly (`Joe Mogollon <joemogollon025@gmail.com>`), so **no change is
   proposed**; it is recorded so the cause is not rediscovered later.

---

## 10. State at the end of this task

| | |
|---|---|
| Configuration changed | `push.default=upstream`, **repository scope only** |
| Tracked files changed | **0** |
| Commits created | **0** |
| History modified | **none** — HEAD `7b2c0aa940d185995305e45a209edf063050e10b` |
| Pushed | **no** — `origin/mogo-main` still at `c50f95ca839fd41f75e56f93997d82928261f0b3` |
| Working tree | clean of tracked modifications; 22 untracked documents (23 with this report) |
| MOGO-011 Step 3 | **not started** |

**Stopped here as instructed.**
