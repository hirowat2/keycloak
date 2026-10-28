"""Etapas do funil, probabilidades e listas usadas pelas propostas."""

from decimal import Decimal

ZERO = Decimal("0.00")

# Etapas da proposta, na ordem do funil.
RASCUNHO = "rascunho"
EM_APROVACAO = "em_aprovacao"
APROVADA = "aprovada"
ENVIADA = "enviada"
NEGOCIACAO = "negociacao"
GANHA = "ganha"
PERDIDA = "perdida"
CANCELADA = "cancelada"
EXPIRADA = "expirada"

ETAPAS = [
    (RASCUNHO, "Rascunho"),
    (EM_APROVACAO, "Em aprovação"),
    (APROVADA, "Aprovada internamente"),
    (ENVIADA, "Enviada ao cliente"),
    (NEGOCIACAO, "Em negociação"),
    (GANHA, "Ganha"),
    (PERDIDA, "Perdida"),
    (CANCELADA, "Cancelada"),
    (EXPIRADA, "Expirada"),
]
ROTULOS_ETAPA = dict(ETAPAS)

# Abertas: ainda podem virar venda. "Com o cliente": já entregues, contam no pipeline e expiram.
ETAPAS_ABERTAS = (RASCUNHO, EM_APROVACAO, APROVADA, ENVIADA, NEGOCIACAO)
ETAPAS_COM_CLIENTE = (ENVIADA, NEGOCIACAO)
# Decididas pelo cliente: entram na taxa de conversão (cancelada é decisão interna e fica de fora).
ETAPAS_DECIDIDAS = (GANHA, PERDIDA, EXPIRADA)

# Probabilidade de fechamento sugerida ao entrar na etapa (%); o vendedor pode ajustar nas etapas abertas.
PROBABILIDADE_PADRAO = {
    RASCUNHO: 10,
    EM_APROVACAO: 10,
    APROVADA: 20,
    ENVIADA: 40,
    NEGOCIACAO: 60,
    GANHA: 100,
    PERDIDA: 0,
    CANCELADA: 0,
    EXPIRADA: 0,
}

ORIGENS = [
    ("indicacao", "Indicação"),
    ("site", "Site / inbound"),
    ("prospeccao", "Prospecção ativa"),
    ("evento", "Evento / feira"),
    ("cliente", "Cliente da base (recompra)"),
    ("parceiro", "Parceiro"),
    ("outro", "Outro"),
]

MOTIVOS_PERDA = [
    ("preco", "Preço"),
    ("concorrente", "Escolheu um concorrente"),
    ("prazo", "Prazo de entrega"),
    ("escopo", "Solução não atende ao escopo"),
    ("orcamento", "Cliente sem orçamento"),
    ("adiado", "Projeto adiado ou cancelado pelo cliente"),
    ("sem_resposta", "Sem resposta do cliente"),
    ("outro", "Outro"),
]

TIPOS_ITEM = [
    ("servico", "Serviço"),
    ("produto", "Produto"),
    ("licenca", "Licença / assinatura"),
    ("treinamento", "Treinamento"),
]
