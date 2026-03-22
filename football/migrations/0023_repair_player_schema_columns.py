from django.db import migrations, models


def _ensure_player_columns(apps, schema_editor):
    Player = apps.get_model('football', 'Player')
    table_name = Player._meta.db_table
    connection = schema_editor.connection

    existing_tables = set(connection.introspection.table_names())
    if table_name not in existing_tables:
        return

    with connection.cursor() as cursor:
        existing_columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

    field_factories = [
        ('full_name', lambda: models.CharField(max_length=180, blank=True, default='')),
        ('nickname', lambda: models.CharField(max_length=80, blank=True, default='')),
        ('birth_date', lambda: models.DateField(null=True, blank=True)),
        ('height_cm', lambda: models.PositiveSmallIntegerField(null=True, blank=True)),
        ('weight_kg', lambda: models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)),
        ('manual_sanction_active', lambda: models.BooleanField(default=False)),
        ('manual_sanction_reason', lambda: models.CharField(max_length=180, blank=True, default='')),
        ('manual_sanction_until', lambda: models.DateField(null=True, blank=True)),
    ]

    for field_name, factory in field_factories:
        if field_name in existing_columns:
            continue
        field = factory()
        field.set_attributes_from_name(field_name)
        schema_editor.add_field(Player, field)


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0022_alter_appuserrole_role'),
    ]

    operations = [
        migrations.RunPython(_ensure_player_columns, migrations.RunPython.noop),
    ]

