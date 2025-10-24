import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen


def make_request(url):
    try:
        with urlopen(url, timeout=10) as r:
            return r.status, len(r.read())
    except Exception as e:
        return 'err', str(e)


def measure(file_url, n, workers):
    start = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(make_request, file_url) for _ in range(n)]
        results = [f.result() for f in as_completed(futures)]
    return time.time() - start, results

def main():
    p = argparse.ArgumentParser(description='Race test for COUNTS on ports 8080 (unsafe) and 8082 (safe)')
    p.add_argument('--requests', type=int, default=200, help='Total requests to issue per server')
    p.add_argument('--workers', type=int, default=100, help='Thread pool size for issuing requests')
    p.add_argument('--filename', default='index.html', help='Filename to request and look for in listing')
    args = p.parse_args()

    targets = [
        ('unsafe', 'http://127.0.0.1:8080/index.html', 'http://127.0.0.1:8080/'),
        ('safe',   'http://127.0.0.1:8082/index.html', 'http://127.0.0.1:8082/'),
    ]

    for label, file_url, listing_url in targets:
        print(f"\n== Testing {label} server ({listing_url}) ==")
        print(f'Issuing {args.requests} concurrent requests to {file_url} (workers={args.workers})')
        elapsed, results = measure(file_url, args.requests, args.workers)
        ok = sum(1 for r in results if r[0] == 200)
        print(f'Requests done in {elapsed:.2f}s ({ok}/{args.requests} OK)')

    # done


if __name__ == '__main__':
    main()
