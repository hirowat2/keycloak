from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from .constantes import (
    ETAPAS,
    ETAPAS_ABERTAS,
    ETAPAS_COM_CLIENTE,
    MOTIVOS_PERDA,
    ORIGENS,
    RASCUNHO,
    ROTULOS_ETAPA,
    TIPOS_ITEM,
    ZERO,
)

PAPEL_LIMITED = "Limited"
PAPEL_TECH = "Tech"
PAPEL_MASTER = "Master"
PAPEL_ADMIN = "Admin"
# Do menor para o maior: quem tem um papel pode tudo o que os anteriores podem.
PAPEIS = [
    (PAPEL_LIMITED, "Limited — só consulta"),
    (PAPEL_TECH, "Tech — vendedor: cadastra clientes e cria, envia e fecha propostas"),
    (PAPEL_MASTER, "Master — gestor: também aprova descontos e mantém o catálogo"),
]

CENTAVO = Decimal("0.01")
PERCENTUAL = [MinValueValidator(0), MaxValueValidator(100)]


class Empresa(models.Model):
    """Empresa que emite as propostas. Cada uma tem clientes, catálogo, propostas e numeração próprios."""

    nome = models.CharField("Nome", max_length=150, help_text="Exibido no menu, no topo e no título das páginas.")
    slug = models.SlugField(
        "Identificador", max_length=50, unique=True,
        help_text="Nome curto, sem espaços, usado nos comandos (ex.: --empresa mbrl).",
    )
    ativa = models.BooleanField("Ativa", default=True)
    razao_social = models.CharField("Razão social", max_length=200, blank=True)
    cnpj = models.CharField("CNPJ", max_length=20, blank=True)
    endereco = models.TextField("Endereço", blank=True)
    telefone = models.CharField("Telefone", max_length=40, blank=True)
    email = models.EmailField("E-mail comercial", blank=True)
    site = models.URLField("Site", blank=True)
    prefixo = models.CharField(
        "Prefixo da numeração", max_length=10, default="PC",
        help_text="As propostas são numeradas por ano: PC-2026-0001, PC-2026-0002…",
    )
    validade_dias = models.PositiveSmallIntegerField(
        "Validade padrão (dias)", default=30, help_text="Validade sugerida para propostas novas e ao enviar."
    )
    desconto_maximo = models.DecimalField(
        "Desconto máximo sem aprovação (%)", max_digits=5, decimal_places=2, default=Decimal("10"),
        validators=PERCENTUAL,
        help_text="Acima deste desconto sobre o preço de tabela, a proposta precisa da aprovação de um Master.",
    )
    condicoes_pagamento = models.CharField("Condições de pagamento padrão", max_length=255, blank=True)
    termos = models.TextField(
        "Termos e condições gerais", blank=True, help_text="Impressos no final de toda proposta desta empresa."
    )
    sharepoint_site = models.URLField(
        "Site do SharePoint", max_length=500, blank=True,
        help_text="Ex.: https://estatcamp.sharepoint.com/sites/propostasestatcamp. Em branco, a empresa não sincroniza.",
    )
    sharepoint_pasta = models.TextField(
        "Pastas das propostas", blank=True, default="01 - Propostas",
        help_text="Uma por linha, na biblioteca principal do site, cada uma com uma subpasta por ano e, dentro dela, "
        "uma por cliente. Opcional: a faixa de anos lida em cada pasta (ex.: \"Propostas_antigas: 2016-2020\" e "
        "\"01 - Propostas: 2021-\").",
    )
    sharepoint_controle = models.CharField(
        "Pasta das planilhas de controle", max_length=255, blank=True, default="02 - Controle de Propostas",
        help_text="Planilhas por ano (serviço, número, empresa, data, responsável); completam o que o .docx não traz.",
    )
    sharepoint_contratos = models.TextField(
        "Pastas de contratos", blank=True, default="",
        help_text="Pastas com contratos e documentos assinados fora das pastas de clientes, uma por linha "
        "(ex.: CONTRATOS_OUT 2023). Entram no acervo e na tela de contratos.",
    )
    sharepoint_controle_contratos = models.CharField(
        "Planilha de controle de contratos", max_length=500, blank=True,
        help_text="Caminho da planilha com a carteira de contratos (ex.: Contratos de Clientes/Controle de Contratos.xlsx).",
    )
    sharepoint_desde = models.PositiveSmallIntegerField(
        "Sincronizar a partir do ano", default=2021, help_text="Anos anteriores ficam de fora em todas as pastas.",
    )
    sincronizado_em = models.DateTimeField("Última sincronização", null=True, blank=True, editable=False)

    class Meta:
        app_label = "commercial"
        ordering = ("nome",)
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

    def __str__(self) -> str:
        return self.nome


