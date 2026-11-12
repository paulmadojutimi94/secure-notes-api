"""Request and response shapes. Pydantic rejects anything that doesn't match."""

import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

Email = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=254)]
# Passwords are never stripped: "  secret  " and "secret" must stay different passwords.
Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Body = Annotated[str, StringConstraints(max_length=10_000)]


class StrictModel(BaseModel):
    """Unknown fields are an error, so clients can't sneak in e.g. owner_id."""

    model_config = ConfigDict(extra="forbid")


class UserCreate(StrictModel):
    email: Email
    password: Password

    @field_validator("email")
    @classmethod
    def email_must_look_valid(cls, value: str) -> str:
        if not EMAIL_PATTERN.match(value):
            raise ValueError("must be a valid email address")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until the token expires")


class NoteCreate(StrictModel):
    title: Title
    body: Body = ""


class NoteUpdate(StrictModel):
    title: Title | None = None
    body: Body | None = None

    @model_validator(mode="after")
    def no_null_values(self) -> "NoteUpdate":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    created_at: datetime
    updated_at: datetime
