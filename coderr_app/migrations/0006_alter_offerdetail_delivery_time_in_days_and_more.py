import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coderr_app', '0005_userprofile_created_at_userprofile_file_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='offerdetail',
            name='delivery_time_in_days',
            field=models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AlterField(
            model_name='offerdetail',
            name='revisions',
            field=models.IntegerField(validators=[django.core.validators.MinValueValidator(-1)]),
        ),
    ]
