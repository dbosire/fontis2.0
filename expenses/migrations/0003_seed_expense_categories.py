from django.db import migrations

SEED_CATEGORIES = [
    "Lunch", "Token", "Rent", "Water Bill", "Bottles", "Non-Spills",
    "Bike Repairs", "Salaries", "Licenses", "Service Charge", "Other",
]


def seed_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model("expenses", "ExpenseCategory")
    Expense = apps.get_model("expenses", "Expense")

    names = set(SEED_CATEGORIES)
    # Also pick up any category value already in use on a real row but not in the
    # original hardcoded list (e.g. from direct DB edits before this migration) —
    # otherwise those existing expenses would reference a category absent from the
    # new manageable list and become impossible to re-select in the edit form.
    names.update(
        value.strip()
        for value in Expense.objects.exclude(category="").values_list("category", flat=True).distinct()
        if value and value.strip()
    )

    ExpenseCategory.objects.bulk_create(
        [ExpenseCategory(name=name) for name in names],
        ignore_conflicts=True,
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("expenses", "0002_expensecategory"),
    ]

    operations = [
        migrations.RunPython(seed_categories, noop_reverse),
    ]
