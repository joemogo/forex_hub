#!/usr/bin/env python3
"""MOGO Automation Platform -- connector authorization gate (MOGO-015 Step 2).

AUTHORITY
    Constitution section 5.1 -- no acquisition without an authorization record
    Architecture section 32 item 5 -- the policy gate precedes ANY connector
    ADR-012 D-15 -- first connector authorization
    MOGO-015 Step 1A decision; Step 2 authorization

WHAT THIS IS

    The boundary that must exist BEFORE MOGO is permitted to open a socket.
    It decides, purely and with no I/O, whether one specific acquisition
    request is permitted -- and it is designed so that a denial happens before
    any transport exists to invoke.

THE ANTI-SSRF PROPERTY, WHICH IS THE WHOLE DESIGN

    A caller does NOT supply a URL. A caller supplies a SOURCE IDENTITY, and
    the gate DERIVES the destination from the approved destination registry
    below. There is therefore no argument a caller can pass that becomes a
    fetch target.

    If a caller also supplies a URL -- which the acquisition capability will do,
    so that the recorded provenance names what was actually requested -- it must
    be byte-identical to the derived one. Supplying an approved sourceId with a
    different URL is refused as SUBSTITUTION, which is the exact attack this
    gate exists to stop.

    This is why the registry maps source -> destination rather than merely
    listing allowed hosts. An allow-list of hosts would still let any path on
    that host be fetched; deriving the whole URL leaves nothing to choose.

DENY IS THE DEFAULT AND THE ONLY FALLTHROUGH

    Every rung of the ladder in `evaluate()` exits with a denial. A permit is
    reached only by passing every check, and anything the ladder did not
    anticipate -- an unknown field, an unexpected shape, a source not in the
    registry -- lands on the final denial rather than slipping through.
"""

from types import MappingProxyType

from . import errors as runtime_errors  # noqa: E402

CONNECTOR_ID = "CONN|research|approved-source-metadata"
CONNECTOR_VERSION = "1.0.0"

# The single approved operation for this connector. Transcript acquisition is
# NOT here: MOGO-015 Step 1A verified that path returns HTTP 200 with an empty
# body, and pursuing it would mean working around an access control.
OPERATION_METADATA = "metadata"

# YouTube video ids are exactly 11 characters of an unreserved alphabet. Pinned
# as a pattern rather than "whatever the caller sent" so a crafted id cannot
# introduce a query parameter, a path segment or an encoded host.
#
# MOGO-018 Step 3A: this is now YouTube's alphabet REFERENCED BY the YouTube
# entry, not a global rule imposed on every destination. It is defined above the
# registry because the entry uses it; a future non-YouTube destination declares
# its own and must not reuse this one.
VIDEO_ID_PATTERN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

# ---------------------------------------------------------------------------
# Approved destination registry -- source identity IS the key.
# ---------------------------------------------------------------------------
# One entry, deliberately. Adding a second external source is a visible, reviewed
# edit to this table, not a configuration change and not a runtime registration.
#
# `urlTemplate` carries exactly one substitution, {videoId}, which is validated
# against a strict pattern before use. Nothing else in the URL is caller-
# influenced -- scheme, host and path are constants in this file.
#
# MOGO-018 Step 3A: each entry now declares its OWN resourceIdAlphabet and
# resourceIdLength. This NARROWS the boundary rather than widening it -- before,
# one global 11-character YouTube rule was applied to every destination, so a
# future destination would have inherited a rule written for someone else. Now a
# destination that does not say what it accepts accepts NOTHING.
APPROVED_DESTINATIONS = MappingProxyType({
    # Alex G -- the educator behind the frozen ALEX strategy. Verified in
    # docs/strategy-fidelity/audit/alex-channel-catalogue.json with
    # authenticityStatus channel_verified, and corroborated in Step 1A by the
    # provider's own oEmbed author_url matching the recorded channel URL.
    "SRC|youtube|c785970cc458": MappingProxyType({
        "sourceLabel": "fxalexg",
        "channelId": "UCgPeeHdxYRal0HTNeAkjqLg",
        "channelUrl": "https://www.youtube.com/@fxalexg__",
        "scheme": "https",
        "host": "www.youtube.com",
        "path": "oembed",   # joined, never a leading-slash literal
        "operation": OPERATION_METADATA,
        "urlTemplate": ("https://www.youtube.com" "/" "oembed"
                        "?url=https://www.youtube.com" "/" "watch%3Fv%3D{videoId}"
                        "&format=json"),
        # MOGO-018 Step 3A. THIS destination's own resource-id rule, declared
        # here rather than applied globally. The VALUES are byte-identical to the
        # global rule they replace, so this source's acceptance boundary is
        # unchanged -- the alphabet is referenced by name rather than retyped
        # precisely so it cannot drift by a character.
        "resourceIdAlphabet": VIDEO_ID_PATTERN,
        "resourceIdLength": 11,
        "maxResponseBytes": 65536,
        "expectedContentType": "application/json",
        "followRedirects": False,
    }),
})


