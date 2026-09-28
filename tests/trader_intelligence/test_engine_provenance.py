"""Tests for scripts/engine_provenance.py (engine-provenance binding).

    python3 -m unittest tests.trader_intelligence.test_engine_provenance
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import engine_provenance as EP  # noqa: E402

METHOD = EP.METHOD


def page(body):
    return ('<html><head><script src="https://cdn.invalid/x.js"></script></head>\n<body><script>'
            + body + '</script></body></html>\n')


class ExtractionTests(unittest.TestCase):
    def test_python_extraction_equals_the_javascript_extraction_on_the_real_engine(self):
        # The engine test (P1) proves the stamp == sha256 of the JS regex extraction; this closes
        # the other side: the Python verifier hashes exactly the same text.
        js = subprocess.run(
            ["node", "-e", "const s=require('fs').readFileSync(process.argv[1],'utf8');"
             "const m=s.match(/<script>([\\s\\S]*?)<\\/script>/);"
             "process.stdout.write(require('crypto').createHash('sha256').update(m[1],'utf8').digest('hex'))",
             os.path.join(REPO, "index.html")], capture_output=True, text=True, check=True).stdout
        self.assertEqual(EP.artifact_sha256(open(os.path.join(REPO, "index.html"), "rb").read()), js)

    def test_the_external_script_tag_is_not_the_engine(self):
        self.assertEqual(EP.script_text(page("let a=1;")), "let a=1;")

    def test_line_endings_are_normalised_as_html_preprocessing_does(self):
        self.assertEqual(EP.artifact_sha256(page("a;\r\nb;\rc;")), EP.artifact_sha256(page("a;\nb;\nc;")))

    def test_a_different_engine_text_is_a_different_artifact(self):
        self.assertNotEqual(EP.artifact_sha256(page("a;")), EP.artifact_sha256(page("a; ")))

    def test_no_inline_script_is_no_artifact(self):
        self.assertIsNone(EP.artifact_sha256('<script src="x.js"></script>'))


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp(prefix="engine_prov_repo_")

        def git(*a):
            return subprocess.run(["git", "-C", cls.d] + list(a), capture_output=True, text=True, check=True).stdout.strip()
        for a in (("init", "-q"), ("config", "user.email", "t@example.invalid"), ("config", "user.name", "t"),
                  ("config", "commit.gpgsign", "false")):
            git(*a)
        cls.commits = []
        for n, body in enumerate(("engine_v1();", "engine_v2();", "engine_v1();")):   # the third RESTORES v1
            with open(os.path.join(cls.d, "index.html"), "w") as f:
                f.write(page(body))
            git("add", "index.html")
            git("commit", "-q", "-m", "c%d" % n, "--date", "2026-01-0%dT00:00:00Z" % (n + 1))
            cls.commits.append(git("rev-parse", "HEAD"))
        with open(os.path.join(cls.d, "notes.txt"), "w") as f:
            f.write("unrelated")
        git("add", "notes.txt")
        git("commit", "-q", "-m", "unrelated")
        cls.index = EP.history_index(cls.d)
        cls.v1, cls.v2 = EP.artifact_sha256(page("engine_v1();")), EP.artifact_sha256(page("engine_v2();"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def pkg(self, **ep):
        return {"packageId": "PKG|T|1", "engineVersion": "12.68.1",
                "engineProvenance": dict({"method": METHOD, "scriptSha256": None, "configSha256": "c" * 64}, **ep)}

    def test_an_artifact_introduced_by_several_commits_is_ambiguous_never_bound(self):
        v = EP.classify(self.pkg(scriptSha256=self.v1), self.index)
        self.assertEqual(v["linkage"], "AMBIGUOUS")
        self.assertEqual([c["commit"] for c in v["candidateCommits"]], [self.commits[0], self.commits[2]])
        self.assertNotIn("introducingCommit", v)
        self.assertEqual(v["configSha256"], "c" * 64)

    def test_an_artifact_introduced_by_exactly_one_commit_is_bound_to_it(self):
        v = EP.classify(self.pkg(scriptSha256=self.v2), self.index)
        self.assertEqual((v["linkage"], v["introducingCommit"]), ("BOUND", self.commits[1]))
        self.assertEqual([c["commit"] for c in v["candidateCommits"]], [self.commits[1]])

    def test_no_verdict_claims_a_deployed_or_producing_commit(self):
        for art in (self.v1, self.v2, "e" * 64):
            v = EP.classify(self.pkg(scriptSha256=art), self.index)
            self.assertEqual(v["claims"], {"deployedCommit": "NOT_ESTABLISHED_BY_ARTIFACT_HASH",
                                           "producingCommit": "NOT_ESTABLISHED_BY_ARTIFACT_HASH"}, v["linkage"])
            self.assertFalse({"deployedCommit", "producingCommit", "sourceCommit"} & set(v), v)

    def test_an_artifact_no_reachable_commit_carries_is_unmatched_not_guessed(self):
        v = EP.classify(self.pkg(scriptSha256="e" * 64), self.index)
        self.assertEqual(v["linkage"], "ARTIFACT_OBSERVED_SOURCE_UNMATCHED")
        self.assertFalse({"introducingCommit", "candidateCommits"} & set(v), v)

    def test_a_package_from_before_the_binding_is_unknown_despite_its_version_string(self):
        legacy = {"packageId": "PKG|T|0", "engineVersion": "12.68.1", "createdAt": "2026-01-02T00:00:00Z"}
        self.assertEqual(EP.classify(legacy, self.index),
                         {"packageId": "PKG|T|0", "linkage": "UNKNOWN", "reason": "NO_ENGINE_PROVENANCE_RECORDED"})

    def test_an_unavailable_artifact_is_unknown(self):
        v = EP.classify(self.pkg(scriptSha256=None), self.index)
        self.assertEqual((v["linkage"], v["reason"]), ("UNKNOWN", "ARTIFACT_NOT_RECORDED"))

    def test_an_unsupported_method_is_unknown_even_with_a_matching_hash(self):
        v = EP.classify(self.pkg(scriptSha256=self.v1, method="GUESS"), self.index)
        self.assertEqual(v["linkage"], "UNKNOWN")

    def test_a_malformed_hash_is_unknown(self):
        self.assertEqual(EP.classify(self.pkg(scriptSha256=self.v1[:-1]), self.index)["linkage"], "UNKNOWN")

    def test_the_index_covers_only_index_html_blobs(self):
        self.assertEqual(set(self.index), {self.v1, self.v2})


if __name__ == "__main__":
    unittest.main()


class ImporterAggregateTests(unittest.TestCase):
    """import_mogo_observations.engine_artifacts: the committed source-record aggregate."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(REPO, "scripts", "trader_intelligence"))
        import import_mogo_observations as IMO
        cls.agg = staticmethod(IMO.engine_artifacts)

    def test_packages_captured_before_the_binding_add_nothing(self):
        # so re-importing an old file leaves its source record byte-identical
        self.assertEqual(self.agg([{"packageId": "a"}, {"packageId": "b", "engineVersion": "12.68.1"}]), {})

    def test_an_unavailable_artifact_adds_nothing_on_its_own(self):
        self.assertEqual(self.agg([{"engineProvenance": {"scriptSha256": None}}]), {})

    def test_artifacts_are_counted_exactly_and_the_rest_are_disclosed(self):
        a, b = "a" * 64, "b" * 64
        got = self.agg([{"engineProvenance": {"scriptSha256": b}}, {"engineProvenance": {"scriptSha256": a}},
                        {"engineProvenance": {"scriptSha256": b}}, {"packageId": "legacy"},
                        {"engineProvenance": {"scriptSha256": None}}])
        self.assertEqual(got, {"engineArtifacts": [{"scriptSha256": a, "packageCount": 1},
                                                   {"scriptSha256": b, "packageCount": 2}],
                               "packagesWithoutEngineArtifact": 2})
