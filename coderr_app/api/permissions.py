from rest_framework.permissions import BasePermission


class IsBusinessProfile(BasePermission):
	def has_permission(self, request, view):
		return (
			request.user.is_authenticated
			and hasattr(request.user, "profile")
			and request.user.profile.user_type == "business"
		)

	def has_object_permission(self, request, view, obj):
		return obj.user_details.user_id == request.user.id


class OfferPermission(BasePermission):
	"""Lesen fuer alle, Erstellen nur fuer Business-User, Bearbeiten/Loeschen nur fuer den Business-Ersteller."""

	def has_permission(self, request, view):
		if view.action in ("list", "retrieve"):
			return True
		if view.action in ("create", "update", "partial_update", "destroy"):
			return IsBusinessProfile().has_permission(request, view)
		return bool(request.user and request.user.is_authenticated)

	def has_object_permission(self, request, view, obj):
		if view.action in ("update", "partial_update", "destroy"):
			return IsBusinessProfile().has_object_permission(request, view, obj)
		return True