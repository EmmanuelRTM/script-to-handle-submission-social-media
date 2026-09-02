"""Settings must come exclusively from environment variables (no hardcoded secrets)."""
import pytest

from submission_workflow.config import MissingConfigError, Settings


def full_env(**overrides):
    env = {
        "GOOGLE_CLIENT_SECRETS_FILE": "/secrets/client.json",
        "GOOGLE_TOKEN_FILE": "/secrets/token.json",
        "DRIVE_FOLDER_ID": "folder123",
        "X_API_KEY": "xk",
        "X_API_SECRET": "xs",
        "X_ACCESS_TOKEN": "xt",
        "X_ACCESS_TOKEN_SECRET": "xts",
        "LINKEDIN_ACCESS_TOKEN": "li-token",
        "LINKEDIN_AUTHOR_URN": "urn:li:person:abc",
    }
    env.update(overrides)
    return env


def test_from_env_reads_all_sections():
    s = Settings.from_env(full_env())
    assert s.google.client_secrets_file == "/secrets/client.json"
    assert s.google.token_file == "/secrets/token.json"
    assert s.drive.folder_id == "folder123"
    assert s.x.api_key == "xk"
    assert s.x.access_token_secret == "xts"
    assert s.linkedin.access_token == "li-token"
    assert s.linkedin.author_urn == "urn:li:person:abc"


def test_defaults_applied():
    s = Settings.from_env(full_env())
    assert s.youtube.category_id == "27"
    assert s.youtube.publish_delay_days == 2
    assert s.x.max_post_chars == 210
    assert s.linkedin.version == "202608"


def test_overridable_defaults():
    s = Settings.from_env(full_env(
        YOUTUBE_PUBLISH_DELAY_DAYS="5",
        X_MAX_POST_CHARS="180",
        LINKEDIN_VERSION="202701",
    ))
    assert s.youtube.publish_delay_days == 5
    assert s.x.max_post_chars == 180
    assert s.linkedin.version == "202701"


def test_missing_variable_raises_with_name():
    env = full_env()
    del env["LINKEDIN_ACCESS_TOKEN"]
    with pytest.raises(MissingConfigError, match="LINKEDIN_ACCESS_TOKEN"):
        Settings.from_env(env)


def _server_env():
    return {
        "GOOGLE_CLIENT_SECRETS_FILE": "c.json", "GOOGLE_TOKEN_FILE": "t.json",
        "DRIVE_PARENT_FOLDER_ID": "parent1",
    }


def test_server_mode_accepts_parent_folder_and_optional_social():
    from submission_workflow.config import Settings
    s = Settings.from_env(_server_env(), require_social=False)
    assert s.drive.parent_folder_id == "parent1" and s.drive.folder_id == ""
    assert s.x is None and s.linkedin is None


def test_cli_mode_still_requires_folder_and_social():
    import pytest
    from submission_workflow.config import MissingConfigError, Settings
    with pytest.raises(MissingConfigError, match="DRIVE_FOLDER_ID"):
        Settings.from_env(_server_env())
