from ...config import settings
from .mock_client import MockHMSClient
from .client import HMSClient

def get_hms_client():
    """Factory function to get appropriate HMS client based on settings."""
    if settings.use_mock_hms:
        return MockHMSClient()
    return HMSClient()
