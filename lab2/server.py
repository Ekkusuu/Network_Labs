import os
import sys
import socket
import threading
import time

HOST_DEFAULT = "0.0.0.0"
PORT_DEFAULT = 8080
SERVER_NAME = "MinimalPythonHTTP-MT/1.0"

ALLOWED_MIME = {
    '.html': 'text/html; charset=utf-8',
    '.htm': 'text/html; charset=utf-8',
    '.png': 'image/png',
    '.pdf': 'application/pdf',
}

# Request counters: map normalized path (leading slash) -> int
COUNTS = {}
COUNTS_LOCK = threading.Lock()

# If True, use a lock to protect counter updates; if False, do naive update (shows race)
USE_LOCK = True

# Rate limiting structures (per-client sliding window)
from collections import deque
REQUEST_TIMES = {}   # client_ip -> deque[timestamps]
REQUEST_TIMES_LOCK = threading.Lock()
RATE_LIMIT_ENABLED = False
RATE_LIMIT_RPS = 5.0


def build_response(status, headers, body=b""):
    base_headers = {
        'Server': SERVER_NAME,
        'Content-Length': str(len(body)),
        'Connection': 'close',
    }
    if headers:
        base_headers.update(headers)
    header_lines = [f"HTTP/1.1 {status}"]
    for k, v in base_headers.items():
        header_lines.append(f"{k}: {v}")
    return ("\r\n".join(header_lines) + "\r\n\r\n").encode('utf-8') + body


def safe_join(root, rel_path):
    rel_path = rel_path.lstrip('/')
    candidate = os.path.normpath(os.path.join(root, rel_path))
    root_real = os.path.realpath(root)
    cand_real = os.path.realpath(candidate)
    if not cand_real.startswith(root_real):
        return False, candidate
    return True, candidate


def html_escape(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def human_size(n):
    try:
        n = int(n)
    except Exception:
        return '—'
    units = ['B','KB','MB','GB','TB']
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units)-1:
        f /= 1024.0
        i += 1
    if i == 0:
        return f"{int(f)} {units[i]}"
    return f"{f:.1f} {units[i]}"


def icon_for(name, is_dir):
    if is_dir:
        return '📁'
    ext = os.path.splitext(name)[1].lower()
    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'):
        return '🖼️'
    if ext == '.pdf':
        return '📕'
    if ext in ('.html', '.htm'):
        return '🧾'
    return '📄'


