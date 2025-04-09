from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.users.models import User

class Shop(models.Model):
    shop_name = models.CharField(max_length=100)
    shop_type = models.CharField(max_length=50)
    address = models.TextField()
    # gstin = models.CharField(max_length=15, unique=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Keep track of who created/owns the shop
    # This is mainly for reference, as multiple users with admin role can manage the shop
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='created_shops',
        null=True
    )

    def __str__(self):
        return self.shop_name

    @property
    def owner(self):
        """For backward compatibility - returns the first admin user"""
        admin = self.users.filter(role=User.ROLE_ADMIN).first()
        return admin

# Now User belongs to one shop but shop can have multiple users
class ShopUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='shop_user')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='users')
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Shop User')
        verbose_name_plural = _('Shop Users')
        
    def __str__(self):
        return f"{self.user.username} - {self.shop.shop_name}"