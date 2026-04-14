from odoo.tests import TransactionCase


class TestAddonSuccess(TransactionCase):
    def test_trivially_passes(self):
        """Smoke test — always passes to validate the happy path."""
        self.assertTrue(True)
