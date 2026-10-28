from django.core.management.base import BaseCommand, CommandError

from commercial.management.empresa import adicionar_opcao, escolher
from commercial.propostas.documentos import anexar_por_link
from commercial.propostas.models import DocumentoEmpresa
from commercial.propostas.sharepoint import SharePointErro


class Command(BaseCommand):
    help = (
        "Anexa à empresa um documento do SharePoint pelo link de compartilhamento (ex.: o cartão CNPJ). "
        "A sincronização baixa de novo quando o arquivo muda. Do cartão CNPJ, preenche CNPJ, razão social, "
        "endereço e telefone da empresa que estiverem em branco."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("link", help="Link de compartilhamento do arquivo no SharePoint.")
        parser.add_argument("--tipo", default=DocumentoEmpresa.CARTAO_CNPJ, choices=[t for t, _ in DocumentoEmpresa.TIPOS])
        parser.add_argument("--nome", default="", help="Nome exibido (padrão: o nome do arquivo).")
        adicionar_opcao(parser, "Slug da empresa (obrigatório se houver mais de uma).")

    def handle(self, *args, **options) -> None:
        empresa = escolher(options["empresa"])
        try:
            documento, mudou = anexar_por_link(empresa, options["link"], options["tipo"], nome=options["nome"])
        except SharePointErro as erro:
            raise CommandError(str(erro)) from erro
        self.stdout.write(self.style.SUCCESS(f"{documento}: {'anexado' if mudou else 'já estava atualizado'} ({documento.arquivo.name})."))
        if documento.dados:
            self.stdout.write(f"  lido do documento: {documento.dados}")
        elif documento.tipo == DocumentoEmpresa.CARTAO_CNPJ:
            self.stdout.write(self.style.WARNING("  texto do PDF não lido (pypdf ausente ou PDF só imagem): preencha os dados à mão."))
