from typing import Dict, Type
from .base import BaseMcpService
from .passbolt import PassboltService
from .google import GoogleService
from .microsoft import MicrosoftService
from .telegram import TelegramService
from .whatsapp import WhatsAppService
from .clickup import ClickUpService
from .ai import AiService
from .notebooklm import NotebookLMService

AVAILABLE_SERVICES: Dict[str, Type[BaseMcpService]] = {
    "passbolt": PassboltService,
    "google": GoogleService,
    "microsoft": MicrosoftService,
    "telegram": TelegramService,
    "whatsapp": WhatsAppService,
    "clickup": ClickUpService,
    "ai": AiService,
    "notebooklm": NotebookLMService,
}
