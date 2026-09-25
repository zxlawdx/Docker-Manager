"""Credentials and destructive bulk-volume regressions; uses mocked Docker only."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from apps.dockerflow.services import compose_service as compose
from apps.dockerflow.services.admin_service import AdminService


class CredentialsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base_patch = patch.object(compose, "BASE", Path(self.temp.name))
        base_patch.start()
        self.addCleanup(base_patch.stop)
        self.yaml = ("services:\n  grafana:\n    image: grafana/grafana:latest\n"
                     "    environment:\n"
                     "      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:?Defina GRAFANA_PASSWORD}\n")

    def test_yaml_variables_are_listed_without_leaking_values(self):
        before = compose.variables_status("painel", self.yaml)
        entry = next(v for v in before["variables"] if v["name"] == "GRAFANA_PASSWORD")
        self.assertTrue(entry["used_by_yaml"])
        self.assertFalse(entry["saved"])
        compose.set_variable("painel", "GRAFANA_PASSWORD", "value-with-#-and-:-chars")
        after = compose.variables_status("painel", self.yaml)
        self.assertTrue(after["variables"][0]["saved"])
        self.assertNotIn("value-with", repr(after))
        self.assertNotIn("value-with", repr(compose.load("painel")) if compose.projects() else "")
        stored = Path(self.temp.name) / "painel" / compose.VAULT
        self.assertTrue(stored.exists())
        if os.name == "posix":
            self.assertEqual(stored.stat().st_mode & 0o077, 0)
            self.assertEqual(stored.parent.stat().st_mode & 0o077, 0)

    def test_injects_secrets_only_at_compose_runtime(self):
        secret = "opaque-foo-#12"
        compose.set_variable("app", "GRAFANA_PASSWORD", secret)
        returned = SimpleNamespace(returncode=0, stdout=secret + " should be hidden",
                                   stderr="\n")
        with patch.object(compose.subprocess, "run", return_value=returned) as process:
            output = compose.execute("app", "validate", self.yaml)
        self.assertTrue(output["ok"])
        self.assertEqual(process.call_args.kwargs["env"]["GRAFANA_PASSWORD"], secret)
        self.assertNotIn(secret, repr(output))
        self.assertIn("[SEGREDO OCULTADO]", output["output"])
        self.assertNotIn(secret, compose.load("app")["content"])

    def test_visual_graph_resolves_exact_reference_from_project(self):
        compose.set_variable("studio", "DB_PASSWORD", "secret-for-creation")
        prepared = compose.resolve_container_secrets({
            "environment": {"POSTGRES_PASSWORD": "${DB_PASSWORD}"},
            "secret_project": "studio", "image": "postgres:16"
        })
        self.assertEqual(prepared["environment"]["POSTGRES_PASSWORD"], "secret-for-creation")
        self.assertNotIn("environment", {"x": "y"})
        with self.assertRaisesRegex(ValueError, "não cadastrada"):
            compose.resolve_container_secrets({
                "environment": {"POSTGRES_PASSWORD": "${UNKNOWN}"},
                "secret_project": "studio"
            })
        with self.assertRaisesRegex(ValueError, "Use"):
            compose.resolve_container_secrets({
                "environment": {"POSTGRES_PASSWORD": "prefix-${DB_PASSWORD}"},
                "secret_project": "studio"
            })

    def test_secure_create_does_not_echo_engine_exception_with_secret(self):
        from docker.errors import DockerException
        compose.set_variable("studio", "PASS", "private-1234")
        engine = MagicMock()
        engine.create_container.side_effect = DockerException("engine said private-1234")
        with self.assertRaises(ValueError) as raised:
            compose.create_container_with_secrets({
                "environment": {"SECRET": "${PASS}"}, "secret_project": "studio"
            }, engine)
        self.assertNotIn("private-1234", str(raised.exception))

    def test_variable_update_delete_and_validations(self):
        with self.assertRaises(ValueError):
            compose.set_variable("app", "INVALID-KEY", "ok")
        with self.assertRaises(ValueError):
            compose.set_variable("app", "VALID", "line\nbreak")
        compose.set_variable("app", "VALID", "first")
        compose.set_variable("app", "VALID", "second")
        self.assertTrue(compose.variables_status("app")["variables"][0]["saved"])
        compose.delete_variable("app", "VALID")
        self.assertFalse(compose.variables_status("app")["variables"])


class VolumeAdminTests(unittest.TestCase):
    def setUp(self):
        self.runner = MagicMock(return_value=SimpleNamespace(returncode=0))
        self.service = AdminService(runner=self.runner)
        self.volumes = [("app_data", "local", ()), ("cache_store", "local", ())]

    def test_preview_lists_all_volumes_and_usage_without_options_secrets(self):
        with patch.object(self.service, "_list_volumes", return_value=[
            ("app_data", "local", ("web",)), ("cache_store", "local", ())
        ]):
            data = self.service.preview_volumes()
        self.assertEqual(data["in_use"], 1)
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["volumes"][0]["containers"], ["web"])
        self.assertEqual(len(data["fingerprint"]), 64)

    def test_volume_confirmation_is_independent_of_container_confirmation(self):
        signature = self.service._fingerprint_volumes(self.volumes)
        with self.assertRaisesRegex(ValueError, "APAGAR VOLUMES"):
            self.service.remove_all_volumes(signature, "APAGAR TODOS")
        self.runner.assert_not_called()
        with patch.object(self.service, "_list_volumes", return_value=self.volumes):
            with self.assertRaisesRegex(ValueError, "mudou"):
                self.service.remove_all_volumes("f" * 64, "APAGAR VOLUMES")
        self.runner.assert_not_called()

    def test_in_use_volumes_are_blocked_without_removing_containers(self):
        busy = [("app_data", "local", ("stopped-app",))]
        with patch.object(self.service, "_list_volumes", return_value=busy):
            with self.assertRaisesRegex(ValueError, "em uso"):
                self.service.remove_all_volumes(
                    self.service._fingerprint_volumes(busy), "APAGAR VOLUMES")
        self.runner.assert_not_called()

    def test_explicit_polkit_invocation_does_not_force_or_shell(self):
        with patch.object(self.service, "_list_volumes", side_effect=[self.volumes, []]):
            with patch.object(self.service, "_trusted_binary", side_effect=[
                "/usr/bin/pkexec", "/usr/bin/docker"
            ]):
                result = self.service.remove_all_volumes(
                    self.service._fingerprint_volumes(self.volumes), "APAGAR VOLUMES")
        self.assertTrue(result["ok"])
        args = self.runner.call_args.args[0]
        self.assertEqual(args[:2], ["/usr/bin/pkexec", "/usr/bin/docker"])
        self.assertEqual(args[-2:], ["app_data", "cache_store"])
        self.assertEqual(args[-5:-2], ["volume", "rm", "--"])
        self.assertNotIn("--force", args)
        self.assertNotIn("shell", self.runner.call_args.kwargs)

    def test_denied_polkit_does_not_claim_volumes_deleted(self):
        self.runner.return_value.returncode = 126
        with patch.object(self.service, "_list_volumes",
                          side_effect=[self.volumes, self.volumes]):
            with patch.object(self.service, "_trusted_binary", side_effect=[
                "/usr/bin/pkexec", "/usr/bin/docker"
            ]):
                result = self.service.remove_all_volumes(
                    self.service._fingerprint_volumes(self.volumes), "APAGAR VOLUMES")
        self.assertFalse(result["ok"])
        self.assertEqual(result["remaining"], 2)


class FrontendBindingsTests(unittest.TestCase):
    def test_ui_has_secret_manager_and_two_separate_destructive_actions(self):
        root = Path(__file__).resolve().parents[1] / "apps" / "dockerflow"
        page = (root / "templates/studio.html").read_text("utf-8")
        script = (root / "static/js/studio.js").read_text("utf-8")
        graph = (root / "static/js/graph.js").read_text("utf-8")
        for ident in ("df-env-key", "df-env-value", "df-env-save", "df-env-list",
                      "df-admin-volumes-scan", "df-admin-volumes-purge"):
            self.assertIn('id="' + ident + '"', page)
        self.assertIn('type="password"', page)
        self.assertIn('"/compose/variables/set"', script)
        self.assertIn('"/admin/volumes/remove-all"', script)
        self.assertIn('"configure-secret"', graph)
        self.assertIn('window.addEventListener("pointermove",globalMove,true)', graph)
        self.assertIn('window.addEventListener("pointerup",globalUp,true)', graph)


if __name__ == "__main__":
    unittest.main()
