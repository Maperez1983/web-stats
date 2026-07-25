from django.db import migrations


def grandfather_paid_modules(apps, schema_editor):
    """C1: al quitar el bypass de `plan_key='pro'`, el acceso pasa a decidirlo `paid_modules`.
    Para no dejar sin módulos a quien HOY tiene acceso total (bundle Pro, o suscripción activa con
    paid_modules vacío — que con el gate viejo daba todo), se les escribe `paid_modules = todos los
    módulos`. Conservador: solo AÑADE módulos a workspaces activos; nunca quita acceso existente."""
    from football.billing_views import _all_module_entitlements

    Workspace = apps.get_model('football', 'Workspace')
    all_ent = _all_module_entitlements()
    bundle = {'pro', 'club_pro', 'bundle'}

    for ws in Workspace.objects.filter(subscription_status='active').iterator():
        paid = ws.paid_modules if isinstance(ws.paid_modules, dict) else {}
        plan = str(ws.plan_key or '').strip().lower()
        # Recibía acceso total con el gate antiguo: bundle mágico, o paid_modules vacío/ausente.
        if plan in bundle or not paid:
            merged = dict(paid)
            merged.update(all_ent)
            ws.paid_modules = merged
            ws.save(update_fields=['paid_modules', 'updated_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0180_merge_copa_groups'),
    ]

    operations = [
        migrations.RunPython(grandfather_paid_modules, migrations.RunPython.noop),
    ]
