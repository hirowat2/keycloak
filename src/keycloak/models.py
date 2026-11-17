from django.conf import settings
from django.db import models


class Aplicacao(models.Model):
    """Cada vez que uma etapa foi simulada ou aplicada no Keycloak, com o plano resultante."""

    REALM, GRUPOS, SSO, MAPEAMENTO, HOST, DUMP = "realm", "grupos", "sso", "mapeamento", "host", "dump"
    ETAPAS = [
        (REALM, "1 · Realm e apps"),
        (GRUPOS, "2 · Grupos e roles"),
        (SSO, "3 · SSO SAML"),
        (MAPEAMENTO, "4 · Grupos do SSO"),
        (HOST, "Migração · host novo"),
        (DUMP, "Banco do Keycloak"),
    ]

    criado_em = models.DateTimeField("Quando", auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Usuário", null=True, on_delete=models.SET_NULL)
    servidor = models.CharField("Keycloak", max_length=255)
    realm = models.CharField("Realm", max_length=255)
    etapa = models.CharField("Etapa", max_length=20, choices=ETAPAS)
    simulacao = models.BooleanField("Só simulação", default=False)
    sucesso = models.BooleanField("Sucesso", default=True)
    mudancas = models.PositiveIntegerField("Mudanças", default=0)
    passos = models.JSONField("Passos", default=list, blank=True)
    erro = models.TextField("Erro", blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "aplicação"
        verbose_name_plural = "histórico de aplicações"

    def __str__(self) -> str:
        return f"{self.get_etapa_display()} em {self.realm} ({self.criado_em:%d/%m/%Y %H:%M})"


class Servidor(models.Model):
    """Um Keycloak que o assistente administra, cadastrado na tela Servidores (o segredo fica cifrado)."""

    nome = models.CharField("Nome", max_length=100, unique=True)
    # CharField: o URLValidator recusaria hosts sem domínio (http://keycloak:8080); a tela valida
    url = models.CharField("URL pública", max_length=255)
    url_interna = models.CharField("URL interna", max_length=255, blank=True)
    usa_client = models.BooleanField("Service account", default=False)
    usuario = models.CharField("Admin do master", max_length=150, blank=True)
    client_id = models.CharField("Client ID", max_length=150, default="admin-cli")
    segredo = models.TextField("Senha ou secret (cifrado)", blank=True)
    verificar_tls = models.BooleanField("Verificar o certificado", default=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Criado por", null=True, blank=True,
                                   on_delete=models.SET_NULL)

    class Meta:
        ordering = ["nome"]
        verbose_name = "servidor Keycloak"
        verbose_name_plural = "servidores Keycloak"

    def __str__(self) -> str:
        return f"{self.nome} ({self.url})"
