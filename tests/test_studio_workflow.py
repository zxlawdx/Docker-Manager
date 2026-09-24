"""Regressões do canvas, templates e autorização do administrador."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import yaml
from apps.dockerflow.services.admin_service import AdminService
from apps.dockerflow.services.template_catalog import list_templates, render_template


class CatalogTests(unittest.TestCase):
    def test_catalog_provides_real_compose_service_and_full_stack_examples(self):
        records = list_templates()
        self.assertGreaterEqual(len(records), 15)
        self.assertTrue(any(item["category"] == "Stacks YAML" for item in records))
        for item in records:
            result = render_template(item["id"])
            parsed = yaml.safe_load(result["content"])
            self.assertTrue(parsed.get("services"))
            self.assertFalse(any(
                spec.get("privileged") or
                any("docker.sock" in str(volume) for volume in spec.get("volumes", []))
                for spec in parsed["services"].values()))
            for spec in parsed["services"].values():
                for exposed in spec.get("ports", []):
                    self.assertTrue(str(exposed).startswith("127.0.0.1:"))
        with self.assertRaises(ValueError):
            render_template("../user_file.yml")

    def test_database_examples_require_environment_credentials(self):
        for name in ("postgres", "mysql", "mariadb", "mongo", "rabbitmq"):
            template = render_template(name)["content"]
            self.assertIn("${", template)
            self.assertIn(":?", template)


class AdminSafetyTests(unittest.TestCase):
    def setUp(self):
        self.runner = MagicMock(return_value=SimpleNamespace(returncode=0))
        self.service = AdminService(runner=self.runner)
        self.rows = [("a" * 64, "web"), ("b" * 64, "db")]

    def test_preview_uses_current_ids_and_no_env_or_command(self):
        with patch.object(self.service, "_list", return_value=self.rows):
            result = self.service.preview()
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["fingerprint"]), 64)
        self.assertEqual(result["containers"][0]["id"], "a" * 12)
        self.assertNotIn("Env", str(result))

    def test_exact_phrase_and_fresh_preview_required_before_any_elevation(self):
        signature = self.service._fingerprint(self.rows)
        with self.assertRaisesRegex(ValueError, "Confirmação"):
            self.service.remove_all(signature, "DELETE")
        self.runner.assert_not_called()
        with patch.object(self.service, "_list", return_value=self.rows):
            with self.assertRaisesRegex(ValueError, "mudou"):
                self.service.remove_all("f" * 64, "APAGAR TODOS")
        self.runner.assert_not_called()

    def test_native_os_prompt_command_uses_only_verified_ids_without_shell(self):
        signature = self.service._fingerprint(self.rows)
        with patch.object(self.service, "_list", side_effect=[self.rows, []]):
            with patch.object(self.service, "_trusted_binary", side_effect=[
                "/usr/bin/pkexec", "/usr/bin/docker"
            ]):
                result = self.service.remove_all(signature, "APAGAR TODOS")
        self.assertTrue(result["ok"])
        self.assertEqual(result["removed"], 2)
        args = self.runner.call_args.args[0]
        self.assertEqual(args[:2], ["/usr/bin/pkexec", "/usr/bin/docker"])
        self.assertIn("unix:///var/run/docker.sock", args)
        self.assertEqual(args[-2:], ["a" * 64, "b" * 64])
        self.assertTrue(self.runner.call_args.kwargs["capture_output"])
        self.assertFalse(self.runner.call_args.kwargs["check"])
        self.assertNotIn("shell", self.runner.call_args.kwargs)

    def test_cancellation_cannot_be_reported_as_complete(self):
        self.runner.return_value.returncode = 126
        signature = self.service._fingerprint(self.rows)
        with patch.object(self.service, "_list", side_effect=[self.rows, self.rows]):
            with patch.object(self.service, "_trusted_binary", side_effect=[
                "/usr/bin/pkexec", "/usr/bin/docker"
            ]):
                result = self.service.remove_all(signature, "APAGAR TODOS")
        self.assertFalse(result["ok"])
        self.assertEqual(result["remaining"], 2)


class VisualWorkflowTests(unittest.TestCase):
    def test_stage_drag_capture_and_two_topology_representations(self):
        base = Path(__file__).resolve().parents[1] / "apps" / "dockerflow"
        graph = (base / "static" / "js" / "graph.js").read_text(encoding="utf-8")
        page = (base / "templates" / "studio.html").read_text(encoding="utf-8")
        spa = (base / "static" / "js" / "studio.js").read_text(encoding="utf-8")
        for name in ("df-network-view", "df-graph-relations", "df-admin-scan",
                     "df-admin-purge", "df-ide-template-load"):
            self.assertIn('id="' + name + '"', page)
        self.assertIn('stage.setPointerCapture(e.pointerId)', graph)
        self.assertIn('stage.addEventListener("pointermove"', graph)
        self.assertIn('function attachByDrop(', graph)
        self.assertIn('function importAllRelations(', graph)
        self.assertIn('"df-graph-relations").onclick=importAllRelations', graph)
        self.assertIn('"/admin/containers/remove-all"', spa)
        self.assertIn('"/templates/compose"', spa)
        self.assertIn("setNetworkView(networkView)", graph)


if __name__ == "__main__":
    unittest.main()
