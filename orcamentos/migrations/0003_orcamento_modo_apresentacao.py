from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orcamentos", "0002_alter_orcamento_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="orcamento",
            name="modo_apresentacao",
            field=models.CharField(
                choices=[
                    ("detalhado", "Detalhado"),
                    ("preco_global", "Preço global"),
                ],
                default="detalhado",
                max_length=20,
                verbose_name="apresentação da proposta",
            ),
        ),
    ]
