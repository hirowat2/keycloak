"""Visões históricas: propostas ano a ano, clientes ao longo dos anos e linhas de serviço.

As propostas entram no ano em que foram emitidas (ano do número). Uma proposta de 2019 ganha
em 2020 conta como ganha em 2019: a visão é de safra, para comparar os anos entre si.
"""

import unicodedata
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal

from .constantes import EXPIRADA, GANHA, PERDIDA, ZERO
from .models import ArquivoSharePoint, Proposta

# Linha de serviço pelo título/serviço; a primeira regra que casa vale (validação antes de consultoria).
LINHAS_DE_SERVICO = [
    ("Perfil de dissolução", ("dissolu",)),
    ("Bioequivalência", ("bioequival",)),
    ("Estabilidade", ("estabilidade",)),
    ("Tamanho de partícula", ("particula", "granulom")),
    ("Validação de métodos", ("validacao", "validação", "metodo alternativo", "metodologia anal")),
    ("Treinamento e cursos", ("treinamento", "curso", "workshop", "capacitacao")),
    ("Licença de software", ("licenca", "licença", "action stat", "software")),
    ("Consultoria e relatórios", ("consultoria", "relatorio", "relatório", "analise", "análise", "estudo")),
]
OUTROS = "Outros"


def _normal(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").lower())
    return base.encode("ascii", "ignore").decode()


def linha_de_servico(proposta: Proposta) -> str:
    texto = _normal(f"{proposta.titulo} {proposta.servico}")
    for nome, chaves in LINHAS_DE_SERVICO:
        if any(_normal(chave) in texto for chave in chaves):
            return nome
    return OUTROS


def _pct(parte, todo) -> Decimal | None:
    return (Decimal(parte) * 100 / Decimal(todo)).quantize(Decimal("0.1"), ROUND_HALF_UP) if todo else None


def _largura(valor, maior) -> int:
    return int(valor * 100 / maior) if maior else 0


def por_ano(propostas: list[Proposta], acervo: dict[int, Counter]) -> list[dict]:
    """Uma linha por ano: emitidas, valores, ganhas, conversão, ticket, clientes e documentos."""
    anos = sorted({p.ano for p in propostas})
    vistos: set[int] = set()
    linhas = []
    for ano in anos:
        do_ano = [p for p in propostas if p.ano == ano]
        ganhas = [p for p in do_ano if p.etapa == GANHA]
        decididas = [p for p in do_ano if p.etapa in (GANHA, PERDIDA, EXPIRADA)]
        clientes = {p.cliente_id for p in do_ano}
        valor_ganho = sum((p.valor_total for p in ganhas), ZERO)
        linhas.append(
            {
                "ano": ano,
                "emitidas": len(do_ano),
                "valor_proposto": sum((p.valor_total for p in do_ano), ZERO),
                "sem_valor": sum(1 for p in do_ano if not p.valor_total),
                "ganhas": len(ganhas),
                "valor_ganho": valor_ganho,
                "conversao": _pct(len(ganhas), len(decididas)),
                "ticket": (valor_ganho / len(ganhas)).quantize(Decimal("0.01")) if ganhas else None,
                "clientes": len(clientes),
                "novos_clientes": len(clientes - vistos),
                "arquivos": sum(acervo.get(ano, Counter()).values()),
                "contratuais": sum(acervo.get(ano, Counter())[c] for c in ArquivoSharePoint.CONTRATUAIS),
            }
        )
        vistos |= clientes
    maior_qtd = max((l["emitidas"] for l in linhas), default=0)
    maior_ganho = max((l["valor_ganho"] for l in linhas), default=ZERO)
    for l in linhas:
        l["largura_qtd"] = _largura(l["emitidas"], maior_qtd)
        l["largura_ganho"] = _largura(l["valor_ganho"], maior_ganho)
    return linhas


def clientes_por_ano(propostas: list[Proposta], anos: list[int], limite: int = 25) -> list[dict]:
    """Os clientes com mais propostas: quantas por ano, o total ganho e o primeiro e o último ano."""
    grupos: dict[int, list[Proposta]] = defaultdict(list)
    for p in propostas:
        grupos[p.cliente_id].append(p)
    linhas = []
    for ps in grupos.values():
        contagem = Counter(p.ano for p in ps)
        linhas.append(
            {
                "cliente": ps[0].cliente,
                "total": len(ps),
                "ganhas": sum(1 for p in ps if p.etapa == GANHA),
                "valor_ganho": sum((p.valor_total for p in ps if p.etapa == GANHA), ZERO),
                "anos": [contagem.get(ano, 0) for ano in anos],
                "anos_ativos": len(contagem),
                "primeiro": min(contagem),
                "ultimo": max(contagem),
            }
        )
    linhas.sort(key=lambda l: (-l["total"], -l["valor_ganho"]))
    maior = max((n for l in linhas for n in l["anos"]), default=0)
    for l in linhas:
        # Intensidade da célula (0–4) para o mapa de calor.
        l["celulas"] = [(n, min(4, (n * 4 + maior - 1) // maior) if maior and n else 0) for n in l["anos"]]
    return linhas[:limite]


def linhas_por_ano(propostas: list[Proposta], anos: list[int]) -> list[dict]:
    grupos: dict[str, list[Proposta]] = defaultdict(list)
    for p in propostas:
        grupos[linha_de_servico(p)].append(p)
    ordem = [nome for nome, _ in LINHAS_DE_SERVICO] + [OUTROS]
    linhas = []
    for nome in ordem:
        ps = grupos.get(nome, [])
        if not ps:
            continue
        contagem = Counter(p.ano for p in ps)
        ganhas = [p for p in ps if p.etapa == GANHA]
        linhas.append(
            {
                "linha": nome,
                "total": len(ps),
                "anos": [contagem.get(ano, 0) for ano in anos],
                "ganhas": len(ganhas),
                "valor_ganho": sum((p.valor_total for p in ganhas), ZERO),
            }
        )
    return linhas


def historico(propostas, acervo_qs) -> dict:
    """Tudo o que a tela de histórico mostra, a partir das propostas (já filtradas) e do acervo da empresa."""
    propostas = list(propostas.select_related("cliente"))
    acervo: dict[int, Counter] = defaultdict(Counter)
    for ano, categoria in acervo_qs.exclude(ano=None).values_list("ano", "categoria"):
        acervo[ano][categoria] += 1
    anos = sorted({p.ano for p in propostas})
    ganhas = [p for p in propostas if p.etapa == GANHA]
    decididas = [p for p in propostas if p.etapa in (GANHA, PERDIDA, EXPIRADA)]
    clientes = clientes_por_ano(propostas, anos, limite=10_000)
    recorrentes = [c for c in clientes if c["anos_ativos"] >= 2]
    return {
        "anos": anos,
        "por_ano": por_ano(propostas, acervo),
        "clientes": clientes[:25],
        "linhas": linhas_por_ano(propostas, anos),
        "total_propostas": len(propostas),
        "total_ganho": sum((p.valor_total for p in ganhas), ZERO),
        "total_ganhas": len(ganhas),
        "conversao": _pct(len(ganhas), len(decididas)),
        "total_clientes": len(clientes),
        "recorrentes": len(recorrentes),
        "pct_recorrentes": _pct(len(recorrentes), len(clientes)),
        "sem_valor": sum(1 for p in propostas if not p.valor_total),
    }
