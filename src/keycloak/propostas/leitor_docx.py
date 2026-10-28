"""Leitura dos campos de uma proposta em .docx feita nos modelos da Estatcamp.

Dois modelos estão em uso na biblioteca do SharePoint:

* consultoria (2022 em diante): "NÚMERO: 021/26", "Data:", "Vencimento:", o título logo
  depois, "A/C: <contato>", seções "VALOR", "FORMA DE PAGAMENTO" e "CRONOGRAMA DE TRABALHO";
* modelo antigo (2016–2020): como o de consultoria, mas com "A: <cliente>" e a seção "PREÇO";
  muitas não têm título, que então sai da "Descrição Geral" ("referente à realização de…");
* PowerPoint (Action Pharma e Action Stat, 2022 em diante): "PROPOSTA COMERCIAL", o cliente, "A/C:",
  "Nº 170/24", "ENVIO:", "VALIDADE:", o título e a seção "INVESTIMENTO";
* Word Action Stat (2021): "Para", "Número", "Data" e "Validade: 30 dias" (relativa à data);
* licença Action Stat (2021): "Proposta No 017/21", "Entrega da Proposta:", "Proposta válida
  até:", "Preparada para:" seguido do contato e do cliente, seção "Valor" e
  "Forma de Pagamento: ..." na mesma linha.

O .docx e o .pptx são lidos direto do XML (zip), sem dependência extra. Campo não encontrado fica vazio;
quem importa decide o que fazer (ex.: usar a planilha de controle).
"""

import html
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from .valores import valor_monetario

DINHEIRO = re.compile(r"R\$\s*([\d.]+,\d{2})")
FIM_DO_VALOR = ("FORMA DE PAGAMENTO", "CRONOGRAMA", "VALIDADE", "A SEU DISPOR", "CONDIÇÕES", "CONDICOES")
TITULOS_DE_SECAO = {"DESCRIÇÃO GERAL", "DESCRICAO GERAL", "ESCOPO", "PROPOSTA COMERCIAL", "PROPOSTA"}
ENVIADA_PARA = re.compile(r"^PROPOSTA(?: DE SERVI[ÇC]O| T[ÉE]CNICA| COMERCIAL| T[ÉE]CNICA E COMERCIAL)? ENVIADA PARA:?\s*", re.I)
CAPA_PPTX = re.compile(r"^PROPOSTA (?:T[ÉE]CNICA E )?COMERCIAL$|^PROPOSTA T[ÉE]CNICA$", re.I)


@dataclass
class DadosDocumento:
    numero: str = ""
    data: date | None = None
    validade: date | None = None
    titulo: str = ""
    cliente: str = ""
    contato: str = ""
    valor: Decimal | None = None
    valores: list[Decimal] = field(default_factory=list)
    pagamento: str = ""
    prazo: str = ""
    escopo: str = ""
    assinante: str = ""

    @property
    def valor_a_conferir(self) -> bool:
        """Mais de um valor na seção de preço: o escolhido pode não ser o total."""
        return len(self.valores) > 1


def _xmls(conteudo: bytes) -> tuple[list[str], str, str]:
    """XMLs com o texto, na ordem, e as tags de parágrafo e de texto: .docx (Word) ou .pptx (PowerPoint)."""
    pacote = zipfile.ZipFile(io.BytesIO(conteudo))
    nomes = pacote.namelist()
    if "word/document.xml" in nomes:
        return [pacote.read("word/document.xml").decode("utf-8")], "w:p", "w:t"
    slides = sorted(
        (n for n in nomes if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
        key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)),
    )
    return [pacote.read(n).decode("utf-8") for n in slides], "a:p", "a:t"


