from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orcamentos", "0003_orcamento_modo_apresentacao"),
    ]

    operations = [
        migrations.AddField(
            model_name="orcamento",
            name="desconto",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
                validators=[
                    django.core.validators.MinValueValidator(
                        Decimal("0.00")
                    )
                ],
                verbose_name="desconto comercial",
            ),
        ),
    ]
