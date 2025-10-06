# Minimal HTTP Server (Programming Lab)

## Features
- Serve files from a specified root directory (command-line argument)
- Supported types: HTML (.html/.htm), PNG (.png), PDF (.pdf)
- Directory listings (auto-generated HTML similar to `python -m http.server`)
- Nested directory navigation with parent (..) link
- Per-file direct download links (`?download=1`)
- Proper HTTP status codes: 200, 400, 403, 404, 405, 500, 505
- Path traversal protection
- Single-request-at-a-time (sequential, no concurrency) per spec
- Graceful restart using `SO_REUSEADDR` (avoid "Address already in use")
- Simple Python HTTP client script

## Library Restriction
Implementation intentionally uses only the Python standard modules: `os`, `sys`, and `socket`.

Implications:
- No `Date` header (would require `datetime` or manual RFC1123 formatting).
- No percent-encoding/decoding beyond very simple manual parsing (directory links assume simple filenames without spaces or special characters).
- Minimal argument parsing (custom lightweight parser instead of `argparse`).
- No automatic generation of placeholder images; files must exist in `content/`.

These constraints keep the code minimal and aligned with the requirement to avoid additional libraries.

## Why Address Reuse Works
`socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)` allows the server to bind to the same host/port even if the previous socket is in `TIME_WAIT`. Without it, restarting quickly can raise: `OSError: [Errno 48] Address already in use` (macOS) or `[Errno 98]` (Linux). This does **not** violate TCP safety: the OS still prevents active conflicting connections; it just lets the listening socket re-bind sooner.

## Project Structure
```
lab-1/
  server/server.py         # HTTP server
  client/client.py         # HTTP client
  content/                 # Served static files
    index.html
    cat_surprise.png
    sample.pdf
  Dockerfile
  docker-compose.yml
```

## Running Locally (Host)
```bash
python server/server.py content --port 8080
# In another shell (client CLI format: server_host server_port filename directory)
python client/client.py YOUR_LAN_IP 8080 /            .           # print directory listing HTML (dir arg required)
python client/client.py YOUR_LAN_IP 8080 /index.html  .           # print page HTML
python client/client.py YOUR_LAN_IP 8080 /sample.pdf  downloads   # save PDF to downloads/
python client/client.py YOUR_LAN_IP 8080 /cat_surprise.png downloads  # save PNG to downloads/
```
Or use a browser: http://YOUR_LAN_IP:8080/

Find YOUR_LAN_IP on macOS:
```bash
ipconfig getifaddr en0   # common Wi‑Fi interface
```

Directory listing example (root of `content`):
```
Directory listing for /
- index.html
- cat_surprise.png
- sample.pdf
```
(Your output is styled HTML; above is a plain text sketch.)

### Nested directories
Sample structure provided:
```
content/
  index.html
  cat_surprise.png
  sample.pdf
  docs/
    index.html
    book1.pdf
    book2.pdf
    more/
      ebook.pdf
```
Navigate to http://YOUR_LAN_IP:8080/docs/ and deeper into /docs/more/.

## Docker Build + Run
```bash
docker compose build
docker compose up -d
# Browse:
open http://YOUR_LAN_IP:8080/
```
Logs:
```bash
docker compose logs -f web
```
Stop:
```bash
docker compose down
```

## Client in Docker
The compose file includes a `client` service for experimentation:
```bash
# format: server_host server_port filename directory
docker compose exec client python client.py web 8080 / .
docker compose exec client python client.py web 8080 /index.html .
docker compose exec client python client.py web 8080 /sample.pdf downloads
docker compose exec client python client.py web 8080 /cat_surprise.png downloads
```
Downloaded PNG/PDF files appear inside the `client` container working directory, which is volume-mounted to your host at `lab-1/client/`.

## Security Notes
- Only basic path traversal prevention (rejects attempts to escape root). Not hardened for production.
- No MIME sniffing; determinations are by file extension whitelist.

## Possible Extensions
- Add caching headers (ETag/Last-Modified)
- Parallel handling (threading / asyncio)
- Support Range requests for large files
- Add logging to a file with common log format

## Friend's Server Browsing
To browse a friend's server on the same LAN, obtain their IP (e.g., 192.168.1.25) and run:
```bash
python client/client.py 192.168.1.25 8080 / ~/Downloads
```
(Ensure network/firewall allows the connection.)

## License
Educational use.