def paragrafos(conteudo: bytes) -> list[str]:
    """Texto de cada parágrafo (inclusive de tabelas), sem os vazios e sem repetições seguidas."""
    xmls, tag_p, tag_t = _xmls(conteudo)
    textos = []
    for p in (p for xml in xmls for p in re.findall(rf"<{tag_p}[ >].*?</{tag_p}>", xml, re.S)):
        texto = html.unescape("".join(re.findall(rf"<{tag_t}(?: [^>]*)?>([^<]*)</{tag_t}>", p)))
        texto = texto.replace("\u200b", "")
        texto = " ".join(texto.replace("\xa0", " ").split())
        # Caixas de texto do Word repetem o mesmo parágrafo (versão nova e antiga do desenho).
        if texto and (not textos or textos[-1] != texto):
            textos.append(texto)
    return textos


def _data(texto: str) -> date | None:
    texto = texto.strip()
    for formato in ("%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%y", "%d.%m.%y"):
        try:
            return datetime.strptime(texto[:10], formato).date()
        except ValueError:
            continue
    return None


def _depois(ps: list[str], *rotulos: str) -> str:
    """Valor de "Rótulo: valor" na mesma linha ou, com o rótulo sozinho, na linha seguinte."""
    for i, p in enumerate(ps):
        for rotulo in rotulos:
            if re.fullmatch(rf"{rotulo}\s*:?", p, re.I):
                return ps[i + 1] if i + 1 < len(ps) else ""
            m = re.match(rf"{rotulo}\s*:\s*(.+)$", p, re.I)
            if m:
                return m.group(1).strip()
    return ""


def _secao(ps: list[str], titulo: str, fim: tuple[str, ...]) -> list[str]:
    """Parágrafos depois do título da seção até o próximo título da lista ``fim``."""
    for i, p in enumerate(ps):
        if p.upper() == titulo or p.upper().startswith(titulo + " "):
            corpo = []
            for q in ps[i + 1:]:
                if corpo and q.upper().startswith(fim):
                    break
                corpo.append(q)
            return corpo
    return []


def _valor(ps: list[str]) -> tuple[Decimal | None, list[Decimal]]:
    """O valor da proposta: o da linha com "total"; senão, o único; senão, o maior."""
    linhas = next((s for titulo in ("VALOR", "PREÇO", "PRECO", "INVESTIMENTO") if (s := _secao(ps, titulo, FIM_DO_VALOR))), [])
    achados = [(linha, valor_monetario(v)) for linha in linhas for v in DINHEIRO.findall(linha)]
    valores = [v for _, v in achados]
    if not valores:
        return None, []
    com_total = [v for linha, v in achados if "total" in linha.lower()]
    return (com_total[-1] if com_total else max(valores)), valores


def _titulo_da_descricao(texto: str) -> str:
    """ "Proposta comercial referente à realização de um treinamento em MSA." -> "Realização de um treinamento em MSA"."""
    m = re.search(r"referentes?\s+(?:à|às|ao|aos|a)\s+(.+)", texto, re.I)
    titulo = (m.group(1) if m else texto).split(". ")[0].rstrip(". ")
    if len(titulo) > 120:
        titulo = titulo[:117].rsplit(" ", 1)[0] + "…"
    return titulo[:1].upper() + titulo[1:]