class AcessoEmpresa(models.Model):
    """Dá aos membros de um grupo acesso a uma empresa, com um papel.

    Quem está em mais de um grupo com acesso à mesma empresa fica com o maior
    papel. O grupo Admin e os superusuários veem todas as empresas.
    """

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="acessos", verbose_name="Empresa")
    grupo = models.ForeignKey(
        "auth.Group", on_delete=models.CASCADE, related_name="acessos_empresa", verbose_name="Grupo"
    )
    papel = models.CharField("Papel", max_length=10, choices=PAPEIS, default=PAPEL_LIMITED)

    class Meta:
        app_label = "commercial"
        ordering = ("empresa__nome", "grupo__name")
        verbose_name = "Acesso à empresa"
        verbose_name_plural = "Acessos às empresas"
        constraints = [models.UniqueConstraint(fields=("empresa", "grupo"), name="acesso_empresa_grupo_unico")]

    def __str__(self) -> str:
        return f"{self.grupo} → {self.empresa} ({self.papel})"


def _empresa_fk(related_name: str) -> models.ForeignKey:
    return models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name=related_name, verbose_name="Empresa")


def _mesma_empresa(objeto, **relacionados) -> None:
    """Erro de validação se algum objeto relacionado for de outra empresa."""
    erros = {
        campo: "Escolha um registro da mesma empresa."
        for campo, outro in relacionados.items()
        if outro is not None and objeto.empresa_id and outro.empresa_id != objeto.empresa_id
    }
    if erros:
        raise ValidationError(erros)


class Cliente(models.Model):
    """Conta (empresa ou pessoa) para quem as propostas são feitas."""

    empresa = _empresa_fk("clientes")
    nome = models.CharField("Razão social / nome", max_length=200)
    nome_fantasia = models.CharField("Nome fantasia", max_length=200, blank=True)
    documento = models.CharField("CNPJ / CPF", max_length=20, blank=True)
    segmento = models.CharField("Segmento", max_length=100, blank=True)
    cidade = models.CharField("Cidade", max_length=100, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    email = models.EmailField("E-mail", blank=True)
    telefone = models.CharField("Telefone", max_length=40, blank=True)
    observacoes = models.TextField("Observações", blank=True)
    ativo = models.BooleanField("Ativo", default=True)
    criado_em = models.DateTimeField("Cadastrado em", auto_now_add=True)
    nomes_sharepoint = models.TextField(
        "Pastas no SharePoint", blank=True,
        help_text="Nomes das pastas deste cliente no SharePoint, um por linha (ex.: EUROFARMA, eurofarma). "
        "A sincronização liga as propostas dessas pastas a este cliente, mesmo que ele seja renomeado aqui.",
    )

    class Meta:
        app_label = "commercial"
        ordering = ("nome",)
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        constraints = [
            models.UniqueConstraint(
                fields=("empresa", "documento"), condition=~Q(documento=""), name="cliente_documento_unico"
            )
        ]

    def __str__(self) -> str:
        return self.nome_fantasia or self.nome


class Contato(models.Model):
    """Pessoa do cliente que recebe a proposta."""

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="contatos", verbose_name="Cliente")
    nome = models.CharField("Nome", max_length=150)
    cargo = models.CharField("Cargo", max_length=100, blank=True)
    email = models.EmailField("E-mail", blank=True)
    telefone = models.CharField("Telefone", max_length=40, blank=True)
    principal = models.BooleanField("Principal", default=False)

    class Meta:
        app_label = "commercial"
        ordering = ("-principal", "nome")
        verbose_name = "Contato"
        verbose_name_plural = "Contatos"

    def __str__(self) -> str:
        return f"{self.nome} ({self.cargo})" if self.cargo else self.nome


