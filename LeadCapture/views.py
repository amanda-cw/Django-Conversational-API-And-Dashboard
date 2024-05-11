# LIBRARIES AND DEPENDENCIES
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import JSONParser
from django.utils import timezone
from django.http.response import JsonResponse
from django.db.models import Max
from LeadCapture.models import (
    Lead,
    Message,
    Form,
    FormQuestion,
    FormResponse,
    PhoneCall,
    APIKey,
)
from LeadCapture.serializers import (
    LeadSerializer,
    MessageSerializer,
    FormSerializer,
    PhoneCallSerializer,
)
import tiktoken
import requests
from decouple import config
import openai
import os
from django.core.mail import send_mail
from twilio.rest import Client
from twilio.twiml.voice_response import Gather, Pause, Record, Say, VoiceResponse
import json
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

# from .models import APIKey
from django.http import HttpResponse, HttpRequest
import time
import datetime

from Dashboard.models import Notifications, DefaultResponse

notifications = Notifications.objects.get(pk=1)
defaultresponse = DefaultResponse.objects.get(pk=1)


def show_notification(request):
    notifications = Notifications.objects.get(pk=1)
    return HttpResponse(f"{notifications.voicemail_email}")


# API KEY CREATION
class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header.split(" ")[1]
            try:
                api_key_obj = APIKey.objects.get(key=api_key)
                logger.error("something")
                return (api_key_obj.user, None)
            except APIKey.DoesNotExist:
                logger.error("api key does not exist")
                raise AuthenticationFailed("No such API key")

        return None


# Form Trigger Words To Start The Form
# General Error message returned to the user if something goes wrong
form_trigger = ["estimate", "'estimate'", '"estimate"']
general_error = "Sorry, it looks like our chatbot is currently experiencing issues. In the meantime, please feel welcome to email us at drainageprofessional@gmail.com, call us at (727) 945-2179, or fill out an estimate form at www.drainageprofessional.com/contact."

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


# Our Main Entry Point for API
# Accepts the following parameters:
# message - the text content of the message
# token - a token associated with the user (can be phone number, Facebook token, browser cookie)
# platform - the platform the message was sent from (text, Facebook, website chatbot, etc.)

# This handler checks if the user has messaged before and saves them as a lead if they have not
# It then decides how to process the message based on the Lead's "form" attribute
# If form is true, we send the message over to the "handle_form" function
# If form is not true, we send the message over to the "process_message" function

# If a user wants to start the form, they send over a trigger word such as "estimate"
# We check if the message is the trigger word, if it is, form is set to true


@api_view(["POST"])  # Decorate the view function with the appropriate HTTP methods
@authentication_classes([APIKeyAuthentication])  # Add API key authentication
@permission_classes([IsAuthenticated])  # Add permission to ensure authenticated users
@csrf_exempt
@csrf_exempt
def leadAPI(request):
    if request.method == "POST":
        try:
            # lead data is extracted from the request
            lead_data = JSONParser().parse(request)

            # Isolate the contents of the message from the lead data
            incoming_message = lead_data.pop("message", None)

            # Scan Lead objects to see if this Lead already exists (has sent a message before)
            existing_lead = Lead.objects.filter(token=lead_data.get("token")).first()

            # If the token has not been seen before, serialize the data and save it
            if existing_lead is None:
                lead_serializer = LeadSerializer(data=lead_data)
                if lead_serializer.is_valid():
                    existing_lead = lead_serializer.save()
                    response_message = "Added successfully!"
                    existing_lead.name = f"Lead #{existing_lead.pk}"
                    existing_lead.save()
                else:
                    logger.error(
                        "An error occurred: Failed to add new lead successfully"
                    )
                    return JsonResponse(general_error, safe=False)
            else:
                response_message = "Token already exists; no new entry created."

            # Check if form = True
            if existing_lead.form:
                outgoing_message = handle_form(existing_lead, incoming_message)
                # outgoing message will be retrieved from "handle_form"

            # If form is not true, we should check if the user used the trigger word
            elif incoming_message:
                if incoming_message.lower().strip() in form_trigger:
                    # Trigger word is present, so we process the incoming message to handle form
                    outgoing_message = handle_form(existing_lead, incoming_message)
                else:
                    # Trigger word is not present, so we send the message to "process_message"
                    outgoing_message = process_message(existing_lead, incoming_message)

            else:
                # assuming something has gone wrong and there is no message, we return general error
                logger.error("An error occurred: No message was sent")
                outgoing_message = general_error

            # return the contents of "outgoing_message" back to the user
            return JsonResponse(outgoing_message, safe=False)
        except:
            # assuming something has gone wrong
            logger.error("An error occurred: Access to POST method failed")
            return JsonResponse(general_error)


