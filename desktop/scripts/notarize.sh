#!/usr/bin/env bash
# Sends a signed .app or .dmg to Apple's notary service, waits for the verdict and staples the ticket,
# so that macOS accepts the file without a network check. A .app is zipped for the upload.
# Needs the keychain profile made once with:
#   xcrun notarytool store-credentials pii-roundtrip --apple-id <Apple ID> --team-id 93VF38C6GZ
# Extra notarytool flags go in NOTARY_ARGS, e.g. NOTARY_ARGS=--no-s3-acceleration when the upload times out.
# Usage: scripts/notarize.sh dist/pii-roundtrip.app | dist/pii-roundtrip-1.0.0.dmg
set -euo pipefail
TARGET="$1"
PROFILE="${NOTARY_PROFILE:-pii-roundtrip}"
UPLOAD="$TARGET"
if [[ "$TARGET" == *.app ]]; then
  UPLOAD="$(mktemp -d)/$(basename "$TARGET" .app).zip"
  ditto -c -k --keepParent "$TARGET" "$UPLOAD"
fi
OUT="$(xcrun notarytool submit "$UPLOAD" --keychain-profile "$PROFILE" ${NOTARY_ARGS:-} --wait 2>&1)" || true
echo "$OUT"
if ! grep -q "status: Accepted" <<< "$OUT"; then
  echo "notarisation failed; see: xcrun notarytool log <id> --keychain-profile $PROFILE" >&2
  exit 1
fi
xcrun stapler staple "$TARGET"
[[ "$UPLOAD" != "$TARGET" ]] && rm -f "$UPLOAD"
echo "notarised and stapled: $TARGET"
