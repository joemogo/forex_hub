"""MOGO-002.5 — Build the ALEX StrategySpecification from repository truth.

The specification is EXTRACTED FROM `RULES_ALEXG` in index.html, never
hand-copied. `RULES_ALEXG` is a PROTECTED CONSTANT (regression-baseline.json),
so it is the repository's own approved statement of what the Alex source
teaches, and re-deriving it on every run means the spec can never silently
drift from the artifact it claims to represent.

THE ARTIFACT ALREADY SEPARATES THE TWO EVIDENCE CLASSES
-------------------------------------------------------
  RULES_ALEXG.originalAlexConcepts     -> what the SOURCE states  == SPECIFICATION
  RULES_ALEXG.hubTestStandardizations  -> what MOGO CHOSE          == EXTRA IMPLEMENTATION
  RULES_ALEXG.config                   -> the parameters actually traded
  RULES_ALEXG.experimentalParams       -> explicitly untuned

That separation is the single most important thing in this milestone and it
already existed. This module does not invent it; it makes it machine-readable.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
-----------------------------------------
It does NOT pull rules from the Trader Intelligence library
(docs/trader-intelligence/, 195 ALEX_G claims). Per
`DECISION|MOGO|20260727|004`, MOGO's ALEX engine describes what MOGO BUILT, not
what the educator teaches, and `traders/alex-g/profile.json` states plainly that
ALEX's rules are "fully specified by MOGO's own implementation and
documentation, not derived from an external trader's research". Treating 195
`emerging` claims as this engine's specification would fabricate a lineage the
repository explicitly denies. Those claims are reported as a KNOWLEDGE GAP and a
completion path instead.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fidelity_model as fm  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
INDEX_HTML = os.path.join(REPO_ROOT, "index.html")

SPEC_EXTRACTOR_VERSION = "1.0.0"


class SpecExtractionError(RuntimeError):
    """Raised when the artifact cannot be located or parsed. Never degraded to a
    warning: an empty specification would make the implementation look 100%
    faithful, which is the exact failure mode this milestone exists to prevent."""


# --- JS literal extraction --------------------------------------------------

def _read_index(path=None):
    p = path or INDEX_HTML
    if not os.path.isfile(p):
        raise SpecExtractionError("index.html not found at %s" % p)
    with open(p, encoding="utf-8") as f:
        return f.read()


def _slice_rules_alexg(text):
    start = text.find("const RULES_ALEXG={")
    if start < 0:
        raise SpecExtractionError(
            "RULES_ALEXG not found in index.html -- the reconstructed ALEX strategy "
            "artifact could not be identified. This is a MOGO-002.5 stop condition.")
    # Brace-match from the opening '{' so nested objects are handled.
    i = text.index("{", start)
    depth, j, in_str, quote, esc = 0, i, False, "", False
    while j < len(text):
        ch = text[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
        else:
            if ch in "'\"":
                in_str, quote = True, ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[i:j + 1]
        j += 1
    raise SpecExtractionError("unterminated RULES_ALEXG object literal")


_STR_RE = re.compile(r"'((?:[^'\\]|\\.)*)'")


def _string_array(block, key):
    m = re.search(re.escape(key) + r"\s*:\s*\[", block)
    if not m:
        return []
    i = block.index("[", m.start())
    depth, j = 0, i
    while j < len(block):
        if block[j] == "[":
            depth += 1
        elif block[j] == "]":
            depth -= 1
            if depth == 0:
                break
        j += 1
    body = block[i:j + 1]
    out = []
    for s in _STR_RE.findall(body):
        out.append(s.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\"))
    return out


def _scalar(block, key):
    m = re.search(re.escape(key) + r"\s*:\s*'([^']*)'", block)
    return m.group(1) if m else None


def extract_rules_alexg(path=None):
    """Returns the raw, repository-truth view of RULES_ALEXG."""
    text = _read_index(path)
    block = _slice_rules_alexg(text)
    line_no = text[:text.find("const RULES_ALEXG={")].count("\n") + 1
    concepts = _string_array(block, "originalAlexConcepts")
    standardizations = _string_array(block, "hubTestStandardizations")
    if not concepts:
        raise SpecExtractionError(
            "RULES_ALEXG.originalAlexConcepts is empty -- refusing to emit an empty "
            "specification, which would report 100%% fidelity against nothing.")
    return {
        "ruleVersion": _scalar(block, "ruleVersion"),
        "sourceLocator": "index.html:%d" % line_no,
        "originalAlexConcepts": concepts,
        "hubTestStandardizations": standardizations,
        "configKeys": sorted(set(re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9_]*)\s*:",
                                            block, re.M))),
        "rawBlockHash": __import__("hashlib").sha256(block.encode("utf-8")).hexdigest(),
    }


# --- Classification of each extracted concept -------------------------------
#
# One entry per `originalAlexConcepts` element, matched by a stable substring so
# a reordering of the array cannot silently reassign a classification. Each entry
# records WHY it is classified that way, using the artifact's own wording.
#
# `required` means: the source states the strategy cannot proceed without it.
# `deterministic` means: it can be evaluated mechanically with no judgement.
#
# Where the artifact's own text hedges ("no formula given", "never stated as a
# requirement", "a single soft mention"), that hedge drives the classification.
# Nothing here is upgraded beyond what the artifact says.

CONCEPT_RULES = [
    ("Support is where buyers hold price up", dict(
        rule_id="ALEX_SR_001", title="Support and resistance definition",
        classification="EXPLICIT", category="MARKET_STRUCTURE",
        required=True, deterministic=False,
        notes="Definitional. Deterministic=False: the artifact defines the concept, "
              "not a computable test for it.")),
    ("collectively \"area of interest\"", dict(
        rule_id="ALEX_SR_002", title="Support/resistance are jointly the area of interest",
        classification="EXPLICIT", category="SETUP",
        required=True, deterministic=False,
        notes="Definitional mapping of the two terms onto one role-dependent concept.")),
    ("can never be traded against its current role", dict(
        rule_id="ALEX_SR_003", title="Never trade a zone against its current role",
        classification="EXPLICIT", category="NO_TRADE_CONDITIONS",
        required=True, deterministic=True,
        notes="A hard prohibition, stated absolutely ('never'), and mechanically checkable "
              "once a zone role exists.")),
    ("bidirectional", dict(
        rule_id="ALEX_SR_004", title="One zone, one shared touch tally from both sides",
        classification="EXPLICIT", category="MARKET_STRUCTURE",
        required=True, deterministic=True)),
    ("Three confirmed reactions validate a zone", dict(
        rule_id="ALEX_SR_005", title="Three reactions validate; the fourth is the first trade",
        classification="EXPLICIT", category="SETUP",
        required=True, deterministic=True,
        notes="The single most load-bearing quantified rule in the artifact.")),
    ("Three named strength tiers", dict(
        rule_id="ALEX_SR_006", title="Zone strength tiers: weak / valid / strong",
        classification="EXPLICIT", category="SETUP",
        required=False, deterministic=True)),
    ("More touches are always better", dict(
        rule_id="ALEX_SR_007", title="More touches are better, with no stated ceiling",
        classification="EXPLICIT", category="SETUP",
        required=False, deterministic=False,
        notes="Directional preference with no threshold; cannot gate a decision as stated.")),
    ("Zones must be tight", dict(
        rule_id="ALEX_SR_008", title="Zones are fitted tightly to where reactions clustered",
        classification="UNRESOLVED", category="SETUP",
        required=True, deterministic=False,
        notes="The artifact itself says 'demonstrated visually, no formula given'. Required "
              "for the method to work, but the source supplies no computable definition -- "
              "so it is UNRESOLVED, not EXPLICIT.")),
    ("Zones exist on H1, H4, Daily, and Weekly", dict(
        rule_id="ALEX_SR_009", title="Zone timeframes are exactly H1, H4, D, W",
        classification="EXPLICIT", category="TIMEFRAMES",
        required=True, deterministic=True,
        notes="The artifact stresses 'exactly these four, explicitly named'.")),
    ("Higher timeframe zones are more respected", dict(
        rule_id="ALEX_SR_010", title="Higher-timeframe zones outrank lower-timeframe zones",
        classification="EXPLICIT", category="TIMEFRAMES",
        required=False, deterministic=True)),
    ("Break and retest", dict(
        rule_id="ALEX_SR_011", title="Break and retest sequence with role flip",
        classification="EXPLICIT", category="SETUP",
        required=True, deterministic=True,
        notes="A four-step ordered sequence: failed rejection, confirmed break, retest from "
              "the new side, role flip.")),
    ("Psychological round-number levels", dict(
        rule_id="ALEX_SR_012", title="Psychological round numbers are optional confluence",
        classification="EXPLICIT", category="SETUP",
        required=False, deterministic=True,
        notes="The artifact states 'additional, non-mandatory'. Required=False is the "
              "artifact's own word, not a downgrade.")),
    ("A single soft mention that trend direction", dict(
        rule_id="ALEX_SR_013", title="Trend direction may improve odds (never a requirement)",
        classification="DISCRETIONARY", category="DIRECTIONAL_BIAS",
        required=False, deterministic=False,
        notes="The artifact's own framing: 'a single soft mention ... never stated as a "
              "requirement'. DISCRETIONARY, so its absence from a gate is NOT a fidelity "
              "failure -- see the NOT_APPLICABLE finding status.")),
]


def build_specification(path=None):
    raw = extract_rules_alexg(path)
    version = raw["ruleVersion"] or "unknown"
    rules, unmatched = [], []
    for concept in raw["originalAlexConcepts"]:
        spec_entry = None
        for needle, meta in CONCEPT_RULES:
            if needle in concept:
                spec_entry = meta
                break
        if spec_entry is None:
            unmatched.append(concept)
            continue
        rules.append(fm.strategy_rule(
            rule_id=spec_entry["rule_id"],
            version=version,
            title=spec_entry["title"],
            normalized_statement=concept,
            classification=spec_entry["classification"],
            category=spec_entry["category"],
            required=spec_entry["required"],
            deterministic=spec_entry["deterministic"],
            source_references=[fm.rule_source_reference(
                "repository_constant",
                "%s (RULES_ALEXG.originalAlexConcepts)" % raw["sourceLocator"],
                excerpt=concept,
                note="Protected constant; byte-identical to the committed baseline.")],
            confidence="MEDIUM",
            validation_status="SOURCE_VERIFIED",
            notes=spec_entry.get("notes")))

    if unmatched:
        # A new concept was added to the artifact that this module has never
        # classified. Failing loudly is correct: silently dropping it would
        # under-report the specification and inflate apparent fidelity.
        raise SpecExtractionError(
            "%d RULES_ALEXG.originalAlexConcepts entries have no classification in "
            "CONCEPT_RULES and would be silently dropped: %r"
            % (len(unmatched), unmatched))

    return fm.strategy_specification(
        strategy_id="alex_g_sr_v1",
        specification_version=version,
        title="ALEX — Alex G Support & Resistance (reconstructed source concepts)",
        rules=rules,
        provenance_note=(
            "Extracted from the PROTECTED constant RULES_ALEXG.originalAlexConcepts at %s. "
            "This is the repository's approved statement of what the Alex source teaches. "
            "It is NOT derived from the Trader Intelligence ALEX_G claim library -- see "
            "DECISION|MOGO|20260727|004 and docs/trader-intelligence/traders/alex-g/profile.json, "
            "which state that this engine's rules come from MOGO's own implementation and "
            "documentation rather than the educator's published material."
            % raw["sourceLocator"]),
        extracted_from={
            "artifact": "RULES_ALEXG",
            "locator": raw["sourceLocator"],
            "rawBlockSha256": raw["rawBlockHash"],
            "extractorVersion": SPEC_EXTRACTOR_VERSION,
            "conceptCount": len(raw["originalAlexConcepts"]),
            "hubStandardizationCount": len(raw["hubTestStandardizations"]),
        })


if __name__ == "__main__":
    spec = build_specification()
    print(fm.dumps(spec))
