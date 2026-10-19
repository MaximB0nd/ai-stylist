"""Exercise authenticated feedback without external services."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.dependencies import get_feedback_repository, get_user_repository
from app.core.security import create_access_token
from app.db.repositories.feedback_repository import FeedbackRepository
from app.main import app

VALID = {"name": "Contact name", "email": "contact@example.com", "comment": "Useful service"}


@pytest.fixture
def context():
    users = {
        user_id: SimpleNamespace(id=user_id, is_active=True)
        for user_id in (uuid.uuid4(), uuid.uuid4())
    }
    records = []

    async def create(**values):
        row = SimpleNamespace(id=uuid.uuid4(), created_at=datetime.now(timezone.utc), **values)
        records.append(row)
        return row

    repo = SimpleNamespace(create=AsyncMock(side_effect=create))
    user_repo = SimpleNamespace(get_by_id=AsyncMock(side_effect=lambda user_id: users.get(user_id)))
    app.dependency_overrides[get_feedback_repository] = lambda: repo
    app.dependency_overrides[get_user_repository] = lambda: user_repo
    yield SimpleNamespace(users=users, records=records, repo=repo)
    app.dependency_overrides.pop(get_feedback_repository, None)
    app.dependency_overrides.pop(get_user_repository, None)


@pytest.fixture
async def client(context):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


def headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(subject=user_id)}"}


async def test_feedback_created_for_authenticated_user(client, context):
    user_id = next(iter(context.users))
    response = await client.post("/api/v1/feedback", json={
        **VALID, "name": "  Иван Петров  ", "comment": "\n Спасибо! \t",
    }, headers=headers(user_id))
    assert response.status_code == 201
    assert set(response.json()) == {"id", "created_at"}
    row = context.records[0]
    assert response.json()["id"] == str(row.id)
    assert datetime.fromisoformat(response.json()["created_at"].replace("Z", "+00:00")).tzinfo
    assert (row.user_id, row.name, row.email, row.comment) == (
        user_id, "Иван Петров", VALID["email"], "Спасибо!",
    )


async def test_feedback_multiple_users_and_repeated_submissions(client, context):
    first, second = context.users
    for user_id in (first, first, second):
        response = await client.post("/api/v1/feedback", json=VALID, headers=headers(user_id))
        assert response.status_code == 201
    assert [row.user_id for row in context.records] == [first, first, second]
    assert len({row.id for row in context.records}) == 3


@pytest.mark.parametrize("field,value", [
    ("name", ""), ("name", " \t\n"), ("name", "a" * 101), ("name", 123),
    ("comment", ""), ("comment", " \t\n"), ("comment", "a" * 5001), ("comment", None),
    ("email", ""), ("email", "not-an-email"), ("email", "a@"), ("email", None),
    ("email", "a" * 64 + "@" + ".".join(["b" * 63] * 3) + ".com"),
])
async def test_feedback_invalid_input(client, context, field, value):
    response = await client.post("/api/v1/feedback", json={**VALID, field: value},
                                 headers=headers(next(iter(context.users))))
    assert response.status_code == 422
    context.repo.create.assert_not_awaited()


@pytest.mark.parametrize("field", ["name", "email", "comment"])
async def test_feedback_required_fields(client, context, field):
    payload = {key: value for key, value in VALID.items() if key != field}
    response = await client.post("/api/v1/feedback", json=payload,
                                 headers=headers(next(iter(context.users))))
    assert response.status_code == 422
    context.repo.create.assert_not_awaited()


@pytest.mark.parametrize("name,comment", [("a", "b"), ("a" * 100, "b" * 5000)])
async def test_feedback_length_boundaries(client, context, name, comment):
    response = await client.post("/api/v1/feedback", json={**VALID, "name": name, "comment": comment},
                                 headers=headers(next(iter(context.users))))
    assert response.status_code == 201
    assert (context.records[0].name, context.records[0].comment) == (name, comment)


@pytest.mark.parametrize("field", ["user_id", "created_at", "unexpected"])
async def test_feedback_rejects_extra_fields(client, context, field):
    response = await client.post("/api/v1/feedback", json={**VALID, field: str(uuid.uuid4())},
                                 headers=headers(next(iter(context.users))))
    assert response.status_code == 422
    context.repo.create.assert_not_awaited()


@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Basic invalid"])
async def test_feedback_requires_authentication(client, context, authorization):
    response = await client.post("/api/v1/feedback", json=VALID,
                                 headers={"Authorization": authorization} if authorization else {})
    assert response.status_code == 401
    context.repo.create.assert_not_awaited()


async def test_feedback_inactive_user_is_rejected(client, context):
    user_id = next(iter(context.users))
    context.users[user_id].is_active = False
    response = await client.post("/api/v1/feedback", json=VALID, headers=headers(user_id))
    assert response.status_code == 401
    context.repo.create.assert_not_awaited()


async def test_feedback_failed_save_is_not_reported_as_success(client, context):
    context.repo.create.side_effect = SQLAlchemyError("private database details")
    response = await client.post("/api/v1/feedback", json=VALID,
                                 headers=headers(next(iter(context.users))))
    assert response.status_code == 503
    assert "private" not in response.text
    assert context.records == []


async def test_feedback_preserves_plain_text(client, context):
    comment = "<script>example</script>\nO'Reilly; DROP TABLE users;"
    response = await client.post("/api/v1/feedback", json={**VALID, "comment": comment},
                                 headers=headers(next(iter(context.users))))
    assert response.status_code == 201
    assert context.records[0].comment == comment


@pytest.mark.parametrize("failed_stage", [None, "flush", "refresh", "commit"])
async def test_feedback_repository_transaction(failed_stage):
    session = SimpleNamespace(add=MagicMock(), flush=AsyncMock(), refresh=AsyncMock(),
                              commit=AsyncMock(), rollback=AsyncMock())
    if failed_stage:
        getattr(session, failed_stage).side_effect = SQLAlchemyError("write failed")
        with pytest.raises(SQLAlchemyError):
            await FeedbackRepository(session).create(user_id=uuid.uuid4(), **VALID)
        session.rollback.assert_awaited_once()
        if failed_stage != "commit":
            session.commit.assert_not_awaited()
    else:
        row = await FeedbackRepository(session).create(user_id=uuid.uuid4(), **VALID)
        session.add.assert_called_once_with(row)
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(row)
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
