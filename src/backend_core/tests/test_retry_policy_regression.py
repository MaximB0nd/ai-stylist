"""Regression coverage for permanent database failures in delivery."""

import pytest
from sqlalchemy.exc import DataError, IntegrityError, OperationalError, ProgrammingError

from app.services.retry_policy import is_retryable_delivery_error


@pytest.mark.parametrize("error_type", [IntegrityError, ProgrammingError, DataError])
def test_permanent_database_error_does_not_retry(error_type):
    error = error_type("statement", {}, ValueError("permanent failure"))
    assert is_retryable_delivery_error(error) is False


@pytest.mark.parametrize("error_type", [IntegrityError, ProgrammingError, DataError])
def test_invalidated_connection_keeps_recovery(error_type):
    error = error_type(
        "statement", {}, ConnectionError("connection lost"), connection_invalidated=True
    )
    assert is_retryable_delivery_error(error) is True


def test_operational_connection_error_is_retryable():
    error = OperationalError("statement", {}, ConnectionError("connection lost"))
    assert is_retryable_delivery_error(error) is True
