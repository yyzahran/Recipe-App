"""Tests for the user api"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status


CREATE_USER_URL = reverse('user:create')
TOKEL_URL = reverse('user:token')
ME_URL = reverse('user:me')


def create_user(**params):
    """Create and return a new user
    params: a dict that contains parameters
    to pass to the user"""
    return get_user_model().objects.create_user(**params)


class PublicUserApiTests(TestCase):
    """Tests the public features of the user api"""

    def setUp(self):
        self.client = APIClient()

    def test_create_user_success(self):
        """Tests creating a user is successful"""
        # test payload/info to pass to the user for the test
        payload = {
            'email': 'test@example.com',
            'password': 'testpass1234',
            'name': 'John Doe',
        }

        res = self.client.post(path=CREATE_USER_URL, data=payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # retrives object from the with the email that was in the payload
        user = get_user_model().objects.get(email=payload['email'])
        self.assertTrue(user.check_password(payload['password']))
        self.assertNotIn('password', res.data)

    def test_create_user_with_email_exists_error(self):
        """Test error is returned if user with email exists"""
        # same payload as above
        payload = {
            'email': 'test@example.com',
            'password': 'testpass1234',
            'name': 'John Doe',
        }

        create_user(**payload)

        res = self.client.post(path=CREATE_USER_URL, data=payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_is_too_short(self):
        """Tests an erorr is returned if password > 5 characters"""

        payload = {
            'email': 'test@example.com',
            'password': '1234',
            'name': 'John Doe',
        }

        res = self.client.post(path=CREATE_USER_URL, data=payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        # making sure the user was not created
        user_exists = get_user_model().objects.filter(
            email=payload['email']
            ).exists()
        self.assertFalse(user_exists)

    def test_create_token_for_user(self):
        """Test generating token for valid credentials"""

        user_details = {
            'name': 'John Doe',
            'email': 'test@example.com',
            'password': 'test-user-password666',
        }

        create_user(**user_details)
        payload = {
            'email': user_details['email'],
            'password': user_details['password'],
        }

        res = self.client.post(path=TOKEL_URL, data=payload)

        self.assertIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_create_token_with_bad_credentials(self):
        """Test returns error if credentials are invalid"""

        create_user(email='test@example.com', password='validpass')
        payload = {
            'email': 'test@example.com',
            'password': 'invalidpass'
        }

        res = self.client.post(path=TOKEL_URL, data=payload)

        self.assertNotIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_token_with_no_password(self):
        """Verify returning an error when no password is sent"""

        create_user(email='test@example.com', password='iAmApassword')
        payload = {
            'email': 'test@example.com',
            'password': '',
        }

        res = self.client.post(path=TOKEL_URL, data=payload)

        self.assertNotIn('token', res.data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_user_unauthorized(self):
        """Verify authentication is required for users,
        data can't be retrieved without authentication"""
        res = self.client.get(ME_URL)

        # making an unauthenticated reuqest to the ME endpoint
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateUserApiTests(TestCase):
    """Test API requests that require authentication"""

    def setUp(self):
        self.user = create_user(
            email='test@example.com',
            password='testpass123',
            name='John Doe',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_profile_succes(self):
        """Test retrieveing prodile for loged in user"""
        res = self.client.get(ME_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {
            'email': self.user.email,
            'name': self.user.name
        })

    def test_post_me_not_allowed(self):
        """Test POST is not allowed for the ME endpoint"""
        res = self.client.post(path=ME_URL, data={})

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_update_user_profile(self):
        """Test updating the user profile for the authenticated user"""
        payload = {
            'name': 'New Name',
            'password': 'newpassword1234',
        }

        res = self.client.patch(path=ME_URL, data=payload)

        self.user.refresh_from_db()
        self.assertEqual(self.user.name, payload['name'])
        self.assertTrue(self.user.check_password(payload['password']))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
