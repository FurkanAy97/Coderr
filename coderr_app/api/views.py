from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db.models import Min
from django.contrib.auth import authenticate
from .filters import OfferFilter
from .pagination import OfferPagination
from .permissions import IsBusinessProfile
from .serializer import OfferSerializer, RegistrationSerializer, LoginSerializer
from coderr_app.models import Offer, UserProfile


class RegistrationView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = RegistrationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "username": user.username,
                "email": user.email,
                "user_id": user.id,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )

        if user is None:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "username": user.username,
                "email": user.email,
                "user_id": user.id,
            },
            status=status.HTTP_200_OK,
        )


class ProfileView(viewsets.ViewSet):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        profiles = UserProfile.objects.all().select_related("user")
        return Response(
            [self._profile_data(profile) for profile in profiles],
            status=status.HTTP_200_OK,
        )

    def retrieve(self, request, pk=None):
        try:
            profile = UserProfile.objects.get(user_id=pk)
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(self._profile_data(profile), status=status.HTTP_200_OK)

    def _profile_data(self, profile):
        return {
            "user": profile.user.id,
            "username": profile.user.username,
            "email": profile.user.email,
            "type": profile.user_type,
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "location": profile.location,
            "tel": profile.tel,
            "description": profile.description,
            "working_hours": profile.working_hours,
        }

    @action(detail=False, methods=["get"], url_path="business")
    def business(self, request):
        profiles = UserProfile.objects.filter(
            user_type="business").select_related("user")
        return Response(
            [self._profile_data(profile) for profile in profiles],
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="customer")
    def customer(self, request):
        profiles = UserProfile.objects.filter(
            user_type="customer").select_related("user")
        return Response(
            [self._profile_data(profile) for profile in profiles],
            status=status.HTTP_200_OK,
        )

    def partial_update(self, request, pk=None):
        try:
            profile = UserProfile.objects.get(user_id=pk)
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        for field in [
            "first_name",
            "last_name",
            "location",
            "tel",
            "description",
            "working_hours",
        ]:
            if field in request.data:
                setattr(profile, field, request.data[field])

        profile.save()

        return Response(
            {"message": "Profile updated successfully"},
            status=status.HTTP_200_OK,
        )
        
class OfferViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    authentication_classes = [TokenAuthentication]
    throttle_classes = []
    serializer_class = OfferSerializer
    filterset_class = OfferFilter
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ["title", "description"]
    pagination_class = OfferPagination

    def get_permissions(self):
        if self.action == "list":
            permission_classes = [AllowAny]
        elif self.action == "create":
            permission_classes = [IsAuthenticated, IsBusinessProfile]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        return Offer.objects.annotate(
            _min_price=Min("details__price"),
            _min_delivery_time=Min("details__delivery_time_in_days"),
        ).select_related("user_details__user").prefetch_related("details").order_by(
            "-created_at",
            "-pk",
        )

    def perform_create(self, serializer):
        serializer.save(user_details=self.request.user.profile)
