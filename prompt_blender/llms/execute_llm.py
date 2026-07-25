import json
import os
import time
import importlib.util
import copy
import traceback
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

from colorama import Fore, Style
from prompt_blender import info
from prompt_blender.analysis import gpt_json
from prompt_blender.modules_loader import load_modules_generic
from prompt_blender.llms.common.stats import ExecutionStats

def validate_llm_module(module):
    """Validate LLM module and return the module if valid."""
    if hasattr(module, 'module'):
        # Forward compatibility with future refactor where each module should have a 'module' object that contains the actual implementation.
        module.exec_init = module.module.exec_init
        module.exec = module.module.exec
        module.exec_delayed = module.module.exec_delayed if hasattr(module.module, 'exec_delayed') else None
        module.exec_close = module.module.exec_close
        module.get_args = module.module.get_args
        module.ConfigPanel = module.module.ConfigPanel

        # Allow module_info to live inside the module object instead of at module level
        if not hasattr(module, 'module_info') and hasattr(module.module, 'module_info') and module.module.module_info is not None:
            module.module_info = module.module.module_info
    else:
        if not hasattr(module, 'exec'):
            raise ValueError("Missing exec method")

    if not 'version' in module.module_info:
        module.module_info['version'] = ''

    module_id = module.module_info.get('id', None)
    if not module_id:
        raise ValueError("Missing module id")
    
    return module

def load_modules(paths):
    """
    Load all available LLM modules.
    """
    modules = load_modules_generic(paths, "LLM", validate_llm_module, "module_info", __file__)
    # Convert from name-based keys to id-based keys
    return {module.module_info['id']: module for module in modules.values()}


def expire_cache(run_args, config, cache_dir, cache_timeout=None, progress_callback=None, combinations=None, error_items_only=False):
    """
    Expire the cache for the given run arguments and configuration.
    
    Args:
        run_args (dict): The run arguments containing the LLM module and other parameters.
        config (ConfigModel): The configuration model containing parameter combinations.
        cache_dir (str): The directory where cache output files are stored.
        cache_timeout (int, optional): The cache timeout in seconds. Defaults to None, meaning no expiration.

    Returns:
        None
    """

    if progress_callback:
        progress_callback(0, 0, description="Loading LLM module...")

    def callback(i, num_combinations):
        if progress_callback:
            description = "Expiring cache..." if i < num_combinations else "Finishing up..."
            return progress_callback(i, num_combinations, description=description)
        else:
            return True

    if combinations is None:
        combinations = config.get_parameter_combinations(callback)

    expired_count = 0
    for argument_combination in combinations:
        result_file = os.path.join(cache_dir, argument_combination.get_result_file(run_args['run_hash']))
        delayed_file = result_file + '.delayed'

        if error_items_only and not is_result_with_error(result_file):
            continue

        #print("EXPIRING", result_file)
        expire_file(cache_timeout, result_file)
        expire_file(cache_timeout, delayed_file)
        expired_count += 1

    if progress_callback:
        progress_callback(0, 0, description="Finishing up...")

    return expired_count

def is_result_with_error(result_file):
    if os.path.exists(result_file):
        with open(result_file, 'r', encoding='utf-8') as file:
            output = json.load(file)
        analysis_results = gpt_json.analyse(output['response'], output['timestamp'])
        
        for r in analysis_results:
            if r.get('_error', None):
                print(r)
                return True
    return False

def expire_file(cache_timeout, file):
    if os.path.exists(file):
        print(file)
        cache_age = time.time() - os.path.getmtime(file)
        if cache_age >= cache_timeout:
            print(f'Expiring cache for {file}')
            os.remove(file)