class ItemCatalogo(models.Model):
    """Produto ou serviço vendido, com o preço de tabela usado como referência dos descontos."""

    empresa = _empresa_fk("catalogo")
    codigo = models.CharField("Código", max_length=30, blank=True)
    nome = models.CharField("Nome", max_length=200)
    descricao = models.TextField("Descrição", blank=True, help_text="Texto sugerido para o item na proposta.")
    tipo = models.CharField("Tipo", max_length=15, choices=TIPOS_ITEM, default=TIPOS_ITEM[0][0])
    unidade = models.CharField("Unidade", max_length=20, default="un", help_text="Ex.: un, h, mês, licença.")
    preco = models.DecimalField("Preço de tabela", max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    ativo = models.BooleanField("Ativo", default=True)

    class Meta:
        app_label = "commercial"
        ordering = ("nome",)
        verbose_name = "Item do catálogo"
        verbose_name_plural = "Catálogo de produtos e serviços"
        constraints = [
            models.UniqueConstraint(fields=("empresa", "codigo"), condition=~Q(codigo=""), name="catalogo_codigo_unico")
        ]

    def __str__(self) -> str:
        return f"{self.codigo} — {self.nome}" if self.codigo else self.nome


class Proposta(models.Model):
    """Proposta comercial. Só o rascunho é editável; mudar uma proposta já enviada gera uma revisão."""

    empresa = _empresa_fk("propostas")
    ano = models.PositiveSmallIntegerField("Ano", editable=False)
    numero = models.PositiveIntegerField("Número", editable=False)
    revisao = models.PositiveSmallIntegerField("Revisão", default=0, editable=False)
    titulo = models.CharField("Título", max_length=200, help_text="Ex.: Implantação do sistema de qualidade.")
    servico = models.CharField("Serviço", max_length=150, blank=True, help_text="Ex.: Perfil de dissolução, RDC 318.")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="propostas", verbose_name="Cliente")
    contato = models.ForeignKey(
        Contato, on_delete=models.SET_NULL, null=True, blank=True, related_name="propostas", verbose_name="Contato"
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="propostas", verbose_name="Responsável",
    )
    origem = models.CharField("Origem", max_length=15, choices=ORIGENS, blank=True)
    etapa = models.CharField("Etapa", max_length=15, choices=ETAPAS, default=RASCUNHO, db_index=True)
    probabilidade = models.PositiveSmallIntegerField(
        "Probabilidade (%)", default=10, validators=[MaxValueValidator(100)],
        help_text="Chance de fechar. Muda com a etapa; ajuste se souber mais.",
    )
    validade = models.DateField("Válida até", null=True, blank=True)
    enviada_em = models.DateField("Enviada em", null=True, blank=True)
    fechada_em = models.DateField("Fechada em", null=True, blank=True)
    previsao_fechamento = models.DateField("Previsão de fechamento", null=True, blank=True)
    escopo = models.TextField("Apresentação e escopo", blank=True, help_text="Impresso na proposta, antes dos itens.")
    condicoes_pagamento = models.CharField("Condições de pagamento", max_length=255, blank=True)
    prazo_entrega = models.CharField("Prazo de entrega / execução", max_length=255, blank=True)
    observacoes = models.TextField("Observações internas", blank=True, help_text="Não saem na proposta impressa.")
    proxima_acao = models.CharField("Próxima ação", max_length=200, blank=True, help_text="Ex.: ligar para o comprador.")
    proxima_acao_em = models.DateField("Data da próxima ação", null=True, blank=True)
    motivo_perda = models.CharField("Motivo da perda", max_length=15, choices=MOTIVOS_PERDA, blank=True)
    concorrente = models.CharField("Concorrente", max_length=150, blank=True)
    comentario_fechamento = models.TextField("Comentário do fechamento", blank=True)
    valor_referencia = models.DecimalField(
        "Valor a preço de tabela", max_digits=16, decimal_places=2, default=ZERO, editable=False
    )
    valor_total = models.DecimalField("Valor total", max_digits=16, decimal_places=2, default=ZERO, editable=False)
    aprovada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="propostas_aprovadas", verbose_name="Aprovada por",
    )
    aprovada_em = models.DateTimeField("Aprovada em", null=True, blank=True, editable=False)
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="propostas_criadas", verbose_name="Criada por",
    )
    criada_em = models.DateTimeField("Criada em", auto_now_add=True)
    atualizada_em = models.DateTimeField("Atualizada em", auto_now=True)
    # Propostas importadas do SharePoint: documento principal (última revisão) e a pasta do cliente.
    sharepoint_item = models.CharField("Documento no SharePoint", max_length=100, blank=True, editable=False)
    sharepoint_versao = models.CharField("Versão do documento", max_length=200, blank=True, editable=False)
    sharepoint_pasta_url = models.URLField("Pasta no SharePoint", max_length=1000, blank=True, editable=False)
    importada_em = models.DateTimeField("Importada em", null=True, blank=True, editable=False)
    assinada_por = models.CharField("Assinada por (documento)", max_length=150, blank=True, editable=False)

    class Meta:
        app_label = "commercial"
        ordering = ("-ano", "-numero")
        verbose_name = "Proposta"
        verbose_name_plural = "Propostas"
        constraints = [models.UniqueConstraint(fields=("empresa", "ano", "numero"), name="proposta_numero_unico")]
        indexes = [models.Index(fields=("empresa", "etapa"))]

    def __str__(self) -> str:
        return f"{self.codigo} — {self.titulo}"

    def clean(self) -> None:
        _mesma_empresa(self, cliente=self.cliente if self.cliente_id else None)
        if self.contato_id and self.cliente_id and self.contato.cliente_id != self.cliente_id:
            raise ValidationError({"contato": "Escolha um contato deste cliente."})

    @property
    def codigo(self) -> str:
        """PC-2026-0007, ou PC-2026-0007-R2 a partir da segunda revisão."""
        base = f"{self.empresa.prefixo}-{self.ano}-{self.numero:04d}"
        return f"{base}-R{self.revisao}" if self.revisao else base

    @property
    def numero_curto(self) -> str:
        """Como a equipe escreve nos arquivos e na planilha: 021/26."""
        return f"{self.numero:03d}/{self.ano % 100:02d}"

    @property
    def importada(self) -> bool:
        return bool(self.sharepoint_item)

    @property
    def rotulo_etapa(self) -> str:
        return ROTULOS_ETAPA[self.etapa]

    @property
    def editavel(self) -> bool:
        return self.etapa == RASCUNHO

    @property
    def aberta(self) -> bool:
        return self.etapa in ETAPAS_ABERTAS

    @property
    def com_cliente(self) -> bool:
        return self.etapa in ETAPAS_COM_CLIENTE

    @property
    def desconto(self) -> Decimal:
        """Desconto total sobre o preço de tabela (%)."""
        if not self.valor_referencia:
            return ZERO
        return ((1 - self.valor_total / self.valor_referencia) * 100).quantize(CENTAVO, ROUND_HALF_UP)

    @property
    def precisa_aprovacao(self) -> bool:
        return self.desconto > self.empresa.desconto_maximo

    @property
    def valor_ponderado(self) -> Decimal:
        return (self.valor_total * self.probabilidade / 100).quantize(CENTAVO, ROUND_HALF_UP)

    def dias_para_vencer(self, hoje: date) -> int | None:
        return (self.validade - hoje).days if self.validade else None

    def acao_atrasada(self, hoje: date) -> bool:
        return self.aberta and bool(self.proxima_acao_em) and self.proxima_acao_em < hoje


