#!/usr/bin/env bash
# =============================================================================
# SERVERDA ishlaydi (Ubuntu). Odatda deploy.sh uni o'zi chaqiradi:
#   bash /opt/nafis/deploy/setup_server.sh DOMEN [SERVER_IP]
#
# Nima qiladi:
#   1) python, nginx, certbot o'rnatadi;
#   2) virtual muhit (.venv) va kutubxonalar + gunicorn;
#   3) .env (faqat birinchi marta: tasodifiy SECRET_KEY, DEBUG=False);
#   4) migratsiyalar va statik fayllar;
#   5) boshliq akkaunti (faqat birinchi marta, tasodifiy parol bilan);
#   6) gunicorn (systemd xizmati) + nginx;
#   7) HTTPS sertifikat (Let's Encrypt) va doimiy buyurtmalar uchun cron.
# =============================================================================
set -euo pipefail

DOMAIN="$1"
IP="${2:-}"
APP_DIR=/opt/nafis
APP_PORT=8000
RUN_USER="$(id -un)"
cd "$APP_DIR"

if ! command -v apt-get >/dev/null; then
  echo "Bu skript Ubuntu/Debian server uchun yozilgan."
  exit 1
fi

echo "==> 1/7 Kerakli dasturlar"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  python3 python3-venv python3-pip nginx certbot python3-certbot-nginx >/dev/null

echo "==> 2/7 Python muhiti"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt gunicorn

echo "==> 3/7 .env"
if [ ! -f .env ]; then
  SECRET=$(.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as g; print(g())")
  HOSTS="$DOMAIN"
  [ -n "$IP" ] && [ "$IP" != "$DOMAIN" ] && HOSTS="$HOSTS,$IP"
  cat > .env <<EOF
SECRET_KEY='$SECRET'
DEBUG=False
ALLOWED_HOSTS=$HOSTS
CSRF_TRUSTED_ORIGINS=https://$DOMAIN,http://$DOMAIN
SECURE_COOKIES=False
BEHIND_PROXY=True
SITE_NAME=Nafis
DB_ENGINE=sqlite
EOF
  chmod 600 .env
  echo "    .env yaratildi"
else
  echo "    .env bor — o'zgartirilmadi"
fi

echo "==> 4/7 Ma'lumotlar bazasi va statik fayllar"
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput -v0

echo "==> 5/7 Boshliq akkaunti"
.venv/bin/python manage.py shell -v0 -c "
import secrets
from accounts.models import User
if User.objects.filter(role=User.Role.BOSS).exists():
    print('    boshliq akkaunti bor — o\'zgartirilmadi')
else:
    password = secrets.token_urlsafe(9)
    User.objects.create_superuser('admin', password=password, first_name='Boshliq')
    with open('$HOME/nafis_admin_parol.txt', 'w') as f:
        f.write('login: admin\nparol: ' + password + '\n')
    print('    YANGI BOSHLIQ: login admin | parol ' + password)
"
[ -f "$HOME/nafis_admin_parol.txt" ] && chmod 600 "$HOME/nafis_admin_parol.txt"

echo "==> 6/7 Gunicorn va Nginx"
sudo tee /etc/systemd/system/nafis.service >/dev/null <<EOF
[Unit]
Description=Nafis (Django + gunicorn)
After=network.target

[Service]
User=$RUN_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:$APP_PORT --workers 3 --timeout 60
Restart=always

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable -q nafis
sudo systemctl restart nafis

sudo tee /etc/nginx/sites-available/nafis >/dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN ${IP};
    client_max_body_size 10M;

    # CSS, JS — to'g'ridan-to'g'ri nginx beradi (tezroq)
    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 7d;
    }

    # Qolgan hamma so'rovlar — Django (gunicorn)
    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
sudo ln -sf /etc/nginx/sites-available/nafis /etc/nginx/sites-enabled/nafis
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t -q
sudo systemctl reload nginx

echo "==> 7/7 HTTPS va cron"
if sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
     --register-unsafely-without-email --redirect -q; then
  sed -i 's/^SECURE_COOKIES=.*/SECURE_COOKIES=True/' .env
  sudo systemctl restart nafis
  URL="https://$DOMAIN"
else
  # HTTP'da "secure" cookie ishlamaydi (login bo'lmaydi), shuning uchun o'chiramiz
  sed -i 's/^SECURE_COOKIES=.*/SECURE_COOKIES=False/' .env
  sudo systemctl restart nafis
  echo "    DIQQAT: HTTPS sertifikat olinmadi — sayt HTTP orqali ishlaydi."
  echo "    (AWS Security Group'da 80 va 443 portlar ochiqligini tekshiring.)"
  URL="http://$DOMAIN"
fi

# Doimiy buyurtmalar har kuni 01:00 UTC (= 06:00 Toshkent) da yaratiladi
CRON="0 1 * * * cd $APP_DIR && .venv/bin/python manage.py create_recurring_orders >> $APP_DIR/recurring.log 2>&1"
( crontab -l 2>/dev/null | grep -v create_recurring_orders || true; echo "$CRON" ) | crontab -

sleep 1
CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: $DOMAIN" http://127.0.0.1:$APP_PORT/login/ || true)
echo
echo "============================================================"
echo " Tayyor: $URL"
echo " Gunicorn javobi (/login/): $CODE"
echo " Boshliq paroli serverda: ~/nafis_admin_parol.txt"
echo "============================================================"
