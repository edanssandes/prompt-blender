import os
import json
import zipfile
import tempfile
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from collections import defaultdict


class Cache:
    """
    A cache system that can work with either a directory or a zipfile backend.
    Directory caches are read-write, zipfile caches are read-only.
    Supports storing prompt files, result files, and provides statistics and management operations.

    Cache Path Logic:
    - Files are stored in a hierarchical structure: cache/{prefix}/{sub_directory}/{file}
    - The {prefix} is the first 2 characters of the {sub_directory} name
    - Example: sub_directory="cdef", file="result_abc123.json" 
               -> stored as: cache/cd/cdef/result_abc123.json
    - This prevents too many files in a single directory and improves filesystem performance
    """

    CACHE_DIR = Path("cache")

    def __init__(self, path: Union[str, Path], mode: str = 'r', encoding: str = 'utf-8'):
        """
        Initialize a Cache instance.

        Args:
            path: Path to the cache directory or zipfile
            mode: Mode for operations ('r' for read, 'w' for write, 'a' for append)
                  Note: zipfile caches only support 'r' mode (read-only)
            encoding: Default encoding to use for text files
        """
        self.path = Path(path)
        self.is_zip = self.path.suffix.lower() == '.zip'
        self.mode = mode
        self.encoding = encoding
        self._zip_file = None

        if self.is_zip:
            if mode != 'r':
                raise ValueError("Zipfile caches are read-only. Use mode='r' only.")
            self._zip_file = zipfile.ZipFile(self.path, 'r')
        else:
            # For directory backend, ensure the directory exists
            self.path.mkdir(parents=True, exist_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the cache and clean up resources."""
        if self._zip_file:
            self._zip_file.close()
            self._zip_file = None

    def _get_real_path(self, cache_path: str) -> Path:
        """
        Get the real filesystem path for a cache path.

        Args:
            cache_path: Path within the cache directory (e.g., 'cache/cd/cdef/prompt.txt')

        Returns:
            Real filesystem path (only for directory caches)
        """
        if self.is_zip:
            raise RuntimeError("Cannot get real path for zipfile cache - zip caches are read-only")
        else:
            return self.path / cache_path

    def _parse_path_to_tuple(self, path_str: str) -> tuple[str, str]:
        """Parse a cache path string to (sub_directory, filename) tuple."""
        parts = Path(path_str).parts
        if len(parts) >= 2:
            sub_dir = parts[1]  # parts[0] is hash_prefix
            filename = str(Path(*parts[2:])) if len(parts) > 2 else parts[1]
            return (sub_dir, filename)
        return ("", "")

    def _list_files(self, pattern: str = "**/*") -> List[tuple[str, str]]:
        """
        List files in the cache.

        Args:
            pattern: Glob pattern to match files

        Returns:
            List of tuples (sub_directory, filename) for files in the cache
        """
        if self.is_zip:
            # For zip files, list all files and filter by pattern
            all_files = self._zip_file.namelist()
            # Filter out files not in cache directory and remove cache/ prefix
            cache_files = [f for f in all_files if f.startswith(str(self.CACHE_DIR) + "/")]
            cache_files = [f[len(str(self.CACHE_DIR)) + 1:] for f in cache_files]
            # Simple pattern matching for zip files (could be enhanced)
            if pattern == "**/*":
                matching_files = cache_files
            else:
                # Basic filtering - could be improved with fnmatch
                matching_files = [f for f in cache_files if pattern.replace("**/", "").replace("*", "") in f]
            
            # Parse to tuples
            return [self._parse_path_to_tuple(f) for f in matching_files]
        else:
            # Return tuples (sub_directory, filename)
            cache_dir = self.path / self.CACHE_DIR
            if cache_dir.exists():
                rel_paths = [str(p.relative_to(cache_dir)) for p in cache_dir.glob(pattern) if p.is_file()]
                return [self._parse_path_to_tuple(f) for f in rel_paths]
            return []

    def _make_cache_path(self, sub_directory: str, file: str) -> Path:
        """
        Given a sub_directory like 'cdef' and file like 'result_abc123.json', return cache/cd/cdef/result_abc123.json
        """
        if len(sub_directory) >= 2:
            prefix = sub_directory[:2]
            return self.CACHE_DIR / prefix / sub_directory / file
        return self.CACHE_DIR / sub_directory / file

    def insert_file(self, sub_directory: str, file: str, content: Union[str, bytes]):
        """
        Insert a file into the cache.

        Args:
            sub_directory: Sub-directory within cache (e.g., 'cdef')
            file: Filename within the sub-directory (e.g., 'prompt.txt')
            content: File content as string or bytes

        Raises:
            RuntimeError: If trying to write to a zipfile cache
        """
        if self.is_zip:
            raise RuntimeError("Cannot insert files into zipfile cache - zip caches are read-only")

        full_path = self._make_cache_path(sub_directory, file)
        real_path = self._get_real_path(str(full_path))
        real_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, str):
            with open(real_path, 'w', encoding=self.encoding) as f:
                f.write(content)
        else:
            with open(real_path, 'wb') as f:
                f.write(content)

    def read_file(self, sub_directory: str, file: str) -> Union[str, bytes]:
        """
        Read a file from the cache.

        Args:
            sub_directory: Sub-directory within cache (e.g., 'cdef')
            file: Filename within the sub-directory (e.g., 'prompt.txt')

        Returns:
            File content
        """
        full_path = self._make_cache_path(sub_directory, file)
        
        if self.is_zip:
            try:
                with self._zip_file.open(str(full_path)) as f:
                    content = f.read()
                    if isinstance(content, bytes):
                        return content.decode(self.encoding)
                    return content
            except KeyError:
                raise FileNotFoundError(f"File {sub_directory}/{file} not found in cache")

        real_path = self._get_real_path(str(full_path))
        if not real_path.exists():
            raise FileNotFoundError(f"File {sub_directory}/{file} not found in cache")

        with open(real_path, 'rb') as f:
            content = f.read()
        
        # Try to decode as text, fall back to bytes if it fails
        try:
            return content.decode(self.encoding)
        except UnicodeDecodeError:
            return content


    def merge(self, other_cache: 'Cache'):
        """
        Merge another cache into this one.

        Args:
            other_cache: Cache to merge from

        Raises:
            RuntimeError: If trying to merge into a zipfile cache
        """
        if self.is_zip:
            raise RuntimeError("Cannot merge into zipfile cache - zip caches are read-only")

        for sub_dir, filename in other_cache._list_files():
            try:
                content = other_cache.read_file(sub_dir, filename)
                self.insert_file(sub_dir, filename, content)
            except (FileNotFoundError, KeyError):
                continue  # Skip files that can't be read

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the cache.

        Returns:
            Dictionary with cache statistics
        """
        files = self._list_files()
        total_size = 0
        file_types = defaultdict(int)
        prompt_files = []
        result_files = []
        delayed_files = []

        for sub_dir, filename in files:
            # Reconstruct the full cache path for checks
            hash_prefix = sub_dir[:2]
            file_path = f"{hash_prefix}/{sub_dir}/{filename}"
            
            if self.is_zip:
                # For zip files, get size from zip info (add back cache/ prefix)
                try:
                    zip_info = self._zip_file.getinfo(str(self.CACHE_DIR / file_path))
                    size = zip_info.file_size
                except KeyError:
                    size = 0
            else:
                # For directories, get size from filesystem
                real_path = self._get_real_path(str(self.CACHE_DIR / file_path))
                if real_path.exists():
                    size = real_path.stat().st_size
                else:
                    size = 0

            total_size += size

            if file_path.endswith('.txt'):
                file_types['text'] += 1
                if 'prompt.txt' in file_path:
                    prompt_files.append(file_path)
            elif file_path.endswith('.json'):
                file_types['json'] += 1
                if 'result_' in file_path and file_path.endswith('.json'):
                    result_files.append(file_path)
            elif file_path.endswith('.delayed'):
                file_types['delayed'] += 1
                delayed_files.append(file_path)
            else:
                file_types['other'] += 1

        return {
            'total_files': len(files),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'file_types': dict(file_types),
            'prompt_files_count': len(prompt_files),
            'result_files_count': len(result_files),
            'delayed_files_count': len(delayed_files),
            'cache_type': 'zipfile' if self.is_zip else 'directory'
        }

    def expire_cache(self, timeout_seconds: Optional[int] = None, error_items_only: bool = False) -> int:
        """
        Expire cache files based on age or error status.

        Args:
            timeout_seconds: Files older than this will be deleted. None means no age-based expiration.
            error_items_only: If True, only expire files with errors in JSON analysis.

        Returns:
            Number of files expired

        Raises:
            RuntimeError: If trying to expire files in a zipfile cache
        """
        if self.is_zip:
            raise RuntimeError("Cannot expire files in zipfile cache - zip caches are read-only")

        expired_count = 0
        result_files = []
        for sub_dir, filename in self._list_files():
            hash_prefix = sub_dir[:2]
            file_path = f"{hash_prefix}/{sub_dir}/{filename}"
            if file_path.endswith('.json') and 'result_' in file_path:
                result_files.append(file_path)

        for result_file in result_files:
            real_path = self._get_real_path(str(self.CACHE_DIR / result_file))

            should_expire = False

            if timeout_seconds is not None and real_path.exists():
                cache_age = time.time() - real_path.stat().st_mtime
                if cache_age >= timeout_seconds:
                    should_expire = True

            if error_items_only and self._is_result_with_error(result_file):
                should_expire = True

            if should_expire:
                self._expire_file(result_file)
                expired_count += 1

        return expired_count

    def _expire_file(self, cache_path: str):
        """Expire (delete) a specific file."""
        real_path = self._get_real_path(str(self.CACHE_DIR / cache_path))
        if real_path.exists():
            real_path.unlink()

        # Also remove delayed file if it exists
        delayed_path = cache_path + '.delayed'
        delayed_real_path = self._get_real_path(str(self.CACHE_DIR / delayed_path))
        if delayed_real_path.exists():
            delayed_real_path.unlink()

    def _is_result_with_error(self, result_file: str) -> bool:
        """Check if a result file contains errors."""
        # result_file is now like "cd/cdef/result_abc123.json" (without cache/ prefix)
        # Remove hash prefix to get clean path
        parts = Path(result_file).parts
        if len(parts) >= 2:
            # Skip the hash prefix directory
            clean_path = str(Path(*parts[1:]))  # Skip hash_dir/
        else:
            clean_path = str(result_file)
        
        try:
            # Split clean_path into sub_directory and file
            path_parts = Path(clean_path).parts
            sub_dir = path_parts[0]
            filename = str(Path(*path_parts[1:]))
            content = self.read_file(sub_dir, filename)
            if isinstance(content, str):
                output = json.loads(content)
            else:
                output = json.loads(content.decode('utf-8'))

            # Import here to avoid circular imports
            from prompt_blender.analysis import gpt_json
            analysis_results = gpt_json.analyse(output.get('response', ''), output.get('timestamp', ''))

            for r in analysis_results:
                if r.get('_error', None):
                    return True
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return False
        return False

    def add_to_zip(self, zipf, data, run_args):
        """
        Add cache files (prompt files and result files) to an existing zip file.

        Args:
            zipf: ZipFile object to add files to
            data: Configuration data with parameter combinations
            run_args: Run arguments dictionary
        """
        # This set keeps track of the result files that are already in the zip
        result_files = set()

        # Add the prompt files and result files to the zip
        for argument_combination in data.get_parameter_combinations():
            # argument_combination.prompt_file already includes cache/ prefix
            prompt_file = self.path / argument_combination.prompt_file
            if prompt_file.exists():
                zipf.write(str(prompt_file), argument_combination.prompt_file)

            for run in run_args.values():
                # argument_combination.get_result_file() returns path with cache/ prefix
                result_file = argument_combination.get_result_file(run['run_hash'])

                if result_file not in result_files:
                    full_result_file = self.path / result_file
                    if full_result_file.exists():
                        zipf.write(str(full_result_file), result_file)
                        result_files.add(result_file)
                    else:
                        print(f"Warning: Result file {result_file} not found")
                    result_files.add(result_file)
