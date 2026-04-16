from django import template

register = template.Library()


CATEGORY_ICON_MAP = {
    'plumbing': 'bi-droplet-half',
    'electrical': 'bi-lightning-charge-fill',
    'carpentry-joinery': 'bi-hammer',
    'painting-finishes': 'bi-brush',
    'masonry-tiling': 'bi-grid-3x3-gap-fill',
    'welding-fabrication': 'bi-gear-wide-connected',
    'roofing-gutters': 'bi-house-gear-fill',
    'flooring': 'bi-border-all',
    'appliance-repair': 'bi-tools',
    'hvac-refrigeration': 'bi-fan',
    'solar-backup-power': 'bi-sun-fill',
    'cctv-security-systems': 'bi-camera-video-fill',
    'cleaning-sanitation': 'bi-stars',
    'moving-delivery-support': 'bi-truck',
    'landscaping-gardening': 'bi-flower1',
    'water-systems-boreholes': 'bi-water',
    'automotive-mechanics': 'bi-car-front-fill',
    'tailoring-fashion': 'bi-scissors',
    'beauty-grooming': 'bi-magic',
    'interior-design-decor': 'bi-lamp-fill',
    'other': 'bi-grid'
}


@register.filter
def category_icon(category):
    if not category:
        return 'bi-grid'
    slug = getattr(category, 'slug', '') or ''
    name = getattr(category, 'name', '') or ''
    key = slug or name.lower().replace(' & ', '-').replace(' ', '-')
    return CATEGORY_ICON_MAP.get(key, 'bi-grid')
