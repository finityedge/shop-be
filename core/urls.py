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
from apps.common.views import DashboardViewSet
from apps.expense.views import ExpenseCategoryDetailView, ExpenseCategoryListCreateView, ExpenseDetailView, ExpenseListCreateView, ExpensePaymentCreateView, ExpenseStatusUpdateView, PaymentMethodDetailView, PaymentMethodListCreateView, RecurringExpenseLogListView
from apps.sale.views import CustomerDetailView, CustomerListCreateView, CustomerSalesHistoryView, PaymentDetailView, PaymentListCreateView, SaleDetailView, SaleListCreateView, SalePaymentsView, SaleReturnsView, SalesReturnApproveView, SalesReturnDetailView, SalesReturnListCreateView
from core.views import index
from apps.users.views import (
    UserRegistrationView,
    UserLoginView,
    VerifyUserView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    SendDummyMessageView
)
from apps.inventory.views import CategoryDetailView, CategoryListCreateView, LowStockAlertsView, ProductDetailView, ProductListCreateView, PurchaseOrderDetailView, PurchaseOrderListCreateView, PurchaseOrderStatusUpdateView, ReceivePurchaseOrderView, StockAdjustmentView, StockMovementListView, SupplierDetailView, SupplierListCreateView, UnitListView


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
    path('api/categories', CategoryListCreateView.as_view(), name='category-list-create'),
    path('api/categories/<int:pk>', CategoryDetailView.as_view(), name='category-detail'),

    # Units URLs
    path('api/units', UnitListView.as_view(), name='unit-list-create'),


    # Inventory URLs - Products
    path('api/products', ProductListCreateView.as_view(), name='product-list-create'),
    path('api/products/<int:pk>', ProductDetailView.as_view(), name='product-detail'),
    # path('api/inventory/products/bulk-upload', BulkProductUploadView.as_view(), name='product-bulk-upload'),
    
    # Inventory URLs - Stock Management
    path('api/inventory/stock/adjust', StockAdjustmentView.as_view(), name='stock-adjust'),
    path('api/inventory/stock/movements', StockMovementListView.as_view(), name='stock-movements'),
    path('api/inventory/stock/low-alerts', LowStockAlertsView.as_view(), name='low-stock-alerts'),

    # Inventory URLs - Suppliers
    path('api/suppliers', SupplierListCreateView.as_view(), name='supplier-list-create'),
    path('api/suppliers/<int:pk>', SupplierDetailView.as_view(), name='supplier-detail'),

    # Inventory URLs - Purchase Orders
    path('api/purchase-orders', PurchaseOrderListCreateView.as_view(), name='purchase-order-list-create'),
    path('api/purchase-orders/<int:pk>', PurchaseOrderDetailView.as_view(), name='purchase-order-detail'),
    path('api/purchase-orders/<int:pk>/status', PurchaseOrderStatusUpdateView.as_view(), name='purchase-order-status-update'),
    path('api/purchase-orders/receive', ReceivePurchaseOrderView.as_view(), name='receive-purchase-order'),

    # Sales URLs - Customers
    path('api/customers', CustomerListCreateView.as_view(), name='customer-list-create'),
    path('api/customers/<int:pk>', CustomerDetailView.as_view(), name='customer-detail'),
    path('api/customers/<int:pk>/sales', CustomerSalesHistoryView.as_view(), name='customer-sales-history'),

    # Sales URLs - Sales
    path('api/sales', SaleListCreateView.as_view(), name='sale-list-create'),
    path('api/sales/<int:pk>', SaleDetailView.as_view(), name='sale-detail'),
    path('api/sales/<int:pk>/payments', SalePaymentsView.as_view(), name='sale-payments'),
    path('api/sales/<int:pk>/returns', SaleReturnsView.as_view(), name='sale-returns'),

    # Sales URLs - Payments
    path('api/payments', PaymentListCreateView.as_view(), name='payment-list-create'),
    path('api/payments/<int:pk>', PaymentDetailView.as_view(), name='payment-detail'),

    # Sales URLs - Returns
    path('api/sales-returns', SalesReturnListCreateView.as_view(), name='sales-return-list-create'),
    path('api/sales-returns/<int:pk>', SalesReturnDetailView.as_view(), name='sales-return-detail'),
    path('api/sales-returns/<int:pk>/approve', SalesReturnApproveView.as_view(), name='sales-return-approve'),

    # Expense URLs - Categories
    path('api/expense-categories', ExpenseCategoryListCreateView.as_view(), name='expense-category-list-create'),
    path('api/expense-categories/<int:pk>', ExpenseCategoryDetailView.as_view(), name='expense-category-detail'),

    # Expense URLs - Payment Methods
    path('api/expense/payment-methods', PaymentMethodListCreateView.as_view(), name='expense-payment-method-list-create'),
    path('api/expense/payment-methods/<int:pk>', PaymentMethodDetailView.as_view(), name='expense-payment-method-detail'),

    # Expense URLs - Expenses
    path('api/expenses', ExpenseListCreateView.as_view(), name='expense-list-create'),
    path('api/expenses/<int:pk>', ExpenseDetailView.as_view(), name='expense-detail'),
    path('api/expenses/<int:pk>/status', ExpenseStatusUpdateView.as_view(), name='expense-status-update'),

    # Expense URLs - Payments
    path('api/expense-payments', ExpensePaymentCreateView.as_view(), name='expense-payment-create'),

    # Expense URLs - Recurring Expenses
    path('api/expenses/recurring-logs', RecurringExpenseLogListView.as_view(), name='recurring-expense-logs'),

    # Analytics URLs
    path('api/dashboard/summary-metrics/', DashboardViewSet.as_view({'get': 'summary_metrics'}), name='dashboard-summary-metrics'),
    path('api/dashboard/sales-trends/', DashboardViewSet.as_view({'get': 'sales_trends'}), name='dashboard-sales-trends'),
    path('api/dashboard/top-products/', DashboardViewSet.as_view({'get': 'top_products'}), name='dashboard-top-products'),
    path('api/dashboard/inventory-status/', DashboardViewSet.as_view({'get': 'inventory_status'}), name='dashboard-inventory-status'),
    path('api/dashboard/expense-analysis/', DashboardViewSet.as_view({'get': 'expense_analysis'}), name='dashboard-expense-analysis'),
    path('api/dashboard/customer-insights/', DashboardViewSet.as_view({'get': 'customer_insights'}), name='dashboard-customer-insights'),
    path('api/dashboard/payment-analytics/', DashboardViewSet.as_view({'get': 'payment_analytics'}), name='dashboard-payment-analytics'),

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