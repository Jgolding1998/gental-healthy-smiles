#!/usr/bin/env python3
"""
A simple feedback website for logo designs.

This script starts an HTTP server using only Python's standard library. It
provides a clean and user‑friendly interface where designers can upload
image files (logo designs) and visitors can view those designs and leave
comments. Uploaded files are stored in the ``uploads`` directory and
comments are recorded in a JSON file (``comments.json``). No external
dependencies are required.

To run the server locally, execute:

    python3 server.py

Then visit ``http://localhost:8000/`` in your browser. If you deploy this
app on a hosting platform, adjust the port as needed.

The interface uses a pastel blue colour scheme to evoke the clean and
gentle feeling appropriate for a dental practice.
"""

import http.server
import socketserver
import os
import urllib.parse
import json
from html import escape
import cgi


# Directory to store uploaded images
UPLOAD_DIR = 'uploads'

# Path to the JSON file that records comments for each image
COMMENTS_FILE = 'comments.json'


class LogoFeedbackHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler that serves the feedback web application."""

    def do_GET(self):
        """Serve the index page or static files."""
        if self.path in ('/', '/index.html'):
            self._serve_index()
        else:
            # Delegate to the base class to serve static files from disk
            super().do_GET()

    def do_POST(self):
        """Handle file uploads and comment submissions."""
        if self.path == '/upload':
            self._handle_upload()
        elif self.path == '/comment':
            self._handle_comment()
        else:
            # Unknown POST endpoint
            self.send_error(404, 'Unknown POST endpoint')

    # ------------------------------------------------------------------
    #  Internal helper methods
    # ------------------------------------------------------------------
    def _serve_index(self) -> None:
        """Dynamically build and send the index page showing all designs."""
        # Ensure directories and comment data exist
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        comments = self._load_comments()

        # Gather list of image files to display
        images = [f for f in os.listdir(UPLOAD_DIR)
                  if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
        images.sort()

        # Build the HTML structure
        html_parts = []
        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html lang="en">')
        html_parts.append('<head>')
        html_parts.append('  <meta charset="UTF-8">')
        html_parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html_parts.append('  <title>Gental Healthy Smiles - Logo Feedback</title>')
        html_parts.append('  <link rel="stylesheet" href="/static/styles.css">')
        html_parts.append('</head>')
        html_parts.append('<body>')
        html_parts.append('  <h1>Gental Healthy Smiles — Logo Design Feedback</h1>')
        # Upload section
        html_parts.append('  <section class="upload-section">')
        html_parts.append('    <h2>Upload a New Design</h2>')
        html_parts.append('    <form action="/upload" method="post" enctype="multipart/form-data">')
        html_parts.append('      <input type="file" name="file" accept="image/*" required>')
        html_parts.append('      <button type="submit">Upload</button>')
        html_parts.append('    </form>')
        html_parts.append('  </section>')

        # Gallery of designs
        html_parts.append('  <section class="gallery">')
        if not images:
            html_parts.append('    <p class="no-designs">No designs uploaded yet. Use the form above to add the first logo design.</p>')
        for img in images:
            safe_filename = urllib.parse.quote(img)
            html_parts.append('    <div class="design">')
            html_parts.append(f'      <img src="/{UPLOAD_DIR}/{safe_filename}" alt="{escape(img)}" />')
            # Comments list
            html_parts.append('      <div class="comments">')
            html_parts.append('        <h3>Feedback</h3>')
            html_parts.append('        <ul>')
            for com in comments.get(img, []):
                html_parts.append(f'          <li>{escape(com)}</li>')
            html_parts.append('        </ul>')
            html_parts.append('      </div>')
            # Comment form
            html_parts.append('      <form action="/comment" method="post" class="comment-form">')
            html_parts.append(f'        <input type="hidden" name="image" value="{escape(img)}">')
            html_parts.append('        <textarea name="comment" placeholder="Leave your feedback here..." required></textarea>')
            html_parts.append('        <button type="submit">Submit</button>')
            html_parts.append('      </form>')
            html_parts.append('    </div>')
        html_parts.append('  </section>')
        html_parts.append('</body>')
        html_parts.append('</html>')

        html_content = '\n'.join(html_parts)
        encoded = html_content.encode('utf-8')
        # Send HTTP response
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _handle_upload(self) -> None:
        """Handle file uploads sent via multipart/form-data."""
        # Ensure upload directory exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        # Parse form data using cgi.FieldStorage
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': self.headers.get('Content-Type'),
            }
        )
        fileitem = form.getfirst('file') or form['file']
        if not fileitem:
            self.send_error(400, 'No file uploaded')
            return
        # When using FieldStorage, fileitem can be a FieldStorage instance or a str
        if isinstance(fileitem, cgi.FieldStorage) and fileitem.filename:
            # Sanitise filename to prevent directory traversal
            filename = os.path.basename(fileitem.filename)
            name, ext = os.path.splitext(filename)
            # Provide a unique filename if the name already exists
            dest_path = os.path.join(UPLOAD_DIR, filename)
            counter = 1
            while os.path.exists(dest_path):
                filename = f"{name}_{counter}{ext}"
                dest_path = os.path.join(UPLOAD_DIR, filename)
                counter += 1
            # Write uploaded file to disk
            with open(dest_path, 'wb') as out_file:
                data = fileitem.file.read()
                out_file.write(data)
            # Update comments file to include an entry for the new design
            comments = self._load_comments()
            comments.setdefault(filename, [])
            self._save_comments(comments)
        else:
            # Not a proper file
            self.send_error(400, 'Invalid file upload')
            return
        # Redirect back to index
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def _handle_comment(self) -> None:
        """Handle comment submissions from regular form encoding."""
        # Read the POST body
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        params = urllib.parse.parse_qs(body, keep_blank_values=True)
        image = params.get('image', [None])[0]
        comment = params.get('comment', [''])[0].strip()
        if not image or not comment:
            # Either image or comment is missing; redirect without saving
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            return
        # Load existing comments
        comments = self._load_comments()
        comments.setdefault(image, [])
        comments[image].append(comment)
        self._save_comments(comments)
        # Redirect back to index
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def _load_comments(self) -> dict:
        """Load comments from the JSON file if it exists."""
        if os.path.exists(COMMENTS_FILE):
            try:
                with open(COMMENTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_comments(self, data: dict) -> None:
        """Persist comments dictionary to disk as JSON."""
        try:
            with open(COMMENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass


def run_server(port: int = 8000) -> None:
    """Start the feedback HTTP server on the given port."""
    # Ensure required directories exist
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs('static', exist_ok=True)
    # Extend MIME type mapping for CSS and JS
    LogoFeedbackHandler.extensions_map.update({
        '.css': 'text/css',
        '.js': 'application/javascript',
    })
    with socketserver.TCPServer(('', port), LogoFeedbackHandler) as httpd:
        print(f"Serving on port {port}")
        httpd.serve_forever()


if __name__ == '__main__':
    run_server(port=8000)
