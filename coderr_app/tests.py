from decimal import Decimal

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from coderr_app.api.serializer import OfferSerializer
from coderr_app.models import Offer, OfferDetail, UserProfile


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


class OfferListViewSetTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username="business_owner",
			email="owner@example.com",
			password="test-password",
		)
		self.profile = UserProfile.objects.create(
			user=self.user,
			user_type="business",
		)
		self.cheaper_offer = self.create_offer(
			"Logo Design",
			[("basic", 100, 5), ("standard", 200, 7), ("premium", 500, 10)],
		)
		self.expensive_offer = self.create_offer(
			"Website Design",
			[("basic", 250, 4), ("standard", 400, 8), ("premium", 800, 12)],
		)
		self.url = reverse("offers-list")

	def create_offer(self, title, detail_values):
		offer = Offer.objects.create(
			title=title,
			description=f"Beschreibung für {title}",
			user_details=self.profile,
		)
		OfferDetail.objects.bulk_create(
			[
				OfferDetail(
					offer=offer,
					title=offer_type.title(),
					revisions=2,
					delivery_time_in_days=delivery_time,
					price=price,
					features=["Design"],
					offer_type=offer_type,
				)
				for offer_type, price, delivery_time in detail_values
			]
		)
		return offer

	def test_returns_paginated_offers_with_calculated_values(self):
		response = self.client.get(self.url, {"page_size": 1})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["count"], 2)
		self.assertIsNotNone(response.data["next"])
		self.assertEqual(len(response.data["results"]), 1)
		self.assertEqual(response.data["results"][0]["title"], "Website Design")
		self.assertEqual(response.data["results"][0]["min_price"], 250)
		self.assertEqual(response.data["results"][0]["min_delivery_time"], 4)

	def test_filters_by_minimum_price_and_search_text(self):
		response = self.client.get(
			self.url,
			{"min_price": "200", "search": "website"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["count"], 1)
		self.assertEqual(response.data["results"][0]["title"], "Website Design")

	def test_orders_by_public_min_price_parameter(self):
		response = self.client.get(self.url, {"ordering": "min_price"})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["results"][0]["title"], "Logo Design")

	def test_rejects_invalid_query_parameters(self):
		response = self.client.get(self.url, {"creator_id": "abc"})

		self.assertEqual(response.status_code, 400)
		self.assertIn("creator_id", response.data)

		response = self.client.get(self.url, {"page_size": "not-a-number"})
		self.assertEqual(response.status_code, 400)
		self.assertIn("page_size", response.data)


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