# Processes incoming message and returns a response from OpenAI API
# The OpenAI API has been given a system message full of information about the business
# OpenAI is instructed to act as a "representative" and answer questions about the company
# We access the full conversation history from the user's messages in the SQL database
# We trim the conversation history to a token size of 1024 to prevent overflow but give adequate context
# A message is returned from OpenAI back to the user
def process_message(user, incoming_message):
    try:
        # configure openai API key
        openai.api_key = config("OPENAI_API_KEY")

        # Fetcg the entire conversation history from the user based on the user ID
        # We only choose messages where form=False!!
        # this is to to prevent chatgpt from becoming confused
        # and also to prevent sensitive data like addresses, phone numbers, etc
        # from being passed into the OpenAI API
        messages = Message.objects.filter(user=user.id, form=False)

        # Initialize our empty chat log
        chat_log = []

        # Iterating through the messages and constructing the chat log based on OpenAI documentation
        # message.message represents the incoming message from the user
        # message.response represents the outgoing message from openai
        # these are assigned their proper roles so OpenAI can understand conversation context
        for message in messages:
            chat_log.append({"role": "user", "content": message.message})
            chat_log.append({"role": "assistant", "content": message.response})

        # Now, we add our incoming recent message to the most recent user message
        chat_log.append({"role": "user", "content": incoming_message})

        # We access our company information and prompt which is contained in the system.txt file
        try:
            # read_system_file() is a function that opens and reads the system.txt file
            content = read_system_file()
        except Exception as e:
            logger.error(f"An error occurred: System file read failed: {e}")
            return general_error

        # Now we create our system message containing Openai's instructions
        system_message = {"role": "system", "content": content}

        # We insert that system message to the very front of the chat_log
        chat_log.insert(0, system_message)

        # We now iterate through the entire chatlog and shorten it to 1024 tokens
        # however, we preserve the system message and most recent message hence del chat_log[1] not [0]
        try:
            while count_tokens(chat_log) > 1024:
                del chat_log[1]
        except Exception as e:
            logger.error(f"An error occurred: Counting tokens failed: {e}")
            return general_error

        # Get response from openai with ChatCompletion
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo", messages=chat_log
            )
        except Exception as e:
            logger.error(f"An error occurred: OpenAI API failed: {e}")
            return general_error

        # Access the text string of OpenAI's response
        outgoing_message = response["choices"][0]["message"]["content"]

        # Save OpenAI's response as the outgoing message into our save_message serializer
        # save_message() is a function that contains a serializer saving this message data type
        # form=False because this is NOT a message that belongs to our form function
        form = False
        save_message(user, incoming_message, outgoing_message, form)

        # We return the outgoing message from ChatGPT to the main function as our response to the user
        return outgoing_message
    except Exception as e:
        logger.error(f"An error occurred: process message failed: {e}")


# Processing incoming message and returns a response from our form questionaire
# A series of "form_question" objects exist that represent estimate/quote request forms
# When the user says the trigger word, this function sets form=True, and handle_form returns the first question
# Now, when form=True, all incoming messages are assigned to the previous question
# This iterates all the way through until all questions have been answered by the user
# Once the form is complete, form is now set to False and messages are no longer sent to handle_form


