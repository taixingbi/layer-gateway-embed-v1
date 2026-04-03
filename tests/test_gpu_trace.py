import httpx
import pytest

import app.config as app_c
from app.config import configure, get_gpu_trace_header
from app.main import _gpu_trace_for_log


@pytest.fixture(autouse=True)
def reset_config():
    app_c._overrides.clear()
    configure(internal_api_key="secret")
    yield
    app_c._overrides.clear()


def test_get_gpu_trace_header_default_empty():
    assert get_gpu_trace_header() == ""


def test_get_gpu_trace_header_configure_strips():
    configure(internal_api_key="secret", gpu_trace_header="  X-GPU-Id  ")
    assert get_gpu_trace_header() == "X-GPU-Id"


def test_gpu_trace_for_log_disabled():
    h = httpx.Headers({"X-GPU-Id": "0"})
    assert _gpu_trace_for_log(h, "") is None
    assert _gpu_trace_for_log(h, "   ") is None


def test_gpu_trace_for_log_present():
    h = httpx.Headers({"X-GPU-Id": "0"})
    assert _gpu_trace_for_log(h, "X-GPU-Id") == "0"


def test_gpu_trace_for_log_missing():
    h = httpx.Headers({})
    assert _gpu_trace_for_log(h, "X-GPU-Id") == "-"


def test_gpu_trace_for_log_case_insensitive():
    h = httpx.Headers({"x-gpu-id": "2"})
    assert _gpu_trace_for_log(h, "X-GPU-Id") == "2"
