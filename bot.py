import os
import logging
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from dotenv import load_dotenv
from heyoo import WhatsApp
from flask import Flask, request, make_response, jsonify
import assemblyai as aai
from datetime import datetime
import json
import time

# from googletrans import Translator

# translator = Translator()

load_dotenv()
genai.configure(
    api_key=os.environ['API_KEY']
)
aai.settings.api_key = os.environ['AAI_API_KEY']
# Initialize Flask App
app = Flask(__name__)

# Initialize messenger functionality
messenger = WhatsApp(os.getenv("WHATSAPP_TOKEN"),
                     os.getenv("PHONE_ID"))
# User state management
user_states = {}

language = 'English'


class Complaint:
    def __init__(self, mobile, date, nature, location, complaint_id, status):
        self.mobile = mobile
        self.date = date
        self.nature = nature
        self.location = location
        self.complaint_id = complaint_id
        self.status = status

    def append_to_file(self, file_path="complaints.json"):
        complaint = {
            "mobile": self.mobile,
            "date": self.date,
            "nature": self.nature,
            "location": self.location,
            "complaint_id": self.complaint_id,
            "status": self.status
        }
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                complaints = json.load(file)
        else:
            complaints = []
        complaints.append(complaint)
        with open(file_path, "w") as file:
            json.dump(complaints, file, indent=4)

    @staticmethod
    def retrieve_by_id(complaint_id, file_path="complaints.json"):
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                complaints = json.load(file)
                for complaint in complaints:
                    if complaint["complaint_id"] == complaint_id:
                        return complaint
        return None

    @staticmethod
    def retrieve_all(file_path="complaints.json"):
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                complaints = json.load(file)
                return complaints
        return []


