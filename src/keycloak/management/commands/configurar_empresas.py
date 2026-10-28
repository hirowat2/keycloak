from django.core.management.base import BaseCommand

from commercial.propostas.empresas_padrao import configurar
from commercial.propostas.sincronizacao import encerrar_interrompidas


class Command(BaseCommand):
    help = (
        "Cria as empresas do grupo que não existem e dá a elas o acesso dos grupos de papel. "
        "Não altera o que já foi configurado. Roda no entrypoint, onde também marca como interrompidas as "
        "sincronizações que o reinício derrubou."
    )

    def handle(self, *args, **options) -> None:
        if interrompidas := encerrar_interrompidas():
            self.stdout.write(f"{interrompidas} sincronização(ões) interrompida(s) pelo reinício.")
        feito = configurar()
        for linha in feito:
            self.stdout.write(linha)
        self.stdout.write(self.style.SUCCESS("Empresas configuradas." if feito else "Empresas já configuradas; nada a fazer."))
