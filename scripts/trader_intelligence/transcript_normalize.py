#!/usr/bin/env python3
"""MOGO Trader Intelligence -- named transcript normalization profiles.

Pure Python standard library. NO NETWORK ACCESS. NO LLM.

A normalization profile strips exactly one class of transport artifact from a
transcript -- player chrome, caption timing markup, speaker prefixes -- and
NEVER changes a spoken word. Every profile satisfies the same contract:

  REVERSIBILITY: for every transformed line, reassembling the recorded parts
  must reproduce the source line exactly. `normalize()` asserts this per line
  and raises rather than returning a lossy result.

  ACCOUNTABILITY: every source line is recorded in the line map, including
  lines no rule matched. Nothing is silently dropped.

Extracted from the validated first production intake (INTAKE|TJR|20260727|001),
where the `youtube_duration_label` profile removed 10,300 characters of
duplicated player labels across 396 of 397 lines with zero word changes.
"""
import hashlib
import re

PROFILES = ("youtube_duration_label", "youtube_timestamp_lines",
            "youtube_timestamp_lines_chaptered", "passthrough")


class NormalizationError(ValueError):
    """Raised when a profile cannot process a transcript losslessly."""


# ---------------------------------------------------------------------------
# youtube_duration_label
# ---------------------------------------------------------------------------
# A YouTube transcript copied out of the player duplicates each cue's duration
# label into the body text: the line "0:088 secondstrading." is the timestamp
# "0:08", then the literal label "8 seconds", then the spoken word "trading.".
# Ordered longest-first so "2 minutes, 3 seconds" is never mis-consumed as a
# bare "2 minutes".
_YT_LABEL = re.compile(
    r"^(?P<ts>\d{1,2}:\d{2})"
    r"(?P<label>\d{1,2} minutes?, \d{1,2} seconds?|\d{1,2} minutes?|\d{1,2} seconds?)"
    r"(?P<text>.*)$"
)


# A chapter heading in this paste format carries no duration label, so it falls
# through to the no-timestamp branch and would be spliced into the middle of a
# spoken sentence -- corrupting segment rawText and stamping the segment that
# starts on it with 0:00. Detection is deliberately LEXICAL ("Chapter <n>: ..."),
# matching the reasoning behind _UI_HEADER below: a structural rule here would
# also catch line 1, which is genuine content.
_CHAPTER_HEADING = re.compile(r"^\s*Chapter \d+:\s*\S")


def _normalize_youtube_duration_label(lines):
    out, current = [], "0:00"
    for i, line in enumerate(lines, start=1):
        m = _YT_LABEL.match(line)
        if m:
            ts, label, spoken = m.group("ts"), m.group("label"), m.group("text")
            current = ts
            transform = "stripped_duplicated_duration_label"
        elif _CHAPTER_HEADING.match(line):
            # Not spoken. Recorded as removed, never silently dropped, and the
            # entry carries the running timestamp so a section that begins here
            # is not stamped 0:00.
            out.append({
                "sourceLine": i,
                "sourceLineSha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                "timestamp": current,
                "removedDurationLabel": line.strip(),
                "transform": "chapter_heading",
                "normalizedText": "",
                "charsRemoved": len(line),
            })
            continue
        else:
            # Content before the first player cue (typically line 1 only).
            ts, label, spoken = "0:00", None, line
            transform = "no_timestamp_present__assigned_0:00_start"
        stripped = spoken.strip()
        out.append({
            "sourceLine": i,
            "sourceLineSha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
            "timestamp": ts,
            "removedDurationLabel": label,
            "transform": transform,
            "normalizedText": stripped,
            "charsRemoved": len(line) - len(stripped),
        })
    return out


def _verify_youtube_duration_label(lines, line_map):
    for line, entry in zip(lines, line_map):
        if entry["transform"] == "chapter_heading":
            if entry["removedDurationLabel"] != line.strip() or entry["normalizedText"] != "":
                raise NormalizationError(
                    "chapter heading %d is not losslessly recorded: %r"
                    % (entry["sourceLine"], line))
            continue
        if entry["removedDurationLabel"] is None:
            continue
        rebuilt = entry["timestamp"] + entry["removedDurationLabel"] + entry["normalizedText"]
        if rebuilt != line.strip():
            raise NormalizationError(
                "line %d is not losslessly reversible:\n  rebuilt: %r\n  source:  %r"
                % (entry["sourceLine"], rebuilt, line))


# ---------------------------------------------------------------------------
# youtube_timestamp_lines
# ---------------------------------------------------------------------------
# YouTube's "Show transcript" panel, copied with timestamps on their own lines:
#
#     What's good, boys? Welcome to day three...
#     0:05
#     beginner side of things. This is going to be...
#     0:12
#     we're going to be going over...
#
# A bare timestamp line marks the start of the text that FOLLOWS it. Text
# appearing before the first marker is spoken from 0:00.
#
# Marker lines carry no spoken content, so they normalize to the empty string
# and the marker itself is recorded as removed. Every source line still gets an
# entry, and each is exactly one of: the marker, or the retained text.
_TS_ONLY = re.compile(r"^\s*(\d{1,3}:\d{2}(?::\d{2})?)\s*$")


