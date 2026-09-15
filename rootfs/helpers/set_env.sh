#!/bin/bash

# Loop over files in /var/run/environment and export them
for file in /var/run/environment/*; do
  [ -f "$file" ] || continue
  name="$(basename "$file")"
  # Preserve values with spaces or glob characters (e.g. database URLs).
  export "${name}=$(cat "$file")"
done