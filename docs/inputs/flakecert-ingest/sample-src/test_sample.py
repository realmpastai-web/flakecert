import os, random, pytest
def test_pass():
    assert 1 + 1 == 2
def test_fail_deterministic():
    assert {"a": 1} == {"a": 2}
def test_flaky_seeded():
    # fails iff the seeded draw is < 0.5; SEED is set by the harness, not recorded by any reporter
    rng = random.Random(int(os.environ.get("SEED", "0")))
    assert rng.random() >= 0.5, "seeded draw below threshold"
@pytest.mark.skip(reason="sample skip")
def test_skip():
    pass
