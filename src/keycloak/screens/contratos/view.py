"""Contratos: propostas fechadas (ganhas), documentos contratuais do SharePoint e documentos da empresa."""
from collections import Counter, defaultdict
from typing import Any

from django.db.models import Prefetch, Q
from django.utils import timezone

from commercial.propostas.constantes import GANHA, ZERO
from commercial.propostas.models import ArquivoProposta, ArquivoSharePoint, Proposta
from commercial.propostas.web import com_empresa

LIMITE_DOCUMENTOS = 300


def _ano(texto: str | None) -> int | None:
    return int(texto) if texto and texto.isdigit() else None


def _por_ano(contratos: list[Proposta], documentos) -> list[dict]:
    """Contratos fechados (pelo ano de fechamento) e documentos contratuais, ano a ano."""
    fechados: dict[int, list[Proposta]] = defaultdict(list)
    for p in contratos:
        fechados[(p.fechada_em or p.enviada_em or timezone.localdate()).year].append(p)
    docs: dict[int, Counter] = defaultdict(Counter)
    for ano, categoria in documentos.exclude(ano=None).values_list("ano", "categoria"):
        docs[ano][categoria] += 1
    linhas = []
    for ano in sorted(set(fechados) | set(docs), reverse=True):
        valor = sum((p.valor_total for p in fechados[ano]), ZERO)
        linhas.append(
            {
                "ano": ano, "contratos": len(fechados[ano]), "valor": valor,
                "clientes": len({p.cliente_id for p in fechados[ano]}),
                "pedidos": docs[ano][ArquivoSharePoint.PEDIDO], "contratos_doc": docs[ano][ArquivoSharePoint.CONTRATO],
                "ndas": docs[ano][ArquivoSharePoint.NDA],
            }
        )
    maior = max((l["valor"] for l in linhas), default=ZERO)
    for l in linhas:
        l["largura"] = int(l["valor"] * 100 / maior) if maior else 0
    return linhas


@com_empresa
def view(context, request, empresa) -> dict[str, Any]:
    hoje = timezone.localdate()
    ano = _ano(request.GET.get("ano"))
    busca = request.GET.get("q", "").strip()
    categoria = request.GET.get("categoria", "contratuais")

    contratos = Proposta.objects.filter(empresa=empresa, etapa=GANHA).select_related("cliente", "responsavel").prefetch_related(
        Prefetch("arquivos", queryset=ArquivoProposta.objects.filter(tipo=ArquivoProposta.PEDIDO), to_attr="pedidos"),
        Prefetch(
            "acervo",
            queryset=ArquivoSharePoint.objects.filter(categoria__in=(ArquivoSharePoint.CONTRATO, ArquivoSharePoint.NDA)),
            to_attr="contratuais",
        ),
    )
    documentos = ArquivoSharePoint.objects.filter(empresa=empresa).select_related("cliente", "proposta")
    if busca:
        filtro = Q(cliente__nome__icontains=busca) | Q(cliente__nome_fantasia__icontains=busca) | Q(titulo__icontains=busca)
        contratos = contratos.filter(filtro)
        documentos = documentos.filter(Q(nome__icontains=busca) | Q(pasta_cliente__icontains=busca) | Q(cliente__nome__icontains=busca))
    por_ano = _por_ano(list(contratos), documentos)
    if ano:
        contratos = contratos.filter(Q(fechada_em__year=ano) | Q(fechada_em=None, ano=ano))
        documentos = documentos.filter(ano=ano)
    contratos = sorted(contratos, key=lambda p: (p.fechada_em or p.enviada_em or hoje), reverse=True)

    contagem = Counter(documentos.values_list("categoria", flat=True))
    if categoria == "contratuais":
        documentos = documentos.filter(categoria__in=ArquivoSharePoint.CONTRATUAIS)
    elif categoria in dict(ArquivoSharePoint.CATEGORIAS):
        documentos = documentos.filter(categoria=categoria)
    total_documentos = documentos.count()

    valor = sum((p.valor_total for p in contratos), ZERO)
    documentos_empresa = list(empresa.documentos.all())
    context.update(
        {
            "contratos": contratos,
            "por_ano": por_ano,
            "valor": valor,
            "ticket": (valor / len(contratos)).quantize(ZERO) if contratos else None,
            "clientes": len({p.cliente_id for p in contratos}),
            "documentos": documentos.order_by("-ano", "-modificado_em")[:LIMITE_DOCUMENTOS],
            "total_documentos": total_documentos,
            "limite": LIMITE_DOCUMENTOS,
            "categorias": [(c, rotulo, contagem.get(c, 0)) for c, rotulo in ArquivoSharePoint.CATEGORIAS],
            "contratuais_qtd": sum(contagem.get(c, 0) for c in ArquivoSharePoint.CONTRATUAIS),
            "categoria": categoria,
            "ano": ano,
            "busca": busca,
            "documentos_empresa": [(d, d.vencido(hoje)) for d in documentos_empresa],
            "hoje": hoje,
        }
    )
    return {"request": request, "context": context}
