from LeadCapture import views
from django.urls import path, include


urlpatterns = [
    path("api", views.leadAPI, name="leadAPI"),
    path("voice", views.inbound_phonecall, name="inbound_phonecall"),
    path("text", views.incoming_message, name="incoming_message"),
    path("handle-recording", views.handle_recording, name="handle_recording"),
    path(
        "handle-transcription", views.handle_transcription, name="handle_transcription"
    ),
    path("show", views.show_notification, name="show"),
]
