from pathlib import Path
import ast
import csv
import io
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class DecisionIntelligenceContractTest(unittest.TestCase):
    def test_lifecycle_models_and_fields_are_declared(self):
        source = (ROOT / "models" / "student_lifecycle.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        text = ast.unparse(tree)
        for value in (
            "student.lifecycle.reason",
            "student.reschedule.event",
            "student.intervention",
            "student.program.transition",
            "quit_date",
            "quit_reason_id",
            "renewal_status",
            "expected_end_date",
            "attention_level",
            "attention_reason",
        ):
            self.assertIn(value, text)

    def test_lifecycle_views_are_valid_xml(self):
        tree = ET.parse(ROOT / "views" / "student_lifecycle_views.xml")
        for xpath in tree.findall(".//xpath"):
            self.assertNotIn("@string", xpath.attrib.get("expr", ""))

    def test_new_models_have_explicit_access_rules(self):
        rows = list(csv.DictReader(io.StringIO(
            (ROOT / "security" / "ir.model.access.csv").read_text(encoding="utf-8")
        )))
        external_ids = {row["model_id/id"] for row in rows}
        self.assertTrue({
            "model_student_lifecycle_reason",
            "model_student_reschedule_event",
            "model_student_intervention",
            "model_student_program_transition",
        }.issubset(external_ids))

    def test_existing_viewer_group_is_preserved(self):
        tree = ET.parse(ROOT / "security" / "security.xml")
        ids = {record.attrib.get("id") for record in tree.findall(".//record")}
        self.assertIn("group_student_viewer", ids)

    def test_manifest_loads_lifecycle_after_student_views(self):
        manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
        self.assertIn("views/student_lifecycle_views.xml", manifest["data"])
        self.assertIn("data/student_lifecycle_reason_data.xml", manifest["data"])
        self.assertGreaterEqual(manifest["version"], "17.0.1.1.0")


if __name__ == "__main__":
    unittest.main()
