"""SINOV UCHUN soxta 'boto3': S3, CloudWatch va Secrets Manager chaqiruvlarini FAYLGA yozadi (FAKE_AWS papkasi).
Haqiqiy AWS bilan aloqa yo'q; maqsad - ilovaning boto3'ga to'g'ri parametrlar bilan murojaat qilishini tekshirish."""
import datetime
import hashlib
import json
import os


def _root():
    r = os.environ["FAKE_AWS"]
    os.makedirs(os.path.join(r, "s3"), exist_ok=True)
    return r


class S3:
    def put_object(self, Bucket, Key, Body, ContentType, ServerSideEncryption=None, **kw):
        assert ServerSideEncryption == "AES256", "S3'ga shifrlanmasdan yozilmoqda!"
        p = os.path.join(_root(), "s3", Bucket, Key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(Body)
        open(p + ".ct", "w").write(ContentType)

    def get_object(self, Bucket, Key):
        p = os.path.join(_root(), "s3", Bucket, Key)
        import io
        return {"Body": io.BytesIO(open(p, "rb").read()), "ContentType": open(p + ".ct").read()}

    def delete_object(self, Bucket, Key):
        p = os.path.join(_root(), "s3", Bucket, Key)
        for x in (p, p + ".ct"):
            if os.path.exists(x):
                os.remove(x)

    def list_objects_v2(self, Bucket, Prefix="", **kw):
        base = os.path.join(_root(), "s3", Bucket)
        out = []
        for d, _, fs in os.walk(base):
            for f in fs:
                if f.endswith(".ct"):
                    continue
                k = os.path.relpath(os.path.join(d, f), base)
                if k.startswith(Prefix):
                    out.append({"Key": k, "Size": os.path.getsize(os.path.join(d, f)), "LastModified": datetime.datetime.now()})
        return {"Contents": out, "IsTruncated": False}

    def generate_presigned_url(self, op, Params, ExpiresIn):
        assert op == "get_object" and ExpiresIn <= 3600
        return "https://%s.s3.amazonaws.com/%s?X-Amz-Expires=%d&X-Amz-Signature=fake" % (Params["Bucket"], Params["Key"], ExpiresIn)


class CW:
    def put_metric_data(self, Namespace, MetricData):
        with open(os.path.join(_root(), "cloudwatch.jsonl"), "a") as f:
            f.write(json.dumps({"ns": Namespace, "data": MetricData}) + "\n")


class SM:
    def get_secret_value(self, SecretId):
        assert SecretId == os.environ.get("FAKE_SECRET_ID"), "noma'lum sir"
        return {"SecretString": os.environ["FAKE_SECRET_JSON"]}


def client(service, region_name=None):
    return {"s3": S3, "cloudwatch": CW, "secretsmanager": SM}[service]()
