#!/bin/sh
# Locally build a merged package from an original DEB obtained legitimately.
set -eu
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo 'Usage: ./scripts/build.sh /path/to/smartnotificationsios16_v1.0_iphoneos-arm64.deb [output_directory]' >&2
    exit 2
fi
SOURCE_DEB=$1
OUT_DIR=${2:-.}
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ ! -f "$SOURCE_DEB" ]; then
    echo "Not found: $SOURCE_DEB" >&2
    exit 1
fi
mkdir -p "$OUT_DIR"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
dpkg-deb -R "$SOURCE_DEB" "$WORK/package"
if ! grep -q '^Package: smartnotificationsios16$' "$WORK/package/DEBIAN/control"; then
    echo 'Unexpected package identifier; supply the original SmartNotifications iOS16 DEB.' >&2
    exit 1
fi
if ! tr -d '\r' < "$WORK/package/DEBIAN/control" | grep -q '^Architecture: iphoneos-arm64$'; then
    echo 'Expected an iOS rootless (iphoneos-arm64) original DEB.' >&2
    exit 1
fi
cp "$ROOT/debian/control" "$WORK/package/DEBIAN/control"
cp "$ROOT/debian/postinst" "$WORK/package/DEBIAN/postinst"
cp "$ROOT/debian/postrm" "$WORK/package/DEBIAN/postrm"
chmod 755 "$WORK/package/DEBIAN/postinst" "$WORK/package/DEBIAN/postrm"
mkdir -p "$WORK/package/var/jb/usr/libexec/smartnotificationsios16-fixed"
cp "$ROOT/scripts/repair.sh" "$WORK/package/var/jb/usr/libexec/smartnotificationsios16-fixed/repair"
chmod 755 "$WORK/package/var/jb/usr/libexec/smartnotificationsios16-fixed/repair"
# Files are unpacked first; postinst assigns mobile ownership to writable folders.
for d in SmartNotifications-plist SnoozedNotifications SmartNotifications; do
    chmod 755 "$WORK/package/var/jb/Library/Application Support/$d"
done
OUTPUT="$OUT_DIR/SmartNotifications-iOS16-Fixed_1.0.1_iphoneos-arm64.deb"
dpkg-deb --build --root-owner-group "$WORK/package" "$OUTPUT"
echo "Built $OUTPUT"
