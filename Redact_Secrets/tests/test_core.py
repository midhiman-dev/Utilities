from redact_secrets.core import redact_high_entropy, redact_text


def test_redacts_github_token():
    token = "ghp_" + "a" * 36
    result, findings = redact_text(f"token={token}")
    assert "GitHub Token" in findings
    assert token not in result


def test_redacts_private_key_block_completely():
    source = "-----BEGIN PRIVATE KEY-----\nprivate material\n-----END PRIVATE KEY-----"
    result, findings = redact_text(source)
    assert result == "[REDACTED:Private Key Block]"
    assert findings == ["Private Key Block"]


def test_entropy_pass_keeps_uuid():
    identifier = "123e4567-e89b-12d3-a456-426614174000"
    result, findings = redact_high_entropy(identifier)
    assert result == identifier
    assert findings == []
