from rest_framework import serializers
from LeadCapture.models import Lead, Message, Form, PhoneCall


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ("token", "platform", "form")


class FormSerializer(serializers.ModelSerializer):
    class Meta:
        model = Form
        fields = ("user", "datetime", "question1", "question2")


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ("user", "datetime", "message", "response", "form")


class PhoneCallSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhoneCall
        fields = (
            "from_field",
            "call_sid",
            "datetime",
            "receive_text_field",
            "lead",
        )
