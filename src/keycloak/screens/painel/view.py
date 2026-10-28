"""Painel: os realms do Keycloak e o andamento das etapas do realm ativo."""
from typing import Any

from keycloak.automacao.api import seg, url_publica
from keycloak.automacao.grupos import ler_grupos
from keycloak.automacao.realm import ROLE_ADMIN, clients_dos_apps
from keycloak.automacao.saml import listar_provedores, ler_mapeamento
from keycloak.automacao.web import api, com_realm
from keycloak.models import Aplicacao


def _etapas(cliente, realm: str) -> list[dict]:
    apps = clients_dos_apps(cliente, realm)
    tem_admin = cliente.get(f"/{seg(realm)}/roles/{ROLE_ADMIN}") is not None
    grupos = ler_grupos(cliente, realm)
    provedores = listar_provedores(cliente, realm)
    mapeados = ler_mapeamento(cliente, realm, provedores[0]["alias"]) if provedores else {}
    sem_mapper = [g for g in grupos if g not in mapeados]
    return [
        {"numero": 1, "titulo": "Realm e apps", "href": "/app/realm/", "feito": tem_admin and bool(apps),
         "resumo": f"{len(apps)} app(s): {', '.join(c['clientId'] for c in apps)}" if apps else "nenhum app cadastrado"},
        {"numero": 2, "titulo": "Grupos e roles", "href": "/app/grupos/", "feito": bool(grupos) and all(grupos.values()),
         "resumo": f"{len(grupos)} grupo(s)" if grupos else "nenhum grupo"},
        {"numero": 3, "titulo": "SSO corporativo", "href": "/app/sso/", "feito": bool(provedores),
         "resumo": ", ".join(p["alias"] for p in provedores) or "nenhum provedor SAML"},
        {"numero": 4, "titulo": "Grupos do SSO", "href": "/app/mapeamento/", "feito": bool(provedores and grupos and not sem_mapper),
         "resumo": f"sem mapper: {', '.join(sem_mapper)}" if provedores and sem_mapper else (f"{len(mapeados)} grupo(s) mapeado(s)" if provedores else "depende da etapa 3")},
    ]


@com_realm(exige_realm=False)
def view(context, request, realm) -> dict[str, Any]:
    cliente = api()
    resumo = [
        {
            "realm": nome,
            "apps": len(clients_dos_apps(cliente, nome)),
            "grupos": len(cliente.get(f"/{seg(nome)}/groups", briefRepresentation="true") or []),
            "provedores": len(listar_provedores(cliente, nome)),
        }
        for nome in context["realms"]
    ]
    context.update(
        {
            "servidor": url_publica() or cliente.url,
            "versao": cliente.versao(),
            "resumo": resumo,
            "etapas": _etapas(cliente, realm) if realm else [],
            "recentes": Aplicacao.objects.select_related("usuario")[:5],
        }
    )
    return {"request": request, "context": context}
