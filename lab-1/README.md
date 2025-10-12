# Lab 1 Report — Minimal HTTP Server (Screenshots Guide)

This report demonstrates that all lab requirements were satisfied. Replace each placeholder with your own screenshot, and keep the short description under each.

Tip: On macOS, you can capture windows with Shift+Cmd+4 (then Space), or the whole screen with Shift+Cmd+3.

---

## 1) Contents of the source directory
![screenshot](images/01-source-tree.png)
Short description: Project structure under `lab-1/` (server, client, content, Dockerfile, docker-compose.yml).

---

## 2) Docker Compose file and Dockerfile
![screenshot](images/02-compose-file.png)
Short description: `docker-compose.yml` mapping port 8080 and mounting `content/`.

![screenshot](images/03-dockerfile.png)
Short description: `Dockerfile` launching `python server.py content --host 0.0.0.0 --port 8080`.

---

## 3) Starting the container
![screenshot](images/04-up-command.png)
Short description: Running `docker compose up -d` in the `lab-1` directory.

---

## 4) Command that runs the server inside the container
![screenshot](images/05-server-cmd.png)
Short description: Server entrypoint shows `python server.py content --host 0.0.0.0 --port 8080` (from Dockerfile or logs).

---

## 5) Contents of the served directory
![screenshot](images/06-content-tree.png)
Short description: `content/` includes `index.html`, `cat_surprise.png`, `sample.pdf`, and nested `docs/` with PDFs.

---

## 6) Browser requests of four files
### a) Inexistent file (404)
![screenshot](images/07-404.png)
Short description: Requesting a missing path returns `404 Not Found`.

### b) HTML file with image
![screenshot](images/08-html-with-image.png)
Short description: `index.html` renders in browser and displays `cat_surprise.png` via `<img>`.

### c) PDF file
![screenshot](images/09-pdf-request.png)
Short description: Requesting a `.pdf` triggers a download (Content-Disposition set by server when using listing link).

### d) PNG file
![screenshot](images/10-png-request.png)
Short description: Requesting a `.png` triggers a download (from listing link that appends `?download=1`).

---

## 7) Client usage (optional for extra points)
![screenshot](images/11-client-run-html.png)
Short description: Running `python client.py localhost 8080 / ~/Downloads` prints directory listing HTML.

![screenshot](images/12-client-run-pdf.png)
Short description: Running `python client.py localhost 8080 /docs/book1.pdf ~/Downloads` saves the PDF to `~/Downloads`.

![screenshot](images/13-client-saved-files.png)
Short description: Finder/Explorer view showing files saved by the client in the chosen directory.

---

## 8) Directory listing (optional for extra points)
![screenshot](images/14-listing-root.png)
Short description: Auto-generated directory listing at `/` with styled grid and icons.

![screenshot](images/15-listing-subdir.png)
Short description: Subdirectory listing (e.g., `/docs/` or `/docs/more/`) with navigation and downloads.

---

## 9) Browsing a friend’s server (optional for extra points)
![screenshot](images/16-network-setup.png)
Short description: Network setup diagram (both machines on same LAN/Wi‑Fi).

![screenshot](images/17-find-ip.png)
Short description: Finding your friend’s IP with `ipconfig getifaddr en0` (macOS) or `ipconfig`/`ip a` (other).

![screenshot](images/18-friend-server-contents.png)
Short description: Browser showing the contents of your friend’s server (their `content/` listing).

![screenshot](images/19-client-against-friend.png)
Short description: Using your client to download a file from your friend’s server into your own directory.

---

## Notes (requirements satisfied)
- Server handles one request at a time and takes the directory to serve as an argument.
- Parses HTTP requests, serves HTML/PNG/PDF, 404 for missing/unsupported.
- Directory listing for folders; nested directories supported.
- Client: `client.py server_host server_port filename directory` — prints HTML, saves PNG/PDF to directory.
- `SO_REUSEADDR` enables fast restart without "Address already in use".

Feel free to add more screenshots if you tested extra scenarios.
