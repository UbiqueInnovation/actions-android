import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

path = Path(__file__).resolve().parents[1] / ".github/actions/limmat-report/report.py"
spec = importlib.util.spec_from_file_location("limmat_report", path)
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "GITHUB_REPOSITORY": "example/android", "GITHUB_RUN_ID": "42",
            "GITHUB_RUN_ATTEMPT": "2", "GITHUB_REF": "refs/heads/main",
            "GITHUB_WORKFLOW": "Build", "GITHUB_ACTOR": "actor",
            "LIMMAT_SCHEME": "app:prodRelease", "LIMMAT_RUNNER_NAME": "k8s",
            "LIMMAT_RUNNER_ENVIRONMENT": "self-hosted", "LIMMAT_OUTCOME": "",
        }
        self.event = {"repository": {"default_branch": "main"}}

    def test_build_boundaries(self):
        for trigger, outcome in [("build_start", "in_progress"), ("build_end", "success"),
                                 ("build_end", "failure"), ("build_end", "cancelled")]:
            with self.subTest(trigger=trigger, outcome=outcome):
                self.env.update(LIMMAT_EVENT=trigger, LIMMAT_OUTCOME=outcome)
                path, body = reporter.report(self.env, self.event, 2000)
                self.assertEqual(path, "/apis/builds/logs")
                self.assertEqual((body["platform"], body["scheme"], body["trigger"], body["outcome"]),
                                 ("android", "app:prodRelease", trigger, outcome))
                self.assertEqual((body["runAttempt"], body["timestamp"]), ("2", 2000))

    def test_gradle_zero_and_branch_guard(self):
        self.env.update(LIMMAT_EVENT="gradle", LIMMAT_PACKAGE="com.example.app", LIMMAT_COUNT="0")
        path, body = reporter.report(self.env, self.event, 2000)
        self.assertEqual(path, "/apis/packages/gradle")
        self.assertEqual(body["outdatedDirectDependencies"], 0)
        self.env["LIMMAT_COUNT"] = ""
        with self.assertRaises(ValueError):
            reporter.report(self.env, self.event, 2000)
        self.env["GITHUB_REF"] = "refs/heads/preview"
        self.assertIsNone(reporter.report(self.env, self.event, 2000))

    def test_retry_reuses_identical_request(self):
        connection = Mock()
        connection.getresponse.side_effect = [Mock(status=503), Mock(status=204)]
        with patch.object(reporter.http.client, "HTTPSConnection", return_value=connection) as connect, patch.object(reporter.time, "sleep"):
            reporter.send("/apis/builds/logs", {"timestamp": 2000}, "test-token", "https://example.invalid:8443/prefix/")
        first, second = connection.request.call_args_list
        self.assertEqual(first, second)
        connect.assert_called_with("example.invalid", port=8443, timeout=5)
        self.assertEqual(first.args[:2], ("POST", "/prefix/apis/builds/logs"))

    def test_rejects_non_https_endpoint_before_sending_token(self):
        with patch.object(reporter.http.client, "HTTPSConnection") as connect:
            for invalid in ["", "http://example.invalid", "https://user@example.invalid"]:
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    reporter.send("/apis/builds/logs", {}, "test-token", invalid)
            connect.assert_not_called()
