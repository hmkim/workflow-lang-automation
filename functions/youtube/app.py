"""
S3 영상 파일 → YouTube 자동 업로드 (D+7)
편집은 수동, 업로드만 자동화
"""
import json
import os
import tempfile
import boto3
import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ssm = boto3.client("ssm")
s3 = boto3.client("s3")
SSM_PREFIX = os.environ.get("SSM_PREFIX", "/nextflow-kr-automation")


def get_param(name: str) -> str:
    return ssm.get_parameter(Name=f"{SSM_PREFIX}/{name}", WithDecryption=True)["Parameter"]["Value"]


def load_youtube_template() -> dict:
    path = os.path.join(os.path.dirname(__file__), "../../config/youtube_template.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def lambda_handler(event, context):
    event_name = event["event_name"]
    dday = event["dday"]
    bucket = get_param("S3_VIDEO_BUCKET")
    key = f"{dday}_{event_name}.mp4"

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        s3.download_fileobj(bucket, key, tmp)
        tmp_path = tmp.name

    sa_json = json.loads(get_param("GOOGLE_SERVICE_ACCOUNT_JSON"))
    creds = service_account.Credentials.from_service_account_info(
        sa_json, scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    youtube = build("youtube", "v3", credentials=creds)

    tmpl = load_youtube_template()
    fmt = {"event_name": event_name, "dday": dday}
    body = {
        "snippet": {
            "title": tmpl["title"].format(**fmt),
            "description": tmpl["description"].format(**fmt),
            "tags": tmpl["tags"],
            "categoryId": tmpl["category_id"],
        },
        "status": {"privacyStatus": tmpl["privacy_status"]},
    }

    media = MediaFileUpload(tmp_path, mimetype="video/mp4", resumable=True)
    response = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    os.unlink(tmp_path)

    return {"statusCode": 200, "video_url": f"https://youtu.be/{response['id']}"}
