import pytest

from ticket_numerics.benchmark import format_report, main, run_benchmark


def test_benchmark_structure_and_agreement_check():
    rows = run_benchmark(sizes=(50, 200), repeats=2, seed=1)
    assert [(r.n, r.method) for r in rows] == [
        (50, "loop"), (50, "numpy"), (50, "numpy+convert"),
        (200, "loop"), (200, "numpy"), (200, "numpy+convert"),
    ]
    assert all(r.median_ms >= 0 and r.min_ms <= r.median_ms and r.repeats == 2 for r in rows)


def test_report_states_method_and_environment_and_makes_no_speed_claim_by_itself():
    text = format_report(run_benchmark((30,), 2, 3), 3)
    for needle in ("python ", "numpy ", "seed 3", "repeats 2", "warm-up", "perf_counter", "measurements, not guarantees"):
        assert needle in text


@pytest.mark.parametrize("kwargs", [dict(sizes=(0,)), dict(sizes=(-5,)), dict(repeats=0)])
def test_bad_benchmark_arguments(kwargs):
    with pytest.raises(ValueError):
        run_benchmark(**{"sizes": (10,), "repeats": 1, **kwargs})


def test_cli_reports_errors_with_exit_code_2(capsys):
    assert main(["--sizes", "0"]) == 2
    assert "error" in capsys.readouterr().err
    assert main(["--sizes", "20", "--repeats", "1"]) == 0
