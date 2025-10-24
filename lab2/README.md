# Lab 2 — Concurrent HTTP Server


Services (docker-compose, `lab2/`):
- `multi_unsafe` — multithreaded, naive counter (race) on http://127.0.0.1:8080
- `single`       — single-threaded server on http://127.0.0.1:8081
- `multi_safe`   — multithreaded, locked counter on http://127.0.0.1:8082
- `rate`         — rate-limited server (per-IP) on http://127.0.0.1:8083

Start services (from `lab2/`):

```cmd
cd C:\Users\saval\Desktop\Network_Labs\lab2
docker-compose up --build
```

---

## 1) Performance comparison — 10 concurrent requests

Command used (issues 10 concurrent requests and prints elapsed time for both servers):

```cmd
python C:\Users\saval\Desktop\Network_Labs\lab2\test_concurrency.py --single-url http://127.0.0.1:8081/index.html --multi-url http://127.0.0.1:8082/index.html
```



![all_thread_10req](images/all_thread_10req.png)


---

## 2) Hit counter and race condition

How to trigger the race (naive counter on port 8080):

1. Ensure `multi_unsafe` is running (port 8080).
2. Run the race tester (200 concurrent requests):

```cmd
python C:\Users\saval\Desktop\Network_Labs\lab2\test_counter_race.py --requests 200 --workers 100
```

Screenshot (replace placeholders):

- Race run (requests sent):

  ![race-naive](images/race-naive.png)

- Directory listing showing hits after naive run (example shows only 11 hits recorded):

  ![race-naive-hits](images/race-naive-hits.png)

Code responsible for the race (naive, max 4 lines):

```py
# naive non-atomic update (race-prone)
cur = COUNTS.get(key, 0)
time.sleep(0.01)  # increase chance of interleaving
COUNTS[key] = cur + 1
```

Fixed code (locked update, max 4 lines):

```py
with COUNTS_LOCK:
    COUNTS[key] = COUNTS.get(key, 0) + 1
```

Re-run the tester against `multi_safe` (port 8082) and verify:

- Race run (requests sent):

  ![race-fixed](images/race-fixed.png)

- Directory listing after fixed run (shows 200 hits):

  ![race-fixed-hits](images/race-fixed-hits.png)

---

## 3) Rate limiting (per-IP)

How to spam (example 20 req/s for 10s):

```cmd
python C:\Users\saval\Desktop\Network_Labs\lab2\test_rate.py 20
```

Screenshot (replace placeholder):

![rate-first](images/rate-first.png)

Caption: 20 req/s for 10s produced only 50 accepted requests out of 200 (≈5 req/s enforced).

How to test a lower rate (4 req/s for 10s):

```cmd
python C:\Users\saval\Desktop\Network_Labs\lab2\test_rate.py 4
```

Screenshot (replace placeholder):

![rate-second](images/rate-second.png)

Caption: 4 req/s for 10s produced 40/40 accepted (≈4 req/s), showing the limiter allows up to the configured rate.

IP awareness: to demonstrate that limits apply per source IP, run the spammer from one host (or container) and then run `test_rate.py 5` from another machine/container — the second source should still be able to get up to the configured rate.

---

## Commands summary

- How to send 10 requests to the single-threaded server:

  ```cmd
  python C:\Users\saval\Desktop\Network_Labs\lab2\test_concurrency.py --single-url http://127.0.0.1:8081/index.html --multi-url http://127.0.0.1:8082/index.html
  ```

- How to send 10 requests to the multi-threaded server: same command as above (the script reports both).

- How to trigger a race condition: run `test_counter_race.py --requests 200 --workers 100` against `multi_unsafe` (port 8080).

- Code responsible for it (max. 4 lines):

```py
cur = COUNTS.get(key, 0)
time.sleep(0.01)
COUNTS[key] = cur + 1
```

- Fixed code:

```py
with COUNTS_LOCK:
    COUNTS[key] = COUNTS.get(key, 0) + 1
```

