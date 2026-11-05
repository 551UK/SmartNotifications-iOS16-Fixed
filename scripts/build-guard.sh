#!/bin/sh
# Repack the user's existing combined package and add a narrow SpringBoard guard.
set -eu
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 /path/to/original.deb /path/to/guard.dylib /output/dir" >&2
    exit 2
fi
ORIGINAL=$1
GUARD=$2
OUT=$3
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
[ -s "$ORIGINAL" ] || exit 1
[ -s "$GUARD" ] || exit 1
mkdir -p "$OUT"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
sh "$ROOT/scripts/build.sh" "$ORIGINAL" "$WORK"
BASE="$WORK/SmartNotifications-iOS16-Fixed_1.0.1_iphoneos-arm64.deb"
dpkg-deb -R "$BASE" "$WORK/package"
LIBS="$WORK/package/var/jb/Library/MobileSubstrate/DynamicLibraries"
mkdir -p "$LIBS"
cp "$GUARD" "$LIBS/zzSmartNotificationsFakeGuard.dylib"
chmod 0644 "$LIBS/zzSmartNotificationsFakeGuard.dylib"
cp "$ROOT/fix/zzSmartNotificationsFakeGuard.plist" "$LIBS/zzSmartNotificationsFakeGuard.plist"
chmod 0644 "$LIBS/zzSmartNotificationsFakeGuard.plist"
sed -i 's/^Version: 1\.0\.1$/Version: 1.0.2/' "$WORK/package/DEBIAN/control"
grep -q '^Version: 1.0.2$' "$WORK/package/DEBIAN/control"
OUTPUT="$OUT/SmartNotifications-iOS16-Fixed_1.0.2_iphoneos-arm64.deb"
dpkg-deb --build --root-owner-group "$WORK/package" "$OUTPUT"
echo "Built $OUTPUT"
