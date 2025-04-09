from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
import secrets

class User(AbstractUser):
    phone = models.CharField(max_length=15, unique=True, blank=True, null=True)
    name = models.CharField(max_length=50)
    address = models.TextField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verification_token = models.CharField(max_length=100, null=True, blank=True)
    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_expiry = models.DateTimeField(null=True, blank=True)
    
    # Add role field directly to user
    ROLE_ADMIN = 'admin'
    ROLE_SALES_REP = 'sales_rep'
    
    ROLE_CHOICES = [
        (ROLE_ADMIN, _('Admin')),
        (ROLE_SALES_REP, _('Sales Representative')),
    ]
    
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES,
        default=ROLE_ADMIN,
        help_text=_('User role within their shop')
    )

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['name', 'phone']

    def __str__(self):
        return self.username
    
    def generate_verification_token(self):
        self.verification_token = secrets.token_urlsafe(32)