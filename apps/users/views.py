from rest_framework import generics, status, views, serializers
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from apps.users.serializers import UserRegistrationSerializer, UserLoginSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator
from .models import User
from drf_yasg import openapi
from .serializers import UserRegistrationSerializer
from drf_yasg.utils import swagger_auto_schema

from core.whatsapp_helper import WhatsAppHelper
from core import settings

# Assuming you have the necessary Twilio credentials
TWILIO_ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
TWILIO_WHATSAPP_FROM_NUMBER = settings.TWILIO_PHONE_NUMBER
VERIFICATION_URL = 'http://localhost:3000/api/verify/{0}'
    
class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            user.generate_verification_token()
            user.save()

            # Send WhatsApp verification message
            whatsapp_helper = WhatsAppHelper(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM_NUMBER)
            verification_url = VERIFICATION_URL.format(user.verification_token)
            message = f"Welcome to our app! Please click the link to verify your account: {verification_url}"
            # whatsapp_helper.send_whatsapp_message(f"whatsapp:{user.phone}", message)

            return Response({
                'message': 'User and Shop registered successfully',
                'user': serializer.to_representation(user)
            }, status=status.HTTP_201_CREATED)

        except serializers.ValidationError as e:
            # Handle validation errors with more detail
            return Response({
                'error': 'Registration failed',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        
class VerifyUserView(views.APIView):
    @swagger_auto_schema(
        operation_summary='Verify user',
        manual_parameters=[openapi.Parameter('token', openapi.IN_QUERY, description='Verification token', type=openapi.TYPE_STRING)],
        operation_description='Verify user with the provided token.',
        responses={
            200: 'User verified successfully.',
            400: 'Invalid verification token.'
        }
    )
    def get(self, request):
        token = request.GET.get('token')
        try:
            user = User.objects.get(verification_token=token)
            user.is_verified = True
            user.save()
            return Response({'message': 'User verified successfully.'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'Invalid verification token.'}, status=status.HTTP_400_BAD_REQUEST)

class UserLoginView(views.APIView):
    @swagger_auto_schema(
        operation_description="Login with phone and password",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phone', 'password'],
            properties={
                'phone': openapi.Schema(type=openapi.TYPE_STRING, description='User phone number'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='User password')
            }
        ),
        responses={
            200: openapi.Response(
                description='Successful Login',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'phone': openapi.Schema(type=openapi.TYPE_STRING),
                        'username': openapi.Schema(type=openapi.TYPE_STRING),
                        'access_token': openapi.Schema(type=openapi.TYPE_STRING),
                        'refresh_token': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: 'Bad Request - Invalid Credentials'
        }
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            login_data = serializer.save()
            
            return Response(login_data, status=status.HTTP_200_OK)
        
        except serializers.ValidationError as e:
            return Response(
                {'error': str(e.detail)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class PasswordResetRequestView(views.APIView):
    @swagger_auto_schema(
        operation_description='Request password reset',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phone'],
            properties={
                'phone': openapi.Schema(type=openapi.TYPE_STRING, description='User phone number')
            }
        ),
        responses={
            200: openapi.Response(
                description='Password reset link sent successfully',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: 'Bad Request - Invalid phone number'
        }
    )

    def post(self, request):
        """
        Handle password reset request via phone number
        
        Validates the phone number, generates OTP, 
        and sends reset instructions via WhatsApp
        """
        serializer = PasswordResetRequestSerializer(data=request.data)
        
        try:
            # Validate the serializer 
            serializer.is_valid(raise_exception=True)
            
            # Create the reset request (which sends OTP)
            user = serializer.save()
            
            # Optional: Send WhatsApp message with OTP
            whatsapp_helper = WhatsAppHelper(
                TWILIO_ACCOUNT_SID, 
                TWILIO_AUTH_TOKEN, 
                TWILIO_WHATSAPP_FROM_NUMBER
            )
            message = f"Your password reset OTP is: {user.otp}. This OTP will expire in 5 minutes."
            # whatsapp_helper.send_whatsapp_message(f"whatsapp:{user.phone}", message)
            
            return Response(
                serializer.to_representation(user),
                status=status.HTTP_200_OK
            )
        
        except serializers.ValidationError as e:
            # Handle validation errors (e.g., user not found, not verified)
            return Response(
                {'error': str(e.detail)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            # Handle any unexpected errors
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PasswordResetConfirmView(views.APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description='Confirm password reset with OTP',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phone', 'otp', 'new_password', 'confirm_password'],
            properties={
                'phone': openapi.Schema(type=openapi.TYPE_STRING, description='User phone number'),
                'otp': openapi.Schema(type=openapi.TYPE_STRING, description='6-digit OTP'),
                'new_password': openapi.Schema(type=openapi.TYPE_STRING, description='New password'),
                'confirm_password': openapi.Schema(type=openapi.TYPE_STRING, description='Confirm new password')
            }
        ),
        responses={
            200: openapi.Response(
                description='Password reset successful',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: 'Bad Request - Invalid reset details'
        }
    )
    def post(self, request):
        """
        Handle password reset confirmation using OTP
        
        Validates:
        - Matching passwords
        - Valid OTP
        - OTP not expired
        """
        serializer = PasswordResetConfirmSerializer(data=request.data)
        
        try:
            # Validate the serializer 
            serializer.is_valid(raise_exception=True)
            
            # Save the new password
            user = serializer.save()
            
            # Optional: Invalidate all existing tokens for the user
            # RefreshToken.for_user(user).blacklist()
            
            return Response(
                {'message': 'Password has been reset successfully.'},
                status=status.HTTP_200_OK
            )
        
        except serializers.ValidationError as e:
            # Handle validation errors 
            return Response(
                {'error': e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            # Handle any unexpected errors
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
