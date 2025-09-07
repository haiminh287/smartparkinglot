from django.contrib import admin
from django.apps import apps

app_models = apps.get_app_config('booking_app').get_models()

for model in app_models:
    if not getattr(model._meta, 'abstract', False):
        try:
            admin.site.register(model)
        except admin.sites.AlreadyRegistered as e:
            print(f"Model {model} is already registered")
            raise
