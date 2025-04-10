from rest_framework import generics, status, views, serializers
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.users.serializers import (
    UserRegistrationSerializer, 
    UserLoginSerializer, 
    PasswordResetRequestSerializer, 
    PasswordResetConfirmSerializer
)
from core.whatsapp_helper import WhatsAppHelper
from core import settings

User = get_user_model()

class UserRegistrationView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    
    This view handles:
    - User and shop creation
    - Generating verification token
    - Sending verification message
    """
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description='Register a new user with shop details',
        tags=['Users'],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=[
                'phone', 'username', 'name', 
                'password', 'confirm_password', 
                'shop_name', 'shop_type', 'address'
            ],
            properties={
                'phone': openapi.Schema(type=openapi.TYPE_STRING, description='User phone number'),
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Unique username'),
                'name': openapi.Schema(type=openapi.TYPE_STRING, description='Full name'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='User password'),
                'confirm_password': openapi.Schema(type=openapi.TYPE_STRING, description='Password confirmation'),
                'shop_name': openapi.Schema(type=openapi.TYPE_STRING, description='Name of the shop'),
                'shop_type': openapi.Schema(type=openapi.TYPE_STRING, description='Type of the shop'),
                'address': openapi.Schema(type=openapi.TYPE_STRING, description='Shop address')
            }
        ),
        responses={
            201: 'User and Shop registered successfully',
            400: 'Registration failed due to validation errors'
        }
    )
    def create(self, request, *args, **kwargs):
        """
        Handle user registration process.
        
        - Validate user and shop details
        - Generate verification token
        - Optionally send verification message
        """
        serializer = self.get_serializer(data=self.request.data)

        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            
            # Generate verification token
            user.generate_verification_token()
            user.verification_token_created_at = timezone.now()
            user.save()

            # Send verification message (optional)
            whatsapp_helper = WhatsAppHelper(
                settings.TWILIO_ACCOUNT_SID, 
                settings.TWILIO_AUTH_TOKEN, 
                settings.TWILIO_PHONE_NUMBER
            )

            frontend_url = settings.FRONTEND_URL

            verification_url = f'{frontend_url}/#/verify?token={user.verification_token}'
            message = f"Welcome! Verify your account: {verification_url}"
            
            whatsapp_helper.send_whatsapp_message(f"whatsapp:{user.phone}", message)

            return Response({
                'message': 'User and Shop registered successfully',
                'user': serializer.to_representation(user)
            }, status=status.HTTP_201_CREATED)

        except serializers.ValidationError as e:
            return Response({
                'error': 'Registration failed',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': 'Unexpected error during registration',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class SendDummyMessageView(views.APIView):
    """
    API endpoint for sending a dummy WhatsApp message.
    
    This view is used to test the WhatsAppHelper class.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description='Send a dummy WhatsApp message',
        tags=['Users'],
        responses={200: 'Message sent successfully'}
    )
    def get(self, request):
        """
        Send a dummy WhatsApp message.
        
        - Create a WhatsAppHelper instance
        - Send a test message
        """
        whatsapp_helper = WhatsAppHelper(
            settings.TWILIO_ACCOUNT_SID, 
            settings.TWILIO_AUTH_TOKEN, 
            '+23058000613'
        )

        verification_url = f'http://localhost:3000/api/verify/6565'
        str_message = f"Welcome! Verify your account: {verification_url}"
        
        message = whatsapp_helper.send_whatsapp_message(
            'whatsapp:+23054879046', 
            str_message
        )

        print(message.sid)
        print(message.status)
        
        return Response({'message': 'Message sent successfully'}, status=status.HTTP_200_OK)

