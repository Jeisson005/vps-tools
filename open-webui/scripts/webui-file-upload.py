#!/usr/bin/env python3
"""
Open WebUI File Bridge & Native Card Registrator.
Registers generated or modified files in Open WebUI database and uploads directory,
making them instantly accessible as authenticated native download cards in chat.
"""

import sys
import os
import shutil
import sqlite3
import uuid
import mimetypes
import hashlib
import time
import json

DATA_DIR = os.path.expanduser("~/vps-tools/open-webui/data/open-webui")
DB_PATH = os.path.join(DATA_DIR, "webui.db")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")


def register_file(file_path: str) -> dict:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    os.makedirs(UPLOADS_DIR, exist_ok=True)

    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    file_id = str(uuid.uuid4())
    dest_filename = f"{file_id}_{filename}"
    dest_path = os.path.join(UPLOADS_DIR, dest_filename)
    container_path = f"/app/backend/data/uploads/{dest_filename}"

    # Copy file to uploads dir
    shutil.copy2(file_path, dest_path)
    os.chmod(dest_path, 0o666)

    # Compute SHA256 hash
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    file_hash = sha256.hexdigest()

    # Determine content type
    content_type, _ = mimetypes.guess_type(filename)
    if not content_type:
        content_type = "application/octet-stream"

    meta = {
        "name": filename,
        "content_type": content_type,
        "size": file_size,
        "file_hash": file_hash,
        "data": {},
        "collection_name": f"file-{file_id}"
    }

    now = int(time.time())

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Find the primary admin user ID
    user_row = c.execute("SELECT id FROM user ORDER BY created_at ASC LIMIT 1").fetchone()
    user_id = user_row[0] if user_row else str(uuid.uuid4())

    c.execute(
        """
        INSERT INTO file (id, user_id, filename, meta, created_at, hash, data, updated_at, path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_id,
            user_id,
            filename,
            json.dumps(meta),
            now,
            file_hash,
            json.dumps({}),
            now,
            container_path
        )
    )

    conn.commit()
    conn.close()

    download_url = f"/api/v1/files/{file_id}/content"
    markdown_link = f"[📄 {filename}]({download_url})"

    return {
        "id": file_id,
        "filename": filename,
        "url": download_url,
        "markdown": markdown_link
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: webui-file-upload <path_to_file>")
        sys.exit(1)

    target_file = sys.argv[1]
    try:
        result = register_file(target_file)
        print(json.dumps(result, indent=2))
        print(f"\nMarkdown Card: {result['markdown']}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
