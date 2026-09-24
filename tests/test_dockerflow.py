"""Testes sem Docker daemon: jamais criam recursos de verdade no CI."""
import unittest
from unittest.mock import MagicMock
from apps.dockerflow.services.docker_service import DockerService
from apps.dockerflow.services.graph_service import to_compose


class DockerFacadeTests(unittest.TestCase):
    def setUp(self):
        self.engine=MagicMock()
        self.engine.ping.return_value=True
        self.service=DockerService(client=self.engine)

    def test_offline_summary_remains_usable(self):
        self.engine.ping.side_effect=RuntimeError("daemon offline")
        result=self.service.overview()
        self.assertFalse(result["online"])
        self.assertIn("offline",result["message"])

    def test_network_membership_is_reported(self):
        network=MagicMock()
        network.id="net-123"
        network.name="laboratorio"
        network.attrs={"Driver":"bridge","Scope":"local","Containers":{
            "container-01":{"Name":"api","IPv4Address":"172.18.0.3/16"}}}
        self.engine.networks.list.return_value=[network]
        result=self.service.networks()
        self.assertEqual(result[0]["containers"][0]["name"],"api")
        self.assertEqual(result[0]["driver"],"bridge")

    def test_connect_is_idempotent(self):
        network=MagicMock()
        network.name="laboratorio"
        network.attrs={"Containers":{"container-01":{"Name":"api"}}}
        container=MagicMock();container.id="container-01"
        self.engine.networks.get.return_value=network
        self.engine.containers.get.return_value=container
        self.service.network_action("connect",{"network":"laboratorio","container":"api"})
        network.connect.assert_not_called()

    def test_default_network_cannot_be_removed(self):
        network=MagicMock();network.name="bridge"
        self.engine.networks.get.return_value=network
        with self.assertRaisesRegex(ValueError,"protegida"):
            self.service.network_action("remove",{"network":"bridge"})
        network.remove.assert_not_called()

    def test_container_create_maps_ports(self):
        c=MagicMock();c.id="abc"
        self.engine.containers.run.return_value=c
        result=self.service.create_container({"image":"nginx:alpine","name":"web",
            "ports":[{"host":"8080","container":"80"}]})
        self.assertEqual(result["id"],"abc")
        self.assertEqual(self.engine.containers.run.call_args.kwargs["ports"],{"80/tcp":8080})

    def test_inspect_does_not_expose_env_password(self):
        container=MagicMock()
        container.id="abc";container.name="test"
        container.attrs={"Config":{"Env":["PASSWORD=SUPER_SECRET"]},
                         "NetworkSettings":{"Networks":{}},"State":{},"HostConfig":{}}
        self.engine.containers.get.return_value=container
        self.assertNotIn("SUPER_SECRET",str(self.service.inspect("abc")))


class GraphTests(unittest.TestCase):
    def test_two_containers_share_a_bridge_network(self):
        g={"nodes":[{"id":"a","kind":"container","name":"API","image":"python:3.12"},
                    {"id":"b","kind":"container","name":"Banco","image":"postgres:16"},
                    {"id":"n","kind":"network","name":"interna","existing":False}],
           "edges":[{"source":"n","target":"a"},{"source":"n","target":"b"}]}
        result=to_compose(g)
        self.assertIn("interna",result)
        self.assertIn("python:3.12",result)
        self.assertIn("postgres:16",result)
        self.assertIn("networks:",result)

    def test_existing_network_is_external(self):
        g={"nodes":[{"id":"api","kind":"container","name":"web","image":"nginx:alpine"},
                    {"id":"rede","kind":"network","name":"lab","existing":True}],
           "edges":[{"source":"rede","target":"api"}]}
        self.assertIn("external: true",to_compose(g))


    def test_canvas_ports_and_environment_export_to_compose(self):
        import yaml
        graph = {"nodes": [
            {"id": "api", "kind": "container", "name": "api",
             "image": "nginx:alpine", "host_port": "8080",
             "container_port": "80", "env_text": '{"MODE":"dev","COUNT":2}'}]}
        result = yaml.safe_load(to_compose(graph))
        service = result["services"]["api"]
        self.assertEqual(service["ports"], ["8080:80"])
        self.assertEqual(service["environment"], {"MODE": "dev", "COUNT": "2"})

    def test_duplicate_service_name_rejected(self):
        g={"nodes":[{"id":"1","kind":"container","name":"web","image":"nginx"},
                    {"id":"2","kind":"container","name":"web","image":"nginx"}]}
        with self.assertRaisesRegex(ValueError,"duplicados"):
            to_compose(g)


if __name__ == "__main__":
    unittest.main()

