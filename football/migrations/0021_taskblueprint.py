from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0020_appuserrole'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskBlueprint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=160)),
                ('category', models.CharField(choices=[('build_up', 'Inicio y progresión'), ('pressing', 'Presión y recuperación'), ('transition', 'Transiciones'), ('finishing', 'Finalización'), ('abp', 'ABP'), ('goalkeeper', 'Porteros'), ('physical', 'Condicionante físico'), ('other', 'Otros')], default='other', max_length=32)),
                ('description', models.CharField(blank=True, max_length=220)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('created_by', models.CharField(blank=True, max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_blueprints', to='football.team')),
            ],
            options={
                'ordering': ['category', 'name', '-updated_at'],
                'unique_together': {('team', 'name')},
            },
        ),
    ]
