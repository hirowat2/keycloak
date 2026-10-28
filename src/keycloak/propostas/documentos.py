"""Documentos da própria empresa (cartão CNPJ, contrato social, certidões) vindos do SharePoint.

O documento é anexado pelo link de compartilhamento; a sincronização baixa de novo quando o
arquivo muda lá (``cTag``). Do cartão CNPJ (comprovante da Receita Federal) são lidos o CNPJ, o
nome empresarial, o endereço e a data de emissão, que preenchem os campos da empresa em branco.
"""

import io
import re
from datetime import date, datetime

from django.core.files.base import ContentFile

from .models import DocumentoEmpresa, Empresa
from .sharepoint import SharePointClient, SharePointErro


def texto_pdf(conteudo: bytes) -> str:
    """Texto do PDF; vazio se o pypdf não estiver instalado ou o PDF não tiver texto."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        return "\n".join(pagina.extract_text() or "" for pagina in PdfReader(io.BytesIO(conteudo)).pages)
    except Exception:  # PDF corrompido ou só imagem: o anexo vale assim mesmo
        return ""


def _depois(linhas: list[str], rotulo: str, exato: bool = False) -> str:
    """Valor da linha seguinte ao rótulo (``exato``: a linha é só o rótulo, ex.: "NÚMERO" e não "NÚMERO DE INSCRIÇÃO")."""
    for i, linha in enumerate(linhas):
        texto = linha.strip().upper()
        if (texto == rotulo if exato else texto.startswith(rotulo)) and i + 1 < len(linhas):
            return linhas[i + 1].strip()
    return ""


def ler_cartao_cnpj(texto: str) -> dict:
    """CNPJ, nome empresarial, endereço e emissão do comprovante de inscrição da Receita."""
    dados: dict = {}
    if m := re.search(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b", texto):
        dados["cnpj"] = m.group(1)
    if m := re.search(r"Emitido no dia (\d{2}/\d{2}/\d{4})", texto):
        dados["emitido_em"] = datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat()
    linhas = [linha for linha in texto.splitlines() if linha.strip()]
    if nome := _depois(linhas, "NOME EMPRESARIAL"):
        dados["nome_empresarial"] = nome
    # Cada rótulo vem numa linha e o valor na seguinte (asteriscos: campo vazio).
    campo = {rotulo: valor for rotulo in ("LOGRADOURO", "NÚMERO", "COMPLEMENTO", "BAIRRO/DISTRITO", "MUNICÍPIO", "UF", "CEP")
             if (valor := _depois(linhas, rotulo, exato=True)) and not valor.startswith("*")}
    if campo.get("LOGRADOURO"):
        rua = ", ".join(filter(None, [campo.get("LOGRADOURO"), campo.get("NÚMERO"), campo.get("COMPLEMENTO")]))
        cidade = "/".join(filter(None, [campo.get("MUNICÍPIO"), campo.get("UF")]))
        partes = [rua, campo.get("BAIRRO/DISTRITO"), cidade, f"CEP {campo['CEP']}" if campo.get("CEP") else ""]
        dados["endereco"] = " — ".join(filter(None, partes))
    if email := _depois(linhas, "ENDEREÇO ELETRÔNICO", exato=True):
        dados["email"] = email.lower()
    if telefone := _depois(linhas, "TELEFONE", exato=True):
        dados["telefone"] = telefone
    if m := re.search(r"SITUAÇÃO CADASTRAL\s+DATA DA SITUAÇÃO CADASTRAL\s+(\w+)", texto):
        dados["situacao"] = m.group(1)
    return dados


def _aplicar_na_empresa(empresa: Empresa, dados: dict) -> list[str]:
    """Preenche só os campos em branco da empresa; devolve os preenchidos."""
    preenchidos = []
    for campo, chave in (
        ("cnpj", "cnpj"), ("razao_social", "nome_empresarial"), ("endereco", "endereco"), ("telefone", "telefone"),
    ):
        if dados.get(chave) and not getattr(empresa, campo):
            setattr(empresa, campo, dados[chave])
            preenchidos.append(campo)
    if preenchidos:
        empresa.save(update_fields=preenchidos)
    return preenchidos


def anexar_por_link(
    empresa: Empresa, link: str, tipo: str, cliente: SharePointClient | None = None, nome: str = ""
) -> tuple[DocumentoEmpresa, bool]:
    """Baixa o arquivo do link e guarda como documento da empresa; devolve (documento, se mudou)."""
    cliente = cliente or SharePointClient.criar(empresa.sharepoint_site or link)
    remoto = cliente.por_link(link)
    documento = DocumentoEmpresa.objects.filter(empresa=empresa, sharepoint_link=link).first()
    if documento is not None and documento.sharepoint_versao == remoto.versao and documento.arquivo:
        return documento, False
    conteudo = cliente.baixar_link(link)
    documento = documento or DocumentoEmpresa(empresa=empresa, sharepoint_link=link, tipo=tipo)
    documento.nome = nome or documento.nome or remoto.nome
    documento.sharepoint_versao = remoto.versao
    if tipo == DocumentoEmpresa.CARTAO_CNPJ or documento.tipo == DocumentoEmpresa.CARTAO_CNPJ:
        documento.dados = ler_cartao_cnpj(texto_pdf(conteudo))
        if documento.dados.get("emitido_em"):
            documento.emitido_em = date.fromisoformat(documento.dados["emitido_em"])
        _aplicar_na_empresa(empresa, documento.dados)
    documento.arquivo.save(remoto.nome, ContentFile(conteudo), save=False)
    documento.save()
    return documento, True


def atualizar_documentos(empresa: Empresa, cliente: SharePointClient) -> list[str]:
    """Na sincronização: baixa de novo os documentos cujo arquivo mudou no SharePoint. Devolve avisos."""
    avisos = []
    for documento in empresa.documentos.exclude(sharepoint_link=""):
        try:
            anexar_por_link(empresa, documento.sharepoint_link, documento.tipo, cliente)
        except SharePointErro as erro:
            avisos.append(f"{documento}: não atualizado ({erro}).")
    return avisos
