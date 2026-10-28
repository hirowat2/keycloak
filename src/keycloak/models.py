from django.conf import settings
from django.db import models


class Aplicacao(models.Model):
    """Cada vez que uma etapa foi simulada ou aplicada no Keycloak, com o plano resultante."""

    REALM, GRUPOS, SSO, MAPEAMENTO, HOST = "realm", "grupos", "sso", "mapeamento", "host"
    ETAPAS = [
        (REALM, "1 · Realm e apps"),
        (GRUPOS, "2 · Grupos e roles"),
        (SSO, "3 · SSO SAML"),
        (MAPEAMENTO, "4 · Grupos do SSO"),
        (HOST, "Migração · host novo"),
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
