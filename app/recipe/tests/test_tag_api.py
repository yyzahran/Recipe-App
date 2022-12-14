"""Tests for the tags APIs"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Tag, Recipe

from recipe.serializers import TagSerializer


TAGS_URL = reverse('recipe:tag-list')


def detail_url(tag_id):
    """Creates and returns a tag detail url"""
    return reverse('recipe:tag-detail', args=[tag_id])


def create_user(email='user@example.com', password='testpass1234'):
    """Create and return a test user"""
    return get_user_model().objects.create_user(email=email, password=password)


class PublicTagsApiTests(TestCase):
    """Tests unauthenticated API requests"""

    def setUp(self):
        self.client = APIClient()

    def test_auth_is_needed(self):
        """Tetss authentication is needed for retrieving tags"""
        res = self.client.get(TAGS_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateTagsApiTests(TestCase):
    """Tests authenticated reuqests"""

    def setUp(self):
        self.user = create_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_tags(self):
        """Tests retrieving a list of tags for user"""
        # creating tags for the authenticated user
        Tag.objects.create(user=self.user, name='Vegetarian')
        Tag.objects.create(user=self.user, name='Vegan')

        res = self.client.get(TAGS_URL)
        tags = Tag.objects.all().order_by('-name')
        serializer = TagSerializer(tags, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_tags_are_limited_to_user(self):
        """Tests list of tags is limited to the authenticated user"""
        # creating a user with a tag
        user2 = create_user(email='user2@example.com')
        Tag.objects.create(user=user2, name='Dessert')

        # creating a tag for the authenticated user
        tag = Tag.objects.create(user=self.user, name='Sweet')

        res = self.client.get(TAGS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], tag.name)
        self.assertEqual(res.data[0]['id'], tag.id)

    def test_update_tag(self):
        """Tests updating a tag"""
        tag = Tag.objects.create(user=self.user, name='Snack')

        payload = {
            'name': 'Banana bread'
        }
        url = detail_url(tag.id)
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        tag.refresh_from_db()
        self.assertEqual(tag.name, payload['name'])

    def test_delete_tag(self):
        """Tests deleting a tag"""
        tag = Tag.objects.create(user=self.user, name='Snack')

        url = detail_url(tag.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        tag = Tag.objects.filter(user=self.user)

        self.assertFalse(tag.exists())

    def test_filtering_on_tags_assigned_to_recipes(self):
        """Test listing only tags that are assigned to recipes"""
        tag1 = Tag.objects.create(user=self.user, name='Tag a')
        tag2 = Tag.objects.create(user=self.user, name='Tag b')
        rec1 = Recipe.objects.create(
            title='Rec 1',
            time_minutes=5,
            price=Decimal('4.50'),
            user=self.user,
        )
        rec1.tags.add(tag1)

        res = self.client.get(TAGS_URL, {'assigned_only': 1})

        s1 = TagSerializer(tag1)
        s2 = TagSerializer(tag2)

        self.assertIn(s1.data, res.data)
        self.assertNotIn(s2.data, res.data)

    def test_filtered_tags_unique(self):
        """Tests filtered tags return a unique list"""
        tag = Tag.objects.create(user=self.user, name='Vegan')
        Tag.objects.create(user=self.user, name='Vegetarian')
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
        rec1.tags.add(tag)
        rec2.tags.add(tag)

        res = self.client.get(TAGS_URL, {'assigned_only': 1})

        self.assertEqual(len(res.data), 1)
