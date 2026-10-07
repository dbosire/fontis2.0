from django.db import migrations


def seed(apps, schema_editor):
    """Starter procedures (as drafts) and the premises checklist. get_or_create on the
    code so re-running never overwrites wording someone has since edited."""
    from compliance.procedure_templates import PREMISES_REQUIREMENTS, PROCEDURES

    Procedure = apps.get_model("compliance", "Procedure")
    PremisesRequirement = apps.get_model("compliance", "PremisesRequirement")

    for data in PROCEDURES:
        Procedure.objects.get_or_create(
            code=data["code"],
            defaults={
                "title": data["title"], "category": data["category"], "owner": data["owner"],
                "content": data["content"], "version": "1.0", "status": "draft",
            },
        )
    for order, (code, description) in enumerate(PREMISES_REQUIREMENTS, start=1):
        PremisesRequirement.objects.get_or_create(
            code=code, defaults={"description": description, "sort_order": order},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
