"""Indicadores comerciais do painel: funil, pipeline, conversão, ticket médio e ciclo de venda.

Convenções:
- pipeline: valor das propostas que estão com o cliente (enviadas e em negociação);
- previsão ponderada: valor × probabilidade de todas as propostas abertas;
- conversão: ganhas ÷ decididas pelo cliente (ganhas, perdidas e expiradas) fechadas no período,
  em quantidade e em valor; canceladas são decisão interna e ficam de fora;
- ciclo de venda: dias entre o envio e o fechamento das propostas ganhas.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import QuerySet

from .constantes import (
    EM_APROVACAO,
    ETAPAS_ABERTAS,
    ETAPAS_COM_CLIENTE,
    ETAPAS_DECIDIDAS,
    GANHA,
    MOTIVOS_PERDA,
    PERDIDA,
    ROTULOS_ETAPA,
    ZERO,
)
from .models import Proposta


@dataclass(frozen=True)
class Taxa:
    quantidade: Decimal | None
    valor: Decimal | None


def _pct(parte, todo) -> Decimal | None:
    if not todo:
        return None
    return (Decimal(parte) * 100 / Decimal(todo)).quantize(Decimal("0.1"), ROUND_HALF_UP)


def _soma(propostas) -> Decimal:
    return sum((p.valor_total for p in propostas), ZERO)


def funil(abertas: list[Proposta]) -> list[dict]:
    """Quantidade e valor por etapa aberta, com a largura relativa da barra."""
    linhas = []
    for etapa in ETAPAS_ABERTAS:
        da_etapa = [p for p in abertas if p.etapa == etapa]
        linhas.append({"etapa": etapa, "rotulo": ROTULOS_ETAPA[etapa], "qtd": len(da_etapa), "valor": _soma(da_etapa)})
    maior = max((l["valor"] for l in linhas), default=ZERO) or Decimal(1)
    for l in linhas:
        l["largura"] = int(l["valor"] * 100 / maior)
    return linhas


def conversao(decididas: list[Proposta]) -> Taxa:
    ganhas = [p for p in decididas if p.etapa == GANHA]
    return Taxa(_pct(len(ganhas), len(decididas)), _pct(_soma(ganhas), _soma(decididas)))


def ciclo_medio(ganhas: list[Proposta]) -> int | None:
    dias = [(p.fechada_em - p.enviada_em).days for p in ganhas if p.enviada_em and p.fechada_em]
    return round(sum(dias) / len(dias)) if dias else None


def motivos_perda(perdidas: list[Proposta]) -> list[dict]:
    contagem: dict[str, list[Proposta]] = defaultdict(list)
    for p in perdidas:
        contagem[p.motivo_perda or "outro"].append(p)
    rotulos = dict(MOTIVOS_PERDA)
    linhas = sorted(
        ({"rotulo": rotulos.get(m, m), "qtd": len(ps), "valor": _soma(ps)} for m, ps in contagem.items()),
        key=lambda l: (-l["qtd"], -l["valor"]),
    )
    total = len(perdidas) or 1
    for l in linhas:
        l["largura"] = int(l["qtd"] * 100 / total)
    return linhas


def por_responsavel(decididas: list[Proposta], abertas: list[Proposta]) -> list[dict]:
    grupos: dict[str, dict] = defaultdict(lambda: {"decididas": [], "abertas": []})
    for p in decididas:
        grupos[_nome(p)]["decididas"].append(p)
    for p in abertas:
        grupos[_nome(p)]["abertas"].append(p)
    linhas = []
    for nome, g in grupos.items():
        ganhas = [p for p in g["decididas"] if p.etapa == GANHA]
        linhas.append(
            {
                "nome": nome,
                "ganhas": len(ganhas),
                "valor_ganho": _soma(ganhas),
                "conversao": conversao(g["decididas"]).quantidade,
                "pipeline": _soma(p for p in g["abertas"] if p.etapa in ETAPAS_COM_CLIENTE),
            }
        )
    return sorted(linhas, key=lambda l: (-l["valor_ganho"], -l["pipeline"], l["nome"]))


def _nome(proposta: Proposta) -> str:
    usuario = proposta.responsavel
    return (usuario.get_full_name() or usuario.username) if usuario else "Sem responsável"


def _rotulo_periodo(dia: date, meses: int) -> str:
    """Rótulo da barra: mês (até 12 meses no filtro), trimestre (até 36) ou ano."""
    nomes = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")
    if meses <= 12:
        return f"{nomes[dia.month - 1]}/{dia.year}"
    if meses <= 36:
        return f"{(dia.month - 1) // 3 + 1}º tri/{dia.year}"
    return str(dia.year)


def _agrupamento(meses: int) -> str:
    return "mês" if meses <= 12 else "trimestre" if meses <= 36 else "ano"


def ganhos_por_mes(ganhas: list[Proposta], inicio: date, fim: date) -> list[dict]:
    """Vendido por mês; em períodos longos, por trimestre ou por ano, para o gráfico continuar legível."""
    quantidade = (fim.year - inicio.year) * 12 + fim.month - inicio.month + 1
    periodos: dict[str, Decimal] = {}
    mes = inicio.replace(day=1)
    while mes <= fim:
        periodos.setdefault(_rotulo_periodo(mes, quantidade), ZERO)
        mes = (mes + timedelta(days=32)).replace(day=1)
    for p in ganhas:
        chave = _rotulo_periodo(p.fechada_em, quantidade)
        if chave in periodos:
            periodos[chave] += p.valor_total
    maior = max(periodos.values(), default=ZERO) or Decimal(1)
    return [{"rotulo": r, "valor": v, "largura": int(v * 100 / maior)} for r, v in periodos.items()]


def painel(propostas: QuerySet[Proposta], inicio: date, fim: date, hoje: date) -> dict:
    """Todos os números do painel. ``propostas`` já vem filtrada pela empresa (e, se houver, pelo responsável)."""
    propostas = propostas.select_related("responsavel", "cliente", "empresa")
    abertas = list(propostas.filter(etapa__in=ETAPAS_ABERTAS))
    decididas = list(propostas.filter(etapa__in=ETAPAS_DECIDIDAS, fechada_em__range=(inicio, fim)))
    ganhas = [p for p in decididas if p.etapa == GANHA]
    perdidas = [p for p in decididas if p.etapa == PERDIDA]
    com_cliente = [p for p in abertas if p.etapa in ETAPAS_COM_CLIENTE]
    limite = hoje + timedelta(days=7)

    return {
        "pipeline": _soma(com_cliente),
        "pipeline_qtd": len(com_cliente),
        "ponderado": sum((p.valor_ponderado for p in abertas), ZERO),
        "abertas_qtd": len(abertas),
        "ganho": _soma(ganhas),
        "ganhas_qtd": len(ganhas),
        "decididas_qtd": len(decididas),
        "conversao": conversao(decididas),
        "ticket_medio": (_soma(ganhas) / len(ganhas)).quantize(Decimal("0.01")) if ganhas else None,
        "ciclo_medio": ciclo_medio(ganhas),
        "funil": funil(abertas),
        "motivos_perda": motivos_perda(perdidas),
        "por_responsavel": por_responsavel(decididas, abertas),
        "por_mes": ganhos_por_mes(ganhas, inicio, fim),
        "por_mes_titulo": _agrupamento((fim.year - inicio.year) * 12 + fim.month - inicio.month + 1),
        "vencendo": sorted((p for p in com_cliente if p.validade and hoje <= p.validade <= limite), key=lambda p: p.validade),
        "aguardando_aprovacao": [p for p in abertas if p.etapa == EM_APROVACAO],
        "acoes_atrasadas": sorted((p for p in abertas if p.acao_atrasada(hoje)), key=lambda p: p.proxima_acao_em),
        "sem_proxima_acao": [p for p in com_cliente if not p.proxima_acao_em],
    }
