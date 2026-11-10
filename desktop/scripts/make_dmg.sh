#!/usr/bin/env bash
# Packs dist/pii-roundtrip.app into dist/pii-roundtrip-<version>.dmg with an Applications shortcut
# and short instructions, signs the image and, unless NOTARIZE=0, notarises and staples it.
# The app itself is signed and notarised before this step:
#   scripts/sign_mac.sh && scripts/notarize.sh dist/pii-roundtrip.app
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-0.3.0}"
STAGE="$(mktemp -d)"
ditto dist/pii-roundtrip.app "$STAGE/pii-roundtrip.app"
ln -s /Applications "$STAGE/Applications"
cp build/licenses/THIRD_PARTY_NOTICES.txt "$STAGE/Licences · Лицензии.txt"
cat > "$STAGE/Как открыть · How to open.txt" <<'TXT'
pii-roundtrip

1. Перетащите pii-roundtrip в папку «Программы».
2. Откройте программу. Она подписана сертификатом разработчика и проверена Apple, поэтому откроется сразу.

Программа работает без интернета и никуда не отправляет ваши данные: https://pii-roundtrip.besk.tech/kuda-uhodyat-dannye/

---

1. Drag pii-roundtrip into Applications.
2. Open it. The app is signed with a Developer ID certificate and notarised by Apple, so it opens straight away.

The app works offline and sends your data nowhere: https://pii-roundtrip.besk.tech/where-your-data-goes/
TXT
OUT="dist/pii-roundtrip-${VERSION}.dmg"
rm -f "$OUT"
hdiutil create -volname "pii-roundtrip ${VERSION}" -srcfolder "$STAGE" -ov -format ULMO -fs HFS+ "$OUT" >/dev/null
rm -rf "$STAGE"
codesign --force --timestamp --sign "${SIGN_IDENTITY:-Developer ID Application: Vladimir Beskorovainyi (93VF38C6GZ)}" "$OUT"
[[ "${NOTARIZE:-1}" == 1 ]] && scripts/notarize.sh "$OUT"
shasum -a 256 "$OUT"
