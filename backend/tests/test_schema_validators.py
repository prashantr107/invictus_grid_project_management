"""Schema/validator tests (SRS §6, TRD §11): password strength, key
normalization, disjoint membership, required review feedback, and null guards.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import Role
from app.schemas import (
    PasswordChange,
    ProjectCreate,
    TaskReviewCreate,
    TaskUpdate,
    UserCreate,
    validate_strong_password,
)


@pytest.mark.parametrize(
    "password",
    [
        "alllowercase12",  # no uppercase
        "ALLUPPERCASE12",  # no lowercase
        "NoDigitsAllowed!",  # no digit
        "NoSymbols12345",  # no symbol
    ],
)
def test_validate_strong_password_rejects_weak_values(password):
    with pytest.raises(ValueError):
        validate_strong_password(password)


def test_validate_strong_password_accepts_valid_value():
    assert validate_strong_password("GoodPassw0rd!1") == "GoodPassw0rd!1"


def test_user_create_rejects_weak_password():
    with pytest.raises(ValidationError):
        UserCreate(email="u@invictusgrid.com", full_name="User", role=Role.MEMBER, initial_password="weak")


def test_user_create_rejects_blank_name():
    with pytest.raises(ValidationError):
        UserCreate(email="u@invictusgrid.com", full_name="   ", role=Role.MEMBER, initial_password="GoodPassw0rd!1")


def test_user_create_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", full_name="User", role=Role.MEMBER, initial_password="GoodPassw0rd!1")


def test_user_create_accepts_valid_payload():
    payload = UserCreate(
        email="u@invictusgrid.com", full_name=" User ", role=Role.MEMBER, initial_password="GoodPassw0rd!1"
    )
    assert payload.full_name == "User"


def test_project_create_normalizes_key():
    payload = ProjectCreate(key="  alpha ", name="Alpha", manager_ids=[uuid4()])
    assert payload.key == "ALPHA"
    assert payload.status.value == "PLANNED"


def test_project_create_rejects_malformed_key():
    with pytest.raises(ValidationError):
        ProjectCreate(key="1bad", name="Bad", manager_ids=[uuid4()])


def test_project_create_rejects_duplicate_managers():
    user_id = uuid4()
    with pytest.raises(ValidationError):
        ProjectCreate(key="DUP", name="Dup", manager_ids=[user_id, user_id])


def test_project_create_rejects_overlapping_membership():
    user_id = uuid4()
    with pytest.raises(ValidationError):
        ProjectCreate(key="OVE", name="Overlap", manager_ids=[user_id], member_ids=[user_id])


@pytest.mark.parametrize("field", ["title", "type", "priority"])
def test_task_update_rejects_explicit_null(field):
    with pytest.raises(ValidationError):
        TaskUpdate(**{field: None})


def test_task_update_accepts_empty_partial_payload():
    assert TaskUpdate().model_dump(exclude_unset=True) == {}


def test_review_requires_feedback_when_changes_requested():
    with pytest.raises(ValidationError):
        TaskReviewCreate(decision="CHANGES_REQUIRED")


def test_review_accepts_changes_requested_with_feedback():
    payload = TaskReviewCreate(decision="CHANGES_REQUIRED", feedback="Please redo")
    assert payload.feedback == "Please redo"
    assert TaskReviewCreate(decision="APPROVED").feedback is None


def test_review_rejects_unknown_decision():
    with pytest.raises(ValidationError):
        TaskReviewCreate(decision="MAYBE")


def test_password_change_rejects_weak_new_password():
    with pytest.raises(ValidationError):
        PasswordChange(current_password="GoodPassw0rd!1", new_password="weak")


def test_password_change_accepts_valid_new_password():
    payload = PasswordChange(current_password="GoodPassw0rd!1", new_password="NewPassw0rd!22")
    assert payload.new_password.get_secret_value() == "NewPassw0rd!22"
