"""Depois de migrar (seção 2 do README_migracao_vm.md): host novo e usuários sem e-mail ou nome."""

from .api import KeycloakAdmin, seg
from .plano import ATUALIZAR, OK, REMOVER, Plano
from .realm import clients_dos_apps

CAMPOS_URL = ("rootUrl", "baseUrl", "adminUrl")


def _trocar(valor: str, antigo: str, novo: str) -> str:
    return valor.replace(antigo, novo) if isinstance(valor, str) else valor


def trocar_host(api: KeycloakAdmin, realm: str, antigo: str, novo: str, simular: bool) -> Plano:
    """a) apaga a Frontend URL do realm; b) troca o host antigo nas URLs dos clients."""
    plano = Plano(simular)
    antigo, novo = antigo.strip().rstrip("/"), novo.strip().rstrip("/")
    if not antigo or not novo or antigo == novo:
        raise ValueError("Informe o host antigo e o novo (ex.: https://sso.vm-antiga.local e https://keycloak.actionstat.app).")

    dados = api.get(f"/{seg(realm)}") or {}
    frontend = dados.get("attributes", {}).get("frontendUrl")
    if frontend:
        plano.registrar(
            REMOVER, "Frontend URL", realm, frontend,
            lambda: api.put(f"/{seg(realm)}", {"attributes": {**dados["attributes"], "frontendUrl": ""}}),
        )
    else:
        plano.registrar(OK, "Frontend URL", realm, "vazia")

    for c in clients_dos_apps(api, realm):
        novo_c = {
            **c,
            "redirectUris": [_trocar(u, antigo, novo) for u in c.get("redirectUris", [])],
            "webOrigins": [_trocar(u, antigo, novo) for u in c.get("webOrigins", [])],
            "attributes": {k: _trocar(v, antigo, novo) for k, v in c.get("attributes", {}).items()},
            **{campo: _trocar(c.get(campo), antigo, novo) for campo in CAMPOS_URL if c.get(campo)},
        }
        mudou = [k for k in ("redirectUris", "webOrigins", "attributes", *CAMPOS_URL) if novo_c.get(k) != c.get(k)]
        if mudou:
            plano.registrar(ATUALIZAR, "client", c["clientId"], ", ".join(mudou),
                            lambda c=c, novo_c=novo_c: api.put(f"/{seg(realm)}/clients/{c['id']}", novo_c))
        else:
            plano.registrar(OK, "client", c["clientId"])
    return plano


def usuarios_incompletos(api: KeycloakAdmin, realm: str, limite: int = 2000) -> list[dict]:
    """Usuários sem e-mail, nome ou sobrenome: no 1º login veem a tela de completar o cadastro,
    e fluxos sem tela falham com "Account is not fully set up"."""
    faltando, inicio, pagina = [], 0, 100
    while inicio < limite:
        lote = api.get(f"/{seg(realm)}/users", first=str(inicio), max=str(pagina), briefRepresentation="true") or []
        for u in lote:
            campos = [rotulo for chave, rotulo in (("email", "e-mail"), ("firstName", "nome"), ("lastName", "sobrenome")) if not u.get(chave)]
            if campos:
                faltando.append({**u, "faltam": campos})
        if len(lote) < pagina:
            break
        inicio += pagina
    return faltando
