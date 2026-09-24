from vela.template_engine.engine import render_template
from apps.dockerflow.services.security_service import TOKEN

def studio_view(params):
    return render_template(
        "apps/dockerflow/templates/studio.html",
        context={"app_name": "DockerFlow", "api_token": TOKEN},
        router=params["router"],
    )
