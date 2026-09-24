"""DockerFlow PR #3: testes unitários sem daemon e contrato mínimo de interface."""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from apps.dockerflow.services.docker_service import DockerService
from apps.dockerflow.services import diagnostic_service
from apps.dockerflow.services.graph_service import plan, to_compose


class DockerStudioPlusTests(unittest.TestCase):
    def setUp(self):
        self.engine = MagicMock()
        self.engine.ping.return_value = True
        self.service = DockerService(client=self.engine)

    def test_ipv6_ipam_and_static_address_validation(self):
        self.engine.networks.create.return_value.id = "dual-stack"
        result = self.service.network_action("create", {
            "name": "lab-dual", "subnet": "172.28.0.0/24",
            "gateway": "172.28.0.1", "ipv6_subnet": "fd45:1234::/64",
            "ipv6_gateway": "fd45:1234::1"})
        self.assertEqual(result["id"], "dual-stack")
        kwargs = self.engine.networks.create.call_args.kwargs
        self.assertTrue(kwargs["enable_ipv6"])
        self.assertIsNotNone(kwargs["ipam"])
        with self.assertRaisesRegex(ValueError, "IPv6"):
            self.service.network_action("create", {"name": "bad", "ipv6_subnet": "172.29.0.0/24"})
        with self.assertRaisesRegex(ValueError, "Gateway IPv6"):
            self.service.network_action("create", {
                "name": "bad", "ipv6_subnet": "fd00::/64", "ipv6_gateway": "fdff::1"})

    def test_network_connect_validates_alias_and_ip_families(self):
        network = MagicMock()
        network.attrs = {"Containers": {}}
        self.engine.networks.get.return_value = network
        self.engine.containers.get.return_value.id = "instance"
        self.service.network_action("connect", {
            "network": "lab", "container": "instance", "aliases": ["api"],
            "ipv4_address": "172.28.0.3", "ipv6_address": "fd00::3"})
        network.connect.assert_called_once()
        self.assertEqual(network.connect.call_args.kwargs["aliases"], ["api"])
        with self.assertRaisesRegex(ValueError, "Aliases"):
            self.service.network_action("connect", {
                "network": "lab", "container": "instance", "aliases": ["bad alias"]})
        with self.assertRaisesRegex(ValueError, "IPv4/IPv6"):
            self.service.network_action("connect", {
                "network": "lab", "container": "instance", "ipv4_address": "fd00::3"})

    def test_dns_and_commands_are_validated_before_container_creation(self):
        with self.assertRaises(ValueError):
            self.service.create_container({"image": "alpine", "dns": ["not-an-IP"]})
        with self.assertRaisesRegex(ValueError, "Comando"):
            self.service.create_container({"image": "alpine", "command": "rm -rf /"})

    def test_processes_do_not_expose_potentially_sensitive_command_args(self):
        c = MagicMock()
        c.name = "api"
        c.status = "running"
        c.top.return_value = {"Titles": ["UID", "PID", "COMMAND"],
                              "Processes": [["root", "123", "python --token PRIVATE_KEY"]]}
        self.engine.containers.get.return_value = c
        result = self.service.processes("api")
        self.assertEqual(result["processes"][0]["PID"], "123")
        self.assertNotIn("PRIVATE_KEY", str(result))
        self.assertNotIn("COMMAND", str(result))

    def test_volume_usage_counts_stopped_containers_and_avoids_sensitive_options(self):
        container = MagicMock()
        container.name = "stopped-app"
        container.attrs = {"Mounts": [{"Type": "volume", "Name": "data"}]}
        self.engine.containers.list.return_value = [container]
        volume = MagicMock()
        volume.name = "data"
        volume.attrs = {"Driver": "local", "Options": {"password": "SECRET"}}
        self.engine.volumes.list.return_value = [volume]
        self.engine.volumes.get.return_value = volume
        self.assertEqual(self.service.volumes()[0]["containers"], ["stopped-app"])
        self.assertNotIn("SECRET", str(self.service.volume_action("inspect", {"name": "data"})))
        with self.assertRaisesRegex(ValueError, "referenciado"):
            self.service.volume_action("remove", {"name": "data"})
        volume.remove.assert_not_called()

    def test_graph_omits_implicit_bridge_for_new_isolated_service(self):
        import yaml
        graph = {"nodes": [{"id": "a", "name": "isolado",
                           "kind": "container", "image": "alpine:3.20"}],
                 "edges": []}
        doc = yaml.safe_load(to_compose(graph))
        self.assertEqual(doc["services"]["isolado"]["network_mode"], "none")
        source = "services:\n  api:\n    image: alpine:3.20\n"
        graph["source_compose"] = source
        self.assertNotIn("network_mode", yaml.safe_load(to_compose(graph))["services"]["isolado"])

    def test_preflight_catches_missing_ipv6_or_invalid_gateway(self):
        self.engine.containers.list.return_value = []
        daemon = MagicMock()
        daemon.containers.return_value = []
        daemon.networks.return_value = []
        graph = {"version": 2, "nodes": [
            {"id": "net", "kind": "network", "name": "dual",
             "x": 10, "y": 10, "ipv6_subnet": "fd00::/64",
             "ipv6_gateway": "fdff::1"}], "edges": []}
        out = plan(graph, daemon)
        self.assertFalse(out["valid"])
        self.assertTrue(any("Gateway" in text for text in out["conflicts"]))


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.ping.return_value = True
        self.left = MagicMock()
        self.left.name = "api"
        self.left.status = "running"
        self.left.attrs = {"NetworkSettings": {"Networks": {"lab": {}}}}
        self.right = MagicMock()
        self.right.name = "db"
        self.right.status = "running"
        self.right.attrs = {"NetworkSettings": {"Networks": {"lab": {}}}}
        self.client.containers.get.side_effect = {
            "left": self.left, "right": self.right}.__getitem__

    def test_dns_success_and_missing_tool_status(self):
        with patch.object(diagnostic_service, "docker_service", DockerService(self.client)):
            self.left.exec_run.return_value = (0, b"172.18.0.3 db")
            result = diagnostic_service.service_probe("left", "right", "dns")
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["shared_networks"], ["lab"])
            self.left.exec_run.side_effect = RuntimeError("executable missing")
            result = diagnostic_service.service_probe("left", "right", "dns")
            self.assertEqual(result["status"], "unavailable")

    def test_refuses_wrong_port_or_network_unshared(self):
        with self.assertRaises(ValueError):
            diagnostic_service.service_probe("left", "right", "tcp", 99999)
        self.right.attrs["NetworkSettings"]["Networks"] = {"isolated": {}}
        with patch.object(diagnostic_service, "docker_service", DockerService(self.client)):
            result = diagnostic_service.service_probe("left", "right", "tcp", 80)
            self.assertEqual(result["status"], "not_run")
            self.left.exec_run.assert_not_called()


class FrontendAppearanceTests(unittest.TestCase):
    def test_theme_canvas_ide_and_diagnostics_are_wired_offline(self):
        base = Path(__file__).resolve().parents[1] / "apps" / "dockerflow"
        template = (base / "templates" / "studio.html").read_text("utf-8")
        style = (base / "static" / "css" / "studio.css").read_text("utf-8")
        spa = (base / "static" / "js" / "studio.js").read_text("utf-8")
        graph = (base / "static" / "js" / "graph.js").read_text("utf-8")
        for element in ("df-theme-toggle", "df-snap", "df-layout", "df-duplicate",
                        "df-graph-png", "df-graph-search", "df-network-diagnose",
                        "df-editor-lines", "df-editor-highlight-toggle"):
            self.assertIn('id="' + element + '"', template)
        self.assertIn('data-theme="dark"', style)
        self.assertIn('localStorage.setItem(appearanceKey,appearance)', spa)
        self.assertIn('service_probe', diagnostic_service.service_probe.__name__)
        self.assertIn('const selectedNodes=new Set()', graph)
        self.assertIn('function exportPng()', graph)
        self.assertIn('function autoLayout()', graph)


if __name__ == "__main__":
    unittest.main()
