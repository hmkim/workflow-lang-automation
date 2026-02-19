"""
Zoom 미팅 자동 생성 (D-7) + Gmail 이메일 발송 (D-2)
"""
import base64
import json
import os
import urllib.request
import boto3
from google.oauth2 import service_account
from googleapiclient.discovery import build

ssm = boto3.client("ssm")
SSM_PREFIX = os.environ.get("SSM_PREFIX", "/workflow-lang-automation")


def get_param(name: str) -> str:
    return ssm.get_parameter(
        Name=f"{SSM_PREFIX}/{name}", WithDecryption=True
    )["Parameter"]["Value"]


def create_zoom_meeting(event_name: str, dday: str) -> str:
    api_key = get_param("ZOOM_API_KEY")
    api_secret = get_param("ZOOM_API_SECRET")

    # Zoom JWT 토큰 생성
    import time, hmac, hashlib
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": api_key, "exp": int(time.time()) + 3600
    }).encode()).rstrip(b"=")
    sig = base64.urlsafe_b64encode(
        hmac.new(api_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=")
    token = f"{header}.{payload}.{sig}"

    data = json.dumps({
        "topic": f"[Nextflow KR] {event_name}",
        "type": 2,
        "start_time": f"{dday}T09:00:00",
        "duration": 120,
        "timezone": "Asia/Seoul",
    }).encode()
    req = urllib.request.Request(
        "https://api.zoom.us/v2/users/me/meetings",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    return resp["join_url"]


def send_email(event_name: str, dday: str, meeting_url: str):
    sa_json = json.loads(get_param("GMAIL_SERVICE_ACCOUNT_JSON"))
    attendee_emails = get_param("ATTENDEE_EMAILS").split(",")

    creds = service_account.Credentials.from_service_account_info(
        sa_json, scopes=["https://www.googleapis.com/auth/gmail.send"]
    ).with_subject(sa_json["client_email"])

    gmail = build("gmail", "v1", credentials=creds)
    subject = f"[Nextflow KR] {event_name} 미팅 안내 ({dday})"
    body = f"안녕하세요,\n\n{event_name} 모임 안내드립니다.\n\n일시: {dday}\n미팅 링크: {meeting_url}\n\n많은 참여 부탁드립니다!"

    for email in attendee_emails:
        raw = base64.urlsafe_b64encode(
            f"To: {email.strip()}\nSubject: {subject}\n\n{body}".encode()
        ).decode()
        gmail.users().messages().send(userId="me", body={"raw": raw}).execute()


def lambda_handler(event, context):
    offset = event["offset"]
    event_name = event["event_name"]
    dday = event["dday"]

    if offset == -7:
        meeting_url = create_zoom_meeting(event_name, dday)
        return {"statusCode": 200, "meeting_url": meeting_url}

    if offset == -2:
        meeting_url = event.get("extra", {}).get("meeting_url", "")
        send_email(event_name, dday, meeting_url)
        return {"statusCode": 200, "message": "이메일 발송 완료"}

    return {"statusCode": 200}
