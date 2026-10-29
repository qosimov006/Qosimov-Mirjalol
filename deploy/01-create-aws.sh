#!/usr/bin/env bash
# BTS Express uchun AWS resurslarini yaratadi: Security Groups, S3, Secrets Manager, RDS, IAM, EC2, CloudWatch alarmlar, Budget.
#
# Talab: AWS CLI v2 o'rnatilgan va SIZNING akkauntingizga ulangan (aws configure yoki aws sso login).
# Bu skriptda PAROL / KALIT YO'Q. Admin paroli tasodifiy yaratiladi va faqat Secrets Manager'ga yoziladi.
# Ishga tushirish:  cp deploy/config.env.example deploy/config.env && (tahrirlang) && bash deploy/01-create-aws.sh
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f deploy/config.env ] || { echo "deploy/config.env topilmadi (config.env.example'dan nusxa oling)"; exit 1; }
# shellcheck disable=SC1091
source deploy/config.env
: "${AWS_REGION:?}" "${PROJECT:?}" "${S3_BUCKET:?}" "${EC2_TYPE:?}" "${DB_CLASS:?}" "${ALERT_EMAIL:?}" "${BUDGET_USD:?}"
case "$S3_BUCKET" in *CHANGE-ME*) echo "config.env'da S3_BUCKET nomini o'zgartiring"; exit 1;; esac
export AWS_DEFAULT_REGION="$AWS_REGION" AWS_PAGER=""
STATE=deploy/.state
[ -f "$STATE" ] && { echo "$STATE mavjud - resurslar allaqachon yaratilgan bo'lishi mumkin. Avval deploy/teardown.sh ni ishlating."; exit 1; }
save() { echo "$1=$2" >> "$STATE"; }
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "== Akkaunt: $ACCOUNT, region: $AWS_REGION"
save REGION "$AWS_REGION"; save PROJECT "$PROJECT"; save BUCKET "$S3_BUCKET"; save ACCOUNT "$ACCOUNT"

echo "== 1/9 Tarmoq va Security Groups"
VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
WEB_SG=$(aws ec2 create-security-group --group-name "$PROJECT-web" --description "BTS Express web (HTTP/HTTPS)" --vpc-id "$VPC_ID" --query GroupId --output text)
save WEB_SG "$WEB_SG"
aws ec2 authorize-security-group-ingress --group-id "$WEB_SG" --ip-permissions \
  'IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0,Description="HTTP (brauzer, Lets Encrypt)"}]' \
  'IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0,Description="HTTPS"}]' >/dev/null
if [ -n "${SSH_CIDR:-}" ]; then
  aws ec2 authorize-security-group-ingress --group-id "$WEB_SG" --ip-permissions \
    "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$SSH_CIDR,Description=\"SSH faqat administrator IP\"}]" >/dev/null
fi
DB_SG=$(aws ec2 create-security-group --group-name "$PROJECT-db" --description "BTS Express RDS (faqat web SG dan)" --vpc-id "$VPC_ID" --query GroupId --output text)
save DB_SG "$DB_SG"
aws ec2 authorize-security-group-ingress --group-id "$DB_SG" --ip-permissions \
  "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$WEB_SG,Description=\"PostgreSQL faqat ilova serveridan\"}]" >/dev/null

echo "== 2/9 S3 bucket (yopiq, shifrlangan)"
if [ "$AWS_REGION" = "us-east-1" ]; then aws s3api create-bucket --bucket "$S3_BUCKET" >/dev/null
else aws s3api create-bucket --bucket "$S3_BUCKET" --create-bucket-configuration "LocationConstraint=$AWS_REGION" >/dev/null; fi
aws s3api put-public-access-block --bucket "$S3_BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket "$S3_BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-lifecycle-configuration --bucket "$S3_BUCKET" --lifecycle-configuration \
  '{"Rules":[{"ID":"expire-exports","Status":"Enabled","Filter":{"Prefix":"bts/exports/"},"Expiration":{"Days":30}},{"ID":"expire-selftest","Status":"Enabled","Filter":{"Prefix":"bts/selftest/"},"Expiration":{"Days":1}}]}'
# Ilova paketi (data/, tests/, maxfiy fayllar kirmaydi)
python3 - <<'PY'
import os, zipfile
skip_dirs = {".git", "data", "tests", "__pycache__", "docs"}
skip_files = {"deploy/config.env", "deploy/.state"}
with zipfile.ZipFile("/tmp/bts-app.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for d, dirs, files in os.walk("."):
        dirs[:] = [x for x in dirs if x not in skip_dirs]
        for f in files:
            p = os.path.relpath(os.path.join(d, f), ".")
            if p in skip_files or p.startswith("deploy/.state") or f.endswith((".pyc", ".pem", ".key", ".zip")):
                continue
            z.write(p, p)
PY
aws s3 cp /tmp/bts-app.zip "s3://$S3_BUCKET/deploy/app.zip" --sse AES256 >/dev/null
rm -f /tmp/bts-app.zip

echo "== 3/9 Admin paroli (Secrets Manager; ekranga chiqarilmaydi)"
umask 077
TMPF=$(mktemp)
printf '{"password":"%s"}' "$(openssl rand -base64 24 | tr -d '=+/')" > "$TMPF"
ADMIN_SECRET_ARN=$(aws secretsmanager create-secret --name "$PROJECT/admin" --description "BTS Express admin paroli" \
  --secret-string "file://$TMPF" --query ARN --output text)
shred -u "$TMPF" 2>/dev/null || rm -f "$TMPF"
save ADMIN_SECRET_ARN "$ADMIN_SECRET_ARN"

echo "== 4/9 RDS PostgreSQL (ochiq emas, shifrlangan; master parol Secrets Manager'da avtomatik)"
aws rds create-db-instance --db-instance-identifier "$PROJECT-db" --engine postgres --engine-version 16 \
  --db-instance-class "$DB_CLASS" --allocated-storage "${DB_STORAGE_GB:-20}" --storage-type gp3 \
  --master-username btsadmin --manage-master-user-password --db-name bts \
  --vpc-security-group-ids "$DB_SG" --no-publicly-accessible --no-multi-az \
  --backup-retention-period 7 --storage-encrypted --no-deletion-protection >/dev/null
save DB_ID "$PROJECT-db"
echo "   RDS yaratilmoqda (5-10 daqiqa)..."
aws rds wait db-instance-available --db-instance-identifier "$PROJECT-db"
DB_HOST=$(aws rds describe-db-instances --db-instance-identifier "$PROJECT-db" --query 'DBInstances[0].Endpoint.Address' --output text)
DB_SECRET_ARN=$(aws rds describe-db-instances --db-instance-identifier "$PROJECT-db" --query 'DBInstances[0].MasterUserSecret.SecretArn' --output text)
save DB_HOST "$DB_HOST"; save DB_SECRET_ARN "$DB_SECRET_ARN"

echo "== 5/9 IAM rol (minimal huquqlar)"
sed -e "s|__BUCKET__|$S3_BUCKET|g" -e "s|__DB_SECRET_ARN__|$DB_SECRET_ARN|g" -e "s|__ADMIN_SECRET_ARN__|$ADMIN_SECRET_ARN|g" \
    -e "s|__REGION__|$AWS_REGION|g" -e "s|__ACCOUNT__|$ACCOUNT|g" deploy/iam/ec2-app-policy.json.tpl > /tmp/bts-policy.json
aws iam create-role --role-name "$PROJECT-ec2-role" --assume-role-policy-document file://deploy/iam/ec2-trust.json >/dev/null
save ROLE "$PROJECT-ec2-role"
aws iam put-role-policy --role-name "$PROJECT-ec2-role" --policy-name "$PROJECT-app" --policy-document file:///tmp/bts-policy.json
aws iam attach-role-policy --role-name "$PROJECT-ec2-role" --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam create-instance-profile --instance-profile-name "$PROJECT-ec2-profile" >/dev/null
aws iam add-role-to-instance-profile --instance-profile-name "$PROJECT-ec2-profile" --role-name "$PROJECT-ec2-role"
rm -f /tmp/bts-policy.json
echo "   IAM tarqalishini kutish..."; sleep 15

echo "== 6/9 EC2 server"
AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query Parameter.Value --output text)
sed -e "s|__REGION__|$AWS_REGION|g" -e "s|__BUCKET__|$S3_BUCKET|g" -e "s|__DB_HOST__|$DB_HOST|g" \
    -e "s|__DB_SECRET_ARN__|$DB_SECRET_ARN|g" -e "s|__ADMIN_SECRET_ARN__|$ADMIN_SECRET_ARN|g" -e "s|__DOMAIN__|${DOMAIN:-}|g" \
    deploy/ec2-userdata.sh.tpl > /tmp/bts-userdata.sh