def execute_llm(run_args, config, cache_dir, cache_timeout=None, progress_callback=None, max_cost=0, gui=False, num_workers=1):
    """
    Executes the LLM (Language Model) with the given arguments and output files.

    Args:
        num_workers (int): Number of combinations to process in parallel within
            this run/model. 1 (default) runs sequentially.
    """
    
    module_args = run_args.get('args', {})
    print('Running module:', run_args['module_name'], 'with args:', module_args)
    print(f'Run Hash: {run_args["run_hash"]}')

    if progress_callback:
        progress_callback(0, 0, description="Loading LLM module...")

    time.sleep(0.75)  # This allows the animation to be shown in the GUI for executions that are too fast (e.g. full cache hits)

    llm_module = run_args['llm_module']

    total_cost = 0

    # Sleep budget spread across all combinations so the GUI animation is visible
    # even for runs that are fully cached (same formula, shared by both paths).
    sleep_time = min(max(2 / config.get_num_combinations(), 0.0001), 0.01)

    # ── Single progress-reporting helper (used by both sequential and parallel) ──

    def build_description(completed, total):
        if completed >= total:
            return 'Finishing up...'
        desc = (f"Execution Cost: ${total_cost:.2f}/{max_cost:.2f}"
                if max_cost else f"Execution Cost: ${total_cost:.2f}")
        if max_cost:
            if total_cost >= max_cost:
                desc += "❌ (over budget)"
            elif total_cost > max_cost * 0.90:
                desc += "⚠️"
        return desc

    def report_progress(completed, total):
        """Update the progress bar and return keep_running.
        Raises RuntimeError when the cost budget is exceeded (always, even
        when there is no progress_callback)."""
        if max_cost and total_cost >= max_cost:
            print("Execution cost exceeded the budget. Stopping execution.")
            raise RuntimeError(
                f"Execution cost exceeded the budget: ${total_cost:.2f} > ${max_cost:.2f}")
        if not progress_callback:
            return True
        keep_running = progress_callback(completed, total,
                                         description=build_description(completed, total))
        return keep_running

    # ── Shared state ──

    # latest timestamp across all processed combinations
    max_timestamp = ''
    module_initialized = False
    stats = ExecutionStats()

    init_lock = threading.Lock()   # guards lazy exec_init
    state_lock = threading.Lock()  # guards max_timestamp / total_cost / stats

    def get_result_key(argument_combination):
        return argument_combination.get_result_file(run_args['run_hash'])

    def ensure_module_initialized():
        nonlocal module_initialized
        with init_lock:
            if not module_initialized:
                llm_module.exec_init(gui=gui)
                module_initialized = True

    def process_combination(argument_combination):
        """Resolve a single combination (cache hit or LLM call).

        Parallel scheduling guarantees there is never more than one in-flight
        worker for the same result key.
        """
        output = get_cached_response(run_args, cache_dir, cache_timeout, argument_combination)
        cached = output is not None
        if not cached:
            ensure_module_initialized()
            output = _execute_inner(run_args, cache_dir, argument_combination)
        time.sleep(sleep_time)
        return output, cached

    def record_output(output, cached):
        nonlocal max_timestamp, total_cost
        with state_lock:
            if cached:
                stats.cached += 1
            elif output is not None:
                stats.executed += 1
            if output:
                max_timestamp = max(max_timestamp, output['timestamp'])
                total_cost += output['cost'] if output.get('cost', None) is not None else 0

    def run_parallel():
        total = config.get_num_combinations()
        combo_iter = iter(config.get_parameter_combinations())
        completed = 0

        if not report_progress(0, total):
            return

        executor = ThreadPoolExecutor(max_workers=num_workers)
        pending_futures = {}
        in_flight_keys = set()
        queued_by_key = {}
        source_exhausted = False

        def submit_combo(argument_combination):
            key = get_result_key(argument_combination)
            future = executor.submit(process_combination, argument_combination)
            pending_futures[future] = key
            in_flight_keys.add(key)

        def enqueue_or_submit(argument_combination):
            key = get_result_key(argument_combination)
            if key in in_flight_keys:
                q = queued_by_key.get(key)
                if q is None:
                    q = deque()
                    queued_by_key[key] = q
                q.append(argument_combination)
            else:
                submit_combo(argument_combination)

        def fill_available_slots():
            nonlocal source_exhausted
            while len(pending_futures) < num_workers and not source_exhausted:
                combo = next(combo_iter, None)
                if combo is None:
                    source_exhausted = True
                    break
                enqueue_or_submit(combo)

        try:
            fill_available_slots()

            while pending_futures:
                done, _ = wait(list(pending_futures.keys()), return_when=FIRST_COMPLETED)

                for fut in done:
                    key = pending_futures.pop(fut)
                    in_flight_keys.discard(key)
                    output, cached = fut.result()  # re-raises any worker exception
                    record_output(output, cached)
                    completed += 1

                    # Release one queued sibling for this key, if any.
                    key_queue = queued_by_key.get(key)
                    if key_queue:
                        next_combo = key_queue.popleft()
                        if not key_queue:
                            queued_by_key.pop(key, None)
                        submit_combo(next_combo)

                if not report_progress(completed, total):
                    break

                fill_available_slots()
        finally:
            # Cancel queued (not-yet-started) tasks and wait for running ones.
            for fut in pending_futures:
                fut.cancel()
            executor.shutdown(wait=True)

    try:
        if llm_module.module_info.get('thread_safe', False) and num_workers > 1:
            run_parallel()
        else:
            for argument_combination in config.get_parameter_combinations(report_progress):
                output, cached = process_combination(argument_combination)
                record_output(output, cached)

        if progress_callback:
            r = progress_callback(0, 0, description="Processing delayed executions...")
            if not r:
                return max_timestamp, stats

        pending = _execute_delayed(run_args, config, cache_dir, llm_module, module_initialized, gui)
        print(pending)
        stats.pending = pending or 0

        if pending:
            raise RuntimeError(f"There {('is', 'are')[pending>1]} {pending} pending results in asynchronous execution. Please, run again later to get the final results.")

        if progress_callback:
            progress_callback(0, 0, description="Finishing up...")
    finally:
        if module_initialized:
            llm_module.exec_close()

    return max_timestamp, stats