class ItemProposta(models.Model):
    """Linha da proposta. O preço de tabela é copiado do catálogo e serve de referência para o desconto."""

    proposta = models.ForeignKey(Proposta, on_delete=models.CASCADE, related_name="itens", verbose_name="Proposta")
    ordem = models.PositiveSmallIntegerField("Ordem", default=0)
    item_catalogo = models.ForeignKey(
        ItemCatalogo, on_delete=models.SET_NULL, null=True, blank=True, related_name="itens_proposta",
        verbose_name="Item do catálogo",
    )
    descricao = models.CharField("Descrição", max_length=255)
    detalhes = models.TextField("Detalhes", blank=True)
    unidade = models.CharField("Unidade", max_length=20, default="un")
    quantidade = models.DecimalField(
        "Quantidade", max_digits=12, decimal_places=2, default=Decimal("1"), validators=[MinValueValidator(Decimal("0.01"))]
    )
    preco_tabela = models.DecimalField("Preço de tabela", max_digits=14, decimal_places=2, default=ZERO, editable=False)
    preco_unitario = models.DecimalField(
        "Preço unitário", max_digits=14, decimal_places=2, validators=[MinValueValidator(0)]
    )
    desconto = models.DecimalField("Desconto (%)", max_digits=5, decimal_places=2, default=ZERO, validators=PERCENTUAL)

    class Meta:
        app_label = "commercial"
        ordering = ("ordem", "pk")
        verbose_name = "Item da proposta"
        verbose_name_plural = "Itens da proposta"

    def __str__(self) -> str:
        return self.descricao

    @property
    def bruto(self) -> Decimal:
        return (self.quantidade * self.preco_unitario).quantize(CENTAVO, ROUND_HALF_UP)

    @property
    def total(self) -> Decimal:
        return (self.bruto * (100 - self.desconto) / 100).quantize(CENTAVO, ROUND_HALF_UP)

    @property
    def referencia(self) -> Decimal:
        """Valor a preço de tabela; sem preço de tabela (item avulso), o próprio preço digitado."""
        preco = max(self.preco_tabela, self.preco_unitario)
        return (self.quantidade * preco).quantize(CENTAVO, ROUND_HALF_UP)


