from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.conf import settings
from django.db import transaction
from apps.shop.models import Shop, ShopUser
from rest_framework_simplejwt.tokens import RefreshToken
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from twilio.rest import Client
import random

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration that includes user and shop creation.
    """
    # User Fields
    name = serializers.CharField(
        write_only=True,
        required=True,
        help_text="Full name of the user"
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="User's password (will be hashed)"
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="Confirm password to ensure accuracy"
    )
    
    # Shop Fields
    shop_name = serializers.CharField(
        write_only=True,
        required=True,
        help_text="Name of the user's shop"
    )
    shop_type = serializers.CharField(
        write_only=True,
        required=True,
        help_text="Type of the shop (e.g., Retail, Wholesale)"
    )
    address = serializers.CharField(
        write_only=True,
        required=True,
        help_text="Shop's physical address"
    )

    class Meta:
        model = User
        fields = [
            'phone', 'username', 'name', 
            'password', 'confirm_password',
            'shop_name', 'shop_type', 'address'
        ]

    def validate(self, data):
        """
        Validate registration data, including password matching.
        """
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        return data
    
    def validate_phone(self, value):
        """
        Validate phone number using Twilio lookup.
        """
        client = Client(
            settings.TWILIO_ACCOUNT_SID, 
            settings.TWILIO_AUTH_TOKEN
        )
        try:
            client.lookups.phone_numbers(value).fetch()
        except Exception as e:
            raise serializers.ValidationError(f"Invalid phone number: {e}")
        return value

    @transaction.atomic
    def create(self, validated_data):
        """
        Create user and associated shop.
        """
        # Remove shop-related and confirm_password fields
        shop_name = validated_data.pop('shop_name', None)
        shop_type = validated_data.pop('shop_type', None)
        address = validated_data.pop('address', None)
        validated_data.pop('confirm_password', None)

        # Set role to admin for users who create shops
        validated_data['role'] = User.ROLE_ADMIN

        # Create user
        user = User.objects.create_user(**validated_data)

        # Create associated shop
        if all([shop_name, shop_type, address]):
            try:
                # Create shop
                shop = Shop.objects.create(
                    shop_name=shop_name,
                    shop_type=shop_type,
                    address=address,
                    created_by=user
                )
                
                # Create shop user relationship
                ShopUser.objects.create(
                    user=user,
                    shop=shop
                )
            except Exception as e:
                # Transaction will rollback automatically
                raise serializers.ValidationError({"shop_creation": str(e)})

        return user
    
    def to_representation(self, instance):
        """
        Customize the response to return relevant information.
        """
        rep = super().to_representation(instance)
        
        # Remove sensitive information
        rep.pop('password', None)
        rep.pop('confirm_password', None)
        
        # Add shop details to response
        try:
            shop = instance.shop_user.shop
            rep['shop'] = {
                'shop_name': shop.shop_name,
                'shop_type': shop.shop_type,
                'address': shop.address,
                'is_verified': shop.is_verified
            }
        except (ShopUser.DoesNotExist, AttributeError):
            rep['shop'] = None
        
        return rep

class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login process.
    """
    username = serializers.CharField(
        required=False,
        help_text="Username or phone number"
    )
    password = serializers.CharField(
        required=True, 
        write_only=True,
        style={'input_type': 'password'},
        help_text="User's password"
    )

    def validate(self, data):
        """
        Validate login credentials.
        """
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            raise serializers.ValidationError("Both phone and password are required.")

        try:
            user = User.objects.get(username=username)
            
            if not user.check_password(password):
                raise serializers.ValidationError("Invalid login credentials.")
            
            if not user.is_verified:
                raise serializers.ValidationError("User account is not verified.")
            
            if not user.is_active:
                raise serializers.ValidationError("User account is not active.")
            
            if user.is_verified and user.verification_token:
                user.verification_token = None
                user.verification_token_created_at = None
                user.save()
            
            data['user'] = user
            return data
        
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid login credentials.")

    def create(self, validated_data):
        """
        Generate authentication tokens and include user role information.
        """
        user = validated_data['user']
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Get user shop and role info
        shop_info = None
        
        try:
            shop = user.shop_user.shop
            shop_info = {
                'shop_id': shop.id,
                'shop_name': shop.shop_name,
            }
        except (ShopUser.DoesNotExist, AttributeError):
            pass
        
        return {
            'user_id': user.id,
            'phone': user.phone,
            'username': user.username,
            'role': user.get_role_display(),
            'shop': shop_info,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh)
        }
class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for initiating password reset process.
    """
    phone = serializers.CharField(
        required=True,
        help_text="Registered phone number to reset password"
    )

    def validate_phone(self, value):
        """
        Validate phone number for password reset.
        """
        try:
            user = User.objects.get(phone=value)

            if not user.is_verified:
                raise serializers.ValidationError("User is not verified.")
            
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this phone number does not exist.")
        return value
    
    def send_reset_link(self, user):
        """
        Generate and send OTP for password reset.
        """
        try:
            # Generate reset OTP
            user.otp = random.randint(100000, 999999)
            user.otp_expiry = timezone.now() + timedelta(minutes=5)
            user.save()
        except Exception as e:
            raise serializers.ValidationError(f"An unexpected error occurred: {e}")

    def create(self, validated_data):
        """
        Process password reset request.
        """
        user = User.objects.get(phone=validated_data['phone'])
        self.send_reset_link(user)
        return user
    
    def to_representation(self, instance):
        """
        Return OTP details for reset process.
        """
        return {
            'message': 'Password reset OTP has been sent.',
            'otp': instance.otp,
            'otp_expiry': instance.otp_expiry
        }

class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for confirming password reset with OTP.
    """
    phone = serializers.CharField(
        required=True,
        help_text="Registered phone number"
    )
    otp = serializers.CharField(
        required=True,
        help_text="One-Time Password received for reset"
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="New password to set"
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="Confirm new password"
    )

    def validate(self, data):
        """
        Validate password matching and OTP.
        """
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        
        return data

    def validate_otp(self, otp):
        """
        Validate OTP for password reset.
        """
        try:
            user = User.objects.get(phone=self.initial_data['phone'])
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this phone number does not exist.")
        
        if str(user.otp) != str(otp):
            raise serializers.ValidationError("Invalid OTP.")
        
        if user.otp_expiry < timezone.now():
            raise serializers.ValidationError("OTP has expired.")
        
        return otp

    def save(self):
        """
        Reset user password and clear OTP.
        """
        user = User.objects.get(phone=self.validated_data['phone'])
        
        user.set_password(self.validated_data['new_password'])
        
        # Clear OTP after successful reset
        user.otp = None
        user.otp_expiry = None
        
        user.save()
        
        return user

# Swagger Schema Definitions
user_registration_schema = {
    'phone': openapi.Schema(
        type=openapi.TYPE_STRING,
        description='User phone number'
    ),
    'username': openapi.Schema(
        type=openapi.TYPE_STRING,
        description='Unique username'
    ),
    'name': openapi.Schema(
        type=openapi.TYPE_STRING,
        description='User full name'
    ),
    'shop_name': openapi.Schema(
        type=openapi.TYPE_STRING,
        description='Name of the shop'
    ),
    'shop_type': openapi.Schema(
        type=openapi.TYPE_STRING,
        description='Type of the shop'
    ),
    'address': openapi.Schema(
        type=openapi.TYPE_STRING,
        description='Shop address'
    )
}