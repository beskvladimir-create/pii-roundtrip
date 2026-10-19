#!/usr/bin/env bash
# Packs dist/pii-roundtrip.app into dist/pii-roundtrip-<version>.dmg with an Applications shortcut
# and first-launch instructions (the app is not signed by Apple yet).
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-0.3.0}"
STAGE="$(mktemp -d)"
cp -R dist/pii-roundtrip.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp build/licenses/THIRD_PARTY_NOTICES.txt "$STAGE/Licences · Лицензии.txt"
cat > "$STAGE/Как открыть · How to open.txt" <<'TXT'
pii-roundtrip

1. Перетащите pii-roundtrip в папку «Программы».
2. При первом запуске macOS предупредит о неизвестном разработчике: программа пока не подписана сертификатом Apple.
3. Откройте «Системные настройки», раздел «Конфиденциальность и безопасность», и нажмите «Всё равно открыть» рядом с сообщением о pii-roundtrip. Это нужно один раз.

Программа работает без интернета и никуда не отправляет ваши данные: https://pii-roundtrip.besk.tech/kuda-uhodyat-dannye/

---

1. Drag pii-roundtrip into Applications.
2. On first launch macOS warns about an unidentified developer: the app is not yet signed with an Apple certificate.
3. Open System Settings, go to Privacy & Security, and click Open Anyway next to the message about pii-roundtrip. You only need to do this once.

The app works offline and sends your data nowhere.
TXT
OUT="dist/pii-roundtrip-${VERSION}.dmg"
rm -f "$OUT"
hdiutil create -volname "pii-roundtrip ${VERSION}" -srcfolder "$STAGE" -ov -format ULMO -fs HFS+ "$OUT" >/dev/null
rm -rf "$STAGE"
shasum -a 256 "$OUT"