def _normalize_youtube_timestamp_lines(lines):
    out, current = [], "0:00"
    for i, line in enumerate(lines, start=1):
        m = _TS_ONLY.match(line)
        if m:
            current = m.group(1)
            out.append({
                "sourceLine": i,
                "sourceLineSha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                "timestamp": current,
                "removedDurationLabel": line.strip(),
                "transform": "timestamp_marker_line",
                "normalizedText": "",
                "charsRemoved": len(line),
            })
        else:
            stripped = line.strip()
            out.append({
                "sourceLine": i,
                "sourceLineSha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                "timestamp": current,
                "removedDurationLabel": None,
                "transform": "timestamp_from_preceding_marker",
                "normalizedText": stripped,
                "charsRemoved": len(line) - len(stripped),
            })
    return out


def _verify_youtube_timestamp_lines(lines, line_map):
    """Reversibility for this profile: every source line is EXACTLY one of the
    two recorded parts -- the removed marker, or the retained text."""
    for line, entry in zip(lines, line_map):
        if entry["transform"] == "timestamp_marker_line":
            if entry["removedDurationLabel"] != line.strip() or entry["normalizedText"] != "":
                raise NormalizationError(
                    "marker line %d is not losslessly recorded: %r" % (entry["sourceLine"], line))
        elif entry["normalizedText"] != line.strip():
            raise NormalizationError(
                "text line %d was altered: %r -> %r"
                % (entry["sourceLine"], line, entry["normalizedText"]))


# ---------------------------------------------------------------------------
# youtube_timestamp_lines_chaptered
# ---------------------------------------------------------------------------
# As above, but the paste also carries YouTube CHAPTER HEADINGS and leading UI
# chrome ("Search in video", the video title), plus sometimes a trailing URL:
#
#     Search in video                      <- leading chrome
#     Why 99% of Traders Fail in Forex     <- leading chrome / title
#     0:00
#     One of the main reasons why...
#     0:05
#     ...I need you to understand why top down analysis
#     Why Top-Down Analysis Is Non-Negotiable   <- CHAPTER HEADING
#     0:51
#     is a non-negotiable in trading...
#
# Detection is structural, not lexical: in this format a spoken line is always
# preceded by a timestamp marker, so a non-timestamp line whose PREDECESSOR is
# also a non-timestamp line and whose SUCCESSOR is a timestamp marker can only
# be a chapter heading. Leading lines before the first marker are chrome, and a
# trailing bare URL is chrome.
#
# Chapter headings are not spoken, so leaving them in would splice a title into
# the middle of a sentence and corrupt every excerpt that crossed it. They are
# recorded as removed, exactly like timestamps -- never silently dropped.
_URL_ONLY = re.compile(r"^\s*https?://\S+\s*$")


# Literal YouTube UI string that precedes the chapter list in a "Show
# transcript" copy. Leading lines are treated as chrome ONLY when this exact
# marker opens the file. Deliberately lexical: a purely structural rule
# ("anything before the first timestamp") would eat a genuine opening sentence,
# which it did on INTAKE|TJR|20260727|002 whose first line is real speech.
_UI_HEADER = "Search in video"


def _classify_chaptered(lines):
    n = len(lines)
    is_ts = [bool(_TS_ONLY.match(l)) for l in lines]
    first_ts = next((i for i, t in enumerate(is_ts) if t), n)
    has_ui_header = bool(lines) and lines[0].strip() == _UI_HEADER
    kinds = []
    for i, line in enumerate(lines):
        if is_ts[i]:
            kinds.append("timestamp")
        elif i < first_ts:
            kinds.append("leading_chrome" if has_ui_header else "text")
        elif _URL_ONLY.match(line):
            kinds.append("trailing_url")
        elif (i > 0 and not is_ts[i - 1] and i + 1 < n and is_ts[i + 1]):
            kinds.append("chapter_heading")
        else:
            kinds.append("text")
    return kinds


def _normalize_youtube_timestamp_lines_chaptered(lines):
    kinds, out, current = _classify_chaptered(lines), [], "0:00"
    for i, (line, kind) in enumerate(zip(lines, kinds), start=1):
        entry = {"sourceLine": i,
                 "sourceLineSha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                 "timestamp": current, "removedDurationLabel": None,
                 "transform": kind, "normalizedText": "", "charsRemoved": len(line)}
        if kind == "timestamp":
            current = _TS_ONLY.match(line).group(1)
            entry["timestamp"] = current
            entry["removedDurationLabel"] = line.strip()
        elif kind in ("chapter_heading", "leading_chrome", "trailing_url"):
            entry["removedDurationLabel"] = line.strip()
        else:
            stripped = line.strip()
            entry["normalizedText"] = stripped
            entry["charsRemoved"] = len(line) - len(stripped)
        out.append(entry)
    return out


