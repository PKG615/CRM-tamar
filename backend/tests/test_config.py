import pytest

from app.core.config import Settings


def make(**kw):
    return Settings(_env_file=None, **kw)


def test_production_refuses_default_or_short_secret():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        make(ENVIRONMENT="production")
    with pytest.raises(ValueError, match="SECRET_KEY"):
        make(ENVIRONMENT="Production", SECRET_KEY="too-short")


def test_production_accepts_a_real_secret_and_dev_is_unrestricted():
    assert make(ENVIRONMENT="production", SECRET_KEY="a" * 32).ENVIRONMENT == "production"
    assert make().ENVIRONMENT == "development"          # default secret is fine locally
