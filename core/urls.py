"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# from django.contrib import admin
# from django.urls import path

# urlpatterns = [
#     path('admin/', admin.site.urls),
# ]

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from core.views import index
from apps.users.views import (
    UserRegistrationView,
    UserLoginView,
    VerifyUserView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    SendDummyMessageView
)
from apps.inventory.views import CategoryDetailView, CategoryListCreateView, LowStockAlertsView, ProductDetailView, ProductListCreateView, PurchaseOrderDetailView, PurchaseOrderListCreateView, ReceivePurchaseOrderView, StockAdjustmentView, StockMovementListView, SupplierDetailView, SupplierListCreateView


# Schema view configuration for Swagger
schema_view = get_schema_view(
    openapi.Info(
        title="Shop Management API",
        default_version='v1',
        description="API documentation",
        terms_of_service="https://www.finityedge.com",
        contact=openapi.Contact(email="francis@finityedge.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),  # Allow access without authentication
    # URLs to API
)

urlpatterns = [
    path('', index, name='index'),
    path('admin/', admin.site.urls),
    # path('api/', include('shop.urls')),

    # User URLs
    path('api/register', UserRegistrationView.as_view(), name='register'),
    path('api/verify', VerifyUserView.as_view(), name='verify'),
    path('api/login', UserLoginView.as_view(), name='login'),
    path('api/password-reset', PasswordResetRequestView.as_view(), name='password-reset'),
    path('api/password-reset-confirm', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('api/send-dummy-message', SendDummyMessageView.as_view(), name='send-dummy-message'),

    # Inventory URLs
    path('api/inventory/categories', CategoryListCreateView.as_view(), name='category-list-create'),
    path('api/inventory/categories/<int:pk>', CategoryDetailView.as_view(), name='category-detail'),

    # Units URLs


    # Inventory URLs - Products
    path('api/inventory/products', ProductListCreateView.as_view(), name='product-list-create'),
    path('api/inventory/products/<int:pk>', ProductDetailView.as_view(), name='product-detail'),
    # path('api/inventory/products/bulk-upload', BulkProductUploadView.as_view(), name='product-bulk-upload'),
    
    # Inventory URLs - Stock Management
    path('api/inventory/stock/adjust', StockAdjustmentView.as_view(), name='stock-adjust'),
    path('api/inventory/stock/movements', StockMovementListView.as_view(), name='stock-movements'),
    path('api/inventory/stock/low-alerts', LowStockAlertsView.as_view(), name='low-stock-alerts'),

    # Inventory URLs - Suppliers
    path('api/inventory/suppliers', SupplierListCreateView.as_view(), name='supplier-list-create'),
    path('api/inventory/suppliers/<int:pk>', SupplierDetailView.as_view(), name='supplier-detail'),

    # Inventory URLs - Purchase Orders
    path('api/inventory/purchase-orders', PurchaseOrderListCreateView.as_view(), name='purchase-order-list-create'),
    path('api/inventory/purchase-orders/<int:pk>', PurchaseOrderDetailView.as_view(), name='purchase-order-detail'),
    path('api/inventory/purchase-orders/<int:pk>/status', PurchaseOrderDetailView.as_view(), name='purchase-order-status-update'),
    path('api/inventory/purchase-orders/receive', ReceivePurchaseOrderView.as_view(), name='receive-purchase-order'),

    # Swagger URLs (accessible in any environment)
    path('swagger.<str:format>', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    re_path(r'^static/(?P<path>.*)$', serve, {
        'document_root': settings.STATIC_ROOT,
    }),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)