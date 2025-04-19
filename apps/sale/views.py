from collections import OrderedDict
from decimal import Decimal
from rest_framework import generics, status, filters, views
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
# from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from django.db.models import Max
import datetime

from .models import (
    Customer, Sale, SaleItem, Payment, 
    SalesReturn, SalesReturnItem
)
from .serializers import (
    CustomerListSerializer, CustomerDetailSerializer, CustomerCreateUpdateSerializer,
    SaleListSerializer, SaleDetailSerializer, SaleCreateSerializer, SaleUpdateSerializer,
    SaleItemDetailSerializer, SaleItemCreateSerializer,
    PaymentListSerializer, PaymentDetailSerializer, PaymentCreateSerializer,
    SalesReturnListSerializer, SalesReturnDetailSerializer, SalesReturnCreateSerializer,
    SalesReturnItemDetailSerializer
)

class BaseAPIView:
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    def perform_create(self, serializer):
        serializer.save(
            shop=self.request.user.shop_user.shop,
            created_by=self.request.user,
            modified_by=self.request.user
        )

    def perform_update(self, serializer):
        serializer.save(modified_by=self.request.user)

    def get_queryset(self):
        # Filter queryset by shop if the model has a shop field
        model = self.queryset.model
        if hasattr(model, 'shop'):
            return self.queryset.filter(shop=self.request.user.shop_user.shop)
        return self.queryset
    
class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        # Convert string values to Decimal before summing
        try:
            total_amount = sum(Decimal(str(item['total'])) for item in data)
            total_paid = sum(Decimal(str(item.get('paid_amount', 0))) for item in data)
            total_balance = sum(Decimal(str(item.get('balance_due', 0))) for item in data)
        except (KeyError, ValueError, TypeError):
            # Fallback if there's any conversion error
            total_amount = Decimal('0.00')
            total_paid = Decimal('0.00')
            total_balance = Decimal('0.00')
            
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('current_page', self.page.number),
            ('total_pages', self.page.paginator.num_pages),
            ('page_size', self.get_page_size(self.request)),
            ('results', data),
            ('metadata', {
                'total_sales': self.page.paginator.count,
                'total_amount': str(total_amount),  # Convert back to string for JSON serialization
                'total_paid': str(total_paid),
                'total_balance': str(total_balance),
                'payment_status_summary': self._get_payment_status_summary(data)
            })
        ]))
    
    def _get_payment_status_summary(self, data):
        """Calculate summary statistics by payment status"""
        summary = {}
        for status in ['PENDING', 'PARTIAL', 'PAID', 'OVERDUE']:
            status_items = [item for item in data if item.get('payment_status') == status]
            if status_items:
                try:
                    total = sum(Decimal(str(item['total'])) for item in status_items)
                except (KeyError, ValueError, TypeError):
                    total = Decimal('0.00')
                    
                summary[status.lower()] = {
                    'count': len(status_items),
                    'total': str(total)
                }
        return summary

