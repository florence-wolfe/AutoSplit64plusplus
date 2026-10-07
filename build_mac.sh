#!/bin/sh
# Builds dist/AutoSplit64++/ containing AutoSplit64++.app and its resources.
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

# Replace the app and its resources, but keep settings, routes and generated reset templates
mkdir -p "dist/$NAME/routes" "dist/$NAME/templates"
rm -rf "dist/$NAME/$NAME.app" "dist/$NAME/logic" "dist/$NAME/resources"
cp -R "$WORK/dist/$NAME.app" logic resources defaults.ini "dist/$NAME/"
rsync -a --ignore-existing routes/ "dist/$NAME/routes/"
rsync -a --ignore-existing templates/ "dist/$NAME/templates/"

echo "Built dist/$NAME/$NAME.app"
