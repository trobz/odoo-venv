from odoo.tests import TransactionCase


class TestAddonFailingTest(TransactionCase):
    def test_always_fails(self):
        """Intentionally failing test — used to verify the action catches test failures."""
        self.fail("This test is supposed to fail to validate CI error detection.")
