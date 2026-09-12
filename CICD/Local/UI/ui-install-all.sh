#!/usr/bin/env bash
# Install each portal's own dependencies. Two node_modules trees, by design.
. "$(dirname "${BASH_SOURCE[0]}")/_ports.sh"

for app in $APPS; do
  echo "==> installing $app"
  ( cd "$(path_of "$app")" && npm install )
done
echo "done"
