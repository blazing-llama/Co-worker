import pytest

from src.security.guardrails import (
    CircuitBreaker,
    DestructiveCommandBlocked,
    DuplicateToolCallDetected,
    LoopLimitExceeded,
    check_command_allowed,
    sanitize_secrets,
)


class TestCircuitBreaker:
    def test_allows_calls_up_to_max_iterations(self):
        breaker = CircuitBreaker(max_iterations=5)
        for i in range(5):
            breaker.record_call("tool", f"args-{i}")
        assert breaker.iteration_count == 5

    def test_raises_on_exceeding_max_iterations(self):
        breaker = CircuitBreaker(max_iterations=5)
        for i in range(5):
            breaker.record_call("tool", f"args-{i}")
        with pytest.raises(LoopLimitExceeded):
            breaker.record_call("tool", "args-6")

    def test_raises_on_duplicate_call(self):
        breaker = CircuitBreaker(max_iterations=5)
        breaker.record_call("search", "query=foo")
        with pytest.raises(DuplicateToolCallDetected):
            breaker.record_call("search", "query=foo")

    def test_reset_clears_state(self):
        breaker = CircuitBreaker(max_iterations=2)
        breaker.record_call("tool", "a")
        breaker.record_call("tool", "b")
        breaker.reset()
        assert breaker.iteration_count == 0
        breaker.record_call("tool", "a")  # would have raised duplicate before reset


class TestDestructiveCommandInterception:
    @pytest.mark.parametrize(
        "command",
        [
            "rm -rf /",
            "rm -fr ./build",
            "sudo rm -rf /var/lib/data",
        ],
    )
    def test_blocks_rm_rf_variants(self, command):
        with pytest.raises(DestructiveCommandBlocked):
            check_command_allowed(command)

    @pytest.mark.parametrize(
        "command",
        [
            "git push --force origin feature-branch",
            "git push -f origin feature-branch",
        ],
    )
    def test_blocks_force_push(self, command):
        with pytest.raises(DestructiveCommandBlocked):
            check_command_allowed(command)

    @pytest.mark.parametrize(
        "command",
        [
            "git push origin main",
            "git push origin master",
        ],
    )
    def test_blocks_push_to_main_or_master(self, command):
        with pytest.raises(DestructiveCommandBlocked):
            check_command_allowed(command)

    def test_allows_safe_commands(self):
        check_command_allowed("git push -u origin claude/some-feature-branch")
        check_command_allowed("rm ./single_file.txt")
        check_command_allowed("pytest tests/")


class TestSecretSanitization:
    def test_redacts_openai_style_key(self):
        text = "here is my key sk-abcdefghijklmnopqrstuvwx1234"
        result = sanitize_secrets(text)
        assert "sk-abcdefghijklmnopqrstuvwx1234" not in result
        assert "[REDACTED_SECRET]" in result

    def test_redacts_github_token(self):
        text = "token: ghp_1234567890abcdefghijklmnopqrstuvwx"
        result = sanitize_secrets(text)
        assert "ghp_1234567890abcdefghijklmnopqrstuvwx" not in result

    def test_redacts_generic_key_value_secret(self):
        text = 'api_key: "abcd1234efgh5678ijkl"'
        result = sanitize_secrets(text)
        assert "abcd1234efgh5678ijkl" not in result

    def test_leaves_non_secret_text_untouched(self):
        text = "The orchestrator dispatches ProductConstraints to five agents."
        assert sanitize_secrets(text) == text
