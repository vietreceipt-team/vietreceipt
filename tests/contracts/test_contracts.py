import copy
import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[2]


def load_json(relative_path):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def openapi_validator(schema_name):
    spec = yaml.safe_load((ROOT / "openapi/openapi.yaml").read_text(encoding="utf-8"))
    wrapper = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"#/components/schemas/{schema_name}",
        "components": spec["components"],
    }
    return Draft202012Validator(wrapper, format_checker=FormatChecker())


class KIEResultContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_json("schemas/kie-result.schema.json")
        cls.validator = Draft202012Validator(cls.schema, format_checker=FormatChecker())
        cls.valid = load_json("examples/kie-result.json")

    def mutated(self, field_name, **changes):
        result = copy.deepcopy(self.valid)
        result["fields"][field_name].update(changes)
        return result

    def assert_invalid(self, instance):
        with self.assertRaises(ValidationError):
            self.validator.validate(instance)

    def test_valid_kie_example(self):
        self.validator.validate(self.valid)

    def test_rejects_present_with_null_normalized_value(self):
        self.assert_invalid(self.mutated("merchant_name", normalized_value=None))

    def test_rejects_unknown_with_prediction(self):
        self.assert_invalid(self.mutated("receipt_date", predicted_value="12/08/2026"))

    def test_rejects_unknown_without_machine_review(self):
        self.assert_invalid(self.mutated("receipt_date", machine_needs_review=False))

    def test_rejects_not_present_without_machine_review(self):
        instance = self.mutated("invoice_id", value_status="NOT_PRESENT", machine_needs_review=False)
        self.assert_invalid(instance)

    def test_rejects_unreadable_without_machine_review(self):
        self.assert_invalid(self.mutated("merchant_address", machine_needs_review=False))

    def test_rejects_provenance_without_raw_text(self):
        self.assert_invalid(self.mutated("merchant_address", raw_text=None))

    def test_rejects_integer_merchant_name(self):
        self.assert_invalid(self.mutated("merchant_name", normalized_value=81302))

    def test_rejects_string_total_amount(self):
        self.assert_invalid(self.mutated("total_amount", normalized_value="81302"))


class OCRResultContractTests(unittest.TestCase):
    def test_valid_ocr_example(self):
        schema = load_json("schemas/ocr-result.schema.json")
        example = load_json("examples/ocr-result.json")
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(example)


class OpenAPIFieldContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        kie = load_json("examples/kie-result.json")
        cls.field = {
            "field_name": "merchant_name",
            "machine": kie["fields"]["merchant_name"],
            "has_correction": False,
            "corrected_status": None,
            "corrected_value": None,
            "effective_status": "PRESENT",
            "effective_value": "CỬA HÀNG MINH HỌA",
            "effective_needs_review": False,
            "updated_at": "2026-08-12T03:00:02Z",
            "corrected_by": None,
            "corrected_at": None,
        }

    def test_valid_merchant_name_projection(self):
        openapi_validator("MerchantNameField").validate(self.field)

    def test_rejects_field_name_not_matching_object_key_schema(self):
        invalid = copy.deepcopy(self.field)
        invalid["field_name"] = "total_amount"
        with self.assertRaises(ValidationError):
            openapi_validator("MerchantNameField").validate(invalid)

    def test_rejects_integer_merchant_name_projection(self):
        invalid = copy.deepcopy(self.field)
        invalid["machine"]["normalized_value"] = 81302
        with self.assertRaises(ValidationError):
            openapi_validator("MerchantNameField").validate(invalid)


class ReceiptLifecycleContractTests(unittest.TestCase):
    def base_receipt(self, status):
        return {
            "receipt_id": "00000000-0000-4000-8000-000000000001",
            "status": status,
            "latest_ocr_run_id": None,
            "latest_kie_run_id": None,
            "created_at": "2026-08-12T03:00:00Z",
            "updated_at": "2026-08-12T03:00:00Z",
        }

    def projected_fields(self):
        machine_fields = load_json("examples/kie-result.json")["fields"]
        values = {
            "merchant_name": "CỬA HÀNG MINH HỌA",
            "receipt_date": None,
            "total_amount": 123000,
            "invoice_id": None,
            "merchant_address": None,
        }
        return {
            name: {
                "field_name": name,
                "machine": machine,
                "has_correction": False,
                "corrected_status": None,
                "corrected_value": None,
                "effective_status": machine["value_status"],
                "effective_value": values[name],
                "effective_needs_review": machine["machine_needs_review"],
                "updated_at": "2026-08-12T03:00:02Z",
                "corrected_by": None,
                "corrected_at": None,
            }
            for name, machine in machine_fields.items()
        }

    def test_pre_kie_statuses_do_not_require_fields(self):
        validator = openapi_validator("Receipt")
        for status in ("UPLOADED", "PROCESSING", "FAILED"):
            with self.subTest(status=status):
                validator.validate(self.base_receipt(status))

    def test_needs_review_requires_full_fields(self):
        receipt = self.base_receipt("NEEDS_REVIEW")
        receipt["latest_kie_run_id"] = "00000000-0000-4000-8000-000000000003"
        with self.assertRaises(ValidationError):
            openapi_validator("Receipt").validate(receipt)

    def test_valid_needs_review_has_full_fields(self):
        receipt = self.base_receipt("NEEDS_REVIEW")
        receipt["latest_kie_run_id"] = "00000000-0000-4000-8000-000000000003"
        receipt["fields"] = self.projected_fields()
        openapi_validator("Receipt").validate(receipt)

    def test_verified_requires_full_fields_and_verification_audit(self):
        receipt = self.base_receipt("VERIFIED")
        receipt["latest_kie_run_id"] = "00000000-0000-4000-8000-000000000003"
        with self.assertRaises(ValidationError):
            openapi_validator("Receipt").validate(receipt)

    def test_valid_verified_has_full_effective_projection_and_audit(self):
        receipt = self.base_receipt("VERIFIED")
        receipt["latest_kie_run_id"] = "00000000-0000-4000-8000-000000000003"
        receipt["fields"] = self.projected_fields()
        actor = "00000000-0000-4000-8000-000000000004"
        for name, field in receipt["fields"].items():
            if field["effective_status"] in ("UNKNOWN", "UNREADABLE"):
                field["has_correction"] = True
                field["corrected_by"] = actor
                field["corrected_at"] = "2026-08-12T03:01:00Z"
                field["effective_needs_review"] = False
                if name == "receipt_date":
                    field["corrected_status"] = "PRESENT"
                    field["corrected_value"] = "2026-08-12"
                    field["effective_status"] = "PRESENT"
                    field["effective_value"] = "2026-08-12"
                else:
                    field["corrected_status"] = "UNREADABLE"
                    field["corrected_value"] = None
                    field["effective_status"] = "UNREADABLE"
                    field["effective_value"] = None
        receipt["verified_by"] = actor
        receipt["verified_at"] = "2026-08-12T03:02:00Z"
        openapi_validator("Receipt").validate(receipt)


if __name__ == "__main__":
    unittest.main()
