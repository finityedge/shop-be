from rest_framework import serializers
from apps.inventory.models import Product
from .models import (
    Customer, Sale, SaleItem, Payment, 
    SalesReturn, SalesReturnItem
)
from decimal import Decimal

# Customer Serializers
class CustomerListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone', 'email', 'is_active']

class CustomerDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class CustomerCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        exclude = ['shop', 'created_at', 'modified_at', 'created_by', 'modified_by']

    def validate_credit_limit(self, value):
        if value < 0:
            raise serializers.ValidationError("Credit limit cannot be negative")
        return value

# Sale Item Serializers
class SaleItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        exclude = ['sale', 'created_at', 'modified_at', 'created_by', 'modified_by']

    def validate(self, data):
        # Check if product has sufficient stock
        product = data['product']
        quantity = data['quantity']
        if product.stock.quantity < quantity:
            raise serializers.ValidationError(
                f"Insufficient stock. Available: {product.stock.quantity}"
            )
        
        # Optional: Validate that discount amount doesn't exceed subtotal
        if 'discount_amount' in data and 'unit_price' in data:
            subtotal = quantity * data['unit_price']
            if data['discount_amount'] > subtotal:
                raise serializers.ValidationError(
                    "Discount amount cannot exceed the subtotal"
                )
        
        return data

class SaleItemDetailSerializer(serializers.ModelSerializer):
    product = serializers.StringRelatedField()
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = SaleItem
        fields = '__all__'
# Sale Serializers
class SaleListSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Sale
        fields = ['id', 'invoice_number', 'sale_date', 'customer_name', 
                 'total', 'payment_status']
    
    def get_customer_name(self, obj):
        return obj.customer.name if obj.customer else None

class SaleDetailSerializer(serializers.ModelSerializer):
    customer = CustomerDetailSerializer(required=False, allow_null=True)
    items = SaleItemDetailSerializer(many=True, read_only=True)
    balance_due = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Sale
        fields = '__all__'
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class SaleCreateSerializer(serializers.ModelSerializer):
    items = SaleItemCreateSerializer(many=True)

    class Meta:
        model = Sale
        exclude = ['shop', 'subtotal', 'discount_amount', 'payment_status', 'payment_method', 'paid_amount', 'total', 'invoice_number', 'created_at', 'modified_at', 'created_by', 'modified_by']

    def create(self, validated_data):
        try:
            items_data = validated_data.pop('items')

            try:
                sale = Sale.objects.create(**validated_data)
            except Exception as e:
                raise serializers.ValidationError(f"Error creating sale: {str(e)}")
            
            # Calculate totals
            subtotal = 0
            for item_data in items_data:
                try:
                    item = SaleItem.objects.create(sale=sale, **item_data)
                    subtotal += item.total
                except Exception as e:
                    # Delete the sale if item creation fails
                    sale.delete()
                    raise serializers.ValidationError(f"Error creating sale item: {str(e)}")

            # Update sale totals
            try:
                sale.subtotal = subtotal
                # sale.tax_amount = subtotal * Decimal(0.1)  # Assuming 10% tax
                sale.tax_amount = 0  # TODO: Set tax amount to 0 for now
                sale.total = sale.subtotal + sale.tax_amount - sale.discount_amount
                sale.save()
            except Exception as e:
                raise serializers.ValidationError(f"Error updating sale totals: {str(e)}")

            return sale
            
        except Exception as e:
            # Catch any other unexpected errors
            raise serializers.ValidationError(f"Unexpected error in sale creation: {str(e)}")

class SaleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        exclude = ['created_at', 'modified_at', 'created_by', 'modified_by']
        read_only_fields = ['invoice_number', 'subtotal', 'total']

# Payment Serializers
class PaymentListSerializer(serializers.ModelSerializer):
    sale_invoice = serializers.CharField(source='sale.invoice_number')

    class Meta:
        model = Payment
        fields = ['id', 'sale_invoice', 'amount', 'payment_date', 'payment_method']

class PaymentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        exclude = ['shop', 'created_at', 'modified_at', 'created_by', 'modified_by']

    def validate(self, data):
        sale = data['sale']
        amount = data['amount']
        
        # Check if payment amount exceeds remaining balance
        if amount > sale.balance_due:
            raise serializers.ValidationError(
                f"Payment amount ({amount}) exceeds remaining balance ({sale.balance_due})"
            )
        return data

# Sales Return Serializers
class SalesReturnItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesReturnItem
        exclude = ['sales_return', 'created_at', 'modified_at', 'created_by', 'modified_by']

    def validate(self, data):
        sale_item = data['sale_item']
        quantity = data['quantity']
        
        if quantity > sale_item.quantity:
            raise serializers.ValidationError(
                f"Return quantity cannot exceed sold quantity ({sale_item.quantity})"
            )
        return data

class SalesReturnItemDetailSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='sale_item.product.name')
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = SalesReturnItem
        fields = '__all__'

class SalesReturnListSerializer(serializers.ModelSerializer):
    sale_invoice = serializers.CharField(source='sale.invoice_number')

    class Meta:
        model = SalesReturn
        fields = ['id', 'sale_invoice', 'return_date', 'status', 'total']

class SalesReturnDetailSerializer(serializers.ModelSerializer):
    items = SalesReturnItemDetailSerializer(many=True, read_only=True)
    sale = SaleDetailSerializer()

    class Meta:
        model = SalesReturn
        fields = '__all__'
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class SalesReturnCreateSerializer(serializers.ModelSerializer):
    items = SalesReturnItemCreateSerializer(many=True)

    class Meta:
        model = SalesReturn
        exclude = ['shop', 'tax_amount', 'subtotal', 'total', 'created_at', 'modified_at', 'created_by', 'modified_by']

    def create(self, validated_data):
        try:
            items_data = validated_data.pop('items')

            validated_data['shop'] = self.context['request'].user.shop

            sales_return = SalesReturn.objects.create(**validated_data)
            
            # Calculate totals
            subtotal = 0
            for item_data in items_data:
                item = SalesReturnItem.objects.create(
                    sales_return=sales_return, 
                    **item_data
                )
                subtotal += item.total

            # Update return totals
            sales_return.subtotal = subtotal
            sales_return.tax_amount = subtotal * Decimal(0.1)  # Assuming 10% tax
            sales_return.total = sales_return.subtotal + sales_return.tax_amount
            sales_return.save()

            return sales_return
        except Exception as e:
            raise serializers.ValidationError(str(e))
        