# the logic in this is a little complicated to handle all possible scenarios, could be simplified
def handle_form(user, incoming_message):
    # Retrieve the user's most recent form data or create a new one if not exists
    try:
        try:
            # find existing user forms based on user.id, and select the most recent one by date
            user_forms = Form.objects.filter(user_id=user.id).order_by("-datetime")

            # Perform this if the user form already exists
            if user_forms.exists():
                # access the most recent form in the list
                most_recent_form = user_forms.first()
                if user.form:
                    # If user.form = True, they are currently filling one out
                    # No form needs to be created because they are currently filling one out
                    user_form = most_recent_form
                    created = None
                else:
                    # If user.form=False, they are not currently filling a form out
                    # A new form needs to be created, so created=True
                    # The user's form status needs to now be updated to Form=True
                    user_form = Form.objects.create(
                        user_id=user.id, datetime=timezone.now()
                    )
                    created = True
                    user.form = True
            else:
                # There are no existing forms for this user, so we are creating their very first
                # A new form needs to be created, so created=True
                # The user's form status needs to now be updated to Form=True
                user_form = Form.objects.create(
                    user_id=user.id, datetime=timezone.now()
                )
                created = True
                user.form = True

        except Form.MultipleObjectsReturned:
            # Same logic as above, but for multiple forms that have been created
            # We need to access the most recent one
            most_recent_form = user_forms.first()
            if user.form:
                # If user.form = True, they are currently filling one out
                # No form needs to be created because they are currently filling one out
                user_form = most_recent_form
                created = None
            else:
                # If user.form=False, they are not currently filling a form out
                # A new form needs to be created, so created=True
                # The user's form status needs to now be updated to Form=True
                user_form = Form.objects.create(
                    user_id=user.id, datetime=timezone.now()
                )
                created = True
                user.form = True

        if created:
            # If a form was created from the previous logic, we present them with the FIRST question
            # We set user.form=True and save that data
            user_form.user.form = True
            user_form.user.save()
            # We access the first question from the FormQuestion objects
            first_question = FormQuestion.objects.filter(deleted=False).first()
            # Our response outgoing message is the first question
            response = (
                f"Please answer the following question: {first_question.question_text}"
            )
        else:
            # This is not the first question in the form, so we must find the next one to be answered
            # We exclude all questions that have already been answered (excluding form)
            # FormQuestion.objects - we query the database for existing Form Question objects
            # .exclude(formresponse__form=user_form) - we ignore any questions that are already associated with the current form we are filling out
            # .first() - we access the first one from this list (as that is the next question to answer)

            # Deleted handles Soft Delets
            # This way if we delete or update our questions, form responses will be saved
            # But deleted questions will not be pushed to the user
            next_question = (
                FormQuestion.objects.filter(deleted=False)
                .exclude(formresponse__form=user_form)
                .first()
            )

            # if there is a next question (there always will be, but we say if so we can catch possible errors and prevent a loop)
            if next_question:
                # The user's answer is the incoming message
                user_answer = incoming_message
                # We assign the incoming message to this unanswered nexxt_question in the Form Response
                FormResponse.objects.create(
                    form=user_form, question=next_question, response=user_answer
                )

                # Now we access the next question after the one we just answered
                next_question = (
                    FormQuestion.objects.filter(deleted=False)
                    .exclude(formresponse__form=user_form)
                    .exclude(pk=next_question.pk)
                    .first()
                )

                if next_question:
                    # If there is another question to answer, we return the next question to the user
                    response = f"Please answer the following question: {next_question.question_text}"
                else:
                    defaultresponse = DefaultResponse.objects.get(pk=1)
                    # If there are no more questions to answer, we end form mode
                    # form is now set to false
                    # we save the user form data
                    # we enact "send_data()" which sends the form data to the business owner
                    # we return "estimate complete message" which says something like "thanks for filling out the form!"
                    user_form.user.form = False
                    user_form.user.save()
                    send_data(user_form)
                    # response = config("ESTIMATE_COMPLETE_MESSAGE")
                    response = defaultresponse.estimate_complete_message
            else:
                # This case should not be reached unless there's an issue with the model or questions
                response = general_error

        # We save the incoming message and our form response as a message object in our sql database
        # The "True" indicates that this message belongs to the form response model, not the OpenAI one
        save_message(user, incoming_message, response, True)
        return response
    except Exception as e:
        logger.error(f"An error occurred: Form method failed because: {e}")
        return general_error


