from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_assistantchat'),
    ]

    operations = [
        migrations.AlterField(
            model_name='artisanprofile',
            name='category',
            field=models.CharField(
                choices=[
                    ('plumbing', 'Plumbing'),
                    ('electrical', 'Electrical'),
                    ('carpentry-joinery', 'Carpentry & Joinery'),
                    ('painting-finishes', 'Painting & Finishes'),
                    ('masonry-tiling', 'Masonry & Tiling'),
                    ('welding-fabrication', 'Welding & Fabrication'),
                    ('roofing-gutters', 'Roofing & Gutters'),
                    ('flooring', 'Flooring'),
                    ('appliance-repair', 'Appliance Repair'),
                    ('hvac-refrigeration', 'HVAC & Refrigeration'),
                    ('solar-backup-power', 'Solar & Backup Power'),
                    ('cctv-security-systems', 'CCTV & Security Systems'),
                    ('cleaning-sanitation', 'Cleaning & Sanitation'),
                    ('moving-delivery-support', 'Moving & Delivery Support'),
                    ('landscaping-gardening', 'Landscaping & Gardening'),
                    ('water-systems-boreholes', 'Water Systems & Boreholes'),
                    ('automotive-mechanics', 'Automotive Mechanics'),
                    ('tailoring-fashion', 'Tailoring & Fashion'),
                    ('beauty-grooming', 'Beauty & Grooming'),
                    ('interior-design-decor', 'Interior Design & Decor'),
                    ('other', 'Other'),
                ],
                max_length=40,
            ),
        ),
    ]
