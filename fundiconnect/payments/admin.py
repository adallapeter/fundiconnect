from django.contrib import admin

from .models import Commission, Dispute, Escrow, Invoice, Milestone, Payment

admin.site.register(Escrow)
admin.site.register(Milestone)
admin.site.register(Invoice)
admin.site.register(Payment)
admin.site.register(Dispute)
admin.site.register(Commission)
