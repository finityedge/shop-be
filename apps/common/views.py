from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDate, TruncMonth, ExtractMonth
from django.utils import timezone
# from datetime import datetime, timedelta
import datetime
from decimal import Decimal

from apps.common.upload_service import upload_image
from apps.expense.serializers import ExpenseListSerializer
from apps.inventory.serializers import StockMovementSerializer
from apps.sale.models import Sale, SaleItem, Payment, SalesReturn
from apps.inventory.models import Product, Stock, StockMovement, PurchaseOrder
from apps.expense.models import Expense
from apps.common.pagination import CustomPagination
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import serializers

class DashboardViewSet(ViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_date_range(self, request):
        """
        Helper method to get date range from query params with proper error handling
        Returns tuple of (start_date, end_date) as datetime.date objects
        """
        today = timezone.now().date()
        
        # Handle end_date
        end_date_str = request.query_params.get('end_date')
        if end_date_str:
            try:
                end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                end_date = today
        else:
            end_date = today
            
        # Handle start_date
        start_date_str = request.query_params.get('start_date')
        if start_date_str:
            try:
                start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                start_date = end_date - datetime.timedelta(days=30)
        else:
            start_date = end_date - datetime.timedelta(days=30)
        
        # Ensure start_date is not after end_date
        if start_date > end_date:
            start_date = end_date - datetime.timedelta(days=30)
            
        return start_date, end_date

    def get_comparison_stats(self, current_value, previous_value):
        """Helper method to calculate comparison statistics"""
        if previous_value:
            percentage_change = ((current_value - previous_value) / previous_value) * 100
            trend = 'up' if percentage_change > 0 else 'down'
        else:
            percentage_change = 0
            trend = 'neutral'
            
        return {
            'current_value': current_value,
            'previous_value': previous_value,
            'percentage_change': round(percentage_change, 2),
            'trend': trend
        }

    @action(detail=False, methods=['get'])
    def summary_metrics(self, request):
        """Key metrics for the summary cards"""
        start_date, end_date = self.get_date_range(request)
        previous_start = start_date - datetime.timedelta(days=(end_date - start_date).days)
        shop = request.user.shop
        
        # Current period calculations
        sales = Sale.objects.filter(
            shop=shop,
            sale_date__range=[start_date, end_date]
        )
        current_sales = sales.aggregate(
            total_sales=Sum('total'),
            total_orders=Count('id')
        )
        
        expenses = Expense.objects.filter(
            shop=shop,
            expense_date__range=[start_date, end_date]
        )
        current_expenses = expenses.aggregate(
            total_expenses=Sum('total_amount')
        )
        
        # Previous period calculations
        previous_sales = Sale.objects.filter(
            shop=shop,
            sale_date__range=[previous_start, start_date]
        ).aggregate(
            total_sales=Sum('total'),
            total_orders=Count('id')
        )
        
        previous_expenses = Expense.objects.filter(
            shop=shop,
            expense_date__range=[previous_start, start_date]
        ).aggregate(
            total_expenses=Sum('total_amount')
        )
        
        # Calculate gross profit
        current_profit = (current_sales['total_sales'] or 0) - (current_expenses['total_expenses'] or 0)
        previous_profit = (previous_sales['total_sales'] or 0) - (previous_expenses['total_expenses'] or 0)
        
        return Response({
            'revenue': self.get_comparison_stats(
                current_sales['total_sales'] or 0,
                previous_sales['total_sales'] or 0
            ),
            'orders': self.get_comparison_stats(
                current_sales['total_orders'] or 0,
                previous_sales['total_orders'] or 0
            ),
            'expenses': self.get_comparison_stats(
                current_expenses['total_expenses'] or 0,
                previous_expenses['total_expenses'] or 0
            ),
            'gross_profit': self.get_comparison_stats(
                current_profit,
                previous_profit
            )
        })

    @action(detail=False, methods=['get'])
    def sales_trends(self, request):
        """Daily/Monthly sales trends for charts"""
        start_date, end_date = self.get_date_range(request)
        shop = request.user.shop
        interval = request.query_params.get('interval', 'daily')
        
        sales = Sale.objects.filter(
            shop=shop,
            sale_date__range=[start_date, end_date]
        )
        
        if interval == 'monthly':
            sales = sales.annotate(
                date=TruncMonth('sale_date')
            )
        else:
            sales = sales.annotate(
                date=TruncDate('sale_date')
            )
            
        trends = sales.values('date').annotate(
            revenue=Sum('total'),
            orders=Count('id'),
            average_order_value=ExpressionWrapper(
                Sum('total') / Count('id'),
                output_field=DecimalField()
            )
        ).order_by('date')
        
        return Response(trends)

    @action(detail=False, methods=['get'])
    def top_products(self, request):
        """Top selling products analysis"""
        start_date, end_date = self.get_date_range(request)
        shop = request.user.shop
        limit = int(request.query_params.get('limit', 10))
        
        top_products = SaleItem.objects.filter(
            sale__shop=shop,
            sale__sale_date__range=[start_date, end_date]
        ).values(
            'product__name',
            'product__sku'
        ).annotate(
            quantity_sold=Sum('quantity'),
            revenue=Sum(F('quantity') * F('unit_price')),
            profit=Sum((F('unit_price') - F('product__cost_price')) * F('quantity'))
        ).order_by('-quantity_sold')[:limit]
        
        return Response(top_products)

    @action(detail=False, methods=['get'])
    def inventory_status(self, request):
        """Inventory metrics and low stock alerts"""
        shop = request.user.shop
        
        # Low stock products
        low_stock = Product.objects.filter(
            shop=shop,
            stock__quantity__lte=F('minimum_stock')
        ).values(
            'name',
            'sku',
            'minimum_stock',
            'stock__quantity'
        ).order_by('stock__quantity')
        
        # Stock value
        stock_value = Stock.objects.filter(
            product__shop=shop
        ).aggregate(
            total_value=Sum(F('quantity') * F('product__cost_price')),
            total_items=Count('product')
        )
        
        # Stock movement analysis
        recent_movements = StockMovement.objects.filter(
            product__shop=shop
        ).order_by('-created_at')[:10]
        
        return Response({
            'low_stock_alerts': low_stock,
            'stock_value': stock_value,
            'recent_movements': StockMovementSerializer(recent_movements, many=True).data
        })

    @action(detail=False, methods=['get'])
    def expense_analysis(self, request):
        """Expense breakdown and trends"""
        start_date, end_date = self.get_date_range(request)
        shop = request.user.shop
        
        # Expense by category
        category_breakdown = Expense.objects.filter(
            shop=shop,
            expense_date__range=[start_date, end_date]
        ).values(
            'category__name'
        ).annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Monthly expense trend
        monthly_trend = Expense.objects.filter(
            shop=shop,
            expense_date__range=[start_date, end_date]
        ).annotate(
            month=TruncMonth('expense_date')
        ).values('month').annotate(
            total=Sum('total_amount')
        ).order_by('month')
        
        # Upcoming expenses
        upcoming = Expense.objects.filter(
            shop=shop,
            due_date__gt=timezone.now(),
            status='pending'
        ).order_by('due_date')[:5]
        
        return Response({
            'category_breakdown': category_breakdown,
            'monthly_trend': monthly_trend,
            'upcoming_expenses': ExpenseListSerializer(upcoming, many=True).data
        })

    @action(detail=False, methods=['get'])
    def customer_insights(self, request):
        """Customer purchase analysis"""
        start_date, end_date = self.get_date_range(request)
        shop = request.user.shop
        
        # Top customers
        top_customers = Sale.objects.filter(
            shop=shop,
            sale_date__range=[start_date, end_date]
        ).values(
            'customer__name',
            'customer__id'
        ).annotate(
            total_spent=Sum('total'),
            orders=Count('id'),
            average_order=ExpressionWrapper(
                Sum('total') / Count('id'),
                output_field=DecimalField()
            )
        ).order_by('-total_spent')[:10]
        
        return Response({
            'top_customers': top_customers
        })

    @action(detail=False, methods=['get'])
    def payment_analytics(self, request):
        """Payment and collection analysis"""
        start_date, end_date = self.get_date_range(request)
        shop = request.user.shop
        
        # Payment method breakdown
        payment_methods = Payment.objects.filter(
            sale__shop=shop,
            payment_date__range=[start_date, end_date]
        ).values(
            'payment_method'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Outstanding payments
        outstanding = Sale.objects.filter(
            shop=shop,
            payment_status='partial'
        ).aggregate(
            total_outstanding=Sum('total') - Sum('paid_amount'),
            count=Count('id')
        )
        
        return Response({
            'payment_methods': payment_methods,
            'outstanding_payments': outstanding
        })

class ImageUploadSerializer(serializers.Serializer):
    file = serializers.ImageField()

class ImageUploadViewSet(ViewSet): 
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=ImageUploadSerializer,
        responses={200: openapi.Response('Image URL', openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'image_url': openapi.Schema(type=openapi.TYPE_STRING, description='URL of the uploaded image')
                }
            ))}
        )
    @action(detail=False, methods=['post'])
    def upload_image(self, request):
        serializer = ImageUploadSerializer(data=request.data)
        if serializer.is_valid():
            file = serializer.validated_data['file']
            try:
                shop = request.user.shop
                image_url = upload_image(file, folder=f"shop_{shop.shop_name}")
                if 'error' in image_url:
                    return Response({'error': image_url}, status=400)
                return Response({'image_url': image_url})
            except Exception as e:
                return Response({'error': str(e)}, status=400)
        return Response(serializer.errors, status=400)
        
        


            