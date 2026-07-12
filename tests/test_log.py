from src.services.log import LogRegistry, add_application_log, log_registry


def test_log_registry_adds_new_entries_first():
    registry = LogRegistry()
    first = registry.add(level="info", source="system", message="Primeiro evento")
    second = registry.add(level="error", source="downloads", message="Segundo evento")

    entries = registry.list_logs()

    assert entries == [second, first]


def test_log_registry_clear_removes_all_entries():
    registry = LogRegistry()
    registry.add(level="warning", source="search", message="Evento")
    registry.clear()

    assert registry.list_logs() == []


def test_add_application_log_uses_shared_registry():
    log_registry.clear()

    entry = add_application_log(
        level="error",
        source="downloads",
        message="Falha de download",
        details="Detalhes",
        reference_id="download-123",
    )

    entries = log_registry.list_logs()

    assert entries[0] == entry
    assert entries[0].reference_id == "download-123"
    log_registry.clear()
