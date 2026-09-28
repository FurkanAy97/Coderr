from decimal import Decimal

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from coderr_app.api.serializer import OfferSerializer
from coderr_app.models import UserProfile


class OfferSerializerTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username="designer",
			email="designer@example.com",
			password="test-password",
		)
		self.profile = UserProfile.objects.create(
			user=self.user,
			user_type="business",
			first_name="Dana",
			last_name="Designer",
		)

	def test_creates_offer_with_three_details_and_calculated_minimums(self):
		payload = {
			"title": "Design-Paket",
			"image": None,
			"description": "Drei Design-Stufen",
			"details": [
				{
					"title": "Basic",
					"revisions": 2,
					"delivery_time_in_days": 5,
					"price": "100.00",
					"features": ["Logo"],
					"offer_type": "basic",
				},
				{
					"title": "Standard",
					"revisions": 5,
					"delivery_time_in_days": 7,
					"price": "200.00",
					"features": ["Logo", "Briefpapier"],
					"offer_type": "standard",
				},
				{
					"title": "Premium",
					"revisions": 10,
					"delivery_time_in_days": 10,
					"price": "500.00",
					"features": ["Logo", "Flyer"],
					"offer_type": "premium",
				},
			],
		}

		serializer = OfferSerializer(data=payload)
		self.assertTrue(serializer.is_valid(), serializer.errors)
		offer = serializer.save(user_details=self.profile)

		self.assertEqual(offer.details.count(), 3)
		self.assertEqual(offer.min_price, Decimal("100.00"))
		self.assertEqual(offer.min_delivery_time, 5)
		self.assertEqual(serializer.data["user"], self.user.pk)
		self.assertEqual(serializer.data["user_details"]["username"], "designer")

	def test_rejects_offer_with_other_than_three_details(self):
		serializer = OfferSerializer(
			data={"title": "Unvollständiges Paket", "details": []}
		)

		self.assertFalse(serializer.is_valid())
		self.assertIn("details", serializer.errors)


class ProfileViewTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username="customer",
			email="customer@example.com",
			password="test-password",
		)
		UserProfile.objects.create(
			user=self.user,
			user_type="customer",
			first_name="Casey",
		)
		self.url = reverse("profile-detail", kwargs={"pk": self.user.pk})

	def test_detail_requires_token_and_uses_user_id(self):
		response = self.client.get(self.url)
		self.assertEqual(response.status_code, 401)

		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		response = self.client.get(self.url)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["user"], self.user.pk)
		self.assertEqual(response.data["type"], "customer")
		self.assertEqual(response.data["first_name"], "Casey")
