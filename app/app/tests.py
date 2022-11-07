"""
Sample tests for calc.py
"""

from django.test import SimpleTestCase

from app import calc

class calcTests(SimpleTestCase):
    """Test the calc module"""

    def test_add_numbers(self):
        """test adding numbers together"""
        res = calc.add(5, 6)
        self.assertEqual(res, 11)

    def test_subtract_numbers(self):
        """test subtracting numbres together"""
        res = calc.subtract(8, 11)
        self.assertEqual(res, 3)