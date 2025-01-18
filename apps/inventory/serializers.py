from rest_framework import serializers
from .models import (
    Category, Unit, Product, Supplier, Stock,
    StockMovement, PurchaseOrder, PurchaseOrderItem
)

class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'parent', 'children',
            'created_at', 'modified_at', 'created_by', 'modified_by'
        ]
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']
    
    def get_children(self, obj):
        if obj.children.exists():
            return CategorySerializer(obj.children.all(), many=True).data
        return []

class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = [
            'id', 'name', 'symbol',
            'created_at', 'modified_at', 'created_by', 'modified_by'
        ]
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    unit_symbol = serializers.CharField(source='unit.symbol', read_only=True)
    current_stock = serializers.DecimalField(
        source='stock.quantity',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    shop = serializers.CharField(source='shop.shop_name', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'shop', 'name', 'sku', 'category_name', 'unit', 'cost_price',
            'unit_symbol', 'selling_price', 'current_stock', 'is_active'
        ]

    def create(self, validated_data):
        validated_data['shop'] = self.context['request'].user.shop
        return super().create(validated_data)
    

class ProductDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    unit_details = UnitSerializer(source='unit', read_only=True)
    current_stock = serializers.DecimalField(
        source='stock.quantity',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = Product
        fields = [
            'id', 'shop', 'name', 'sku', 'barcode', 'category', 'category_name',
            'description', 'unit', 'unit_details', 'cost_price', 'selling_price',
            'minimum_stock', 'maximum_stock', 'current_stock', 'is_active',
            'created_at', 'modified_at', 'created_by', 'modified_by'
        ]
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            'id', 'shop', 'name', 'contact_person', 'email', 'phone',
            'address', 'tax_number', 'is_active',
            'created_at', 'modified_at', 'created_by', 'modified_by'
        ]
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class StockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    unit_symbol = serializers.CharField(source='product.unit.symbol', read_only=True)

    class Meta:
        model = Stock
        fields = [
            'id', 'product', 'product_name', 'quantity', 'unit_symbol',
            'created_at', 'modified_at', 'created_by', 'modified_by'
        ]
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    unit_symbol = serializers.CharField(source='product.unit.symbol', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_name', 'movement_type', 'movement_type_display',
            'quantity', 'unit_symbol', 'reference_number', 'supplier',
            'supplier_name', 'unit_price', 'notes',
            'created_at', 'modified_at', 'created_by', 'modified_by'
        ]
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    unit_symbol = serializers.CharField(source='product.unit.symbol', read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id', 'purchase_order', 'product', 'product_name',
            'quantity', 'unit_symbol', 'unit_price', 'received_quantity',
            'total_price', 'created_at', 'modified_at', 'created_by', 'modified_by'
        ]
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

class PurchaseOrderListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'shop', 'po_number', 'supplier', 'supplier_name',
            'status', 'status_display', 'expected_delivery_date',
            'subtotal', 'tax_amount', 'total',
            'created_at', 'modified_at'
        ]

class PurchaseOrderDetailSerializer(serializers.ModelSerializer):
    supplier_details = SupplierSerializer(source='supplier', read_only=True)
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'shop', 'po_number', 'supplier', 'supplier_details',
            'status', 'status_display', 'expected_delivery_date', 'notes',
            'subtotal', 'tax_amount', 'total', 'items',
            'created_at', 'modified_at', 'created_by', 'modified_by'
        ]
        read_only_fields = ['created_at', 'modified_at', 'created_by', 'modified_by']

    def create(self, validated_data):
        items_data = self.context.get('items', [])
        purchase_order = PurchaseOrder.objects.create(**validated_data)
        
        for item_data in items_data:
            PurchaseOrderItem.objects.create(
                purchase_order=purchase_order,
                **item_data
            )
        
        return purchase_order