from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.
# models.py

from django.contrib.auth.models import User


class APIKey(models.Model):
    user = models.OneToOeField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.CharField(max_length=40, unique=True)

    def __str__(self):
        return self.key


class Lead(models.Model):
    token = models.TextField()
    platform = models.TextField()
    form = models.BooleanField(default=False)
    name = models.CharField(max_length=100, blank=True, null=True)


class FormQuestion(models.Model):
    question_text = models.TextField()
    deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(
        default=timezone.now, null=True
    )  # Add the datetime field

    def __str__(self):
        return self.question_text


class Form(models.Model):
    user = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="form_data")
    datetime = models.DateTimeField()
    questions = models.ManyToManyField(FormQuestion, through="FormResponse")

    def __str__(self):
        return f"Form for {self.user}"


class Message(models.Model):
    user = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="messages")
    datetime = models.DateTimeField()
    message = models.TextField()
    response = models.TextField()
    form = models.BooleanField()  # New field


class FormResponse(models.Model):
    form = models.ForeignKey("Form", on_delete=models.CASCADE)
    question = models.ForeignKey("FormQuestion", on_delete=models.CASCADE)
    response = models.TextField()

    def __str__(self):
        return f"{self.form.user}'s response to {self.question}: {self.response}"


#  phone call
# from, call_sid, datetime, recieved_text (default 0), lead number
class PhoneCall(models.Model):
    from_field = models.TextField()
    call_sid = models.TextField()
    datetime = models.DateTimeField()
    receive_text_field = models.BooleanField(default=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)


# in dashboard - call data
# duration, voicemail (true or false), voicemail link, foreign key phone call id
