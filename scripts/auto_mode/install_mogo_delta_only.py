#!/usr/bin/env python3
"""Install ONLY named MOGO rule changes into the installed autoMode block; touch nothing else.

WHY THIS EXISTS. build_auto_mode_config.py --write regenerates the whole block from
the shipped defaults of the installed CLI. When the installed block has drifted from
those defaults, that also rewrites rules MOGO never reviewed. On 2026-11-04 it would
have loosened Git Destructive, added PR-work allowances to External System Writes,
and dropped the Scheduled-Task Fires allow entry, all to install one MOGO rule. This
tool installs a reviewed MOGO change and nothing else:

  * only MOGO-labelled entries ("MOGO ..." / "**MOGO ...**") can change;
  * the set of labels that change must EQUAL --expect, or nothing is written;
  * every non-MOGO entry, the order of every section and every other key in the
    settings file are asserted byte-identical before and after;
  * a new entry is inserted directly after the MOGO entry that precedes it in
    mogo_rules.json;
  * it never calls the claude CLI and never reads the shipped defaults.

Dry run by default. --write takes the generator's timestamped backup, writes, then
re-reads the file and verifies the result. Run it yourself: writing the user
settings file is a Self-Modification boundary, and the operator owns it.

    python3 scripts/auto_mode/install_mogo_delta_only.py                 # show, write nothing
    python3 scripts/auto_mode/install_mogo_delta_only.py --write
    python3 scripts/auto_mode/install_mogo_delta_only.py --settings COPY --write   # rehearse on a copy
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_auto_mode_config as gen   # noqa: E402  (label_of, mogo_delta, load/write_settings only)

#: The reviewed change (commit a2e63c0d7). Anything else changing refuses the install.
DEFAULT_EXPECT = ("environment|**MOGO trading posture**", "soft_deny|MOGO Broker-Practice Execution")


def is_mogo(label):
    return label.startswith("MOGO ") or label.startswith("**MOGO ")


def plan(installed_block, delta):
    """The new block, plus the list of (section, label, action) it changes."""
    new_block = {k: list(v) for k, v in installed_block.items()}
    changes = []
    for section, rules in delta.items():
        current = new_block.setdefault(section, [])
        labels = [gen.label_of(r) for r in current]
        previous_mogo = None
        for rule in rules:
            label = gen.label_of(rule)
            if not is_mogo(label):
                raise SystemExit("refusing: mogo_rules.json carries a non-MOGO label %r" % label)
            if label in labels:
                i = labels.index(label)
                if current[i] != rule:
                    current[i] = rule
                    changes.append((section, label, "replace"))
            else:
                at = labels.index(previous_mogo) + 1 if previous_mogo in labels else len(current)
                current.insert(at, rule)
                labels.insert(at, label)
                changes.append((section, label, "insert"))
            previous_mogo = label
    return new_block, changes


def non_mogo_view(block):
    return {s: [r for r in rules if not is_mogo(gen.label_of(r))] for s, rules in block.items()}


def verify(before_settings, after_settings, expected_block):
    problems = []
    rest_before = {k: v for k, v in before_settings.items() if k != "autoMode"}
    rest_after = {k: v for k, v in after_settings.items() if k != "autoMode"}
    if rest_before != rest_after:
        problems.append("a setting other than autoMode changed")
    if non_mogo_view(before_settings.get("autoMode", {})) != non_mogo_view(after_settings.get("autoMode", {})):
        problems.append("a non-MOGO rule changed")
    if after_settings.get("autoMode") != expected_block:
        problems.append("the installed block is not the planned block")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--settings", default=gen.SETTINGS_PATH)
    parser.add_argument("--expect", action="append", default=None,
                        help="section|label expected to change (repeatable); default: the reviewed change")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    expect = set(args.expect or DEFAULT_EXPECT)

    before = gen.load_settings(args.settings)
    installed = before.get("autoMode")
    if not isinstance(installed, dict):
        print("refusing: %s has no autoMode block to update" % args.settings)
        return 2
    new_block, changes = plan(installed, gen.mogo_delta())
    changed = {"%s|%s" % (s, l) for s, l, _a in changes}
    for s, l, a in changes:
        print("%-8s %-12s %s" % (a, s, l))
    if not changes:
        print("installed MOGO rules already match mogo_rules.json; nothing to do")
        return 0
    if changed != expect:
        print("refusing: the changes %s are not exactly the expected %s" % (sorted(changed), sorted(expect)))
        return 1
    if non_mogo_view(installed) != non_mogo_view(new_block):
        print("refusing: the plan would alter a non-MOGO rule")
        return 1
    if not args.write:
        print("dry run: nothing written. Every non-MOGO rule and every other setting would be unchanged.")
        return 0
    backup = gen.write_settings(new_block, args.settings)
    problems = verify(before, gen.load_settings(args.settings), new_block)
    print("backup: %s" % backup)
    if problems:
        print("VERIFY FAILED: %s -- restore from the backup above" % "; ".join(problems))
        return 1
    print("INSTALLED and verified: only the expected MOGO rules changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
