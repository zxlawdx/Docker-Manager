"""DockerFlow Vela: interface independente do shell visual padrão."""
APP_TITLE = "DockerFlow"
APP_VERSION = "0.2.0"
APP_DESCRIPTION = "Docker Studio: editor de topologia, IDE e terminal embutido"
APP_AUTHOR = "zxlawdx"
ENTRY_ROUTE = "/"
WINDOW_WIDTH = 1550
WINDOW_HEIGHT = 930
LAYOUT = {"sidebar": False, "topbar": False, "theme": "light"}
DEBUG = False
API = {
    "enabled": True,
    "host": "127.0.0.1",  # Nunca expor controle do Docker na rede.
    "port": 8766,
    "auto_port": True,
    "server": "waitress",
    "workers": 6,
    "docs_enabled": False,
}
SHELL_MODE = "http"
STATIC_ROOT = "staticfiles"