def _verify_youtube_timestamp_lines_chaptered(lines, line_map):
    """Every source line is EXACTLY one of the two recorded parts -- the removed
    marker/heading/chrome, or the retained spoken text."""
    for line, entry in zip(lines, line_map):
        if entry["transform"] == "text":
            if entry["normalizedText"] != line.strip():
                raise NormalizationError("text line %d was altered: %r -> %r"
                                         % (entry["sourceLine"], line, entry["normalizedText"]))
        elif entry["removedDurationLabel"] != line.strip() or entry["normalizedText"] != "":
            raise NormalizationError("non-spoken line %d is not losslessly recorded: %r"
                                     % (entry["sourceLine"], line))


def removed_non_spoken(line_map):
    """Every line this profile classified as NOT spoken, for eyeball review.
    Structural detection is deterministic but format-dependent, so the operator
    must confirm it removed chrome and not content."""
    return [(e["sourceLine"], e["transform"], e["removedDurationLabel"]) for e in line_map
            if e["transform"] in ("chapter_heading", "leading_chrome", "trailing_url")]


# ---------------------------------------------------------------------------
# passthrough
# ---------------------------------------------------------------------------
# For transcripts that are already clean prose. Records every line unchanged so
# the provenance chain has the same shape regardless of profile.

def _normalize_passthrough(lines):
    return [{
        "sourceLine": i,
        "sourceLineSha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
        "timestamp": None,
        "removedDurationLabel": None,
        "transform": "passthrough",
        "normalizedText": line.strip(),
        "charsRemoved": len(line) - len(line.strip()),
    } for i, line in enumerate(lines, start=1)]


def _verify_passthrough(lines, line_map):
    for line, entry in zip(lines, line_map):
        if entry["normalizedText"] != line.strip():
            raise NormalizationError("passthrough altered line %d" % entry["sourceLine"])


_IMPL = {
    "youtube_duration_label": (_normalize_youtube_duration_label, _verify_youtube_duration_label),
    "youtube_timestamp_lines": (_normalize_youtube_timestamp_lines, _verify_youtube_timestamp_lines),
    "youtube_timestamp_lines_chaptered": (_normalize_youtube_timestamp_lines_chaptered,
                                          _verify_youtube_timestamp_lines_chaptered),
    "passthrough": (_normalize_passthrough, _verify_passthrough),
}


# ---------------------------------------------------------------------------
# Detection and entry point
# ---------------------------------------------------------------------------

def detect_profile(text):
    """Returns the profile whose pattern matches the most lines, or
    'passthrough'. Detection is a convenience for the operator -- always
    reported, never silent, and overridable with --normalize-profile."""
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines:
        return "passthrough"
    yt_hits = sum(1 for l in lines if _YT_LABEL.match(l))
    if yt_hits >= max(1, int(0.8 * len(lines))):
        return "youtube_duration_label"
    # Timestamp-marker transcripts alternate marker/text, so markers are close
    # to half the lines. A 25% floor detects them while staying clear of prose
    # that merely mentions a time.
    ts_hits = sum(1 for l in lines if _TS_ONLY.match(l))
    if ts_hits >= max(2, int(0.25 * len(lines))):
        # Chaptered variant if any chapter heading / leading chrome is present.
        # Only a genuine MID-transcript chapter heading selects the chaptered
        # profile. Leading chrome alone is not enough -- see _classify_chaptered.
        kinds = _classify_chaptered(text.split("\n"))
        if "chapter_heading" in kinds:
            return "youtube_timestamp_lines_chaptered"
        return "youtube_timestamp_lines"
    return "passthrough"


def normalize(text, profile=None):
    """Returns (profile_used, line_map). Raises NormalizationError if the
    profile cannot process the text losslessly -- callers must not catch and
    continue, because a lossy normalization silently corrupts every excerpt
    extracted downstream."""
    if "\x00" in text:
        raise NormalizationError("Transcript contains a null byte -- rejected as unsafe/malformed.")
    profile = profile or detect_profile(text)
    if profile not in _IMPL:
        raise NormalizationError("Unknown normalization profile %r (known: %r)" % (profile, PROFILES))
    lines = text.split("\n")
    fn, verify = _IMPL[profile]
    line_map = fn(lines)
    verify(lines, line_map)
    if len(line_map) != len(lines):
        raise NormalizationError("profile %r dropped lines (%d in, %d out)"
                                 % (profile, len(lines), len(line_map)))
    return profile, line_map


def unmatched_lines(line_map):
    """Source lines no substantive rule matched -- surfaced so an operator can
    confirm they are genuinely exceptions rather than a mis-chosen profile."""
    return [e["sourceLine"] for e in line_map
            if e["transform"].startswith("no_timestamp_present")]


def policy_summary(profile, line_map):
    return {
        "profile": profile,
        "wordsAdded": 0, "wordsRemoved": 0, "wordsReordered": 0,
        "charsRemoved": sum(e["charsRemoved"] for e in line_map),
        "linesTransformed": sum(1 for e in line_map if e["removedDurationLabel"] is not None),
        "lineCount": len(line_map),
        "unmatchedLines": unmatched_lines(line_map),
        "reversible": True,
        "reversibilityProof": "Reassembly of the recorded parts equals the source line; asserted "
                              "for every transformed line at generation time.",
    }
