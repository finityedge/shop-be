from django.db import models
from django.conf import settings
from apps.shop.models import Shop
from apps.inventory.models import TimeStampedModel, Supplier

class ExpenseCategory(TimeStampedModel):
    """Categories for expenses (e.g., Utilities, Rent, Salaries, etc.)"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='expense_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = 'Expense categories'
        
    def __str__(self):
        return self.name

class PaymentMethod(TimeStampedModel):
    """Payment methods for expenses (e.g., Cash, Bank Transfer, Credit Card)"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='payment_methods')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name

class Expense(TimeStampedModel):
    """Main expense record"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('CANCELLED', 'Cancelled'),
        ('PARTIALLY_PAID', 'Partially Paid'),
    ]
    
    RECURRING_CHOICES = [
        ('NONE', 'None'),
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('YEARLY', 'Yearly'),
    ]
    
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='expenses')
    expense_number = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    
    # Expense details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Dates
    expense_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    
    # Payment details
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Recurring expense settings
    is_recurring = models.BooleanField(default=False)
    recurring_frequency = models.CharField(max_length=10, choices=RECURRING_CHOICES, default='NONE')
    recurring_end_date = models.DateField(null=True, blank=True)
    
    # References
    invoice_number = models.CharField(max_length=50, blank=True)
    reference_number = models.CharField(max_length=50, blank=True)
    
    # File attachments
    attachment_url = models.URLField(blank=True)
    
    def __str__(self):
        return f"{self.expense_number} - {self.title}"
    
    def save(self, *args, **kwargs):
        # Calculate total amount including tax
        self.total_amount = self.amount + self.tax_amount
        super().save(*args, **kwargs)

class ExpensePayment(TimeStampedModel):
    """Record of payments made against expenses"""
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    reference_number = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    attachment_url = models.URLField(blank=True)
    
    def __str__(self):
        return f"Payment for {self.expense.expense_number} - {self.amount}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update the paid amount and status of the expense
        total_paid = self.expense.payments.aggregate(total=models.Sum('amount'))['total'] or 0
        self.expense.paid_amount = total_paid
        
        if total_paid >= self.expense.total_amount:
            self.expense.status = 'PAID'
        elif total_paid > 0:
            self.expense.status = 'PARTIALLY_PAID'
        self.expense.save()

class RecurringExpenseLog(TimeStampedModel):
    """Log of automatically generated recurring expenses"""
    original_expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='recurring_logs')
    generated_expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='recurring_source')
    generation_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Recurring log for {self.original_expense.expense_number}"