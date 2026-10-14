# setup urlpatterns
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views


router = DefaultRouter()
router.register(r"profiles", views.ProfileView, basename="profiles")
router.register(r"offers", views.OfferViewSet, basename="offers")
router.register(r"offerdetails", views.OfferDetailViewSet, basename="offerdetails")


urlpatterns = [
    path("", include(router.urls)),
    path("registration/", views.RegistrationView.as_view(), name="registration"),
    path("login/", views.LoginView.as_view(), name="login"),
    path(
        "profile/<int:pk>/",
        views.ProfileView.as_view(
            {"get": "retrieve", "patch": "partial_update"}
        ),
        name="profile-detail",
    ),
]