class RevisaoProposta(models.Model):
    """Cópia de uma versão da proposta, guardada quando ela é revisada."""

    proposta = models.ForeignKey(Proposta, on_delete=models.CASCADE, related_name="revisoes", verbose_name="Proposta")
    revisao = models.PositiveSmallIntegerField("Revisão")
    etapa = models.CharField("Etapa na época", max_length=15, choices=ETAPAS)
    valor_total = models.DecimalField("Valor total", max_digits=16, decimal_places=2)
    dados = models.JSONField("Dados da versão")
    motivo = models.TextField("Motivo da revisão", blank=True)
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Revisada por"
    )
    criada_em = models.DateTimeField("Revisada em", auto_now_add=True)

    class Meta:
        app_label = "commercial"
        ordering = ("-revisao",)
        verbose_name = "Revisão da proposta"
        verbose_name_plural = "Revisões da proposta"
        constraints = [models.UniqueConstraint(fields=("proposta", "revisao"), name="revisao_proposta_unica")]

    def __str__(self) -> str:
        return f"{self.proposta} (revisão {self.revisao})"


class EventoProposta(models.Model):
    """Linha do histórico: mudança de etapa, edição, revisão ou anotação de follow-up."""

    CRIADA = "criada"
    EDITADA = "editada"
    ETAPA = "etapa"
    REVISADA = "revisada"
    NOTA = "nota"
    TIPOS = [
        (CRIADA, "Criada"),
        (EDITADA, "Editada"),
        (ETAPA, "Mudança de etapa"),
        (REVISADA, "Revisada"),
        (NOTA, "Anotação"),
    ]

    proposta = models.ForeignKey(Proposta, on_delete=models.CASCADE, related_name="eventos", verbose_name="Proposta")
    tipo = models.CharField("Tipo", max_length=10, choices=TIPOS)
    descricao = models.TextField("Descrição")
    etapa_de = models.CharField("Etapa anterior", max_length=15, choices=ETAPAS, blank=True)
    etapa_para = models.CharField("Nova etapa", max_length=15, choices=ETAPAS, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuário"
    )
    criado_em = models.DateTimeField("Quando", auto_now_add=True)

    class Meta:
        app_label = "commercial"
        ordering = ("-criado_em", "-pk")
        verbose_name = "Evento da proposta"
        verbose_name_plural = "Histórico das propostas"

    def __str__(self) -> str:
        return f"{self.proposta.codigo}: {self.descricao}"


