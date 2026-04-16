from django.utils.text import slugify

from .models import Category, Skill


JOB_CATEGORY_DATA = [
    {
        'name': 'Plumbing',
        'icon': 'fa-solid fa-faucet-drip',
        'description': 'Water systems, drainage, piping, leak repair, and bathroom or kitchen plumbing work.',
        'skills': ['Leak repair', 'Pipe installation', 'Drain unclogging', 'Bathroom fitting', 'Water tank installation'],
    },
    {
        'name': 'Electrical',
        'icon': 'fa-solid fa-bolt',
        'description': 'Residential and commercial electrical wiring, fittings, repairs, and diagnostics.',
        'skills': ['House wiring', 'Socket installation', 'Lighting systems', 'Fault diagnosis', 'Backup power setup'],
    },
    {
        'name': 'Carpentry & Joinery',
        'icon': 'fa-solid fa-hammer',
        'description': 'Woodwork, fittings, cabinetry, wardrobes, roofing timber, and custom joinery.',
        'skills': ['Cabinet making', 'Roof timber framing', 'Wardrobe installation', 'Door fitting', 'Custom shelving'],
    },
    {
        'name': 'Painting & Finishes',
        'icon': 'fa-solid fa-paint-roller',
        'description': 'Interior and exterior painting, decorative finishes, and surface restoration.',
        'skills': ['Interior painting', 'Exterior painting', 'Texture finishes', 'Surface prep', 'Color consultation'],
    },
    {
        'name': 'Masonry & Tiling',
        'icon': 'fa-solid fa-trowel-bricks',
        'description': 'Block work, plastering, floor and wall tiling, concrete work, and finishing.',
        'skills': ['Wall tiling', 'Floor tiling', 'Plastering', 'Concrete casting', 'Brick laying'],
    },
    {
        'name': 'Welding & Fabrication',
        'icon': 'fa-solid fa-industry',
        'description': 'Metal fabrication, grills, gates, structural welding, and repairs.',
        'skills': ['Gate fabrication', 'Window grills', 'Structural welding', 'Metal repair', 'Canopy fabrication'],
    },
    {
        'name': 'Roofing & Gutters',
        'icon': 'fa-solid fa-house-chimney',
        'description': 'Roof installation, waterproofing, repairs, and gutter systems.',
        'skills': ['Roof repair', 'Gutter installation', 'Waterproofing', 'Sheet installation', 'Roof inspection'],
    },
    {
        'name': 'Flooring',
        'icon': 'fa-solid fa-border-all',
        'description': 'Wood, vinyl, laminate, epoxy, and specialty flooring supply and installation.',
        'skills': ['Laminate flooring', 'Vinyl installation', 'Epoxy flooring', 'Screeding', 'Floor polishing'],
    },
    {
        'name': 'Appliance Repair',
        'icon': 'fa-solid fa-blender',
        'description': 'Home and business appliance repair, diagnostics, and maintenance.',
        'skills': ['Cooker repair', 'Washing machine repair', 'Microwave repair', 'Fridge service', 'Small appliance diagnostics'],
    },
    {
        'name': 'HVAC & Refrigeration',
        'icon': 'fa-solid fa-fan',
        'description': 'Air conditioning, cold room, ventilation, and refrigeration installation or repair.',
        'skills': ['AC installation', 'AC servicing', 'Cold room maintenance', 'Ventilation setup', 'Refrigerant recharge'],
    },
    {
        'name': 'Solar & Backup Power',
        'icon': 'fa-solid fa-solar-panel',
        'description': 'Solar installation, inverters, batteries, and backup power systems.',
        'skills': ['Solar installation', 'Inverter setup', 'Battery bank wiring', 'Solar maintenance', 'Site assessment'],
    },
    {
        'name': 'CCTV & Security Systems',
        'icon': 'fa-solid fa-video',
        'description': 'CCTV installation, alarms, access control, and smart security systems.',
        'skills': ['CCTV installation', 'Alarm systems', 'Access control', 'Intercom setup', 'Remote monitoring'],
    },
    {
        'name': 'Cleaning & Sanitation',
        'icon': 'fa-solid fa-soap',
        'description': 'Deep cleaning, move-in cleaning, office cleaning, and sanitation services.',
        'skills': ['Deep cleaning', 'Office cleaning', 'Sofa cleaning', 'Mattress cleaning', 'Post-construction cleanup'],
    },
    {
        'name': 'Moving & Delivery Support',
        'icon': 'fa-solid fa-truck-fast',
        'description': 'House moving, office relocations, packing, loading, and bulky-item delivery support.',
        'skills': ['House moving', 'Office relocation', 'Packing services', 'Loading support', 'Furniture transport'],
    },
    {
        'name': 'Landscaping & Gardening',
        'icon': 'fa-solid fa-seedling',
        'description': 'Outdoor spaces, compound maintenance, gardening, lawn care, and landscaping.',
        'skills': ['Garden design', 'Lawn care', 'Tree trimming', 'Compound cleanup', 'Irrigation setup'],
    },
    {
        'name': 'Water Systems & Boreholes',
        'icon': 'fa-solid fa-water',
        'description': 'Water pump setup, borehole support, tank installation, and filtration systems.',
        'skills': ['Water pump installation', 'Tank setup', 'Filtration systems', 'Pressure systems', 'Borehole maintenance'],
    },
    {
        'name': 'Automotive Mechanics',
        'icon': 'fa-solid fa-car-side',
        'description': 'Vehicle diagnostics, servicing, electrical systems, and repairs.',
        'skills': ['Engine diagnostics', 'Vehicle servicing', 'Brake repair', 'Auto electricals', 'Suspension repair'],
    },
    {
        'name': 'Tailoring & Fashion',
        'icon': 'fa-solid fa-shirt',
        'description': 'Alterations, custom tailoring, uniform work, repairs, and fashion support.',
        'skills': ['Alterations', 'Custom outfits', 'Uniform stitching', 'Repairs', 'Pattern cutting'],
    },
    {
        'name': 'Beauty & Grooming',
        'icon': 'fa-solid fa-scissors',
        'description': 'Hair, barbering, makeup, nails, grooming, and beauty services.',
        'skills': ['Hair styling', 'Barber services', 'Makeup', 'Nail care', 'Home beauty visits'],
    },
    {
        'name': 'Interior Design & Decor',
        'icon': 'fa-solid fa-couch',
        'description': 'Interior styling, space planning, decor sourcing, and furnishing support.',
        'skills': ['Space planning', 'Decor styling', 'Curtain fitting', 'Furniture selection', 'Accent wall design'],
    },
]


def seed_job_categories():
    seeded_categories = []
    seeded_skills = []

    for item in JOB_CATEGORY_DATA:
        category, _ = Category.objects.update_or_create(
            slug=slugify(item['name']),
            defaults={
                'name': item['name'],
                'icon': item['icon'],
                'description': item['description'],
            },
        )
        seeded_categories.append(category)

        existing_skill_names = set(category.skills.values_list('name', flat=True))
        for skill_name in item['skills']:
            skill, created = Skill.objects.get_or_create(category=category, name=skill_name)
            if created or skill_name not in existing_skill_names:
                seeded_skills.append(skill)

    return seeded_categories, seeded_skills
