"""
Tests for the signal validators in clinical_signal_validator_adapter.py.

The generalized DomainSignalValidator and its tests were ported from ZTGKT
when that repo was buried in the Graveyard. The clinical rules are unchanged.

Run: python3 -m pytest test_domain_signal_validator.py -v
"""

import re
import unittest

from clinical_signal_validator_adapter import (
    ClinicalSignalValidator,
    DomainSignalValidator,
)

GOOD = "At 14:22 the patient SpO2 reading fell to 88 percent."


class ClinicalValidatorTests(unittest.TestCase):
    def test_complete_signal_validates(self):
        ok, failures = ClinicalSignalValidator().validate_signal(GOOD)
        self.assertTrue(ok)
        self.assertEqual(failures, [])

    def test_missing_time_anchor_fails(self):
        ok, failures = ClinicalSignalValidator().validate_signal(
            "The patient SpO2 fell to 88 percent.")
        self.assertFalse(ok)
        self.assertTrue(any("temporal" in f for f in failures))

    def test_missing_measurement_fails(self):
        ok, failures = ClinicalSignalValidator().validate_signal(
            "At 14:22 the patient was monitored.")
        self.assertFalse(ok)
        self.assertTrue(any("quantitative" in f for f in failures))

    def test_missing_context_fails(self):
        ok, failures = ClinicalSignalValidator().validate_signal(
            "At 14:22 a reading of 88 percent.")
        self.assertFalse(ok)
        self.assertTrue(any("clinical context" in f for f in failures))

    def test_hedging_is_never_a_failure(self):
        """The defect that caused the split: hedging must not fail a clinical signal."""
        ok, failures = ClinicalSignalValidator().validate_signal(
            "At 14:22 the patient SpO2 of 88 percent may indicate desaturation.")
        self.assertTrue(ok)
        self.assertEqual(failures, [])

    def test_log_records_each_call_with_original_shape(self):
        v = ClinicalSignalValidator()
        v.validate_signal(GOOD)
        v.validate_signal("nothing useful")
        self.assertEqual([e["is_valid"] for e in v.validation_log], [True, False])
        self.assertEqual(
            sorted(v.validation_log[0]),
            ["failures", "is_valid", "signal_sample", "timestamp"])

    def test_archive_attribute_names_survive(self):
        self.assertEqual(
            set(ClinicalSignalValidator.REQUIRED_CLINICAL_MARKERS),
            {"temporal_specificity", "numeric_value", "clinical_context"})
        self.assertTrue(ClinicalSignalValidator.HEDGING_IS_GOOD.search("may"))


class DomainValidatorTests(unittest.TestCase):
    def test_accepts_a_custom_marker_set(self):
        v = DomainSignalValidator(
            {"ticket": re.compile(r"\b[A-Z]+-\d+\b")},
            {"ticket": "Missing ticket reference"},
            profile_name="ops")
        self.assertTrue(v.validate_signal("Rollback for OPS-4412 completed.")[0])
        self.assertEqual(
            v.validate_signal("Rollback completed.")[1], ["Missing ticket reference"])

    def test_unnamed_failure_gets_a_default_message(self):
        v = DomainSignalValidator({"owner": re.compile(r"owner:")})
        self.assertEqual(
            v.validate_signal("no owner")[1], ["Missing required marker: owner"])

    def test_no_markers_means_nothing_can_fail(self):
        self.assertEqual(DomainSignalValidator({}).validate_signal("anything"), (True, []))

    def test_clinical_is_a_domain_validator(self):
        self.assertIsInstance(ClinicalSignalValidator(), DomainSignalValidator)


if __name__ == "__main__":
    unittest.main()
