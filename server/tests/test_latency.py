"""Latency budget tests (doc/03 §13).

A synthetic ~64 KB file must analyze (diagnostics) with p95 < 100 ms and answer
a hover with p95 < 50 ms on CI-class hardware.
"""

from __future__ import annotations

import statistics
import time

import pytest
from helixlang_lsp.analysis import analyze
from helixlang_lsp.features.hover import hover

DIAGNOSTIC_P95_MS = 100
HOVER_P95_MS = 50
SAMPLES = 7


@pytest.fixture(autouse=True)
def _skip_under_coverage(pytestconfig):
    """Latency budgets are only meaningful on un-instrumented runs.

    pytest-cov's trace hook inflates per-call timings by a large constant
    factor, so these tests would be flaky inside the coverage-gated CI step.
    CI measures budgets separately in a plain (non-``--cov``) run.
    """
    if pytestconfig.getoption("cov_source"):
        pytest.skip("latency budgets are measured on un-instrumented runs")


def _big_file() -> str:
    codons = "GCT GCA GGT GCC TTG CGT "
    line = "ATG " + codons * 8 + "TAA\n"
    body = "#gene name=g\n" + line * 320 + "#end\n"
    assert len(body) > 60_000, f"built file only {len(body)} bytes"
    return body


def test_analyze_latency():
    text = _big_file()
    times: list[float] = []
    for _ in range(SAMPLES):
        t0 = time.perf_counter()
        ana = analyze(text, uri="file:///big.helix")
        times.append((time.perf_counter() - t0) * 1000)
    p95 = statistics.quantiles(times, n=20)[18]
    assert ana.diagnostics == []
    assert p95 < DIAGNOSTIC_P95_MS, f"diagnostics p95={p95:.1f}ms"


def test_hover_latency():
    text = _big_file()
    ana = analyze(text, uri="file:///big.helix")
    times: list[float] = []
    for _ in range(SAMPLES):
        t0 = time.perf_counter()
        hover(text, ana, {"position": {"line": 3, "character": 4}})
        times.append((time.perf_counter() - t0) * 1000)
    p95 = statistics.quantiles(times, n=20)[18]
    assert p95 < HOVER_P95_MS, f"hover p95={p95:.1f}ms"
