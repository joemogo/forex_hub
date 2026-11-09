"""The kill switch: a file. Its presence blocks every write request.

A file rather than a flag in memory or in the journal, so it can be engaged by
the operator from any shell (`touch`), survives restarts, and is checked by
the executor before any work AND by the transport immediately before a write
leaves the process. Releasing it is a deliberate, separate act.
"""
import datetime
import os


class KillSwitch(object):
    FILENAME = "KILL"

    def __init__(self, state_dir):
        self.path = os.path.join(state_dir, self.FILENAME)

    def engaged(self):
        # Fail closed: if the state directory cannot be inspected, treat as engaged.
        try:
            return os.path.lexists(self.path) or not os.path.isdir(os.path.dirname(self.path))
        except OSError:
            return True

    def engage(self, reason="operator"):
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write("%s %s\n" % (datetime.datetime.now(datetime.timezone.utc).isoformat(), reason))
            handle.flush()
            os.fsync(handle.fileno())

    def release(self, confirm=False):
        if confirm is not True:
            raise ValueError("releasing the kill switch requires confirm=True")
        if os.path.lexists(self.path):
            os.remove(self.path)
