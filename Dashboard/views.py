from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import JSONParser
from django.utils import timezone
from validate_email import validate_email
from django.contrib.auth.decorators import login_required
from django.http.response import JsonResponse
from django.db.models import Max, Count, Prefetch, Min
import base64
from django.contrib.auth.views import PasswordResetView

from django.core.mail import send_mail
from LeadCapture.models import (
    Lead,
    Message,
    Form,
    FormQuestion,
    FormResponse,
    PhoneCall,
)
from django.urls import reverse
from LeadCapture.serializers import LeadSerializer, MessageSerializer, FormSerializer
import tiktoken
from django.contrib.auth import authenticate, login, logout
import requests
from decouple import config
import openai
import os
from django.core.mail import send_mail
from twilio.rest import Client
from twilio.twiml.voice_response import Gather, Pause, Record, Say, VoiceResponse
import json
import random
import logging
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response

from django.http import HttpResponse, HttpRequest
import time
import datetime
import phonenumbers
from phonenumbers import format_number, PhoneNumberFormat

import requests
from LeadCapture.models import (
    Lead,
    Form,
    FormQuestion,
    FormResponse,
    Message,
    PhoneCall,
)
from .models import Notifications, DefaultResponse, PhoneCallInfo, LeadDisplay
from .serializers import PhoneCallInfoSerializer, LeadDisplaySerializer
from itertools import chain

# Creating Out Logging File for Debugging Purposes
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Create a formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# Create a file handler
file_handler = logging.FileHandler("app.log")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
# Create your views here.


@csrf_exempt
def login_view(request):
    if request.method == "GET":
        return render(request, "login.html")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Authenticate the user
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # The user has been authenticated, log them in
            login(request, user)
            # Redirect to a success page or do something else
            return redirect("home")
        else:
            # The username and password didn't match, show an error message
            error_message = "Invalid username or password."

    # Render the login form
    return HttpResponse("failure")


@csrf_exempt
@login_required
def logout_view(request):
    # Log the user out
    logout(request)
    request.session.flush()
    # Redirect to a page after logout (e.g., the homepage)
    return redirect("login")


@login_required
def home(request):
    if request.method == "GET":
        active_tab = "home"

        # Count Instances of Objects in Database for Display
        leads = Lead.objects.count()
        forms = Form.objects.count()
        messages = Message.objects.count()
        calls = PhoneCall.objects.count()

        # Retrieve and order interactions (most recent first)
        form_interactions = Form.objects.order_by("-datetime")[:10]
        message_interactions = Message.objects.order_by("-datetime")[:10]
        phone_call_interactions = PhoneCall.objects.order_by("-datetime")[:10]

        # For each interaction, assign it a "type" so we can
        # display interaction type on dashboard "Latest Activity"
        for form in form_interactions:
            form.type = "form"
        for message in message_interactions:
            message.type = "message"
        for call in phone_call_interactions:
            call.type = "phone_call"

        # Merge Into One List, organized by most recent
        latest_interactions = sorted(
            chain(form_interactions, message_interactions, phone_call_interactions),
            key=lambda x: x.datetime,
            reverse=True,
        )

        # Organize context information
        context = {
            "active_tab": active_tab,
            "leads": leads,
            "forms": forms,
            "messages": messages,
            "calls": calls,
            "latest_activity": latest_interactions,
        }

        return render(request, "dashboard.html", context)


