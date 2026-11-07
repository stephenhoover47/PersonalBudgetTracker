"""Expose only the authenticated household app. Legacy routers are not mounted."""

import logging
from household.api import create_app

logging.basicConfig(level=logging.INFO)
app = create_app()
