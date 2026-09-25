"""Catálogo offline, declarativo e sem execução automática para DockerFlow."""
from copy import deepcopy
import yaml


def _service(title, category, description, services, *, networks=None, volumes=None, notes=""):
    document = {"services": services}
    if networks:
        document["networks"] = networks
    if volumes:
        document["volumes"] = volumes
    return {"title": title, "category": category, "description": description,
            "compose": document, "notes": notes}


LOCAL = "127.0.0.1:"
PASSWORD = "${PASSWORD:?Defina PASSWORD no ambiente antes de executar}"
CATALOG = {
    "nginx": _service("Nginx · servidor web", "Web", "Servidor HTTP local; edite a configuração antes da produção.",
        {"web": {"image": "nginx:alpine", "ports": [LOCAL + "8080:80"]}}),
    "caddy": _service("Caddy · servidor web", "Web", "Servidor web com diretório local.",
        {"web": {"image": "caddy:2", "ports": [LOCAL + "8080:80"],
                 "volumes": ["./site:/usr/share/caddy:ro"]}}, notes="Crie a pasta site no workspace Compose."),
    "python": _service("Python · serviço de teste", "Desenvolvimento", "Servidor HTTP descartável para laboratório.",
        {"python": {"image": "python:3.12-slim", "working_dir": "/app",
                    "command": ["python", "-m", "http.server", "8000"],
                    "ports": [LOCAL + "8000:8000"]}}, notes="Template demonstrativo, sem autenticação."),
    "node": _service("Node.js · ambiente", "Desenvolvimento", "Runtime Node com volume de projeto.",
        {"node": {"image": "node:22-alpine", "working_dir": "/app",
                  "command": ["node", "--version"], "volumes": ["./app:/app:ro"]}},
        notes="Troque command pela inicialização real do projeto."),
    "postgres": _service("PostgreSQL · banco", "Banco de dados", "Banco persistente acessível somente no host.",
        {"postgres": {"image": "postgres:16-alpine",
                      "environment": {"POSTGRES_PASSWORD": "${POSTGRES_PASSWORD:?Defina POSTGRES_PASSWORD}",
                                      "POSTGRES_DB": "app"},
                      "volumes": ["pg_data:/var/lib/postgresql/data"],
                      "ports": [LOCAL + "5432:5432"]}}, volumes={"pg_data": {}}),
    "mysql": _service("MySQL · banco", "Banco de dados", "MySQL com armazenamento persistente.",
        {"mysql": {"image": "mysql:8.4", "environment": {
            "MYSQL_ROOT_PASSWORD": "${MYSQL_ROOT_PASSWORD:?Defina MYSQL_ROOT_PASSWORD}",
            "MYSQL_DATABASE": "app"}, "volumes": ["mysql_data:/var/lib/mysql"],
            "ports": [LOCAL + "3306:3306"]}}, volumes={"mysql_data": {}}),
    "mariadb": _service("MariaDB · banco", "Banco de dados", "MariaDB com armazenamento persistente.",
        {"mariadb": {"image": "mariadb:11", "environment": {
            "MARIADB_ROOT_PASSWORD": "${MARIADB_ROOT_PASSWORD:?Defina MARIADB_ROOT_PASSWORD}",
            "MARIADB_DATABASE": "app"}, "volumes": ["mariadb_data:/var/lib/mysql"],
            "ports": [LOCAL + "3306:3306"]}}, volumes={"mariadb_data": {}}),
    "mongo": _service("MongoDB · banco", "Banco de dados", "MongoDB com credenciais obrigatórias.",
        {"mongodb": {"image": "mongo:7", "environment": {
            "MONGO_INITDB_ROOT_USERNAME": "${MONGO_USER:?Defina MONGO_USER}",
            "MONGO_INITDB_ROOT_PASSWORD": "${MONGO_PASSWORD:?Defina MONGO_PASSWORD}"},
            "volumes": ["mongo_data:/data/db"], "ports": [LOCAL + "27017:27017"]}},
        volumes={"mongo_data": {}}),
    "redis": _service("Redis · cache", "Mensageria e cache", "Cache local com persistência RDB.",
        {"redis": {"image": "redis:7-alpine", "command": ["redis-server", "--appendonly", "yes"],
                   "volumes": ["redis_data:/data"], "ports": [LOCAL + "6379:6379"]}},
        volumes={"redis_data": {}}, notes="Configure autenticação/ACL antes de publicar a porta."),
    "rabbitmq": _service("RabbitMQ · filas", "Mensageria e cache", "Broker e painel web locais.",
        {"rabbitmq": {"image": "rabbitmq:3-management", "environment": {
            "RABBITMQ_DEFAULT_USER": "${RABBIT_USER:?Defina RABBIT_USER}",
            "RABBITMQ_DEFAULT_PASS": "${RABBIT_PASSWORD:?Defina RABBIT_PASSWORD}"},
            "ports": [LOCAL + "5672:5672", LOCAL + "15672:15672"],
            "volumes": ["rabbit_data:/var/lib/rabbitmq"]}}, volumes={"rabbit_data": {}}),
    "grafana": _service("Grafana · dashboard", "Observabilidade", "Dashboard com senha exigida.",
        {"grafana": {"image": "grafana/grafana:latest", "environment": {
            "GF_SECURITY_ADMIN_PASSWORD": "${GRAFANA_PASSWORD:?Defina GRAFANA_PASSWORD}"},
            "ports": [LOCAL + "3000:3000"], "volumes": ["grafana_data:/var/lib/grafana"]}},
        volumes={"grafana_data": {}}),
    "prometheus": _service("Prometheus · métricas", "Observabilidade", "Coletor básico local; personalize alvos.",
        {"prometheus": {"image": "prom/prometheus:latest",
                        "ports": [LOCAL + "9090:9090"],
                        "volumes": ["prom_data:/prometheus"]}}, volumes={"prom_data": {}}),
    "registry": _service("Registry · imagens", "Infraestrutura", "Registro local de imagens para desenvolvimento.",
        {"registry": {"image": "registry:2", "ports": [LOCAL + "5000:5000"],
                      "volumes": ["registry_data:/var/lib/registry"]}},
        volumes={"registry_data": {}}, notes="Não tem autenticação: mantenha exposto somente em loopback."),
    "ollama": _service("Ollama · LLM local", "IA", "Runtime local de modelos; baixar modelos requer ação separada.",
        {"ollama": {"image": "ollama/ollama:latest", "ports": [LOCAL + "11434:11434"],
                    "volumes": ["ollama_data:/root/.ollama"]}}, volumes={"ollama_data": {}}),
    "stack-web": _service("Stack Web · Nginx + PostgreSQL + Redis", "Stacks YAML",
        "Base local com rede pública e backend privado.",
        {"web": {"image": "nginx:alpine", "ports": [LOCAL + "8080:80"], "networks": ["front"]},
         "api": {"image": "python:3.12-slim", "command": ["python", "-m", "http.server", "8000"],
                 "networks": ["front", "data"]},
         "database": {"image": "postgres:16-alpine", "environment": {
             "POSTGRES_PASSWORD": "${POSTGRES_PASSWORD:?Defina POSTGRES_PASSWORD}"},
             "volumes": ["pg_data:/var/lib/postgresql/data"], "networks": ["data"]},
         "cache": {"image": "redis:7-alpine", "networks": ["data"]}},
        networks={"front": {}, "data": {"internal": True}}, volumes={"pg_data": {}},
        notes="Exemplo estrutural: configure reverse proxy, aplicação, credenciais e firewall antes de usar."),
    "stack-observability": _service("Stack · Prometheus + Grafana", "Stacks YAML",
        "Métricas e visualização numa rede local privada.",
        {"prometheus": {"image": "prom/prometheus:latest", "networks": ["monitor"],
                        "ports": [LOCAL + "9090:9090"]},
         "grafana": {"image": "grafana/grafana:latest", "networks": ["monitor"],
                     "environment": {"GF_SECURITY_ADMIN_PASSWORD":
                                     "${GRAFANA_PASSWORD:?Defina GRAFANA_PASSWORD}"},
                     "ports": [LOCAL + "3000:3000"],
                     "volumes": ["grafana_data:/var/lib/grafana"]}},
        networks={"monitor": {}}, volumes={"grafana_data": {}},
        notes="Configure uma fonte Prometheus em Grafana manualmente."),
    "stack-wordpress": _service("Stack · WordPress + MariaDB", "Stacks YAML",
        "Blog local com banco de dados privado.",
        {"wordpress": {"image": "wordpress:php8.3-apache",
                       "depends_on": ["db"], "networks": ["public", "private"],
                       "environment": {"WORDPRESS_DB_HOST": "db",
                                       "WORDPRESS_DB_USER": "wordpress",
                                       "WORDPRESS_DB_PASSWORD":
                                           "${WP_DB_PASSWORD:?Defina WP_DB_PASSWORD}",
                                       "WORDPRESS_DB_NAME": "wordpress"},
                       "ports": [LOCAL + "8080:80"], "volumes": ["wp_files:/var/www/html"]},
         "db": {"image": "mariadb:11", "networks": ["private"],
                "environment": {
                    "MARIADB_DATABASE": "wordpress",
                    "MARIADB_USER": "wordpress",
                    "MARIADB_PASSWORD": "${WP_DB_PASSWORD:?Defina WP_DB_PASSWORD}",
                    "MARIADB_ROOT_PASSWORD": "${DB_ROOT_PASSWORD:?Defina DB_ROOT_PASSWORD}"},
                "volumes": ["db_files:/var/lib/mysql"]}},
        networks={"public": {}, "private": {"internal": True}},
        volumes={"wp_files": {}, "db_files": {}}),
}


def list_templates():
    """Retorna apenas metadados; não precisa de Docker Engine nem expõe env."""
    return [{"id": key, "title": item["title"], "category": item["category"],
             "description": item["description"], "notes": item["notes"]}
            for key, item in CATALOG.items()]


def render_template(identifier):
    """IDs são constantes locais: não aceita URL nem paths fornecidos pelo cliente."""
    if not isinstance(identifier, str) or identifier not in CATALOG:
        raise ValueError("Template não encontrado")
    item = CATALOG[identifier]
    # deep copy evita mutações em parâmetros compartilhados entre solicitações.
    content = yaml.safe_dump(deepcopy(item["compose"]), allow_unicode=True,
                             sort_keys=False, default_flow_style=False)
    return {"id": identifier, "title": item["title"], "notes": item["notes"],
            "content": "# DockerFlow · " + item["title"] + "\n" + content}
