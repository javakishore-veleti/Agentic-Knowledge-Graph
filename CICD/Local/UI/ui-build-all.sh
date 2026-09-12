#!/usr/bin/env bash
# Production build of each portal, independently. Mirrors the per-app CI lane.
. "$(dirname "${BASH_SOURCE[0]}")/_ports.sh"

for app in $APPS; do
  echo "==> building $app"
  ( cd "$(path_of "$app")" && npx ng build --configuration production )
done
echo "artifacts:"
for app in $APPS; do echo "  Portals/$app/dist/$app"; done
