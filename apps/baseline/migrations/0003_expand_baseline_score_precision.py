from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("baseline", "0002_hasilindikator_import_batch_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hasilbaseline",
            name="skor_pm",
            field=models.DecimalField(
                blank=True,
                decimal_places=20,
                max_digits=30,
                null=True,
                verbose_name="skor PM",
            ),
        ),
        migrations.AlterField(
            model_name="hasilbaseline",
            name="skor_kka",
            field=models.DecimalField(
                blank=True,
                decimal_places=20,
                max_digits=30,
                null=True,
                verbose_name="skor KKA",
            ),
        ),
        migrations.AlterField(
            model_name="historicalhasilbaseline",
            name="skor_pm",
            field=models.DecimalField(
                blank=True,
                decimal_places=20,
                max_digits=30,
                null=True,
                verbose_name="skor PM",
            ),
        ),
        migrations.AlterField(
            model_name="historicalhasilbaseline",
            name="skor_kka",
            field=models.DecimalField(
                blank=True,
                decimal_places=20,
                max_digits=30,
                null=True,
                verbose_name="skor KKA",
            ),
        ),
    ]
