#!/bin/sh
# Builds dist/AutoSplit64++.app, which includes its resources and can be installed anywhere.
set -e
cd "$(dirname "$0")"
. .venv/bin/activate

NAME="AutoSplit64++"
WORK=build/mac

# Convert the PNG icon to .icns
mkdir -p "$WORK/as64plus.iconset"
for size in 16 32 128 256; do
    sips -z $size $size resources/gui/icons/as64plus.png --out "$WORK/as64plus.iconset/icon_${size}x${size}.png" >/dev/null
done
iconutil -c icns "$WORK/as64plus.iconset" -o "$WORK/as64plus.icns"

# Bundle the resources without files the app writes at runtime, like the capture preview
rm -rf "$WORK/resources"
rsync -a --exclude game_preview.png resources/ "$WORK/resources/"

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
    --add-data "logic:logic" \
    --add-data "$WORK/resources:resources" \
    --add-data "routes:routes" \
    --add-data "templates:templates" \
    --add-data "defaults.ini:." \
    AutoSplit64.py

rm -rf "dist/$NAME.app"
mkdir -p dist
cp -R "$WORK/dist/$NAME.app" dist/

echo "Built dist/$NAME.app"