class VerifyUserView(views.APIView):
    """
    API endpoint for user account verification.
    
    Validates user's verification token and activates the account.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary='Verify user account',
        tags=['Users'],
        manual_parameters=[
            openapi.Parameter(
                'token', 
                openapi.IN_QUERY, 
                description='Verification token sent to user',
                type=openapi.TYPE_STRING
            )
        ],
        responses={
            200: 'User verified successfully',
            400: 'Invalid or expired verification token',
            500: 'Unexpected error during verification'
        }
    )
    def get(self, request):
        """
        Verify user account using token.
        
        - Check token validity
        - Mark user as verified
        - Handle token expiration
        """
        token = request.GET.get('token')
        
        if not token:
            return Response(
                {'error': 'Verification token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(verification_token=token)
            
            # Check token expiration (e.g., 24 hours)
            # token_age = timezone.now() - user.verification_token_created_at
            # if token_age.total_seconds() > 24 * 3600:
            #     return Response(
            #         {'error': 'Verification token has expired'},
            #         status=status.HTTP_400_BAD_REQUEST
            #     )

            user.is_verified = True
            # user.verification_token = None
            # user.verification_token_created_at = None
            user.save()

            return Response(
                {'message': 'User verified successfully'},
                status=status.HTTP_200_OK
            )

        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid verification token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': 'Unexpected error during verification', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UserLoginView(views.APIView):
    """
    API endpoint for user login.
    
    Handles user authentication and token generation.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description='Authenticate user and generate tokens',
        tags=['Users'],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'password'],
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Username'),
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
            400: 'Authentication failed',
            500: 'Unexpected server error'
        }
    )
    def post(self, request):
        """
        Authenticate user and generate JWT tokens.
        
        - Validate login credentials
        - Generate access and refresh tokens
        """
        serializer = UserLoginSerializer(data=self.request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            login_data = serializer.save()
            
            return Response(login_data, status=status.HTTP_200_OK)
        
        except serializers.ValidationError as e:
            return Response(
                {'error': 'Authentication failed', 'details': e.detail}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': 'Unexpected error during login', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PasswordResetRequestView(views.APIView):
    """
    API endpoint for initiating password reset.
    
    Generates and sends OTP for password reset.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description='Request password reset OTP',
        tags=['Users'],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phone'],
            properties={
                'phone': openapi.Schema(type=openapi.TYPE_STRING, description='User phone number')
            }
        ),
        responses={
            200: openapi.Response(
                description='OTP sent successfully',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'otp': openapi.Schema(type=openapi.TYPE_STRING),
                        'otp_expiry': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: 'Bad Request - Invalid phone number',
            500: 'Unexpected server error'
        }
    )
    def post(self, request):
        """
        Handle password reset request.
        
        - Validate phone number
        - Generate OTP
        - Send OTP via WhatsApp
        """
        serializer = PasswordResetRequestSerializer(data=self.request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            
            # Optional: Send WhatsApp message
            whatsapp_helper = WhatsAppHelper(
                settings.TWILIO_ACCOUNT_SID, 
                settings.TWILIO_AUTH_TOKEN, 
                settings.TWILIO_PHONE_NUMBER
            )
            message = f"Your password reset OTP is: {user.otp}. This OTP will expire in 5 minutes."
            # Uncomment to send WhatsApp message
            whatsapp_helper.send_whatsapp_message(f"whatsapp:{user.phone}", message)
            
            return Response(
                serializer.to_representation(user),
                status=status.HTTP_200_OK
            )
        
        except serializers.ValidationError as e:
            return Response(
                {'error': 'Password reset request failed', 'details': e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': 'Unexpected error during password reset request', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PasswordResetConfirmView(views.APIView):
    """
    API endpoint for confirming password reset.
    
    Validates OTP and sets new password.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description='Confirm password reset with OTP',
        tags=['Users'],
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
            200: 'Password reset successful',
            400: 'Invalid reset details',
            500: 'Unexpected server error'
        }
    )
    def post(self, request):
        """
        Handle password reset confirmation.
        
        - Validate OTP and new password
        - Reset password
        - Optional: Invalidate existing tokens
        """
        serializer = PasswordResetConfirmSerializer(data=self.request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            
            # Optional: Invalidate all existing tokens
            # RefreshToken.for_user(user).blacklist()
            
            return Response(
                {'message': 'Password reset successful'},
                status=status.HTTP_200_OK
            )
        
        except serializers.ValidationError as e:
            return Response(
                {'error': 'Password reset failed', 'details': e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': 'Unexpected error during password reset', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )