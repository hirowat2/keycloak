"""Histórico: propostas ano a ano desde o primeiro registro, clientes ao longo dos anos e linhas de serviço."""
from typing import Any

from django.db.models import Max, Min, Q

from commercial.propostas.historico import LINHAS_DE_SERVICO, OUTROS, historico, linha_de_servico
from commercial.propostas.models import ArquivoSharePoint, Proposta
from commercial.propostas.web import com_empresa


def _ano(texto: str | None) -> int | None:
    return int(texto) if texto and texto.isdigit() else None


@com_empresa
def view(context, request, empresa) -> dict[str, Any]:
    todas = Proposta.objects.filter(empresa=empresa)
    limites = todas.aggregate(primeiro=Min("ano"), ultimo=Max("ano"))
    de, ate = _ano(request.GET.get("de")) or limites["primeiro"], _ano(request.GET.get("ate")) or limites["ultimo"]
    propostas = todas
    if de:
        propostas = propostas.filter(ano__gte=de)
    if ate:
        propostas = propostas.filter(ano__lte=ate)
    busca = request.GET.get("cliente", "").strip()
    if busca:
        propostas = propostas.filter(Q(cliente__nome__icontains=busca) | Q(cliente__nome_fantasia__icontains=busca))
    linha = request.GET.get("linha", "")
    if linha:
        propostas = Proposta.objects.filter(pk__in=[p.pk for p in propostas if linha_de_servico(p) == linha])

    acervo = ArquivoSharePoint.objects.filter(empresa=empresa)
    if de:
        acervo = acervo.filter(ano__gte=de)
    if ate:
        acervo = acervo.filter(ano__lte=ate)
    if busca:
        acervo = acervo.filter(Q(cliente__nome__icontains=busca) | Q(pasta_cliente__icontains=busca))
    context.update(
        {
            **historico(propostas, acervo),
            "de": de,
            "ate": ate,
            "busca": busca,
            "linha": linha,
            "linhas_opcoes": [nome for nome, _ in LINHAS_DE_SERVICO] + [OUTROS],
            "anos_opcoes": list(range(limites["primeiro"], limites["ultimo"] + 1)) if limites["primeiro"] else [],
        }
    )
    return {"request": request, "context": context}
