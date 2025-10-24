#!/usr/bin/env python3
"""Simple single-threaded HTTP server.

Features:
 - Serves files (HTML, PNG, PDF) from a given root directory passed as argv[1].
 - Generates directory listings (like python -m http.server) with hyperlinks.
 - Returns 404 for missing files or unsupported extensions.
 - Handles only GET method, returns 405 for others.
 - Ensures path traversal attempts (.. etc.) are blocked.
 - Uses SO_REUSEADDR so restart does not yield 'Address already in use'.
 - Handles one request at a time (no concurrency) as specified.

Usage:
  python server.py <root_directory> [--host 0.0.0.0] [--port 8080]
"""
import os
import sys
import socket

HOST_DEFAULT = "0.0.0.0"
PORT_DEFAULT = 8080
SERVER_NAME = "MinimalPythonHTTP/1.0"

ALLOWED_MIME = {
    '.html': 'text/html; charset=utf-8',
    '.htm': 'text/html; charset=utf-8',
    '.png': 'image/png',
    '.pdf': 'application/pdf',
}

def http_date():
    # Without datetime we omit Date header (requirement: only os, sys, socket)
    return None

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
    # Normalize req_path for display and breadcrumbs
    disp_path = req_path if req_path else '/'

    # Build breadcrumb (Home / segment / ...)
    crumbs = [("/", "Home")]
    if disp_path not in ('', '/'):
        parts = disp_path.strip('/').split('/')
        cur = ''
        for p in parts:
            cur += '/' + p
            crumbs.append((cur + ('/' if not cur.endswith('/') else ''), p))

    cards = []
    # Parent card
    if disp_path not in ('', '/'):
        parent = disp_path.rstrip('/')
        parent = parent.rsplit('/', 1)[0]
        if parent == '':
            parent = '/'
        cards.append(
            """
            <a class="card" href="{href}">
              <div class="icon">↩️</div>
              <div class="name">..</div>
              <div class="meta">Up</div>
            </a>
            """.replace('{href}', parent)
        )

    try:
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            is_dir = os.path.isdir(full)
            display = name + ('/' if is_dir else '')
            # HTML should open inline; others default to download
            if is_dir:
                href = display
            else:
                ext = os.path.splitext(name)[1].lower()
                if ext in ('.html', '.htm'):
                    href = display
                else:
                    href = display + '?download=1'
            size_meta = ''
            if is_dir:
                try:
                    count = len(os.listdir(full))
                    size_meta = f"{count} items"
                except Exception:
                    size_meta = 'Folder'
            else:
                try:
                    size_meta = human_size(os.path.getsize(full))
                except Exception:
                    size_meta = '—'
            icon = icon_for(name, is_dir)
            safe_name = html_escape(display)
            cards.append(
                """
                <a class="card" href="{href}">
                  <div class="icon">{icon}</div>
                  <div class="name">{name}</div>
                  <div class="meta">{meta}</div>
                </a>
                """.replace('{href}', href)
                     .replace('{icon}', icon)
                     .replace('{name}', safe_name)
                     .replace('{meta}', html_escape(size_meta))
            )
    except OSError as e:
        cards.append(f"<div class='error'>Error reading directory: {html_escape(str(e))}</div>")

    # Compose page
    breadcrumb_html = []
    for i, (href, label) in enumerate(crumbs):
        if i == len(crumbs) - 1:
            breadcrumb_html.append(f"<span class='crumb current'>{html_escape(label)}</span>")
        else:
            breadcrumb_html.append(f"<a class='crumb' href='{href}'>{html_escape(label)}</a><span class='sep'>/</span>")

    page = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Directory listing for {html_escape(disp_path)}</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #11162a;
      --text: #eef2ff;
      --muted: #9aa4c7;
      --accent: #4f7cff;
      --card: #141b34;
      --card-hover: #1a2342;
      --border: #232a4a;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background: var(--bg); color: var(--text); }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    .head {{ display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom: 18px; }}
    .title {{ font-size: 20px; font-weight: 600; letter-spacing: .2px; }}
    .crumbs {{ color: var(--muted); font-size: 14px; display:flex; align-items:center; flex-wrap:wrap; gap:6px; }}
    .crumb, .sep {{ color: var(--muted); text-decoration:none; }}
    .crumb:hover {{ color: var(--text); }}
    .current {{ color: var(--text); font-weight:600; }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:12px; margin-top: 8px; }}
    .card {{ display:block; background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px; text-decoration: none; color: var(--text); transition: transform .12s ease, background .12s ease, box-shadow .12s ease; }}
    .card:hover {{ background: var(--card-hover); transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,.25); }}
    .icon {{ font-size: 26px; line-height: 1; margin-bottom: 8px; }}
    .name {{ font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .meta {{ margin-top: 6px; font-size: 12px; color: var(--muted); }}
    .error {{ padding: 12px; background: #3b1d1d; border: 1px solid #6a2a2a; border-radius: 8px; color: #ffd8d8; }}
  </style>
  <link rel='icon' href='data:;base64,iVBORw0KGgo='>
  <meta name='color-scheme' content='dark light'>
  <meta name='robots' content='noindex'>
  <meta name='referrer' content='no-referrer'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <meta http-equiv='X-UA-Compatible' content='IE=edge'>
  <meta name='description' content='Directory listing'>
  <meta name='theme-color' content='#0b1020'>
  <style>@media (prefers-color-scheme: light) {{ :root {{ --bg:#f4f6fb; --panel:#fff; --text:#101428; --muted:#50618b; --card:#fff; --card-hover:#f3f6ff; --border:#dfe5fb; }} }}</style>
</head>
<body>
  <div class='wrap'>
    <div class='head'>
      <div class='title'>Directory listing</div>
      <div class='crumbs'>{''.join(breadcrumb_html)}</div>
    </div>
    <div class='grid'>
      {''.join(cards)}
    </div>
  </div>
</body>
</html>
"""
    return page.encode('utf-8')

def handle_request(root: str, raw_request: bytes) -> bytes:
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

    # Query parsing (only need download flag)
    if '?' in target:
        path_part, query_part = target.split('?', 1)
    else:
        path_part, query_part = target, ''
    download_flag = False
    if query_part:
        for kv in query_part.split('&'):
            if kv.lower() == 'download=1' or kv.lower() == 'download=true':
                download_flag = True
                break
    target_no_query = path_part

    # Directory request root or path
    ok, fs_path = safe_join(root, target_no_query)
    if not ok:
        return build_response('403 Forbidden', {'Content-Type': 'text/plain; charset=utf-8'}, b'Forbidden')

    if os.path.isdir(fs_path):
        body = directory_listing(fs_path, target_no_query if target_no_query else '/')
        return build_response('200 OK', {'Content-Type': 'text/html; charset=utf-8'}, body)

    if not os.path.exists(fs_path):
        return build_response('404 Not Found', {'Content-Type': 'text/plain; charset=utf-8'}, b'Not Found')

    ext = os.path.splitext(fs_path)[1].lower()
    if ext not in ALLOWED_MIME:
        return build_response('404 Not Found', {'Content-Type': 'text/plain; charset=utf-8'}, b'Unsupported file type')

    try:
        mode = 'rb'
        with open(fs_path, mode) as f:
            data = f.read()
    except OSError:
        return build_response('500 Internal Server Error', {'Content-Type': 'text/plain; charset=utf-8'}, b'Error reading file')

    headers = {'Content-Type': ALLOWED_MIME[ext]}
    if download_flag:
        fname = os.path.basename(fs_path) or 'download'
        headers['Content-Disposition'] = 'attachment; filename="' + fname + '"'
    return build_response('200 OK', headers, data)

def serve(root, host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Allow immediate reuse of address after server stops.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(1)
        print(f"Serving {root} on http://{host}:{port} (Ctrl+C to stop)")
        while True:
            conn, addr = s.accept()
            with conn:
                try:
                    request = b''
                    # Simple read until double CRLF or limit
                    while b'\r\n\r\n' not in request and len(request) < 8192:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        request += chunk
                    response = handle_request(root, request)
                    conn.sendall(response)
                except Exception as e:
                    try:
                        err_body = f"Internal error: {e}".encode('utf-8')
                        conn.sendall(build_response('500 Internal Server Error', {'Content-Type': 'text/plain; charset=utf-8'}, err_body))
                    except Exception:
                        pass

def parse_args(argv):
    # Very small manual parser: first arg root, optional --host X --port Y
    root = None
    host = HOST_DEFAULT
    port = PORT_DEFAULT
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--host' and i + 1 < len(argv):
            host = argv[i+1]; i += 2; continue
        if a == '--port' and i + 1 < len(argv):
            try:
                port = int(argv[i+1])
            except ValueError:
                print('Invalid port, using default', file=sys.stderr)
            i += 2; continue
        if not root:
            root = a
            i += 1; continue
        else:
            print(f'Ignoring extra argument: {a}', file=sys.stderr)
            i += 1
    if not root:
        print('Usage: server.py <root> [--host HOST] [--port PORT]', file=sys.stderr)
        sys.exit(1)
    return type('Args', (), {'root': root, 'host': host, 'port': port})

def main():
    args = parse_args(sys.argv[1:])
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print('Error: ' + root + ' is not a directory', file=sys.stderr)
        sys.exit(1)
    try:
        serve(root, args.host, args.port)
    except KeyboardInterrupt:
        print('\nShutting down.')

if __name__ == '__main__':
    main()