def get_cached_response(run, cache_dir, cache_timeout, argument_combination):
    """
    Retrieves cached responses for the given run arguments and configuration.
    """
    run_hash = run['run_hash']

    #module_args = dict(run['args']) # Make a copy of the module arguments to avoid modifying the original

    prompt_file = os.path.join(cache_dir, argument_combination.prompt_file)
    result_file = os.path.join(cache_dir, argument_combination.get_result_file(run_hash))
    delayed_file = result_file + '.delayed'

    if os.path.exists(delayed_file):
        return None

    with open(prompt_file, 'r', encoding='utf-8') as file:
        prompt_content = file.read()

    if cache_timeout is None:
        cache_timeout = float('inf')

    if os.path.exists(result_file):
        cache_age = time.time() - os.path.getmtime(result_file)

        if cache_age < cache_timeout:
            # Read the result file
            try:
                with open(result_file, 'r', encoding='utf-8') as file:
                    output = json.load(file)

                # Check if the prompt file is the same
                if output['prompt'] != prompt_content:
                    print(f'{prompt_file}: prompt file has changed')
                else:
                    return output                    
            except json.JSONDecodeError:
                print(f'{result_file}: cache file is corrupted. Deleting it.')
                os.remove(result_file)
            except Exception:
                print(f'{result_file}: cache file is corrupted.')
                raise

    return None



def _atomic_write_json(path, data):
    """Write JSON to ``path`` atomically.

    The data is first written to a per-thread temporary file and then moved
    into place with ``os.replace`` (atomic on the same filesystem). This avoids
    readers ever seeing a partially written file when combinations are executed
    in parallel.
    """
    tmp_path = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp_path, 'w', encoding='utf-8') as file:
        json.dump(data, file)
    os.replace(tmp_path, path)


