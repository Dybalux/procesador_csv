"""Tests unitarios de reglas de validación Strategy.

No dependen de infraestructura externa.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from domain.validation_rules import DateRule, EmailRule, UrlRule


class TestEmailRule:
    def test_valid_email(self) -> None:
        rule = EmailRule()
        assert rule.validate({"email": "user@example.com"}) is None

    def test_valid_email_with_plus(self) -> None:
        rule = EmailRule()
        assert rule.validate({"email": "user.name+tag@example.co.uk"}) is None

    def test_missing_email(self) -> None:
        rule = EmailRule()
        assert rule.validate({"website": "https://example.com"}) == "Missing email field"

    def test_empty_email(self) -> None:
        rule = EmailRule()
        assert rule.validate({"email": ""}) == "Missing email field"

    @pytest.mark.parametrize(
        "raw",
        [
            "not-an-email",
            "@example.com",
            "user@",
            "user@.com",
        ],
    )
    def test_invalid_email_returns_reason(self, raw: str) -> None:
        rule = EmailRule()
        result = rule.validate({"email": raw})
        assert result is not None
        assert "Invalid email format" in result


class TestUrlRule:
    def test_valid_http_url(self) -> None:
        rule = UrlRule()
        assert rule.validate({"website": "http://example.com"}) is None

    def test_valid_https_url_with_path(self) -> None:
        rule = UrlRule()
        assert rule.validate({"website": "https://example.com/path/to/resource"}) is None

    def test_valid_url_with_port(self) -> None:
        rule = UrlRule()
        assert rule.validate({"website": "http://localhost:8080/api"}) is None

    def test_missing_website(self) -> None:
        rule = UrlRule()
        assert rule.validate({"email": "user@example.com"}) == "Missing website field"

    def test_empty_website(self) -> None:
        rule = UrlRule()
        assert rule.validate({"website": ""}) == "Missing website field"

    @pytest.mark.parametrize(
        "raw",
        [
            "example.com",
            "ftp://example.com",
            "/local/path",
            "http://",
        ],
    )
    def test_invalid_url_returns_reason(self, raw: str) -> None:
        rule = UrlRule()
        result = rule.validate({"website": raw})
        assert result is not None
        assert "Invalid URL format" in result


class TestDateRule:
    def test_valid_past_date(self) -> None:
        rule = DateRule()
        past = (date.today() - timedelta(days=1)).isoformat()
        assert rule.validate({"subscription_date": past}) is None

    def test_valid_today(self) -> None:
        rule = DateRule()
        today = date.today().isoformat()
        assert rule.validate({"subscription_date": today}) is None

    def test_missing_date(self) -> None:
        rule = DateRule()
        assert rule.validate({"email": "user@example.com"}) == "Missing subscription_date field"

    def test_empty_date(self) -> None:
        rule = DateRule()
        assert rule.validate({"subscription_date": ""}) == "Missing subscription_date field"

    def test_invalid_format(self) -> None:
        rule = DateRule()
        result = rule.validate({"subscription_date": "15/01/2023"})
        assert result is not None
        assert "Invalid date format" in result

    def test_future_date(self) -> None:
        rule = DateRule()
        future = (date.today() + timedelta(days=1)).isoformat()
        result = rule.validate({"subscription_date": future})
        assert result is not None
        assert "future" in result.lower()
