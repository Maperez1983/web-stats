from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0023_repair_player_schema_columns'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlayerFine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(choices=[('absence', 'Ausencia'), ('late', 'Retraso'), ('indiscipline', 'Indisciplina'), ('expulsion', 'Expulsión')], max_length=20)),
                ('amount', models.PositiveSmallIntegerField(help_text='Importe en euros, múltiplo de 5')),
                ('note', models.CharField(blank=True, max_length=220)),
                ('created_by', models.CharField(blank=True, max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fines', to='football.player')),
            ],
            options={
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
