import json
import os
import tempfile
import threading
import logging
import queue
from queue import Queue, Empty

logger = logging.getLogger("UIHelpers")

def atomic_write(path, data, mode='w', encoding='utf-8'):
    """Write file atomically to avoid partial writes.
    Writes to a temp file then renames into place.
    """
    dirn = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(dir=dirn)
    try:
        with os.fdopen(fd, mode, encoding=encoding) as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except OSError as e:
                logger.debug(f"Failed to remove temp file {tmp}: {e}")

def safe_read_json(path):
    """Read JSON file returning None on error instead of raising.
    This reduces chance of crashes from transient file corruption.
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, IOError) as e:
        logger.warning(f"Failed to load JSON from {path}: {e}")
        return None


class BackgroundWorker:
    """Simple background worker that runs callables in a thread and
    allows scheduling UI-updates via a callback queue.
    """
    def __init__(self):
        self._q = Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, fn, *args, **kwargs):
        self._q.put((fn, args, kwargs))

    def _run(self):
        while True:
            try:
                fn, args, kwargs = self._q.get()
                try:
                    fn(*args, **kwargs)
                except Exception as e:
                    logger.exception(f"Worker task failed: {e}")
            except (queue.Empty, Exception) as e:
                if not isinstance(e, queue.Empty):
                    logger.exception(f"Worker error: {e}")
