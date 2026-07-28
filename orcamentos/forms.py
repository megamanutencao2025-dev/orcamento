from django import forms

from cadastros.models import Material, Servico

from .models import (
    InsumoInterno,
    ItemServico,
    MaterialCliente,
    MaterialFornecido,
    Orcamento,
    OutroCusto,
)


class OrcamentoForm(forms.ModelForm):
    class Meta:
        model = Orcamento
        fields = (
            "data",
            "validade",
            "status",
            "modo_apresentacao",
            "cliente_nome",
            "cliente_telefone",
            "endereco_obra",
            "veiculo",
            "distancia_km",
            "metodo_mao_obra",
            "tempo_estimado_horas",
            "valor_hora",
            "percentual_ferramentas",
            "percentual_empresa",
            "percentual_lucro",
            "desconto",
            "observacoes_internas",
            "observacoes_cliente",
        )
        widgets = {
            "data": forms.DateInput(
                format="%Y-%m-%d", attrs={"type": "date"}
            ),
            "validade": forms.DateInput(
                format="%Y-%m-%d", attrs={"type": "date"}
            ),
            "cliente_nome": forms.TextInput(
                attrs={"placeholder": "Nome do cliente"}
            ),
            "cliente_telefone": forms.TextInput(
                attrs={"placeholder": "(00) 00000-0000"}
            ),
            "endereco_obra": forms.TextInput(
                attrs={"placeholder": "Rua, número, bairro e cidade"}
            ),
            "distancia_km": forms.NumberInput(
                attrs={"min": "0", "step": "0.01"}
            ),
            "tempo_estimado_horas": forms.NumberInput(
                attrs={"min": "0", "step": "0.01"}
            ),
            "valor_hora": forms.NumberInput(
                attrs={"min": "0", "step": "0.01"}
            ),
            "percentual_ferramentas": forms.NumberInput(
                attrs={"min": "0", "step": "0.01"}
            ),
            "percentual_empresa": forms.NumberInput(
                attrs={"min": "0", "step": "0.01"}
            ),
            "percentual_lucro": forms.NumberInput(
                attrs={"min": "0", "step": "0.01"}
            ),
            "desconto": forms.NumberInput(
                attrs={"min": "0", "step": "0.01"}
            ),
            "observacoes_internas": forms.Textarea(attrs={"rows": 3}),
            "observacoes_cliente": forms.Textarea(attrs={"rows": 3}),
        }

class MaterialFornecidoForm(forms.ModelForm):
    class Meta:
        model = MaterialFornecido
        fields = ("material", "quantidade", "unidade", "preco_unitario", "fornecedor")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = Material.objects.filter(
            ativo=True, tipo_uso=Material.TipoUso.FORNECIDO
        )

    def save(self, commit=True):
        item = super().save(commit=False)
        item.descricao = item.material.nome
        if commit:
            item.save()
        return item


class MaterialClienteForm(forms.ModelForm):
    class Meta:
        model = MaterialCliente
        fields = (
            "material_referencia",
            "descricao",
            "quantidade",
            "unidade",
            "observacao",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material_referencia"].queryset = Material.objects.filter(
            ativo=True
        )


class InsumoInternoForm(forms.ModelForm):
    class Meta:
        model = InsumoInterno
        fields = ("material", "quantidade", "unidade", "preco_unitario")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = Material.objects.filter(
            ativo=True, tipo_uso=Material.TipoUso.INSUMO
        )

    def save(self, commit=True):
        item = super().save(commit=False)
        item.descricao = item.material.nome
        if commit:
            item.save()
        return item


class ItemServicoForm(forms.ModelForm):
    class Meta:
        model = ItemServico
        fields = (
            "servico",
            "quantidade",
            "preco_unitario",
            "dificuldade",
            "altura",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["servico"].queryset = Servico.objects.filter(ativo=True)

    def save(self, commit=True):
        item = super().save(commit=False)
        item.descricao = item.servico.nome
        item.unidade = item.servico.unidade
        if commit:
            item.save()
        return item


class OutroCustoForm(forms.ModelForm):
    class Meta:
        model = OutroCusto
        fields = ("descricao", "valor")
