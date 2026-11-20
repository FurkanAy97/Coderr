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

	def test_offer_list_and_detail_contain_detail_links(self):
		list_response = self.client.get(self.url)
		detail_url = reverse("offers-detail", kwargs={"pk": self.expensive_offer.pk})
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		detail_response = self.client.get(detail_url)

		self.assertEqual(list_response.status_code, 200)
		self.assertEqual(detail_response.status_code, 200)
		list_offer = next(
			offer for offer in list_response.data["results"]
			if offer["id"] == self.expensive_offer.pk
		)
		expected = {
			detail.pk: f"/offerdetails/{detail.pk}/"
			for detail in self.expensive_offer.details.all()
		}
		for details in [list_offer["details"], detail_response.data["details"]]:
			self.assertTrue(all(set(detail) == {"id", "url"} for detail in details))
			self.assertEqual({detail["id"]: detail["url"] for detail in details}, expected)

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

	def test_post_requires_authentication(self):
		response = self.client.post(self.url, self.offer_payload(), format="json")
		self.assertEqual(response.status_code, 401)

	def test_customer_cannot_create_offer(self):
		customer = User.objects.create_user(
			username="customer_user",
			email="customer@example.com",
			password="test-password",
		)
		UserProfile.objects.create(user=customer, user_type="customer")
		token = Token.objects.create(user=customer)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

		response = self.client.post(self.url, self.offer_payload(), format="json")
		self.assertEqual(response.status_code, 403)

	def test_business_user_can_create_offer_with_three_details(self):
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

		response = self.client.post(self.url, self.offer_payload(), format="json")

		self.assertEqual(response.status_code, 201)
		self.assertEqual(response.data["user"], self.user.pk)
		self.assertEqual(len(response.data["details"]), 3)
		self.assertEqual(Offer.objects.count(), 3)

	def test_business_user_cannot_create_duplicate_offer_title(self):
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		payload = self.offer_payload()

		first_response = self.client.post(self.url, payload, format="json")
		second_response = self.client.post(self.url, payload, format="json")

		self.assertEqual(first_response.status_code, 201)
		self.assertEqual(second_response.status_code, 400)
		self.assertIn("title", second_response.data)
		self.assertEqual(Offer.objects.count(), 3)

	def test_offer_detail_get_requires_authentication(self):
		url = reverse("offers-detail", kwargs={"pk": self.expensive_offer.pk})

		self.assertEqual(self.client.get(url).status_code, 401)
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		response = self.client.get(url)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["id"], self.expensive_offer.pk)
		self.assertEqual(response.data["title"], "Website Design")

	def test_offerdetail_get_requires_authentication(self):
		offer_detail = self.expensive_offer.details.first()
		url = reverse("offerdetails-detail", kwargs={"pk": offer_detail.pk})

		self.assertEqual(self.client.get(url).status_code, 401)
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		response = self.client.get(url)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["id"], offer_detail.pk)
		self.assertEqual(response.data["offer_type"], "basic")

	def test_revisions_delivery_and_numeric_prices_in_offer_endpoints(self):
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		payload = self.offer_payload()
		payload["details"][0].update(revisions=-1, delivery_time_in_days=1, price=120.50)

		response = self.client.post(self.url, payload, format="json")

		self.assertEqual(response.status_code, 201)
		basic = next(detail for detail in response.json()["details"] if detail["offer_type"] == "basic")
		self.assertEqual(basic["revisions"], -1)
		self.assertEqual(basic["delivery_time_in_days"], 1)
		self.assertIsInstance(basic["price"], (int, float))
		self.assertEqual(basic["price"], 120.5)

		detail_url = reverse("offerdetails-detail", kwargs={"pk": basic["id"]})
		detail_response = self.client.get(detail_url)
		self.assertEqual(detail_response.status_code, 200)
		self.assertEqual(detail_response.json()["price"], 120.5)
		self.assertIsInstance(detail_response.json()["price"], (int, float))

		offer_url = reverse("offers-detail", kwargs={"pk": response.data["id"]})
		patch_response = self.client.patch(
			offer_url,
			{"details": [{"offer_type": "standard", "revisions": -1, "price": "99.25"}]},
			format="json",
		)
		self.assertEqual(patch_response.status_code, 200)
		standard = next(detail for detail in patch_response.json()["details"] if detail["offer_type"] == "standard")
		self.assertEqual(standard["revisions"], -1)
		self.assertEqual(standard["price"], 99.25)
		self.assertIsInstance(standard["price"], (int, float))

	def test_rejects_revisions_below_minus_one_and_nonpositive_delivery(self):
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		offer_url = reverse("offers-detail", kwargs={"pk": self.expensive_offer.pk})

		for field, value in [("revisions", -2), ("delivery_time_in_days", 0), ("delivery_time_in_days", -1)]:
			with self.subTest(field=field, value=value):
				payload = self.offer_payload()
				payload["details"][0][field] = value
				self.assertEqual(self.client.post(self.url, payload, format="json").status_code, 400)
				self.assertEqual(
					self.client.patch(
						offer_url, {"details": [{"offer_type": "basic", field: value}]}, format="json"
					).status_code,
					400,
				)

	def test_business_owner_can_patch_offer(self):
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		url = reverse("offers-detail", kwargs={"pk": self.expensive_offer.pk})

		response = self.client.patch(
			url,
			{"title": "Updated Website Design"},
			format="json",
		)

		self.assertEqual(response.status_code, 200)
		self.expensive_offer.refresh_from_db()
		self.assertEqual(self.expensive_offer.title, "Updated Website Design")

	def test_business_owner_can_patch_one_offer_detail_without_changing_others(self):
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		url = reverse("offers-detail", kwargs={"pk": self.expensive_offer.pk})
		basic_detail = self.expensive_offer.details.get(offer_type="basic")
		standard_detail = self.expensive_offer.details.get(offer_type="standard")

		response = self.client.patch(
			url,
			{"details": [{"offer_type": "basic", "price": "80.00"}]},
			format="json",
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.data["details"]), 3)
		self.assertEqual(response.data["min_price"], 80)
		basic_detail.refresh_from_db()
		standard_detail.refresh_from_db()
		self.assertEqual(basic_detail.price, Decimal("80.00"))
		self.assertEqual(standard_detail.price, Decimal("400.00"))

	def test_rejects_invalid_detail_type_updates(self):
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		url = reverse("offers-detail", kwargs={"pk": self.expensive_offer.pk})
		self.expensive_offer.details.filter(offer_type="premium").delete()
		invalid_details = [
			[{"price": "80.00"}],
			[{"id": self.expensive_offer.details.first().pk, "price": "80.00"}],
			[{"offer_type": "premium", "price": "80.00"}],
			[{"offer_type": "basic", "price": "80.00"}, {"offer_type": "basic", "price": "90.00"}],
			[{"offer_type": "basic"}],
		]

		for details in invalid_details:
			with self.subTest(details=details):
				response = self.client.patch(url, {"details": details}, format="json")
				self.assertEqual(response.status_code, 400)
		self.assertEqual(self.expensive_offer.details.get(offer_type="basic").price, Decimal("250.00"))

	def test_rejects_ambiguous_existing_detail_type(self):
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		url = reverse("offers-detail", kwargs={"pk": self.expensive_offer.pk})
		self.expensive_offer.details.filter(offer_type="standard").update(offer_type="basic")

		response = self.client.patch(
			url, {"details": [{"offer_type": "basic", "price": "80.00"}]}, format="json"
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(
			set(self.expensive_offer.details.filter(offer_type="basic").values_list("price", flat=True)),
			{Decimal("250.00"), Decimal("400.00")},
		)

	def test_rejects_creating_offer_with_duplicate_detail_types(self):
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		payload = self.offer_payload()
		payload["details"][1]["offer_type"] = "basic"

		response = self.client.post(self.url, payload, format="json")

		self.assertEqual(response.status_code, 400)
		self.assertEqual(Offer.objects.count(), 2)

	def test_other_business_cannot_patch_or_delete_offer(self):
		other_user = User.objects.create_user(
			username="other_business",
			email="other@example.com",
			password="test-password",
		)
		UserProfile.objects.create(user=other_user, user_type="business")
		token = Token.objects.create(user=other_user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		url = reverse("offers-detail", kwargs={"pk": self.expensive_offer.pk})

		patch_response = self.client.patch(
			url,
			{"title": "Stolen Offer"},
			format="json",
		)
		delete_response = self.client.delete(url)

		self.assertEqual(patch_response.status_code, 403)
		self.assertEqual(delete_response.status_code, 403)

	def test_business_owner_can_delete_offer_and_its_details(self):
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		offer_id = self.expensive_offer.pk
		detail_ids = list(self.expensive_offer.details.values_list("pk", flat=True))
		url = reverse("offers-detail", kwargs={"pk": offer_id})

		response = self.client.delete(url)

		self.assertEqual(response.status_code, 204)
		self.assertFalse(Offer.objects.filter(pk=offer_id).exists())
		self.assertFalse(OfferDetail.objects.filter(pk__in=detail_ids).exists())

	def test_put_is_not_enabled(self):
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
		url = reverse("offers-detail", kwargs={"pk": self.expensive_offer.pk})

		response = self.client.put(url, {"title": "Replacement"}, format="json")

		self.assertEqual(response.status_code, 405)

	def offer_payload(self):
		return {
			"title": "New Design Offer",
			"image": None,
			"description": "Design package",
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

	def test_partial_update_forbidden_for_user_without_profile(self):
		other_user = User.objects.create_user(
			username="other",
			email="other@example.com",
			password="test-password",
		)
		token = Token.objects.create(user=other_user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

		response = self.client.patch(self.url, {"first_name": "Changed"})

		self.assertEqual(response.status_code, 403)

	def test_profile_list_routes_and_removed_plural_routes(self):
		business = User.objects.create_user(username="business", password="test-password")
		UserProfile.objects.create(user=business, user_type="business")
		token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

		for url, expected_user in [
			("/api/profiles/business/", business),
			("/api/profiles/customer/", self.user),
		]:
			with self.subTest(url=url):
				response = self.client.get(url)
				self.assertEqual(response.status_code, 200)
				self.assertEqual([profile["user"] for profile in response.data], [expected_user.pk])
				self.assertEqual(self.client.patch(url, {}).status_code, 405)

		for url in ["/api/profiles/", f"/api/profiles/{self.user.pk}/"]:
			with self.subTest(url=url):
				self.assertEqual(self.client.get(url).status_code, 404)
				self.assertEqual(self.client.patch(url, {}).status_code, 404)
