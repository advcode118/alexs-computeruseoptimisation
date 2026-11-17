"""Offline checks for report estimators; no model/browser clients."""

import unittest
from unittest.mock import patch

import report_rep1 as report


class ReportTests(unittest.TestCase):
    def test_p90_interpolates_and_handles_singleton(self):
        self.assertEqual(report.quantile([10, 20, 30], .9), 28)
        self.assertEqual(report.quantile([10], .9), 10)

    def test_empty_inputs_are_rejected(self):
        for operation in (lambda: report.quantile([], .9), lambda: report.metrics([]),
                          lambda: report.bootstrap({}, {}, "best")):
            with self.assertRaises(ValueError):
                operation()

    def test_metrics_include_failed_attempts(self):
        rows = [{"success": True, "wall_ms": 10, "usd": .01},
                {"success": False, "wall_ms": 30, "usd": .03}]
        result = report.metrics(rows)
        self.assertEqual(result["pass_rate"], .5)
        self.assertEqual(result["mean_wall_ms"], 20)
        self.assertEqual(result["p90_wall_ms"], 28)
        self.assertEqual(result["mean_usd"], .02)

    def test_cluster_bootstrap_keeps_pairs_and_site_multiplicity(self):
        tasks = {"a": {"start_url": "https://www.example.com/a"},
                 "b": {"start_url": "https://example.com/b"},
                 "c": {"start_url": "https://other.test/c"}}
        rows = {"a": {"success": True, "wall_ms": 10},
                "b": {"success": False, "wall_ms": 20},
                "c": {"success": False, "wall_ms": 30}}
        with patch.object(report, "BOOTSTRAPS", 500):
            result = report.bootstrap({"best": rows, "same": rows}, tasks, "best")
        self.assertEqual(result["clusters"], {"example.com": 2, "other.test": 1})
        self.assertEqual(result["pass_rate_ci"]["best"], [0, .5])
        self.assertEqual(result["difference_ci"]["same"], [0, 0])
        self.assertEqual(result["wall_difference_ci"]["same"], [0, 0])

    def test_unpaired_task_sets_are_rejected(self):
        with self.assertRaises(AssertionError):
            report.bootstrap({"best": {"a": {}}, "other": {"b": {}}}, {}, "best")


if __name__ == "__main__":
    unittest.main()
