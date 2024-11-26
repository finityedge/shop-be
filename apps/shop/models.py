from django.db import models
from django.conf import settings

class Shop(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='shop'
    )
    shop_name = models.CharField(max_length=100)
    shop_type = models.CharField(max_length=50)
    address = models.TextField()
    # gstin = models.CharField(max_length=15, unique=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.shop_name