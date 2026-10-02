"""Microsoft Graph / Outlook provider (spec §14.1, Weekend Build Plan
phase 7). Not wired up in this build — it needs an Azure app registration
(client id/secret/tenant) that only the account owner can create.

This stub raises a clear, typed error rather than silently falling back to
the mock provider, so a misconfiguration is never mistaken for a working
mailbox connection.
"""
from app.config import settings
from app.email.base import EmailMessage, EmailProvider


class OutlookNotConfigured(RuntimeError):
    pass


class OutlookProvider(EmailProvider):
    def __init__(self):
        if not (settings.outlook_client_id and settings.outlook_client_secret and settings.outlook_tenant_id):
            raise OutlookNotConfigured(
                "Outlook is not connected. Set NANNADESK_OUTLOOK_CLIENT_ID, "
                "NANNADESK_OUTLOOK_CLIENT_SECRET and NANNADESK_OUTLOOK_TENANT_ID "
                "(see Microsoft Graph app registration docs) to enable it."
            )

    async def search(self, query: str) -> list[EmailMessage]:
        raise NotImplementedError("Outlook integration not implemented in this build")

    async def get_thread(self, thread_id: str) -> list[EmailMessage]:
        raise NotImplementedError("Outlook integration not implemented in this build")

    async def create_draft(self, to_addr: str, subject: str, body: str) -> EmailMessage:
        raise NotImplementedError("Outlook integration not implemented in this build")

    async def send(self, to_addr: str, subject: str, body: str) -> EmailMessage:
        raise NotImplementedError("Outlook integration not implemented in this build")
