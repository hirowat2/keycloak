"""Etapa 5: confere o realm contra o README_sso.md, consulta um usuário e exporta o que vale versionar."""

from dataclasses import dataclass

from .api import KeycloakAdmin, seg
from .grupos import ROLES_INTERNAS, ler_grupos
from .realm import CLIENTS_PADRAO, CONFIG_REALM, ROLE_ADMIN, clients_dos_apps
from .saml import MAPPER_ATRIBUTO, MAPPER_GRUPO, MAPPER_USERNAME, listar_provedores
from .plano import diferencas


@dataclass
class Verificacao:
    secao: str
    item: str
    ok: bool
    detalhe: str = ""
    referencia: str = ""


def auditar(api: KeycloakAdmin, realm: str) -> list[Verificacao]:
    lista: list[Verificacao] = []

    def conferir(secao, item, ok, detalhe="", referencia=""):
        lista.append(Verificacao(secao, item, bool(ok), detalhe, referencia))

    dados = api.get(f"/{seg(realm)}") or {}
    for chave in CONFIG_REALM:
        errado = diferencas(dados, {chave: CONFIG_REALM[chave]})
        conferir("Realm", chave, not errado, f"atual: {dados.get(chave)!r}, esperado: {CONFIG_REALM[chave]!r}" if errado else "", "1.2–1.5")
    frontend = dados.get("attributes", {}).get("frontendUrl")
    conferir("Realm", "Frontend URL vazia", not frontend, f"aponta para {frontend}" if frontend else "", "migração · host novo")

    roles = {r["name"] for r in api.get(f"/{seg(realm)}/roles") or []}
    conferir("Roles", f"role {ROLE_ADMIN}", ROLE_ADMIN in roles, "", "1.6")

    clients = clients_dos_apps(api, realm)
    conferir("Clients", "pelo menos um app cadastrado", clients, "", "1.7")
    for c in clients:
        atributos = c.get("attributes", {})
        problemas = [
            texto for texto, errado in [
                ("tem secret (Client authentication On)", not c.get("publicClient")),
                ("Require PKCE S256 desligado", atributos.get("pkce.code.challenge.method") != "S256"),
                ("Direct access grants ligado", c.get("directAccessGrantsEnabled")),
                ("Implicit flow ligado", c.get("implicitFlowEnabled")),
                ("sem Valid redirect URIs", not c.get("redirectUris")),
                ("redirect com curinga em todo o host", any(u.strip() in ("*", "/*") for u in c.get("redirectUris", []))),
            ] if errado
        ]
        conferir("Clients", c["clientId"], not problemas, "; ".join(problemas), "1.7")
        conferir("Roles", f"role de acesso {c['clientId']}", c["clientId"] in roles, "usada no KEYCLOAK_REQUIRED_ROLE do app", "3.1")

    grupos = ler_grupos(api, realm)
    conferir("Grupos", "pelo menos um grupo", grupos, "", "3.2")
    for nome, roles_grupo in grupos.items():
        conferir("Grupos", nome, roles_grupo, ", ".join(roles_grupo) or "grupo sem role não libera nada nos apps", "3.2")
    padrao = api.get(f"/{seg(realm)}/default-groups") or []
    conferir("Grupos", "sem Default groups", not padrao, ", ".join(g["name"] for g in padrao), "3.2")

    provedores = listar_provedores(api, realm)
    conferir("SSO", "provedor SAML cadastrado", provedores, "", "2.3")
    for p in provedores:
        config = p.get("config", {})
        problemas = [
            texto for texto, errado in [
                ("Trust Email desligado", not p.get("trustEmail")),
                ("Sync mode diferente de Force", config.get("syncMode") != "FORCE"),
                ("Want Assertions signed desligado", config.get("wantAssertionsSigned") != "true"),
                ("Validate Signatures desligado", config.get("validateSignature") != "true"),
            ] if errado
        ]
        conferir("SSO", p["alias"], not problemas, "; ".join(problemas), "2.3")
        mappers = api.get(f"/{seg(realm)}/identity-provider/instances/{seg(p['alias'])}/mappers") or []
        campos = {m.get("config", {}).get("user.attribute") for m in mappers if m.get("identityProviderMapper") == MAPPER_ATRIBUTO}
        faltam = {"email", "firstName", "lastName"} - campos
        conferir("SSO", f"{p['alias']}: mappers de e-mail e nome", not faltam, f"faltam {', '.join(sorted(faltam))}" if faltam else "", "2.4")
        conferir("SSO", f"{p['alias']}: mapper de username", any(m.get("identityProviderMapper") == MAPPER_USERNAME for m in mappers), "", "2.4")
        mapeados = {m.get("config", {}).get("group", "").lstrip("/") for m in mappers if m.get("identityProviderMapper") == MAPPER_GRUPO}
        sem_mapper = [g for g in grupos if g not in mapeados]
        conferir("SSO", f"{p['alias']}: grupos com mapper", not sem_mapper,
                 f"sem mapper: {', '.join(sem_mapper)} (membros só à mão)" if sem_mapper else "", "4.4")
    return lista


