# fundiconnect/sms_helpers.py
import requests
from django.conf import settings

def send_sms(phone_number, message):
    """
    Sends an SMS message using the Africa's Talking API.
    """
    # The AT SMS API requires the phone number in international format, e.g. +2547XXXXXXXX
    if not phone_number.startswith('+'):
        phone_number = f'+{phone_number}'
        
    url = 'https://api.africastalking.com/version1/messaging'
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'apiKey': settings.AFRICASTALKING_API_KEY
    }
    payload = {
        'username': settings.AFRICASTALKING_USERNAME,
        'to': phone_number,
        'message': message,
        'from': settings.AFRICASTALKING_SENDER_ID # Optional, but recommended
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        print(f"Africa's Talking SMS Response: {response.text}")
        if response.status_code == 201:
            return True
        else:
            return False
    except requests.exceptions.RequestException as e:
        print(f"Network error sending SMS: {e}")
        return False
