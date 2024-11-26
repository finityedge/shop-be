from twilio.rest import Client

class WhatsAppHelper:
    def __init__(self, account_sid, auth_token, from_number):
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number

    def send_whatsapp_message(self, to_number, message):
        message = self.client.messages.create(
            body=message,
            from_='whatsapp:' + self.from_number,
            to='whatsapp:' + to_number
        )
        return message