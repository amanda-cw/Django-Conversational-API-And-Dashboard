from rest_framework import serializers
from .models import PhoneCallInfo, LeadDisplay


class PhoneCallInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhoneCallInfo
        fields = ("duration", "voicemail", "voicemail_link", "call_num")


class LeadDisplaySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadDisplay
        fields = ("color", "name", "lead")
