from .studio import studio_view

def register_routes(router):
    router.add("/", studio_view, title="DockerFlow Studio", name="studio",
               layout="blank", show_in_sidebar=False)
