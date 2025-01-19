from rest_framework import serializers
from .models import (
    ExpenseCategory, PaymentMethod, Expense,
    ExpensePayment, RecurringExpenseLog
)

class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = [
            'id', 'shop', 'name', 'description', 'is_active',
            'created_at', 'modified_at', 'created_by', 'modified_by'
        ]
        read_only_fields = ['shop', 'created_at', 'modified_at', 'created_by', 'modified_by']

    def create(self, validated_data):
        validated_data['shop'] = self.context['request'].user.shop
        return super().create(validated_data)

class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'shop', 'name', 'description', 'is_active',
            'created_at', 'modified_at', 'created_by', 'modified_by'
        ]
        read_only_fields = ['shop', 'created_at', 'modified_at', 'created_by', 'modified_by']

    def create(self, validated_data):
        validated_data['shop'] = self.context['request'].user.shop
        return super().create(validated_data)

class ExpensePaymentSerializer(serializers.ModelSerializer):
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True)

    class Meta:
        model = ExpensePayment
        fields = [
            'id', 'expense', 'payment_method', 'payment_method_name',
            'amount', 'payment_date', 'reference_number', 'notes',
            'attachment_url', 'created_at', 'modified_at', 'created_by', 'modified_by'
        ]
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class ExpenseListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    shop = serializers.CharField(source='shop.shop_name', read_only=True)

    class Meta:
        model = Expense
        fields = [
            'id', 'shop', 'expense_number', 'category', 'category_name',
            'supplier_name', 'title', 'amount', 'total_amount',
            'expense_date', 'due_date', 'status', 'status_display',
            'is_recurring', 'paid_amount', 'created_at'
        ]

class ExpenseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            'category', 'supplier', 'title', 'description', 'amount',
            'tax_amount', 'expense_date', 'due_date', 'payment_method',
            'invoice_number', 'reference_number', 'attachment_url',
            'is_recurring', 'recurring_frequency', 'recurring_end_date'
        ]

    def create(self, validated_data):
        validated_data['shop'] = self.context['request'].user.shop
        expense = Expense.objects.create(**validated_data)
        return expense

class ExpenseUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            'category', 'supplier', 'title', 'description', 'amount',
            'tax_amount', 'expense_date', 'due_date', 'payment_method',
            'invoice_number', 'reference_number', 'attachment_url',
            'is_recurring', 'recurring_frequency', 'recurring_end_date', 'status'
        ]

class ExpenseDetailSerializer(serializers.ModelSerializer):
    category = ExpenseCategorySerializer(read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    recurring_frequency_display = serializers.CharField(source='get_recurring_frequency_display', read_only=True)
    payments = ExpensePaymentSerializer(many=True, read_only=True)
    shop = serializers.CharField(source='shop.shop_name', read_only=True)

    class Meta:
        model = Expense
        fields = [
            'id', 'shop', 'expense_number', 'category', 'supplier',
            'supplier_name', 'title', 'description', 'amount', 'tax_amount',
            'total_amount', 'expense_date', 'due_date', 'status', 'status_display',
            'payment_method', 'payment_method_name', 'paid_amount',
            'is_recurring', 'recurring_frequency', 'recurring_frequency_display',
            'recurring_end_date', 'invoice_number', 'reference_number',
            'attachment_url', 'payments', 'created_at', 'modified_at',
            'created_by', 'modified_by'
        ]
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class ExpensePaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpensePayment
        fields = [
            'expense', 'payment_method', 'amount', 'payment_date',
            'reference_number', 'notes', 'attachment_url'
        ]

    def validate(self, data):
        expense = data['expense']
        amount = data['amount']
        
        # Calculate total paid amount including this payment
        total_paid = expense.paid_amount + amount
        
        # Check if payment would exceed total amount
        if total_paid > expense.total_amount:
            raise serializers.ValidationError(
                "Payment amount would exceed the total expense amount"
            )
        
        return data

class RecurringExpenseLogSerializer(serializers.ModelSerializer):
    original_expense_number = serializers.CharField(
        source='original_expense.expense_number',
        read_only=True
    )
    generated_expense_number = serializers.CharField(
        source='generated_expense.expense_number',
        read_only=True
    )

    class Meta:
        model = RecurringExpenseLog
        fields = [
            'id', 'original_expense', 'original_expense_number',
            'generated_expense', 'generated_expense_number',
            'generation_date', 'created_at', 'modified_at',
            'created_by', 'modified_by'
        ]
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class ExpenseStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ['status']