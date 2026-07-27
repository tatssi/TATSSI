"""
Multiprocess helpers for per-pixel time series operations.

Some Analysis tools (change point detection with R's ``changepoint`` via
rpy2, per-pixel peak finding with scipy) cannot be vectorised: they need one
call per pixel. This module runs those loops across CPU cores while keeping
memory bounded:

* The input cube ``(time, rows, cols)`` never travels whole to the workers -
  it is split into row blocks of a few MB each.
* The output is written in-place into a single pre-allocated array as blocks
  complete (no result lists accumulate).
* The worker count is capped both by CPU count and by the RAM available at
  launch time (``/proc/meminfo`` MemAvailable), so the pool cannot push the
  system into swap. The ``TATSSI_WORKERS`` environment variable overrides it.
* Workers use the ``spawn`` start method: each one is a clean interpreter
  with its own embedded R (rpy2 must not be shared with the Qt GUI process).

Worker functions live at module level so they are picklable under spawn.
"""

import os
import math
from functools import partial
import multiprocessing as mp

import numpy as np

import logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

# Estimated peak memory per worker process: embedded R + numpy + one block
PER_WORKER_MB = 350


def _mem_available_mb():
    """MemAvailable from /proc/meminfo, in MB (None if unreadable)."""
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return None


def get_n_workers(n_workers=None, per_worker_mb=PER_WORKER_MB):
    """
    Decide how many worker processes to use.

    Priority: explicit argument > TATSSI_WORKERS env var > automatic.
    The automatic value is capped by CPU count (leaving one core for the
    GUI/OS) and by available RAM (each worker budgeted ``per_worker_mb``,
    using at most half of MemAvailable) so the pool cannot exhaust RAM+swap.
    """
    env = os.environ.get('TATSSI_WORKERS')
    if n_workers is None and env is not None:
        try:
            n_workers = max(1, int(env))
            LOG.info("Using TATSSI_WORKERS=%d worker processes", n_workers)
            return n_workers
        except ValueError:
            LOG.warning("Ignoring invalid TATSSI_WORKERS=%r", env)

    if n_workers is not None:
        return max(1, int(n_workers))

    cpu_cap = max(1, (os.cpu_count() or 2) - 1)
    avail = _mem_available_mb()
    if avail is not None:
        ram_cap = max(1, int((avail * 0.5) // per_worker_mb))
    else:
        ram_cap = cpu_cap

    n_workers = max(1, min(cpu_cap, ram_cap))
    LOG.info("Workers: %d (CPU cap %d, RAM cap %d; MemAvailable %s MB, "
             "~%d MB/worker budget)", n_workers, cpu_cap, ram_cap,
             avail, per_worker_mb)
    return n_workers


def apply_along_time_blocks(data, block_func, out_dtype=np.int16,
                            n_workers=None, initializer=None,
                            block_rows=None, progress_cb=None,
                            maxtasksperchild=50):
    """
    Run ``block_func`` over row blocks of ``data`` in a process pool.

    :param data: numpy array (time, rows, cols)
    :param block_func: picklable callable taking ``(row0, block)`` and
        returning ``(row0, out_block)`` with ``out_block`` shaped like the
        input block (same time axis) in ``out_dtype``.
    :param progress_cb: optional callable(fraction 0..1), invoked in the
        MAIN process every time a block completes (safe for Qt widgets).
    :return: numpy array (time, rows, cols) of ``out_dtype``
    """
    data = np.asarray(data)
    t, rows, cols = data.shape

    n_workers = get_n_workers(n_workers)

    if block_rows is None:
        # Blocks of ~16 MB, but at least enough blocks to keep every
        # worker busy and give a usable progress bar
        bytes_per_row = t * cols * max(data.dtype.itemsize, 1)
        by_size = max(1, int((16 * 1024 * 1024) // bytes_per_row))
        by_count = max(1, math.ceil(rows / max(4 * n_workers, 16)))
        block_rows = max(1, min(by_size, by_count))

    n_blocks = math.ceil(rows / block_rows)
    est_mb = (data.nbytes + rows * cols * t *
              np.dtype(out_dtype).itemsize) // 2**20 + \
             n_workers * PER_WORKER_MB
    LOG.info("Parallel run: %d workers, %d blocks of %d rows "
             "(~%d MB estimated peak)", n_workers, n_blocks, block_rows,
             est_mb)

    out = np.zeros((t, rows, cols), dtype=out_dtype)

    def _blocks():
        for r0 in range(0, rows, block_rows):
            yield r0, data[:, r0:r0 + block_rows, :]

    ctx = mp.get_context('spawn')
    with ctx.Pool(processes=n_workers, initializer=initializer,
                  maxtasksperchild=maxtasksperchild) as pool:
        done = 0
        for r0, out_block in pool.imap_unordered(block_func, _blocks()):
            out[:, r0:r0 + out_block.shape[1], :] = out_block
            done += 1
            if progress_cb is not None:
                progress_cb(done / n_blocks)

    return out


# ---------------------------------------------------------------------------
# Change point detection (R `changepoint` via rpy2, one embedded R per worker)
# ---------------------------------------------------------------------------

_CPT = None
_FloatVector = None
_numpy2ri = None


def _cpd_worker_init():
    """Initialise a private embedded R with `changepoint` in this worker."""
    global _CPT, _FloatVector, _numpy2ri
    from rpy2.robjects.packages import importr
    from rpy2.robjects import FloatVector, numpy2ri
    _CPT = importr('changepoint')
    _FloatVector = FloatVector
    _numpy2ri = numpy2ri


def _cpd_block(args, test_stat='Normal', method='BinSeg', penalty='SIC'):
    """Detect change points for every pixel of a row block."""
    r0, block = args
    t, brows, cols = block.shape
    out = np.zeros((t, brows, cols), dtype=np.int16)

    for y in range(brows):
        for x in range(cols):
            px = np.asarray(block[:, y, x], dtype=np.float64)

            # Skip pixels where no change point can exist: all-NaN or
            # constant series (fill areas). R returns no change points for
            # them anyway - this only saves the R round-trip.
            finite = np.isfinite(px)
            if not finite.any():
                continue
            fpx = px[finite]
            if fpx.min() == fpx.max():
                continue

            changepoints_r = _CPT.cpt_meanvar(
                    _FloatVector(px), test_stat=test_stat,
                    method=method, penalty=penalty)
            changepoints = _numpy2ri.rpy2py(
                    _CPT.cpts(changepoints_r)).astype(int)

            if changepoints.shape[0] > 0:
                out[changepoints + 1, y, x] = 1

    return r0, out


def parallel_changepoints(data, test_stat='Normal', method='BinSeg',
                          penalty='SIC', n_workers=None, progress_cb=None):
    """
    Per-pixel change point detection (same semantics as the previous serial
    loop: ``output[changepoints + 1, y, x] = 1``, dtype int16).

    :param data: numpy array (time, rows, cols) - typically the trend cube
    """
    func = partial(_cpd_block, test_stat=test_stat, method=method,
                   penalty=penalty)
    return apply_along_time_blocks(
            data, func, out_dtype=np.int16, n_workers=n_workers,
            initializer=_cpd_worker_init, progress_cb=progress_cb)


# ---------------------------------------------------------------------------
# Per-pixel peak finding (scipy.signal.find_peaks)
# ---------------------------------------------------------------------------

def _peaks_block(args, distance=1):
    """Find peaks for every pixel of a row block."""
    from scipy.signal import find_peaks

    r0, block = args
    t, brows, cols = block.shape
    out = np.zeros((t, brows, cols), dtype=np.int16)

    for y in range(brows):
        for x in range(cols):
            px = block[:, y, x]

            # Constant or all-NaN pixels cannot have local maxima
            finite = np.isfinite(px) if px.dtype.kind == 'f' \
                else np.ones(t, dtype=bool)
            if not finite.any():
                continue
            fpx = px[finite]
            if fpx.min() == fpx.max():
                continue

            idx, _ = find_peaks(px, distance=distance)
            if idx.shape[0] > 0:
                out[idx, y, x] = 1

    return r0, out


def parallel_find_peaks(data, distance, n_workers=None, progress_cb=None):
    """
    Per-pixel peak finding (same semantics as the previous serial loop:
    ``peaks[idx, y, x] = 1``).

    :param data: numpy array (time, rows, cols)
    """
    func = partial(_peaks_block, distance=int(distance))
    return apply_along_time_blocks(
            data, func, out_dtype=np.int16, n_workers=n_workers,
            progress_cb=progress_cb)
