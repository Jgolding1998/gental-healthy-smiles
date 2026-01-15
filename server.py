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
# NOTE: The built-in `cgi` module was removed in Python 3.13.  We
# implement our own minimal multipart/form-data parser using the
# `email` package so that the application can run on newer Python
# versions without requiring the deprecated `cgi` module.
import email
from email import policy
from email.parser import BytesParser


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
        elif self.path == '/reply':
            # Handle replies to existing comments
            self._handle_reply()
        elif self.path == '/delete':
            # Handle deletion of an uploaded design
            self._handle_delete()
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

        # Gather list of image files to display. Only include files with
        # image extensions and skip hidden or placeholder files (e.g., .gitkeep).
        allowed_exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        images = []
        for f in os.listdir(UPLOAD_DIR):
            path = os.path.join(UPLOAD_DIR, f)
            # Skip directories and hidden files
            if not os.path.isfile(path) or f.startswith('.'):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in allowed_exts:
                images.append(f)
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
        # Add a friendly tagline under the main heading to welcome visitors and encourage participation
        # Update the tagline to invite visitors to view existing designs and leave gentle feedback.
        html_parts.append('  <p class="tagline">View designs below and leave your gentle feedback.</p>')
        # Upload section
        html_parts.append('  <section class="upload-section">')
        html_parts.append('    <h2>Upload a New Design</h2>')
        # Standard file picker allows selecting multiple images
        html_parts.append('    <form action="/upload" method="post" enctype="multipart/form-data">')
        html_parts.append('      <input type="file" name="file" accept="image/*" multiple required>')
        html_parts.append('      <button type="submit">Upload</button>')
        html_parts.append('    </form>')
        # Drag‑and‑drop zone; users can drop multiple files here
        html_parts.append('    <div id="drop-zone">Drag & drop files here</div>')
        html_parts.append('  </section>')

        # Gallery of designs
        html_parts.append('  <section class="gallery">')
        if not images:
            html_parts.append('    <p class="no-designs">No designs uploaded yet. Use the form above or drag files into the drop zone to add the first logo design.</p>')
        for img in images:
            safe_filename = urllib.parse.quote(img)
            html_parts.append('    <div class="design">')
            # Wrap the image in a link to allow viewing the file directly in a new tab
            html_parts.append(f'      <a href="/{UPLOAD_DIR}/{safe_filename}" target="_blank"><img src="/{UPLOAD_DIR}/{safe_filename}" alt="{escape(img)}" /></a>')
            # Comments and replies list
            html_parts.append('      <div class="comments">')
            html_parts.append('        <h3>Feedback</h3>')
            # Retrieve list of comment objects (each with text and replies)
            comment_list = comments.get(img, [])
            if comment_list:
                html_parts.append('        <ul>')
                for idx, com in enumerate(comment_list):
                    # Each comment may be a dict with text and replies
                    if isinstance(com, dict):
                        text = escape(com.get('text', ''))
                        replies = com.get('replies', [])
                    else:
                        # Fallback: treat plain string as text
                        text = escape(str(com))
                        replies = []
                    html_parts.append(f'          <li><span class="comment-text">{text}</span>')
                    # Show replies, if any
                    if replies:
                        html_parts.append('            <ul class="replies">')
                        for rep in replies:
                            html_parts.append(f'              <li>{escape(str(rep))}</li>')
                        html_parts.append('            </ul>')
                    # Reply form for this comment
                    html_parts.append('            <form action="/reply" method="post" class="reply-form">')
                    html_parts.append(f'              <input type="hidden" name="image" value="{escape(img)}">')
                    html_parts.append(f'              <input type="hidden" name="comment_index" value="{idx}">')
                    html_parts.append('              <textarea name="reply" placeholder="Write a reply..." required></textarea>')
                    html_parts.append('              <button type="submit">Reply</button>')
                    html_parts.append('            </form>')
                    html_parts.append('          </li>')
                html_parts.append('        </ul>')
            html_parts.append('      </div>')
            # Top-level comment form
            html_parts.append('      <form action="/comment" method="post" class="comment-form">')
            html_parts.append(f'        <input type="hidden" name="image" value="{escape(img)}">')
            html_parts.append('        <textarea name="comment" placeholder="Leave your feedback here..." required></textarea>')
            html_parts.append('        <button type="submit">Submit</button>')
            html_parts.append('      </form>')
            # Delete form to remove this design
            html_parts.append('      <form action="/delete" method="post" class="delete-form" onsubmit="return confirm(\'Delete this design and all comments?\');">')
            html_parts.append(f'        <input type="hidden" name="image" value="{escape(img)}">')
            html_parts.append('        <button type="submit">Delete</button>')
            html_parts.append('      </form>')
            html_parts.append('    </div>')
        html_parts.append('  </section>')
        # Client‑side script to enable drag‑and‑drop uploads. The script
        # listens for drag events on the drop zone and submits dropped
        # files via Fetch API. When the upload completes the page
        # reloads to show the new designs.
        html_parts.append('    <script>')
        html_parts.append('      (function() {')
        html_parts.append('        const dropZone = document.getElementById(\'drop-zone\');')
        html_parts.append('        if (dropZone) {')
        html_parts.append('          dropZone.addEventListener(\'dragover\', function(e) {')
        html_parts.append('            e.preventDefault();')
        html_parts.append('            dropZone.classList.add(\'dragover\');')
        html_parts.append('          });')
        html_parts.append('          dropZone.addEventListener(\'dragleave\', function() {')
        html_parts.append('            dropZone.classList.remove(\'dragover\');')
        html_parts.append('          });')
        html_parts.append('          dropZone.addEventListener(\'drop\', function(e) {')
        html_parts.append('            e.preventDefault();')
        html_parts.append('            dropZone.classList.remove(\'dragover\');')
        html_parts.append('            const files = e.dataTransfer.files;')
        html_parts.append('            if (!files || files.length === 0) return;')
        html_parts.append('            const formData = new FormData();')
        html_parts.append('            for (let i = 0; i < files.length; i++) {')
        html_parts.append('              formData.append(\'file\', files[i]);')
        html_parts.append('            }')
        html_parts.append('            fetch(\'/upload\', { method: \'POST\', body: formData })\n')
        html_parts.append('              .then(() => { window.location.reload(); });')
        html_parts.append('          });')
        html_parts.append('        }')
        html_parts.append('      })();')
        html_parts.append('    </script>')
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
        # Parse multipart form data using our custom parser
        form = self._parse_multipart()
        # Support multiple file uploads. The file field may be a list or a single entry.
        file_entries = form.get('file') or form.get('design')
        if not file_entries:
            self.send_error(400, 'No file(s) provided')
            return
        # Normalise to list
        if isinstance(file_entries, list):
            files = file_entries
        else:
            files = [file_entries]
        comments = self._load_comments()
        for fileitem in files:
            # Each fileitem should be a dict with filename and content
            if not isinstance(fileitem, dict) or 'filename' not in fileitem:
                continue
            # Sanitise filename to prevent directory traversal
            filename = os.path.basename(fileitem['filename'])
            name, ext = os.path.splitext(filename)
            # Provide a unique filename if the name already exists
            dest_path = os.path.join(UPLOAD_DIR, filename)
            counter = 1
            while os.path.exists(dest_path):
                filename = f"{name}_{counter}{ext}"
                dest_path = os.path.join(UPLOAD_DIR, filename)
                counter += 1
            # Write uploaded file to disk
            try:
                with open(dest_path, 'wb') as out_file:
                    data = fileitem.get('content', b'')
                    out_file.write(data)
            except Exception:
                # Skip file if write fails
                continue
            # Initialize comments for this design if not already present
            comments.setdefault(filename, [])
        # Save updated comments
        self._save_comments(comments)
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
        # Append as a comment object with text and empty replies
        comments[image].append({"text": comment, "replies": []})
        self._save_comments(comments)
        # Redirect back to index
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def _handle_reply(self) -> None:
        """Handle reply submissions to existing comments."""
        # Read the POST body
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        params = urllib.parse.parse_qs(body, keep_blank_values=True)
        image = params.get('image', [None])[0]
        reply_text = params.get('reply', [''])[0].strip()
        idx_str = params.get('comment_index', [None])[0]
        if not image or not reply_text or idx_str is None:
            # Missing required fields; redirect
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            return
        try:
            idx = int(idx_str)
        except Exception:
            idx = -1
        # Load existing comments
        comments = self._load_comments()
        # Ensure list exists
        comment_list = comments.setdefault(image, [])
        # If index is valid, append reply
        if 0 <= idx < len(comment_list):
            comment_obj = comment_list[idx]
            if isinstance(comment_obj, dict):
                comment_obj.setdefault('replies', [])
                comment_obj['replies'].append(reply_text)
            else:
                # Upgrade plain string comment to dict format
                comment_list[idx] = {'text': str(comment_obj), 'replies': [reply_text]}
        # Save comments and redirect
        self._save_comments(comments)
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def _handle_delete(self) -> None:
        """Handle deletion of an uploaded design and its comments."""
        # Read the POST body
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        params = urllib.parse.parse_qs(body, keep_blank_values=True)
        image = params.get('image', [None])[0]
        if not image:
            # Nothing to delete
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            return
        # Delete the file from disk
        file_path = os.path.join(UPLOAD_DIR, os.path.basename(image))
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        # Remove comments
        comments = self._load_comments()
        if image in comments:
            comments.pop(image, None)
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
                    data = json.load(f)
                    # Convert legacy list-of-strings format to list of comment objects
                    for image, comment_list in list(data.items()):
                        if isinstance(comment_list, list):
                            new_list = []
                            for entry in comment_list:
                                if isinstance(entry, dict):
                                    # Ensure keys exist
                                    text = entry.get('text', '')
                                    replies = entry.get('replies', [])
                                    new_list.append({'text': text, 'replies': list(replies)})
                                else:
                                    new_list.append({'text': str(entry), 'replies': []})
                            data[image] = new_list
                    return data
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

    def _parse_multipart(self) -> dict:
        """
        Parse a multipart/form-data request body into a dictionary.

        This helper uses the ``email`` package to parse the raw request
        body. Each form field is returned either as a string (for
        regular fields) or as a dictionary with ``filename`` and
        ``content`` keys for file uploads.

        Returns an empty dict if the Content-Type header does not
        indicate multipart/form-data.
        """
        ctype = self.headers.get('Content-Type', '') or ''
        if 'multipart/form-data' not in ctype:
            return {}
        # Read the full request body
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        # Prepend the Content-Type header so the email parser can
        # understand the multipart structure. The MIME-Version header is
        # required by the parser for strict compliance.
        header_bytes = f'Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n'.encode('utf-8')
        msg = BytesParser(policy=policy.default).parsebytes(header_bytes + body)
        result: dict[str, object] = {}
        # Iterate through each part of the multipart message
        for part in msg.iter_parts():
            disposition = part.get('Content-Disposition') or ''
            if 'form-data' not in disposition:
                continue
            # Extract the form field name
            name = part.get_param('name', header='Content-Disposition', unquote=True)
            if not name:
                continue
            filename = part.get_filename()
            payload = part.get_payload(decode=True)
            # Determine the item (file dict or string)
            if filename is not None:
                item: object = {'filename': filename, 'content': payload or b''}
            else:
                if isinstance(payload, (bytes, bytearray)):
                    item = payload.decode('utf-8', errors='ignore')
                else:
                    item = payload
            # If the field name already exists, convert to list to support multiple entries
            if name in result:
                existing = result[name]
                if isinstance(existing, list):
                    existing.append(item)
                else:
                    result[name] = [existing, item]
            else:
                result[name] = item
        return result


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