def main(chat):
    @app.route("/", methods=["GET", "POST"])
    def webhook():
        if request.method == "GET":
            return verify_webhook(request)
        elif request.method == "POST":
            data = request.get_json()
            if data is None:
                logging.error("No JSON data received")
                return "No JSON data received", 400
            logging.info("Received data: %s", data)
            changed_field = messenger.changed_field(data)
            return handle_messages(changed_field, data)
        return "Invalid request method", 405

    def retry_api_call(api_call, *args, retries=3, delay=2, **kwargs):
        for attempt in range(retries):
            try:
                return api_call(*args, **kwargs)
            except ResourceExhausted:
                if attempt < retries - 1:
                    time.sleep(delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise

    def verify_webhook(request):
        if request.args.get("hub.verify_token") == os.environ['VERIFY_TOKEN']:
            logging.info("Verified webhook")
            response = make_response(request.args.get("hub.challenge"), 200)
            response.mimetype = "text/plain"
            return response
        logging.error("Webhook Verification failed")
        return "Invalid verification token"

    def generate_complaint_id(nature, location):
        complaints = Complaint.retrieve_all()
        for complaint in complaints:
            if complaint["nature"] == nature and complaint["location"] == location:
                return complaint["complaint_id"]

        # Generate a new unique ID
        prefix = "C"
        existing_ids = {complaint["complaint_id"] for complaint in complaints}
        counter = 1
        new_id = f"{prefix}{counter:04d}"
        while new_id in existing_ids:
            counter += 1
            new_id = f"{prefix}{counter:04d}"
        return new_id

    def respond(user_input, instruction):
        try:
            response = retry_api_call(chat.send_message, instruction + user_input)
            return response.text
        except ResourceExhausted:
            return "API quota exceeded. Please try again later."

    def is_greeting(user_input):
        response = respond(user_input,
                           "Check if user's message is a greeting in either Zulu or English, respond with either True or "
                           "False only")
        return 'Yes' if response.strip() == 'True' else 'No'

    def is_language(user_input):
        languages = ['english', 'zulu']
        user_input = user_input.lower().strip()
        # Check if the user input is in the list of greetings
        return user_input in languages

    def log_message(message_type, message, mobile):
        log_file = "message_log.txt"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a") as f:
            f.write(f"{timestamp} - {message_type} - {mobile}: {message}\n")

    def checkComplaintPathway(user_input):
        response = respond(user_input, 'Check if message is to lodge or track a complaint in either Zulu or English. '
                                       'Respond with either Track or Lodge only.')
        return response.strip()

    def handle_messages(changed_field, data):
        if changed_field == "messages":
            new_message = messenger.get_mobile(data)
            if new_message:
                mobile = messenger.get_mobile(data)
                message_type = messenger.get_message_type(data)
                if message_type == "text":
                    message = messenger.get_message(data)  # using original method
                    if mobile in user_states:
                        # Continue the process based on the state
                        if user_states[mobile] == "complaint_lodging":
                            handle_complaint_process(mobile, message)
                        elif user_states[mobile] == "complaint_tracking":
                            handle_tracking_process(mobile, message)
                    else:
                        handle_text_message(message, mobile)
                elif message_type == "location":
                    handle_location_message(data, mobile)
                elif message_type == "image":
                    image = messenger.get_image(data)
                    image_id, mime_type = image["id"], image["mime_type"]
                    image_url = messenger.query_media_url(image_id)
                    image_filename = messenger.download_media(image_url, mime_type)
                    response = respond(image_filename, 'Analyse the image and return insights on the image')
                    messenger.send_message(response, mobile)
                elif message_type == 'audio':
                    handle_audio_messages(data, mobile)
                elif message_type == 'interactive':
                    handle_interactive_message(data, mobile)
                # elif message_type == 'location':
                #     handle_location_message(data, mobile)
                else:
                    messenger.send_message(message="Please send me text messages", recipient_id=mobile)
            return jsonify({'status': 'success'}), 200
        return jsonify({'error': 'No messages found'}), 404

    def handle_text_message(message, mobile):
        if len(message) > 4096:
            message = message[:4096]
        greeting_status = is_greeting(message)
        if str(greeting_status) != 'No':
            send_language_buttons(mobile)
        else:
            response = respond(message, 'Respond as a Durban Municipality assistant. Do not include emojis')
            logging.info("\nResponse: %s\n", response)
            messenger.send_message(message=f"{response}", recipient_id=mobile)
            log_message('Text', response, mobile)
        return "ok"

    def handle_location_message(data, mobile):
        message_location = messenger.get_location(data)
        message_latitude = message_location["latitude"]
        message_longitude = message_location["longitude"]
        logging.info("Location: %s, %s", message_latitude, message_longitude)
        user_states[f"{mobile}_location"] = f"Latitude: {message_latitude}, Longitude: {message_longitude}"
        handle_complaint_process(mobile, 'Sent location')

    def handle_audio_messages(data, mobile):
        audio = messenger.get_audio(data)
        audio_id, mime_type = audio["id"], audio["mime_type"]
        audio_url = messenger.query_media_url(audio_id)
        audio_filename = messenger.download_media(audio_url, mime_type)
        logging.info(f"{mobile} sent audio {audio_filename}")
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_filename)
        if transcript.status == aai.TranscriptStatus.error:
            result = transcript.error
        else:
            result = transcript.text
        if len(result) > 4096:
            result = result[:4096]  # Truncate text to fit within limit
        messenger.send_message(result, mobile)

    def handle_interactive_message(data, mobile):
        message_response = messenger.get_interactive_response(data)
        interactive_type = message_response.get("type")
        message_id = message_response[interactive_type]["id"]
        message_text = message_response[interactive_type]["title"]
        complaintPathway = checkComplaintPathway(message_text)
        if is_language(message_text):
            handle_language_selection(mobile, message_text)
        elif complaintPathway == 'Lodge':
            user_states[mobile] = "complaint_lodging"
            user_states[f"{mobile}_stage"] = "start"
            response = respond('A user wants to lodge a complaint', 'Ask for the nature of the complaint, keep your '
                                                                    f'response short, precise and polite.Reply in {language}')
            messenger.send_message(response, mobile)
        elif complaintPathway == 'Track':
            user_states[mobile] = "complaint_tracking"
            user_states[f"{mobile}_stage"] = "start"
            response = respond('A user wants to track a complaint', 'Ask for the ID of the complaint, keep your '
                                                                    f'response short, precise and polite.Reply in {language}')
            messenger.send_message(response, mobile)
        logging.info(f"Interactive Message {message_id}: {message_text}")
        return "ok"

    def send_language_buttons(mobile):
        messenger.send_reply_button(
            recipient_id=mobile,
            button={
                "type": "button",
                "body": {
                    "text": "Welcome! What language would you like to communicate in?"
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": "b1",
                                "title": "Zulu"
                            }
                        },
                        {
                            "type": "reply",
                            "reply": {
                                "id": "b2",
                                "title": "English"
                            }
                        },
                    ]
                }
            },
        )
        log_message('Interactive', 'Language Selection', mobile)

    def handle_language_selection(mobile, message_text):
        global language
        if message_text == 'Zulu':
            language = 'Zulu'
            messenger.send_reply_button(
                recipient_id=mobile,
                button={
                    "type": "button",
                    "body": {
                        "text": "Siyakwamukela! Yini ongathanda ukuyisiza namuhla?"
                    },
                    "action": {
                        "buttons": [
                            {
                                "type": "reply",
                                "reply": {
                                    "id": "c1",
                                    "title": "Faka isikhalazo"
                                }
                            },
                            {
                                "type": "reply",
                                "reply": {
                                    "id": "c2",
                                    "title": "Landelela isikhalazo"
                                }
                            },
                            {
                                "type": "reply",
                                "reply": {
                                    "id": "c3",
                                    "title": "Usizo Olukhulu"
                                }
                            },
                        ]
                    }
                },
            )
        else:
            language = 'English'
            messenger.send_reply_button(
                recipient_id=mobile,
                button={
                    "type": "button",
                    "body": {
                        "text": "Welcome! What would you like assistance with today?"
                    },
                    "action": {
                        "buttons": [
                            {
                                "type": "reply",
                                "reply": {
                                    "id": "d1",
                                    "title": "Lodge a complaint"
                                }
                            },
                            {
                                "type": "reply",
                                "reply": {
                                    "id": "d2",
                                    "title": "Track a complaint"
                                }
                            },
                            {
                                "type": "reply",
                                "reply": {
                                    "id": "d3",
                                    "title": "General Assistance"
                                }
                            },
                        ]
                    }
                },
            )
        log_message('Interactive', 'Operation Selection', mobile)

    def handle_complaint_process(mobile, text):
        stage = user_states[f"{mobile}_stage"]
        if stage == "start":
            user_states[f"{mobile}_nature"] = text
            user_states[f"{mobile}_stage"] = "date"
            response = respond('Lodge a complaint', 'Ask the user to provide the date of the incident. Keep your '
                                                    'response'
                                                    f'short, precise and polite.Respond in {language}')
            messenger.send_message(response, mobile)
        elif stage == "date":
            user_states[f"{mobile}_date"] = text
            user_states[f"{mobile}_stage"] = "location"
            response = respond('Lodge a complaint', 'Ask the user to provide the location of the incident. Keep your '
                                                    'response'
                                                    f'short, precise and polite.Respond in {language}')
            messenger.send_message(response, mobile)
        elif stage == "location":
            complaint_id = generate_complaint_id(user_states[f"{mobile}_nature"], user_states[f"{mobile}_location"])
            user_states[f"{mobile}_complaint_id"] = complaint_id
            # Save the complaint
            complaint = Complaint(
                mobile=mobile,
                date=user_states[f"{mobile}_date"],
                nature=user_states[f"{mobile}_nature"],
                location=user_states[f"{mobile}_location"],
                complaint_id=user_states[f"{mobile}_complaint_id"],
                status='Received'
            )
            complaint.append_to_file()
            messenger.send_message(f"Your complaint has been lodged successfully with ID: {complaint_id}", mobile)
            nature = user_states[f'{mobile}_nature']
            response = respond(nature,
                               f'Inform the user that their complaint with ID : {complaint_id} has been lodged successfully. Give some tips pertaining the complaint at hand.Respond in {language}')
            messenger.send_message(response, mobile)
            # Clear the state
            del user_states[mobile]
            del user_states[f"{mobile}_nature"]
            del user_states[f"{mobile}_location"]
            del user_states[f"{mobile}_date"]
            del user_states[f"{mobile}_complaint_id"]
            del user_states[f"{mobile}_stage"]

    def handle_tracking_process(mobile, text):
        if user_states[f"{mobile}_stage"] == "start":
            complaint = Complaint.retrieve_by_id(text)
            if complaint:
                response_text = (f"Complaint ID: {complaint['complaint_id']}\n"
                                 f"Nature: {complaint['nature']}\n"
                                 f"Date: {complaint['date']}\n"
                                 f"Mobile: {complaint['mobile']}")
                response = respond(response_text, f'Inform the user about their complaint.Respond in {language}')
                messenger.send_message(response, mobile)
            else:
                response = respond(text, f'Inform the user that their complaint with the provided ID, has not been '
                                         f'found.Respond in {language}')
                messenger.send_message(response, mobile)
            # Clear the state
            del user_states[mobile]
            del user_states[f"{mobile}_stage"]


if __name__ == "__main__":
    model = genai.GenerativeModel(
        "gemini-1.5-pro-latest"
    )
    chat = model.start_chat()
    main(chat=chat)
    app.run(port=5000, debug=False)
