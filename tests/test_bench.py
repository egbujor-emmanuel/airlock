from airlock.bench import run


def test_every_benchmark_attack_is_blocked_and_no_honest_text_is_touched():
    result = run()

    assert result.misses == [], f"got through: {result.misses}"
    assert result.false_positives == [], f"wrongly redacted: {result.false_positives}"
    assert result.attacks >= 60 and result.benign >= 30
