"""Utilitários compartilhados pelas telas do sistema."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from .empresas import eh_admin, empresa_ativa, papel_ativo
from .models import Empresa
from .valores import valor_monetario

GRUPOS_EDICAO = ["Admin", "Master", "Tech"]
GRUPOS_GESTAO = ["Admin", "Master"]


def pode(request, grupos: list[str]) -> bool:
    """O papel do usuário na empresa ativa está entre ``grupos``."""
    return papel_ativo(request) in grupos


def com_empresa(view):
    """Tela do sistema: recebe a empresa ativa; sem acesso a nenhuma empresa, mostra o aviso.

    Os formulários da tela enviam a empresa em que foram abertos (``empresa_tela``).
    A empresa ativa fica na sessão, comum a todas as abas: se ela mudou em outra
    aba, a ação é recusada em vez de cair na empresa errada.
    """

    @wraps(view)
    def envolvida(context, request):
        empresa = empresa_ativa(request)
        if empresa is None or papel_ativo(request) is None:
            context["pode_cadastrar"] = eh_admin(request.user)
            return render(request, "sem_empresa.html", context, status=403)
        if request.method == "POST" and request.POST.get("empresa_tela") != str(empresa.pk):
            messages.error(
                request,
                f"A empresa ativa mudou para {empresa} em outra aba. Nada foi feito; confira a tela e repita a ação.",
            )
            return redirect(request.get_full_path())
        context["empresa"] = empresa
        return view(context, request, empresa)

    return envolvida


def exigir(request, grupos: list[str]) -> bool:
    """True se o usuário pode; senão registra a mensagem de erro."""
    if pode(request, grupos):
        return True
    messages.error(request, "Você não tem permissão para esta operação.")
    return False


class FiltroPeriodoForm(forms.Form):
    inicio = forms.DateField(label="Fechadas de", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    fim = forms.DateField(label="até", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    responsavel = forms.ModelChoiceField(
        label="Responsável", queryset=User.objects.none(), required=False, empty_label="Todos"
    )

    def __init__(self, *args, empresa: Empresa, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsavel"].queryset = responsaveis(empresa)

    def clean(self):
        dados = super().clean()
        if dados.get("inicio") and dados.get("fim") and dados["inicio"] > dados["fim"]:
            raise forms.ValidationError("A data inicial deve ser anterior à final.")
        return dados


def responsaveis(empresa: Empresa):
    """Usuários que já são responsáveis por alguma proposta da empresa."""
    return User.objects.filter(propostas__empresa=empresa).distinct().order_by("first_name", "username")


@dataclass(frozen=True)
class Periodo:
    inicio: date
    fim: date
    responsavel: User | None
    form: FiltroPeriodoForm

    @property
    def descricao(self) -> str:
        return f"{self.inicio:%d/%m/%Y} a {self.fim:%d/%m/%Y}"


def periodo(request, empresa: Empresa) -> Periodo:
    """Período filtrado; padrão: do início do ano até hoje."""
    hoje = date.today()
    form = FiltroPeriodoForm(request.GET or None, empresa=empresa)
    dados = form.cleaned_data if form.is_valid() else {}
    inicio = dados.get("inicio") or hoje.replace(month=1, day=1)
    fim = dados.get("fim") or (hoje if inicio <= hoje else inicio.replace(month=12, day=31))
    if not request.GET:
        form = FiltroPeriodoForm(initial={"inicio": inicio, "fim": fim}, empresa=empresa)
    return Periodo(inicio=inicio, fim=fim, responsavel=dados.get("responsavel"), form=form)


class CampoValor(forms.DecimalField):
    """Valor em reais digitado como no Brasil: "1.234,56", "1234,56", "R$ 75,53" (ou "1234.56")."""

    class Entrada(forms.TextInput):
        input_type = "text"

        def format_value(self, value):
            if isinstance(value, Decimal):
                return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return super().format_value(value)

    widget = Entrada

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_digits", 16)
        kwargs.setdefault("decimal_places", 2)
        super().__init__(*args, **kwargs)
        self.widget.attrs.setdefault("inputmode", "decimal")
        self.widget.attrs.setdefault("placeholder", "0,00")

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return valor_monetario(value)
        except ValueError as erro:
            raise forms.ValidationError("Informe um valor como 1.234,56.", code="invalid") from erro

    def widget_attrs(self, widget):
        return {}  # sem os atributos de <input type="number"> (step, min)
