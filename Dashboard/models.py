from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone

from LeadCapture.models import PhoneCall, Lead


class Notifications(models.Model):
    voicemail_email = models.TextField(null=True, default=None)
    voicemail_phone = models.TextField(null=True, default=None)
    form_email = models.TextField(null=True, default=None)
    form_phone = models.TextField(null=True, default=None)


class DefaultResponse(models.Model):
    first_message = models.TextField()
    estimate_complete_message = models.TextField()


class PhoneCallInfo(models.Model):
    duration = models.IntegerField()
    voicemail = models.BooleanField(default=False)
    voicemail_link = models.TextField(null=True, default=None)
    call_num = models.ForeignKey(PhoneCall, on_delete=models.CASCADE)


class LeadDisplay(models.Model):
    color = models.TextField()
    name = models.TextField()
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
