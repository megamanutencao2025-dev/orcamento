from django import forms

from .models import Configuracao


class ConfiguracaoForm(forms.ModelForm):
    class Meta:
        model = Configuracao
        exclude = ("atualizado_em",)
        widgets = {
            "observacao_cliente_padrao": forms.Textarea(attrs={"rows": 3}),
            "observacao_interna_padrao": forms.Textarea(attrs={"rows": 3}),
        }
