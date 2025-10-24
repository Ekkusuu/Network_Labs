#!/usr/bin/env python3
import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request


def single_request(url):
    try:
        req = Request(url, headers={'User-Agent':'rate-tester'})
        with urlopen(req, timeout=5) as r:
            return r.status
    except Exception:
        return None


def run_for_rps(url, rps, duration, workers):
    # We will run for `duration` seconds. Each second schedule `rps` requests spaced evenly.
    successes_per_second = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for sec in range(duration):
            start = time.time()
            futures = [ex.submit(single_request, url) for _ in range(rps)]
            # collect results as they complete for this second
            ok = 0
            for f in as_completed(futures, timeout=5):
                try:
                    status = f.result()
                    if status == 200:
                        ok += 1
                except Exception:
                    pass
            elapsed = time.time() - start
            # sleep until next second boundary (if any)
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)
            successes_per_second.append(ok)
    return successes_per_second


def main():
    p = argparse.ArgumentParser(description='Rate test: run for 10s at the given requests-per-second (single positional argument)')
    p.add_argument('rps', type=int, help='Requests per second to issue (single positional argument)')
    args = p.parse_args()

    RPS = args.rps
    DURATION = 10
    URL = 'http://127.0.0.1:8083/index.html'
    WORKERS = max(200, RPS * 10)

    per_sec = run_for_rps(URL, RPS, DURATION, WORKERS)
    total = sum(per_sec)
    avg = total / DURATION
    # Output with simple labels so it's human-readable
    print(f"Total successful: {total}/{RPS * DURATION}")
    print(f"Average success/sec: {avg:.2f}")


if __name__ == '__main__':
    main()