def _execute_inner(run, cache_dir, argument_combination):
    llm_module = run['llm_module']
    run_hash = run['run_hash']

    #module_args = dict(run['args']) # Make a copy of the module arguments to avoid modifying the original

    prompt_file = os.path.join(cache_dir, argument_combination.prompt_file)
    result_file = os.path.join(cache_dir, argument_combination.get_result_file(run_hash))
    delayed_file = result_file + '.delayed'

    if os.path.exists(delayed_file):
        return None

    with open(prompt_file, 'r', encoding='utf-8') as file:
        prompt_content = file.read()

    # Remove sensitive arguments from the output
    module_args_public = {k: v for k, v in run['args'].items() if not k.startswith('_')}  # FIXME duplicated code

    #timestamp = pd.Timestamp.now().strftime("%Y%m%d%H%M%S")
    # UTC timestamp
    timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())

    print(f'{prompt_file}: processing')
    t0 = time.time()
    
    args = copy.deepcopy(run['args'])  # creating an deepcopy to avoid the llm_module modifying the original arguments
    response = llm_module.exec(prompt_content, **args)

    output = {
            'params': argument_combination._prompt_arguments_masked,
            'prompt': prompt_content,
            'module_name': llm_module.__name__,
            'module_version': llm_module.module_info.get('version', ''),
            'module_args': module_args_public,
            'timestamp': timestamp,
            'app_name': info.APP_NAME,
            'app_version': info.__version__,
        }

    if 'delayed' in response:
        output['delayed'] = response['delayed']
        _atomic_write_json(delayed_file, output)

        return None
    
    t1 = time.time()

    output['response'] = response['response']
    output['cost'] = response.get('cost', 0)
    output['elapsed_time'] = t1 - t0

    _atomic_write_json(result_file, output)

    return output


def _execute_delayed(run_args, config, cache_dir, llm_module, initialized, gui):
    if 'exec_delayed' not in dir(llm_module):
        # If the module does not support delayed execution, return immediately
        return None
    
    old_delayed_data = {}
    delayed_params = {}
    for argument_combination in config.get_parameter_combinations():
        result_file = os.path.join(cache_dir, argument_combination.get_result_file(run_args['run_hash']))
        delayed_file = result_file + '.delayed'
        if os.path.exists(delayed_file):
            with open(delayed_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
                old_delayed_data[argument_combination.prompt_hash] = data
                delayed_params[argument_combination.prompt_hash] = data['delayed']

    if not delayed_params:
        return 0

    if not initialized:
        llm_module.exec_init(gui=gui)
        # FIXME: initialized stays False here - it's a local variable
        # The actual initialization happens lazily in exec_delayed

    new_delayed_data = llm_module.exec_delayed(delayed_params)

    pending = 0
    for argument_combination in config.get_parameter_combinations():
        result_file = os.path.join(cache_dir, argument_combination.get_result_file(run_args['run_hash']))
        delayed_file = result_file + '.delayed'
        if os.path.exists(delayed_file):

            new_info = new_delayed_data.get(argument_combination.prompt_hash, None)


            if new_info is None:
                pending += 1
            elif 'delayed' in new_info:
                pending += 1

                # Save delayed data to file
                with open(delayed_file, 'w', encoding='utf-8') as file:
                    # Update the old delayed data with the new information - only the 'delayed' key. We keep the rest of the data intact
                    old_info = old_delayed_data.get(argument_combination.prompt_hash, {})
                    old_info['delayed'] = new_info['delayed']
                    json.dump(old_info, file)
                print("New delayed data saved to file:", delayed_file)
            else:
                # If the delayed data is not present, we can remove the file
                if os.path.exists(delayed_file):
                    os.remove(delayed_file)

                # Save the new data to the result file
                with open(result_file, 'w', encoding='utf-8') as file:
                    old_info = old_delayed_data.get(argument_combination.prompt_hash, {})
                    new_info = {**old_info, **new_info}
                    json.dump(new_info, file)

    return pending