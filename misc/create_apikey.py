import os
import django

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "DjangoAPI.settings"
)  # Replace "your_project_name" with your actual project name
django.setup()
from django.contrib.auth.models import User  # Import the User model
from LeadCapture.models import APIKey

# Assuming you want to set the third user (with ID 3) as the owner of the API key
user_id = 3

# Retrieve the User object for the third user
try:
    user = User.objects.get(id=user_id)
except User.DoesNotExist:
    # Handle the case where the user with ID 3 does not exist
    user = None

# Create the APIKey object and associate it with the user
if user:
    new_key = APIKey.objects.create(key="2tf0bPXQWhKLXA5tBa46wt2dmR6eDcft", user=user)
    new_key.save()
    print("success")
else:
    # Handle the case where the user with ID 3 does not exist
    pass
