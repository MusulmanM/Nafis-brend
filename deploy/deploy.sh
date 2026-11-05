#!/usr/bin/env bash
# =============================================================================
# Loyihani kompyuterdan AWS (Ubuntu) serverga joylash.
#
#   bash deploy/deploy.sh ubuntu@SERVER_IP /yo'l/kalit.pem [domen]
#
# Domen berilmasa, bepul vaqtinchalik domen ishlatiladi:
#   SERVER_IP = 13.50.1.2  ->  13-50-1-2.sslip.io
# (sslip.io — ro'yxatdan o'tishsiz ishlaydigan xizmat: domen nomidagi IP
#  manzilga yo'naltiradi.)
#
# Qayta ishga tushirish xavfsiz: kod yangilanadi, server bazasi (db.sqlite3)
# va .env fayli o'zgarmaydi.
# =============================================================================
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Ishlatish: bash deploy/deploy.sh ubuntu@SERVER_IP /yo'l/kalit.pem [domen]"
  exit 1
fi

TARGET="$1"          # masalan: ubuntu@13.50.1.2
KEY="$2"             # AWS'dan yuklab olingan .pem kalit
DOMAIN="${3:-}"
HOST="${TARGET#*@}"
APP_DIR=/opt/nafis

if [ -z "$DOMAIN" ]; then
  if [[ ! "$HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Vaqtinchalik domen uchun server IP manzili kerak (masalan ubuntu@13.50.1.2)."
    exit 1
  fi
  DOMAIN="${HOST//./-}.sslip.io"
fi

chmod 600 "$KEY"   # ssh kalit faylni faqat egasi o'qiy olishini talab qiladi
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new"
cd "$(dirname "$0")/.."

echo "==> Server: $TARGET  |  Domen: $DOMAIN"
$SSH "$TARGET" "sudo mkdir -p $APP_DIR && sudo chown \$(id -un): $APP_DIR"

echo "==> Kod yuklanmoqda..."
# Server bazasi, .env, virtual muhit va loglar serverda qoladi (o'chirilmaydi)
rsync -az --delete -e "$SSH" \
  --exclude ".git" --exclude ".venv" --exclude "__pycache__" --exclude "*.pyc" \
  --exclude "db.sqlite3" --exclude ".env" --exclude "staticfiles" --exclude "*.log" \
  ./ "$TARGET:$APP_DIR/"

echo "==> Server sozlanmoqda..."
$SSH "$TARGET" "bash $APP_DIR/deploy/setup_server.sh '$DOMAIN' '$HOST'"
