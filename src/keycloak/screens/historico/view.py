"""Histórico: cada etapa simulada ou aplicada, por quem, em que realm e com que resultado."""
from typing import Any

from django.core.paginator import Paginator

from keycloak.automacao.plano import Passo, Plano
from keycloak.automacao.web import GRUPOS_CONSULTA, exigir
from keycloak.models import Aplicacao


def view(context, request) -> dict[str, Any]:
    if not exigir(request, GRUPOS_CONSULTA):
        context["pagina"] = None
        return {"request": request, "context": context}
    registros = Aplicacao.objects.select_related("usuario")
    realm = request.GET.get("realm", "")
    if realm:
        registros = registros.filter(realm=realm)
    if request.GET.get("aplicadas") == "1":
        registros = registros.filter(simulacao=False)
    detalhe = registros.filter(pk=request.GET["id"]).first() if request.GET.get("id", "").isdigit() else None
    plano = None
    if detalhe:
        plano = Plano(detalhe.simulacao)
        plano.passos = [Passo(**p) for p in detalhe.passos]
    context.update(
        {
            "pagina": Paginator(registros, 30).get_page(request.GET.get("pagina")),
            "realms_historico": Aplicacao.objects.order_by("realm").values_list("realm", flat=True).distinct(),
            "filtro_realm": realm,
            "aplicadas": request.GET.get("aplicadas") == "1",
            "detalhe": detalhe,
            "plano": plano,
        }
    )
    return {"request": request, "context": context}
