"""Valores em reais: leitura do que o usuário digita e textos curtos para rótulos."""

import re
from decimal import Decimal, InvalidOperation

CENTAVO = Decimal("0.01")


def _separador_decimal_ponto(texto: str) -> str:
    """Remove separadores de milhar e deixa o ponto como separador decimal."""
    if "," in texto and "." in texto:
        decimal_sep = "," if texto.rfind(",") > texto.rfind(".") else "."
        milhar_sep = "." if decimal_sep == "," else ","
        return texto.replace(milhar_sep, "").replace(decimal_sep, ".")
    if "," in texto:
        return texto.replace(",", ".") if texto.count(",") == 1 else texto.replace(",", "")
    if texto.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", texto):
        return texto.replace(".", "")
    return texto


def valor_monetario(valor: object) -> Decimal | None:
    """Converte "R$ 1.234,56", "(1.234,56)", "-1234.56" ou números em Decimal.

    Com ponto e vírgula juntos, o último separador é o decimal. Um único ponto
    seguido de exatamente três dígitos ("1.500") é tratado como milhar, pois
    valores monetários não costumam ter três casas decimais.
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        raise ValueError(f"valor inválido: {valor!r}")
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor)).quantize(CENTAVO)

    texto = str(valor).strip().replace("R$", "").replace(" ", "").replace("\xa0", "")
    if not texto or texto in {"-", "--"}:
        return None
    negativo = texto.startswith("(") and texto.endswith(")")
    texto = texto.strip("()")
    if texto.endswith("-"):
        negativo, texto = True, texto[:-1]

    try:
        numero = Decimal(_separador_decimal_ponto(texto))
    except InvalidOperation as erro:
        raise ValueError(f"valor inválido: {valor!r}") from erro
    return (-numero if negativo else numero).quantize(CENTAVO)


def valor_curto(valor: Decimal | float) -> str:
    """R$ 1.234.567 -> 'R$ 1,2 mi'; R$ 12.300 -> 'R$ 12 mil'."""
    numero = float(valor)
    sinal = "-" if numero < 0 else ""
    numero = abs(numero)
    if numero >= 1_000_000:
        texto = f"{numero / 1_000_000:.1f} mi"
    elif numero >= 10_000:
        texto = f"{numero / 1_000:.0f} mil"
    elif numero >= 1_000:
        texto = f"{numero / 1_000:.1f} mil"
    else:
        texto = f"{numero:.0f}"
    return f"{sinal}R$ {texto.replace('.', ',')}"
