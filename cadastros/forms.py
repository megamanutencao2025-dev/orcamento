from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q
from django.forms import (
    DecimalField,
    HiddenInput,
    ModelForm,
    NumberInput,
    Textarea,
)

from .models import (
    CategoriaMaterial,
    Dificuldade,
    Material,
    Servico,
    TrabalhoAltura,
    UnidadeMedida,
    Veiculo,
)


class MaterialForm(ModelForm):
    preco_compra = DecimalField(
        label="Preço unitário",
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        widget=NumberInput(attrs={"min": "0", "step": "0.01"}),
    )
    preco_unitario_calculado = DecimalField(
        label="Preço calculado por unidade",
        required=False,
        disabled=True,
        max_digits=12,
        decimal_places=2,
        widget=NumberInput(attrs={"tabindex": "-1"}),
        help_text="Valor utilizado como referência nos orçamentos.",
    )

    class Meta:
        model = Material
        fields = (
            "nome",
            "categoria",
            "forma_compra",
            "unidade_medida",
            "quantidade_unidades_caixa",
            "preco_compra",
            "preco_unitario_calculado",
            "fornecedor",
            "tipo_uso",
            "imagem_url",
            "url_origem",
            "fonte_importacao",
        )
        widgets = {
            "quantidade_unidades_caixa": NumberInput(
                attrs={"min": "1", "step": "1"}
            ),
            "imagem_url": HiddenInput(),
            "url_origem": HiddenInput(),
            "fonte_importacao": HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        unidades = UnidadeMedida.objects.filter(ativo=True)
        if self.instance.pk and self.instance.unidade_medida_id:
            unidades = UnidadeMedida.objects.filter(
                Q(ativo=True) | Q(pk=self.instance.unidade_medida_id)
            )
        self.fields["unidade_medida"].queryset = unidades

        if not self.is_bound:
            self.initial["preco_compra"] = self.instance.preco_compra
            self.initial["preco_unitario_calculado"] = (
                self.instance.preco_unitario
            )
        forma = (
            self.data.get(self.add_prefix("forma_compra"))
            if self.is_bound
            else self.instance.forma_compra
        )
        if forma == Material.FormaCompra.CAIXA:
            self.fields["preco_compra"].label = "Preço da caixa"

    def clean(self):
        cleaned_data = super().clean()
        forma = cleaned_data.get("forma_compra")
        preco_compra = cleaned_data.get("preco_compra")
        quantidade = cleaned_data.get("quantidade_unidades_caixa")
        self.instance.forma_compra = forma or Material.FormaCompra.UNIDADE

        if preco_compra is None:
            return cleaned_data
        if forma == Material.FormaCompra.CAIXA:
            self.instance.preco_caixa = preco_compra
            self.instance.quantidade_unidades_caixa = quantidade
            if not quantidade:
                self.add_error(
                    "quantidade_unidades_caixa",
                    "Informe quantas unidades existem na caixa.",
                )
                return cleaned_data
            preco_unitario = (
                preco_compra / Decimal(quantidade)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            self.instance.preco_unitario = preco_unitario
            cleaned_data["preco_unitario_calculado"] = preco_unitario
        else:
            cleaned_data["quantidade_unidades_caixa"] = None
            self.instance.quantidade_unidades_caixa = None
            self.instance.preco_caixa = None
            self.instance.preco_unitario = preco_compra
            cleaned_data["preco_unitario_calculado"] = preco_compra
        return cleaned_data


class CategoriaMaterialForm(ModelForm):
    class Meta:
        model = CategoriaMaterial
        fields = ("nome", "descricao")
        widgets = {"descricao": Textarea(attrs={"rows": 2})}


class UnidadeMedidaForm(ModelForm):
    class Meta:
        model = UnidadeMedida
        fields = ("nome", "sigla", "ativo")


class ServicoForm(ModelForm):
    class Meta:
        model = Servico
        fields = ("nome", "unidade", "preco_unitario", "descricao")
        widgets = {"descricao": Textarea(attrs={"rows": 2})}


class VeiculoForm(ModelForm):
    class Meta:
        model = Veiculo
        fields = ("nome", "km_por_litro", "preco_combustivel")


class DificuldadeForm(ModelForm):
    class Meta:
        model = Dificuldade
        fields = ("nome", "percentual", "descricao")
        widgets = {"descricao": Textarea(attrs={"rows": 2})}


class TrabalhoAlturaForm(ModelForm):
    class Meta:
        model = TrabalhoAltura
        fields = ("nome", "percentual", "descricao")
        widgets = {"descricao": Textarea(attrs={"rows": 2})}
