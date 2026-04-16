from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_email_verification_code_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='email_verification_code',
            field=models.CharField(blank=True, max_length=6, null=True),
        ),
    ]
