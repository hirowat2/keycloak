from django import forms
from django.contrib.auth.models import User
from django.forms import inlineformset_factory

from commercial.propostas.constantes import MOTIVOS_PERDA
from commercial.propostas.models import Cliente, Contato, ItemCatalogo, ItemProposta, Proposta
from commercial.propostas.web import CampoValor

DATA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class PropostaForm(forms.ModelForm):
    """Cabeçalho da proposta; os itens vêm no formset ``ItensFormSet``."""

    # Seções do formulário: (título, campos).
    SECOES = [
        ("Cliente", ["titulo", "cliente", "contato", "responsavel", "origem"]),
        ("Condições comerciais", ["validade", "condicoes_pagamento", "prazo_entrega", "escopo"]),
        ("Acompanhamento", ["probabilidade", "previsao_fechamento", "proxima_acao", "proxima_acao_em", "observacoes"]),
    ]

    class Meta:
        model = Proposta
        fields = [
            "titulo", "cliente", "contato", "responsavel", "origem", "validade", "condicoes_pagamento", "prazo_entrega",
            "escopo", "probabilidade", "previsao_fechamento", "proxima_acao", "proxima_acao_em", "observacoes",
        ]
        widgets = {
            "validade": DATA, "previsao_fechamento": DATA, "proxima_acao_em": DATA,
            "escopo": forms.Textarea(attrs={"rows": 5}),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, empresa, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.empresa = empresa
        clientes = Cliente.objects.filter(empresa=empresa)
        atual = self.instance.cliente_id
        self.fields["cliente"].queryset = clientes.filter(ativo=True) | clientes.filter(pk=atual)
        self.fields["contato"].queryset = Contato.objects.filter(cliente__empresa=empresa).select_related("cliente")
        self.fields["contato"].label_from_instance = lambda c: f"{c.cliente} · {c}"
        self.fields["responsavel"].queryset = User.objects.filter(is_active=True).order_by("first_name", "username")
        self.fields["responsavel"].label_from_instance = lambda u: u.get_full_name() or u.username
        if not self.instance.pk and not self.is_bound:
            self.initial.setdefault("condicoes_pagamento", empresa.condicoes_pagamento)

    def clean(self):
        dados = super().clean()
        contato, cliente = dados.get("contato"), dados.get("cliente")
        if contato and cliente and contato.cliente_id != cliente.pk:
            self.add_error("contato", "Escolha um contato deste cliente.")
        if dados.get("proxima_acao_em") and not dados.get("proxima_acao"):
            self.add_error("proxima_acao", "Diga qual é a próxima ação.")
        return dados


class ItemForm(forms.ModelForm):
    """Linha da proposta. Escolhendo um item do catálogo, descrição, unidade e preço vazios vêm dele."""

    class Meta:
        model = ItemProposta
        fields = ["item_catalogo", "descricao", "detalhes", "unidade", "quantidade", "preco_unitario", "desconto"]
        field_classes = {"quantidade": CampoValor, "preco_unitario": CampoValor, "desconto": CampoValor}
        widgets = {"detalhes": forms.Textarea(attrs={"rows": 1})}

    def __init__(self, *args, empresa, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item_catalogo"].queryset = ItemCatalogo.objects.filter(empresa=empresa, ativo=True)
        self.fields["item_catalogo"].empty_label = "Item avulso"
        for nome in ("descricao", "preco_unitario", "unidade", "quantidade", "desconto"):
            self.fields[nome].required = False
        self.fields["quantidade"].widget.attrs["placeholder"] = "1"
        self.fields["desconto"].widget.attrs["placeholder"] = "0"

    def clean(self):
        dados = super().clean()
        catalogo = dados.get("item_catalogo")
        if catalogo:
            dados["descricao"] = dados.get("descricao") or catalogo.nome
            dados["unidade"] = dados.get("unidade") or catalogo.unidade
            if dados.get("preco_unitario") is None:
                dados["preco_unitario"] = catalogo.preco
        dados["unidade"] = dados.get("unidade") or "un"
        dados["quantidade"] = dados.get("quantidade") or 1
        dados["desconto"] = dados.get("desconto") or 0
        if not dados.get("descricao"):
            self.add_error("descricao", "Descreva o item ou escolha um do catálogo.")
        if dados.get("preco_unitario") is None:
            self.add_error("preco_unitario", "Informe o preço.")
        return dados


ItensFormSet = inlineformset_factory(
    Proposta, ItemProposta, form=ItemForm, extra=0, min_num=1, validate_min=True, can_delete=True
)


class PerdaForm(forms.Form):
    motivo_perda = forms.ChoiceField(label="Motivo da perda", choices=[("", "Escolha…"), *MOTIVOS_PERDA])
    concorrente = forms.CharField(label="Concorrente que ganhou", required=False, max_length=150)


class AnotacaoForm(forms.Form):
    texto = forms.CharField(label="Anotação", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    proxima_acao = forms.CharField(label="Próxima ação", required=False, max_length=200)
    proxima_acao_em = forms.DateField(label="Quando", required=False, widget=DATA)
