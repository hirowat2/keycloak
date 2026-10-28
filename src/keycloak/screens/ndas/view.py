"""NDAs: acordos de confidencialidade por cliente, a partir do acervo do SharePoint e da carteira de contratos."""
import re
import unicodedata
from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone

from commercial.propostas.models import ArquivoSharePoint, ContratoCliente
from commercial.propostas.web import com_empresa

AVISO_DIAS = 60
CITA_NDA = re.compile(r"\bnda\b|\bdna\b|confidencial|sigilo", re.I)  # "DNA" aparece como erro de digitação de NDA
ASSINADO = re.compile(r"assinad|signed|docusign|clicksign", re.I)


def _chave(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").replace("_", " "))
    return " ".join(base.encode("ascii", "ignore").decode().lower().split())


def _situacao(vencimento, hoje) -> str:
    if not vencimento:
        return "sem_vencimento"
    if vencimento < hoje:
        return "vencido"
    return "vence_em_breve" if vencimento <= hoje + timedelta(days=AVISO_DIAS) else "vigente"


@com_empresa
def view(context, request, empresa) -> dict[str, Any]:
    hoje = timezone.localdate()
    busca = request.GET.get("q", "").strip()

    arquivos = ArquivoSharePoint.objects.filter(empresa=empresa, categoria=ArquivoSharePoint.NDA).select_related("cliente")
    carteira = [
        c for c in ContratoCliente.objects.filter(empresa=empresa).select_related("cliente")
        if CITA_NDA.search(f"{c.historico} {c.sistema} {c.observacao}")
    ]
    if busca:
        arquivos = arquivos.filter(Q(nome__icontains=busca) | Q(pasta_cliente__icontains=busca) | Q(cliente__nome__icontains=busca))
        carteira = [c for c in carteira if busca.lower() in f"{c.cliente_nome} {c.cliente}".lower()]

    # Um grupo por cliente: pelo cadastro quando ligado; senão, pelo nome da pasta ou da planilha.
    grupos: dict[str, dict] = defaultdict(lambda: {"nome": "", "cliente": None, "arquivos": [], "carteira": []})
    for a in arquivos:
        chave = f"c{a.cliente_id}" if a.cliente_id else _chave(a.pasta_cliente or a.pasta_raiz)
        grupo = grupos[chave]
        grupo["cliente"], grupo["nome"] = a.cliente or grupo["cliente"], str(a.cliente or a.pasta_cliente or a.pasta_raiz)
        grupo["arquivos"].append(a)
    for c in carteira:
        chave = f"c{c.cliente_id}" if c.cliente_id else _chave(c.cliente_nome)
        grupo = grupos[chave]
        grupo["cliente"], grupo["nome"] = c.cliente or grupo["cliente"], grupo["nome"] or c.cliente_nome
        grupo["carteira"].append(c)

    linhas = []
    for grupo in grupos.values():
        vencimento = max((c.vencimento for c in grupo["carteira"] if c.vencimento), default=None)
        datas = [a.modificado_em for a in grupo["arquivos"] if a.modificado_em]
        linhas.append(
            {
                **grupo,
                "arquivos": sorted(grupo["arquivos"], key=lambda a: a.modificado_em or timezone.now(), reverse=True),
                "assinado": any(ASSINADO.search(a.nome) for a in grupo["arquivos"])
                or any(c.assinado.lower().startswith("sim") for c in grupo["carteira"]),
                "ultimo": max(datas) if datas else None,
                "vencimento": vencimento,
                "situacao": _situacao(vencimento, hoje),
            }
        )
    ordem = {"vencido": 0, "vence_em_breve": 1, "vigente": 2, "sem_vencimento": 3}
    linhas.sort(key=lambda l: (ordem[l["situacao"]], l["nome"].lower()))

    # Clientes com contrato em andamento na carteira e nenhum NDA encontrado.
    com_nda = {l["cliente"].pk for l in linhas if l["cliente"]} | {_chave(l["nome"]) for l in linhas}
    sem_nda = sorted(
        {
            c.cliente_nome: c for c in ContratoCliente.objects.filter(empresa=empresa, situacao=ContratoCliente.ANDAMENTO)
            if not (c.cliente_id in com_nda or _chave(c.cliente_nome) in com_nda)
        }.values(),
        key=lambda c: c.cliente_nome.lower(),
    )
    context.update(
        {
            "linhas": linhas,
            "busca": busca,
            "total_arquivos": sum(len(l["arquivos"]) for l in linhas),
            "assinados": sum(1 for l in linhas if l["assinado"]),
            "vencidos": sum(1 for l in linhas if l["situacao"] == "vencido"),
            "vencendo": sum(1 for l in linhas if l["situacao"] == "vence_em_breve"),
            "sem_nda": sem_nda,
            "aviso_dias": AVISO_DIAS,
            "rotulos": {"vencido": "Vencido", "vence_em_breve": f"Vence em até {AVISO_DIAS} dias", "vigente": "Vigente", "sem_vencimento": "Sem vencimento informado"},
            "tem_carteira": ContratoCliente.objects.filter(empresa=empresa).exists(),
        }
    )
    return {"request": request, "context": context}
