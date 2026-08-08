#!/usr/bin/env python3
"""MOGO-011 Step 2 -- lease acquisition, expiry, reclaim and holder authority.

Pure stdlib (unittest). Fully offline, deterministic, repeatable. Tempfile
state root. Nothing sleeps: expiry is reached by advancing an injected clock.

THE CASE THIS SUITE EXISTS TO PROVE
    Step 1 reclaimed every task in claimed/running unconditionally, justified
    by "single-writer, so the previous holder is gone". That is true, and it is
    an ASSUMPTION -- and Constitution section 11 requires recovery to resume
    from a verified checkpoint, "never from an assumed one".

    The test that matters most here is therefore
    test_a_live_lease_is_not_reclaimed_prematurely: the case Step 1 could not
    express at all, and the one that makes the lease a verification rather than
    a rubber stamp.

Run with:
    python3 -m unittest tests.platform.test_runtime_lease -v
"""

import ast
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "platform", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mogo_platform.contracts import ids  # noqa: E402
from mogo_platform.runtime import clock as clock_module  # noqa: E402
from mogo_platform.runtime import cli as cli_module  # noqa: E402
from mogo_platform.runtime import errors as runtime_errors  # noqa: E402
from mogo_platform.runtime import lease  # noqa: E402
from mogo_platform.runtime import orchestrator as orchestrator_module  # noqa: E402
from mogo_platform.runtime import paths as paths_module  # noqa: E402
from mogo_platform.runtime import projection  # noqa: E402

OURS = "runner:11111111-1111-4111-8111-111111111111"
THEIRS = "runner:22222222-2222-4222-8222-222222222222"


class TestReclaimPredicate(unittest.TestCase):
    """Four quadrants, no database, no process."""

    def test_a_lease_from_a_previous_run_is_reclaimed(self):
        self.assertEqual(lease.reclaim_reason(THEIRS, 10_000, 1, OURS),
                         "owner_gone")

    def test_an_expired_lease_is_reclaimed(self):
        self.assertEqual(lease.reclaim_reason(OURS, 1_000, 1_000, OURS),
                         "lease_expired")
        self.assertEqual(lease.reclaim_reason(OURS, 1_000, 1_001, OURS),
                         "lease_expired")

    def test_a_live_lease_is_not_reclaimed_prematurely(self):
        """The case Step 1 could not express."""
        self.assertIsNone(lease.reclaim_reason(OURS, 1_000, 999, OURS))
        self.assertIsNone(lease.reclaim_reason(OURS, 1_000, 0, OURS))

    def test_a_claimed_task_with_no_lease_is_reclaimed(self):
        """The v1 -> v2 upgrade path is a first-class case, not an afterthought."""
        self.assertEqual(lease.reclaim_reason(None, None, 1, OURS), "no_lease")

    def test_every_reclaim_reason_is_declared(self):
        produced = {
            lease.reclaim_reason(THEIRS, 10_000, 1, OURS),
            lease.reclaim_reason(OURS, 1_000, 2_000, OURS),
            lease.reclaim_reason(None, None, 1, OURS),
        }
        self.assertEqual(produced, set(lease.RECLAIM_REASONS))

    def test_owner_identity_precedes_expiry(self):
        """A lease held by an absent owner is reclaimed as `owner_gone` even
        when it has also expired -- the more specific fact is recorded."""
        self.assertEqual(lease.reclaim_reason(THEIRS, 1_000, 9_999, OURS),
                         "owner_gone")


