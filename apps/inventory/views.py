from decimal import Decimal
from rest_framework import generics, status, views, filters
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from .models import (
    Category, Product, Supplier, Stock,
    StockMovement, PurchaseOrder, PurchaseOrderItem, Unit
)

from .serializers import (
    CategorySerializer, ProductCreateSerializer, ProductListSerializer, ProductDetailSerializer, ProductUpdateSerializer, PurchaseOrderCreateSerializer, PurchaseOrderStatusSerializer,
    SupplierSerializer, StockSerializer, StockMovementSerializer,
    PurchaseOrderListSerializer, PurchaseOrderDetailSerializer,
    PurchaseOrderItemSerializer, UnitSerializer
)

class CategoryListCreateView(generics.ListCreateAPIView):
    """API endpoint for listing and creating categories."""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='List all categories or create a new one',
        tags=['Categories'],
        responses={
            201: CategorySerializer,
            400: 'Bad Request',
            401: 'Unauthorized'
        }
    )
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Set created_by and modified_by
            serializer.validated_data['created_by'] = request.user
            serializer.validated_data['modified_by'] = request.user
            
            category = serializer.save()
            return Response({
                'message': 'Category created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            return Response({
                'error': 'Invalid data provided',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': 'Failed to create category',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProductListCreateView(generics.ListCreateAPIView):
    """API endpoint for listing and creating products."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Return different serializers for list and create actions."""
        if self.request.method == 'POST':
            return ProductCreateSerializer
        return ProductListSerializer

    def get_queryset(self):
        """Filter products by shop."""
        return Product.objects.filter(shop=self.request.user.shop)

    @swagger_auto_schema(
        operation_description='Create a new product with initial stock',
        tags=['Products'],
        request_body=ProductCreateSerializer,
        responses={
            201: openapi.Response(
                description="Product created successfully",
                schema=ProductListSerializer
            )
        }
    )
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Set shop and user fields
            serializer.validated_data['shop'] = request.user.shop
            serializer.validated_data['created_by'] = request.user
            serializer.validated_data['modified_by'] = request.user
            
            # Create product
            product = serializer.save()
            
            # Create initial stock if provided
            initial_stock = request.data.get('initial_stock', 0)
            if initial_stock:
                Stock.objects.create(
                    product=product,
                    quantity=initial_stock,
                    created_by=request.user,
                    modified_by=request.user
                )
                
                # Create stock movement record
                StockMovement.objects.create(
                    product=product,
                    movement_type='IN',
                    quantity=initial_stock,
                    unit_price=product.cost_price,
                    reference_number='INITIAL',
                    created_by=request.user,
                    modified_by=request.user
                )
            
            detail_serializer = ProductDetailSerializer(product)

            return Response({
                'message': 'Product created successfully',
                'data': detail_serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            return Response({
                'error': 'Invalid product data',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': 'Failed to create product',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StockAdjustmentView(views.APIView):
    """API endpoint for adjusting stock levels."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='Adjust stock level for a product',
        tags=['Stock'],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['product_id', 'adjustment', 'reason'],
            properties={
                'product_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'adjustment': openapi.Schema(type=openapi.TYPE_NUMBER),
                'reason': openapi.Schema(type=openapi.TYPE_STRING)
            }
        )
    )
    @transaction.atomic
    def post(self, request):
        try:
            product_id = request.data.get('product_id')
            adjustment = request.data.get('adjustment')
            reason = request.data.get('reason')
            
            if not all([product_id, adjustment, reason]):
                raise ValidationError('Missing required fields')
            
            # Get product and verify ownership
            product = get_object_or_404(Product, id=product_id, shop=request.user.shop)
            
            # Get or create stock record
            stock, created = Stock.objects.get_or_create(
                product=product,
                defaults={'quantity': 0, 'created_by': request.user, 'modified_by': request.user}
            )
            
            # Update stock
            stock.quantity = F('quantity') + adjustment
            stock.modified_by = request.user
            stock.save()
            
            # Refresh from database to get actual quantity
            stock.refresh_from_db()
            
            # Create stock movement record
            movement = StockMovement.objects.create(
                product=product,
                movement_type='ADJ',
                quantity=adjustment,
                unit_price=product.cost_price,
                reference_number=f'ADJ-{timezone.now().strftime("%Y%m%d%H%M%S")}',
                notes=reason,
                created_by=request.user,
                modified_by=request.user
            )
            
            return Response({
                'message': 'Stock adjusted successfully',
                'current_stock': stock.quantity,
                'movement': StockMovementSerializer(movement).data
            }, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            return Response({
                'error': 'Invalid data provided',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': 'Failed to adjust stock',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PurchaseOrderListCreateView(generics.ListCreateAPIView):
    """API endpoint for listing and creating purchase orders."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Return different serializers for list and create actions."""
        if self.request.method == 'POST':
            return PurchaseOrderCreateSerializer
        return PurchaseOrderListSerializer

    def get_queryset(self):
        """Filter purchase orders by shop."""
        return PurchaseOrder.objects.filter(shop=self.request.user.shop)

    @swagger_auto_schema(
        operation_description='Create a new purchase order with items',
        tags=['Purchase Orders'],
        request_body=PurchaseOrderCreateSerializer
    )
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            # Validate supplier
            supplier_id = request.data.get('supplier_id')
            supplier = get_object_or_404(Supplier, id=supplier_id, shop=request.user.shop)
            
            # Generate PO number
            po_number = f'PO-{timezone.now().strftime("%Y%m%d%H%M%S")}'
            
            # Create purchase order
            purchase_order = PurchaseOrder.objects.create(
                shop=request.user.shop,
                supplier=supplier,
                po_number=po_number,
                expected_delivery_date=request.data.get('expected_delivery_date'),
                created_by=request.user,
                modified_by=request.user
            )
            
            # Create items and calculate totals
            items_data = request.data.get('items', [])
            if not items_data:
                raise ValidationError('No items provided')
            
            subtotal = Decimal('0')
            for item_data in items_data:
                product = get_object_or_404(
                    Product, 
                    id=item_data['product'],
                    shop=request.user.shop
                )
                
                # Explicitly convert to Decimal
                quantity = Decimal(str(item_data['quantity']))
                unit_price = Decimal(str(item_data['unit_price']))
                
                PurchaseOrderItem.objects.create(
                    purchase_order=purchase_order,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    created_by=request.user,
                    modified_by=request.user
                )
                
                subtotal += quantity * unit_price
            
            # Update PO totals with Decimal
            tax_rate = Decimal('0.1')  # 10% tax as Decimal
            purchase_order.subtotal = subtotal
            purchase_order.tax_amount = subtotal * tax_rate
            purchase_order.total = subtotal + purchase_order.tax_amount
            purchase_order.save()

            return Response({
                'message': 'Purchase order created successfully',
                'data': PurchaseOrderDetailSerializer(purchase_order).data
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            return Response({
                'error': 'Invalid data provided',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': 'Failed to create purchase order',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """API endpoint for retrieving, updating, and deleting categories."""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        serializer.validated_data['modified_by'] = self.request.user
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.products.exists():
                return Response({
                    'error': 'Cannot delete category with associated products',
                    'details': 'Remove or reassign all products first'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            instance.delete()
            return Response({
                'message': 'Category deleted successfully'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': 'Failed to delete category',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """API endpoint for retrieving, updating, and deleting products."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Return different serializers for different actions."""
        if self.request.method in ['PUT', 'PATCH']:
            return ProductUpdateSerializer
        return ProductDetailSerializer

    def get_queryset(self):
        return Product.objects.filter(shop=self.request.user.shop)

    @swagger_auto_schema(
        operation_description='Update a product',
        tags=['Products'],
        request_body=ProductUpdateSerializer,
        responses={
            200: openapi.Response(
                description="Product updated successfully",
                schema=ProductDetailSerializer
            )
        }
    )
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Use UpdateSerializer for validation
        update_serializer = ProductUpdateSerializer(
            instance,
            data=request.data,
            partial=partial
        )
        update_serializer.is_valid(raise_exception=True)
        
        # Add modified_by to validated data
        update_serializer.validated_data['modified_by'] = request.user
        
        # Perform update
        self.perform_update(update_serializer)

        # Return data using DetailSerializer
        detail_serializer = ProductDetailSerializer(instance)
        
        return Response({
            'message': 'Product updated successfully',
            'data': detail_serializer.data
        })

    def perform_update(self, serializer):
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if StockMovement.objects.filter(product=instance).exists():
                # Instead of deleting, mark as inactive
                instance.is_active = False
                instance.modified_by = request.user
                instance.save()
                return Response({
                    'message': 'Product marked as inactive due to existing stock movements'
                }, status=status.HTTP_200_OK)
            
            instance.delete()
            return Response({
                'message': 'Product deleted successfully'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': 'Failed to delete product',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SupplierListCreateView(generics.ListCreateAPIView):
    """API endpoint for listing and creating suppliers."""
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'contact_person', 'email']

    def get_queryset(self):
        return Supplier.objects.filter(shop=self.request.user.shop)

    def perform_create(self, serializer):
        serializer.validated_data['shop'] = self.request.user.shop
        serializer.validated_data['created_by'] = self.request.user
        serializer.validated_data['modified_by'] = self.request.user
        serializer.save()

class SupplierDetailView(generics.RetrieveUpdateDestroyAPIView):
    """API endpoint for retrieving, updating, and deleting suppliers."""
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Supplier.objects.filter(shop=self.request.user.shop)

    def perform_update(self, serializer):
        serializer.validated_data['modified_by'] = self.request.user
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if PurchaseOrder.objects.filter(supplier=instance).exists():
                # Instead of deleting, mark as inactive
                instance.is_active = False
                instance.modified_by = request.user
                instance.save()
                return Response({
                    'message': 'Supplier marked as inactive due to existing purchase orders'
                }, status=status.HTTP_200_OK)
            
            instance.delete()
            return Response({
                'message': 'Supplier deleted successfully'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': 'Failed to delete supplier',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StockMovementListView(generics.ListAPIView):
    """API endpoint for listing stock movements."""
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['movement_type', 'product']

    def get_queryset(self):
        queryset = StockMovement.objects.filter(
            product__shop=self.request.user.shop
        ).select_related('product', 'supplier')
        
        # Date range filtering
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
            
        return queryset

class LowStockAlertsView(generics.ListAPIView):
    """API endpoint for listing products with low stock."""
    serializer_class = ProductDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(
            shop=self.request.user.shop,
            is_active=True,
            stock__quantity__lte=F('minimum_stock')
        ).select_related('stock', 'category', 'unit')

class PurchaseOrderDetailView(generics.RetrieveUpdateDestroyAPIView):
    """API endpoint for managing individual purchase orders."""
    serializer_class = PurchaseOrderDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PurchaseOrder.objects.filter(shop=self.request.user.shop)

    @swagger_auto_schema(
        method='patch',
        operation_description='Update purchase order status',
        tags=['Purchase Orders'],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['status'],
            properties={
                'status': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['PENDING', 'ORDERED', 'RECEIVED', 'CANCELLED']
                )
            }
        )
    )

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        try:
            purchase_order = self.get_object()
            new_status = request.data.get('status')
            
            if not new_status:
                raise ValidationError('Status is required')
                
            if new_status not in dict(PurchaseOrder.STATUS_CHOICES):
                raise ValidationError('Invalid status')
                
            # Validate status transition
            if purchase_order.status == 'RECEIVED':
                raise ValidationError('Cannot change status of received orders')
                
            if purchase_order.status == 'CANCELLED':
                raise ValidationError('Cannot change status of cancelled orders')
            
            purchase_order.status = new_status
            purchase_order.modified_by = request.user
            purchase_order.save()
            
            return Response({
                'message': 'Purchase order status updated successfully',
                'data': self.get_serializer(purchase_order).data
            })
            
        except Exception as e:
            return Response({
                'error': 'Failed to update purchase order status',
                'details': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
class PurchaseOrderStatusUpdateView(views.APIView):
    """API endpoint for updating purchase order status."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return PurchaseOrderStatusSerializer
        return PurchaseOrderDetailSerializer

    @swagger_auto_schema(
        operation_description='Update purchase order status',
        tags=['Purchase Orders'],
        request_body=PurchaseOrderStatusSerializer
    )
    def patch(self, request, pk):
        try:
            purchase_order = get_object_or_404(PurchaseOrder, id=pk, shop=request.user.shop)
            new_status = request.data.get('status')
            
            if not new_status:
                raise ValidationError('Status is required')
                
            if new_status not in dict(PurchaseOrder.STATUS_CHOICES):
                raise ValidationError('Invalid status')
                
            # Validate status transition
            if purchase_order.status == 'RECEIVED':
                raise ValidationError('Cannot change status of received orders')
                
            if purchase_order.status == 'CANCELLED':
                raise ValidationError('Cannot change status of cancelled orders')
            
            purchase_order.status = new_status
            purchase_order.modified_by = request.user
            purchase_order.save()
            
            return Response({
                'message': 'Purchase order status updated successfully',
                'data': PurchaseOrderDetailSerializer(purchase_order).data
            })
            
        except ValidationError as e:
            return Response({
                'error': 'Invalid data provided',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': 'Failed to update purchase order status',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReceivePurchaseOrderView(views.APIView):
    """API endpoint for receiving purchase order items."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='Receive items from a purchase order',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['purchase_order_id', 'items'],
            tags= ['Purchase Orders'],
            properties={
                'purchase_order_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'items': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        required=['item_id', 'received_quantity'],
                        properties={
                            'item_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'received_quantity': openapi.Schema(type=openapi.TYPE_NUMBER)
                        }
                    )
                )
            }
        )
    )
    @transaction.atomic
    def post(self, request):
        try:
            po_id = request.data.get('purchase_order_id')
            items_data = request.data.get('items', [])
            
            if not po_id or not items_data:
                raise ValidationError('Purchase order ID and items are required')
            
            # Get purchase order
            purchase_order = get_object_or_404(
                PurchaseOrder,
                id=po_id,
                shop=request.user.shop
            )
            
            if purchase_order.status == 'RECEIVED':
                raise ValidationError('Purchase order already received')
            
            if purchase_order.status == 'CANCELLED':
                raise ValidationError('Cannot receive cancelled purchase order')
            
            # Process each item
            for item_data in items_data:
                item_id = item_data.get('item_id')
                received_qty = item_data.get('received_quantity')
                
                if not item_id or received_qty is None:
                    raise ValidationError('Item ID and received quantity are required')
                
                # Get PO item
                po_item = get_object_or_404(
                    PurchaseOrderItem,
                    id=item_id,
                    purchase_order=purchase_order
                )
                
                # Validate quantity
                if received_qty > (po_item.quantity - po_item.received_quantity):
                    raise ValidationError(
                        f'Received quantity exceeds remaining quantity for {po_item.product.name}'
                    )
                
                # Update stock
                stock, created = Stock.objects.get_or_create(
                    product=po_item.product,
                    defaults={'quantity': 0, 'created_by': request.user, 'modified_by': request.user}
                )
                
                stock.quantity = F('quantity') + received_qty
                stock.modified_by = request.user
                stock.save()
                
                # Create stock movement
                StockMovement.objects.create(
                    product=po_item.product,
                    movement_type='IN',
                    quantity=received_qty,
                    unit_price=po_item.unit_price,
                    reference_number=purchase_order.po_number,
                    supplier=purchase_order.supplier,
                    created_by=request.user,
                    modified_by=request.user
                )
                
                # Update PO item
                po_item.received_quantity = F('received_quantity') + received_qty
                po_item.modified_by = request.user
                po_item.save()
            
            # Check if all items are received
            purchase_order.refresh_from_db()
            all_items_received = all(
                item.received_quantity >= item.quantity 
                for item in purchase_order.items.all()
            )
            
            if all_items_received:
                purchase_order.status = 'RECEIVED'
                purchase_order.modified_by = request.user
                purchase_order.save()
            
            return Response({
                'message': 'Items received successfully',
                'purchase_order': PurchaseOrderDetailSerializer(purchase_order).data
            }, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            return Response({
                'error': 'Invalid data provided',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': 'Failed to receive items',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UnitListView(generics.ListAPIView):
    """API endpoint for listing units."""
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    @swagger_auto_schema(
        operation_description='List all units',
        tags=['Units'],
        responses={
            200: UnitSerializer,
            401: 'Unauthorized'
        }
    )
    def list(self, request, *args, **kwargs):
        units = self.get_queryset()
        serializer = self.get_serializer(units, many=True)
        return Response(serializer.data)
    
    def get_queryset(self):
        return Unit.objects.all()
    
    def perform_create(self, serializer):
        serializer.validated_data['shop'] = self.request.user.shop
        serializer.validated_data['created_by'] = self.request.user
        serializer.validated_data['modified_by'] = self.request.user
        serializer.save()

