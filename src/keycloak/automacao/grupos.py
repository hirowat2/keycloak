"""Etapa 2: grupos do Keycloak e as roles de realm de cada um (seções 3.1 e 3.2 do README_sso.md).

As roles vão sempre para grupos, nunca para usuários: assim toda permissão
aparece em Groups e acompanha o SSO.
"""

from .api import KeycloakAdmin, seg
from .plano import ATUALIZAR, CRIAR, OK, REMOVER, Plano
from .realm import ROLE_ADMIN

# Roles que o Keycloak cria sozinho; não dão acesso a app nenhum.
ROLES_INTERNAS = ("offline_access", "uma_authorization")


def roles_do_realm(api: KeycloakAdmin, realm: str) -> list[str]:
    nomes = [r["name"] for r in api.get(f"/{seg(realm)}/roles") or []]
    return sorted(
        (n for n in nomes if n not in ROLES_INTERNAS and not n.startswith("default-roles-")),
        key=lambda n: (n != ROLE_ADMIN, n),
    )


def _grupo(api: KeycloakAdmin, realm: str, nome: str) -> dict | None:
    encontrados = api.get(f"/{seg(realm)}/groups", search=nome, exact="true", briefRepresentation="true") or []
    return next((g for g in encontrados if g["name"] == nome), None)


def _roles_do_grupo(api: KeycloakAdmin, realm: str, grupo_id: str) -> list[str]:
    return [r["name"] for r in api.get(f"/{seg(realm)}/groups/{grupo_id}/role-mappings/realm") or []]


def ler_grupos(api: KeycloakAdmin, realm: str) -> dict[str, list[str]]:
    """Grupos do primeiro nível e as roles de realm de cada um."""
    grupos = api.get(f"/{seg(realm)}/groups", briefRepresentation="true", max="1000") or []
    return {g["name"]: sorted(_roles_do_grupo(api, realm, g["id"])) for g in sorted(grupos, key=lambda g: g["name"])}


def estrutura_sugerida(prefixo: str, apps: list[str]) -> dict[str, list[str]]:
    """Tabela da seção 3.2: um grupo de admins com todas as roles e um grupo por app."""
    sugestao = {f"{prefixo}-admins": [ROLE_ADMIN, *apps]}
    sugestao.update({f"{prefixo}-{app}": [app] for app in apps})
    return sugestao


def aplicar(api: KeycloakAdmin, realm: str, grupos: dict[str, list[str]], simular: bool) -> Plano:
    plano = Plano(simular)
    representacoes = {r["name"]: r for r in api.get(f"/{seg(realm)}/roles") or []}
    for nome, roles in grupos.items():
        faltam = sorted(set(roles) - set(representacoes))
        if faltam:
            raise ValueError(f"As roles {', '.join(faltam)} não existem no realm {realm}. Crie-as na etapa 1.")
        grupo = _grupo(api, realm, nome)
        criado: dict = {}
        if grupo is None:
            def criar(nome=nome):
                resposta = api.post(f"/{seg(realm)}/groups", {"name": nome})
                criado["id"] = resposta.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
            plano.registrar(CRIAR, "grupo", nome, "", criar)
            atuais: list[str] = []
        else:
            plano.registrar(OK, "grupo", nome)
            criado["id"] = grupo["id"]
            atuais = _roles_do_grupo(api, realm, grupo["id"])

        adicionar = [representacoes[r] for r in sorted(set(roles) - set(atuais))]
        remover = [representacoes[r] for r in sorted(set(atuais) - set(roles)) if r in representacoes]
        caminho = lambda: f"/{seg(realm)}/groups/{criado['id']}/role-mappings/realm"  # noqa: E731 (id só existe depois de criar)
        if adicionar:
            plano.registrar(
                ATUALIZAR, "roles do grupo", nome, "+ " + ", ".join(r["name"] for r in adicionar),
                lambda adicionar=adicionar, caminho=caminho: api.post(caminho(), adicionar),
            )
        if remover:
            plano.registrar(
                REMOVER, "roles do grupo", nome, "− " + ", ".join(r["name"] for r in remover),
                lambda remover=remover, caminho=caminho: api.delete(caminho(), remover),
            )
    return plano
