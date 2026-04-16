from django.db import migrations
from django.utils.text import slugify


JOB_CATEGORY_DATA = [
    ('Plumbing', 'fa-solid fa-faucet-drip', 'Water systems, drainage, piping, leak repair, and bathroom or kitchen plumbing work.', ['Leak repair', 'Pipe installation', 'Drain unclogging', 'Bathroom fitting', 'Water tank installation']),
    ('Electrical', 'fa-solid fa-bolt', 'Residential and commercial electrical wiring, fittings, repairs, and diagnostics.', ['House wiring', 'Socket installation', 'Lighting systems', 'Fault diagnosis', 'Backup power setup']),
    ('Carpentry & Joinery', 'fa-solid fa-hammer', 'Woodwork, fittings, cabinetry, wardrobes, roofing timber, and custom joinery.', ['Cabinet making', 'Roof timber framing', 'Wardrobe installation', 'Door fitting', 'Custom shelving']),
    ('Painting & Finishes', 'fa-solid fa-paint-roller', 'Interior and exterior painting, decorative finishes, and surface restoration.', ['Interior painting', 'Exterior painting', 'Texture finishes', 'Surface prep', 'Color consultation']),
    ('Masonry & Tiling', 'fa-solid fa-trowel-bricks', 'Block work, plastering, floor and wall tiling, concrete work, and finishing.', ['Wall tiling', 'Floor tiling', 'Plastering', 'Concrete casting', 'Brick laying']),
    ('Welding & Fabrication', 'fa-solid fa-industry', 'Metal fabrication, grills, gates, structural welding, and repairs.', ['Gate fabrication', 'Window grills', 'Structural welding', 'Metal repair', 'Canopy fabrication']),
    ('Roofing & Gutters', 'fa-solid fa-house-chimney', 'Roof installation, waterproofing, repairs, and gutter systems.', ['Roof repair', 'Gutter installation', 'Waterproofing', 'Sheet installation', 'Roof inspection']),
    ('Flooring', 'fa-solid fa-border-all', 'Wood, vinyl, laminate, epoxy, and specialty flooring supply and installation.', ['Laminate flooring', 'Vinyl installation', 'Epoxy flooring', 'Screeding', 'Floor polishing']),
    ('Appliance Repair', 'fa-solid fa-blender', 'Home and business appliance repair, diagnostics, and maintenance.', ['Cooker repair', 'Washing machine repair', 'Microwave repair', 'Fridge service', 'Small appliance diagnostics']),
    ('HVAC & Refrigeration', 'fa-solid fa-fan', 'Air conditioning, cold room, ventilation, and refrigeration installation or repair.', ['AC installation', 'AC servicing', 'Cold room maintenance', 'Ventilation setup', 'Refrigerant recharge']),
    ('Solar & Backup Power', 'fa-solid fa-solar-panel', 'Solar installation, inverters, batteries, and backup power systems.', ['Solar installation', 'Inverter setup', 'Battery bank wiring', 'Solar maintenance', 'Site assessment']),
    ('CCTV & Security Systems', 'fa-solid fa-video', 'CCTV installation, alarms, access control, and smart security systems.', ['CCTV installation', 'Alarm systems', 'Access control', 'Intercom setup', 'Remote monitoring']),
    ('Cleaning & Sanitation', 'fa-solid fa-soap', 'Deep cleaning, move-in cleaning, office cleaning, and sanitation services.', ['Deep cleaning', 'Office cleaning', 'Sofa cleaning', 'Mattress cleaning', 'Post-construction cleanup']),
    ('Moving & Delivery Support', 'fa-solid fa-truck-fast', 'House moving, office relocations, packing, loading, and bulky-item delivery support.', ['House moving', 'Office relocation', 'Packing services', 'Loading support', 'Furniture transport']),
    ('Landscaping & Gardening', 'fa-solid fa-seedling', 'Outdoor spaces, compound maintenance, gardening, lawn care, and landscaping.', ['Garden design', 'Lawn care', 'Tree trimming', 'Compound cleanup', 'Irrigation setup']),
    ('Water Systems & Boreholes', 'fa-solid fa-water', 'Water pump setup, borehole support, tank installation, and filtration systems.', ['Water pump installation', 'Tank setup', 'Filtration systems', 'Pressure systems', 'Borehole maintenance']),
    ('Automotive Mechanics', 'fa-solid fa-car-side', 'Vehicle diagnostics, servicing, electrical systems, and repairs.', ['Engine diagnostics', 'Vehicle servicing', 'Brake repair', 'Auto electricals', 'Suspension repair']),
    ('Tailoring & Fashion', 'fa-solid fa-shirt', 'Alterations, custom tailoring, uniform work, repairs, and fashion support.', ['Alterations', 'Custom outfits', 'Uniform stitching', 'Repairs', 'Pattern cutting']),
    ('Beauty & Grooming', 'fa-solid fa-scissors', 'Hair, barbering, makeup, nails, grooming, and beauty services.', ['Hair styling', 'Barber services', 'Makeup', 'Nail care', 'Home beauty visits']),
    ('Interior Design & Decor', 'fa-solid fa-couch', 'Interior styling, space planning, decor sourcing, and furnishing support.', ['Space planning', 'Decor styling', 'Curtain fitting', 'Furniture selection', 'Accent wall design']),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('jobs', 'Category')
    Skill = apps.get_model('jobs', 'Skill')

    for name, icon, description, skills in JOB_CATEGORY_DATA:
        category, _ = Category.objects.update_or_create(
            slug=slugify(name),
            defaults={
                'name': name,
                'icon': icon,
                'description': description,
            },
        )
        for skill_name in skills:
            Skill.objects.get_or_create(category=category, name=skill_name)


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, migrations.RunPython.noop),
    ]
