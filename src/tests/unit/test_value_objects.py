"""Tests unitarios de value objects.

No dependen de ninguna infraestructura externa.
"""

from datetime import date, timedelta

import pytest

from domain.exceptions import ValidationFailed
from domain.value_objects import Email, SubscriptionDate, Url


class TestEmail:
    def test_valid_email(self) -> None:
        email = Email("user@example.com")
        assert email.value == "user@example.com"

    def test_valid_email_with_plus(self) -> None:
        email = Email("user.name+tag@example.co.uk")
        assert email.value == "user.name+tag@example.co.uk"

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "not-an-email",
            "@example.com",
            "user@",
            "user@.com",
            "user name@example.com",
        ],
    )
    def test_invalid_email_raises(self, raw: str) -> None:
        with pytest.raises(ValidationFailed):
            Email(raw)


class TestUrl:
    def test_valid_http_url(self) -> None:
        url = Url("http://example.com")
        assert url.value == "http://example.com"

    def test_valid_https_url_with_path(self) -> None:
        url = Url("https://example.com/path/to/resource")
        assert url.value == "https://example.com/path/to/resource"

    def test_valid_url_with_port(self) -> None:
        url = Url("http://localhost:8080/api")
        assert url.value == "http://localhost:8080/api"

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "example.com",
            "ftp://example.com",
            "/local/path",
            "http://",
        ],
    )
    def test_invalid_url_raises(self, raw: str) -> None:
        with pytest.raises(ValidationFailed):
            Url(raw)


class TestSubscriptionDate:
    def test_valid_past_date(self) -> None:
        past = date.today() - timedelta(days=1)
        sd = SubscriptionDate(past)
        assert sd.value == past

    def test_valid_today(self) -> None:
        today = date.today()
        sd = SubscriptionDate(today)
        assert sd.value == today

    def test_future_date_raises(self) -> None:
        future = date.today() + timedelta(days=1)
        with pytest.raises(ValidationFailed):
            SubscriptionDate(future)
