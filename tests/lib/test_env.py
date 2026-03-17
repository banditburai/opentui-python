"""Tests for env registry — ported from lib/env.test.ts (14 tests).

Upstream: reference/opentui/packages/core/src/lib/env.test.ts
"""

from __future__ import annotations

import os

import pytest
from opentui.env import env_registry, register_env_var, env, clear_env_cache


@pytest.fixture(autouse=True)
def _clean_registry():
    """Backup/restore registry and clean TEST_ env vars between tests."""
    backup = dict(env_registry)
    clear_env_cache()
    # Remove any TEST_ env vars
    for k in list(os.environ):
        if k.startswith("TEST_"):
            del os.environ[k]
    yield
    # Restore
    for k in list(env_registry):
        if k.startswith("TEST_") and k not in backup:
            del env_registry[k]
    for k in list(os.environ):
        if k.startswith("TEST_"):
            del os.environ[k]
    clear_env_cache()


def test_register_and_access_string():
    register_env_var(
        {
            "name": "TEST_STRING",
            "description": "A test string variable",
            "type": "string",
            "default": "default_value",
        }
    )
    os.environ["TEST_STRING"] = "test_value"
    clear_env_cache()
    assert env.TEST_STRING == "test_value"


def test_boolean_true_values():
    register_env_var(
        {"name": "TEST_BOOL_TRUE", "description": "A test boolean variable", "type": "boolean"}
    )
    for val in ("true", "1", "on", "yes"):
        os.environ["TEST_BOOL_TRUE"] = val
        clear_env_cache()
        assert env.TEST_BOOL_TRUE is True, f"Expected True for {val!r}"


def test_boolean_false_values():
    register_env_var(
        {"name": "TEST_BOOL_FALSE", "description": "A test boolean variable", "type": "boolean"}
    )
    for val in ("false", "0", "off"):
        os.environ["TEST_BOOL_FALSE"] = val
        clear_env_cache()
        assert env.TEST_BOOL_FALSE is False, f"Expected False for {val!r}"


def test_number_env_var():
    register_env_var(
        {"name": "TEST_NUMBER", "description": "A test number variable", "type": "number"}
    )
    os.environ["TEST_NUMBER"] = "42"
    clear_env_cache()
    assert env.TEST_NUMBER == 42


def test_invalid_number_throws():
    register_env_var(
        {"name": "TEST_INVALID_NUMBER", "description": "A test number variable", "type": "number"}
    )
    os.environ["TEST_INVALID_NUMBER"] = "not_a_number"
    clear_env_cache()
    with pytest.raises((ValueError, RuntimeError), match="must be a valid number"):
        _ = env.TEST_INVALID_NUMBER


def test_default_values():
    register_env_var(
        {
            "name": "TEST_DEFAULT",
            "description": "A test variable with default",
            "type": "string",
            "default": "default_value",
        }
    )
    assert env.TEST_DEFAULT == "default_value"


def test_required_throws():
    register_env_var({"name": "TEST_REQUIRED", "description": "A required test variable"})
    with pytest.raises(
        RuntimeError, match="Required environment variable TEST_REQUIRED is not set"
    ):
        _ = env.TEST_REQUIRED


def test_unregistered_throws():
    with pytest.raises(
        RuntimeError, match="Environment variable UNREGISTERED_VAR is not registered"
    ):
        _ = env.UNREGISTERED_VAR


def test_proxy_enumeration():
    register_env_var({"name": "TEST_ENUM_1", "description": "First test var", "default": "value1"})
    register_env_var({"name": "TEST_ENUM_2", "description": "Second test var", "default": "value2"})
    keys = env.keys()
    assert "TEST_ENUM_1" in keys
    assert "TEST_ENUM_2" in keys


def test_in_operator():
    register_env_var(
        {"name": "TEST_IN_OPERATOR", "description": "Test for 'in' operator", "default": "test"}
    )
    assert "TEST_IN_OPERATOR" in env
    assert "NON_EXISTENT" not in env


def test_reregister_identical():
    config = {
        "name": "TEST_IDENTICAL",
        "description": "Test for identical re-registration",
        "type": "boolean",
        "default": False,
    }
    register_env_var(config)
    register_env_var(config)  # should not raise
    assert "TEST_IDENTICAL" in env


def test_reregister_different_type():
    register_env_var(
        {"name": "TEST_DIFFERENT_TYPE", "description": "Test for different type", "type": "string"}
    )
    with pytest.raises(ValueError, match="already registered with different configuration"):
        register_env_var(
            {
                "name": "TEST_DIFFERENT_TYPE",
                "description": "Test for different type",
                "type": "boolean",
            }
        )


def test_reregister_different_default():
    register_env_var(
        {
            "name": "TEST_DIFFERENT_DEFAULT",
            "description": "Test for different default",
            "type": "string",
            "default": "first",
        }
    )
    with pytest.raises(ValueError, match="already registered with different configuration"):
        register_env_var(
            {
                "name": "TEST_DIFFERENT_DEFAULT",
                "description": "Test for different default",
                "type": "string",
                "default": "second",
            }
        )


def test_reregister_different_description():
    register_env_var(
        {"name": "TEST_DIFFERENT_DESC", "description": "First description", "type": "string"}
    )
    with pytest.raises(ValueError, match="already registered with different configuration"):
        register_env_var(
            {"name": "TEST_DIFFERENT_DESC", "description": "Second description", "type": "string"}
        )
