from django.contrib import admin

from .models import (
    AcessoEmpresa,
    ArquivoProposta,
    DocumentoEmpresa,
    Cliente,
    Contato,
    Empresa,
    EventoProposta,
    ExecucaoSincronizacao,
    ItemCatalogo,
    ItemProposta,
    Proposta,
    RevisaoProposta,
)
from .servicos import recalcular


class AcessoEmpresaInline(admin.TabularInline):
    model = AcessoEmpresa
    extra = 1
    autocomplete_fields = ("grupo",)
    verbose_name_plural = "Grupos com acesso (o grupo Admin e os superusuários veem todas as empresas)"


class DocumentoEmpresaInline(admin.TabularInline):
    model = DocumentoEmpresa
    extra = 0
    fields = ("tipo", "nome", "arquivo", "emitido_em", "validade", "sharepoint_link")
    verbose_name_plural = "Documentos da empresa (cartão CNPJ, contrato social, certidões)"


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "prefixo", "validade_dias", "desconto_maximo", "ativa")
    list_filter = ("ativa",)
    search_fields = ("nome", "slug", "razao_social", "cnpj")
    prepopulated_fields = {"slug": ("nome",)}
    inlines = [AcessoEmpresaInline, DocumentoEmpresaInline]
    fieldsets = (
        (None, {"fields": ("nome", "slug", "ativa")}),
        ("Dados impressos na proposta", {"fields": ("razao_social", "cnpj", "endereco", "telefone", "email", "site")}),
        (
            "Regras comerciais",
            {"fields": ("prefixo", "validade_dias", "desconto_maximo", "condicoes_pagamento", "termos")},
        ),
        (
            "SharePoint",
            {
                "description": "Credenciais do app (tenant, client id e segredo) vêm do ambiente, comuns a todas as empresas.",
                "fields": (
                    "sharepoint_site", "sharepoint_pasta", "sharepoint_controle", "sharepoint_contratos",
                    "sharepoint_desde", "sincronizado_em",
                ),
            },
        ),
    )
    readonly_fields = ("sincronizado_em",)


class ContatoInline(admin.TabularInline):
    model = Contato
    extra = 0


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nome", "nome_fantasia", "documento", "segmento", "cidade", "uf", "empresa", "ativo")
    list_filter = ("empresa", "ativo", "segmento", "uf")
    search_fields = ("nome", "nome_fantasia", "documento", "email")
    inlines = [ContatoInline]


@admin.register(ItemCatalogo)
class ItemCatalogoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "tipo", "unidade", "preco", "empresa", "ativo")
    list_editable = ("preco", "ativo")
    list_filter = ("empresa", "tipo", "ativo")
    search_fields = ("codigo", "nome")


class ItemPropostaInline(admin.TabularInline):
    model = ItemProposta
    extra = 0
    fields = ("ordem", "item_catalogo", "descricao", "unidade", "quantidade", "preco_tabela", "preco_unitario", "desconto")
    readonly_fields = ("preco_tabela",)
    autocomplete_fields = ("item_catalogo",)


class ArquivoPropostaInline(admin.TabularInline):
    model = ArquivoProposta
    extra = 0
    fields = ("tipo", "nome", "revisao", "url", "modificado_em")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False


class EventoPropostaInline(admin.TabularInline):
    model = EventoProposta
    extra = 0
    fields = ("criado_em", "tipo", "descricao", "usuario")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Proposta)
class PropostaAdmin(admin.ModelAdmin):
    """Correções pontuais. Etapa e numeração mudam só pelo sistema, que registra o histórico."""

    list_display = ("codigo", "titulo", "cliente", "etapa", "valor_total", "validade", "responsavel", "empresa")
    list_filter = ("empresa", "etapa", "origem", "responsavel", ("importada_em", admin.EmptyFieldListFilter))
    search_fields = ("titulo", "cliente__nome", "cliente__nome_fantasia", "numero")
    date_hierarchy = "criada_em"
    autocomplete_fields = ("cliente",)
    readonly_fields = (
        "etapa", "ano", "numero", "revisao", "valor_referencia", "valor_total", "aprovada_por", "aprovada_em",
        "enviada_em", "fechada_em", "criada_por", "criada_em", "sharepoint_item", "sharepoint_versao",
        "sharepoint_pasta_url", "importada_em",
    )
    inlines = [ItemPropostaInline, ArquivoPropostaInline, EventoPropostaInline]

    def has_add_permission(self, request) -> bool:
        return False

    def save_related(self, request, form, formsets, change) -> None:
        super().save_related(request, form, formsets, change)
        recalcular(form.instance)


@admin.register(RevisaoProposta)
class RevisaoPropostaAdmin(admin.ModelAdmin):
    list_display = ("proposta", "revisao", "etapa", "valor_total", "criada_por", "criada_em")
    list_filter = ("proposta__empresa",)
    readonly_fields = ("proposta", "revisao", "etapa", "valor_total", "dados", "motivo", "criada_por", "criada_em")

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(AcessoEmpresa)
class AcessoEmpresaAdmin(admin.ModelAdmin):
    list_display = ("empresa", "grupo", "papel")
    list_filter = ("empresa", "papel")
    autocomplete_fields = ("grupo",)


@admin.register(ExecucaoSincronizacao)
class ExecucaoSincronizacaoAdmin(admin.ModelAdmin):
    list_display = ("empresa", "inicio", "fim", "usuario", "simulacao", "criadas", "atualizadas", "ganhas", "expiradas")
    list_filter = ("empresa", "simulacao")
    readonly_fields = [f.name for f in ExecucaoSincronizacao._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False
