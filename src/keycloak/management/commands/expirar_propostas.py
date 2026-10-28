from django.core.management.base import BaseCommand

from commercial.management.empresa import adicionar_opcao, alvos
from commercial.propostas.servicos import expirar_vencidas


class Command(BaseCommand):
    help = (
        "Marca como expiradas as propostas enviadas ou em negociação cuja validade passou. "
        "As telas já fazem isso ao abrir; o comando serve para agendar (cron) e manter o painel em dia."
    )

    def add_arguments(self, parser) -> None:
        adicionar_opcao(parser, "Slug da empresa; sem ele, todas as ativas.")

    def handle(self, *args, **options) -> None:
        for empresa in alvos(options["empresa"]):
            vencidas = expirar_vencidas(empresa)
            for proposta in vencidas:
                self.stdout.write(f"{empresa.slug}: {proposta.codigo} expirada.")
        self.stdout.write(self.style.SUCCESS("Validades conferidas."))
