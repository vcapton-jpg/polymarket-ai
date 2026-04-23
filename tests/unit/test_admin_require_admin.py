import pytest
from fastapi import HTTPException

from app.api.deps.admin import _parse_admin_emails, _is_admin_email


def test_parse_admin_emails_splits_and_lowercases():
    assert _parse_admin_emails("A@x.com, b@y.com,, C@z.com") == {
        "a@x.com",
        "b@y.com",
        "c@z.com",
    }


def test_parse_admin_emails_empty_string():
    assert _parse_admin_emails("") == set()


def test_is_admin_email_matches_case_insensitively():
    assert _is_admin_email("Admin@Example.com", "admin@example.com,other@x.com") is True


def test_is_admin_email_rejects_non_member():
    assert _is_admin_email("nope@x.com", "a@x.com,b@y.com") is False


def test_is_admin_email_handles_none_email():
    assert _is_admin_email(None, "a@x.com") is False
