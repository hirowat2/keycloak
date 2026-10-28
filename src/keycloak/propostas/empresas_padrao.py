"""Empresas do grupo que emitem propostas e onde ficam as propostas de cada uma no SharePoint.

``configurar`` roda a cada inicialização (``docker-entrypoint.sh``) e só completa o que falta:
cria a empresa que não existe; numa que já existe, preenche a configuração do SharePoint só se o
site estiver em branco (o que foi ajustado em Administração → Empresas é mantido). Os acessos dos
grupos de papel entram só na empresa que ainda não tem nenhum.
"""

from dataclasses import dataclass

from django.contrib.auth.models import Group
from django.db import transaction

from .models import AcessoEmpresa, Empresa

PAPEIS = ("Master", "Tech", "Limited")


@dataclass(frozen=True)
class EmpresaPadrao:
    slug: str
    nome: str
    razao_social: str
    prefixo: str
    sharepoint_site: str = ""
    sharepoint_pasta: str = "01 - Propostas"
    sharepoint_controle: str = "02 - Controle de Propostas"
    sharepoint_contratos: str = ""
    sharepoint_controle_contratos: str = ""
    sharepoint_desde: int = 2021


SHAREPOINT = "https://estatcamp.sharepoint.com/sites"
EMPRESAS = [
    EmpresaPadrao(
        slug="mbrlproc-sistemas-ltda", nome="PHARMA / MBRLPROC Sistemas", razao_social="MBRLPROC SISTEMAS LTDA",
        prefixo="MBRL", sharepoint_site=f"{SHAREPOINT}/actionpharma",
        sharepoint_pasta="02 - Propostas Clientes", sharepoint_controle="04 - Controle de Propostas",
        sharepoint_contratos="Contratos de Clientes\nCONTRATOS 2022\n01 - Contrato da Parceria",
        sharepoint_controle_contratos="Contratos de Clientes/Controle de Contratos.xlsx",
    ),
    EmpresaPadrao(
        slug="estatcamp", nome="ESTATCAMP CONSULTORIA ESTATISTICA EM QUALIDADE LTDA",
        razao_social="ESTATCAMP CONSULTORIA ESTATISTICA EM QUALIDADE LTDA", prefixo="EST",
        sharepoint_site=f"{SHAREPOINT}/propostasestatcamp",
        sharepoint_pasta="Propostas_antigas: 2016-2020\n01 - Propostas: 2021-",
        sharepoint_contratos="CONTRATOS_OUT 2023\nDocuSign", sharepoint_desde=2016,
    ),
    EmpresaPadrao(
        slug="action-stat", nome="Action Stat", razao_social="", prefixo="AS", sharepoint_site=f"{SHAREPOINT}/actionstat",
        sharepoint_pasta="03 - Propostas Clientes", sharepoint_controle="04 - Controle de Propostas",
        sharepoint_contratos="01 - Documentos Parceria",
    ),
]
CAMPOS_SHAREPOINT = (
    "sharepoint_site", "sharepoint_pasta", "sharepoint_controle", "sharepoint_contratos", "sharepoint_controle_contratos",
    "sharepoint_desde",
)


@transaction.atomic
def configurar() -> list[str]:
    """Cria ou completa as empresas; devolve o que foi feito (vazio se nada mudou)."""
    feito = []
    grupos = {nome: Group.objects.get_or_create(name=nome)[0] for nome in PAPEIS}
    for padrao in EMPRESAS:
        empresa = Empresa.objects.filter(slug=padrao.slug).first() or Empresa.objects.filter(nome=padrao.nome).first()
        if empresa is None:
            empresa = Empresa.objects.create(
                slug=padrao.slug, nome=padrao.nome, razao_social=padrao.razao_social, prefixo=padrao.prefixo,
                **{campo: getattr(padrao, campo) for campo in CAMPOS_SHAREPOINT},
            )
            feito.append(f"{empresa}: criada.")
        elif padrao.sharepoint_site and not empresa.sharepoint_site:
            for campo in CAMPOS_SHAREPOINT:
                setattr(empresa, campo, getattr(padrao, campo))
            empresa.save(update_fields=list(CAMPOS_SHAREPOINT))
            feito.append(f"{empresa}: SharePoint {padrao.sharepoint_site}.")
        if not empresa.acessos.exists():
            for papel in PAPEIS:
                AcessoEmpresa.objects.create(empresa=empresa, grupo=grupos[papel], papel=papel)
            feito.append(f"{empresa}: acesso dos grupos {', '.join(PAPEIS)}.")
    return feito