class TestLeaseArithmetic(unittest.TestCase):
    def test_expiry_is_inclusive_at_the_boundary(self):
        self.assertFalse(lease.is_expired(1_000, 999))
        self.assertTrue(lease.is_expired(1_000, 1_000))
        self.assertTrue(lease.is_expired(1_000, 1_001))

    def test_an_absent_expiry_is_treated_as_expired(self):
        self.assertTrue(lease.is_expired(None, 0))

    def test_ttl_is_twice_the_declared_wall_clock_with_a_floor(self):
        self.assertEqual(lease.lease_ttl_ms(5_000), 30_000)     # floor wins
        self.assertEqual(lease.lease_ttl_ms(20_000), 40_000)    # 2x wins
        self.assertEqual(lease.lease_ttl_ms(None), 30_000)
        self.assertEqual(lease.LEASE_TTL_FLOOR_MS, 30_000)

    def test_the_ttl_always_exceeds_the_execution_it_protects(self):
        """A lease cannot expire mid-execution under any normal condition,
        because it is at least twice the bound the execution runs under."""
        for wall_clock in (1, 100, 5_000, 15_000, 60_000):
            with self.subTest(wallClockMs=wall_clock):
                self.assertGreaterEqual(lease.lease_ttl_ms(wall_clock),
                                        2 * wall_clock)

    def test_holder_identity_is_the_run_not_the_process(self):
        run_id = ids.new_uuid4()
        holder = lease.holder_for_run(run_id)
        self.assertEqual(holder, "runner:" + run_id)
        self.assertNotIn(str(os.getpid()), holder)
        for bad in ("", "   ", None, 17):
            with self.subTest(run_id=bad):
                with self.assertRaises(runtime_errors.ContractValidationError):
                    lease.holder_for_run(bad)

    def test_is_held_by_requires_both_holder_and_generation(self):
        self.assertTrue(lease.is_held_by(OURS, 3, OURS, 3))
        self.assertFalse(lease.is_held_by(OURS, 4, OURS, 3))   # bumped mid-flight
        self.assertFalse(lease.is_held_by(THEIRS, 3, OURS, 3))
        self.assertFalse(lease.is_held_by(None, 3, OURS, 3))

    def test_the_lease_module_reads_no_clock(self):
        with open(os.path.join(SRC_DIR, "mogo_platform", "runtime", "lease.py"),
                  "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = ([a.name for a in node.names]
                         if isinstance(node, ast.Import) else [node.module or ""])
                for name in names:
                    self.assertNotIn(name.split(".")[0],
                                     ("time", "datetime", "random", "secrets"))


class LeaseRuntimeCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.paths = paths_module.RuntimePaths(os.path.join(self._tmp.name, "state"))
        self.clock = clock_module.ManualClock("2026-08-08T12:00:00.000Z")
        self.runtime = self._open()

    def _open(self):
        runtime = orchestrator_module.Orchestrator(
            paths=self.paths, clock=self.clock, create=True).open()
        runtime.register_builtin_capabilities()
        return runtime

    def tearDown(self):
        try:
            self.runtime.close()
        except Exception:  # noqa: BLE001 - a closed runtime is fine in teardown
            pass
        self._tmp.cleanup()

    def reopen(self):
        """Close and reopen -- a NEW run, with a new runId and lease holder."""
        self.runtime.close()
        self.runtime = self._open()
        return self.runtime

    def submit(self, fail_until=0, note="lease"):
        envelope, payload = cli_module.build_retry_demo_command(fail_until, note)
        return self.runtime.submit(envelope, payload)

    def task(self, task_id):
        return self.runtime.connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()

    def strand_in_claimed(self, task_id):
        """Drive the task to `queued`, then claim it and stop.

        Uses the real claim path, so the lease under test is a genuine one.
        """
        self.runtime.run_once()
        return self.task(task_id)


