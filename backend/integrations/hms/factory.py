from backend.config import settings
from backend.integrations.hms.client import HMSClient
from backend.integrations.hms.mock_client import MockHMSClient

def get_hms_client() -> MockHMSClient | HMSClient:
    """
    Factory helper untuk mengembalikan client HMS yang sesuai dengan konfigurasi env.
    
    Returns:
        MockHMSClient | HMSClient: Objek integrasi HMS terkonfigurasi.
    """
    if settings.use_mock_hms:
        return MockHMSClient()
    return HMSClient()

# Type alias untuk mempermudah penulisan static typing di modul lain
HMSClientType = MockHMSClient | HMSClient
