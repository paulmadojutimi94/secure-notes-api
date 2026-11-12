"""Notes CRUD. Every query is scoped to the caller: there is no way to name someone else's note."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import CurrentUser, DbSession
from ..models import Note, User
from ..schemas import NoteCreate, NoteOut, NoteUpdate

router = APIRouter(prefix="/notes", tags=["notes"])


def get_owned_note(db: Session, note_id: int, user: User) -> Note:
    # Someone else's note and a missing note both give 404, so ids can't be probed.
    note = db.scalar(select(Note).where(Note.id == note_id, Note.owner_id == user.id))
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return note


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(payload: NoteCreate, user: CurrentUser, db: DbSession) -> Note:
    note = Note(owner_id=user.id, **payload.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("", response_model=list[NoteOut])
def list_notes(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Note]:
    query = select(Note).where(Note.owner_id == user.id).order_by(Note.id).limit(limit).offset(offset)
    return list(db.scalars(query))


@router.get("/{note_id}", response_model=NoteOut)
def read_note(note_id: int, user: CurrentUser, db: DbSession) -> Note:
    return get_owned_note(db, note_id, user)


@router.patch("/{note_id}", response_model=NoteOut)
def update_note(note_id: int, payload: NoteUpdate, user: CurrentUser, db: DbSession) -> Note:
    note = get_owned_note(db, note_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(note, field, value)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, user: CurrentUser, db: DbSession) -> None:
    note = get_owned_note(db, note_id, user)
    db.delete(note)
    db.commit()
