"""Cliente mínimo (só leitura) do Microsoft Graph para a biblioteca de propostas no SharePoint.

Usa o fluxo client credentials. O aplicativo no Entra ID precisa das permissões de
aplicação ``Sites.Read.All`` e ``Files.Read.All`` com consentimento do administrador.
As credenciais vêm do ambiente (``SHAREPOINT_TENANT_ID``, ``SHAREPOINT_CLIENT_ID`` e
``SHAREPOINT_CLIENT_SECRET``); o site e as pastas são de cada empresa.
"""

import base64
import os
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote, urlparse

import requests

GRAPH = "https://graph.microsoft.com/v1.0"
CAMPOS = "id,name,size,folder,file,cTag,eTag,webUrl,createdDateTime,lastModifiedDateTime"


class SharePointErro(Exception):
    pass


class NaoEncontrado(SharePointErro):
    """Pasta ou arquivo inexistente (404): a configuração aponta para um caminho que não existe."""


@dataclass(frozen=True)
class ItemRemoto:
    id: str
    nome: str
    caminho: str
    pasta: bool
    versao: str
    url: str
    tamanho: int
    criado: datetime | None
    modificado: datetime | None


def _data(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto.replace("Z", "+00:00")) if texto else None


class SharePointClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, site_url: str, timeout: int = 60) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.site_url = site_url
        self.timeout = timeout
        self._sessao = requests.Session()
        self._drive_id: str | None = None

    @classmethod
    def criar(cls, site_url: str) -> "SharePointClient":
        """Cliente com as credenciais do ambiente para o site informado."""
        obrigatorias = {
            "SHAREPOINT_TENANT_ID": os.environ.get("SHAREPOINT_TENANT_ID", ""),
            "SHAREPOINT_CLIENT_ID": os.environ.get("SHAREPOINT_CLIENT_ID", ""),
            "SHAREPOINT_CLIENT_SECRET": os.environ.get("SHAREPOINT_CLIENT_SECRET", ""),
        }
        faltando = [nome for nome, valor in obrigatorias.items() if not valor]
        if faltando:
            raise SharePointErro("SharePoint não configurado; defina " + ", ".join(faltando) + ".")
        if not site_url:
            raise SharePointErro("Informe o site do SharePoint da empresa em Administração → Empresas.")
        return cls(*obrigatorias.values(), site_url=site_url)

    def _autenticar(self) -> None:
        resposta = requests.post(
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=self.timeout,
        )
        if resposta.status_code != 200:
            try:
                detalhe = resposta.json().get("error_description", resposta.text)
            except ValueError:
                detalhe = resposta.text
            raise SharePointErro(f"Falha ao obter token do Microsoft Graph: {detalhe[:300]}")
        self._sessao.headers["Authorization"] = f"Bearer {resposta.json()['access_token']}"

    def _get(self, url: str) -> requests.Response:
        if "Authorization" not in self._sessao.headers:
            self._autenticar()
        resposta = self._sessao.get(url if url.startswith("http") else GRAPH + url, timeout=self.timeout)
        if resposta.status_code == 403:
            raise SharePointErro(
                "Acesso negado pelo Microsoft Graph (403). Confira as permissões Sites.Read.All e "
                "Files.Read.All com consentimento do administrador."
            )
        if resposta.status_code == 404:
            raise NaoEncontrado(f"Não encontrado no SharePoint: {url}")
        if not resposta.ok:
            raise SharePointErro(f"Erro {resposta.status_code} do Microsoft Graph: {resposta.text[:300]}")
        return resposta

    def _paginas(self, url: str) -> list[dict]:
        itens = []
        while url:
            dados = self._get(url).json()
            itens.extend(dados.get("value", []))
            url = dados.get("@odata.nextLink")
        return itens

    def drive_id(self) -> str:
        """Biblioteca de documentos principal do site."""
        if self._drive_id is None:
            endereco = urlparse(self.site_url)
            site = self._get(f"/sites/{endereco.hostname}:{endereco.path.rstrip('/')}").json()
            self._drive_id = self._get(f"/sites/{site['id']}/drive").json()["id"]
        return self._drive_id

    def listar(self, caminho: str, profundidade: int = 1) -> list[ItemRemoto]:
        """Pastas e arquivos a partir de ``caminho`` (na raiz da biblioteca), até ``profundidade`` níveis."""
        drive = self.drive_id()
        caminho = caminho.strip("/")
        inicio = f"/drives/{drive}/root:/{quote(caminho)}:/children" if caminho else f"/drives/{drive}/root/children"
        encontrados, pendentes = [], [(inicio, caminho, 1)]
        while pendentes:
            url, atual, nivel = pendentes.pop()
            for item in self._paginas(f"{url}?$top=999&$select={CAMPOS}"):
                remoto = ItemRemoto(
                    id=item["id"],
                    nome=item["name"],
                    caminho=f"{atual}/{item['name']}".lstrip("/"),
                    pasta="folder" in item,
                    # cTag muda só com o conteúdo; a eTag muda também com metadados que o próprio SharePoint atualiza.
                    versao=item.get("cTag") or item.get("eTag") or item.get("lastModifiedDateTime", ""),
                    url=item.get("webUrl", ""),
                    tamanho=item.get("size") or 0,
                    criado=_data(item.get("createdDateTime")),
                    modificado=_data(item.get("lastModifiedDateTime")),
                )
                encontrados.append(remoto)
                if remoto.pasta and nivel < profundidade:
                    pendentes.append((f"/drives/{drive}/items/{item['id']}/children", remoto.caminho, nivel + 1))
        return sorted(encontrados, key=lambda i: i.caminho)

    @staticmethod
    def _codigo_compartilhamento(link: str) -> str:
        """Link de compartilhamento ("https://…/:b:/s/site/…") no formato que o Graph aceita em /shares."""
        return "u!" + base64.urlsafe_b64encode(link.strip().encode()).decode().rstrip("=")

    def por_link(self, link: str) -> ItemRemoto:
        """Arquivo de um link de compartilhamento do SharePoint."""
        item = self._get(f"/shares/{self._codigo_compartilhamento(link)}/driveItem?$select={CAMPOS},parentReference").json()
        pasta = (item.get("parentReference") or {}).get("path", "").split("root:", 1)[-1].strip("/")
        return ItemRemoto(
            id=item["id"], nome=item["name"], caminho=f"{pasta}/{item['name']}".strip("/"), pasta="folder" in item,
            versao=item.get("cTag") or item.get("eTag") or "", url=item.get("webUrl", link), tamanho=item.get("size") or 0,
            criado=_data(item.get("createdDateTime")), modificado=_data(item.get("lastModifiedDateTime")),
        )

    def baixar_link(self, link: str) -> bytes:
        return self._get(f"/shares/{self._codigo_compartilhamento(link)}/driveItem/content").content

    def baixar(self, item: ItemRemoto) -> bytes:
        return self._get(f"/drives/{self.drive_id()}/items/{item.id}/content").content
