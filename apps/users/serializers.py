from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.conf import settings
from apps.shop.models import Shop
from rest_framework_simplejwt.tokens import RefreshToken

from twilio.rest import Client
import random

from core import settings

User = get_user_model()

TWILIO_ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN

class UserRegistrationSerializer(serializers.ModelSerializer):
    # User Fields
    name = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    
    # Shop Fields
    shop_name = serializers.CharField(write_only=True)
    shop_type = serializers.CharField(write_only=True)
    address = serializers.CharField(write_only=True)
    # gstin = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            # User fields
            'phone', 'username', 'name', 
            'password', 'confirm_password',
            
            # Shop fields
            'shop_name', 'shop_type', 
            'address' 
            # 'gstin'
        ]

    def validate(self, data):
        # Password validation
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        
        # GSTIN validation with more robust error handling
        # gstin = data.get('gstin')
        # if gstin is not None:  # Only validate if gstin is provided
        #     if not isinstance(gstin, str):
        #         raise serializers.ValidationError({"gstin": "GSTIN must be a string."})
            
        #     if not self.validate_gstin(gstin):
        #         raise serializers.ValidationError({"gstin": "Invalid GSTIN number."})
        
        return data
    
    def validate_phone(self, value):
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        try:
            client.lookups.phone_numbers(value).fetch()
        except Exception as e:
            raise serializers.ValidationError(f"Invalid phone number: {e}")
        return value

    def validate_gstin(self, gstin):
        # More comprehensive GSTIN validation
        if not gstin:
            return False
        
        try:
            # Check length
            if len(gstin) != 15:
                return False
            
            # Check alphanumeric
            if not gstin.isalnum():
                return False
            
            # Optional: More specific GSTIN validation logic
            # For example, check state code, PAN, entity type, etc.
            # This is a placeholder - you'd want to implement more specific checks
            return True
        
        except Exception as e:
            # Log the error if needed
            print(f"GSTIN Validation Error: {e}")
            return False

    def create(self, validated_data):
        # Remove shop-related and confirm_password fields
        shop_name = validated_data.pop('shop_name', None)
        shop_type = validated_data.pop('shop_type', None)
        address = validated_data.pop('address', None)
        # gstin = validated_data.pop('gstin', None)
        validated_data.pop('confirm_password', None)

        # Create user
        user = User.objects.create_user(**validated_data)

        # Create associated shop only if shop details are provided
        if all([shop_name, shop_type, address]):
            try:
                Shop.objects.create(
                    owner=user,
                    shop_name=shop_name,
                    shop_type=shop_type,
                    address=address
                    # gstin=None  # This can be None
                )
            except Exception as e:
                # If shop creation fails, delete the user
                user.delete()
                raise serializers.ValidationError({"shop_creation": str(e)})

        return user
    
    def to_representation(self, instance):
        # Customize the response to return relevant information
        rep = super().to_representation(instance)
        
        # Remove sensitive information from response
        rep.pop('password', None)
        rep.pop('confirm_password', None)
        
        # Add shop details to response
        try:
            shop = instance.shop
            rep['shop'] = {
                'shop_name': shop.shop_name,
                'shop_type': shop.shop_type,
                'address': shop.address,
                'is_verified': shop.is_verified
            }
            rep['token'] = instance.verification_token
        except Shop.DoesNotExist:
            rep['shop'] = None
        
        return rep

class UserLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True, 
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, data):
        phone = data.get('phone')
        password = data.get('password')

        if not phone or not password:
            raise serializers.ValidationError("Both phone and password are required.")

        # Debugging: Print out details for troubleshooting
        print(f"Attempting to authenticate - Phone: {phone}")

        # Use the custom authentication
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(phone=phone)
            print(f"User found: {user}")
            
            # Directly check password
            if not user.check_password(password):
                print("Password check failed")
                raise serializers.ValidationError("Invalid login credentials.")
            
            if not user.is_verified:
                raise serializers.ValidationError("User account is not verified.")
            
            if not user.is_active:
                raise serializers.ValidationError("User account is not active.")
            
            # Add user to validated data for use in create method
            data['user'] = user
            return data
        
        except UserModel.DoesNotExist:
            print("User not found")
            raise serializers.ValidationError("Invalid login credentials.")

    def create(self, validated_data):
        user = validated_data['user']
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return {
            'user_id': user.id,
            'phone': user.phone,
            'username': user.username,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh)
        }

    def to_representation(self, instance):
        return instance

class PasswordResetRequestSerializer(serializers.Serializer):
    phone = serializers.CharField()

    def validate_phone(self, value):
        try:
            user = User.objects.get(phone=value)

            # check if user is verified
            if not user.is_verified:
                raise serializers.ValidationError("User is not verified.")
            
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this phone number does not exist.")
        return value
    
    def send_reset_link(self, user):
        try:
            # Generate reset OTP
            user.otp = random.randint(100000, 999999)
            user.otp_expiry = timezone.now() + timedelta(minutes=5)
            user.save()
        except Exception as e:
            raise serializers.ValidationError(f"An unexpected error occurred: {e}")

        # Send OTP via whatsapp


    def create(self, validated_data):
        user = User.objects.get(phone=validated_data['phone'])
        self.send_reset_link(user)
        return user
    
    def to_representation(self, instance):
        return {
            'message': 'Password reset link has been sent.',
            'otp': instance.otp,
            'otp_expiry': instance.otp_expiry
        }

class PasswordResetConfirmSerializer(serializers.Serializer):
    phone = serializers.CharField()
    otp = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, data):
        # Check if passwords match
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        
        return data

    def validate_otp(self, otp):
        # Find user by phone number
        try:
            user = User.objects.get(phone=self.initial_data['phone'])
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this phone number does not exist.")
        
        # Check if OTP matches
        if str(user.otp) != str(otp):
            raise serializers.ValidationError("Invalid OTP.")
        
        # Check OTP expiry
        if user.otp_expiry < timezone.now():
            raise serializers.ValidationError("OTP has expired.")
        
        return otp

    def save(self):
        # Retrieve user
        user = User.objects.get(phone=self.validated_data['phone'])
        
        # Set new password
        user.set_password(self.validated_data['new_password'])
        
        # Clear OTP after successful reset
        user.otp = None
        user.otp_expiry = None
        
        user.save()
        
        return user