def directory_listing(path, req_path):
    disp_path = req_path if req_path else '/'
    try:
        items = sorted(os.listdir(path))
    except OSError as e:
        return f"<html><body>Error reading directory: {html_escape(str(e))}</body></html>".encode('utf-8')

    cards = []
    for name in items:
        full = os.path.join(path, name)
        is_dir = os.path.isdir(full)
        display = name + ('/' if is_dir else '')
        # href: directories link to folder, files link to file
        href = display
        # Build relative key for counters (leading slash)
        if disp_path in ('', '/'):
            rel = '/' + name.lstrip('/')
        else:
            rel = '/' + os.path.join(disp_path.lstrip('/'), name).lstrip('/')
        count = COUNTS.get(rel, 0)
        icon = icon_for(name, is_dir)
        safe_name = html_escape(display)
        cards.append(
            f"<a class=\"card\" href=\"{html_escape(href)}\">"
            f"<div class=\"icon\">{icon}</div>"
            f"<div class=\"name\">{safe_name}</div>"
            f"<div class=\"meta\">Hits: {count}</div>"
            f"</a>"
        )

    page = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Index of {html_escape(disp_path)}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Arial; padding: 24px; background: #f6f8fb; color: #0b1220 }}
    .wrap {{ max-width: 1000px; margin: 0 auto }}
    h1 {{ margin: 0 0 12px 0 }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap:12px }}
    .card {{ display:block; background: white; border-radius:10px; padding:12px; text-decoration:none; color:inherit; box-shadow: 0 6px 18px rgba(12,18,35,.06); border:1px solid #e6e9f2 }}
    .card:hover {{ transform: translateY(-4px); box-shadow: 0 12px 30px rgba(12,18,35,.08) }}
    .icon {{ font-size:28px; margin-bottom:8px }}
    .name {{ font-weight:600; font-size:14px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }}
    .meta {{ margin-top:6px; color:#556; font-size:12px }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Index of {html_escape(disp_path)}</h1>
    <div class="grid">{''.join(cards)}</div>
  </div>
</body>
</html>
"""
    return page.encode('utf-8')


def handle_request(root: str, raw_request: bytes) -> bytes:
    # Simulate work
    time.sleep(1.0)

    try:
        text = raw_request.decode('iso-8859-1', errors='replace')
        request_line = text.splitlines()[0]
    except Exception:
        return build_response('400 Bad Request', {'Content-Type': 'text/plain; charset=utf-8'}, b'Malformed request')

    parts = request_line.split()
    if len(parts) != 3:
        return build_response('400 Bad Request', {'Content-Type': 'text/plain; charset=utf-8'}, b'Bad request line')
    method, target, version = parts
    if version not in ('HTTP/1.0', 'HTTP/1.1'):
        return build_response('505 HTTP Version Not Supported', {'Content-Type': 'text/plain; charset=utf-8'}, b'Unsupported HTTP version')
    if method != 'GET':
        return build_response('405 Method Not Allowed', {'Allow': 'GET', 'Content-Type': 'text/plain; charset=utf-8'}, b'Only GET supported')

    if '?' in target:
        path_part, _ = target.split('?', 1)
    else:
        path_part = target

    ok, fs_path = safe_join(root, path_part)
    if not ok:
        return build_response('403 Forbidden', {'Content-Type': 'text/plain; charset=utf-8'}, b'Forbidden')

    if os.path.isdir(fs_path):
        body = directory_listing(fs_path, path_part if path_part else '/')
        return build_response('200 OK', {'Content-Type': 'text/html; charset=utf-8'}, body)

    if not os.path.exists(fs_path):
        return build_response('404 Not Found', {'Content-Type': 'text/plain; charset=utf-8'}, b'Not Found')

    ext = os.path.splitext(fs_path)[1].lower()
    if ext not in ALLOWED_MIME:
        return build_response('404 Not Found', {'Content-Type': 'text/plain; charset=utf-8'}, b'Unsupported file type')

    try:
        with open(fs_path, 'rb') as f:
            data = f.read()
    except OSError:
        return build_response('500 Internal Server Error', {'Content-Type': 'text/plain; charset=utf-8'}, b'Error reading file')

    headers = {'Content-Type': ALLOWED_MIME[ext]}
    # Update counter for this file. Use normalized key starting with '/'
    try:
        rel = os.path.relpath(fs_path, root)
        key = '/' + rel.replace('\\', '/')
    except Exception:
        key = '/' + os.path.basename(fs_path)

    if USE_LOCK:
        with COUNTS_LOCK:
            COUNTS[key] = COUNTS.get(key, 0) + 1
    else:
        # naive non-atomic update to demonstrate race
        cur = COUNTS.get(key, 0)
        # small sleep to increase chance of interleaving
        time.sleep(0.01)
        COUNTS[key] = cur + 1

    return build_response('200 OK', headers, data)


def handle_connection(conn, addr, root):
    with conn:
        try:
            request = b''
            while b'\r\n\r\n' not in request and len(request) < 8192:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                request += chunk
            # Rate limiting by client IP (optional) - strict sliding 1s window
            if RATE_LIMIT_ENABLED:
                # Prefer X-Forwarded-For header when present (useful behind proxies).
                client_ip = None
                try:
                    text = request.decode('iso-8859-1', errors='replace')
                    # Parse headers to look for X-Forwarded-For (simple linear scan)
                    lines = text.split('\r\n')
                    for h in lines[1:]:
                        if not h:
                            break
                        parts = h.split(':', 1)
                        if len(parts) != 2:
                            continue
                        k = parts[0].strip().lower()
                        v = parts[1].strip()
                        if k == 'x-forwarded-for' and v:
                            # header may contain a comma-separated list; take the first IP
                            client_ip = v.split(',')[0].strip()
                            break
                except Exception:
                    client_ip = None
                # Fall back to socket address if header not present
                if not client_ip:
                    try:
                        client_ip = addr[0]
                    except Exception:
                        client_ip = None

                if client_ip:
                    now = time.time()
                    window = 1.0
                    limit = max(1, int(RATE_LIMIT_RPS))
                    allowed = False
                    with REQUEST_TIMES_LOCK:
                        dq = REQUEST_TIMES.get(client_ip)
                        if dq is None:
                            dq = deque()
                            REQUEST_TIMES[client_ip] = dq
                        # pop old timestamps
                        while dq and dq[0] <= now - window:
                            dq.popleft()
                        if len(dq) < limit:
                            dq.append(now)
                            allowed = True
                    if not allowed:
                        # Optionally log a brief message to stdout for debugging
                        try:
                            print(f"[rate] {client_ip} -> 429 (over {limit}/s)")
                        except Exception:
                            pass
                        resp = build_response('429 Too Many Requests', {'Content-Type': 'text/plain; charset=utf-8', 'Retry-After': '1'}, b'Too Many Requests')
                        conn.sendall(resp)
                        return
            response = handle_request(root, request)
            conn.sendall(response)
        except Exception:
            try:
                conn.sendall(build_response('500 Internal Server Error', {'Content-Type': 'text/plain; charset=utf-8'}, b'Internal error'))
            except Exception:
                pass


def serve(root, host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(32)
        print(f"[multi] Serving {root} on http://{host}:{port}")
        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_connection, args=(conn, addr, root), daemon=True)
            t.start()


def parse_args(argv):
    root = None
    host = HOST_DEFAULT
    port = PORT_DEFAULT
    unsafe = False
    rate_limit = False
    rate = RATE_LIMIT_RPS
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--unsafe':
            unsafe = True; i += 1; continue
        if a == '--rate-limit':
            rate_limit = True; i += 1; continue
        if a == '--rate' and i + 1 < len(argv):
            try:
                rate = float(argv[i+1])
            except Exception:
                pass
            i += 2; continue
        if a == '--host' and i + 1 < len(argv):
            host = argv[i+1]; i += 2; continue
        if a == '--port' and i + 1 < len(argv):
            try:
                port = int(argv[i+1])
            except ValueError:
                pass
            i += 2; continue
        if not root:
            root = a; i += 1; continue
        i += 1
    if not root:
        print('Usage: server.py <root> [--host HOST] [--port PORT]', file=sys.stderr)
        sys.exit(1)
    return type('Args', (), {'root': root, 'host': host, 'port': port, 'unsafe': unsafe, 'rate_limit': rate_limit, 'rate': rate})


def main():
    args = parse_args(sys.argv[1:])
    global USE_LOCK
    if getattr(args, 'unsafe', False):
        USE_LOCK = False
    global RATE_LIMIT_ENABLED, RATE_LIMIT_RPS
    if getattr(args, 'rate_limit', False):
        RATE_LIMIT_ENABLED = True
        try:
            RATE_LIMIT_RPS = float(getattr(args, 'rate', RATE_LIMIT_RPS))
        except Exception:
            pass
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print('Error: ' + root + ' is not a directory', file=sys.stderr)
        sys.exit(1)
    try:
        serve(root, args.host, args.port)
    except KeyboardInterrupt:
        print('\nShutting down (multi).')


if __name__ == '__main__':
    main()
