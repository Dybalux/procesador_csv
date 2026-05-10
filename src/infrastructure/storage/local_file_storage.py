"""Almacenamiento local de archivos CSV.

Implementa el puerto :class:`domain.ports.FileStorage` usando el
sistema de archivos local y ``csv.DictReader`` para lectura por chunks.
"""

from __future__ import annotations

import csv
import os
import tempfile
from collections.abc import Iterable
from typing import IO

from domain.ports import FileStorage


class LocalFileStorage(FileStorage):
    """Guarda archivos en disco y los lee por chunks de filas."""

    def __init__(self, base_dir: str | None = None) -> None:
        self._base_dir = base_dir or os.path.join(
            tempfile.gettempdir(), "procesador_csv", "uploads"
        )
        os.makedirs(self._base_dir, exist_ok=True)

    def save(self, filename: str, content: bytes) -> str:
        """Guarda contenido en disco y retorna el path absoluto."""
        path = os.path.join(self._base_dir, filename)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def read_chunks(self, path: str, chunk_size: int) -> Iterable[list[dict[str, str]]]:
        """Lee un CSV por chunks de ``chunk_size`` filas.

        Cada chunk es una lista de diccionarios ``{columna: valor}``.
        """
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            chunk: list[dict[str, str]] = []
            for row in reader:
                chunk.append(dict(row))
                if len(chunk) == chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk

    def read_chunk(self, path: str, chunk_size: int, offset: int) -> list[dict[str, str]]:
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
                chunk.append(dict(row))
                if len(chunk) == chunk_size:
                    break
            return chunk

    def delete(self, path: str) -> None:
        """Elimina el archivo si existe."""
        if os.path.exists(path):
            os.remove(path)
