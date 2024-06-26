# Generated by Django 4.2.4 on 2023-10-05 17:09

from django.db import migrations, models


def populate_lead_names(apps, schema_editor):
    Lead = apps.get_model("LeadCapture", "Lead")
    for lead in Lead.objects.all():
        if not lead.name:
            lead.name = f"Lead #{lead.pk or ''}"
            lead.save()


def set_default_name_for_new_leads(apps, schema_editor):
    Lead = apps.get_model("LeadCapture", "Lead")
    for lead in Lead.objects.filter(name=""):
        lead.name = f"Lead #{lead.pk or ''}"
        lead.save()


class Migration(migrations.Migration):
    dependencies = [
        ("LeadCapture", "0011_rename_datetime_field_phonecall_datetime"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="name",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.RunPython(populate_lead_names),
        migrations.RunPython(set_default_name_for_new_leads),
    ]