# Our function that saves the message object for easy retrieval for later in our SQL Database
def save_message(user, incoming, outgoing, form):
    try:  # create new message data object and populate it with the parameters
        # The significance of the "form" in the message object
        # We want to know if our message belongs to the form or to the general OpenAI Conversation
        # we do not want openAI to recieve the information from the form messages because it's private information like addresses, etc.abs
        # by saving Form boolean, we can exclude form messages from OpenAI conversation history
        message_data = {
            "user": user.id,
            "datetime": timezone.now(),
            "message": incoming,
            "response": outgoing,
            "form": form,  # will save as true or false
        }
        # serialize and add to database
        message_serializer = MessageSerializer(data=message_data)

        # Check that it's valid and save

        if message_serializer.is_valid():
            message_serializer.save()
        else:
            # handle message save errors
            return general_error
    except Exception as e:
        logger.error(f"An error occurred: saving message failed {e}")
        return general_error


# Counting tokens in messages sent over to OpenAI
# Basic tiktoken library, this is to prevent errors like sending messages that go over the token limit
def count_tokens(messages):
    num_tokens = 0
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    for i in range(0, len(messages)):
        num_tokens = num_tokens + len(encoding.encode(messages[i]["content"]))
    return num_tokens


# Reads system.txt file
# System.txt file contains a set of instructions for ChatGPT on how to behave as a customer service rep
# System.txt also contains a bunch of information about the company like hours of operations, services, contact info, etc
# This is the "prompt" - See prompt engineering in ChatGPT to optimize its behavior
def read_system_file():
    app_directory = os.path.dirname(
        __file__
    )  # Directory of the current module (views.py)
    file_path = os.path.join(app_directory, "files", "system.txt")

    with open(file_path, "r") as file:
        content = file.read().strip()  # Remove leading/trailing whitespaces

    return content


# This function sends the contents of the COMPLETED form data to the business owner or any other recipients
# We use twilio to send the text message, and django backend email to send the emails
def send_data(user_form):
    try:
        # Retrieve all the FormResponses associated with the Form
        form_responses = FormResponse.objects.filter(form=user_form)

        results = ""
        # Access form questions and responses and append them to a string
        for response in form_responses:
            question_text = response.question.question_text
            response_text = response.response
            results += f"{question_text}:\n{response_text}\n\n\n"

        # Create our email subject and email body
        email_subject = f"New Estimate for {form_responses[3].response} on {user_form.datetime.strftime('%Y-%m-%d %I:%M:%S')}"
        email_body = results

        # Access all of the emails that will recieve the contents of the user form
        notifications = Notifications.objects.get(pk=1)
        emails_string = notifications.form_email

        # Split the string into individual email addresses
        email_list = emails_string.split(",")

        # Remove any leading/trailing whitespaces from each email
        email_list = [email.strip() for email in email_list]

        # Send the email using Django's send_mail function
        send_mail(
            email_subject,
            email_body,
            config("EMAIL_SENDER"),
            email_list,
        )

        # Sending results via text

        # Configure Twilio account authorization
        account_sid = config("ACCOUNT_NUM")
        auth_token = config("AUTH_TOKEN")
        client = Client(account_sid, auth_token)

        # Access all of the phone numbers to recieve the form responses
        phones_string = notifications.form_phone

        # Split the string into individual phone numbers
        phone_list = phones_string.split(",")

        # Remove any leading/trailing whitespaces from each phone
        phone_list = [phone.strip() for phone in phone_list]

        # send the text to each phone
        for phone in phone_list:
            message = client.messages.create(
                from_=config("PHONE_NUMBER"),
                body=f"Estimate Request From {form_responses[0].response} on {user_form.datetime.strftime('%Y-%m-%d %I:%M:%S')}\n\n {results}",
                to=phone,
            )
    except Exception as e:
        logger.error(f"An error occurred: Send data method failed: {e}")


