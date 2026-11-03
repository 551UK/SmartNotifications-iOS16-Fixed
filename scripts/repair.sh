#!/bin/sh
# SmartNotifications iOS16 preference repair for rootless iOS 16.
# Only acts on SmartNotifications directories; existing .plist files are kept.
set -eu

jb=/var/jb
support="$jb/Library/Application Support"
prefs="$support/SmartNotifications-plist"
snoozes="$support/SnoozedNotifications"
sounds="$support/SmartNotifications"

# The original package creates these directories under _installd, preventing
# the mobile user (including Settings) from creating and updating preferences.
for folder in "$prefs" "$snoozes" "$sounds"; do
    if [ -L "$folder" ]; then
        echo "SmartNotifications iOS16 Fixed: skipping unexpected directory symlink: $folder" >&2
        continue
    fi
    mkdir -p "$folder"
    chown -R mobile:mobile "$folder"
    find "$folder" -type d -exec chmod 0755 '{}' ';'
    find "$folder" -type f -exec chmod u+rw '{}' ';'
done

# The original preference code refers to both locations for allApps.plist.
# Alias only the relevant leaf directory instead of changing unrelated paths.
legacy_parent="$jb/Application Support"
legacy_prefs="$legacy_parent/SmartNotifications-plist"
marker_dir="$jb/var/lib/com.551uk.smartnotificationsfix"

if [ ! -e "$legacy_prefs" ] && [ ! -L "$legacy_prefs" ]; then
    mkdir -p "$legacy_parent"
    ln -s "$prefs" "$legacy_prefs"
    mkdir -p "$marker_dir"
    : > "$marker_dir/created-alias"
elif [ -L "$legacy_prefs" ]; then
    if [ "$(readlink "$legacy_prefs")" != "$prefs" ]; then
        echo "SmartNotifications iOS16 Fixed: existing unrelated alias left untouched: $legacy_prefs" >&2
    fi
else
    echo "SmartNotifications iOS16 Fixed: existing alternate preference folder left untouched: $legacy_prefs" >&2
fi

echo 'SmartNotifications iOS16 Fixed: preference folders repaired.'
