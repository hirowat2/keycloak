"""Painel comercial: pipeline, previsão, conversão, ciclo de venda e o que precisa de atenção."""
from typing import Any

from django.contrib import messages
from django.utils import timezone

from commercial.propostas import indicadores
from commercial.propostas.models import Proposta
from commercial.propostas.servicos import expirar_vencidas
from commercial.propostas.web import com_empresa, periodo


@com_empresa
def view(context, request, empresa) -> dict[str, Any]:
    hoje = timezone.localdate()
    for proposta in expirar_vencidas(empresa, hoje):
        messages.info(request, f"{proposta.codigo} expirou: a validade ({proposta.validade:%d/%m/%Y}) passou sem resposta.")
    filtro = periodo(request, empresa)
    propostas = Proposta.objects.filter(empresa=empresa)
    if filtro.responsavel:
        propostas = propostas.filter(responsavel=filtro.responsavel)

    context.update(
        {
            "filtro": filtro,
            "hoje": hoje,
            "vazio": not Proposta.objects.filter(empresa=empresa).exists(),
            **indicadores.painel(propostas, filtro.inicio, filtro.fim, hoje),
        }
    )
    return {"request": request, "context": context}
