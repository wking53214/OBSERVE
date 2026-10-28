"""
Tests: observe_clinical_risk_adapter.py
=======================================

Unit tests for the GSA adapter modules in observe_clinical_risk_adapter.py.
Run: python3 -m pytest test_observe_clinical_risk_adapter.py -v
"""

import unittest

from observe_clinical_risk_adapter import RegimeClassificationModule


class TestRegimeClassificationModule(unittest.TestCase):

    def test_empty_regime_distribution_is_not_classified_stable(self):
        """No data is not evidence of stability: an empty distribution escalates."""
        payload = RegimeClassificationModule().process({"fused_result": {}})
        verdict = payload["verdict"]
        self.assertTrue(verdict["escalation_required"])
        self.assertNotEqual(verdict["classified_regime"], "stable")
        self.assertTrue(payload["_gaps_headers"]["risk_metrics"]["escalation_required"])


if __name__ == "__main__":
    unittest.main()
