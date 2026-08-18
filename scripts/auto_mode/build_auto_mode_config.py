#!/usr/bin/env python3
"""Generate the Claude Code auto-mode configuration for MOGO.

WHY THIS EXISTS
---------------
Auto mode is configured by an `autoMode` block in the USER settings file
(~/.claude/settings.json). Two facts about it determine this script's shape, and
both were established by probing the installed CLI rather than assumed:

1. The block is read from the user settings file only. A project-level
   `.claude/settings.json` is ignored for auto-mode purposes -- writing an
   `autoMode` section there changes nothing.

2. Each section REPLACES the shipped defaults; it does not merge with them.
   Setting `allow` alone drops all 17 default allow rules AND all 20 default
   environment entries. So any customisation has to re-emit the defaults.

Because the user settings file is global, MOGO's rules would otherwise apply to
every repository on this machine. They do not, because each MOGO rule states its
own scope IN ITS OWN TEXT. The shared `MOGO ` label prefix is a naming convention
and means nothing to the classifier, so a rule that merely carries the prefix
without naming the trusted repository is machine-wide policy by accident -- an
adversarial review of the first draft found two such rules. Other checkouts
(Life OS, DFS) keep default treatment.

WHAT IT DOES
------------
Reads the shipped defaults from the installed CLI, appends the MOGO delta from
`mogo_rules.json`, and writes the result to the user settings file -- preserving
every other setting in that file and taking a timestamped backup first.

Re-run it after a Claude Code upgrade so newly shipped default rules are picked
up; the generated block is otherwise frozen at the defaults of whichever version
last generated it.

    python3 scripts/auto_mode/build_auto_mode_config.py --diff    # show, write nothing
    python3 scripts/auto_mode/build_auto_mode_config.py --check   # exit 1 if drifted
    python3 scripts/auto_mode/build_auto_mode_config.py --write

Verify afterwards with `claude auto-mode config`, and get an independent read on
the rules with `claude auto-mode critique`.
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.path.join(HERE, "mogo_rules.json")
SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")

# Sections that are rule lists. `hard_deny` is deliberately absent: MOGO adds
# nothing to it, so leaving it unset keeps the shipped Data Exfiltration rule
# authoritative and current instead of freezing a copy of it here.
SECTIONS = ("environment", "allow", "soft_deny")


def shipped_defaults():
    """The defaults from the installed CLI, so the copy tracks the version in use."""
    out = subprocess.run(["claude", "auto-mode", "defaults"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def label_of(rule):
    """A rule's label.

    Splitting on the first ':' is wrong: a soft_deny rule reads
    `Git Destructive [named+specifics -- **must name:** the target]: ...` and the
    bar itself contains a colon, so a naive split yields a truncated label and the
    collision check compares garbage to garbage. The label ends at the bar when
    there is one, and at the first colon otherwise.
    """
    head = rule.split(" [", 1)[0]
    return head.split(":", 1)[0].strip()


def mogo_delta(path=RULES_PATH):
    with open(path, "r", encoding="utf-8") as handle:
        rules = json.load(handle)
    unknown = set(rules) - set(SECTIONS) - {"_readme"}
    if unknown:
        # Notably `hard_deny`: it is not generated, so a rule added there would be
        # silently dropped -- and hard_deny is where the most consequential rule
        # would go. Fail loudly rather than discard it.
        raise SystemExit(
            "refusing to generate: %s contains section(s) %s that this generator "
            "does not emit, so their rules would be silently dropped. Either add "
            "them to SECTIONS deliberately or remove them."
            % (os.path.basename(path), ", ".join(sorted(unknown))))
    return {section: rules.get(section, []) for section in SECTIONS}


def build(defaults, delta):
    """Defaults first, MOGO rules appended.

    Order matters for readability in a decision trace, not for evaluation: the
    shipped rules read as the baseline and the MOGO block reads as local policy.
    """
    config = {}
    for section in SECTIONS:
        base = list(defaults.get(section, []))
        added = list(delta.get(section, []))
        # Seeded from the shipped rules, then GROWN as MOGO rules are accepted --
        # otherwise two MOGO rules sharing a label pass each other silently, which
        # is the exact ambiguity this check exists to prevent.
        labels = {label_of(rule) for rule in base}
        for rule in added:
            label = label_of(rule)
            if label in labels:
                raise SystemExit(
                    "refusing to generate: rule label %r appears twice. A duplicate "
                    "label makes a decision trace ambiguous about which rule fired."
                    % label)
            labels.add(label)
        config[section] = base + added
    return config


def load_settings(path=SETTINGS_PATH):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_settings(config, path=SETTINGS_PATH, now=None):
    """Replace only the autoMode block. Every other setting is preserved."""
    settings = load_settings(path)
    if os.path.exists(path):
        stamp = (now or datetime.datetime.now(datetime.timezone.utc)).strftime(
            "%Y%m%dT%H%M%SZ")
        backup = "%s.pre-mogo-automode.%s.bak" % (path, stamp)
        shutil.copy2(path, backup)
    else:
        backup = None
    settings["autoMode"] = config
    with open(path, "w", encoding="utf-8") as handle:
        # ensure_ascii=False deliberately: the shipped rules are full of em dashes,
        # and escaping them turns 62KB of policy into — soup that no one can
        # read or diff. The settings file is UTF-8.
        json.dump(settings, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return backup


def check_drift(config, path=SETTINGS_PATH):
    """Is the installed block still the one this repo would generate?

    Because sections REPLACE the defaults, every rule shipped by a newer Claude
    Code is silently absent from the installed block until someone re-runs this.
    Nothing warns. This turns that silent policy regression into a check that can
    fail in CI.

    Returns a list of human-readable drift descriptions; empty means in sync.
    """
    installed = load_settings(path).get("autoMode")
    if not installed:
        return ["no autoMode block is installed in %s" % path]
    drift = []
    for section in SECTIONS:
        want, have = config[section], installed.get(section, [])
        if want == have:
            continue
        missing = [label_of(r) for r in want if r not in have]
        extra = [label_of(r) for r in have if r not in want]
        # A label on both sides is one rule whose TEXT changed, not two problems.
        # Reporting it twice is what made the first version of this unreadable.
        changed = [lab for lab in missing if lab in extra]
        missing = [lab for lab in missing if lab not in extra]
        extra = [lab for lab in extra if lab not in changed]
        parts = ["%s: %d installed vs %d generated" % (section, len(have), len(want))]
        for name, labels in (("reworded", changed), ("missing", missing),
                             ("unexpected", extra)):
            if labels:
                shown = ", ".join(labels[:5])
                more = "" if len(labels) <= 5 else " (+%d more)" % (len(labels) - 5)
                parts.append("%s: %s%s" % (name, shown, more))
        drift.append("; ".join(parts))
    for section in set(installed) - set(SECTIONS):
        drift.append("%s: installed block carries a section this generator does "
                     "not emit" % section)
    return drift


def summarize(config, defaults):
    lines = []
    for section in SECTIONS:
        base = len(defaults.get(section, []))
        total = len(config[section])
        lines.append("  %-12s %3d shipped + %2d MOGO = %3d"
                     % (section, base, total - base, total))
    lines.append("  %-12s %3d shipped (left unset -- shipped rule stays authoritative)"
                 % ("hard_deny", len(defaults.get("hard_deny", []))))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--write", action="store_true",
                        help="write the autoMode block to the user settings file")
    parser.add_argument("--diff", action="store_true",
                        help="list the MOGO rule labels that would be added")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if the installed block has drifted from what "
                             "this repo generates (e.g. after a Claude Code upgrade)")
    args = parser.parse_args(argv)

    defaults = shipped_defaults()
    delta = mogo_delta()
    config = build(defaults, delta)

    if args.check:
        drift = check_drift(config)
        if not drift:
            print("auto-mode config IN SYNC (%d environment / %d allow / %d soft_deny)"
                  % tuple(len(config[s]) for s in SECTIONS))
            return 0
        print("auto-mode config HAS DRIFTED from what this repository generates:")
        for line in drift:
            print("  " + line)
        print("\nRe-run with --write to bring it back in sync.")
        return 1

    print("MOGO auto-mode configuration")
    print(summarize(config, defaults))

    if args.diff or not args.write:
        print("\nMOGO rules added:")
        for section in SECTIONS:
            for rule in delta[section]:
                print("  %-12s %s" % (section, label_of(rule)))

    if not args.write:
        print("\nNothing written. Re-run with --write to apply.")
        return 0

    backup = write_settings(config)
    print("\nWrote autoMode to %s" % SETTINGS_PATH)
    if backup:
        print("Backup: %s" % backup)
    print("Verify: claude auto-mode config   |   Review: claude auto-mode critique")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