class ArquivoProposta(models.Model):
    """Arquivo do SharePoint ligado à proposta: as versões do documento e os pedidos de compra."""

    DOCUMENTO = "documento"
    PEDIDO = "pedido"
    ANEXO = "anexo"
    TIPOS = [(DOCUMENTO, "Proposta"), (PEDIDO, "Pedido de compra"), (ANEXO, "Anexo")]

    proposta = models.ForeignKey(Proposta, on_delete=models.CASCADE, related_name="arquivos", verbose_name="Proposta")
    tipo = models.CharField("Tipo", max_length=10, choices=TIPOS)
    nome = models.CharField("Nome", max_length=255)
    caminho = models.CharField("Caminho", max_length=1000)
    url = models.URLField("Link", max_length=1000)
    item_id = models.CharField("Item no SharePoint", max_length=100)
    revisao = models.PositiveSmallIntegerField("Revisão", null=True, blank=True)
    tamanho = models.PositiveBigIntegerField("Tamanho (bytes)", default=0)
    modificado_em = models.DateTimeField("Modificado em", null=True, blank=True)

    class Meta:
        app_label = "commercial"
        ordering = ("tipo", "-revisao", "nome")
        verbose_name = "Arquivo da proposta"
        verbose_name_plural = "Arquivos das propostas"
        constraints = [models.UniqueConstraint(fields=("proposta", "item_id"), name="arquivo_proposta_unico")]

    def __str__(self) -> str:
        return self.nome


class ExecucaoSincronizacao(models.Model):
    """Uma rodada de sincronização com o SharePoint: quem pediu, quando e o que aconteceu."""

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="sincronizacoes", verbose_name="Empresa")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Pedida por",
        help_text="Vazio: rodada automática ou pelo comando.",
    )
    simulacao = models.BooleanField("Simulação", default=False)
    inicio = models.DateTimeField("Início", auto_now_add=True)
    fim = models.DateTimeField("Fim", null=True, blank=True)
    criadas = models.PositiveIntegerField("Criadas", default=0)
    atualizadas = models.PositiveIntegerField("Atualizadas", default=0)
    sem_mudanca = models.PositiveIntegerField("Sem mudança", default=0)
    ganhas = models.PositiveIntegerField("Ganhas por pedido", default=0)
    expiradas = models.PositiveIntegerField("Expiradas", default=0)
    arquivos = models.PositiveIntegerField("Arquivos no acervo", default=0)
    conflitos = models.JSONField("Conflitos", default=list, blank=True)
    avisos = models.JSONField("Avisos", default=list, blank=True)
    erro = models.TextField("Erro", blank=True)

    class Meta:
        app_label = "commercial"
        ordering = ("-inicio",)
        verbose_name = "Execução da sincronização"
        verbose_name_plural = "Execuções da sincronização"

    def __str__(self) -> str:
        return f"{self.empresa} {self.inicio:%d/%m/%Y %H:%M}"

    @property
    def em_andamento(self) -> bool:
        return self.fim is None

    @property
    def duracao(self):
        return (self.fim - self.inicio) if self.fim else None

    @property
    def situacao(self) -> str:
        if self.fim is None:
            return "em andamento"
        if self.erro:
            return "erro"
        return "simulação" if self.simulacao else "concluída"


