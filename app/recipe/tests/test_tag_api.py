"""Tests for the tags APIs"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Tag

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
