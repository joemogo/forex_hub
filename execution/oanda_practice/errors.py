"""The failure vocabulary. Each class answers one question: WAS ANYTHING SENT?

A refusal before any write request is harmless and needs no reconciliation. A
failure after a write request may have reached the broker, so it is UNCERTAIN
and blocks every further submission until reconcile proves the outcome.
"""


class PracticeExecutionError(Exception):
    """Base class. Messages never carry credentials, headers or request URLs."""


class ConfigRefused(PracticeExecutionError):
    """The configuration cannot be trusted to address only the practice account."""


class AuthorizationRefused(PracticeExecutionError):
    """The operator authorization is missing, malformed, expired or already used."""


class OrderRefused(PracticeExecutionError):
    """Refused before any write request. `codes` lists every reason found."""

    def __init__(self, codes):
        self.codes = list(codes)
        super().__init__("order refused: " + ", ".join(self.codes))


class TransportRefused(PracticeExecutionError):
    """The transport refused to form the request. Nothing was sent."""


class NotSent(PracticeExecutionError):
    """The opener proves the request never left the process (e.g. network disabled)."""


class SendUncertain(PracticeExecutionError):
    """The request may have been sent and its outcome is unknown."""


class BrokerReadFailed(PracticeExecutionError):
    """A read request failed. Harmless before a write; blocks resolution after one."""