class TestLeaseAcquisition(LeaseRuntimeCase):
    def test_lease_acquisition_is_atomic_with_the_claim(self):
        outcome = self.submit(fail_until=0)
        self.runtime.run_once()
        claims = [record for record in self.runtime.log.scan(verify=True).records
                  if record.event.get("taskId") == outcome.task_id
                  and record.event["eventType"] == "TaskClaimed"]
        self.assertEqual(len(claims), 1)
        payload = claims[0].event["payload"]
        for field in ("leaseHolder", "leaseGeneration", "leaseAcquiredAt",
                      "leaseExpiresAt", "leaseTtlMs", "claimMode", "attempt"):
            self.assertIn(field, payload)
        self.assertEqual(payload["claimMode"], "compare_and_set_lease")
        self.assertEqual(payload["leaseGeneration"], 1)
        self.assertEqual(payload["leaseHolder"], self.runtime.lease_holder)

    def test_the_lease_expiry_is_derivable_from_the_payload_alone(self):
        outcome = self.submit(fail_until=0)
        self.runtime.run_once()
        payload = [r.event["payload"] for r in self.runtime.log.scan().records
                   if r.event.get("taskId") == outcome.task_id
                   and r.event["eventType"] == "TaskClaimed"][0]
        acquired = clock_module.parse_iso8601_ms(payload["leaseAcquiredAt"])
        expires = clock_module.parse_iso8601_ms(payload["leaseExpiresAt"])
        self.assertEqual(expires - acquired, payload["leaseTtlMs"])

    def test_lease_timestamps_are_canonical_utc(self):
        outcome = self.submit(fail_until=1)
        self.runtime.run_once()
        for record in self.runtime.log.scan().records:
            if record.event.get("taskId") != outcome.task_id:
                continue
            for field in ("leaseAcquiredAt", "leaseExpiresAt"):
                value = record.event["payload"].get(field)
                if value is not None:
                    with self.subTest(field=field, value=value):
                        ids.require_iso8601_utc_ms(value, field)
                        self.assertTrue(value.endswith("Z"))

    def test_the_lease_is_cleared_when_the_task_leaves_the_running_states(self):
        outcome = self.submit(fail_until=0)
        self.runtime.run_once()
        row = self.task(outcome.task_id)
        self.assertEqual(row["state"], "succeeded")
        self.assertIsNone(row["lease_holder"])
        self.assertIsNone(row["lease_expires_at"])
        # The GENERATION is preserved -- it only ever increases.
        self.assertEqual(row["lease_generation"], 1)

    def test_lease_generation_is_monotonic_per_task(self):
        outcome = self.submit(fail_until=2)
        self.runtime.run_once()
        generations = [r.event["payload"]["leaseGeneration"]
                       for r in self.runtime.log.scan().records
                       if r.event.get("taskId") == outcome.task_id
                       and r.event["eventType"] == "TaskClaimed"]
        self.assertEqual(generations, [1, 2, 3])
        self.assertEqual(generations, sorted(set(generations)))

    def test_only_an_eligible_queued_task_can_be_leased(self):
        """The guard is `AND state = 'queued'`, and there is no other path."""
        outcome = self.submit(fail_until=0)
        self.runtime.run_once()
        row = self.task(outcome.task_id)
        self.assertEqual(row["state"], "succeeded")
        before = dict(row)
        # A terminal task cannot be claimed again, so a second run changes
        # nothing about its lease.
        self.runtime.run_once()
        self.assertEqual(dict(self.task(outcome.task_id)), before)

    def test_lease_columns_are_written_by_exactly_one_sql_statement(self):
        """Every lease column is set inside the guarded transition UPDATE.

        The projection builds that statement from declared (column, value)
        pairs, so a bare `UPDATE tasks SET lease_...` anywhere would be a
        second write path -- and there must not be one.
        """
        runtime_dir = os.path.join(SRC_DIR, "mogo_platform", "runtime")
        offenders = []
        for root, _dirs, files in os.walk(runtime_dir):
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(root, name)
                with open(path, "r", encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=path)
                for node in ast.walk(tree):
                    if not (isinstance(node, ast.Constant)
                            and isinstance(node.value, str)):
                        continue
                    upper = node.value.upper()
                    if "UPDATE" in upper and "LEASE_" in upper:
                        offenders.append((name, node.lineno, node.value))
        self.assertEqual(offenders, [])


