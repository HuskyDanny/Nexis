"""Tests for the domain exception hierarchy."""

import pytest

from src.core.exceptions import (
    ConfigError,
    GraphError,
    NexisError,
    PipelineError,
    ThinkingError,
)


class TestExceptionHierarchy:
    """All domain exceptions inherit from NexisError -> Exception."""

    @pytest.mark.parametrize(
        "exc_cls",
        [ThinkingError, PipelineError, GraphError, ConfigError],
        ids=lambda c: c.__name__,
    )
    def test_subclass_of_nexis_error(self, exc_cls):
        assert issubclass(exc_cls, NexisError)

    def test_nexis_error_is_exception(self):
        assert issubclass(NexisError, Exception)

    @pytest.mark.parametrize(
        "exc_cls",
        [NexisError, ThinkingError, PipelineError, GraphError, ConfigError],
        ids=lambda c: c.__name__,
    )
    def test_carries_message(self, exc_cls):
        err = exc_cls("something broke")
        assert str(err) == "something broke"

    @pytest.mark.parametrize(
        "exc_cls",
        [ThinkingError, PipelineError, GraphError, ConfigError],
        ids=lambda c: c.__name__,
    )
    def test_catchable_as_nexis_error(self, exc_cls):
        with pytest.raises(NexisError):
            raise exc_cls("test")

    def test_not_catchable_across_siblings(self):
        """ThinkingError should not be caught by except GraphError."""
        with pytest.raises(ThinkingError):
            try:
                raise ThinkingError("agent failed")
            except GraphError:
                pytest.fail("ThinkingError should not match GraphError")

    def test_chained_exception(self):
        """Domain exceptions support raise ... from ... chaining."""
        original = ValueError("bad json")
        err = ThinkingError("thinker parse failed")
        err.__cause__ = original
        assert err.__cause__ is original
