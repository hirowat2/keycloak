"""Etapa 1: realm, role ADMIN, clients dos apps e uma role de acesso por app.

Segue as seções 1.1 a 1.7 e 3.1 do README_sso.md.
"""

import re
from dataclasses import dataclass

from .api import KeycloakAdmin, seg
from .plano import ATUALIZAR, CRIAR, OK, Plano, diferencas

ROLE_ADMIN = "ADMIN"

# Seções 1.2 a 1.5: SSL só para fora, sem cadastro nem "esqueci a senha" (a senha é do SSO),
# login com e-mail, português como padrão e bloqueio temporário contra força bruta.
CONFIG_REALM = {
    "sslRequired": "external",
    "registrationAllowed": False,
    "resetPasswordAllowed": False,
    "loginWithEmailAllowed": True,
    "internationalizationEnabled": True,
    "supportedLocales": ["pt-BR", "en"],
    "defaultLocale": "pt-BR",
    "bruteForceProtected": True,
    "permanentLockout": False,
    "maxTemporaryLockouts": 0,
}

# Clients que o Keycloak cria em todo realm; não são apps.
CLIENTS_PADRAO = {"account", "account-console", "admin-cli", "broker", "realm-management", "security-admin-console"}

NOME_VALIDO = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass
class App:
    client_id: str
    nome: str
    url: str
    # Os apps Django recebem o login em /oidc/callback/; o assistente (keycloak.js) volta para qualquer página.
    callback: str = "/oidc/callback/"

    def representacao(self) -> dict:
        url = self.url.rstrip("/")
        return {
            "clientId": self.client_id,
            "name": self.nome,
            "protocol": "openid-connect",
            "enabled": True,
            # Seção 1.7: client público, só Standard flow, PKCE S256
            "publicClient": True,
            "standardFlowEnabled": True,
            "implicitFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": False,
            "redirectUris": [f"{url}{self.callback}"],
            "webOrigins": [url],
            "attributes": {"pkce.code.challenge.method": "S256", "post.logout.redirect.uris": f"{url}/*"},
        }


def listar_realms(api: KeycloakAdmin) -> list[dict]:
    return api.get("", briefRepresentation="true") or []


def ler_realm(api: KeycloakAdmin, realm: str) -> dict | None:
    return api.get(f"/{seg(realm)}")


def clients_dos_apps(api: KeycloakAdmin, realm: str) -> list[dict]:
    return [
        c for c in api.get(f"/{seg(realm)}/clients") or []
        if c["clientId"] not in CLIENTS_PADRAO and not c["clientId"].endswith("-realm")
    ]


def ler_apps(api: KeycloakAdmin, realm: str) -> list[App]:
    """Apps já cadastrados (clients que não são do Keycloak), para preencher o formulário."""
    apps = []
    for c in clients_dos_apps(api, realm):
        url = (c.get("webOrigins") or [c.get("rootUrl") or ""])[0].rstrip("/")
        redirect = next(iter(c.get("redirectUris") or []), "")
        callback = redirect[len(url):] if url and redirect.startswith(url) else App.callback
        apps.append(App(c["clientId"], c.get("name") or c["clientId"], url, callback or App.callback))
    return apps


def garantir_role(api: KeycloakAdmin, plano: Plano, realm: str, nome: str, descricao: str) -> None:
    if api.get(f"/{seg(realm)}/roles/{seg(nome)}") is not None:
        plano.registrar(OK, "role", nome)
        return
    plano.registrar(
        CRIAR, "role", nome, descricao,
        lambda: api.post(f"/{seg(realm)}/roles", {"name": nome, "description": descricao}),
    )


def aplicar_realm(api: KeycloakAdmin, plano: Plano, realm: str, nome_exibicao: str) -> None:
    if not NOME_VALIDO.match(realm):
        raise ValueError("O nome do realm só pode ter minúsculas, números e hífen, sem espaço.")
    desejado = {**CONFIG_REALM, "displayName": nome_exibicao or realm, "enabled": True}
    atual = ler_realm(api, realm)
    if atual is None:
        plano.registrar(CRIAR, "realm", realm, nome_exibicao, lambda: api.post("", {"realm": realm, **desejado}))
    elif mudou := diferencas(atual, desejado):
        plano.registrar(
            ATUALIZAR, "realm", realm, ", ".join(mudou),
            lambda: api.put(f"/{seg(realm)}", {chave: desejado[chave] for chave in mudou}),
        )
    else:
        plano.registrar(OK, "realm", realm)
    if plano.simular and atual is None:
        # Realm ainda não existe: tudo o que depende dele seria criado.
        plano.registrar(CRIAR, "role", ROLE_ADMIN, "Administrador: vira superuser nos apps")
        return
    garantir_role(api, plano, realm, ROLE_ADMIN, "Administrador: vira superuser nos apps")


def aplicar_app(api: KeycloakAdmin, plano: Plano, realm: str, app: App, realm_existe: bool = True) -> None:
    desejado = app.representacao()
    if not realm_existe:
        plano.registrar(CRIAR, "client", app.client_id, app.url)
        plano.registrar(CRIAR, "role", app.client_id, f"Acesso ao {app.nome}")
        return
    atual = next(iter(api.get(f"/{seg(realm)}/clients", clientId=app.client_id) or []), None)
    if atual is None:
        plano.registrar(CRIAR, "client", app.client_id, app.url, lambda: api.post(f"/{seg(realm)}/clients", desejado))
    else:
        atributos = desejado.pop("attributes")
        mudou = diferencas(atual, desejado) + [f"attributes.{c}" for c in diferencas(atual.get("attributes", {}), atributos)]
        if mudou:
            novo = {**atual, **desejado, "attributes": {**atual.get("attributes", {}), **atributos}}
            plano.registrar(
                ATUALIZAR, "client", app.client_id, ", ".join(mudou),
                lambda: api.put(f"/{seg(realm)}/clients/{atual['id']}", novo),
            )
        else:
            plano.registrar(OK, "client", app.client_id)
    # Seção 3.1: uma role de acesso por app, com o mesmo nome do client (KEYCLOAK_REQUIRED_ROLE)
    garantir_role(api, plano, realm, app.client_id, f"Acesso ao {app.nome}")


def aplicar(api: KeycloakAdmin, realm: str, nome_exibicao: str, apps: list[App], simular: bool) -> Plano:
    plano = Plano(simular)
    existia = ler_realm(api, realm) is not None
    aplicar_realm(api, plano, realm, nome_exibicao)
    for app in apps:
        aplicar_app(api, plano, realm, app, realm_existe=existia or not simular)
    return plano
