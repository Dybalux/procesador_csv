"""Reglas de validación Strategy para filas CSV.

Cada regla implementa el protocolo `ValidationRule` y valida un
campo específico reutilizando los value objects del dominio.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from domain.exceptions import ValidationFailed
from domain.value_objects import Email, SubscriptionDate, Url


class EmailRule:
    """Valida que el campo 'email' exista y tenga formato correcto."""

    def validate(self, row: dict[str, Any]) -> str | None:
        raw = row.get("email")
        if not raw:
            return "Missing email field"
        try:
            Email(str(raw))
        except ValidationFailed as exc:
            return str(exc)
        return None


class UrlRule:
    """Valida que el campo 'website' exista y sea una URL con scheme."""

    def validate(self, row: dict[str, Any]) -> str | None:
        raw = row.get("website")
        if not raw:
            return "Missing website field"
        try:
            Url(str(raw))
        except ValidationFailed as exc:
            return str(exc)
        return None


class DateRule:
    """Valida que el campo 'subscription_date' exista, sea parseable y no futura."""

    def validate(self, row: dict[str, Any]) -> str | None:
        raw = row.get("subscription_date")
        if not raw:
            return "Missing subscription_date field"
        try:
            parsed = date.fromisoformat(str(raw))
        except ValueError:
            return f"Invalid date format: '{raw}'"
        try:
            SubscriptionDate(parsed)
        except ValidationFailed as exc:
            return str(exc)
        return None
