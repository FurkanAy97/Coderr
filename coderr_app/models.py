from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    USER_TYPE_CHOICES = [
        ("customer", "Customer"),
        ("business", "Business"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default="customer",
    )
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=100, blank=True)
    tel = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    working_hours = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} ({self.user_type})"


class Offer(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="offers/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user_details = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="offers")

    class Meta:
        verbose_name = "Offer"
        verbose_name_plural = "Offers"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} by {self.user_details.user.username}"

    @property
    def min_price(self):
        return self.details.aggregate(value=models.Min("price"))["value"]

    @property
    def min_delivery_time(self):
        return self.details.aggregate(value=models.Min("delivery_time_in_days"))["value"]


class OfferDetail(models.Model):
    OFFER_TYPE_CHOICES = [
        ("basic", "Basic"),
        ("standard", "Standard"),
        ("premium", "Premium"),
    ]

    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name="details")
    title = models.CharField(max_length=100)
    revisions = models.PositiveIntegerField()
    delivery_time_in_days = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    features = models.JSONField(default=list)
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPE_CHOICES)

    class Meta:
        ordering = ["price"]

    def __str__(self):
        return f"{self.title} ({self.offer_type})"