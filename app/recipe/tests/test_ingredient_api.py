"""Tests for the tags APIs"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Ingredient, Recipe

from recipe.serializers import IngredientSerializer


INGREDIENTS_URL = reverse('recipe:ingredient-list')


def detail_url(ingredient_url):
    """Creates and returns an ingredient detail url"""
    return reverse('recipe:ingredient-detail', args=[ingredient_url])


def create_user(email='user@example.com', password='testpass2234'):
    """Create and return a test user"""
    return get_user_model().objects.create_user(email=email, password=password)


class PublicIngredientsApiTests(TestCase):
    """Tests for unauthenticated API requests"""

    def setUp(self):
        self.client = APIClient()

    def test_auth_is_needed(self):
        """Tests authentication is needed when retrieving ingredients"""
        res = self.client.get(INGREDIENTS_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateIngredientsApiTests(TestCase):
    """Tests auhtenticated requests to ingredients endpoint"""

    def setUp(self):
        self.user = create_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_ingredients(self):
        """Tests retrieving a list of tags for authenticated user"""
        # creating ingredients for the authenticated user
        Ingredient.objects.create(user=self.user, name='Oatmeal')
        Ingredient.objects.create(user=self.user, name='Banana')

        res = self.client.get(INGREDIENTS_URL)
        ingredients = Ingredient.objects.all().order_by('-name')
        serializer = IngredientSerializer(ingredients, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_ingredients_are_limited_to_user(self):
        """Tests list of ingredients is limited to the authenticated user"""
        user2 = create_user(email='user2@example.com', password='testpass123')
        Ingredient.objects.create(user=user2, name='Nuts')
        ingredient = Ingredient.objects.create(user=self.user, name='Flour')

        res = self.client.get(INGREDIENTS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], ingredient.name)
        self.assertEqual(res.data[0]['id'], ingredient.id)

    def test_update_an_ingredient(self):
        """Tests updating an ingredient"""
        ingredient = Ingredient.objects.create(user=self.user, name='Cilantro')

        payload = {
            'name': 'Parsley'
        }
        url = detail_url(ingredient.id)
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ingredient.refresh_from_db()
        self.assertEqual(ingredient.name, payload['name'])

    def test_delete_ingredient(self):
        """Tests deleting an ingredient"""
        ingredient = Ingredient.objects.create(
            user=self.user, name='Chopped onion')

        url = detail_url(ingredient.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        ingredient = Ingredient.objects.filter(user=self.user)
        self.assertFalse(ingredient.exists())

    def test_filtering_on_ingredients_assigned_to_recipes(self):
        """Test listing only ingredients that are assigned to recipes"""
        ing1 = Ingredient.objects.create(user=self.user, name='Ing a')
        ing2 = Ingredient.objects.create(user=self.user, name='Ing b')
        rec1 = Recipe.objects.create(
            title='Rec 1',
            time_minutes=5,
            price=Decimal('4.50'),
            user=self.user,
        )
        rec1.ingredients.add(ing1)

        res = self.client.get(INGREDIENTS_URL, {'assigned_only': 1})

        s1 = IngredientSerializer(ing1)
        s2 = IngredientSerializer(ing2)

        self.assertIn(s1.data, res.data)
        self.assertNotIn(s2.data, res.data)

    def test_filtered_ingredients_unique(self):
        """Tests filtered ingredients return a unique list"""
        ing = Ingredient.objects.create(user=self.user, name='Fish')
        Ingredient.objects.create(user=self.user, name='Bread')
        rec1 = Recipe.objects.create(
            title='Cereal',
            time_minutes=10,
            price=Decimal('4.50'),
            user=self.user,
        )
        rec2 = Recipe.objects.create(
            title='Sunny side up',
            time_minutes=20,
            price=Decimal('4.50'),
            user=self.user,
        )
        rec1.ingredients.add(ing)
        rec2.ingredients.add(ing)

        res = self.client.get(INGREDIENTS_URL, {'assigned_only': 1})

        self.assertEqual(len(res.data), 1)
