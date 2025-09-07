from django.contrib import admin
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

# Lấy tất cả model trong app 'users'
app_models = apps.get_app_config('users').get_models()

User = get_user_model()  # lấy model User hiện tại (mặc định hoặc custom)

for model in app_models:
    if getattr(model._meta, 'abstract', False):
        continue  # bỏ qua abstract model

    try:
        if model == User:
            # nếu là model User, đăng ký với UserAdmin
            admin.site.register(model, UserAdmin)
        else:
            # các model khác đăng ký bình thường
            admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        # nếu đã đăng ký thì bỏ qua, không raise lỗi
        print(f"Model {model.__name__} is already registered")