class TestLeaseHolderAuthority(LeaseRuntimeCase):
    def test_a_result_is_refused_when_the_lease_generation_changed_mid_execution(self):
        """Architecture section 24, exercised rather than inspected.

        The generation is bumped behind the executing code's back, simulating a
        reclaim that happened mid-flight. No result event may be appended, and
        the discard must be recorded rather than silent.
        """
        outcome = self.submit(fail_until=0)
        task_id = outcome.task_id
        original = self.runtime._holds_lease

        def bump_then_check(checked_task_id, generation):
            with self.runtime.connection:
                self.runtime.connection.execute(
                    "UPDATE tasks SET lease_generation = lease_generation + 1 "
                    "WHERE task_id = ?", (checked_task_id,))
            self.runtime._holds_lease = original
            return original(checked_task_id, generation)

        self.runtime._holds_lease = bump_then_check
        report = self.runtime.run_once()

        self.assertIn(task_id, report["abandoned"])
        types = [row[0] for row in self.runtime.connection.execute(
            "SELECT event_type FROM event_index WHERE task_id = ?", (task_id,))]
        self.assertNotIn("TaskSucceeded", types)
        anomaly = self.runtime.connection.execute(
            "SELECT reason FROM transition_anomalies WHERE task_id = ? "
            "ORDER BY anomaly_id DESC LIMIT 1", (task_id,)).fetchone()
        self.assertIsNotNone(anomaly)
        self.assertIn("result_written_without_lease", anomaly["reason"])
        # The task is left for recovery to reclaim, not silently completed.
        self.assertEqual(self.task(task_id)["state"], "running")

    def test_the_lease_owner_is_auditable(self):
        outcome = self.submit(fail_until=1)
        self.runtime.run_once()
        run_row = self.runtime.connection.execute(
            "SELECT * FROM runs WHERE run_id = ?", (self.runtime.run_id,)).fetchone()
        self.assertIsNotNone(run_row)
        self.assertEqual(run_row["pid"], os.getpid())
        holders = {r.event["payload"]["leaseHolder"]
                   for r in self.runtime.log.scan().records
                   if r.event.get("taskId") == outcome.task_id
                   and r.event["eventType"] == "TaskClaimed"}
        self.assertEqual(holders, {"runner:" + self.runtime.run_id})