class CustomerListCreateView(BaseAPIView, generics.ListCreateAPIView):
    """API endpoint for listing and creating customers."""
    queryset = Customer.objects.all()
    search_fields = ['name', 'email', 'phone']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CustomerCreateUpdateSerializer
        return CustomerListSerializer

    @swagger_auto_schema(
        operation_description='Create a new customer',
        request_body=CustomerCreateUpdateSerializer,
        responses={201: CustomerDetailSerializer}
    )
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=self.request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(
                CustomerDetailSerializer(serializer.instance).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class CustomerDetailView(BaseAPIView, generics.RetrieveUpdateDestroyAPIView):
    """API endpoint for retrieving, updating and deleting a customer."""
    queryset = Customer.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return CustomerCreateUpdateSerializer
        return CustomerDetailSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.sales.exists():
                instance.is_active = False
                instance.save()
                return Response(
                    {"detail": "Customer has associated sales. Marked as inactive instead of deleting."},
                    status=status.HTTP_200_OK
                )
            return super().destroy(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class CustomerSalesHistoryView(BaseAPIView, generics.ListAPIView):
    """API endpoint for retrieving customer sales history."""
    serializer_class = SaleListSerializer

    def get_queryset(self):
        customer = get_object_or_404(Customer, pk=self.kwargs['pk'])
        return Sale.objects.filter(customer=customer)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class SaleListCreateView(BaseAPIView, generics.ListCreateAPIView):
    """API endpoint for listing and creating sales."""
    pagination_class = CustomPagination
    # Add DjangoFilterBackend to the filter_backends
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # Add created_by and other relevant filters
    filterset_fields = ['payment_status', 'payment_method', 'sale_date', 'created_by', 'customer']
    search_fields = ['invoice_number', 'customer__name', 'created_by__username', 'notes']
    ordering_fields = ['sale_date', 'total', 'created_at', 'paid_amount', 'due_date']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Sale.objects.filter(shop=self.request.user.shop_user.shop)
        
        # Additional date range filtering
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(sale_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(sale_date__lte=end_date)
            
        # Payment status filtering
        status = self.request.query_params.get('payment_status', None)
        if status:
            queryset = queryset.filter(payment_status=status)
            
        # Amount range filtering
        min_amount = self.request.query_params.get('min_amount', None)
        max_amount = self.request.query_params.get('max_amount', None)
        
        if min_amount:
            queryset = queryset.filter(total__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(total__lte=max_amount)
            
        return queryset

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SaleCreateSerializer
        return SaleListSerializer
    
    def generate_invoice_number(self, shop):
        """
        Generates a unique invoice number with randomness to reduce collision probability
        Format: SHOP-YYYY-MM-XXXXX-RANDOM
        """
        import random
        import string
        import uuid
        import time
        
        today = datetime.datetime.now()
        year = today.strftime('%Y')
        month = today.strftime('%m')
        day = today.strftime('%d')
        
        # Get the prefix for the current shop
        shop_prefix = shop.code if hasattr(shop, 'code') else 'INV'
        
        # Generate a timestamp component (milliseconds)
        timestamp = int(time.time() * 1000) % 10000
        
        # Generate a random alphanumeric string (4 characters)
        random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        
        # Generate a random number between 1000-9999
        random_num = random.randint(1000, 9999)
        
        # Take the first 4 characters of a UUID (without hyphens)
        uuid_segment = str(uuid.uuid4()).replace('-', '')[:4]
        
        # Find the last invoice number for this shop and date to maintain some sequentiality
        prefix = f"{shop_prefix}-{year}-{month}"
        last_invoice = Sale.objects.filter(
            shop=shop,
            invoice_number__startswith=prefix
        ).aggregate(Max('invoice_number'))['invoice_number__max']
        
        if last_invoice:
            try:
                # Try to extract the sequence number and increment it
                parts = last_invoice.split('-')
                if len(parts) >= 4:
                    sequence = int(parts[3]) + 1
                else:
                    sequence = 1
            except (ValueError, IndexError):
                sequence = 1
        else:
            # Start with 1 if no previous invoice exists
            sequence = 1
        
        # Generate final invoice number
        invoice_number = f"{shop_prefix}-{year}{month}{day}-{sequence:05d}-{random_chars}{timestamp}"
        
        return invoice_number


    @swagger_auto_schema(
        operation_description='Create a new sale with items',
        request_body=SaleCreateSerializer,
        responses={201: SaleDetailSerializer}
    )
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=self.request.data)
            serializer.is_valid(raise_exception=True)

            serializer.validated_data['shop'] = request.user.shop_user.shop
            serializer.validated_data['invoice_number'] = self.generate_invoice_number(request.user.shop_user.shop)

            sale = serializer.save(
                created_by=self.request.user,
                modified_by=self.request.user
            )
            
            # Update stock levels
            for item in sale.items.all():
                stock = item.product.stock
                stock.quantity -= item.quantity
                if stock.quantity < 0:
                    raise ValidationError(f"Insufficient stock for {item.product.name}")
                stock.save()
            
            return Response(
                SaleDetailSerializer(sale).data,
                status=status.HTTP_201_CREATED
            )
        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"detail": "An error occurred while processing the sale."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SaleDetailView(BaseAPIView, generics.RetrieveUpdateAPIView):
    """API endpoint for retrieving and updating sales."""
    queryset = Sale.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return SaleUpdateSerializer
        return SaleDetailSerializer

class SalePaymentsView(BaseAPIView, generics.ListAPIView):
    """API endpoint for listing sale payments."""
    serializer_class = PaymentListSerializer

    def get_queryset(self):
        sale = get_object_or_404(Sale, pk=self.kwargs['pk'])
        return Payment.objects.filter(sale=sale)

class SaleReturnsView(BaseAPIView, generics.ListAPIView):
    """API endpoint for listing sale returns."""
    serializer_class = SalesReturnListSerializer

    def get_queryset(self):
        sale = get_object_or_404(Sale, pk=self.kwargs['pk'])
        return SalesReturn.objects.filter(sale=sale, shop=self.request.user.shop_user.shop)

class PaymentListCreateView(BaseAPIView, generics.ListCreateAPIView):
    """API endpoint for listing and creating payments."""
    filterset_fields = ['payment_method', 'payment_date']
    search_fields = ['sale__invoice_number', 'reference_number']
    ordering_fields = ['payment_date', 'amount']
    ordering = ['-payment_date']

    def get_queryset(self):
        return Payment.objects.filter(shop=self.request.user.shop_user.shop)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PaymentCreateSerializer
        return PaymentListSerializer

    @swagger_auto_schema(
        operation_description='Create a new payment',
        request_body=PaymentCreateSerializer,
        responses={201: PaymentDetailSerializer}
    )
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=self.request.data)
            serializer.is_valid(raise_exception=True)

            serializer.validated_data['shop'] = request.user.shop_user.shop

            payment = serializer.save(
                created_by=self.request.user,
                modified_by=self.request.user
            )
            
            # Update sale's paid amount and status
            sale = payment.sale
            sale.paid_amount += payment.amount
            
            if sale.paid_amount >= sale.total:
                sale.payment_status = 'PAID'
            elif sale.paid_amount > 0:
                sale.payment_status = 'PARTIAL'
            
            sale.save()
            
            return Response(
                PaymentDetailSerializer(payment).data,
                status=status.HTTP_201_CREATED
            )
        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"detail": "An error occurred while processing the payment."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PaymentDetailView(BaseAPIView, generics.RetrieveAPIView):
    """API endpoint for retrieving payment details."""
    serializer_class = PaymentDetailSerializer

    def get_queryset(self):
        return Payment.objects.filter(shop=self.request.user.shop_user.shop)

class SalesReturnListCreateView(BaseAPIView, generics.ListCreateAPIView):
    """API endpoint for listing and creating sales returns."""
    filterset_fields = ['status', 'return_date']
    search_fields = ['sale__invoice_number']
    ordering_fields = ['return_date', 'total']
    ordering = ['-created_at']

    def get_queryset(self):
        return SalesReturn.objects.filter(shop=self.request.user.shop_user.shop)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SalesReturnCreateSerializer
        return SalesReturnListSerializer

    @swagger_auto_schema(
        operation_description='Create a new sales return',
        request_body=SalesReturnCreateSerializer,
        responses={201: SalesReturnDetailSerializer}
    )
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=self.request.data)
            serializer.is_valid(raise_exception=True)

            serializer.validated_data['shop'] = request.user.shop_user.shop
            
            sales_return = serializer.save(
                created_by=self.request.user,
                modified_by=self.request.user
            )
            
            # Update stock levels for returned items
            for item in sales_return.items.all():
                stock = item.sale_item.product.stock
                stock.quantity += item.quantity
                stock.save()
            
            return Response(
                SalesReturnDetailSerializer(sales_return).data,
                status=status.HTTP_201_CREATED
            )
        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"detail": "An error occurred while processing the return."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SalesReturnDetailView(BaseAPIView, generics.RetrieveAPIView):
    """API endpoint for retrieving sales return details."""
    serializer_class = SalesReturnDetailSerializer

    def get_queryset(self):
        return SalesReturn.objects.filter(shop=self.request.user.shop_user.shop)

class SalesReturnApproveView(BaseAPIView, views.APIView):
    """API endpoint for approving sales returns."""
    
    @swagger_auto_schema(
        operation_description='Approve a sales return',
        responses={200: openapi.Response(description="Return approved successfully")}
    )
    def post(self, request, pk):
        try:
            sales_return = get_object_or_404(SalesReturn, pk=pk)
            if sales_return.status != 'PENDING':
                return Response(
                    {"detail": "Only pending returns can be approved."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            sales_return.status = 'APPROVED'
            sales_return.save()
            
            return Response({"status": "Return approved successfully"})
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class SaleDeleteView(BaseAPIView, generics.DestroyAPIView):
    """API endpoint for deleting sales."""
    queryset = Sale.objects.all()
    
    @swagger_auto_schema(
        operation_description='Delete a sale and all related records',
        responses={
            204: openapi.Response(description="Sale deleted successfully"),
            400: openapi.Response(description="Bad request"),
            403: openapi.Response(description="Not authorized to delete this sale"),
        }
    )
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        try:
            sale = self.get_object()
            
            # Check if user has permission to delete this sale
            if sale.shop != request.user.shop_user.shop:
                return Response(
                    {"detail": "You do not have permission to delete this sale."},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get related records before deletion to update inventory
            sale_items = list(sale.items.all())
            
            # Delete related objects in the correct order
            # 1. Delete sales returns and return items first
            for sales_return in sale.returns.all():
                sales_return.items.all().delete()
                sales_return.delete()
            
            # 2. Delete payments
            sale.payments.all().delete()
            
            # 3. Delete sale items
            sale.items.all().delete()
            
            # 4. Delete the sale itself
            sale.delete()
            
            # 5. Update inventory - restore quantities back to stock
            for item in sale_items:
                stock = item.product.stock
                stock.quantity += item.quantity
                stock.save()
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
