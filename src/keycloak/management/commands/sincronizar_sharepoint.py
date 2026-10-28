from django.core.management.base import BaseCommand, CommandError

from commercial.management.empresa import adicionar_opcao, alvos
from commercial.propostas.sharepoint import SharePointErro
from commercial.propostas.sincronizacao import sincronizar


class Command(BaseCommand):
    help = (
        "Importa e atualiza as propostas a partir da biblioteca do SharePoint de cada empresa (só leitura no "
        "SharePoint). Bom para agendar; a tela de propostas tem o mesmo botão para o Master."
    )

    def add_arguments(self, parser) -> None:
        adicionar_opcao(parser, "Slug da empresa; sem ele, todas as ativas com site do SharePoint.")
        parser.add_argument("--simular", action="store_true", help="Mostra o que seria feito e desfaz tudo.")

    def handle(self, *args, **options) -> None:
        empresas = [e for e in alvos(options["empresa"]) if e.sharepoint_site]
        if not empresas:
            raise CommandError("Nenhuma empresa com site do SharePoint (Administração → Empresas).")
        falhas = []
        for empresa in empresas:
            try:
                relatorio = sincronizar(empresa, simular=options["simular"])
            except SharePointErro as erro:  # uma empresa com problema não impede as outras
                falhas.append(f"{empresa.slug}: {erro}")
                self.stderr.write(self.style.ERROR(falhas[-1]))
                continue
            prefixo = "[simulação] " if options["simular"] else ""
            self.stdout.write(self.style.SUCCESS(f"{prefixo}{empresa.slug}: {relatorio.resumo()}"))
            for linha in relatorio.conflitos:
                self.stdout.write(self.style.WARNING(f"  conflito: {linha}"))
            for linha in relatorio.avisos:
                self.stdout.write(f"  aviso: {linha}")
        if falhas:
            raise CommandError(f"{len(falhas)} empresa(s) não sincronizada(s).")
