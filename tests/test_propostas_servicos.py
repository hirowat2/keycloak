"""Ciclo de vida da proposta: numeração, totais, alçada de desconto, etapas, revisões e expiração."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from commercial.propostas.constantes import (
    APROVADA,
    CANCELADA,
    EM_APROVACAO,
    ENVIADA,
    EXPIRADA,
    GANHA,
    NEGOCIACAO,
    PERDIDA,
    RASCUNHO,
)
from commercial.propostas.models import Empresa, EventoProposta, ItemProposta, Proposta
from commercial.propostas.servicos import (
    acoes_disponiveis,
    anotar,
    duplicar,
    executar,
    expirar_vencidas,
    salvar_proposta,
)

pytestmark = pytest.mark.django_db
D = Decimal
HOJE = date(2026, 10, 28)


def test_numeracao_por_empresa_e_ano(empresa, cliente, nova_proposta) -> None:
    primeira, segunda = nova_proposta(), nova_proposta()
    ano = timezone.localdate().year
    assert (primeira.numero, segunda.numero) == (1, 2)
    assert primeira.codigo == f"PC-{ano}-0001"
    outra = Empresa.objects.create(nome="Outra", slug="outra", prefixo="OT")
    from commercial.propostas.models import Cliente

    cliente_outra = Cliente.objects.create(empresa=outra, nome="Cliente da outra")
    p = salvar_proposta(
        Proposta(empresa=outra, cliente=cliente_outra, titulo="X"),
        [ItemProposta(descricao="Avulso", quantidade=D("1"), preco_unitario=D("50"))], [], None,
    )
    assert p.codigo == f"OT-{ano}-0001"


def test_totais_e_desconto_sobre_a_tabela(nova_proposta) -> None:
    # 10 h × R$ 180 (tabela 200) com 5% = 1.710; referência 2.000 → 14,5% de desconto.
    p = nova_proposta(preco=D("180"), desconto=D("5"))
    assert p.valor_total == D("1710.00")
    assert p.valor_referencia == D("2000.00")
    assert p.desconto == D("14.50")
    assert p.precisa_aprovacao


def test_rascunho_nasce_com_validade_padrao_e_historico(empresa, nova_proposta) -> None:
    p = nova_proposta()
    assert p.etapa == RASCUNHO
    assert p.validade == timezone.localdate() + timedelta(days=empresa.validade_dias)
    assert p.eventos.get().tipo == EventoProposta.CRIADA


def test_desconto_dentro_da_alcada_envia_direto(nova_proposta) -> None:
    p = nova_proposta(desconto=D("10"))
    chaves = [a.chave for a in acoes_disponiveis(p, "Tech")]
    assert "enviar" in chaves and "solicitar_aprovacao" not in chaves
    p = executar(p, "enviar", None, "Tech", hoje=HOJE)
    assert p.etapa == ENVIADA and p.enviada_em == HOJE and p.probabilidade == 40


def test_desconto_acima_da_alcada_precisa_de_master(nova_proposta) -> None:
    p = nova_proposta(desconto=D("25"))
    with pytest.raises(ValidationError):
        executar(p, "enviar", None, "Tech")
    p = executar(p, "solicitar_aprovacao", None, "Tech")
    assert p.etapa == EM_APROVACAO
    with pytest.raises(ValidationError):
        executar(p, "aprovar", None, "Tech")
    p = executar(p, "aprovar", None, "Master")
    assert p.etapa == APROVADA and p.aprovada_em is not None
    assert executar(p, "enviar", None, "Tech").etapa == ENVIADA


def test_limited_nao_muda_etapa(nova_proposta) -> None:
    p = nova_proposta()
    assert acoes_disponiveis(p, "Limited") == []
    with pytest.raises(ValidationError):
        executar(p, "enviar", None, "Limited")


def test_enviar_com_validade_vencida_renova(empresa, nova_proposta) -> None:
    p = nova_proposta(validade=HOJE - timedelta(days=3))
    p = executar(p, "enviar", None, "Tech", hoje=HOJE)
    assert p.validade == HOJE + timedelta(days=empresa.validade_dias)


def test_perder_exige_motivo_e_fecha(nova_proposta) -> None:
    p = executar(nova_proposta(), "enviar", None, "Tech", hoje=HOJE)
    with pytest.raises(ValidationError):
        executar(p, "perder", None, "Tech")
    p = executar(p, "perder", None, "Tech", hoje=HOJE, motivo_perda="preco", concorrente="Rival SA")
    assert (p.etapa, p.motivo_perda, p.concorrente, p.fechada_em, p.probabilidade) == (PERDIDA, "preco", "Rival SA", HOJE, 0)
    assert acoes_disponiveis(p, "Master") == []


def test_ganhar_limpa_proxima_acao(nova_proposta) -> None:
    p = executar(nova_proposta(), "enviar", None, "Tech", hoje=HOJE)
    anotar(p, "Ligou pedindo prazo", None, "Retornar", HOJE + timedelta(days=2))
    p = executar(p, "negociar", None, "Tech")
    assert p.etapa == NEGOCIACAO and p.proxima_acao == "Retornar"
    p = executar(p, "ganhar", None, "Tech", hoje=HOJE, comentario="Pedido 123")
    assert (p.etapa, p.probabilidade, p.proxima_acao, p.comentario_fechamento) == (GANHA, 100, "", "Pedido 123")


def test_so_rascunho_e_editavel(nova_proposta) -> None:
    p = executar(nova_proposta(), "enviar", None, "Tech")
    p.titulo = "Mudei"
    with pytest.raises(ValidationError):
        salvar_proposta(p, [], [], None)


def test_revisao_guarda_versao_e_volta_ao_rascunho(nova_proposta) -> None:
    p = executar(nova_proposta(), "enviar", None, "Tech", hoje=HOJE)
    codigo = p.codigo
    p = executar(p, "revisar", None, "Tech", motivo="Cliente pediu menos horas")
    assert p.etapa == RASCUNHO and p.revisao == 1 and p.enviada_em is None
    assert p.codigo == f"{codigo}-R1"
    revisao = p.revisoes.get()
    assert revisao.revisao == 0 and revisao.etapa == ENVIADA and revisao.motivo == "Cliente pediu menos horas"
    assert revisao.dados["codigo"] == codigo and revisao.dados["itens"][0]["total"] == "2000.00"
    item = p.itens.get()
    item.quantidade = D("5")
    salvar_proposta(p, [item], [], None)
    p.refresh_from_db()
    assert p.valor_total == D("1000.00")


def test_cancelar_e_saida_de_qualquer_etapa_aberta(nova_proposta) -> None:
    assert executar(nova_proposta(), "cancelar", None, "Tech").etapa == CANCELADA


def test_enviar_sem_itens_e_recusado(empresa, cliente) -> None:
    p = salvar_proposta(Proposta(empresa=empresa, cliente=cliente, titulo="Vazia"), [], [], None)
    with pytest.raises(ValidationError):
        executar(p, "enviar", None, "Tech")


def test_expira_so_quem_esta_com_o_cliente(nova_proposta) -> None:
    enviada = executar(nova_proposta(), "enviar", None, "Tech", hoje=HOJE - timedelta(days=40))
    Proposta.objects.filter(pk=enviada.pk).update(validade=HOJE - timedelta(days=1))
    rascunho = nova_proposta(validade=HOJE - timedelta(days=1))
    assert [p.pk for p in expirar_vencidas(enviada.empresa, HOJE)] == [enviada.pk]
    enviada.refresh_from_db()
    rascunho.refresh_from_db()
    assert enviada.etapa == EXPIRADA and enviada.fechada_em == HOJE
    assert rascunho.etapa == RASCUNHO
    assert [a.chave for a in acoes_disponiveis(enviada, "Tech")] == ["revisar"]


def test_duplicar_cria_rascunho_com_numero_novo(nova_proposta, usuario) -> None:
    vendedor = usuario("Tech")
    origem = executar(nova_proposta(desconto=D("5")), "enviar", None, "Tech")
    copia = duplicar(origem, vendedor)
    assert copia.pk != origem.pk and copia.numero == origem.numero + 1
    assert copia.etapa == RASCUNHO and copia.responsavel == vendedor
    assert copia.valor_total == origem.valor_total
    assert copia.itens.get().preco_tabela == D("200.00")


def test_anotacao_exige_texto_ou_acao(nova_proposta) -> None:
    p = nova_proposta()
    with pytest.raises(ValidationError):
        anotar(p, "  ", None)
    anotar(p, "Cliente gostou da apresentação", None)
    assert p.eventos.filter(tipo=EventoProposta.NOTA).exists()
