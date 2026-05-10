"""Value objects del dominio.

Los value objects son inmutables, se comparan por valor, y encapsulan
reglas de formato/validez propias del negocio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

from domain.exceptions import ValidationFailed

# Regex simplificada de RFC 5322 (suficiente para este dominio)
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# Requiere scheme (http/https) y dominio
_URL_RE = re.compile(
    r"^https?://[a-zA-Z0-9.-]+(:[0-9]+)?(/.*)?$"
)


@dataclass(frozen=True, slots=True)
class Email:
    """Dirección de correo electrónico validada."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not _EMAIL_RE.match(self.value):
            raise ValidationFailed(f"Invalid email format: '{self.value}'")


@dataclass(frozen=True, slots=True)
class Url:
    """URL validada con scheme obligatorio."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not _URL_RE.match(self.value):
            raise ValidationFailed(f"Invalid URL format: '{self.value}'")


@dataclass(frozen=True, slots=True)
class SubscriptionDate:
    """Fecha de suscripción que no puede ser futura."""

    value: date

    def __post_init__(self) -> None:
        today = datetime.now(timezone.utc).date()
        if self.value > today:
            raise ValidationFailed(
                f"Subscription date {self.value} cannot be in the future."
            )
