"""Garante o client de login do assistente (KEYCLOAK_CLIENT_ID) e a role ADMIN no realm KEYCLOAK_REALM.

Roda no entrypoint: num realm já importado antes (ex.: o de produção), o client
do assistente não existe, e sem ele ninguém entra. Usa a Admin API, como as telas.
"""
from os import environ

from django.core.management.base import BaseCommand, CommandError

from keycloak.automacao import realm as servico
from keycloak.automacao.api import ErroKeycloak, conexao
from keycloak.automacao.plano import Plano


class Command(BaseCommand):
    help = "Cria (ou acerta) o client de login do assistente e a role ADMIN no realm do login."

    def handle(self, *args, **options) -> None:
        realm, client_id, host = environ.get("KEYCLOAK_REALM"), environ.get("KEYCLOAK_CLIENT_ID"), environ.get("HOST", "")
        if not (realm and client_id and host.startswith("http")):
            raise CommandError("Defina KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID e HOST (URL pública do assistente).")
        api = conexao()
        try:
            if servico.ler_realm(api, realm) is None:
                raise CommandError(f"O realm {realm} não existe no Keycloak em {api.url}.")
            plano = Plano(simular=False)
            servico.garantir_role(api, plano, realm, servico.ROLE_ADMIN, "Administrador: vira superuser nos apps")
            # O keycloak.js volta para a página em que o login começou: callback "/*"
            servico.aplicar_app(api, plano, realm, servico.App(client_id, "Assistente Keycloak", host, callback="/*"))
        except ErroKeycloak as erro:
            raise CommandError(str(erro)) from erro
        for passo in plano.passos:
            self.stdout.write(f"[preparar_login] {passo.rotulo}: {passo.tipo} {passo.alvo} {passo.detalhe}".rstrip())
