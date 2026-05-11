"""Almacenamiento local de archivos CSV.

Implementa el puerto :class:`domain.ports.FileStorage` usando el
sistema de archivos local y ``csv.DictReader`` para lectura por chunks.
"""

from __future__ import annotations

import csv
import os
from collections.abc import Iterable
from typing import IO

from domain.ports import FileStorage
from infrastructure.config.settings import settings


def _apply_header_mapping(
    row: dict[str, str], mapping: dict[str, str] | None
) -> dict[str, str]:
    """Renombra las claves de un dict según un mapping.

    Las claves que no están en el mapping se mantienen tal cual.
    """
    if mapping is None:
        return row
    return {mapping.get(k, k): v for k, v in row.items()}


class LocalFileStorage(FileStorage):
    """Guarda archivos en disco y los lee por chunks de filas."""

    def __init__(self, base_dir: str | None = None) -> None:
        self._base_dir = base_dir or settings.UPLOAD_BASE_DIR
        os.makedirs(self._base_dir, exist_ok=True)

    def save(self, filename: str, content: bytes) -> str:
        """Guarda contenido en disco y retorna el path absoluto."""
        path = os.path.join(self._base_dir, filename)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def read_chunks(
        self,
        path: str,
        chunk_size: int,
        header_mapping: dict[str, str] | None = None,
    ) -> Iterable[list[dict[str, str]]]:
        """Lee un CSV por chunks de ``chunk_size`` filas.

        Cada chunk es una lista de diccionarios ``{columna: valor}``.
        Si se provee ``header_mapping``, renombra las claves antes
        de entregarlas.
        """
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            chunk: list[dict[str, str]] = []
            for row in reader:
                chunk.append(_apply_header_mapping(dict(row), header_mapping))
                if len(chunk) == chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk

    def read_chunk(
        self,
        path: str,
        chunk_size: int,
        offset: int,
        header_mapping: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Lee un chunk específico saltando ``offset`` filas.

        Método de conveniencia (no forma parte del protocolo
        :class:`domain.ports.FileStorage`) para lectura eficiente de
        un único chunk sin recorrer todo el archivo.
        """
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for _ in range(offset):
                next(reader, None)
            chunk: list[dict[str, str]] = []
            for row in reader:
                chunk.append(_apply_header_mapping(dict(row), header_mapping))
                if len(chunk) == chunk_size:
                    break
            return chunk

    def delete(self, path: str) -> None:
        """Elimina el archivo si existe."""
        if os.path.exists(path):
            os.remove(path)
