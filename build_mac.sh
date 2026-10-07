#!/bin/sh
# Builds dist/AutoSplit64plusplus/ containing AutoSplit64plusplus.app and its resources.
set -e
cd "$(dirname "$0")"
. .venv/bin/activate

NAME=AutoSplit64plusplus
WORK=build/mac

# Convert the PNG icon to .icns
mkdir -p "$WORK/as64plus.iconset"
for size in 16 32 128 256; do
    sips -z $size $size resources/gui/icons/as64plus.png --out "$WORK/as64plus.iconset/icon_${size}x${size}.png" >/dev/null
done
iconutil -c icns "$WORK/as64plus.iconset" -o "$WORK/as64plus.icns"

pyinstaller \
    --noconfirm \
    --name "$NAME" \
    --icon "$WORK/as64plus.icns" \
    --osx-bundle-identifier "local.autosplit64plusplus" \
    --windowed \
    --clean \
    --noupx \
    --workpath "$WORK" \
    --distpath "$WORK/dist" \
    AutoSplit64.py

rm -rf "dist/$NAME"
mkdir -p "dist/$NAME"
cp -R "$WORK/dist/$NAME.app" "dist/$NAME/"
cp -R logic resources routes templates defaults.ini "dist/$NAME/"

echo "Built dist/$NAME/$NAME.app"
