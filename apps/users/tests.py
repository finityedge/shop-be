from django.test import Client, TestCase
from django.urls import reverse
from .models import User

class UserRegistrationTestCase(TestCase):
    def test_user_registration(self):
        # Test successful user registration
        data = {
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'testpassword'
        }
        response = self.client.post(reverse('register'), data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='testuser').exists())

        # Test user registration with existing username
        data = {
            'username': 'testuser',
            'email': 'another@example.com',
            'password': 'newpassword'
        }
        response = self.client.post(reverse('register'), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email='another@example.com').exists())

        # Test user registration with invalid email
        data = {
            'username': 'anotheruser',
            'email': 'invalid_email',
            'password': 'somepassword'
        }
        response = self.client.post(reverse('register'), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username='anotheruser').exists())