# Handle inbound phone calls to our Twilio number
# When the user calls the business phone number, missed calls are forwarded to the Twilio phone number
# The twilio phone number has a webhook that sends it to here
# Here we process the phone call with a pre recorded message containing some instructions
# The user can press a number to recieve a text from the automated AI
# Or they can just leave a message and have that message texted/emailed to the business owner
# Whenever the user presses a digit on the keypad, this function is evoked again!!
# this is why we check digit_pressed initially and the logic is non-linear
@csrf_exempt
def inbound_phonecall(request):
    if request.method == "POST":
        # Create the voice response object
        response = VoiceResponse()

        # get call sid
        callsid = request.POST.get("CallSid")

        # get from number
        number = request.POST.get("From")

        # save and process phone call, create any new leads for phone call
        save_call(number, callsid)

        # Check if the user has pressed any digits
        digit_pressed = request.POST.get("Digits")

        # if digit pressed is none, they have just called and will hear the initial message
        if digit_pressed is None:
            # Play the pre-recorded message only if no digit has been pressed
            initial_message = (
                "Hi, this is David Wood. Sorry I missed your call. "
                "If you're calling to learn more about Drainage Professional "
                "and want to receive more information, please press 1 on the keypad. "
                "You will receive a text message from our personal assistant "
                "with further details and an estimate form. "
                "You can leave a message by pressing 2 now or leaving a message after the tone."
            )
            response.say(initial_message, voice="alice")

            # gather the response digit
            gather = Gather(numDigits=1, timeout=10)
            gather.say("Press 1 to receive a message, or press 2 to leave a message.")
            response.append(gather)

        # Handle user input based on the pressed digit
        # 1 represents that the user wants to recieve a text message from our automated AI bot
        if digit_pressed == "1":
            response.say(
                "Thank you for requesting more information. You will receive a text message shortly."
            )
            # access the phone number of the user
            number = request.POST.get("From")
            # send an introductory text to that user
            send_text(number, callsid)
            # serialize call - recieved text = true

        # if digit pressed is 2, they just want to leave an audio message
        elif digit_pressed == "2":
            response.say("No problem. Please leave your message after the tone.")
            response.record(
                action="/handle-recording",
                maxLength=120,
                transcribe=True,
                transcribeCallback="/handle-transcription",
            )
            # serialize call - recieve text = false
        else:
            # if no digit is pressed, automatically send a text message
            response.say(
                "No response received. Please leave your message after the tone."
            )
            response.record(
                action="/handle-recording",
                maxLength=120,
                transcribe=True,
                transcribeCallback="/handle-transcription",
            )
            # serialize call - recieve text = false
            # Check if the call is completed (using call status)

        return HttpResponse(str(response), content_type="application/xml")

    else:
        # Return a default response for other HTTP methods
        return HttpResponse("Method not allowed", status=405)


