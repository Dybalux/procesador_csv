"""Tests unitarios para LocalFileStorage."""

from __future__ import annotations

import os
import tempfile

from infrastructure.storage.local_file_storage import LocalFileStorage


class TestLocalFileStorage:
    def test_save_creates_file_and_returns_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)
            path = storage.save("test.csv", b"a,b\n1,2\n")
            assert os.path.exists(path)
            assert path.startswith(tmpdir)

    def test_read_chunks_yields_expected_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)
            content = b"name,age\nAlice,30\nBob,25\nCharlie,35\n"
            path = storage.save("people.csv", content)

            chunks = list(storage.read_chunks(path, chunk_size=2))
            assert len(chunks) == 2
            assert chunks[0] == [
                {"name": "Alice", "age": "30"},
                {"name": "Bob", "age": "25"},
            ]
            assert chunks[1] == [
                {"name": "Charlie", "age": "35"},
            ]

    def test_read_chunk_skips_offset_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)
            content = b"name,age\nAlice,30\nBob,25\nCharlie,35\n"
            path = storage.save("people.csv", content)

            chunk = storage.read_chunk(path, chunk_size=1, offset=1)
            assert chunk == [{"name": "Bob", "age": "25"}]

    def test_delete_removes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)
            path = storage.save("to_delete.csv", b"x\n")
            assert os.path.exists(path)
            storage.delete(path)
            assert not os.path.exists(path)

    def test_delete_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)
            storage.delete("/nonexistent/path.csv")
            # no raise

    def test_read_chunks_with_header_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)
            content = (
                b"Email,Subscription Date,Website\n"
                b"alice@test.com,2020-08-24,http://example.com\n"
            )
            path = storage.save("customers.csv", content)

            chunks = list(
                storage.read_chunks(
                    path,
                    chunk_size=1,
                    header_mapping={
                        "Email": "email",
                        "Subscription Date": "subscription_date",
                        "Website": "website",
                    },
                )
            )
            assert chunks[0] == [
                {
                    "email": "alice@test.com",
                    "subscription_date": "2020-08-24",
                    "website": "http://example.com",
                }
            ]

    def test_read_chunk_with_header_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(base_dir=tmpdir)
            content = b"Email,Website\nalice@test.com,http://example.com\n"
            path = storage.save("customers.csv", content)

            chunk = storage.read_chunk(
                path,
                chunk_size=1,
                offset=0,
                header_mapping={"Email": "email", "Website": "website"},
            )
            assert chunk == [
                {"email": "alice@test.com", "website": "http://example.com"}
            ]