class TestLeaseRecovery(LeaseRuntimeCase):
    def _strand_running(self, fail_until=0):
        """Leave a task in `running` holding a live lease of THIS run."""
        outcome = self.submit(fail_until=fail_until)
        original = self.runtime._holds_lease
        self.runtime._holds_lease = lambda *_args: False
        self.runtime.run_once()
        self.runtime._holds_lease = original
        row = self.task(outcome.task_id)
        self.assertEqual(row["state"], "running")
        self.assertIsNotNone(row["lease_holder"])
        return outcome.task_id

    def test_a_live_lease_of_this_run_is_not_reclaimed(self):
        task_id = self._strand_running()
        report = self.runtime.recover()
        self.assertIn(task_id, report["live_leases_kept"])
        self.assertEqual(report["reclaimed"], [])
        self.assertEqual(self.task(task_id)["state"], "running")
        action = self.runtime.connection.execute(
            "SELECT action FROM recovery_actions ORDER BY action_id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(action["action"], "live_lease_not_reclaimed")

    def test_an_expired_lease_is_reclaimed(self):
        task_id = self._strand_running()
        expires = self.task(task_id)["lease_expires_at"]
        self.clock.set_to(clock_module.parse_iso8601_ms(expires))
        report = self.runtime.recover()
        self.assertEqual(report["reclaim_reasons"][task_id], "lease_expired")
        self.assertEqual(self.task(task_id)["state"], "queued")

    def test_a_lease_from_a_previous_run_is_reclaimed(self):
        task_id = self._strand_running()
        self.reopen()                     # a new run, therefore a new holder
        report = self.runtime.recover()
        self.assertEqual(report["reclaim_reasons"][task_id], "owner_gone")
        row = self.task(task_id)
        self.assertEqual(row["state"], "queued")
        self.assertIsNone(row["lease_holder"])

    def test_a_claimed_task_with_no_lease_is_reclaimed(self):
        task_id = self._strand_running()
        with self.runtime.connection:
            self.runtime.connection.execute(
                "UPDATE tasks SET lease_holder = NULL, lease_expires_at = NULL "
                "WHERE task_id = ?", (task_id,))
        report = self.runtime.recover()
        self.assertEqual(report["reclaim_reasons"][task_id], "no_lease")

    def test_restart_recovers_an_expired_lease_and_completes_the_task(self):
        task_id = self._strand_running()
        self.reopen()
        self.runtime.recover()
        self.runtime.run_once()
        row = self.task(task_id)
        self.assertEqual(row["state"], "succeeded")
        self.assertEqual(row["lease_generation"], 2)

    def test_the_reclaim_reason_is_recorded_in_the_event(self):
        task_id = self._strand_running()
        self.reopen()
        self.runtime.recover()
        reclaims = [r.event["payload"] for r in self.runtime.log.scan().records
                    if r.event.get("taskId") == task_id
                    and r.event["eventType"] == "TaskReclaimed"]
        self.assertEqual(len(reclaims), 1)
        payload = reclaims[0]
        self.assertEqual(payload["reason"], "owner_gone")
        for field in ("reclaimedFrom", "previousLeaseHolder",
                      "previousLeaseGeneration", "leaseExpiresAt",
                      "observedAtUtc", "attempt"):
            self.assertIn(field, payload)

    def test_recover_is_idempotent_with_leases(self):
        task_id = self._strand_running()
        self.reopen()
        first = self.runtime.recover()
        before = self.runtime.log.size_bytes()
        second = self.runtime.recover()
        self.assertEqual(first["reclaimed"], [task_id])
        self.assertEqual(second["reclaimed"], [])
        self.assertEqual(self.runtime.log.size_bytes(), before)

    def test_lease_replay_is_idempotent(self):
        outcome = self.submit(fail_until=1)
        self.runtime.run_once()
        before = dict(self.task(outcome.task_id))
        projection.replay(self.runtime.connection, self.runtime.log,
                          from_log_sequence=0)
        self.assertEqual(dict(self.task(outcome.task_id)), before)

    def test_task_state_and_lease_projection_remain_consistent(self):
        outcome = self.submit(fail_until=2)
        self.runtime.run_once()
        row = self.task(outcome.task_id)
        last_claim = [r.event["payload"] for r in self.runtime.log.scan().records
                      if r.event.get("taskId") == outcome.task_id
                      and r.event["eventType"] == "TaskClaimed"][-1]
        self.assertEqual(row["lease_generation"], last_claim["leaseGeneration"])

    def test_a_backward_clock_is_refused_before_any_append(self):
        """Nothing is written when the clock goes backwards.

        The log length is captured before and after, so a partial append would
        be visible rather than inferred.
        """
        self.submit(fail_until=0)
        size_before = self.runtime.log.size_bytes()
        self.clock.set_to("2026-08-08T11:00:00.000Z")     # one hour into the past
        with self.assertRaises(runtime_errors.ClockRollbackError):
            self.runtime.run_once()
        self.assertEqual(self.runtime.log.size_bytes(), size_before)

    def test_a_backward_clock_cannot_make_an_expired_lease_look_live(self):
        """The monotonic guard fires first, so the runtime refuses to act at
        all rather than reaching a wrong conclusion about expiry."""
        task_id = self._strand_running()
        self.clock.set_to("2026-08-08T11:00:00.000Z")
        with self.assertRaises(runtime_errors.ClockRollbackError):
            self.runtime.recover()
        self.assertEqual(self.task(task_id)["state"], "running")


if __name__ == "__main__":
    unittest.main(verbosity=2)