class ArquivoSharePoint(models.Model):
    """Acervo: cada arquivo das pastas de propostas e de contratos no SharePoint, classificado pelo nome."""

    PROPOSTA = "proposta"
    PEDIDO = "pedido"
    CONTRATO = "contrato"
    NDA = "nda"
    CADASTRO = "cadastro"
    FISCAL = "fiscal"
    DADOS = "dados"
    OUTRO = "outro"
    CATEGORIAS = [
        (PROPOSTA, "Proposta"),
        (PEDIDO, "Pedido de compra"),
        (CONTRATO, "Contrato / aditivo"),
        (NDA, "Confidencialidade (NDA)"),
        (CADASTRO, "Cadastro de fornecedor / certidões"),
        (FISCAL, "Nota fiscal / cobrança"),
        (DADOS, "Planilha / dados"),
        (OUTRO, "Outro"),
    ]
    CONTRATUAIS = (PEDIDO, CONTRATO, NDA)

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="acervo", verbose_name="Empresa")
    item_id = models.CharField("Item no SharePoint", max_length=100)
    nome = models.CharField("Nome", max_length=255)
    caminho = models.CharField("Caminho", max_length=1000)
    url = models.URLField("Link", max_length=1000)
    pasta_raiz = models.CharField("Pasta", max_length=255)
    ano = models.PositiveSmallIntegerField("Ano", null=True, blank=True, db_index=True)
    pasta_cliente = models.CharField("Pasta do cliente", max_length=255, blank=True)
    cliente = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name="arquivos", verbose_name="Cliente"
    )
    proposta = models.ForeignKey(
        Proposta, on_delete=models.SET_NULL, null=True, blank=True, related_name="acervo", verbose_name="Proposta"
    )
    categoria = models.CharField("Categoria", max_length=10, choices=CATEGORIAS, db_index=True)
    extensao = models.CharField("Extensão", max_length=10, blank=True)
    tamanho = models.PositiveBigIntegerField("Tamanho (bytes)", default=0)
    modificado_em = models.DateTimeField("Modificado em", null=True, blank=True)

    class Meta:
        app_label = "commercial"
        ordering = ("-ano", "pasta_cliente", "nome")
        verbose_name = "Arquivo do acervo"
        verbose_name_plural = "Acervo do SharePoint"
        constraints = [models.UniqueConstraint(fields=("empresa", "item_id"), name="acervo_item_unico")]

    def __str__(self) -> str:
        return self.caminho


def _caminho_documento(instancia, nome: str) -> str:
    return f"empresas/{instancia.empresa.slug}/{nome}"


