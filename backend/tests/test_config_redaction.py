from app.services.config_redaction import (
    count_unredacted_secret_lines,
    redact_configuration,
)


def test_redacts_secrets_from_multiple_vendor_config_syntaxes():
    original = (
        "hostname edge-01\n"
        "enable secret 9 $9$hash\n"
        "username operator secret 5 salted-hash\n"
        "snmp-server community read-only RO\n"
        "set psksecret \"vpn-secret\"\n"
        "password=router-secret\n"
        "service password-encryption\n"
    )

    redacted, count = redact_configuration(original)

    assert count == 5
    assert "hash" not in redacted
    assert "salted-hash" not in redacted
    assert "read-only" not in redacted
    assert "vpn-secret" not in redacted
    assert "router-secret" not in redacted
    assert "service password-encryption" in redacted
    assert redacted.count("[REDACTED]") == 5


def test_redaction_audit_counts_without_returning_secret_values():
    raw = "tacacs-server key 0 cleartext\n"
    assert count_unredacted_secret_lines(raw) == 1
    assert count_unredacted_secret_lines(
        "tacacs-server key [REDACTED]\n"
    ) == 0
