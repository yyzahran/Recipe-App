"""Tests for recipe APIs"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe

from recipe.serializers import (
    RecipeSerializer,
    RecipeDetailSerializer
)

RECIPES_URL = reverse('recipe:recipe-list')


def detail_url(recipe_id):
    """Creates and returns a recipe detail url"""
    return reverse('recipe:recipe-detail', args=[recipe_id])


def create_recipe(user, **params):
    """Create and return a sample recipe for testing"""
    defaults = {
        'title': 'Sample title',
        'time_minutes': 20,
        'description': 'The quick brown fox jumps \
            over the lazy dog',
        'price': Decimal('4.55'),
        'link': 'hhtps://www.example.com/recipe.pdf',
    }

    defaults.update(params)

    recipe = Recipe.objects.create(user=user, **defaults)

    return recipe


def create_user(**params):
    """Create and return a new user"""
    return get_user_model().objects.create_user(**params)


class PublicRecipeApiTests(TestCase):
    """Test unauthenticated API requests"""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test authentication is reuired to call API"""
        res = self.client.get(RECIPES_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeApiTests(TestCase):
    """Test authenticated API requests"""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email='user@example.com', password='testpass123')
        self.client.force_authenticate(user=self.user)

    def test_retrieve_recipes(self):
        """Test retrieving a list of recipes"""
        create_recipe(user=self.user)
        create_recipe(user=self.user)

        res = self.client.get(path=RECIPES_URL)

        recipes = Recipe.objects.all().order_by('-id')
        serializer = RecipeSerializer(recipes, many=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_recipe_list_limited_to_user(self):
        """Test list of recipes is liited to authenticated user,
        and not all recipes in the database"""
        other_user = create_user(email='other_user@example.com',
                                 password='othertestpass1234'
                                 )
        create_recipe(user=other_user)
        create_recipe(user=self.user)

        res = self.client.get(path=RECIPES_URL)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_get_recipe_detail(self):
        """Test get details of a recipe"""
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe_id=recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(res.data, serializer.data)

    def test_create_recipe(self):
        """Test creating a recipe"""
        payload = {
            'title': 'Sample recipe',
            'time_minutes': 30,
            'price': Decimal('5.99'),
        }

        res = self.client.post(RECIPES_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # getting the recipe by the id gotten from the 201 request
        recipe = Recipe.objects.get(id=res.data['id'])
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)

        self.assertEqual(recipe.user, self.user)

    def test_partial_recipe_update(self):
        """Tests partially updating a recipe, it's by udpating
        a part of the recipe object"""
        original_link = 'http://example.com/recipe.pdf'
        recipe = create_recipe(
            user=self.user, title='Sample recipe title', link=original_link)
        payload = {
            'title': "New recipe title"
        }

        url = detail_url(recipe_id=recipe.id)
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        self.assertEqual(recipe.link, original_link)
        self.assertEqual(recipe.user, self.user)

    def test_full_recipe_update(self):
        """Tests fully updating a recipe, it's by updating
        all its fields"""
        recipe = create_recipe(
            user=self.user,
            title='Sample recipe title',
            link='http://example.com/recipe.pdf',
            description='Sample recipe description',
        )

        payload = {
            'title': "New recipe title",
            'link': 'http://example.com/recipe2.pdf',
            'description': 'New sample recipe description',
            'time_minutes': 10,
            'price': Decimal(2.50),
        }

        url = detail_url(recipe_id=recipe.id)
        res = self.client.put(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)

        self.assertEqual(recipe.user, self.user)

    def test_update_recipe_user_returns_error(self):
        """Tetss updating the user for a recipe results in an error"""
        new_user = create_user(
            email='user2@example.com',
            password='testpass1234',
        )

        recipe = create_recipe(user=self.user)

        payload = {'user': new_user.id}
        url = detail_url(recipe_id=recipe.id)
        self.client.patch(url, payload)

        recipe.refresh_from_db()
        self.assertEqual(recipe.user, self.user)

    def test_delete_recipe(self):
        """Tests deleting a recipe"""
        recipe = create_recipe(user=self.user)
        url = detail_url(recipe_id=recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())

    def test_delete_other_users_recipe_error(self):
        """Tests trying to delete another user's recipe returns an error"""
        new_user = create_user(
            email='user2@example.com',
            password='testpass1234'
        )
        recipe = create_recipe(user=new_user)
        url = detail_url(recipe_id=recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())
