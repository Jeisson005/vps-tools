from typing import Dict, Type
from .base import BaseMcpService
from .passbolt import PassboltService

AVAILABLE_SERVICES: Dict[str, Type[BaseMcpService]] = {
    "passbolt": PassboltService,
}
