"""Plano de uma etapa: o que será criado, atualizado ou removido no Keycloak.

Cada etapa compara o estado atual com o desejado e registra um ``Passo`` por
objeto. Na simulação nada é gravado; na aplicação, cada ação roda na hora em
que o passo é registrado. Rodar de novo uma etapa já aplicada só gera passos "ok".
"""

from dataclasses import asdict, dataclass
from typing import Callable

CRIAR, ATUALIZAR, REMOVER, OK = "criar", "atualizar", "remover", "ok"
ROTULOS = {CRIAR: "Criar", ATUALIZAR: "Atualizar", REMOVER: "Remover", OK: "Sem mudança"}


@dataclass
class Passo:
    situacao: str
    tipo: str
    alvo: str
    detalhe: str = ""

    @property
    def rotulo(self) -> str:
        return ROTULOS[self.situacao]


class Plano:
    def __init__(self, simular: bool):
        self.simular = simular
        self.passos: list[Passo] = []

    def registrar(self, situacao: str, tipo: str, alvo: str, detalhe: str = "", acao: Callable[[], object] | None = None):
        if situacao != OK and acao is not None and not self.simular:
            acao()
        self.passos.append(Passo(situacao, tipo, alvo, detalhe))

    @property
    def mudancas(self) -> int:
        return sum(1 for p in self.passos if p.situacao != OK)

    def como_lista(self) -> list[dict]:
        return [asdict(p) for p in self.passos]


def _normalizar(valor):
    if isinstance(valor, list):
        return sorted(str(v) for v in valor)
    if isinstance(valor, bool):
        return str(valor).lower()
    return "" if valor is None else str(valor)


def diferencas(atual: dict, desejado: dict) -> list[str]:
    """Chaves de ``desejado`` com valor diferente em ``atual`` (listas sem ordem, "true" == True)."""
    return [chave for chave, valor in desejado.items() if _normalizar(atual.get(chave)) != _normalizar(valor)]
