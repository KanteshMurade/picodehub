"""
project_store.py — makes admin-uploaded files survive Render's free-tier
restarts.

The problem: three local-disk locations hold admin-uploaded content --
  - PROJECTS_DIR      (catalog project.json, .ino sketch, cover image, firmware.bin)
  - RESOURCE_FILES_DIR (driver zips / PDFs uploaded under the Resources tab)
  - CUSTOM_FILES_DIR   (files an admin attaches when responding to a custom order)
Render's free-tier web services wipe local disk contents on every
restart, redeploy, or spin-down/spin-up cycle. Database rows (in
MongoDB) already survive that fine -- but any *file* saved only to disk
in these three folders would silently vanish.

The fix: every write into any of these three folders is mirrored into a
MongoDB collection (raw bytes, keyed by which folder + relative path it
came from) right after the write happens on disk. On every app boot,
before serving any requests, everything stored in Mongo is written back
out to disk first. Disk is treated purely as a fast, disposable cache;
MongoDB is the permanent source of truth. No route that *reads* these
files needs to change -- they keep reading straight off disk as before,
it's just guaranteed to already be there by the time a request arrives.
"""

import os
from bson.binary import Binary

from dbshim import get_raw_db

# Files larger than this are skipped from mirroring (defensive cap --
# catches an accidental huge upload before it blows through MongoDB's
# 16MB/document limit; nothing in this project should ever need to be
# this big).
_MAX_FILE_BYTES = 12 * 1024 * 1024

# One Mongo collection, one document per (root, subfolder) pair. "root"
# distinguishes which of the three base directories this came from, so a
# custom-request folder and a project folder can never collide even if
# they happened to share a name.
_COLLECTION = "project_files"


def save_folder(base_dir, root_label, subfolder_name):
    """Mirror every file under base_dir/subfolder_name into Mongo.
    Call this right after any admin write into that folder finishes.
    root_label distinguishes which base directory this is (e.g.
    "projects", "resources", "custom_uploads")."""
    folder_path = os.path.join(base_dir, subfolder_name)
    if not os.path.isdir(folder_path):
        return

    files = {}
    for root, _dirs, filenames in os.walk(folder_path):
        for fn in filenames:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, folder_path)
            try:
                size = os.path.getsize(full)
                if size > _MAX_FILE_BYTES:
                    print(f"[project_store] Skipping oversized file from backup: {root_label}/{subfolder_name}/{rel} ({size} bytes)")
                    continue
                with open(full, "rb") as f:
                    files[rel] = Binary(f.read())
            except OSError as e:
                print(f"[project_store] Could not read {full}: {e}")

    get_raw_db()[_COLLECTION].update_one(
        {"root": root_label, "folder": subfolder_name},
        {"$set": {"root": root_label, "folder": subfolder_name, "files": files}},
        upsert=True,
    )


def save_single_file(base_dir, root_label, relative_path):
    """Mirror one specific file (not a whole folder) into Mongo -- for
    admin uploads that live loose inside a shared directory rather than
    their own subfolder (e.g. resource_uploads/<uuid>_driver.zip)."""
    full = os.path.join(base_dir, relative_path)
    if not os.path.isfile(full):
        return
    try:
        size = os.path.getsize(full)
        if size > _MAX_FILE_BYTES:
            print(f"[project_store] Skipping oversized file from backup: {root_label}/{relative_path} ({size} bytes)")
            return
        with open(full, "rb") as f:
            content = Binary(f.read())
    except OSError as e:
        print(f"[project_store] Could not read {full}: {e}")
        return

    get_raw_db()[_COLLECTION].update_one(
        {"root": root_label, "folder": relative_path},
        {"$set": {"root": root_label, "folder": relative_path, "files": {".": content}, "single_file": True}},
        upsert=True,
    )


def delete_folder(root_label, subfolder_name):
    """Call this right after an admin deletes a mirrored folder/file from disk."""
    get_raw_db()[_COLLECTION].delete_one({"root": root_label, "folder": subfolder_name})


def restore_all(base_dir, root_label):
    """Call once at app startup, before serving requests, once per base
    directory (projects / resources / custom uploads). Recreates every
    folder or single file Mongo knows about for that root, so anything
    added after the last git deploy survives a restart. Safe to call even
    when nothing needs restoring yet."""
    try:
        docs = list(get_raw_db()[_COLLECTION].find({"root": root_label}))
    except Exception as e:
        print(f"[project_store] Could not reach MongoDB to restore '{root_label}': {e}")
        return

    restored = 0
    for doc in docs:
        subfolder_name = doc.get("folder")
        files = doc.get("files") or {}
        if not subfolder_name or not files:
            continue

        if doc.get("single_file"):
            content = files.get(".")
            if content is None:
                continue
            dest = os.path.join(base_dir, subfolder_name)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(bytes(content))
        else:
            folder_path = os.path.join(base_dir, subfolder_name)
            os.makedirs(folder_path, exist_ok=True)
            for rel, content in files.items():
                dest = os.path.join(folder_path, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(bytes(content))
        restored += 1

    if restored:
        print(f"[project_store] Restored {restored} item(s) for '{root_label}' from MongoDB.")


# --- Backwards-compatible aliases (used by earlier hooks in app.py for
#     the project catalog specifically) ---------------------------------

def save_project_folder(projects_dir, folder_name):
    save_folder(projects_dir, "projects", folder_name)


def delete_project_folder(folder_name):
    delete_folder("projects", folder_name)


def restore_all_project_folders(projects_dir):
    restore_all(projects_dir, "projects")
