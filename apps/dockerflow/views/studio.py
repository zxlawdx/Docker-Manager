from vela.template_engine.engine import render_template

def studio_view(params):
    return render_template(
        "apps/dockerflow/templates/studio.html",
        context={"app_name": "DockerFlow"},
        router=params["router"],
    )
