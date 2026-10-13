from django.contrib import admin

from .models import Offer, OfferDetail, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "user_type", "first_name", "last_name")
    list_filter = ("user_type",)
    search_fields = ("user__username", "user__email", "first_name", "last_name")


class OfferDetailInline(admin.TabularInline):
    model = OfferDetail
    extra = 0


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("title", "user_details", "created_at", "updated_at")
    search_fields = ("title", "description", "user_details__user__username")
    inlines = [OfferDetailInline]


@admin.register(OfferDetail)
class OfferDetailAdmin(admin.ModelAdmin):
    list_display = ("title", "offer", "offer_type", "price", "delivery_time_in_days")
    list_filter = ("offer_type",)
    search_fields = ("title", "offer__title")
