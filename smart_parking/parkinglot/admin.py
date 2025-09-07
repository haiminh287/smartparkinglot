from django.contrib import admin
from django.apps import apps
from .models import Zone, CarSlot   # import đúng model CarSlot

app_models = apps.get_app_config('parkinglot').get_models()


class CarSlotAdmin(admin.ModelAdmin):
    list_display = ("code", "zone", "is_available")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "zone":
            kwargs["queryset"] = Zone.objects.filter(vehicle_type="Car")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


for model in app_models:
    if not getattr(model._meta, 'abstract', False):
        try:
            if model.__name__ == "CarSlot":
                continue
            admin.site.register(model)
        except admin.sites.AlreadyRegistered:
            pass

# Đăng ký CarSlot với custom admin
admin.site.register(CarSlot, CarSlotAdmin)