@login_required
def leads(request):
    if request.method == "GET":
        active_tab = "myleads"
        # Define a Prefetch object to prefetch related messages for each lead
        message_prefetch = Prefetch(
            "messages", queryset=Message.objects.order_by("datetime")
        )

        # Retrieve all leads with related messages and annotate with the count of filled forms
        leads_with_annotation = Lead.objects.annotate(
            num_forms=Count("form_data")
        ).prefetch_related(message_prefetch)

        # Create a list to store leads with their original primary keys
        leads_with_filtered_messages = list(leads_with_annotation)

        # Iterate through the leads
        for lead in leads_with_filtered_messages:
            # Get all messages for the current lead
            messages = lead.messages.all()

            # Check if there are messages for this lead
            if messages.exists():
                # Get the oldest and newest messages
                oldest_message = messages.first()
                newest_message = messages.last()

                # Add the oldest and newest messages as attributes to the lead
                lead.oldest_message = oldest_message
                lead.newest_message = newest_message

        # Sort the list of leads based on the datetime of newest_message (newest to oldest)
        leads_with_filtered_messages_sorted = sorted(
            leads_with_filtered_messages,
            key=lambda lead: lead.newest_message.datetime,
            reverse=True,  # Reverse order for newest to oldest
        )
        # Now, leads_with_filtered_messages_sorted contains the leads with preserved primary keys
        context = {
            "active_tab": active_tab,
            "lead_data": leads_with_filtered_messages_sorted,
        }
        return render(request, "leads.html", context)


@csrf_exempt
@login_required
def myLeads(request, id):
    if request.method == "GET":
        active_tab = "myleads"
        # Access lead data
        mylead = Lead.objects.filter(pk=id).first()

        if mylead is None:
            return render(request, "404.html")

        # Access forms and all associated form responses
        forms = (
            Form.objects.filter(user_id=id)
            .prefetch_related("formresponse_set__question")
            .order_by("-datetime")
        )

        # Access Message History
        message_history = Message.objects.filter(user=id)

        # Access User Data
        platform = mylead.platform.capitalize()
        token = mylead.token

        # Check if phone number
        if platform == "Text":
            phone = token
        else:
            phone = "N/a"

        # phone calls
        phone_calls = (
            PhoneCall.objects.filter(lead=id)
            .prefetch_related("phonecallinfo_set")
            .order_by("-datetime")
        )

        # processing data via context
        name = mylead.name
        context = {
            "id": id,
            "name": name,
            "platform": platform,
            "token": token,
            "message_history": message_history,
            "phone": phone,
            "user_forms": forms,
            "active_tab": active_tab,
            "phone_calls": phone_calls,
        }

        return render(request, "myleads.html", context)

    if request.method == "POST":
        # Access lead data
        mylead = Lead.objects.filter(pk=id).first()

        if mylead is None:
            return render(request, "404.html")

        new_name = request.POST.get("newLeadName")

        if new_name is not None:
            mylead.name = new_name
            mylead.save()

        return redirect(reverse("myLeads", args=[id]))


@login_required
def forms(request):
    if request.method == "GET":
        active_tab = "forms"

        forms = Form.objects.all().order_by("-datetime")
        print(f"{forms[0]}")

        context = {"active_tab": active_tab, "forms": forms}
        return render(request, "forms.html", context)


@login_required
def showform(request, id):
    if request.method == "GET":
        active_tab = "forms"
        form = Form.objects.get(pk=id)
        responses = form.formresponse_set.all()

        context = {"active_tab": active_tab, "form": form, "responses": responses}

        return render(request, "showforms.html", context)


@login_required
def messages(request):
    if request.method == "GET":
        active_tab = "messages"
        messages = Message.objects.all().order_by("-datetime")
        context = {"active_tab": active_tab, "messages": messages}
        return render(request, "messages.html", context)


# Create your views here.


