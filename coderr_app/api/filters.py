import django_filters
from django import forms

from coderr_app.models import Offer


class IntegerFilter(django_filters.Filter):
    field_class = forms.IntegerField


class OfferFilter(django_filters.FilterSet):
    creator_id = IntegerFilter(field_name="user_details__user_id", min_value=1)
    min_price = django_filters.NumberFilter(
        field_name="_min_price",
        lookup_expr="gte",
        min_value=0,
    )
    max_delivery_time = IntegerFilter(
        field_name="_min_delivery_time",
        lookup_expr="lte",
        min_value=0,
    )
    ordering = django_filters.OrderingFilter(
        fields=(
            ("updated_at", "updated_at"),
            ("_min_price", "min_price"),
        )
    )

    class Meta:
        model = Offer
        fields = ["creator_id", "min_price", "max_delivery_time"]