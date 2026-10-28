"""Etapa 5: checklist do realm contra o README_sso.md, roles de um usuário, .env dos apps e o JSON versionável."""
import json
from itertools import groupby
from typing import Any

from django.http import HttpResponse

from keycloak.automacao import conferir as servico
from keycloak.automacao.api import url_interna, url_publica
from keycloak.automacao.realm import clients_dos_apps
from keycloak.automacao.web import api, com_realm


@com_realm()
def view(context, request, realm) -> dict[str, Any] | HttpResponse:
    cliente = api()
    if request.GET.get("exportar") == "1":
        resposta = HttpResponse(
            json.dumps(servico.exportar(cliente, realm), indent=2, ensure_ascii=False), content_type="application/json"
        )
        resposta["Content-Disposition"] = f'attachment; filename="{realm}-realm.json"'
        return resposta

    verificacoes = servico.auditar(cliente, realm)
    busca = request.GET.get("usuario", "").strip()
    apps = [c["clientId"] for c in clients_dos_apps(cliente, realm)]
    context.update(
        {
            "secoes": [(secao, list(itens)) for secao, itens in groupby(verificacoes, key=lambda v: v.secao)],
            "total": len(verificacoes),
            "ok": sum(v.ok for v in verificacoes),
            "pendentes": sum(not v.ok for v in verificacoes),
            "busca": busca,
            "usuarios": servico.consultar_usuario(cliente, realm, busca) if busca else None,
            "envs": servico.env_dos_apps(url_publica(), url_interna(), realm, apps),
            "conta": f"{url_publica()}/realms/{realm}/account",
        }
    )
    return {"request": request, "context": context}
