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

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['name', 'phone']

    def __str__(self):
        return self.username
    
    def generate_verification_token(self):
        self.verification_token = secrets.token_urlsafe(32)
    
