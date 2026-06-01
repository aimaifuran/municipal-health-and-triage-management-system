"""Production CSP must allow frontend CDNs used in templates."""
from django.test import SimpleTestCase

from config.settings import production as production_settings


class ProductionCspTests(SimpleTestCase):
    def test_script_src_allows_chartjs_cdn(self):
        csp = production_settings.CONTENT_SECURITY_POLICY
        self.assertIn("https://cdn.jsdelivr.net", csp)
        self.assertIn("https://unpkg.com", csp)
