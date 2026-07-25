import json
import os
import threading
import time

import pytest

from prompt_blender.model import Model
from prompt_blender.blend import blend_prompt
from prompt_blender.llms import execute_llm


class FakeModule:
    """A minimal, thread-tracking stand-in for an LLM module.

    It records how many calls run at the same time so tests can assert that
    parallel execution really overlaps, and how many times init/close run.
    """

    __name__ = "fake_module"
    module_info = {
        "id": "fake",
        "name": "Fake",
        "version": "1.0.0",
        "cache_prefix": "fake",
        "thread_safe": True,
    }

    def __init__(self, delay=0.05):
        self.delay = delay
        self._lock = threading.Lock()
        self.init_count = 0
        self.close_count = 0
        self.exec_count = 0
        self._active = 0
        self.max_concurrency = 0

    def exec_init(self, gui=False):
        with self._lock:
            self.init_count += 1

    def exec(self, prompt, **kwargs):
        with self._lock:
            self._active += 1
            self.max_concurrency = max(self.max_concurrency, self._active)
            self.exec_count += 1
        time.sleep(self.delay)
        with self._lock:
            self._active -= 1
        return {"response": f"echo:{prompt}", "cost": 0.01}

    def exec_close(self):
        with self._lock:
            self.close_count += 1


def _make_model(num_items=20):
    data = {
        "prompts": {"p": "Hello {{name}}"},
        "parameters": {"name": [{"name": f"n{i}"} for i in range(num_items)]},
        "runs": {},
    }
    return Model(data)


def _make_run_args(module):
    return {
        "llm_module": module,
        "run_hash": "testhash",
        "args": {},
        "module_name": "Fake",
    }


def _result_files(model, cache_dir, run_hash="testhash"):
    files = []
    for combo in model.get_parameter_combinations():
        files.append(os.path.join(cache_dir, combo.get_result_file(run_hash)))
    return files


def test_parallel_executes_all_combinations(tmp_path):
    model = _make_model(20)
    cache_dir = str(tmp_path)
    blend_prompt(model, cache_dir)

    module = FakeModule(delay=0.02)
    _, stats = execute_llm.execute_llm(
        _make_run_args(module), model, cache_dir, num_workers=5
    )

    assert stats.executed == 20
    assert stats.cached == 0
    assert module.exec_count == 20
    # Module must be initialized and closed exactly once, even in parallel.
    assert module.init_count == 1
    assert module.close_count == 1
    # All result files were written.
    for f in _result_files(model, cache_dir):
        assert os.path.exists(f)


def test_parallel_actually_overlaps(tmp_path):
    model = _make_model(20)
    cache_dir = str(tmp_path)
    blend_prompt(model, cache_dir)

    module = FakeModule(delay=0.05)
    execute_llm.execute_llm(
        _make_run_args(module), model, cache_dir, num_workers=5
    )

    # With 5 workers and a per-call delay, several calls must overlap.
    assert module.max_concurrency > 1


def test_sequential_does_not_overlap(tmp_path):
    model = _make_model(10)
    cache_dir = str(tmp_path)
    blend_prompt(model, cache_dir)

    module = FakeModule(delay=0.01)
    execute_llm.execute_llm(
        _make_run_args(module), model, cache_dir, num_workers=1
    )

    assert module.max_concurrency == 1
    assert module.init_count == 1
    assert module.close_count == 1


def test_parallel_and_sequential_produce_same_results(tmp_path):
    model = _make_model(15)

    seq_dir = str(tmp_path / "seq")
    par_dir = str(tmp_path / "par")
    os.makedirs(seq_dir, exist_ok=True)
    os.makedirs(par_dir, exist_ok=True)

    blend_prompt(model, seq_dir)
    blend_prompt(model, par_dir)

    execute_llm.execute_llm(_make_run_args(FakeModule()), model, seq_dir, num_workers=1)
    execute_llm.execute_llm(_make_run_args(FakeModule()), model, par_dir, num_workers=8)

    for seq_file, par_file in zip(_result_files(model, seq_dir), _result_files(model, par_dir)):
        with open(seq_file, encoding="utf-8") as f:
            seq_data = json.load(f)
        with open(par_file, encoding="utf-8") as f:
            par_data = json.load(f)
        # Ignore volatile fields.
        for key in ("timestamp", "elapsed_time"):
            seq_data.pop(key, None)
            par_data.pop(key, None)
        assert seq_data == par_data


def test_parallel_second_run_uses_cache(tmp_path):
    model = _make_model(12)
    cache_dir = str(tmp_path)
    blend_prompt(model, cache_dir)

    execute_llm.execute_llm(_make_run_args(FakeModule()), model, cache_dir, num_workers=4)

    module = FakeModule()
    _, stats = execute_llm.execute_llm(
        _make_run_args(module), model, cache_dir, num_workers=4
    )

    assert stats.cached == 12
    assert stats.executed == 0
    assert module.exec_count == 0
    # No execution happened, so the module is never initialized.
    assert module.init_count == 0


def test_parallel_cancellation_stops_early(tmp_path):
    model = _make_model(50)
    cache_dir = str(tmp_path)
    blend_prompt(model, cache_dir)

    calls = {"n": 0}
    lock = threading.Lock()

    def progress_callback(current, total, description=""):
        with lock:
            calls["n"] += 1
            # Cancel after the first progress report.
            return calls["n"] < 2

    module = FakeModule(delay=0.02)
    execute_llm.execute_llm(
        _make_run_args(module),
        model,
        cache_dir,
        num_workers=4,
        progress_callback=progress_callback,
    )

    # Execution was cancelled, so not all 50 combinations ran.
    assert module.exec_count < 50


def test_parallel_budget_raises(tmp_path):
    model = _make_model(30)
    cache_dir = str(tmp_path)
    blend_prompt(model, cache_dir)

    # Each call costs 0.01; a tiny budget must trip the guard.
    with pytest.raises(RuntimeError, match="budget"):
        execute_llm.execute_llm(
            _make_run_args(FakeModule(delay=0.005)),
            model,
            cache_dir,
            num_workers=4,
            max_cost=0.05,
        )


def test_parallel_repeated_hashes_execute_once_per_unique_result(tmp_path):
    data = {
        "prompts": {"p": "Hello {{name}}"},
        # Same value repeated -> same interpolated prompt -> same result hash.
        "parameters": {
            "name": [{"name": "dup"} for _ in range(20)] + [{"name": "unique"}]
        },
        "runs": {},
    }
    model = Model(data)
    cache_dir = str(tmp_path)
    blend_prompt(model, cache_dir)

    unique_result_files = {
        combo.get_result_file("testhash") for combo in model.get_parameter_combinations()
    }
    assert len(unique_result_files) == 2

    module = FakeModule(delay=0.02)
    _, stats = execute_llm.execute_llm(
        _make_run_args(module), model, cache_dir, num_workers=8
    )

    # Only unique prompts should trigger real executions.
    assert module.exec_count == len(unique_result_files)
    assert stats.executed == len(unique_result_files)
    assert stats.cached == model.get_num_combinations() - len(unique_result_files)
