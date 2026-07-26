from cbsc_zdc.cloud.auto_smoke import _pilot_counts_are_exact


def test_pilot_counts_require_selected_and_excluded_events_exactly():
    counts = {
        "train": 338,
        "validation": 104,
        "test": 0,
        "excluded": 764498,
    }
    assert _pilot_counts_are_exact(counts, 764940)
    assert not _pilot_counts_are_exact({**counts, "excluded": 764497}, 764940)
    assert not _pilot_counts_are_exact({**counts, "test": 1}, 764940)
