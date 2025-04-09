from rest_framework import generics, status, views, filters
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from .models import (
    ExpenseCategory, PaymentMethod, Expense,
    ExpensePayment, RecurringExpenseLog
)
from .serializers import (
    ExpenseCategorySerializer, PaymentMethodSerializer,
    ExpenseListSerializer, ExpenseCreateSerializer,
    ExpenseDetailSerializer, ExpenseUpdateSerializer,
    ExpensePaymentSerializer, ExpensePaymentCreateSerializer,
    RecurringExpenseLogSerializer, ExpenseStatusSerializer
)

class ExpenseCategoryListCreateView(generics.ListCreateAPIView):
    """API endpoint for listing and creating expense categories."""
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self):
        """Filter categories by shop."""
        return ExpenseCategory.objects.filter(shop=self.request.user.shop_user.shop)

    @swagger_auto_schema(
        operation_description='List all expense categories or create a new one',
        tags=['Expense Categories'],
        responses={
            201: ExpenseCategorySerializer,
            400: 'Bad Request',
            401: 'Unauthorized'
        }
    )
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            serializer.validated_data['created_by'] = request.user
            serializer.validated_data['modified_by'] = request.user
            
            category = serializer.save()
            return Response({
                'message': 'Expense category created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            return Response({
                'error': 'Invalid data provided',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': 'Failed to create expense category',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ExpenseCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """API endpoint for retrieving, updating and deleting expense categories."""
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ExpenseCategory.objects.filter(shop=self.request.user.shop_user.shop)

    def perform_update(self, serializer):
        serializer.validated_data['modified_by'] = self.request.user
        serializer.save()

class PaymentMethodListCreateView(generics.ListCreateAPIView):
    """API endpoint for listing and creating payment methods."""
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        return PaymentMethod.objects.filter(shop=self.request.user.shop_user.shop)

    def perform_create(self, serializer):
        serializer.validated_data['created_by'] = self.request.user
        serializer.validated_data['modified_by'] = self.request.user
        serializer.save()

class PaymentMethodDetailView(generics.RetrieveUpdateDestroyAPIView):
    """API endpoint for retrieving, updating and deleting payment methods."""
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PaymentMethod.objects.filter(shop=self.request.user.shop_user.shop)

    def perform_update(self, serializer):
        serializer.validated_data['modified_by'] = self.request.user
        serializer.save()

class ExpenseListCreateView(generics.ListCreateAPIView):
    """API endpoint for listing and creating expenses."""
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['expense_number', 'title', 'description', 'supplier__name']
    ordering_fields = ['expense_date', 'due_date', 'amount', 'created_at']

    def get_serializer_class(self):
        """Return different serializers for list and create actions."""
        if self.request.method == 'POST':
            return ExpenseCreateSerializer
        return ExpenseListSerializer

    def get_queryset(self):
        """Filter expenses by shop and optional query parameters."""
        queryset = Expense.objects.filter(shop=self.request.user.shop_user.shop)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(expense_date__range=[start_date, end_date])
        
        # Filter by status
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        return queryset

    @swagger_auto_schema(
        operation_description='Create a new expense',
        tags=['Expenses'],
        responses={
            201: ExpenseCreateSerializer,
            400: 'Bad Request',
            401: 'Unauthorized'
        }
    )
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                
                # Set created_by and modified_by
                serializer.validated_data['created_by'] = request.user
                serializer.validated_data['modified_by'] = request.user
                
                # Generate expense number
                last_expense = Expense.objects.filter(shop=request.user.shop).order_by('-id').first()
                expense_number = f"EXP-{(last_expense.id + 1 if last_expense else 1):06d}-{request.user.shop.id:03d}"
                serializer.validated_data['expense_number'] = expense_number
                
                expense = serializer.save()
                
                return Response({
                    'message': 'Expense created successfully',
                    'data': ExpenseDetailSerializer(expense).data
                }, status=status.HTTP_201_CREATED)
                
        except ValidationError as e:
            return Response({
                'error': 'Invalid data provided',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': 'Failed to create expense',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ExpenseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """API endpoint for retrieving, updating and deleting expenses."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ExpenseUpdateSerializer
        return ExpenseDetailSerializer

    def get_queryset(self):
        return Expense.objects.filter(shop=self.request.user.shop_user.shop)

    def perform_update(self, serializer):
        serializer.validated_data['modified_by'] = self.request.user
        serializer.save()

class ExpensePaymentCreateView(generics.CreateAPIView):
    """API endpoint for creating expense payments."""
    serializer_class = ExpensePaymentCreateSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='Create a new expense payment',
        tags=['Expense Payments'],
        responses={
            201: ExpensePaymentSerializer,
            400: 'Bad Request',
            401: 'Unauthorized'
        }
    )
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                # Verify expense belongs to user's shop
                expense_id = request.data.get('expense')
                expense = get_object_or_404(Expense, id=expense_id, shop=request.user.shop)
                
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                
                serializer.validated_data['shop'] = request.user.shop
                serializer.validated_data['created_by'] = request.user
                serializer.validated_data['modified_by'] = request.user
                
                payment = serializer.save()
                
                return Response({
                    'message': 'Payment recorded successfully',
                    'data': ExpensePaymentSerializer(payment).data
                }, status=status.HTTP_201_CREATED)
                
        except ValidationError as e:
            return Response({
                'error': 'Invalid data provided',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': 'Failed to create payment',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ExpenseStatusUpdateView(generics.UpdateAPIView):
    """API endpoint for updating expense status."""
    serializer_class = ExpenseStatusSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Expense.objects.filter(shop=self.request.user.shop_user.shop)

    def perform_update(self, serializer):
        serializer.validated_data['modified_by'] = self.request.user
        serializer.save()

class RecurringExpenseLogListView(generics.ListAPIView):
    """API endpoint for listing recurring expense logs."""
    serializer_class = RecurringExpenseLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['generation_date', 'created_at']

    def get_queryset(self):
        return RecurringExpenseLog.objects.filter(
            original_expense__shop=self.request.user.shop_user.shop
        )