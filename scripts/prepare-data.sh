#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)

if [ ! -f "$project_dir/config.ini" ]; then
    echo "Copy config.ini.sample to config.ini and fill in your credentials first." >&2
    exit 1
fi

umask 077
mkdir -p "$project_dir/data"

# Seed persistent container state from the existing local installation once.
# Never overwrite tokens or playlist IDs already updated by the container.
for filename in .cache playlists.json; do
    if [ -f "$project_dir/$filename" ] && [ ! -e "$project_dir/data/$filename" ]; then
        cp -- "$project_dir/$filename" "$project_dir/data/$filename"
    fi
done
