#!/usr/bin/env python3

import argparse
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from PIL import Image

from db import DB, PreviewsDB, bad_resource_sha1s

sys.path.insert(0, "tools")
import fishlabs_obfuscation
from render_obj import render_obj

MIN_VERSION = 4
VERSION = 5

# v5: add model orientation information in DB

parser = argparse.ArgumentParser()
parser.add_argument("db")
parser.add_argument("workdir", type=Path)
parser.add_argument("--resource")
parser.add_argument("jars", nargs="+", type=Path)

args = parser.parse_args()

rel_full_dir = Path("full")
rel_thumbs_dir = Path("thumbs")

workdir = args.workdir
workdir.mkdir(exist_ok=True)
(workdir / rel_full_dir).mkdir(exist_ok=True)
(workdir / rel_thumbs_dir).mkdir(exist_ok=True)

db = DB(args.db)
previews_db = PreviewsDB(workdir / "previews.sqlite")


def stream_hash(f):
    h = hashlib.sha1()

    for b in iter(lambda: f.read(128 * 1024), b""):
        h.update(b)

    return h.hexdigest()


def render_mbac(title, path, mbac, sha1, rel_output_path, is_thumb, resolution):
    texture_sha1 = db.find_texture_sha1_for_model(title, path)

    if texture_sha1 is not None:
        # TODO: eventually db.find_texture_filename_for_model after previewsDB populated
        texture_path = workdir / rel_full_dir / f"{texture_sha1}.png"
    else:
        texture_path = None

    # TODO: search by exact resolution instead
    record = previews_db.get_mbac_preview(sha1, is_thumb)

    axis_forward, axis_up = db.find_default_model_orientation_for_title(title)
    if axis_forward is None:
        axis_forward = "-Z"
    if axis_up is None:
        axis_up = "Y"

    output_path = workdir / rel_output_path

    if (
        record
        and record["version"] >= MIN_VERSION
        and record["texture_sha1"] == texture_sha1
        and record["axis_forward"] == axis_forward
        and record["axis_up"] == axis_up
        and output_path.is_file()
    ):
        print("UP-TO-DATE", rel_output_path)
        return

    with open("tmp.mbac", "wb") as f:
        f.write(mbac)

    print(
        f"RENDER title={title} path={path} {resolution=} {is_thumb=} texture_path={texture_path} {axis_forward=} {axis_up=}"
    )
    # TODO: just import the function
    subprocess.check_call(["tools/mbac2obj.py", "tmp.mbac", "vertexdump.obj"])
    render_obj(
        "vertexdump.obj",
        "preview",
        texture=texture_path,
        resolution=resolution,
        axis_forward=axis_forward,
        axis_up=axis_up,
    )
    os.rename("preview0000.png", output_path)

    previews_db.add_mbac_preview(
        sha1=sha1,
        thumb=is_thumb,
        filename=str(rel_output_path),
        width=resolution[0],
        height=resolution[1],
        version=VERSION,
        texture_sha1=texture_sha1,
        axis_forward=axis_forward,
        axis_up=axis_up,
    )


# images first to ensure we have textures
for path in args.jars:
    with zipfile.ZipFile(path, mode="r") as z:
        for info in z.infolist():
            ext = Path(info.filename).suffix.upper()

            if ext == ".BMP" or ext == ".PNG":
                with z.open(info.filename, "r") as f:
                    data = f.read()
                    f.seek(0)
                    sha1 = stream_hash(f)

                if (workdir / rel_thumbs_dir / (sha1 + ".png")).is_file() and (
                    workdir / rel_full_dir / (sha1 + ".png")
                ).is_file():
                    continue

                data = fishlabs_obfuscation.normalize(data, ext)

                print("PREVIEW", info, data[-8:])
                image = Image.open(io.BytesIO(data))
                image.save(workdir / rel_full_dir / (sha1 + ".png"))
                image.thumbnail((256, 144))
                image.save(workdir / rel_thumbs_dir / (sha1 + ".png"))

# previews

for path in args.jars:
    title = path.parent.name

    with zipfile.ZipFile(path, mode="r") as z:
        for info in z.infolist():
            if args.resource and info.filename != args.resource:
                continue

            ext = Path(info.filename).suffix.upper()

            if ext == ".MBAC":
                with z.open(info.filename, "r") as f:
                    mbac = f.read()
                    f.seek(0)
                    sha1 = stream_hash(f)

                if sha1 not in bad_resource_sha1s:
                    mbac = fishlabs_obfuscation.normalize(mbac, ext)
                    render_mbac(
                        title,
                        info.filename,
                        mbac,
                        sha1,
                        rel_thumbs_dir / (sha1 + ".png"),
                        is_thumb=True,
                        resolution=(256, 144),
                    )

# full-size renders

for path in args.jars:
    title = path.parent.name

    with zipfile.ZipFile(path, mode="r") as z:
        for info in z.infolist():
            if args.resource and info.filename != args.resource:
                continue

            ext = Path(info.filename).suffix.upper()

            if ext == ".MBAC":
                with z.open(info.filename, "r") as f:
                    mbac = f.read()
                    f.seek(0)
                    sha1 = stream_hash(f)

                if sha1 not in bad_resource_sha1s:
                    mbac = fishlabs_obfuscation.normalize(mbac, ext)
                    render_mbac(
                        title,
                        info.filename,
                        mbac,
                        sha1,
                        rel_full_dir / (sha1 + ".png"),
                        is_thumb=False,
                        resolution=(1280, 720),
                    )