@login_required
@csrf_exempt
def notificationSettings(request):
    if request.method == "GET":
        active_tab = "notifsettings"
        # do create notification settings object if pk=1 doesnt exist

        notification_settings = Notifications.objects.get(pk=1)
        if notification_settings is None:
            notification_settings = Notifications.objects.create()
        # if doesnt exist, create
        context = {"settings": notification_settings, "active_tab": active_tab}
        return render(request, "notifsettings.html", context)

    if request.method == "POST":
        active_tab = "notifsettings"
        notification_settings = Notifications.objects.get(pk=1)

        form_emails = request.POST.get("form_emails")
        form_phones = request.POST.get("form_phones")

        voicemail_emails = request.POST.get("voicemail_emails")
        voicemail_phones = request.POST.get("voicemail_phones")
        form_error = None
        voicemail_error = None

        # need logic nesting for this

        if form_emails:
            check = check_emails(form_emails)
            if check == True:
                notification_settings.form_email = form_emails
                notification_settings.save()
            else:
                form_error = f"Error in your form notification settings. Email list is invalid. The following email is invalid: {check}. Please make sure they are comma separated and are valid email addresses."
                context = {
                    "settings": notification_settings,
                    "active_tab": active_tab,
                    "form_error": form_error,
                }
                return render(request, "notifsettings.html", context)

        if form_phones:
            check = check_phones(form_phones)
            if check[1] == True:
                notification_settings.form_phone = check[0]
                notification_settings.save()
            else:
                form_error = f"Error in your form notification settings. Phone list is invalid. The following phone number is invalid: {check[0]}. Please make sure they are comma separated and are valid phone numbers."
                context = {
                    "settings": notification_settings,
                    "active_tab": active_tab,
                    "form_error": form_error,
                }

        if voicemail_emails:
            check = check_emails(voicemail_emails)
            if check:
                notification_settings.voicemail_email = voicemail_emails
                notification_settings.save()
            else:
                voicemail_error = f"Error in your form notification settings. Email list is invalid. The following email is invalid: {check}. Please make sure they are comma separated and are valid email addresses."
                context = {
                    "settings": notification_settings,
                    "active_tab": active_tab,
                    "voicemail_error": voicemail_error,
                }
                return render(request, "notifsettings.html", context)

        if voicemail_phones:
            check = check_phones(voicemail_phones)
            if check[1] == True:
                print(f"{check[0]}")
                notification_settings.voicemail_phone = check[0]
                notification_settings.save()
            else:
                voicemail_error = f"Error in your voicemail notification settings. Phone list is invalid. The following phone number is invalid: {check[0]}. Please make sure they are comma separated and are valid phone numbers."
                context = {
                    "settings": notification_settings,
                    "active_tab": active_tab,
                    "voicemail_error": voicemail_error,
                }

        context = {
            "settings": notification_settings,
            "active_tab": active_tab,
            "form_error": form_error,
        }
        return render(request, "notifsettings.html", context)


@login_required
@csrf_exempt
def messageSettings(request):
    if request.method == "GET":
        active_tab = "messagesettings"

        message_settings = DefaultResponse.objects.get(pk=1)
        first = message_settings.first_message
        second = message_settings.estimate_complete_message

        context = {"settings": message_settings, "active_tab": active_tab}

        return render(request, "messagesettings.html", context)

    if request.method == "POST":
        message_settings = DefaultResponse.objects.get(pk=1)

        active_tab = "messagesettings"
        first_message = request.POST.get("first_message")
        estimate_complete_message = request.POST.get("estimate_complete_message")

        if first_message:
            # check some sort of validity
            message_settings.first_message = first_message
            message_settings.save()

        if estimate_complete_message:
            # check some sort of validity
            message_settings.estimate_complete_message = estimate_complete_message
            message_settings.save()

        context = {"settings": message_settings, "active_tab": active_tab}

        return render(request, "messagesettings.html", context)


@login_required
@csrf_exempt
def documentation(request):
    if request.method == "GET":
        active_tab = "documentation"
        context = {"active_tab": active_tab}
        return render(request, "documentation.html", context=context)


@login_required
@csrf_exempt
def contact(request):
    if request.method == "GET":
        active_tab = "contact"
        context = {"active_tab": active_tab}
        return render(request, "contact.html", context=context)

    if request.method == "POST":
        active_tab = "contact"
        form_data = request.POST.dict()

        # You can now work with the form data as a regular Python dictionary
        email_subject = (
            f"{form_data['Priority Level']} Priority: {form_data['Subject']}"
        )
        email_body = ""
        for key, value in form_data.items():
            email_body += f"{key}:\n {value} \n\n"

        admin_contact = ["contact@eflexer.com", "amandacmwood@gmail.com"]
        try:
            send_mail(
                email_subject,
                email_body,
                config("EMAIL_SENDER"),
                admin_contact,
            )
            context = {"active_tab": active_tab, "success": True}
        except Exception as e:
            logger.info(f"Failed to send contact email: {e}")
            print(f"fail: {e}")
            context = {"active_tab": active_tab, "error": True}

        return render(request, "contact.html", context=context)


