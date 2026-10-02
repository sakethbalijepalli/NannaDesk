from app.config import settings
from app.email.base import EmailProvider
from app.email.mock import get_mock_provider


def get_email_provider() -> EmailProvider:
    if settings.email_provider == "outlook":
        from app.email.outlook import OutlookProvider  # raises if not configured
        return OutlookProvider()
    return get_mock_provider()
