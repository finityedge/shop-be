from django.db import models
from django.conf import settings
from apps.shop.models import Shop
from apps.inventory.models import TimeStampedModel, Product

class Customer(TimeStampedModel):
    """Customer information"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    tax_number = models.CharField(max_length=50, blank=True)
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Sale(TimeStampedModel):
    """Sales transaction"""
    PAYMENT_STATUS = [
        ('PENDING', 'Pending'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
    ]
    
    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('BANK', 'Bank Transfer'),
        ('MOBILE', 'Mobile Money'),
        ('CREDIT', 'Store Credit'),
    ]

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='sales')
    customer = models.ForeignKey(Customer, null=True, on_delete=models.CASCADE, related_name='sales')
    invoice_number = models.CharField(max_length=50, unique=True)
    sale_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    
    # Payment information
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default='PENDING')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='CASH')
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return self.invoice_number
    
    @property
    def balance_due(self):
        return self.total - self.paid_amount

class SaleItem(TimeStampedModel):
    """Individual items in a sale"""
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    @property
    def subtotal(self):
        return self.quantity * self.unit_price
    
    @property
    def discount_amount(self):
        return self.subtotal * (self.discount_percentage / 100)
    
    @property
    def total(self):
        return self.subtotal - self.discount_amount
    
    def __str__(self):
        return f"{self.sale.invoice_number} - {self.product.name}"

class Payment(TimeStampedModel):
    """Payment records for sales"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='payments')
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=10, choices=Sale.PAYMENT_METHODS)
    reference_number = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.sale.invoice_number} - {self.amount}"

class SalesReturn(TimeStampedModel):
    """Sales returns/refunds"""
    RETURN_STATUS = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
    ]
    
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='sales_returns')
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='returns')
    return_date = models.DateField()
    status = models.CharField(max_length=10, choices=RETURN_STATUS, default='PENDING')
    reason = models.TextField()
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def __str__(self):
        return f"Return for {self.sale.invoice_number}"

class SalesReturnItem(TimeStampedModel):
    """Individual items in a sales return"""
    sales_return = models.ForeignKey(SalesReturn, on_delete=models.CASCADE, related_name='items')
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    @property
    def total(self):
        return self.quantity * self.unit_price
    
    def __str__(self):
        return f"{self.sales_return} - {self.sale_item.product.name}"