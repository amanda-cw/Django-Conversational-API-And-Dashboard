import os
import django

# Run This Script to Add Super Users

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "DjangoAPI.settings"
)  # Replace "your_project_name" with your actual project name
django.setup()

from django.contrib.auth.models import User

# Uncomment Here and Insert Permissions: 

# User.objects.create_superuser("admin", "username", "password")
