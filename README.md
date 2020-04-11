# mbac-gallery

## Usage

```
DB=mbac-gallery.sqlite
OUTDIR=out/

mkdir -p $OUTDIT
./analysis/build_db.py $DB game1.jar game2.jar ...
./analysis/update_previews.py $DB $OUTDIR game1.jar game2.jar ...
./analysis/make_html.py $DB $OUTDIR
```

## Special thanks

- [Durik256](https://github.com/Durik256) for texture mappings for Stalker
- Blender, sqlite
- https://purecss.io/