class DocumentoEmpresa(models.Model):
    """Documento da própria empresa pedido em cadastros de fornecedor e enviado com propostas."""

    CARTAO_CNPJ = "cartao_cnpj"
    CONTRATO_SOCIAL = "contrato_social"
    CERTIDAO = "certidao"
    OUTRO = "outro"
    TIPOS = [
        (CARTAO_CNPJ, "Cartão CNPJ"),
        (CONTRATO_SOCIAL, "Contrato social / alteração"),
        (CERTIDAO, "Certidão negativa"),
        (OUTRO, "Outro"),
    ]
    # Prazo em que cadastros de fornecedor costumam aceitar o documento (dias desde a emissão).
    VALIDADE_USUAL = {CARTAO_CNPJ: 90, CERTIDAO: 180}

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="documentos", verbose_name="Empresa")
    tipo = models.CharField("Tipo", max_length=20, choices=TIPOS)
    nome = models.CharField("Nome", max_length=200)
    arquivo = models.FileField("Arquivo", upload_to=_caminho_documento)
    emitido_em = models.DateField("Emitido em", null=True, blank=True, help_text="Lido do PDF quando possível.")
    validade = models.DateField("Válido até", null=True, blank=True)
    sharepoint_link = models.URLField(
        "Link no SharePoint", max_length=1000, blank=True,
        help_text="Com o link, a sincronização baixa de novo o arquivo quando ele muda no SharePoint.",
    )
    sharepoint_versao = models.CharField("Versão no SharePoint", max_length=200, blank=True, editable=False)
    dados = models.JSONField("Dados lidos do documento", default=dict, blank=True, editable=False)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        app_label = "commercial"
        ordering = ("tipo", "-emitido_em")
        verbose_name = "Documento da empresa"
        verbose_name_plural = "Documentos da empresa"

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — {self.empresa}"

    def vencido(self, hoje) -> bool:
        """Fora da validade informada ou, sem ela, emitido há mais tempo que o usual para o tipo."""
        if self.validade:
            return self.validade < hoje
        dias = self.VALIDADE_USUAL.get(self.tipo)
        return bool(dias and self.emitido_em and (hoje - self.emitido_em).days > dias)


class ContratoCliente(models.Model):
    """Linha da planilha de controle de contratos: a carteira de contratos, pedidos e NDAs em vigor."""

    PARADO = "parado"
    ANDAMENTO = "andamento"
    ENCERRADO = "encerrado"
    DESCOMISSIONADO = "descomissionado"
    SITUACOES = [
        (ANDAMENTO, "Em andamento"),
        (PARADO, "Parado"),
        (DESCOMISSIONADO, "Descomissionamento"),
        (ENCERRADO, "Encerrado"),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="contratos", verbose_name="Empresa")
    cliente = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name="contratos", verbose_name="Cliente"
    )
    cliente_nome = models.CharField("Cliente (planilha)", max_length=200)
    sistema = models.CharField("Sistema / módulo", max_length=255, blank=True)
    situacao = models.CharField("Situação", max_length=15, choices=SITUACOES, blank=True)
    ativo = models.BooleanField("Cliente ativo", null=True, blank=True)
    responsavel = models.TextField("Responsável pelo contrato", blank=True)
    em_nome_de = models.CharField("Em nome de", max_length=150, blank=True)
    assinado = models.CharField("Assinado", max_length=100, blank=True)
    vencimento = models.DateField("Vencimento", null=True, blank=True, db_index=True)
    fechamento = models.DateField("Fechamento", null=True, blank=True)
    historico = models.TextField("Contrato, aditivos e pedidos", blank=True)
    observacao = models.TextField("Observação", blank=True)
    link = models.URLField("Link do contrato", max_length=1000, blank=True)
    valor_licenciamento = models.DecimalField("Licenciamento", max_digits=14, decimal_places=2, null=True, blank=True)
    valor_hospedagem = models.DecimalField("Hospedagem", max_digits=14, decimal_places=2, null=True, blank=True)
    valor_total = models.DecimalField("Total", max_digits=14, decimal_places=2, null=True, blank=True)
    linha = models.PositiveIntegerField("Linha na planilha")

    class Meta:
        app_label = "commercial"
        ordering = ("cliente_nome", "linha")
        verbose_name = "Contrato de cliente"
        verbose_name_plural = "Carteira de contratos"

    def __str__(self) -> str:
        return f"{self.cliente_nome} — {self.sistema}"

    def dias_para_vencer(self, hoje) -> int | None:
        return (self.vencimento - hoje).days if self.vencimento else None