# handle message
# if the user opted to recieve a text message to fill out the estimate form
# their number will be saved into the sql system somewhere, they will be saved as a lead
# then they will recieve a text from twilio number initiating conversation
# this sends the default first text to the person
def send_text(number, callsid):
    existing_call = PhoneCall.objects.filter(call_sid=callsid).first()

    if existing_call is None:
        save_call(number, callsid)

    existing_call.receive_text_field = True
    existing_call.save()

    account_sid = config("ACCOUNT_NUM")
    auth_token = config("AUTH_TOKEN")
    client = Client(account_sid, auth_token)

    defaultresponse = DefaultResponse.objects.get(pk=1)
    try:
        message = client.messages.create(
            from_=config("PHONE_NUMBER"),
            body=defaultresponse.first_message,
            to=number,
        )
    except Exception as e:
        logger.info(f"Error sending text message: {e}")
        return

    existing_lead = Lead.objects.filter(token=number).first()
    # If the token has not been seen before, serialize the data and save it
    if existing_lead is None:
        phone_lead(number)

    message_data = {
        "user": existing_lead.pk,
        "datetime": timezone.now(),
        "message": "Hello",
        "response": defaultresponse.first_message,
        "form": False,  # will save as true or false
    }
    save_message = MessageSerializer(data=message_data)
    if save_message.is_valid():
        save_message.save()
    else:
        logger.info("First optin text failed to save")


@csrf_exempt
def phone_lead(number):
    existing_lead = Lead.objects.filter(token=number).first()
    # If the token has not been seen before, serialize the data and save it
    if existing_lead is None:
        lead_data = {"token": number, "platform": "phone", "form": False}
        # serialize and add to database
        lead_serializer = LeadSerializer(data=lead_data)
        if lead_serializer.is_valid():
            lead_serializer.save()
        else:
            return
    else:
        return


@csrf_exempt
def save_call(number, callsid):
    existing_call = PhoneCall.objects.filter(call_sid=callsid).first()

    if existing_call is None:
        lead = Lead.objects.filter(token=number).first()

        if lead is None:
            # If there's no matching Lead, create a new one
            lead = phone_lead(number)

        if lead is not None:
            phone_call_data = {
                "from_field": number,
                "call_sid": callsid,
                "datetime": timezone.now(),
                "lead": lead.pk,
            }
            new_call_serializer = PhoneCallSerializer(data=phone_call_data)
            if new_call_serializer.is_valid():
                new_call_serializer.save()
            else:
                logger.info(
                    f"Call serializer failed, was invalid. Phone data: {phone_call_data}"
                )


# This is the function for handling the voicemail recording
# We are processing the voicemail recording and attaching the audio recording to an email
# We email this audio recording to whatever email recipients are set
@csrf_exempt
def handle_recording(request):
    print(request.POST)

    account_sid = config("ACCOUNT_NUM")
    auth_token = config("AUTH_TOKEN")
    client = Client(account_sid, auth_token)

    recording_url = request.POST.get(
        "RecordingUrl"
    )  # Get the URL of the recorded audio

    caller_number = request.POST.get("Caller")

    logger.info(f"{recording_url}, {caller_number}")
    # Perform actions with the recording URL, such as sending an email with the audio attachment
    send_email_with_audio(recording_url, caller_number)

    # Create a TwiML response to acknowledge the handling of the recording
    response = VoiceResponse()
    response.say("Thank you for leaving a message. Your message has been recorded.")

    return HttpResponse(str(response), content_type="application/xml")


# This is the function for handling the transcription of the voicemail recording
# We process the audio transcription and send it as a text to the desired recipients
# We say the date, the number it's from, and the transcribed message
@csrf_exempt
def handle_transcription(request):
    account_sid = config("ACCOUNT_NUM")
    auth_token = config("AUTH_TOKEN")
    client = Client(account_sid, auth_token)

    transcription_text = request.POST.get("TranscriptionText")

    customer_number = request.POST.get("From")

    notifications = Notifications.objects.get(pk=1)

    phones_string = notifications.voicemail_phone

    # Split the string into individual email addresses
    phone_list = phones_string.split(",")

    # Remove any leading/trailing whitespaces from each email
    phone_list = [phone.strip() for phone in phone_list]

    for phone in phone_list:
        message = client.messages.create(
            from_=config("PHONE_NUMBER"),
            body=f"New Message from {customer_number} on {timezone.localtime(timezone.now()).strftime('%Y-%m-%d %I:%M:%S')} - '{transcription_text}'",
            to=phone,
        )

    return HttpResponse("success", content_type="application/xml")