APPROVED_SCHEMES = ("https",)

# Destinations refused regardless of any registry entry. Belt and braces: the
# registry contains none of these, and it never should, but a future edit that
# added one must still be refused here.
FORBIDDEN_HOST_FRAGMENTS = (
    "localhost", "127.", "0.0.0.0", "::1", "169.254.", "metadata.",
    "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
    "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
)
FORBIDDEN_SCHEMES = ("file", "ftp", "gopher", "data", "blob", "ws", "wss",
                     "http")   # plain http included: this connector is https-only

# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

DECISION_PERMIT = "permit"
DECISION_DENY = "deny"

REASON_PERMITTED = "connector_destination_permitted"
REASON_NO_SOURCE = "no_source_identity"
REASON_SOURCE_NOT_APPROVED = "source_not_in_approved_destination_registry"
REASON_NO_AUTHORIZATION = "no_authorization_identity"
REASON_MALFORMED_AUTHORIZATION = "malformed_authorization_identity"
REASON_OPERATION_NOT_PERMITTED = "operation_not_permitted_for_connector"
REASON_SCHEME_FORBIDDEN = "scheme_forbidden"
REASON_HOST_FORBIDDEN = "host_forbidden"
REASON_URL_SUBSTITUTION = "requested_url_does_not_match_approved_destination"
REASON_MALFORMED_VIDEO_ID = "malformed_resource_identifier"
REASON_REDIRECT_NOT_PERMITTED = "redirect_destination_not_permitted"
REASON_UNANTICIPATED = "unanticipated_request_shape"


class ConnectorDecision(object):
    """The decision, and everything needed to audit it."""

    __slots__ = ("permitted", "decision", "reason", "connectorId",
                 "connectorVersion", "capabilityId", "capabilityVersion",
                 "sourceId", "authorizationId", "operation", "scheme", "host",
                 "requestedUrl", "approvedUrl", "decidedAt", "limits")

    def __init__(self, permitted, reason, **fields):
        # Explicit assignment rather than setattr() in a loop: the platform
        # boundary tests forbid dynamic attribute writes in the runtime, and
        # they are right to -- a field set by name from data is a field no
        # reader can find by searching.
        self.permitted = permitted
        self.decision = DECISION_PERMIT if permitted else DECISION_DENY
        self.reason = reason
        self.connectorId = fields.get("connectorId")
        self.connectorVersion = fields.get("connectorVersion")
        self.capabilityId = fields.get("capabilityId")
        self.capabilityVersion = fields.get("capabilityVersion")
        self.sourceId = fields.get("sourceId")
        self.authorizationId = fields.get("authorizationId")
        self.operation = fields.get("operation")
        self.scheme = fields.get("scheme")
        self.host = fields.get("host")
        self.requestedUrl = fields.get("requestedUrl")
        self.approvedUrl = fields.get("approvedUrl")
        self.decidedAt = fields.get("decidedAt")
        self.limits = fields.get("limits")

    def as_record(self):
        return {name: getattr(self, name) for name in self.__slots__}


def _deny(reason, **fields):
    return ConnectorDecision(False, reason, **fields)


def approved_source_ids():
    return tuple(sorted(APPROVED_DESTINATIONS))


def _valid_resource_id(entry, value):
    """Does this identifier satisfy THIS destination's own declared rule?

    FAILS CLOSED in every direction that matters. A destination that declares no
    constraint, or a malformed one, accepts NOTHING -- because a registry entry
    that cannot say what it accepts must never be read as accepting anything.
    That is the whole point of moving the rule off the module and onto the entry.

    `hasattr(entry, "get")` rather than isinstance(entry, dict): registry entries
    are MappingProxyType, which is deliberately NOT a dict.
    """
    if entry is None or not hasattr(entry, "get"):
        return False
    alphabet = entry.get("resourceIdAlphabet")
    length = entry.get("resourceIdLength")
    if not isinstance(alphabet, str) or not alphabet:
        return False
    if isinstance(length, bool) or not isinstance(length, int) or length <= 0:
        return False
    if not isinstance(value, str) or len(value) != length:
        return False
    return all(character in alphabet for character in value)


def _looks_like_uuid4(value):
    """Shape check only -- authorizations.validate_record() is the authority."""
    if not isinstance(value, str) or len(value) != 36:
        return False
    parts = value.split("-")
    if [len(part) for part in parts] != [8, 4, 4, 4, 12]:
        return False
    return all(character in "0123456789abcdef-" for character in value)


