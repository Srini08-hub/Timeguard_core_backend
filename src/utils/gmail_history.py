from src.core.services.gmail_service import GmailService

gmail = GmailService()

profile = gmail.get_profile()

print(profile)
