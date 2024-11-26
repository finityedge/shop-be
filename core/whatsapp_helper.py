from twilio.rest import Client
import phonenumbers
import re

class WhatsAppHelper:
    def __init__(self, account_sid, auth_token, from_number):
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number.strip('+')  # Remove any leading + if present

    def validate_phone_number(self, phone_number):
        """
        Validate and format the phone number
        
        Args:
            phone_number (str): Phone number to validate
        
        Returns:
            str: Formatted international phone number without '+' or spaces
        
        Raises:
            ValueError: If the phone number is invalid
        """
        # Remove any non-digit characters
        cleaned_number = re.sub(r'\D', '', phone_number)
        
        try:
            # Parse the phone number
            parsed_number = phonenumbers.parse(f"+{cleaned_number}", None)
            
            # Check if the number is valid
            if not phonenumbers.is_valid_number(parsed_number):
                raise ValueError("Invalid phone number")
            
            # Format to E.164 without the '+' sign
            formatted_number = phonenumbers.format_number(
                parsed_number, 
                phonenumbers.PhoneNumberFormat.E164
            ).lstrip('+')
            
            return formatted_number
        
        except Exception as e:
            raise ValueError(f"Phone number validation error: {str(e)}")

    def send_whatsapp_message(self, to_number, message):
        """
        Send a WhatsApp message with validated phone number
        
        Args:
            to_number (str): Recipient's phone number
            message (str): Message to send
        
        Returns:
            Twilio message object
        
        Raises:
            ValueError: If phone number is invalid
            TwilioRestException: If Twilio message sending fails
        """
        try:
            # Validate and format the phone number
            validated_to_number = self.validate_phone_number(to_number)

            print(f"Sending message to: {validated_to_number}")
            
            # Send the message
            message = self.client.messages.create(
                body=message,
                from_='whatsapp:' + self.from_number,
                to='whatsapp:' + validated_to_number
            )
            
            return message
        
        except ValueError as ve:
            # Log the validation error
            print(f"Phone number validation error: {ve}")
            raise
        except Exception as e:
            # Log any other errors
            print(f"Error sending WhatsApp message: {e}")
            raise