class SecurityAndProjectTests(unittest.TestCase):
    def test_local_api_denies_requests_without_matching_token(self):
        from apps.dockerflow.services.security_service import validate, TOKEN
        valid = {"headers": {"Host": "127.0.0.1:8766", "X-DockerFlow-Token": TOKEN}}
        validate(valid)
        for headers in (
            {"Host": "evil.invalid", "X-DockerFlow-Token": TOKEN},
            {"Host": "127.0.0.1:8766", "X-DockerFlow-Token": "wrong"},
            {"Host": "127.0.0.1:8766", "Origin": "http://evil.invalid", "X-DockerFlow-Token": TOKEN}
        ):
            with self.assertRaises(PermissionError):
                validate({"headers": headers})

    def test_saved_graph_is_not_treated_as_verified_docker_resources(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from apps.dockerflow.services import graph_project_service as store
        graph = {"version": 2, "nodes": [
            {"id": "n", "kind": "network", "name": "lab", "x": 30, "y": 50}],
            "edges": []}
        with tempfile.TemporaryDirectory() as tmp, patch.object(store, "BASE", Path(tmp)):
            store.save("lab", graph)
            self.assertEqual(store.load("lab")["nodes"][0]["name"], "lab")
            with self.assertRaises(ValueError):
                store.save("../escape", graph)

    def test_from_compose_creates_drawable_network_edges(self):
        from apps.dockerflow.services.graph_service import from_compose
        graph = from_compose("services:\n  api:\n    image: nginx:alpine\n    networks: [internal]\nnetworks:\n  internal: {}\n")
        self.assertEqual(len(graph["edges"]), 1)
        self.assertFalse(graph["nodes"][0]["existing"])

    def test_advanced_network_ipam_requires_gateway_inside_subnet(self):
        engine = MagicMock()
        engine.ping.return_value = True
        svc = DockerService(engine)
        with self.assertRaisesRegex(ValueError, "fora da sub-rede"):
            svc.network_action("create", {"name": "lab", "subnet": "172.29.0.0/24",
                                           "gateway": "172.30.0.1"})

class MonitoringAndReportTests(unittest.TestCase):
    def test_cpu_and_memory_sample(self):
        from apps.dockerflow.services.monitor_service import _snapshot
        stats = {"cpu_stats": {"cpu_usage": {"total_usage": 220}, "system_cpu_usage": 1200, "online_cpus": 2},
                 "precpu_stats": {"cpu_usage": {"total_usage": 120}, "system_cpu_usage": 1000},
                 "memory_stats": {"usage": 1200, "limit": 4000, "stats": {"cache": 200}},
                 "networks": {"eth0": {"rx_bytes": 20, "tx_bytes": 30}}}
        result = _snapshot(stats)
        self.assertEqual(result["cpu_percent"], 100)
        self.assertEqual(result["memory_bytes"], 1000)
        self.assertEqual(result["network_tx"], 30)

    def test_report_excludes_environment_secrets(self):
        from apps.dockerflow.services.graph_service import report
        doc = {"nodes": [{"id": "1", "name": "api", "kind": "container",
                           "image": "python:3.12", "env_text": '{"SECRET":"private"}'}],
               "edges": []}
        output = report(doc)
        self.assertIn("api", output)
        self.assertNotIn("private", output)

    def test_compose_preserves_unedited_advanced_fields(self):
        import yaml
        from apps.dockerflow.services.graph_service import from_compose
        source = "services:\n  api:\n    image: nginx:alpine\n    healthcheck:\n      test: ['CMD', 'true']\n"
        graph = from_compose(source)
        result = yaml.safe_load(to_compose(graph))
        self.assertEqual(result["services"]["api"]["healthcheck"]["test"], ["CMD", "true"])

class GraphPlanTests(unittest.TestCase):
    def test_reject_stale_identity(self):
        from apps.dockerflow.services.graph_service import plan
        daemon=MagicMock()
        daemon.containers.return_value=[{"id":"real-id","name":"web","ports":{}}]
        daemon.networks.return_value=[]
        graph={"version":2,"nodes":[{"id":"node","name":"web","kind":"container",
               "existing":True,"dockerId":"stale-id","x":10,"y":10}],"edges":[]}
        result=plan(graph,daemon)
        self.assertFalse(result["valid"])
        self.assertIn("recriado",result["conflicts"][0])

    def test_preflight_detects_occupied_port(self):
        from apps.dockerflow.services.graph_service import plan
        daemon=MagicMock()
        daemon.containers.return_value=[{"id":"live","name":"another",
                     "ports":{"80/tcp":[{"HostPort":"8080","HostIp":"0.0.0.0"}]}}]
        daemon.networks.return_value=[]
        graph={"version":2,"nodes":[{"id":"new","name":"web","kind":"container",
               "image":"nginx:alpine","host_port":"8080","x":10,"y":10}],
               "edges":[]}
        result=plan(graph,daemon)
        self.assertFalse(result["valid"])
        self.assertIn("ocupada",result["conflicts"][0])