INSTANCE_ID=$(aws ec2 run-instances --image-id "$AMI" --instance-type "$EC2_TYPE" --security-group-ids "$WEB_SG" \
  --iam-instance-profile "Name=$PROJECT-ec2-profile" --user-data file:///tmp/bts-userdata.sh \
  --metadata-options HttpTokens=required,HttpEndpoint=enabled \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=10,VolumeType=gp3,Encrypted=true,DeleteOnTermination=true}' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$PROJECT}]" --query 'Instances[0].InstanceId' --output text)
rm -f /tmp/bts-userdata.sh
save INSTANCE_ID "$INSTANCE_ID"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
ALLOC=$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)
save ALLOC_ID "$ALLOC"
aws ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOC" >/dev/null
PUBLIC_IP=$(aws ec2 describe-addresses --allocation-ids "$ALLOC" --query 'Addresses[0].PublicIp' --output text)
save PUBLIC_IP "$PUBLIC_IP"

echo "== 7/9 CloudWatch alarmlar + email xabarnoma"
TOPIC=$(aws sns create-topic --name "$PROJECT-alerts" --query TopicArn --output text)
save SNS_TOPIC "$TOPIC"
aws sns subscribe --topic-arn "$TOPIC" --protocol email --notification-endpoint "$ALERT_EMAIL" >/dev/null
alarm() { aws cloudwatch put-metric-alarm --alarm-name "$PROJECT-$1" --alarm-actions "$TOPIC" --treat-missing-data "${TM:-notBreaching}" "${@:2}"; }
alarm ec2-cpu-high --namespace AWS/EC2 --metric-name CPUUtilization --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
  --statistic Average --period 300 --evaluation-periods 2 --threshold 80 --comparison-operator GreaterThanThreshold
alarm ec2-status-check --namespace AWS/EC2 --metric-name StatusCheckFailed --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
  --statistic Maximum --period 60 --evaluation-periods 2 --threshold 0 --comparison-operator GreaterThanThreshold
alarm app-5xx-errors --namespace BTSExpress --metric-name Errors5xx --statistic Sum --period 300 --evaluation-periods 1 \
  --threshold 5 --comparison-operator GreaterThanOrEqualToThreshold
alarm rds-cpu-high --namespace AWS/RDS --metric-name CPUUtilization --dimensions Name=DBInstanceIdentifier,Value="$PROJECT-db" \
  --statistic Average --period 300 --evaluation-periods 2 --threshold 80 --comparison-operator GreaterThanThreshold
alarm rds-low-storage --namespace AWS/RDS --metric-name FreeStorageSpace --dimensions Name=DBInstanceIdentifier,Value="$PROJECT-db" \
  --statistic Minimum --period 300 --evaluation-periods 1 --threshold 2000000000 --comparison-operator LessThanThreshold

echo "== 8/9 Byudjet signali (\$$BUDGET_USD/oy)"
aws budgets create-budget --account-id "$ACCOUNT" \
  --budget "{\"BudgetName\":\"$PROJECT-monthly\",\"BudgetLimit\":{\"Amount\":\"$BUDGET_USD\",\"Unit\":\"USD\"},\"TimeUnit\":\"MONTHLY\",\"BudgetType\":\"COST\"}" \
  --notifications-with-subscribers "[{\"Notification\":{\"NotificationType\":\"ACTUAL\",\"ComparisonOperator\":\"GREATER_THAN\",\"Threshold\":80,\"ThresholdType\":\"PERCENTAGE\"},\"Subscribers\":[{\"SubscriptionType\":\"EMAIL\",\"Address\":\"$ALERT_EMAIL\"}]}]" \
  || echo "   (byudjet yaratilmadi - ruxsat yetishmasligi mumkin, konsolda qo'lda yarating)"
save BUDGET "$PROJECT-monthly"

echo "== 9/9 Tayyor"
cat <<DONE

  Ilova manzili : http://$PUBLIC_IP/        (EC2 o'rnatishni tugatguncha ~3-5 daqiqa kuting)
  Salomatlik    : http://$PUBLIC_IP/api/health
  Admin login   : admin
  Admin paroli  : aws secretsmanager get-secret-value --secret-id $PROJECT/admin --query SecretString --output text
                  (parol faqat shu yerda saqlanadi; hisobotga/GitHub'ga YOZMANG)
  Email         : $ALERT_EMAIL manziliga kelgan SNS tasdiqlash xatini tasdiqlang (aks holda alarm xabari kelmaydi)
  O'chirish     : bash deploy/teardown.sh   (himoyadan keyin, xarajat to'xtashi uchun)
DONE
