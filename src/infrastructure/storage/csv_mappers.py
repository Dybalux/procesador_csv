"""Mappers de headers CSV para archivos con columnas no estandarizadas.

Estos diccionarios transforman los nombres de columnas del archivo CSV
al formato que espera el dominio (minúsculas, snake_case).
"""

from __future__ import annotations

CUSTOMERS_100_MAP: dict[str, str] = {
    "Email": "email",
    "Subscription Date": "subscription_date",
    "Website": "website",
}
