"""Mappers de headers CSV para archivos con columnas no estandarizadas.

Estos diccionarios transforman los nombres de columnas del archivo CSV
al formato que espera el dominio (minúsculas, snake_case).
"""

from __future__ import annotations

# Mapping para el dataset customers-100.csv (headers con mayúsculas y espacios)
CUSTOMERS_100_MAP: dict[str, str] = {
    "Email": "email",
    "Subscription Date": "subscription_date",
    "Website": "website",
}

# Columnas requeridas por el dominio (en formato estándar)
REQUIRED_FIELDS = {"email", "website", "subscription_date"}


def detect_header_mapping(headers: list[str]) -> dict[str, str] | None:
    """Detecta automáticamente el mapping de headers basado en coincidencias.

    Si los headers ya están en el formato correcto (minúsculas, snake_case),
    retorna None (no mapping necesario).

    Si los headers usan otro formato (mayúsculas, espacios, etc.),
    intenta crear un mapping automático basado en coincidencias case-insensitive.

    Args:
        headers: Lista de nombres de columnas del CSV.

    Returns:
        Diccionario de mapping {header_original: header_estandar} o None.
    """
    # Normalizar headers: lowercase, strip, replace spaces with underscores
    normalized = {h: h.lower().strip().replace(" ", "_") for h in headers}

    # Verificar si ya están en formato correcto
    if all(norm in REQUIRED_FIELDS for norm in normalized.values() if norm in REQUIRED_FIELDS):
        # Si TODOS los required fields están presentes sin transformación
        present_required = set(normalized.values()) & REQUIRED_FIELDS
        if present_required == REQUIRED_FIELDS:
            return None  # No mapping needed

    # Intentar crear mapping automático
    mapping: dict[str, str] = {}
    for original, norm in normalized.items():
        if norm in REQUIRED_FIELDS:
            if original != norm:
                mapping[original] = norm

    return mapping if mapping else None
