#!/usr/bin/env bash
# Yaratilgan hamma AWS resurslarini o'chiradi (himoyadan keyin, o'qituvchi ko'rsatmasiga binoan). Qaytarib bo'lmaydi!
set -uo pipefail
cd "$(dirname "$0")/.."
[ -f deploy/.state ] || { echo "deploy/.state topilmadi - o'chiradigan narsa yo'q"; exit 0; }
# shellcheck disable=SC1091
source deploy/.state
export AWS_DEFAULT_REGION="$REGION" AWS_PAGER=""
read -r -p "$PROJECT resurslari ($REGION) butunlay o'chiriladi, ma'lumotlar bazasi ham. Davom etasizmi? [yes/NO] " a
[ "$a" = "yes" ] || { echo "Bekor qilindi"; exit 1; }
step() { echo "-- $*"; }
step "Alarmlar, byudjet, xabarnoma"
aws cloudwatch delete-alarms --alarm-names "$PROJECT-ec2-cpu-high" "$PROJECT-ec2-status-check" "$PROJECT-app-5xx-errors" "$PROJECT-rds-cpu-high" "$PROJECT-rds-low-storage"
[ -n "${BUDGET:-}" ] && aws budgets delete-budget --account-id "$ACCOUNT" --budget-name "$BUDGET"
[ -n "${SNS_TOPIC:-}" ] && aws sns delete-topic --topic-arn "$SNS_TOPIC"
step "EC2 va Elastic IP"
if [ -n "${INSTANCE_ID:-}" ]; then aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" >/dev/null; aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"; fi
[ -n "${ALLOC_ID:-}" ] && aws ec2 release-address --allocation-id "$ALLOC_ID"
step "RDS (5-10 daqiqa)"
if [ -n "${DB_ID:-}" ]; then
  aws rds delete-db-instance --db-instance-identifier "$DB_ID" --skip-final-snapshot --delete-automated-backups >/dev/null
  aws rds wait db-instance-deleted --db-instance-identifier "$DB_ID"
fi
step "Security Groups"
[ -n "${DB_SG:-}" ] && aws ec2 delete-security-group --group-id "$DB_SG"
[ -n "${WEB_SG:-}" ] && aws ec2 delete-security-group --group-id "$WEB_SG"
step "S3 bucket va maxfiy ma'lumotlar"
[ -n "${BUCKET:-}" ] && aws s3 rb "s3://$BUCKET" --force
[ -n "${ADMIN_SECRET_ARN:-}" ] && aws secretsmanager delete-secret --secret-id "$ADMIN_SECRET_ARN" --force-delete-without-recovery >/dev/null
step "IAM"
if [ -n "${ROLE:-}" ]; then
  aws iam remove-role-from-instance-profile --instance-profile-name "$PROJECT-ec2-profile" --role-name "$ROLE"
  aws iam delete-instance-profile --instance-profile-name "$PROJECT-ec2-profile"
  aws iam detach-role-policy --role-name "$ROLE" --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
  aws iam delete-role-policy --role-name "$ROLE" --policy-name "$PROJECT-app"
  aws iam delete-role --role-name "$ROLE"
fi
step "CloudWatch loglari"
for g in /bts-express/app /bts-express/nginx-access; do aws logs delete-log-group --log-group-name "$g" 2>/dev/null; done
mv deploy/.state "deploy/.state.deleted.$(date +%Y%m%d-%H%M)"
echo "Tayyor. Konsolda (EC2, RDS, S3, VPC > Elastic IPs) qolgan resurs yo'qligini tekshiring."
