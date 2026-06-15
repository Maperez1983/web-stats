from django.db import migrations, models


def _column_names(schema_editor, table_name):
    conn = schema_editor.connection
    vendor = conn.vendor
    cursor = conn.cursor()
    if vendor == 'sqlite':
        cursor.execute(f'PRAGMA table_info({table_name})')
        return {str(row[1]) for row in cursor.fetchall()}
    if vendor in {'postgresql', 'mysql'}:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            """,
            [table_name],
        )
        return {str(row[0]) for row in cursor.fetchall()}
    return set()


def add_columns_if_missing(apps, schema_editor):
    table = 'football_rivalvideo'
    vendor = schema_editor.connection.vendor
    existing = _column_names(schema_editor, table)

    if vendor == 'postgresql':
        quoted_table = f'"{table}"'
        statements = {
            'duration_ms': f'ALTER TABLE {quoted_table} ADD COLUMN duration_ms integer NOT NULL DEFAULT 0',
            'ingest_status': f"ALTER TABLE {quoted_table} ADD COLUMN ingest_status varchar(12) NOT NULL DEFAULT ''",
            'ingest_error': f"ALTER TABLE {quoted_table} ADD COLUMN ingest_error text NOT NULL DEFAULT ''",
            'video_fps': f'ALTER TABLE {quoted_table} ADD COLUMN video_fps double precision NOT NULL DEFAULT 0',
            'video_w': f'ALTER TABLE {quoted_table} ADD COLUMN video_w integer NOT NULL DEFAULT 0',
            'video_h': f'ALTER TABLE {quoted_table} ADD COLUMN video_h integer NOT NULL DEFAULT 0',
        }
    elif vendor == 'mysql':
        statements = {
            'duration_ms': f'ALTER TABLE {table} ADD COLUMN duration_ms integer unsigned NOT NULL DEFAULT 0',
            'ingest_status': f"ALTER TABLE {table} ADD COLUMN ingest_status varchar(12) NOT NULL DEFAULT ''",
            'ingest_error': f"ALTER TABLE {table} ADD COLUMN ingest_error TEXT NOT NULL DEFAULT ''",
            'video_fps': f'ALTER TABLE {table} ADD COLUMN video_fps DOUBLE NOT NULL DEFAULT 0',
            'video_w': f'ALTER TABLE {table} ADD COLUMN video_w integer unsigned NOT NULL DEFAULT 0',
            'video_h': f'ALTER TABLE {table} ADD COLUMN video_h integer unsigned NOT NULL DEFAULT 0',
        }
    else:
        statements = {
            'duration_ms': f'ALTER TABLE {table} ADD COLUMN duration_ms integer unsigned NOT NULL DEFAULT 0',
            'ingest_status': f"ALTER TABLE {table} ADD COLUMN ingest_status varchar(12) NOT NULL DEFAULT ''",
            'ingest_error': f"ALTER TABLE {table} ADD COLUMN ingest_error TEXT NOT NULL DEFAULT ''",
            'video_fps': f'ALTER TABLE {table} ADD COLUMN video_fps REAL NOT NULL DEFAULT 0',
            'video_w': f'ALTER TABLE {table} ADD COLUMN video_w integer unsigned NOT NULL DEFAULT 0',
            'video_h': f'ALTER TABLE {table} ADD COLUMN video_h integer unsigned NOT NULL DEFAULT 0',
        }
    for column, sql in statements.items():
        if column not in existing:
            schema_editor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0141_videoaitrackjob_export_follow_choice'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_columns_if_missing, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='rivalvideo',
                    name='duration_ms',
                    field=models.PositiveIntegerField(default=0),
                ),
                migrations.AddField(
                    model_name='rivalvideo',
                    name='ingest_status',
                    field=models.CharField(blank=True, default='', max_length=12),
                ),
                migrations.AddField(
                    model_name='rivalvideo',
                    name='ingest_error',
                    field=models.TextField(blank=True, default=''),
                ),
                migrations.AddField(
                    model_name='rivalvideo',
                    name='video_fps',
                    field=models.FloatField(default=0),
                ),
                migrations.AddField(
                    model_name='rivalvideo',
                    name='video_w',
                    field=models.PositiveIntegerField(default=0),
                ),
                migrations.AddField(
                    model_name='rivalvideo',
                    name='video_h',
                    field=models.PositiveIntegerField(default=0),
                ),
            ],
        ),
    ]
