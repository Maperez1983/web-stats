from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0019_rivalanalysisreport'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AppUserRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('jugador', 'Jugador'), ('entrenador', 'Entrenador'), ('preparador_fisico', 'Preparador físico'), ('preparador_portero', 'Preparador portero'), ('analista', 'Analista'), ('administrador', 'Administrador')], default='jugador', max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='app_role', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Rol de usuario',
                'verbose_name_plural': 'Roles de usuario',
                'ordering': ['user__username'],
            },
        ),
    ]
