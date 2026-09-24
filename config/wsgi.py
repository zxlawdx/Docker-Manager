"""Boot do app: as rotas Vela substituem a camada gRPC, sem processo extra."""
from vela.core.app import VelaApp

def run():
    app = VelaApp(settings_module="config.settings")
    app.register_app("apps.dockerflow")
    app.run()
