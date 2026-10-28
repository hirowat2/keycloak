"""Escolha da empresa nos comandos de gerenciamento (opção ``--empresa``)."""

from django.core.management.base import CommandError

from commercial.propostas.models import Empresa


def adicionar_opcao(parser, ajuda: str) -> None:
    parser.add_argument("--empresa", default="", help=ajuda)


def _disponiveis() -> str:
    return ", ".join(Empresa.objects.filter(ativa=True).values_list("slug", flat=True)) or "nenhuma cadastrada"


def escolher(slug: str) -> Empresa:
    """A empresa do slug; sem slug, a única empresa ativa (com mais de uma, o slug é obrigatório)."""
    if slug:
        empresa = Empresa.objects.filter(slug=slug).first()
        if empresa is None:
            raise CommandError(f"Empresa '{slug}' não encontrada. Disponíveis: {_disponiveis()}.")
        return empresa
    ativas = list(Empresa.objects.filter(ativa=True)[:2])
    if len(ativas) != 1:
        raise CommandError(f"Informe --empresa. Disponíveis: {_disponiveis()}.")
    return ativas[0]


def alvos(slug: str) -> list[Empresa]:
    """A empresa do slug ou, sem slug, todas as ativas."""
    return [escolher(slug)] if slug else list(Empresa.objects.filter(ativa=True))