# This is the function that sends the email from handle_recording
def send_email_with_audio(recording_url, caller_number):
    # Code to send an email with the audio recording as an attachment
    # You can use a library like smtplib or Django's EmailMessage
    # Example using EmailMessage:
    from django.core.mail import EmailMessage

    account_sid = config("ACCOUNT_NUM")
    auth_token = config("AUTH_TOKEN")
    client = Client(account_sid, auth_token)

    notifications = Notifications.objects.get(pk=1)
    emails_string = notifications.voicemail_email

    # Split the string into individual email addresses
    email_list = emails_string.split(",")

    # Remove any leading/trailing whitespaces from each email
    email_list = [email.strip() for email in email_list]

    email = EmailMessage(
        f"New Voicemail From {caller_number} on {timezone.localtime(timezone.now()).strftime('%Y-%m-%d %I:%M:%S')}",
        f"You have recieved a voicemail message {caller_number} on {timezone.localtime(timezone.now()).strftime('%Y-%m-%d %I:%M:%S')}. The voicemail message is attached.",
        config("EMAIL_SENDER"),
        email_list,
    )
    recording_content = fetch_audio_data(recording_url)

    email.attach("recording.wav", recording_content, "audio/wav")
    email.send()


# This is the function that accesses the audio data of the voicemail message from handle_recording
def fetch_audio_data(recording_url):
    account_sid = config("ACCOUNT_NUM")
    auth_token = config("AUTH_TOKEN")
    auth = (account_sid, auth_token)

    with requests.get(recording_url, stream=True, auth=auth) as r:
        if r.status_code == 200:
            return r.raw.read()
        else:
            logger.info(f"Failed to fetch audio data. Status code: {r.status_code}")
            return None


def process_phonecall(sid, recieved_text):
    # Your Twilio Account SID and Auth Token
    account_sid = config("ACCOUNT_NUM")
    auth_token = config("AUTH_TOKEN")

    # Create a Twilio client
    client = Client(account_sid, auth_token)

    # Retrieve the call details
    call = client.calls(sid).fetch()

    print(f"{call.duration}")
    print(f"{call.call_sid}")


# This is the api view for when the Twilio phone number gets a text message
# The number sends a webhook to this (incoming message)
# It processes the data and sends the correct parameters over to our main function (at the top)
# It recieves a response, then returns that response back to the user who texted
@api_view(["POST"])
@csrf_exempt
def incoming_message(request):
    if request.method == "POST":
        try:
            message = request.POST.get("Body")
            platform = "text"
            token = request.POST.get("From")

            data = {"message": message, "platform": platform, "token": token}
            json_data = json.dumps(data)

            # headers = {"Authorization": f"Bearer {config('APP_API_KEY')}"}

            current_host = request.get_host()  # Get the current host (domain)
            url = f"http://{current_host}/api"

            # Send a POST request using the requests library
            response = requests.post(url, data=json_data)

            response_data = response.json()  # Parse JSON response content

            # response_data = json.loads(response.content)

            # return a text message back to the user
            account_sid = config("ACCOUNT_NUM")
            auth_token = config("AUTH_TOKEN")
            client = Client(account_sid, auth_token)

            message = client.messages.create(
                from_=config("PHONE_NUMBER"),
                body=response_data,
                to=token,
            )

            return HttpResponse("success")
        except Exception as e:
            logger.info(f"Error has occured in recieving text message: {e}")
            # return a text message back to the user
            account_sid = config("ACCOUNT_NUM")
            auth_token = config("AUTH_TOKEN")
            client = Client(account_sid, auth_token)

            message = client.messages.create(
                from_=config("PHONE_NUMBER"),
                body=general_error,
                to=request.POST.get("From"),
            )
            return HttpResponse("failure")
