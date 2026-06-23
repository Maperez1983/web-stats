from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('football', '0143_training_methodology_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceAccessToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=140)),
                ('token_prefix', models.CharField(db_index=True, max_length=16)),
                ('token_hash', models.CharField(max_length=180)),
                ('is_active', models.BooleanField(default=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.CharField(blank=True, max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='service_access_tokens',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'workspace',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='service_access_tokens',
                        to='football.workspace',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Token de acceso de servicio',
                'verbose_name_plural': 'Tokens de acceso de servicio',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='serviceaccesstoken',
            index=models.Index(fields=['token_prefix', 'is_active'], name='svtok_prefix_active_idx'),
        ),
        migrations.AddIndex(
            model_name='serviceaccesstoken',
            index=models.Index(fields=['user', 'is_active'], name='svtok_user_active_idx'),
        ),
    ]
