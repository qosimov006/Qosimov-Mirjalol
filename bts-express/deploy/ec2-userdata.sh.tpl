#!/bin/bash
# EC2 birinchi ishga tushganda avtomatik bajariladi (user-data).
# Bu yerda PAROL YO'Q: user-data AWS konsolida ko'rinadi, shuning uchun faqat maxfiy bo'lmagan sozlamalar yoziladi.
set -euxo pipefail
exec > >(tee /var/log/bts-userdata.log) 2>&1

REGION=__REGION__
BUCKET=__BUCKET__
DB_HOST=__DB_HOST__
DB_SECRET=__DB_SECRET_ARN__
ADMIN_SECRET=__ADMIN_SECRET_ARN__
DOMAIN=__DOMAIN__

dnf install -y python3.11 python3.11-pip nginx amazon-cloudwatch-agent unzip
id bts &>/dev/null || useradd --system --home-dir /opt/bts-express --shell /sbin/nologin bts
mkdir -p /opt/bts-express /var/log/bts-express

# 1) Ilova paketi S3'dan (EC2 IAM roli orqali, hech qanday kalit kerak emas)
aws s3 cp "s3://$BUCKET/deploy/app.zip" /tmp/app.zip --region "$REGION"
unzip -oq /tmp/app.zip -d /opt/bts-express
python3.11 -m venv /opt/bts-express/venv
/opt/bts-express/venv/bin/pip install --no-cache-dir -r /opt/bts-express/requirements.txt
mkdir -p /opt/bts-express/data
chown -R bts:bts /opt/bts-express /var/log/bts-express

# 2) Sozlamalar (maxfiy emas). Parollar Secrets Manager'da, ilova ularni o'zi o'qiydi.
cat > /etc/bts-express.env <<ENV
BTS_STORAGE=postgres
DB_HOST=$DB_HOST
DB_PORT=5432
DB_NAME=bts
DB_SSLMODE=require
DB_SECRET_ID=$DB_SECRET
ADMIN_SECRET_ID=$ADMIN_SECRET
S3_BUCKET=$BUCKET
S3_PREFIX=bts/
AWS_REGION=$REGION
CW_NAMESPACE=BTSExpress
TRUST_PROXY=1
BIND=127.0.0.1
PORT=8000
ENV
chmod 640 /etc/bts-express.env && chown root:bts /etc/bts-express.env

# 3) systemd + nginx + CloudWatch agent
cp /opt/bts-express/deploy/systemd/bts-express.service /etc/systemd/system/
cp /opt/bts-express/deploy/nginx/bts-express.conf /etc/nginx/conf.d/
cp /opt/bts-express/deploy/nginx/bts-proxy.inc /etc/nginx/bts-proxy.inc
cp /opt/bts-express/deploy/cloudwatch/agent.json /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
systemctl daemon-reload
systemctl enable --now bts-express
nginx -t && systemctl enable --now nginx
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s

# 4) HTTPS (faqat domen berilgan bo'lsa)
if [ -n "$DOMAIN" ]; then
  python3.11 -m pip install certbot certbot-nginx
  sed -i "s/server_name _;/server_name $DOMAIN;/" /etc/nginx/conf.d/bts-express.conf
  systemctl reload nginx
  /usr/local/bin/certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect || echo "certbot muvaffaqiyatsiz - DNS A yozuvi EC2 IP'ga qaratilganini tekshiring"
fi
echo "BTS Express o'rnatildi"
