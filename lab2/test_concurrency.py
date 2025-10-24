import os
import sys
import subprocess
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen

ROOT = os.path.join(os.path.dirname(__file__), 'content')
PY = sys.executable
NUM = 10


def start_server(script, port):
    return subprocess.Popen([PY, script, ROOT, '--host', '127.0.0.1', '--port', str(port)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def make_request(url):
    with urlopen(url, timeout=10) as r:
        return r.status, len(r.read())


def measure(url_base, n=NUM):
    urls = [url_base] * n
    start = time.time()
    with ThreadPoolExecutor(max_workers=n) as ex:
        futures = [ex.submit(make_request, u) for u in urls]
        results = []
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except Exception as e:
                results.append(('err', str(e)))
    elapsed = time.time() - start
    return elapsed, results


def main():
    parser = argparse.ArgumentParser(description='Concurrency test for lab2 servers')
    parser.add_argument('--multi-url', default='http://127.0.0.1:8080/index.html', help='URL for multithreaded server')
    parser.add_argument('--single-url', default='http://127.0.0.1:8081/index.html', help='URL for single-threaded server')
    parser.add_argument('--num', type=int, default=NUM, help='Number of concurrent requests to issue')
    args = parser.parse_args()

    s_url = args.single_url
    m_url = args.multi_url
    n = args.num

    print(f'Issuing {n} concurrent requests to single-threaded server... (URL: {s_url})')
    s_elapsed, s_results = measure(s_url, n)
    print(f'Single-threaded elapsed: {s_elapsed:.2f}s')

    print(f'Issuing {n} concurrent requests to multithreaded server... (URL: {m_url})')
    m_elapsed, m_results = measure(m_url, n)
    print(f'Multithreaded elapsed: {m_elapsed:.2f}s')

    print('\nSummary:')
    print(f'  Single-threaded:   {s_elapsed:.2f}s for {n} requests')
    print(f'  Multithreaded:     {m_elapsed:.2f}s for {n} requests')


if __name__ == '__main__':
    main()
