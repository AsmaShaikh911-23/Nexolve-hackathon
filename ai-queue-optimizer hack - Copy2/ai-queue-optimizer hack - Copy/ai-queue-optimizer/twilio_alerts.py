from twilio.rest import Client

account_sid = "AC2bddc98e5e0803f72ebdc051b18275f7"
auth_token = "24a09de7b779876b24015573523e4a94"
from_number = "+12673231834"
client = Client(account_sid, auth_token)

def send_alert(phone, message):
    client.messages.create(
        body=message,
        from_=from_number,
        to=phone
    )
