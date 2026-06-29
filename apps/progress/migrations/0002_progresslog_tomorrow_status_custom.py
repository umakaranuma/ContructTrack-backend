from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progress', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='progresslog',
            name='tomorrow_status',
            field=models.CharField(
                default='working',
                help_text='Preset or custom status for the next working day.',
                max_length=100,
            ),
        ),
    ]