def ler(conteudo: bytes) -> DadosDocumento:
    ps = paragrafos(conteudo)
    pptx = "word/document.xml" not in zipfile.ZipFile(io.BytesIO(conteudo)).namelist()
    dados = DadosDocumento()
    numero = _depois(ps, "NÚMERO", "NUMERO")
    if not numero:
        achado = next(
            (m for p in ps if (m := re.match(r"(?:Proposta\s+)?N[oº°.]+\s*(\d{1,4}\s*/\s*\d{2})", p, re.I))), None
        )
        numero = achado.group(1) if achado else ""
    dados.numero = numero.split()[0] if numero else ""
    dados.data = _data(_depois(ps, "Data", "Entrega da Proposta", "ENVIO"))
    validade = _depois(ps, "Vencimento", "Proposta válida até", "Válida até", "Validade até", "VALIDADE")
    dados.validade = _data(validade)
    if not dados.validade and dados.data and (dias := re.fullmatch(r"(\d{1,3})\s*dias", validade.strip(), re.I)):
        dados.validade = dados.data + timedelta(days=int(dias.group(1)))

    # Título: a linha depois da validade (rótulo e valor na mesma linha ou em linhas seguidas), se não for um título de seção.
    linha_validade = next(
        (i for i, p in enumerate(ps) if re.match(r"(Vencimento|Proposta válida até|Válida até|Validade até|Validade)\b", p, re.I)), None
    )
    if linha_validade is not None:
        i = linha_validade + (1 if ":" in ps[linha_validade] and ps[linha_validade].rstrip()[-1] != ":" else 2)
        seguinte = ps[i] if i < len(ps) else ""
        if seguinte.upper() not in TITULOS_DE_SECAO and not seguinte.upper().startswith(("A/C", "DESCRI")):
            dados.titulo = seguinte

    enviada = next((i for i, p in enumerate(ps) if ENVIADA_PARA.match(p)), None)
    if enviada is not None:
        dados.cliente = ENVIADA_PARA.sub("", ps[enviada]).strip()
        if not dados.cliente and enviada + 1 < len(ps):
            dados.cliente = ps[enviada + 1]
    # PowerPoint: "PROPOSTA COMERCIAL" na capa e o cliente logo abaixo.
    capa = next((i for i, p in enumerate(ps[:3]) if CAPA_PPTX.match(p)), None) if pptx else None
    if not dados.cliente and capa is not None and capa + 1 < len(ps) and not ps[capa + 1].upper().startswith("A/C"):
        dados.cliente = ps[capa + 1]
    dados.cliente = re.sub(r"^EMPRESA\s*:\s*", "", dados.cliente or _depois(ps, "Para"), flags=re.I)
    para = next((p for p in ps if re.match(r"A\s*:\s*\S", p) and not p.upper().startswith("A/C")), "")
    dados.cliente = dados.cliente or para.split(":", 1)[-1].strip()
    dados.contato = _depois(ps, "A/C", "Preparada para")
    if not dados.cliente and "Preparada para:" in ps:
        indice = ps.index("Preparada para:")
        dados.cliente = ps[indice + 2] if indice + 2 < len(ps) else ""

    dados.valor, dados.valores = _valor(ps)
    pagamento = _secao(ps, "FORMA DE PAGAMENTO", ("CRONOGRAMA", "A SEU DISPOR", "VALIDADE"))
    dados.pagamento = pagamento[0] if pagamento else _depois(ps, "Forma de Pagamento")
    prazo = _secao(ps, "CRONOGRAMA DE TRABALHO", ("A SEU DISPOR", "VALIDADE"))
    dados.prazo = prazo[0] if prazo else ""
    escopo = _secao(ps, "DESCRIÇÃO GERAL", ("ESCOPO",))
    dados.escopo = "\n\n".join(escopo[:3])
    if not dados.titulo and escopo:
        dados.titulo = _titulo_da_descricao(escopo[0])
    if not dados.titulo and "Proposta Comercial" in ps:
        # Modelo de licença: o produto vem logo depois ("“ACTION STAT”").
        produto = ps[ps.index("Proposta Comercial") + 1] if ps.index("Proposta Comercial") + 1 < len(ps) else ""
        if produto and not produto.lower().startswith("proposta"):
            dados.titulo = "Licença " + produto.strip("“”\"' ")
    fechamento = next((i for i, p in enumerate(ps) if p.lower().startswith("a seu dispor")), None)
    if fechamento is not None and fechamento + 1 < len(ps):
        dados.assinante = ps[fechamento + 1]
    for campo in ("titulo", "cliente", "contato", "pagamento", "prazo", "assinante"):
        setattr(dados, campo, getattr(dados, campo)[:250])
    return dados
