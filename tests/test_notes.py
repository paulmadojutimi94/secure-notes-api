"""Happy-path CRUD for notes."""


def test_full_crud_cycle(client, alice):
    created = client.post("/notes", json={"title": "  Groceries ", "body": "milk"}, headers=alice)
    assert created.status_code == 201
    note = created.json()
    assert note["title"] == "Groceries"

    assert client.get(f"/notes/{note['id']}", headers=alice).json()["body"] == "milk"

    updated = client.patch(f"/notes/{note['id']}", json={"body": "milk, eggs"}, headers=alice)
    assert updated.status_code == 200
    assert updated.json()["body"] == "milk, eggs" and updated.json()["title"] == "Groceries"

    assert client.delete(f"/notes/{note['id']}", headers=alice).status_code == 204
    assert client.get(f"/notes/{note['id']}", headers=alice).status_code == 404


def test_list_is_paginated(client, alice):
    for i in range(5):
        client.post("/notes", json={"title": f"n{i}"}, headers=alice)
    page = client.get("/notes?limit=2&offset=1", headers=alice).json()
    assert [n["title"] for n in page] == ["n1", "n2"]
    assert client.get("/notes?limit=0", headers=alice).status_code == 422
    assert client.get("/notes?limit=101", headers=alice).status_code == 422


def test_notes_require_login(client):
    assert client.get("/notes").status_code == 401
    assert client.post("/notes", json={"title": "x"}).status_code == 401


def test_invalid_note_input_is_422(client, alice):
    assert client.post("/notes", json={"title": ""}, headers=alice).status_code == 422
    assert client.post("/notes", json={"body": "no title"}, headers=alice).status_code == 422
