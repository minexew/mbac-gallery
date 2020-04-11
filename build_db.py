#!/usr/bin/env python3

import argparse
from datetime import datetime
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from PIL import Image

from db import DB, bad_resource_sha1s

# TODO: proper dependency management
sys.path.insert(0, "tools")
import fishlabs_obfuscation
from render_obj import render_obj

parser = argparse.ArgumentParser()
parser.add_argument("db", type=Path)
parser.add_argument("jars", nargs="+", type=Path)
args = parser.parse_args()

db = DB(args.db)


def file_hash(path):
    h = hashlib.sha1()

    with open(path, "rb", buffering=0) as f:
        for b in iter(lambda: f.read(128 * 1024), b""):
            h.update(b)

    return h.hexdigest()


def stream_hash(f):
    h = hashlib.sha1()

    for b in iter(lambda: f.read(128 * 1024), b""):
        h.update(b)

    return h.hexdigest()


def read_manifest(z):
    manifest = {}

    try:
        with z.open("META-INF/MANIFEST.MF", "r") as manifest_file:
            for line in manifest_file:
                line = line.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    delim = line.index(":")
                except Exception:
                    continue
                [key, value] = line[:delim], line[delim + 1 :]
                manifest[key.strip()] = value.strip()
    except KeyError:
        with z.open("META-INF/manifest.mf", "r") as manifest_file:
            for line in manifest_file:
                line = line.decode().strip()
                if not line:
                    continue
                try:
                    delim = line.index(":")
                except Exception:
                    continue
                [key, value] = line[:delim], line[delim + 1 :]
                manifest[key.strip()] = value.strip()

    return manifest


all_bins = []

for path in args.jars:
    print("scan", path, file=sys.stderr)

    title = Path(path).parts[-2]
    if title == "Other":
        continue

    size = os.stat(path).st_size
    jar_hash = file_hash(path)

    resource_exts = {".BMP", ".MBAC", ".PNG"}

    with zipfile.ZipFile(path, mode="r") as z:
        manifest = read_manifest(z)
        assert "MIDlet-Name" in manifest

        contents_size = 0
        h = hashlib.sha1()

        all_exts = set()
        obfuscation = None
        flags = set()

        widest_image = None
        tallest_image = None
        detected_m3g = 0
        detected_mascot = 0

        min_timestamp = None
        max_timestamp = None

        for info in z.infolist():
            ext = Path(info.filename).suffix.upper()
            all_exts.add(ext)

            timestamp = datetime(*info.date_time)

            if min_timestamp is None or timestamp < min_timestamp:
                min_timestamp = timestamp

            if max_timestamp is None or timestamp < max_timestamp:
                max_timestamp = timestamp

            if "MANIFEST.MF" not in info.filename.upper():
                contents_size += info.file_size

                with z.open(info.filename, "r") as f:
                    for b in iter(lambda: f.read(128 * 1024), b""):
                        h.update(b)

            if ext == ".M3G":
                detected_m3g += 1
                flags.add("M3G")
            elif ext == ".MBAC":
                detected_mascot += 1
                flags.add("MASCOT")

            if not obfuscation and (ext == ".BMP" or ext == ".MBAC"):
                with z.open(info.filename, "r") as f:
                    all_data = f.read()

                    detect = fishlabs_obfuscation.is_obfuscated(ext, all_data)
                    if detect is True:
                        obfuscation = True

            width, height = None, None

            with z.open(info.filename, "r") as f:
                try:
                    data = fishlabs_obfuscation.normalize(f.read(), ext)
                    img = Image.open(io.BytesIO(data))
                    width, height = img.size

                    if widest_image is None or img.size[0] > widest_image[0]:
                        widest_image = (img.size[0], img.size[1], info.filename)

                    if tallest_image is None or img.size[1] > tallest_image[1]:
                        tallest_image = (img.size[0], img.size[1], info.filename)
                except IOError:
                    pass
                except Image.DecompressionBombError:
                    print(info.filename, ": PIL.Image.DecompressionBombError", file=sys.stderr)

            if ext in resource_exts:
                with z.open(info.filename, "r") as f:
                    sha1 = stream_hash(f)

                if sha1 not in bad_resource_sha1s:
                    db.add_resource(
                        jar_sha1=jar_hash,
                        sha1=sha1,
                        filename=info.filename,
                        size=info.file_size,
                        type=ext,
                        width=width,
                        height=height,
                    )

        # retrieve MIDlet icon
        icon_path = manifest["MIDlet-1"].split(",")[1].strip()
        if icon_path[0] == "/":
            icon_path = icon_path[1:]
        with z.open(icon_path, "r") as f:
            icon_data = f.read()

        contents_hash = h.hexdigest()
        num_files = len(z.infolist())

    name = Path(path).parts[-1]
    filetypes = " ".join(sorted(list(all_exts)))

    db.add_jar(
        title_id=db.get_title_id(title),
        filename=name,
        size=size,
        sha1=jar_hash,
        detected_fishlabs_obfuscation=obfuscation,
        detected_mascot=detected_mascot,
        detected_m3g=detected_m3g,
        filetypes=filetypes,
        widest_image=str(widest_image),
        tallest_image=str(tallest_image),
        min_timestamp=min_timestamp,
        max_timestamp=max_timestamp,
        icon=icon_data,
    )

db.close()
