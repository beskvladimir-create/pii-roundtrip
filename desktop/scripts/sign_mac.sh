#!/usr/bin/env bash
# Signs dist/pii-roundtrip.app with the Developer ID certificate and the hardened runtime, as Apple
# requires for notarisation: every Mach-O file inside first, then the bundle itself.
# Usage: scripts/sign_mac.sh [path/to/pii-roundtrip.app]
set -euo pipefail
cd "$(dirname "$0")/.."
APP="${1:-dist/pii-roundtrip.app}"
IDENTITY="${SIGN_IDENTITY:-Developer ID Application: Vladimir Beskorovainyi (93VF38C6GZ)}"
ENT="scripts/entitlements.plist"
n=0
while IFS= read -r -d '' f; do
  if file -b "$f" | grep -q "Mach-O"; then
    codesign --force --timestamp --options runtime --sign "$IDENTITY" "$f"
    n=$((n + 1))
  fi
done < <(find "$APP/Contents" -type f ! -path "*/Contents/MacOS/pii-roundtrip" -print0)
codesign --force --timestamp --options runtime --entitlements "$ENT" --sign "$IDENTITY" "$APP"
codesign --verify --deep --strict "$APP"
echo "signed $n nested files and the bundle: $APP"
