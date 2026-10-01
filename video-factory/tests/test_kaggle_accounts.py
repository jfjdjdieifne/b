import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from video_factory.providers.kaggle import (
    KaggleAccount,
    KaggleAccountPool,
    KaggleProvider,
    load_kaggle_accounts,
)


CONFIG = {
    "kaggle": {
        "kernel_slug": "wan-video-worker",
        "accelerator": "NvidiaTeslaT4",
    }
}


def clear_kaggle_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("KAGGLE_"):
            monkeypatch.delenv(key, raising=False)


def test_numbered_accounts_are_loaded_in_order(monkeypatch: pytest.MonkeyPatch):
    clear_kaggle_env(monkeypatch)
    monkeypatch.setenv("KAGGLE_USERNAME_2", "second-user")
    monkeypatch.setenv("KAGGLE_API_TOKEN_2", "secret-token-2")
    monkeypatch.setenv("KAGGLE_USERNAME_1", "first-user")
    monkeypatch.setenv("KAGGLE_API_TOKEN_1", "secret-token-1")
    # Numbered slots intentionally take precedence over the legacy pair.
    monkeypatch.setenv("KAGGLE_USERNAME", "legacy-user")
    monkeypatch.setenv("KAGGLE_API_TOKEN", "legacy-secret")

    accounts = load_kaggle_accounts(CONFIG)

    assert [account.id for account in accounts] == ["account-1", "account-2"]
    assert [account.username for account in accounts] == ["first-user", "second-user"]
    assert "secret-token-1" not in repr(accounts[0])


def test_incomplete_numbered_slot_is_rejected(monkeypatch: pytest.MonkeyPatch):
    clear_kaggle_env(monkeypatch)
    monkeypatch.setenv("KAGGLE_USERNAME_1", "first-user")

    with pytest.raises(RuntimeError, match="slot 1 is incomplete"):
        load_kaggle_accounts(CONFIG)


def test_json_account_pool(monkeypatch: pytest.MonkeyPatch):
    clear_kaggle_env(monkeypatch)
    monkeypatch.setenv(
        "KAGGLE_ACCOUNTS_JSON",
        json.dumps(
            [
                {"id": "primary", "username": "user-a", "api_token": "token-a"},
                {"id": "backup", "username": "user-b", "token": "token-b"},
            ]
        ),
    )

    accounts = load_kaggle_accounts(CONFIG)

    assert [(account.id, account.username) for account in accounts] == [
        ("primary", "user-a"),
        ("backup", "user-b"),
    ]


def test_pool_round_robin_cooldown_and_no_token_leak(tmp_path: Path):
    accounts = [
        KaggleAccount("primary", "user-a", "very-secret-token-a"),
        KaggleAccount("backup", "user-b", "very-secret-token-b"),
    ]
    state_path = tmp_path / "kaggle_accounts.json"
    pool = KaggleAccountPool(accounts, state_path, cooldown_minutes=60)

    assert [account.id for account in pool.candidates()] == ["primary", "backup"]
    pool.mark_success(accounts[0])
    assert [account.id for account in pool.candidates()] == ["backup", "primary"]

    pool.mark_failure(accounts[1], "HTTP 401 unauthorized")
    assert [account.id for account in pool.candidates()] == ["primary"]
    assert pool.next_available_at(datetime.now(timezone.utc)) is not None

    state_text = state_path.read_text()
    assert "very-secret-token-a" not in state_text
    assert "very-secret-token-b" not in state_text
    assert "backup" in state_text


def test_provider_forces_selected_account_environment(monkeypatch: pytest.MonkeyPatch):
    clear_kaggle_env(monkeypatch)
    monkeypatch.setenv("KAGGLE_KEY", "old-key-that-must-not-be-used")
    provider = KaggleProvider(
        CONFIG,
        KaggleAccount("backup", "selected-user", "selected-token"),
    )

    assert provider.env["KAGGLE_USERNAME"] == "selected-user"
    assert provider.env["KAGGLE_API_TOKEN"] == "selected-token"
    assert "KAGGLE_KEY" not in provider.env
