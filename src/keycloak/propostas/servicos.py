"""Regras do ciclo de vida da proposta: numeração, totais, etapas, revisões e expiração.

As telas e o admin só mudam propostas por aqui, para que toda mudança de etapa
siga as transições permitidas e fique registrada no histórico.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .constantes import (
    APROVADA,
    CANCELADA,
    EM_APROVACAO,
    ENVIADA,
    ETAPAS_ABERTAS,
    ETAPAS_COM_CLIENTE,
    EXPIRADA,
    GANHA,
    NEGOCIACAO,
    PERDIDA,
    PROBABILIDADE_PADRAO,
    RASCUNHO,
    ROTULOS_ETAPA,
    ZERO,
)
from .models import (
    PAPEL_ADMIN,
    PAPEL_MASTER,
    PAPEL_TECH,
    Empresa,
    EventoProposta,
    ItemProposta,
    Proposta,
    RevisaoProposta,
)

VENDEDORES = (PAPEL_ADMIN, PAPEL_MASTER, PAPEL_TECH)
GESTORES = (PAPEL_ADMIN, PAPEL_MASTER)


@dataclass(frozen=True)
class Acao:
    """Botão do funil: de quais etapas sai, para qual vai e quem pode usar."""

    chave: str
    rotulo: str
    origens: tuple[str, ...]
    destino: str
    papeis: tuple[str, ...]
    estilo: str = ""
    confirmar: str = ""


ACOES = {
    a.chave: a
    for a in [
        Acao("solicitar_aprovacao", "Pedir aprovação", (RASCUNHO,), EM_APROVACAO, VENDEDORES, "primario"),
        Acao("aprovar", "Aprovar desconto", (EM_APROVACAO,), APROVADA, GESTORES, "primario"),
        Acao("reprovar", "Devolver ao rascunho", (EM_APROVACAO,), RASCUNHO, GESTORES),
        Acao("enviar", "Marcar como enviada", (RASCUNHO, APROVADA), ENVIADA, VENDEDORES, "primario"),
        Acao("negociar", "Em negociação", (ENVIADA,), NEGOCIACAO, VENDEDORES),
        Acao("ganhar", "Ganha", (ENVIADA, NEGOCIACAO), GANHA, VENDEDORES, "primario"),
        Acao("perder", "Perdida", ETAPAS_ABERTAS, PERDIDA, VENDEDORES, "perigo"),
        Acao(
            "cancelar", "Cancelar", ETAPAS_ABERTAS, CANCELADA, VENDEDORES, "perigo",
            "Cancelar a proposta? Ela sai do funil e não conta na taxa de conversão.",
        ),
        Acao(
            "revisar", "Criar revisão", (EM_APROVACAO, APROVADA, ENVIADA, NEGOCIACAO, EXPIRADA), RASCUNHO, VENDEDORES,
            confirmar="A versão atual fica guardada no histórico e a proposta volta ao rascunho com o número de revisão seguinte.",
        ),
    ]
}


def acoes_disponiveis(proposta: Proposta, papel: str | None) -> list[Acao]:
    """Ações que o papel pode usar na etapa atual (enviar um rascunho só se o desconto não pede aprovação)."""
    acoes = [a for a in ACOES.values() if proposta.etapa in a.origens and papel in a.papeis]
    if proposta.etapa == RASCUNHO:
        bloqueada = "enviar" if proposta.precisa_aprovacao else "solicitar_aprovacao"
        acoes = [a for a in acoes if a.chave != bloqueada]
    return acoes


def registrar(proposta: Proposta, tipo: str, descricao: str, usuario=None, de: str = "", para: str = "") -> EventoProposta:
    return EventoProposta.objects.create(
        proposta=proposta, tipo=tipo, descricao=descricao, usuario=usuario, etapa_de=de, etapa_para=para
    )


def _proximo_numero(empresa: Empresa, ano: int) -> int:
    """Sequência por empresa e ano. A trava na linha da empresa evita dois números iguais em salvamentos simultâneos."""
    Empresa.objects.select_for_update().filter(pk=empresa.pk).first()
    ultimo = Proposta.objects.filter(empresa=empresa, ano=ano).aggregate(m=Max("numero"))["m"]
    return (ultimo or 0) + 1


def recalcular(proposta: Proposta) -> None:
    """Atualiza os totais guardados na proposta a partir dos itens."""
    itens = list(proposta.itens.all())
    proposta.valor_total = sum((i.total for i in itens), ZERO)
    proposta.valor_referencia = sum((i.referencia for i in itens), ZERO)
    proposta.save(update_fields=["valor_total", "valor_referencia", "atualizada_em"])


def _preparar_itens(itens: list[ItemProposta]) -> None:
    for ordem, item in enumerate(itens, start=1):
        item.ordem = ordem
        if item.item_catalogo_id and item.item_catalogo.empresa_id != item.proposta.empresa_id:
            raise ValidationError("Um dos itens é do catálogo de outra empresa.")
        # O preço de tabela é o do catálogo no momento em que o item entrou; não muda se o catálogo mudar depois.
        if item.item_catalogo_id and not item.pk:
            item.preco_tabela = item.item_catalogo.preco


@transaction.atomic
def salvar_proposta(proposta: Proposta, itens: list[ItemProposta], removidos: list[ItemProposta], usuario) -> Proposta:
    """Cria ou atualiza um rascunho com os itens do formulário."""
    nova = proposta.pk is None
    if not nova and Proposta.objects.get(pk=proposta.pk).etapa != RASCUNHO:
        raise ValidationError("Só o rascunho pode ser editado. Crie uma revisão para mudar uma proposta enviada.")
    if nova:
        hoje = timezone.localdate()
        proposta.ano = hoje.year
        proposta.numero = _proximo_numero(proposta.empresa, proposta.ano)
        proposta.criada_por = usuario
        proposta.etapa = RASCUNHO
        proposta.validade = proposta.validade or hoje + timedelta(days=proposta.empresa.validade_dias)
    proposta.full_clean(exclude=["ano", "numero"])
    proposta.save()
    for item in removidos:
        if item.pk:
            item.delete()
    for item in itens:
        item.proposta = proposta
    _preparar_itens(itens)
    for item in itens:
        item.save()
    recalcular(proposta)
    if nova:
        registrar(proposta, EventoProposta.CRIADA, f"Proposta {proposta.codigo} criada.", usuario, para=RASCUNHO)
    else:
        registrar(proposta, EventoProposta.EDITADA, "Rascunho editado.", usuario)
    return proposta


def _foto(proposta: Proposta) -> dict:
    """Dados da versão atual, para guardar na revisão."""
    campos = (
        "titulo", "escopo", "condicoes_pagamento", "prazo_entrega", "probabilidade", "valor_total", "valor_referencia",
    )
    dados = {campo: str(getattr(proposta, campo)) for campo in campos}
    dados.update(
        codigo=proposta.codigo,
        cliente=str(proposta.cliente),
        contato=str(proposta.contato or ""),
        validade=proposta.validade.isoformat() if proposta.validade else None,
        enviada_em=proposta.enviada_em.isoformat() if proposta.enviada_em else None,
        itens=[
            {
                "descricao": i.descricao,
                "detalhes": i.detalhes,
                "unidade": i.unidade,
                "quantidade": str(i.quantidade),
                "preco_tabela": str(i.preco_tabela),
                "preco_unitario": str(i.preco_unitario),
                "desconto": str(i.desconto),
                "total": str(i.total),
            }
            for i in proposta.itens.all()
        ],
    )
    return dados


@transaction.atomic
def executar(proposta: Proposta, chave: str, usuario, papel: str | None, hoje: date | None = None, **dados) -> Proposta:
    """Aplica uma ação do funil. ``dados``: motivo_perda, concorrente e comentario (perder/ganhar) ou motivo (revisar)."""
    hoje = hoje or timezone.localdate()
    proposta = Proposta.objects.select_for_update().select_related("empresa").get(pk=proposta.pk)
    acao = ACOES.get(chave)
    if acao is None or acao not in acoes_disponiveis(proposta, papel):
        raise ValidationError(f"Ação não permitida para uma proposta “{proposta.rotulo_etapa}” com o seu papel.")
    if not proposta.itens.exists() and acao.destino in (EM_APROVACAO, ENVIADA):
        raise ValidationError("Inclua pelo menos um item antes de enviar a proposta.")

    origem = proposta.etapa
    comentario = (dados.get("comentario") or "").strip()
    detalhe = ""
    if chave == "revisar":
        RevisaoProposta.objects.create(
            proposta=proposta, revisao=proposta.revisao, etapa=origem, valor_total=proposta.valor_total,
            dados=_foto(proposta), motivo=(dados.get("motivo") or "").strip(), criada_por=usuario,
        )
        proposta.revisao += 1
        proposta.aprovada_por = proposta.aprovada_em = proposta.enviada_em = None
        detalhe = f" Versão anterior guardada; agora {proposta.codigo}."
    elif chave == "aprovar":
        proposta.aprovada_por, proposta.aprovada_em = usuario, timezone.now()
        detalhe = f" Desconto de {proposta.desconto}% aprovado."
    elif chave == "reprovar":
        proposta.aprovada_por = proposta.aprovada_em = None
    elif chave == "enviar":
        proposta.enviada_em = hoje
        if not proposta.validade or proposta.validade < hoje:
            proposta.validade = hoje + timedelta(days=proposta.empresa.validade_dias)
        detalhe = f" Válida até {proposta.validade:%d/%m/%Y}."
    elif chave == "perder":
        motivo = dados.get("motivo_perda") or ""
        if not motivo:
            raise ValidationError("Informe o motivo da perda.")
        proposta.motivo_perda = motivo
        proposta.concorrente = (dados.get("concorrente") or "").strip()
        detalhe = f" Motivo: {proposta.get_motivo_perda_display()}."
    if acao.destino in (GANHA, PERDIDA, CANCELADA):
        proposta.fechada_em = hoje
        proposta.comentario_fechamento = comentario
        proposta.proxima_acao, proposta.proxima_acao_em = "", None
    elif acao.destino == RASCUNHO:
        proposta.fechada_em = None

    proposta.etapa = acao.destino
    proposta.probabilidade = PROBABILIDADE_PADRAO[acao.destino]
    proposta.save()
    texto = f"{ROTULOS_ETAPA[origem]} → {ROTULOS_ETAPA[acao.destino]}.{detalhe}"
    if comentario:
        texto += f" {comentario}"
    tipo = EventoProposta.REVISADA if chave == "revisar" else EventoProposta.ETAPA
    registrar(proposta, tipo, texto, usuario, de=origem, para=acao.destino)
    return proposta


def anotar(proposta: Proposta, texto: str, usuario, proxima_acao: str = "", proxima_acao_em: date | None = None) -> None:
    """Follow-up: anotação no histórico e, se informada, a próxima ação."""
    texto = texto.strip()
    if not texto and not proxima_acao:
        raise ValidationError("Escreva a anotação ou a próxima ação.")
    if proxima_acao or proxima_acao_em:
        if not proposta.aberta:
            raise ValidationError("Proposta fechada não tem próxima ação.")
        proposta.proxima_acao, proposta.proxima_acao_em = proxima_acao.strip(), proxima_acao_em
        proposta.save(update_fields=["proxima_acao", "proxima_acao_em", "atualizada_em"])
        quando = f" em {proxima_acao_em:%d/%m/%Y}" if proxima_acao_em else ""
        texto = f"{texto} Próxima ação: {proxima_acao.strip()}{quando}.".strip()
    registrar(proposta, EventoProposta.NOTA, texto, usuario)


@transaction.atomic
def duplicar(proposta: Proposta, usuario) -> Proposta:
    """Nova proposta (rascunho, número novo) com os dados e itens de outra; serve de modelo."""
    itens = list(proposta.itens.all())
    copia = Proposta(
        empresa=proposta.empresa, titulo=proposta.titulo, cliente=proposta.cliente, contato=proposta.contato,
        responsavel=usuario, origem=proposta.origem, escopo=proposta.escopo,
        condicoes_pagamento=proposta.condicoes_pagamento, prazo_entrega=proposta.prazo_entrega,
        probabilidade=PROBABILIDADE_PADRAO[RASCUNHO],
    )
    novos = [
        ItemProposta(
            item_catalogo=i.item_catalogo, descricao=i.descricao, detalhes=i.detalhes, unidade=i.unidade,
            quantidade=i.quantidade, preco_unitario=i.preco_unitario, desconto=i.desconto,
        )
        for i in itens
    ]
    # Os itens do catálogo entram com o preço de tabela de hoje, como numa proposta nova.
    copia = salvar_proposta(copia, novos, [], usuario)
    registrar(copia, EventoProposta.NOTA, f"Criada a partir da proposta {proposta.codigo}.", usuario)
    return copia


def expirar_vencidas(empresa: Empresa, hoje: date | None = None) -> list[Proposta]:
    """Propostas com o cliente cuja validade passou viram "Expirada"."""
    hoje = hoje or timezone.localdate()
    vencidas = list(
        Proposta.objects.filter(empresa=empresa, etapa__in=ETAPAS_COM_CLIENTE, validade__lt=hoje).select_related("empresa")
    )
    for proposta in vencidas:
        origem = proposta.etapa
        proposta.etapa = EXPIRADA
        proposta.probabilidade = PROBABILIDADE_PADRAO[EXPIRADA]
        proposta.fechada_em = hoje
        proposta.save(update_fields=["etapa", "probabilidade", "fechada_em", "atualizada_em"])
        registrar(
            proposta, EventoProposta.ETAPA,
            f"{ROTULOS_ETAPA[origem]} → {ROTULOS_ETAPA[EXPIRADA]}. Validade de {proposta.validade:%d/%m/%Y} vencida sem resposta.",
            de=origem, para=EXPIRADA,
        )
    return vencidas
