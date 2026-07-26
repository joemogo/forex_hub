#!/usr/bin/env python3
"""PROGRAM-006 Phase 1B (ADR-009, Deliverable 7) -- transcript ingestion
adapters for locally-supplied transcript content.

Pure Python standard library. NO NETWORK ACCESS. NO video/audio downloading.
NO code evaluation of any kind (no eval/exec/pickle) -- every adapter here
only ever calls str methods, re, and json.loads on already-in-memory text
supplied by the caller. Adapters convert one of three accepted local formats
into a list of in-memory segment dicts (not yet persisted); persistence is a
separate step in intake_registry.py so a caller can inspect/adjust parsed
segments before they become authoritative TranscriptSegment records.
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc      # noqa: E402
import evidence_common as evc  # noqa: E402

_TIMESTAMP_LINE = re.compile(
    r"^\s*\[?(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\]?\s*(?:-\s*)?(?:(?P<speaker>[A-Za-z][A-Za-z0-9 _.'-]{0,40}):\s*)?(?P<text>.*\S.*)$"
)


def _reject_unsafe(text):
    if not isinstance(text, str):
        raise evc.EvidenceValidationError("Transcript content must be a string, got %r" % (type(text).__name__,))
    if "\x00" in text:
        raise evc.EvidenceValidationError("Transcript content contains a null byte -- rejected as unsafe/malformed.")
    return text


def transcript_content_hash(raw_text):
    return evc.text_sha256(_reject_unsafe(raw_text))


def parse_plain_text_transcript(raw_text, language=None):
    """Splits on blank-line-separated paragraphs. No timestamps, no speakers.
    Each paragraph becomes one segment, in order, with 1-indexed line ranges
    preserved. rawText is the exact paragraph text -- never altered."""
    raw_text = _reject_unsafe(raw_text)
    lines = raw_text.splitlines()
    segments = []
    seq = 0
    buffer_lines = []
    buffer_start = None
    for i, line in enumerate(lines, start=1):
        if line.strip() == "":
            if buffer_lines:
                seq += 1
                segments.append({
                    "sequenceNumber": seq, "speaker": None, "startTimestamp": None, "endTimestamp": None,
                    "lineStart": buffer_start, "lineEnd": i - 1, "sectionTitle": None,
                    "rawText": "\n".join(buffer_lines), "language": language,
                })
                buffer_lines = []
                buffer_start = None
            continue
        if buffer_start is None:
            buffer_start = i
        buffer_lines.append(line)
    if buffer_lines:
        seq += 1
        segments.append({
            "sequenceNumber": seq, "speaker": None, "startTimestamp": None, "endTimestamp": None,
            "lineStart": buffer_start, "lineEnd": len(lines), "sectionTitle": None,
            "rawText": "\n".join(buffer_lines), "language": language,
        })
    return segments


def parse_timestamped_text_transcript(raw_text, language=None):
    """Each line beginning with a recognized timestamp (optionally bracketed,
    optionally followed by 'Speaker:') starts a new segment; subsequent
    non-timestamped lines are appended as continuation text of that segment
    (a spoken line often wraps without repeating the timestamp)."""
    raw_text = _reject_unsafe(raw_text)
    lines = raw_text.splitlines()
    segments = []
    current = None
    seq = 0
    for i, line in enumerate(lines, start=1):
        if line.strip() == "":
            continue
        m = _TIMESTAMP_LINE.match(line)
        if m:
            if current:
                segments.append(current)
            seq += 1
            current = {
                "sequenceNumber": seq, "speaker": m.group("speaker"),
                "startTimestamp": m.group("ts"), "endTimestamp": None,
                "lineStart": i, "lineEnd": i, "sectionTitle": None,
                "rawText": m.group("text").strip(), "language": language,
            }
        elif current is not None:
            current["rawText"] = current["rawText"] + "\n" + line.strip()
            current["lineEnd"] = i
        else:
            raise evc.EvidenceValidationError(
                "Timestamped transcript must begin with a recognized timestamp line; line %d (%r) has none." % (i, line))
    if current:
        segments.append(current)
    if not segments:
        raise evc.EvidenceValidationError("No timestamped lines found -- content does not match transcriptFormat='timestamped_text'.")
    return segments


_REQUIRED_JSON_SEGMENT_FIELDS = ("text",)
_OPTIONAL_JSON_SEGMENT_STRING_FIELDS = ("speaker", "startTimestamp", "endTimestamp", "sectionTitle", "language")


def parse_structured_json_transcript(raw_text_or_obj, language=None):
    """Accepts either a JSON string or an already-parsed dict/list. Expected
    shape: {"segments": [{"text": "...", "speaker": "...", "startTimestamp":
    "...", "endTimestamp": "...", "sectionTitle": "...", "lineStart": int,
    "lineEnd": int}, ...], "language": "..."}. json.loads only -- never
    eval/exec; malformed shapes are rejected with a clear error, not guessed."""
    if isinstance(raw_text_or_obj, (dict, list)):
        obj = raw_text_or_obj
    else:
        raw_text_or_obj = _reject_unsafe(raw_text_or_obj)
        try:
            obj = json.loads(raw_text_or_obj)
        except (json.JSONDecodeError, ValueError) as exc:
            raise evc.EvidenceValidationError("Structured JSON transcript is not valid JSON: %s" % (exc,))

    if isinstance(obj, list):
        raw_segments = obj
        doc_language = language
    elif isinstance(obj, dict):
        raw_segments = obj.get("segments")
        doc_language = obj.get("language", language)
        if not isinstance(raw_segments, list):
            raise evc.EvidenceValidationError("Structured JSON transcript must have a top-level 'segments' array.")
    else:
        raise evc.EvidenceValidationError("Structured JSON transcript must be a JSON object or array, got %r." % (type(obj).__name__,))

    segments = []
    for idx, raw in enumerate(raw_segments):
        if not isinstance(raw, dict):
            raise evc.EvidenceValidationError("Structured JSON transcript segment #%d is not an object." % (idx,))
        for field in _REQUIRED_JSON_SEGMENT_FIELDS:
            if not isinstance(raw.get(field), str) or not raw.get(field).strip():
                raise evc.EvidenceValidationError("Structured JSON transcript segment #%d is missing required string field %r." % (idx, field))
        for field in _OPTIONAL_JSON_SEGMENT_STRING_FIELDS:
            if field in raw and raw[field] is not None and not isinstance(raw[field], str):
                raise evc.EvidenceValidationError("Structured JSON transcript segment #%d field %r must be a string or null." % (idx, field))
        for field in ("lineStart", "lineEnd"):
            if field in raw and raw[field] is not None and not isinstance(raw[field], int):
                raise evc.EvidenceValidationError("Structured JSON transcript segment #%d field %r must be an integer or null." % (idx, field))
        segments.append({
            "sequenceNumber": idx + 1,
            "speaker": raw.get("speaker"),
            "startTimestamp": raw.get("startTimestamp"),
            "endTimestamp": raw.get("endTimestamp"),
            "lineStart": raw.get("lineStart"),
            "lineEnd": raw.get("lineEnd"),
            "sectionTitle": raw.get("sectionTitle"),
            "rawText": raw["text"],
            "language": raw.get("language", doc_language),
        })
    if not segments:
        raise evc.EvidenceValidationError("Structured JSON transcript contains zero segments.")
    return segments


_ADAPTERS = {
    "plain_text": parse_plain_text_transcript,
    "timestamped_text": parse_timestamped_text_transcript,
    "structured_json": parse_structured_json_transcript,
}


def parse_transcript(raw_content, transcript_format, language=None):
    """Single dispatch point so callers (and a future controlled extraction
    pipeline) never need to know which adapter handles which format."""
    if transcript_format not in evc.TRANSCRIPT_FORMATS:
        raise evc.EvidenceValidationError("Unknown transcriptFormat %r (expected one of %r)." % (
            transcript_format, evc.TRANSCRIPT_FORMATS))
    return _ADAPTERS[transcript_format](raw_content, language=language)
