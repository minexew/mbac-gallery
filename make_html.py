#!/usr/bin/env python3

import argparse
import base64
import os
from pathlib import Path
import sys
import zipfile

from PIL import Image

from db import DB

parser = argparse.ArgumentParser()
parser.add_argument('db')
parser.add_argument("outputdir", type=Path)

args = parser.parse_args()

db = DB(args.db)

args.outputdir.mkdir(exist_ok=True)

full_dir = args.outputdir / "full"
thumbs_dir = args.outputdir / "thumbs"

# TODO: should obviously use Jinja or something
with open(args.outputdir / "index.html", "wt") as f:
    f.write('<link rel="stylesheet" href="https://unpkg.com/purecss@1.0.1/build/pure-min.css" integrity="sha384-oAOxQR6DkCoMliIh8yFnu25d7Eq/PHS21PClpwjOTeU2jRSq11vu66rf90/cZr47" crossorigin="anonymous">')

    # https://stackoverflow.com/a/1094933
    def sizeof_fmt(num, suffix='B'):
        for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
            if abs(num) < 1024.0:
                return "%3.1f%s%s" % (num, unit, suffix)
            num /= 1024.0
        return "%.1f%s%s" % (num, 'Yi', suffix)

    for title in db.titles():
        f.write(f"<h1><a href='{title + '.html'}'>{title}</a></h1>")

        f1 = f
        f = open(args.outputdir / (title + ".html"), "wt")

        # sort resources by path
        resources_by_path = dict()

        for res in db.resources(title_name=title):
            p = Path(res["filename"])
            try:
                resources_by_path[p.parent].append(res)
            except KeyError:
                resources_by_path[p.parent] = [res]

        f.write('<link rel="stylesheet" href="https://unpkg.com/purecss@1.0.1/build/pure-min.css" integrity="sha384-oAOxQR6DkCoMliIh8yFnu25d7Eq/PHS21PClpwjOTeU2jRSq11vu66rf90/cZr47" crossorigin="anonymous">')

        f.write(f"<h1>{title}</h1>")

        f.write("""<table class='pure-table'>
            <tr>
              <th></th><th>Filename</th><th>Size</th><th>MBAC files</th><th>M3G files</th><th>Date range</th><th>Filetypes</th>
            </tr>""")

        for jar in db.jars(title_name=title):
            f.write(f"""
                <tr>
                    <td><img src="data:image/png;base64,{base64.b64encode(jar["icon"]).decode()}"></td>
                   <td><p>{jar["filename"]}</p><p style="font-size: 10px; opacity: 0.5">{jar["sha1"]}</p></td>
                   <td>{sizeof_fmt(jar['size'])}</td>
                   <td>{jar['detected_mascot']}</td>
                   <td>{jar['detected_m3g']}</td>
                   <td>{jar['min_timestamp']}<br>{jar['max_timestamp']}</td>
                   <td>{jar['filetypes']}</td>
                </tr>
                """)

        f.write("</table>")

        def display_cell(f, res):
            f.write('<div class="pure-u-1-6" style="text-align: center">')

            full = (full_dir / f'{res["sha1"]}.png').is_file()
            # thumb = (thumbs_dir / f'{res["sha1"]}.png').is_file()

            if full:
                f.write(f'<a href="full/{res["sha1"]}.png">')
            f.write(f'<img src="thumbs/{res["sha1"]}.png">')
            if full:
                f.write('</a>')

            p = Path(res["filename"])
            f.write(f'<p style="font-size: 12px">{p.name}</p>')
            if res["width"] and res["height"]:
                f.write(f'<p style="font-size: 12px">{res["width"]} x {res["height"]}</p>')
            f.write(f'<p style="font-size: 10px; opacity: 0.5">{res["sha1"]}</p>')
            f.write('</div>')

        f.write("<h2>Models</h2>")

        for path, resources in resources_by_path.items():
            filtered = [res for res in resources if res["type"] == ".MBAC"]
            if not len(filtered): continue

            f.write(f"<h3>{path}</h3>")
            f.write('<div class="pure-g">')

            for res in filtered:
                display_cell(f, res)

            f.write("</div>")

        f.write("<h2>Textures</h2>")

        f.write('<div class="pure-g">')

        for res in db.resources(title_name=title):
            if res["type"] == ".BMP":
                display_cell(f, res)

        f.write("</div>")

        f.write("<h2>Images</h2>")

        f.write('<div class="pure-g">')

        for res in db.resources(title_name=title):
            if res["type"] == ".PNG":
                display_cell(f, res)

        f.write("</div>")

        f.close()
        f = f1

db.close()
