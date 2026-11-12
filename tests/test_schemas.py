"""Input validation rules, tested directly on the Pydantic models."""

import pytest
from pydantic import ValidationError

from app.schemas import NoteCreate, NoteUpdate, UserCreate


def test_email_is_trimmed_and_lowercased():
    assert UserCreate(email="  Alice@Example.COM ", password="x" * 12).email == "alice@example.com"


@pytest.mark.parametrize("email", ["not-an-email", "a@b", "a b@c.com", "@example.com", ""])
def test_bad_emails_are_rejected(email):
    with pytest.raises(ValidationError):
        UserCreate(email=email, password="x" * 12)


@pytest.mark.parametrize("password", ["short", "x" * 11, "x" * 129])
def test_password_length_is_enforced(password):
    with pytest.raises(ValidationError):
        UserCreate(email="a@example.com", password=password)


def test_password_is_not_stripped():
    assert UserCreate(email="a@example.com", password="  twelve-chars ").password == "  twelve-chars "


def test_unknown_fields_are_rejected_to_block_mass_assignment():
    with pytest.raises(ValidationError):
        NoteCreate(title="hi", owner_id=999)
    with pytest.raises(ValidationError):
        UserCreate(email="a@example.com", password="x" * 12, is_admin=True)


def test_title_is_trimmed_and_cannot_be_blank_or_huge():
    assert NoteCreate(title="  hello  ").title == "hello"
    for bad in ["", "   ", "x" * 201]:
        with pytest.raises(ValidationError):
            NoteCreate(title=bad)


def test_body_has_a_size_limit():
    with pytest.raises(ValidationError):
        NoteCreate(title="t", body="x" * 10_001)


def test_update_allows_partial_but_not_null():
    assert NoteUpdate(body="new").model_dump(exclude_unset=True) == {"body": "new"}
    with pytest.raises(ValidationError):
        NoteUpdate(title=None)