def consultar_usuario(api: KeycloakAdmin, realm: str, busca: str) -> list[dict]:
    """Seções 3.3 e 4.5: grupos, roles efetivas (as que vão no token) e vínculo com o SSO."""
    usuarios = []
    for u in api.get(f"/{seg(realm)}/users", search=busca, max="10") or []:
        base = f"/{seg(realm)}/users/{u['id']}"
        efetivas = [r["name"] for r in api.get(f"{base}/role-mappings/realm/composite") or []]
        diretas = [r["name"] for r in api.get(f"{base}/role-mappings/realm") or []]
        usuarios.append({
            **u,
            "grupos": [g["name"] for g in api.get(f"{base}/groups") or []],
            "roles": sorted(r for r in efetivas if r not in ROLES_INTERNAS and not r.startswith("default-roles-")),
            "roles_diretas": sorted(r for r in diretas if r not in ROLES_INTERNAS and not r.startswith("default-roles-")),
            "provedores": [f"{v['identityProvider']} ({v.get('userName', '')})" for v in api.get(f"{base}/federated-identity") or []],
        })
    return usuarios


def env_dos_apps(host: str, interno: str, realm: str, client_ids: list[str]) -> dict[str, str]:
    """Trecho do .env de cada app (seções 1.8 e 3.1)."""
    return {
        cid: "\n".join([
            f"KEYCLOAK_HOST={host.rstrip('/')}/",
            f"KEYCLOAK_INTERNAL_URL={interno.rstrip('/')}",
            f"KEYCLOAK_REALM={realm}",
            f"KEYCLOAK_CLIENT_ID={cid}",
            f"KEYCLOAK_REQUIRED_ROLE={cid}",
        ])
        for cid in client_ids
    }


def _sem_ids(valor):
    if isinstance(valor, dict):
        return {k: _sem_ids(v) for k, v in valor.items() if k not in ("id", "containerId", "internalId", "secret")}
    if isinstance(valor, list):
        return [_sem_ids(v) for v in valor]
    return valor


def exportar(api: KeycloakAdmin, realm: str) -> dict:
    """JSON versionável: configurações, roles, grupos, clients dos apps, provedores e mappers.

    Sem usuários, hashes de senha, secrets nem ``components`` (chaves privadas),
    como pede a seção "Versionando o que foi feito no console".
    """
    completo = api.post(f"/{seg(realm)}/partial-export", params={"exportGroupsAndRoles": "true", "exportClients": "true"}).json()
    roles = [
        r for r in completo.get("roles", {}).get("realm", [])
        if r["name"] not in ROLES_INTERNAS and not r["name"].startswith("default-roles-")
    ]
    clients = [c for c in completo.get("clients", []) if c["clientId"] not in CLIENTS_PADRAO and not c["clientId"].endswith("-realm")]
    saida = {"realm": realm, "displayName": completo.get("displayName"), "enabled": True}
    saida.update({chave: completo.get(chave) for chave in CONFIG_REALM})
    saida.update({
        "roles": {"realm": roles},
        "groups": completo.get("groups", []),
        "clients": clients,
        "identityProviders": completo.get("identityProviders", []),
        "identityProviderMappers": completo.get("identityProviderMappers", []),
    })
    return _sem_ids(saida)
