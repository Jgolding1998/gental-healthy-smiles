# Gental Healthy Smiles – Logo Feedback Site

This repository contains a simple web application that allows a designer to
upload logo concepts and collect feedback from others.  The site is aimed at
showcasing up to six (or more) logo designs for **Gental Healthy Smiles**, but
it can be adapted for any project that needs image uploads and comments.

## Features

* **Image uploads** – Designers can upload new logo drafts through a form on
  the main page.  Files are stored in an `uploads/` directory on the server.
* **Public gallery** – Every uploaded design appears in a neat card layout
  with the image displayed at full width.
* **Feedback** – Under each design visitors can read previous comments and
  leave new feedback using a simple form.  Comments are stored in
  `comments.json` and persist across server restarts.
* **Clean, responsive design** – The included CSS uses a gentle blue colour
  palette suitable for a dental practice and scales gracefully on desktop and
  mobile screens.

## Quick start

> **Requirements:** Python 3.8 or later (no external libraries needed).

1. Make sure you have Python installed.  To check, run `python3 --version`.
2. From within this directory, start the development server:

   ```bash
   python3 server.py
   ```

   By default the server listens on port 8000.  You should see an output like:

   ```
   Serving on port 8000
   ```

3. Open your browser and navigate to [http://localhost:8000/](http://localhost:8000/).
4. Use the **Upload a New Design** form to add PNG, JPG or other image files.
   After uploading, the page refreshes and the new design appears in the
   gallery.
5. Visitors can add comments to each design via the **Leave your feedback**
   textarea.  Comments are appended to the list beneath the image.

## Deployment

This application uses Python’s built‑in HTTP server and is not intended
for high‑traffic production environments.  For a lightweight deployment
on platforms like **Render**, you can do the following:

1. In the Render dashboard, create a new **Web Service** and link it to
   the GitHub repository containing this code.
2. Choose an environment based on Python 3, leave the build command
   empty (none is needed) and set the **Start command** to:

   ```bash
   python3 server.py --bind 0.0.0.0 --port 10000
   ```

   (Render provides the environment variable `PORT`, so you may wish to
   substitute `--port $PORT`.)
3. Deploy the service.  Render will run the server and make your site
   publicly accessible.  Since Python’s `http.server` is single‑threaded,
   consider adding caching or placing it behind a proxy if traffic grows.

Alternatively, you can wrap the logic in a framework like Flask or
Express for scalability.  The provided code demonstrates the core
functionality without external dependencies.

## Customisation

* **Design palette** – Edit `static/styles.css` to adjust colours, fonts
  and layout.  The current palette uses pastel blues to evoke calm and
  cleanliness.
* **Validation** – The server trusts that uploaded files are images.
  For a production site you should validate MIME types and size to prevent
  misuse.
* **Data storage** – Comments are stored in a JSON file for simplicity.
  Consider using a database (e.g. SQLite) if you expect many comments or
  concurrent visitors.

## License

This project is provided under the MIT licence.  See `LICENSE` for details.
