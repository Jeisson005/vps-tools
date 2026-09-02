from typing import Dict, Type
from .base import BaseMcpService
from .passbolt import PassboltService
from .google import GoogleService
from .microsoft import MicrosoftService
from .telegram import TelegramService
from .whatsapp import WhatsAppService
from .ai import AiService

AVAILABLE_SERVICES: Dict[str, Type[BaseMcpService]] = {
    "passbolt": PassboltService,
    "google": GoogleService,
    "microsoft": MicrosoftService,
    "telegram": TelegramService,
    "whatsapp": WhatsAppService,
    "ai": AiService,
}
