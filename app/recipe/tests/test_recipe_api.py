"""Tests for recipe APIs"""

from decimal import Decimal
import tempfile
import os

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    Recipe,
    Tag,
    Ingredient
)

from recipe.serializers import (
    RecipeSerializer,
    RecipeDetailSerializer
)

RECIPES_URL = reverse('recipe:recipe-list')


def image_upload_url(recipe_id):
    """Creates and returns an image upload URL"""
    return reverse('recipe:recipe-upload-image', args=[recipe_id])


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

    def test_create_recipe_with_new_tags(self):
        """Tests creating a recipe with new tags"""
        payload = {
            'title': "Overnight oats",
            'link': 'http://example.com/overnight-oats.pdf',
            'description': 'Oats that you leave overnight',
            'time_minutes': 5,
            'price': Decimal(4.99),
            'tags': [
                {'name': 'Dinner'},
                {'name': 'Snack'},
                {'name': 'Healthy'},
            ]
        }
        res = self.client.post(RECIPES_URL, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)

        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 3)
        for tag in payload['tags']:
            exists = recipe.tags.filter(
                name=tag['name'],
                user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_already_existing_tags(self):
        """Tests creating a crecipe with an arleady-existing tag"""
        tag_italian = Tag.objects.create(user=self.user, name='Italian')
        payload = {
            'title': "Pizza",
            'link': 'http://example.com/pizza.pdf',
            'description': 'Visuvio pizza, pizza with spicy \
                salami and fior de latte',
            'time_minutes': 30,
            'price': Decimal(4.99),
            'tags': [
                {'name': 'Junk'},
                {'name': 'Lunch'},
                {'name': 'Italian'}
            ]
        }
        res = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)

        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 3)
        self.assertIn(tag_italian, recipe.tags.all())

        for tag in payload['tags']:
            exists = recipe.tags.filter(
                name=tag['name'],
                user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_create_tag_on_updating_recipe(self):
        """Test creating a tag while updating recipe"""
        recipe = create_recipe(user=self.user)
        payload = {
            'tags': [{
                'name': 'Lunch'
            }]
        }

        url = detail_url(recipe_id=recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_tag = Tag.objects.get(user=self.user, name='Lunch')

        self.assertIn(new_tag, recipe.tags.all())

    def test_update_recipe_assign_tag(self):
        """Test assiging an exisitng tag when updating a recipe
        by replacing the old tag with a new one"""
        tag_dinner = Tag.objects.create(user=self.user, name='Dinner')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag_dinner)

        tag_lunch = Tag.objects.create(user=self.user, name='Lunch')

        payload = {
            'tags': [{
                'name': 'Lunch'
            }]
        }
        url = detail_url(recipe_id=recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(tag_lunch, recipe.tags.all())
        self.assertNotIn(tag_dinner, recipe.tags.all())

    def test_clear_recipe_tag(self):
        """Test deleing tags from a recipe"""
        tag = Tag.objects.create(user=self.user, name='Lunch')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag)

        payload = {'tags': []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(), 0)

    def test_update_ingredient_on_updating_recipe(self):
        """Test updating a recipe with an ingredient works"""
        payload = {
            'title': "Overnight oats",
            'link': 'http://example.com/overnight-oats.pdf',
            'description': 'Oats that you leave overnight',
            'time_minutes': 5,
            'price': Decimal(4.99),
            'tags': [
                {'name': 'Dinner'},
                {'name': 'Snack'},
                {'name': 'Healthy'},
            ],
            'ingredients': [
                {'name': 'Oatmeal'},
                {'name': 'Chea seeds'},
            ],
        }

        res = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)

        recipe = recipes[0]

        self.assertEqual(recipe.ingredients.count(), 2)
        for ingredient in payload['ingredients']:
            exists = recipe.ingredients.filter(
                user=self.user, name=ingredient['name']).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_already_existing_ingredients(self):
        """Test creating a recipe with an already-existsing ingredient"""
        ingredient = Ingredient.objects.create(user=self.user, name='Oatmeal')

        payload = {
            'title': "Overnight oats",
            'link': 'http://example.com/overnight-oats.pdf',
            'description': 'Oats that you leave overnight',
            'time_minutes': 5,
            'price': Decimal(4.99),
            'tags': [
                {'name': 'Dinner'},
                {'name': 'Snack'},
            ],
            'ingredients': [
                {'name': 'Oatmeal'},
                {'name': 'Chea seeds'},
            ],
        }

        res = self.client.post(RECIPES_URL, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)

        recipe = recipes[0]

        self.assertEqual(recipe.ingredients.count(), 2)
        self.assertIn(ingredient, recipe.ingredients.all())
        for ingredient in payload['ingredients']:
            exists = recipe.ingredients.filter(
                user=self.user, name=ingredient['name']).exists()
            self.assertTrue(exists)

    def test_create_ingredient_on_updating_recipe(self):
        """Test creating an ingredient while updating recipe"""
        recipe = create_recipe(user=self.user)

        payload = {
            'ingredients': [{
                'name': "Raisins"
            }]
        }
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_ingredient = Ingredient.objects.get(user=self.user, name='Raisins')

        self.assertIn(new_ingredient, recipe.ingredients.all())

    def test_update_recipe_assign_ingredient(self):
        """Test assiging an exisitng ingredient when updating a recipe
        by replacing the old ingredient with a new one"""
        ingredient1 = Ingredient.objects.create(user=self.user, name='Saffron')
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient1)
        ingredient2 = Ingredient.objects.create(user=self.user, name='Cyanide')

        payload = {
            'ingredients': [{
                'name': 'Cyanide'
            }]
        }
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(recipe.ingredients.count(), 1)
        self.assertIn(ingredient2, recipe.ingredients.all())
        self.assertNotIn(ingredient1, recipe.ingredients.all())

    def test_clear_recipe_ingredient(self):
        """Test deleting ingredients from a recipe"""
        ingredient = Ingredient.objects.create(user=self.user, name='Peas')
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient)

        payload = {
            'ingredients': []
        }
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(), 0)


class ImageUploadTests(TestCase):
    """Tests for the image upload API"""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email='user@example.com',
            password='testpass1234'
        )
        self.client.force_authenticate(self.user)
        self.recipe = create_recipe(user=self.user)

    def TearDown(self):
        return self.recipe.image.delete()

    def test_upload_valid_image(self):
        """Test uploading a valid image to a recipe"""
        url = image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix='.jpg') as image_file:
            img = Image.new('RGB', (10, 10))
            img.save(image_file, format='JPEG')
            image_file.seek(0)
            payload = {
                'image': image_file
            }
            res = self.client.post(url, payload, format='multipart')

        self.recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('image', res.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_invalid_image(self):
        """Tests uploading an invalid image returns a bad request"""
        url = image_upload_url(self.recipe.id)

        payload = {
            'image': 'img.jpeg'
        }

        res = self.client.post(url, payload, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
