#!/usr/bin/env python3
"""Simple HTTP client for the minimal server.

Usage:
  python client.py http://host:port/path

Behavior:
  - Performs a GET request.
  - If response Content-Type indicates HTML, prints body to stdout.
  - If PNG or PDF, saves to current directory using the path's basename (fallback names).
  - Otherwise prints status line and does nothing else.
"""
import sys
import os
import socket

def parse_cli(host_arg, port_arg, filename_arg):
    host = host_arg or 'localhost'
    try:
        port = int(port_arg)
    except Exception:
        port = 80
    path = filename_arg or '/'
    if not path.startswith('/'):
        path = '/' + path
    return host, port, path

def percent_decode(s):
    # Minimal %XX decoding
    out = []
    i = 0
    while i < len(s):
        if s[i] == '%' and i + 2 < len(s):
            hex_part = s[i+1:i+3]
            try:
                out.append(chr(int(hex_part, 16)))
                i += 3
                continue
            except ValueError:
                pass
        out.append(s[i])
        i += 1
    return ''.join(out)

def make_request(host, port, path):
    req = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\nAccept: */*\r\n\r\n".encode('utf-8')
    with socket.create_connection((host, port), timeout=5) as s:
        s.sendall(req)
        chunks = []
        while True:
            data = s.recv(4096)
            if not data:
                break
            chunks.append(data)
    return b''.join(chunks)

def split_response(resp):
    try:
        header_part, body = resp.split(b'\r\n\r\n', 1)
    except ValueError:
        return resp, b''
    return header_part, body

def parse_headers(header_bytes):
    lines = header_bytes.decode('iso-8859-1', errors='replace').split('\r\n')
    status_line = lines[0] if lines else ''
    headers = {}
    for line in lines[1:]:
        if not line or ':' not in line:
            continue
        k, v = line.split(':', 1)
        headers[k.strip().lower()] = v.strip()
    return status_line, headers

def ensure_outdir(outdir):
    if outdir and not os.path.isdir(outdir):
        try:
            os.makedirs(outdir, exist_ok=True)
        except Exception:
            pass

def main():
    # Expected format:
    #   python client.py server_host server_port filename directory
    if len(sys.argv) != 5:
        print('Usage: python client.py server_host server_port filename directory', file=sys.stderr)
        sys.exit(1)
    host, port, path = parse_cli(sys.argv[1], sys.argv[2], sys.argv[3])
    outdir = sys.argv[4]
    ensure_outdir(outdir)

    resp = make_request(host, port, path)
    header_bytes, body = split_response(resp)
    _status_line, headers = parse_headers(header_bytes)

    ctype = headers.get('content-type', '')
    if ctype.startswith('text/html'):
        # Print body as text
        try:
            print(body.decode('utf-8', errors='replace'))
        except Exception:
            print(body)
    elif ctype == 'image/png':
        filename = percent_decode(path.rsplit('/', 1)[-1]) or 'download.png'
        if not filename.lower().endswith('.png'):
            filename += '.png'
        with open(os.path.join(outdir, filename), 'wb') as f:
            f.write(body)
        print(f'Saved PNG to {os.path.join(outdir, filename)}')
    elif ctype == 'application/pdf':
        filename = percent_decode(path.rsplit('/', 1)[-1]) or 'download.pdf'
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        with open(os.path.join(outdir, filename), 'wb') as f:
            f.write(body)
        print(f'Saved PDF to {os.path.join(outdir, filename)}')
    else:
        # For any other content-type, print body as text when possible
        try:
            print(body.decode('utf-8', errors='replace'))
        except Exception:
            # Fallback: just show length
            print(f'Unhandled content-type {ctype}; body length {len(body)} bytes', file=sys.stderr)

if __name__ == '__main__':
    main()