def check_emails(email_list):
    check_emails = email_list.split(",")
    check_emails = [email.strip() for email in check_emails]
    print(f"{check_emails}")
    for email in check_emails:
        if validate_email(email, verify=True):
            pass
        else:
            return f"{email}"

    return True


def check_phones(text):
    # Split the input text by commas and remove leading/trailing whitespace
    phone_list = [phone.strip() for phone in text.split(",")]

    # Create lists to store valid and invalid phone numbers
    valid_numbers = []
    invalid_numbers = []

    # Iterate through the phone numbers
    for phone in phone_list:
        try:
            parsed_number = phonenumbers.parse(phone, "US")
            if not phonenumbers.is_valid_number(parsed_number):
                invalid_numbers.append(phone)
            else:
                valid_numbers.append(parsed_number)
        except Exception as e:
            invalid_numbers.append(phone)

    # Check if there are any invalid phone numbers
    if invalid_numbers:
        error_numbers = f"{', '.join(invalid_numbers)}"
        return (error_numbers, False)

        # If all phone numbers are valid, format them in E.164 format
    formatted_numbers = [
        phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
        for number in valid_numbers
    ]
    formatted_list = ", ".join(formatted_numbers)
    return (formatted_list, True)


@login_required
@csrf_exempt
def phone_calls(request):
    if request.method == "GET":
        active_tab = "calls"
        update_phonecallinfo()

        # access all phone call data
        # Retrieve the PhoneCall and its related PhoneCallInfo in a single query
        phone_calls = (
            PhoneCall.objects.order_by("-datetime")
            .prefetch_related("phonecallinfo_set")
            .all()
        )

        context = {"phone_calls": phone_calls, "active_tab": active_tab}

        return render(request, "phonecalls.html", context)


@login_required
@csrf_exempt
def showcall(request, id):
    if request.method == "GET":
        active_tab = "calls"
        try:
            phone_call = PhoneCall.objects.prefetch_related("phonecallinfo_set").get(
                pk=id
            )
        except PhoneCall.DoesNotExist:
            return render(request, "404.html")

        audio_data = None

        for info in phone_call.phonecallinfo_set.all():
            if info.voicemail:
                audio_data = retrieve_audio_data(info.voicemail_link)

        context = {
            "call": phone_call,
            "active_tab": active_tab,
            "audio_data": audio_data,
        }
        return render(request, "showcall.html", context)


@login_required
@csrf_exempt
def formquestionSettings(request):
    if request.method == "GET":
        active_tab = "formsettings"
        questions = FormQuestion.objects.filter(deleted=False)
        context = {"questions": questions, "active_tab": active_tab}
        return render(request, "formsettings.html", context)
    if request.method == "POST":
        active_tab = "formsettings"
        question_list = request.POST.getlist("question")
        # update question list to ignore all blank fields
        question_list = [
            question for question in question_list if len(question.strip()) > 0
        ]

        # Find all existing questions with deleted=False and set them to deleted=True
        existing_questions = FormQuestion.objects.filter(deleted=False)
        existing_questions.update(deleted=True)

        # Add new questions
        for question_text in question_list:
            FormQuestion.objects.create(question_text=question_text)

        # access new questions and display
        questions = FormQuestion.objects.filter(deleted=False)
        context = {"questions": questions, "active_tab": active_tab}
        return render(request, "formsettings.html", context)


@login_required
@csrf_exempt
def accountSettings(request):
    if request.method == "GET":
        active_tab = "accountsettings"
        email = request.user.email
        username = request.user.username
        context = {"active_tab": active_tab, "email": email, "username": username}
        return render(request, "accountsettings.html", context)
    if request.method == "POST":
        if request.POST.get("email") != request.user.email:
            # Handle the case where the entered email doesn't match the user's email
            # You can return a response with an error message or render a template
            return HttpResponse("Error: The entered email doesn't match your account.")

        # Trigger sending the password reset email using PasswordResetView
        password_reset_view = PasswordResetView.as_view()
        password_reset_response = password_reset_view(request)

        # Check if the email was sent successfully
        if password_reset_response.status_code == 302:
            # Email sent successfully, redirect to "Settings" page with success message
            messages.success(
                request, "We have sent you an email to reset your password!"
            )
            return redirect("settings")


