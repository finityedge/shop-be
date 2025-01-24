from rest_framework import generics, status, filters, views
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view
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
            shop=self.request.user.shop,
            created_by=self.request.user,
            modified_by=self.request.user
        )

    def perform_update(self, serializer):
        serializer.save(modified_by=self.request.user)

    def get_queryset(self):
        # Filter queryset by shop if the model has a shop field
        model = self.queryset.model
        if hasattr(model, 'shop'):
            return self.queryset.filter(shop=self.request.user.shop)
        return self.queryset

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
            serializer = self.get_serializer(data=request.data)
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

class SaleListCreateView(BaseAPIView, generics.ListCreateAPIView):
    """API endpoint for listing and creating sales."""
    filterset_fields = ['payment_status', 'payment_method', 'sale_date']
    search_fields = ['invoice_number', 'customer__name']
    ordering_fields = ['sale_date', 'total', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return Sale.objects.filter(shop=self.request.user.shop)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SaleCreateSerializer
        return SaleListSerializer
    
    def generate_invoice_number(self, shop):
        """
        Generates a unique invoice number in the format: SHOP-YYYY-MM-XXXXX
        Where XXXXX is a sequential number padded with zeros
        """
        today = datetime.datetime.now()
        year = today.strftime('%Y')
        month = today.strftime('%m')
        
        # Get the prefix for the current shop
        shop_prefix = shop.code if hasattr(shop, 'code') else 'INV'
        
        # Find the last invoice number for this shop, year and month
        prefix = f"{shop_prefix}-{year}-{month}-"
        last_invoice = Sale.objects.filter(
            shop=shop,
            invoice_number__startswith=prefix
        ).aggregate(Max('invoice_number'))['invoice_number__max']
        
        if last_invoice:
            # Extract the sequence number and increment it
            sequence = int(last_invoice.split('-')[-1]) + 1
        else:
            # Start with 1 if no previous invoice exists
            sequence = 1
            
        # Generate new invoice number with 5-digit sequence
        invoice_number = f"{prefix}{str(sequence).zfill(5)}-{shop.id}"
        return invoice_number


    @swagger_auto_schema(
        operation_description='Create a new sale with items',
        request_body=SaleCreateSerializer,
        responses={201: SaleDetailSerializer}
    )
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            serializer.validated_data['shop'] = request.user.shop
            serializer.validated_data['invoice_number'] = self.generate_invoice_number(request.user.shop)

            sale = serializer.save(
                created_by=request.user,
                modified_by=request.user
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
        return SalesReturn.objects.filter(sale=sale, shop=self.request.user.shop)

class PaymentListCreateView(BaseAPIView, generics.ListCreateAPIView):
    """API endpoint for listing and creating payments."""
    filterset_fields = ['payment_method', 'payment_date']
    search_fields = ['sale__invoice_number', 'reference_number']
    ordering_fields = ['payment_date', 'amount']
    ordering = ['-payment_date']

    def get_queryset(self):
        return Payment.objects.filter(shop=self.request.user.shop)

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
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            serializer.validated_data['shop'] = request.user.shop

            payment = serializer.save(
                created_by=request.user,
                modified_by=request.user
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
        return Payment.objects.filter(shop=self.request.user.shop)

class SalesReturnListCreateView(BaseAPIView, generics.ListCreateAPIView):
    """API endpoint for listing and creating sales returns."""
    filterset_fields = ['status', 'return_date']
    search_fields = ['sale__invoice_number']
    ordering_fields = ['return_date', 'total']
    ordering = ['-created_at']

    def get_queryset(self):
        return SalesReturn.objects.filter(shop=self.request.user.shop)

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
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            serializer.validated_data['shop'] = request.user.shop
            
            sales_return = serializer.save(
                created_by=request.user,
                modified_by=request.user
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
        return SalesReturn.objects.filter(shop=self.request.user.shop)

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
        
