"""Indicadores do painel: pipeline, previsão ponderada, conversão, ticket médio e ciclo de venda."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from commercial.propostas.constantes import ENVIADA
from commercial.propostas.indicadores import painel
from commercial.propostas.models import Proposta
from commercial.propostas.servicos import anotar, executar

pytestmark = pytest.mark.django_db
D = Decimal
HOJE = date(2026, 10, 28)
INICIO = date(2026, 1, 1)


@pytest.fixture
def carteira(nova_proposta):
    """Ganha (R$ 2.000, 10 dias), perdida (R$ 1.000), expirada (R$ 500), enviada (R$ 4.000) e rascunho (R$ 200)."""
    ganha = executar(nova_proposta(), "enviar", None, "Tech", hoje=HOJE - timedelta(days=10))
    executar(ganha, "ganhar", None, "Tech", hoje=HOJE)
    perdida = executar(nova_proposta(quantidade=D("5")), "enviar", None, "Tech", hoje=HOJE)
    executar(perdida, "perder", None, "Tech", hoje=HOJE, motivo_perda="preco")
    expirada = executar(nova_proposta(quantidade=D("2.5")), "enviar", None, "Tech", hoje=HOJE)
    Proposta.objects.filter(pk=expirada.pk).update(etapa="expirada", fechada_em=HOJE)
    enviada = executar(nova_proposta(quantidade=D("20")), "enviar", None, "Tech", hoje=HOJE)
    anotar(enviada, "", None, "Ligar", HOJE - timedelta(days=1))
    nova_proposta(quantidade=D("1"))
    return enviada


def test_painel(empresa, carteira) -> None:
    dados = painel(Proposta.objects.filter(empresa=empresa), INICIO, HOJE, HOJE)
    assert dados["pipeline"] == D("4000.00") and dados["pipeline_qtd"] == 1
    # 4.000 × 40% + 200 × 10%
    assert dados["ponderado"] == D("1620.00")
    assert dados["ganho"] == D("2000.00") and dados["ganhas_qtd"] == 1
    assert dados["conversao"].quantidade == D("33.3")
    assert dados["conversao"].valor == D("57.1")
    assert dados["ticket_medio"] == D("2000.00")
    assert dados["ciclo_medio"] == 10
    assert [m["rotulo"] for m in dados["motivos_perda"]] == ["Preço"]
    assert [p.pk for p in dados["acoes_atrasadas"]] == [carteira.pk]
    assert [p.pk for p in dados["vencendo"]] == []
    funil = {l["etapa"]: (l["qtd"], l["valor"]) for l in dados["funil"]}
    assert funil[ENVIADA] == (1, D("4000.00")) and funil["rascunho"] == (1, D("200.00"))
    assert sum(m["valor"] for m in dados["por_mes"]) == D("2000.00") and len(dados["por_mes"]) == 10


def test_periodo_sem_fechamentos(empresa, carteira) -> None:
    dados = painel(Proposta.objects.filter(empresa=empresa), date(2025, 1, 1), date(2025, 12, 31), HOJE)
    assert dados["conversao"].quantidade is None and dados["ticket_medio"] is None and dados["ciclo_medio"] is None
    assert dados["pipeline"] == D("4000.00")