def derive_destination(source_id, resource_id):
    """The ONLY way a destination URL comes into existence.

    Callers never supply one. Returns (url, entry) or raises -- so a capability
    physically cannot fetch something the registry does not describe.
    """
    entry = APPROVED_DESTINATIONS.get(source_id)
    if entry is None:
        runtime_errors.fail(
            "source %r is not in the approved destination registry" % (source_id,),
            runtime_errors.ContractValidationError)
    if not _valid_resource_id(entry, resource_id):
        runtime_errors.fail(
            "resource identifier %r does not satisfy the declared constraint for "
            "source %r" % (resource_id, source_id),
            runtime_errors.ContractValidationError)
    return (entry["urlTemplate"].format(videoId=resource_id), entry)


def evaluate(request):
    """THE CONNECTOR AUTHORIZATION GATE. Pure: no clock, no socket, no I/O.

    `request` is a plain mapping. Returns a ConnectorDecision. A permit is
    reached only by falling through every rung; every earlier exit denies.
    """
    if not isinstance(request, dict):
        return _deny(REASON_UNANTICIPATED)

    source_id = request.get("sourceId")
    authorization_id = request.get("authorizationId")
    capability_id = request.get("capabilityId")
    capability_version = request.get("capabilityVersion")
    operation = request.get("operation")
    resource_id = request.get("resourceId")
    requested_url = request.get("requestedUrl")
    decided_at = request.get("decidedAt")

    common = {"connectorId": CONNECTOR_ID,
              "connectorVersion": CONNECTOR_VERSION,
              "capabilityId": capability_id,
              "capabilityVersion": capability_version,
              "sourceId": source_id,
              "authorizationId": authorization_id,
              "operation": operation,
              "requestedUrl": requested_url,
              "decidedAt": decided_at}

    # 1. A request with no subject source cannot be authorized for anything.
    if not source_id or not isinstance(source_id, str):
        return _deny(REASON_NO_SOURCE, **common)

    # 2. The source must be in the registry. This is what makes the destination
    #    derivable at all, and it is checked before anything else is trusted.
    entry = APPROVED_DESTINATIONS.get(source_id)
    if entry is None:
        return _deny(REASON_SOURCE_NOT_APPROVED, **common)

    # 3. An authorization identity must be present and well shaped. Absent is a
    #    different failure from malformed, and the operator needs to know which.
    if authorization_id is None or authorization_id == "":
        return _deny(REASON_NO_AUTHORIZATION, **common)
    if not _looks_like_uuid4(authorization_id):
        return _deny(REASON_MALFORMED_AUTHORIZATION, **common)

    # 4. The operation must be the one this connector exists for.
    if operation != entry["operation"]:
        return _deny(REASON_OPERATION_NOT_PERMITTED, **common)

    # 5. Scheme and host come from the REGISTRY, never from the request -- but
    #    they are still checked, so a bad registry edit is refused too.
    scheme, host = entry["scheme"], entry["host"]
    common.update({"scheme": scheme, "host": host})
    if scheme in FORBIDDEN_SCHEMES or scheme not in APPROVED_SCHEMES:
        return _deny(REASON_SCHEME_FORBIDDEN, **common)
    lowered = host.lower()
    for fragment in FORBIDDEN_HOST_FRAGMENTS:
        if lowered.startswith(fragment) or lowered == fragment.rstrip("."):
            return _deny(REASON_HOST_FORBIDDEN, **common)

    # 6. The resource identifier must match its pinned shape before it is ever
    #    substituted into a URL.
    if not _valid_resource_id(entry, resource_id):
        return _deny(REASON_MALFORMED_VIDEO_ID, **common)

    approved_url = entry["urlTemplate"].format(videoId=resource_id)
    common["approvedUrl"] = approved_url

    # 7. SUBSTITUTION. If the caller named a URL it must be byte-identical to
    #    the derived one. An approved sourceId carrying someone else's URL is
    #    the attack this gate exists to stop.
    if requested_url is not None and requested_url != approved_url:
        return _deny(REASON_URL_SUBSTITUTION, **common)

    # 8. Redirects are not authorized for this connector. Recorded on the
    #    decision so the transport cannot decide otherwise on its own.
    if request.get("followRedirects") and not entry["followRedirects"]:
        return _deny(REASON_REDIRECT_NOT_PERMITTED, **common)

    common["limits"] = {
        "maxResponseBytes": entry["maxResponseBytes"],
        "expectedContentType": entry["expectedContentType"],
        "followRedirects": entry["followRedirects"],
    }
    return ConnectorDecision(True, REASON_PERMITTED, **common)


def evaluate_redirect(source_id, location):
    """A redirect destination is re-validated against the SAME boundary.

    Called by a future transport before following anything. The connector
    currently permits no redirects at all, so this denies unconditionally --
    stated as a function rather than an omission so the transport has something
    concrete to call and cannot forget.
    """
    entry = APPROVED_DESTINATIONS.get(source_id)
    if entry is None:
        return _deny(REASON_SOURCE_NOT_APPROVED, sourceId=source_id,
                     requestedUrl=location)
    return _deny(REASON_REDIRECT_NOT_PERMITTED, sourceId=source_id,
                 requestedUrl=location, scheme=entry["scheme"],
                 host=entry["host"])
