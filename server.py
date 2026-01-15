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

# Path to the JSON file that records designs (images and comments).
# We continue to use the same file name for backward compatibility with
# earlier versions that stored comments keyed by filename. In the new
# structure, each key corresponds to a design and stores a list of
# images and a list of comments.
DATA_FILE = 'comments.json'

import uuid


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
        # Ensure required directories and data exist
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        designs = self._load_designs()

        # Build the HTML structure
        html_parts: list[str] = []
        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html lang="en">')
        html_parts.append('<head>')
        html_parts.append('  <meta charset="UTF-8">')
        html_parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html_parts.append('  <title>Gentle Healthy Smiles - Logo Feedback</title>')
        html_parts.append('  <link rel="stylesheet" href="/static/styles.css">')
        html_parts.append('</head>')
        html_parts.append('<body>')
        html_parts.append('  <h1>Gentle Healthy Smiles — Logo Design Feedback</h1>')
        # Friendly tagline
        html_parts.append('  <p class="tagline">View designs below and leave your gentle feedback.</p>')
        # Upload section with multiple file support and drag-and-drop zone
        html_parts.append('  <section class="upload-section">')
        html_parts.append('    <h2>Upload a New Design</h2>')
        html_parts.append('    <form action="/upload" method="post" enctype="multipart/form-data" id="upload-form">')
        html_parts.append('      <label id="drop-zone">')
        html_parts.append('        <span>Choose Files</span>')
        html_parts.append('        <input type="file" name="file" accept="image/*" multiple required>')
        html_parts.append('      </label>')
        html_parts.append('      <button type="submit">Upload</button>')
        html_parts.append('      <p class="drop-message">Drag & drop files here</p>')
        html_parts.append('    </form>')
        html_parts.append('  </section>')
        # Gallery of designs
        html_parts.append('  <section class="gallery">')
        if not designs:
            html_parts.append('    <p class="no-designs">No designs uploaded yet. Use the form above or drag files into the drop zone to add the first logo design.</p>')
        # Iterate through designs; sort by key for determinism
        for design_id, record in designs.items():
            images = record.get('images', [])
            comments = record.get('comments', [])
            html_parts.append('    <div class="design">')
            # Display all images associated with this design
            html_parts.append('      <div class="design-images">')
            for img in images:
                safe_filename = urllib.parse.quote(img)
                html_parts.append(f'        <a href="/{UPLOAD_DIR}/{safe_filename}" target="_blank"><img src="/{UPLOAD_DIR}/{safe_filename}" alt="{escape(img)}" /></a>')
            html_parts.append('      </div>')
            # Comments and replies
            html_parts.append('      <div class="comments">')
            html_parts.append('        <h3>Feedback</h3>')
            if comments:
                html_parts.append('        <ul>')
                for idx, com in enumerate(comments):
                    text = escape(com.get('text', ''))
                    replies = com.get('replies', [])
                    html_parts.append(f'          <li><span class="comment-text">{text}</span>')
                    if replies:
                        html_parts.append('            <ul class="replies">')
                        for rep in replies:
                            html_parts.append(f'              <li>{escape(str(rep))}</li>')
                        html_parts.append('            </ul>')
                    # Reply form
                    html_parts.append('            <form action="/reply" method="post" class="reply-form">')
                    html_parts.append(f'              <input type="hidden" name="design_id" value="{escape(design_id)}">')
                    html_parts.append(f'              <input type="hidden" name="comment_index" value="{idx}">')
                    html_parts.append('              <textarea name="reply" placeholder="Write a reply..." required></textarea>')
                    html_parts.append('              <button type="submit">Reply</button>')
                    html_parts.append('            </form>')
                    html_parts.append('          </li>')
                html_parts.append('        </ul>')
            html_parts.append('      </div>')
            # Top-level comment form
            html_parts.append('      <form action="/comment" method="post" class="comment-form">')
            html_parts.append(f'        <input type="hidden" name="design_id" value="{escape(design_id)}">')
            html_parts.append('        <textarea name="comment" placeholder="Leave your feedback here..." required></textarea>')
            html_parts.append('        <button type="submit">Submit</button>')
            html_parts.append('      </form>')
            # Delete form
            html_parts.append('      <form action="/delete" method="post" class="delete-form" onsubmit="return confirm(\'Delete this design and all comments?\');">')
            html_parts.append(f'        <input type="hidden" name="design_id" value="{escape(design_id)}">')
            html_parts.append('        <button type="submit">Delete</button>')
            html_parts.append('      </form>')
            html_parts.append('    </div>')
        html_parts.append('  </section>')
        # Include a small script to handle drag & drop events for the upload zone
        html_parts.append('<script>')
        html_parts.append('  const dropZone = document.getElementById("drop-zone");')
        html_parts.append('  const fileInput = dropZone.querySelector("input[type=file]");')
        html_parts.append('  dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("dragover"); });')
        html_parts.append('  dropZone.addEventListener("dragleave", () => { dropZone.classList.remove("dragover"); });')
        html_parts.append('  dropZone.addEventListener("drop", (e) => {')
        html_parts.append('    e.preventDefault(); dropZone.classList.remove("dragover");')
        html_parts.append('    const files = e.dataTransfer.files;')
        html_parts.append('    if (files.length) { fileInput.files = files; document.getElementById("upload-form").submit(); }')
        html_parts.append('  });')
        html_parts.append('</script>')
        html_parts.append('</body>')
        html_parts.append('</html>')

        html_content = '\n'.join(html_parts)
        encoded = html_content.encode('utf-8')
        # Send response
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _handle_upload(self) -> None:
        """Handle file uploads sent via multipart/form-data.

        This handler supports uploading multiple image files at once. All
        files uploaded in the same request are grouped into a single
        design. A unique design identifier is generated and the
        uploaded files are saved into the ``uploads`` directory. The
        design metadata (image list and empty comments list) is stored
        in the JSON data file.
        """
        # Ensure upload directory exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        # Parse multipart form data using our custom parser
        form = self._parse_multipart()
        file_field = form.get('file') or form.get('design')
        if not file_field:
            self.send_error(400, 'No file provided')
            return
        # Normalise to a list of file items (dicts)
        if isinstance(file_field, list):
            fileitems = file_field
        else:
            fileitems = [file_field]
        # Filter out items that lack filename
        fileitems = [fi for fi in fileitems if isinstance(fi, dict) and fi.get('filename')]
        if not fileitems:
            self.send_error(400, 'Invalid file upload')
            return
        # Generate a design identifier based on the first file's base name
        first_filename = os.path.basename(fileitems[0]['filename'])
        base_name, _ = os.path.splitext(first_filename)
        # Clean base_name to remove problematic characters
        base_slug = ''.join(ch for ch in base_name if ch.isalnum() or ch in ('-', '_')).strip('_-') or 'design'
        designs = self._load_designs()
        design_id = base_slug
        suffix = 1
        while design_id in designs:
            design_id = f"{base_slug}_{suffix}"
            suffix += 1
        saved_images: list[str] = []
        # Save each uploaded file to disk, ensuring unique filenames
        for fi in fileitems:
            raw_filename = os.path.basename(fi['filename'])
            name, ext = os.path.splitext(raw_filename)
            dest_filename = raw_filename
            counter = 1
            while os.path.exists(os.path.join(UPLOAD_DIR, dest_filename)):
                dest_filename = f"{name}_{counter}{ext}"
                counter += 1
            dest_path = os.path.join(UPLOAD_DIR, dest_filename)
            try:
                with open(dest_path, 'wb') as out_file:
                    out_file.write(fi.get('content') or b'')
            except Exception:
                # Skip file if cannot write
                continue
            saved_images.append(dest_filename)
        # Only record design if at least one file was saved
        if saved_images:
            designs[design_id] = {
                'images': saved_images,
                'comments': []
            }
            self._save_designs(designs)
        # Redirect back to index
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def _handle_comment(self) -> None:
        """Handle top-level comment submissions for a design."""
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        params = urllib.parse.parse_qs(body, keep_blank_values=True)
        design_id = params.get('design_id', [None])[0]
        comment = params.get('comment', [''])[0].strip()
        if not design_id or not comment:
            # Missing required fields; redirect without saving
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            return
        designs = self._load_designs()
        record = designs.get(design_id)
        if record is None:
            # Design not found; just redirect
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            return
        # Append new comment object
        record.setdefault('comments', [])
        record['comments'].append({'text': comment, 'replies': []})
        self._save_designs(designs)
        # Redirect back to index
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def _handle_reply(self) -> None:
        """Handle reply submissions to existing comments."""
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        params = urllib.parse.parse_qs(body, keep_blank_values=True)
        design_id = params.get('design_id', [None])[0]
        reply_text = params.get('reply', [''])[0].strip()
        idx_str = params.get('comment_index', [None])[0]
        if not design_id or not reply_text or idx_str is None:
            # Missing required fields; redirect
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            return
        try:
            idx = int(idx_str)
        except Exception:
            idx = -1
        designs = self._load_designs()
        record = designs.get(design_id)
        if not record:
            # Design not found
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            return
        comments = record.setdefault('comments', [])
        if 0 <= idx < len(comments):
            comment_obj = comments[idx]
            if isinstance(comment_obj, dict):
                comment_obj.setdefault('replies', [])
                comment_obj['replies'].append(reply_text)
            else:
                comments[idx] = {'text': str(comment_obj), 'replies': [reply_text]}
        self._save_designs(designs)
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def _handle_delete(self) -> None:
        """Handle deletion of an uploaded design and its comments."""
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        params = urllib.parse.parse_qs(body, keep_blank_values=True)
        design_id = params.get('design_id', [None])[0]
        if not design_id:
            # Nothing to delete
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            return
        designs = self._load_designs()
        record = designs.pop(design_id, None)
        if record:
            # Delete associated image files
            for img in record.get('images', []):
                path = os.path.join(UPLOAD_DIR, os.path.basename(img))
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
            self._save_designs(designs)
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

    # ------------------------------------------------------------------
    # Design data helpers (new format)
    # ------------------------------------------------------------------
    def _load_designs(self) -> dict:
        """
        Load design data from disk. The return value is a dictionary
        mapping design identifiers to a record containing a list of
        image filenames and a list of comment objects. Comment objects
        contain a ``text`` field and a list of ``replies``.

        Backwards compatibility: If the file contains the old format
        (mapping from image filename to a list of comments), it will
        automatically be converted to the new format on load.
        """
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
            except Exception:
                return {}
            designs: dict[str, dict] = {}
            for key, value in raw.items():
                # If value already has 'images', assume new format
                if isinstance(value, dict) and 'images' in value:
                    # Ensure nested comments have correct structure
                    images = value.get('images', [])
                    comments_list = value.get('comments', [])
                    new_comments = []
                    for entry in comments_list:
                        if isinstance(entry, dict):
                            text = entry.get('text', '')
                            replies = list(entry.get('replies', []))
                        else:
                            text = str(entry)
                            replies = []
                        new_comments.append({'text': text, 'replies': replies})
                    designs[key] = {'images': list(images), 'comments': new_comments}
                else:
                    # Old format: key is filename, value is list of comments
                    img = key
                    comments_list = value if isinstance(value, list) else []
                    new_comments = []
                    for entry in comments_list:
                        if isinstance(entry, dict):
                            text = entry.get('text', '')
                            replies = list(entry.get('replies', []))
                        else:
                            text = str(entry)
                            replies = []
                        new_comments.append({'text': text, 'replies': replies})
                    designs[img] = {'images': [img], 'comments': new_comments}
            return designs
        return {}

    def _save_designs(self, data: dict) -> None:
        """Persist design data to disk as JSON."""
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
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
            if filename is not None:
                # File upload: dictionary with filename and binary content
                item: object = {'filename': filename, 'content': payload or b''}
            else:
                # Regular form field: decode bytes to string
                if isinstance(payload, (bytes, bytearray)):
                    value = payload.decode('utf-8', errors='ignore')
                else:
                    value = payload
                item = value
            # Accumulate multiple entries for the same field name
            existing = result.get(name)
            if existing is None:
                result[name] = item
            else:
                # If a previous value exists, convert to list and append
                if not isinstance(existing, list):
                    result[name] = [existing, item]
                else:
                    existing.append(item)
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
