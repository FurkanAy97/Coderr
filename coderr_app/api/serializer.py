from django.contrib.auth.models import User
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
            raise serializers.ValidationError("User with this username does not exist")
        return value
    
    def validate(self, data):
        username = data.get("username")
        password = data.get("password")

        if username and password:
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                raise serializers.ValidationError("Invalid username or password")

            if not user.check_password(password):
                raise serializers.ValidationError("Invalid username or password")

        return data



class OfferDetailSerializer(serializers.ModelSerializer):
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


class OfferUserDetailsSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = UserProfile
        fields = ["first_name", "last_name", "username"]


class OfferSerializer(serializers.ModelSerializer):
    user = serializers.IntegerField(source="user_details.user_id", read_only=True)
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
        read_only_fields = ["id", "user", "created_at", "updated_at", "user_details"]

    def validate_details(self, value):
        if len(value) != 3:
            raise serializers.ValidationError("An offer must contain exactly 3 details.")
        return value

    def get_min_price(self, offer):
        if hasattr(offer, "_min_price"):
            return offer._min_price
        return offer.min_price

    def get_min_delivery_time(self, offer):
        if hasattr(offer, "_min_delivery_time"):
            return offer._min_delivery_time
        return offer.min_delivery_time

    def create(self, validated_data):
        details_data = validated_data.pop("details")
        offer = Offer.objects.create(**validated_data)
        OfferDetail.objects.bulk_create(
            [OfferDetail(offer=offer, **detail_data) for detail_data in details_data]
        )
        return offer