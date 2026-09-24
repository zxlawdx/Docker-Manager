"""Segurança de sessão da API local DockerFlow.

O token fica no HTML renderizado da janela, nunca em arquivos estáticos.
Não substitui isolamento do socket Docker ou autenticação multiusuário.
"""
import hmac
import secrets
from urllib.parse import urlsplit

TOKEN = secrets.token_urlsafe(32)


def validate(context):
    headers = {str(k).lower(): str(v) for k, v in context.get("headers", {}).items()}
    host = headers.get("host", "")
    try:
        parsed = urlsplit("http://" + host)
        if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError()
        # A instância usa porta dinâmica; compara origin com host exato.
        origin = headers.get("origin")
        if origin and origin.rstrip("/") != "http://" + host:
            raise ValueError()
        if headers.get("sec-fetch-site", "").lower() not in ("", "none", "same-origin"):
            raise ValueError()
        supplied = headers.get("x-dockerflow-token", "")
        if not hmac.compare_digest(supplied, TOKEN):
            raise ValueError()
    except ValueError as exc:
        raise PermissionError("Acesso negado à API local do DockerFlow") from exc
