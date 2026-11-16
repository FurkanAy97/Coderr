from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from coderr_app.models import Offer, OfferDetail, UserProfile


class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    repeated_password = serializers.CharField(write_only=True)
    type = serializers.ChoiceField(
        choices=[("customer", "Customer"), ("business", "Business")],
    )

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email is already in use")
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Username is already in use")
        return value

    def validate(self, data):
        if data["password"] != data["repeated_password"]:
            raise serializers.ValidationError(
                {"repeated_password": "Passwords do not match"}
            )
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )

        UserProfile.objects.create(
            user=user,
            user_type=validated_data["type"],
        )

        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if not User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "User with this username does not exist")
        return value

    def validate(self, data):
        username = data.get("username")
        password = data.get("password")

        if username and password:
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    "Invalid username or password")

            if not user.check_password(password):
                raise serializers.ValidationError(
                    "Invalid username or password")

        return data


class OfferDetailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False)

    class Meta:
        model = OfferDetail
        fields = [
            "id",
            "title",
            "revisions",
            "delivery_time_in_days",
            "price",
            "features",
            "offer_type",
        ]
        read_only_fields = ["id"]


class OfferDetailLinkSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="offerdetails-detail")

    class Meta:
        model = OfferDetail
        fields = ["id", "url"]


class OfferUserDetailsSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = UserProfile
        fields = ["first_name", "last_name", "username"]


class OfferSerializer(serializers.ModelSerializer):
    user = serializers.IntegerField(
        source="user_details.user_id", read_only=True)
    user_details = OfferUserDetailsSerializer(read_only=True)
    details = OfferDetailSerializer(many=True)
    min_price = serializers.SerializerMethodField()
    min_delivery_time = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = [
            "id",
            "user",
            "title",
            "image",
            "description",
            "created_at",
            "updated_at",
            "details",
            "min_price",
            "min_delivery_time",
            "user_details",
        ]
        read_only_fields = ["id", "user",
                            "created_at", "updated_at", "user_details"]

    def validate_title(self, value):
        request = self.context.get("request")
        if (
            request
            and request.method in ("POST", "PUT", "PATCH")
            and request.user.is_authenticated
        ):
            profile = getattr(request.user, "profile", None)
            if profile:
                matching_offers = Offer.objects.filter(
                    user_details=profile,
                    title__iexact=value,
                )
                if self.instance:
                    matching_offers = matching_offers.exclude(
                        pk=self.instance.pk)
                if matching_offers.exists():
                    raise serializers.ValidationError(
                        "You already have an offer with this title."
                    )
        return value

    def validate_details(self, value):
        if self.instance is None:
            if len(value) != 3:
                raise serializers.ValidationError(
                    "An offer must contain exactly 3 details."
                )
            if any("id" in detail_data for detail_data in value):
                raise serializers.ValidationError(
                    "Detail IDs are assigned by the server when creating an offer."
                )
            types = [detail_data["offer_type"] for detail_data in value]
            if len(types) != len(set(types)):
                raise serializers.ValidationError(
                    "Each offer type may only appear once."
                )
            return value

        if not value:
            raise serializers.ValidationError(
                "Provide at least one detail to update.")

        existing_types = list(
            self.instance.details.values_list("offer_type", flat=True))
        received_types = set()
        for detail_data in value:
            detail_type = detail_data.get("offer_type")
            if "id" in detail_data:
                raise serializers.ValidationError(
                    "Use offer_type instead of id to update a detail."
                )
            if detail_type is None:
                raise serializers.ValidationError(
                    "Each detail update must include its offer_type."
                )
            if existing_types.count(detail_type) != 1:
                raise serializers.ValidationError(
                    f"Offer type {detail_type} must identify exactly one detail."
                )
            if detail_type in received_types:
                raise serializers.ValidationError(
                    f"Offer type {detail_type} was included more than once."
                )
            if len(detail_data) == 1:
                raise serializers.ValidationError(
                    f"Provide at least one field to update for offer type {detail_type}."
                )
            received_types.add(detail_type)
        return value

    def get_min_price(self, offer):
        if hasattr(offer, "_min_price"):
            return offer._min_price
        return offer.min_price

    def get_min_delivery_time(self, offer):
        if hasattr(offer, "_min_delivery_time"):
            return offer._min_delivery_time
        return offer.min_delivery_time

    @transaction.atomic
    def create(self, validated_data):
        details_data = validated_data.pop("details")
        offer = Offer.objects.create(**validated_data)
        OfferDetail.objects.bulk_create(
            [OfferDetail(offer=offer, **detail_data)
             for detail_data in details_data]
        )
        return offer

    @transaction.atomic
    def update(self, instance, validated_data):
        details_data = validated_data.pop("details", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if details_data is not None:
            for detail_data in details_data:
                detail_type = detail_data.pop("offer_type")
                OfferDetail.objects.filter(
                    offer=instance,
                    offer_type=detail_type,
                ).update(**detail_data)
            instance.__dict__.pop("_min_price", None)
            instance.__dict__.pop("_min_delivery_time", None)
            getattr(instance, "_prefetched_objects_cache",
                    {}).pop("details", None)

        return instance


class OfferReadSerializer(OfferSerializer):
    details = OfferDetailLinkSerializer(many=True, read_only=True)