def retrieve_audio_data(recording_uri):
    account_sid = config("ACCOUNT_NUM")
    auth_token = config("AUTH_TOKEN")
    client = Client(account_sid, auth_token)
    media_url = "https://api.twilio.com" + recording_uri.replace(".json", "")

    # Create a session with authentication headers
    session = requests.Session()
    session.auth = (account_sid, auth_token)

    # Send a GET request to the media URL
    response = session.get(media_url)

    # Check if the request was successful
    if response.status_code == 200:
        audio_data = response.content
        audio_data = base64.b64encode(audio_data).decode("utf-8")
    else:
        audio_data = None

    return audio_data


def update_phonecallinfo():
    # Check for finished phone calls and update them
    calls = PhoneCall.objects.all()
    print("method invoked")

    for call in calls:
        call_info = PhoneCallInfo.objects.filter(call_num=call.pk).first()
        if call_info is None:
            # create new call info class
            # Access data via twilio
            # get call based on call sid
            # Your Twilio Account SID and Auth Token

            account_sid = config("ACCOUNT_NUM")
            auth_token = config("AUTH_TOKEN")
            client = Client(account_sid, auth_token)

            # Replace 'your_call_sid' with the actual Call SID you want to retrieve data for
            call_sid = call.call_sid

            # Retrieve the call using the call SID
            call_info = client.calls(call_sid).fetch()

            # if call is still ongoing skip this process
            if call_info.status in ["queued", "ringing", "in-progress"]:
                print("call in progress")
                pass

            else:
                print("call is finished")
                duration = call_info.duration
                voicemail_recordings = call_info.recordings.list()
                voicemail_links = ""
                if len(voicemail_recordings) < 1:
                    voicemail = False
                    voicemail_links = None
                else:
                    voicemail = True
                    for recording in voicemail_recordings:
                        voicemail_links = voicemail_links + f"{recording.uri}"

                phone_data = {
                    "duration": duration,
                    "voicemail": voicemail,
                    "voicemail_link": voicemail_links,
                    "call_num": call.pk,
                }

                new_phone_call_info = PhoneCallInfoSerializer(data=phone_data)
                if new_phone_call_info.is_valid():
                    print("this is executed 1")
                    new_phone_call_info.save()
    return


def get_lead_display():
    leads = Lead.objects.all()

    for lead in leads:
        lead_display = LeadDisplay.object.filter(lead=lead.pk).first()
        if lead_display is None:
            colors = [
                "magenta",
                "red",
                "orange",
                "gold",
                "green",
                "cyan",
                "geekblue",
                "purple",
            ]

            random_number = random.randint(0, 8)
            color = colors[random_number]

            name = f"Lead #{lead.pk}"

            display_data = {"color": color, "name": name, "lead": lead.pk}
            lead_display_serializer = LeadDisplaySerializer(data=display_data)
            if lead_display_serializer.is_valid():
                lead_display_serializer.save()
            else:
                logger.info("Lead Display Invalid")

    return LeadDisplay.objects.all()


# PASSWORD MANAGEMENT


# class CustomPasswordResetView(PasswordResetView):
#     template_name = "registration/password_reset_form.html"  # Custom HTML template for the password reset form
#     email_template_name = "registration/password_reset_email.html"  # Custom email template for the password reset email

#     def form_valid(self, form):
#         # Get the email entered in the password reset form
#         email = form.cleaned_data["email"]

#         # Check if the email exists in the User model (auth_user)
#         if User.objects.filter(email=email).exists():
#             # If the email exists, proceed with the password reset
#             return super().form_valid(form)
#         else:
#             # If the email does not exist, display an error message
#             form.add_error("email", "This email does not exist in our records.")
#             return self.form_invalid(form)
