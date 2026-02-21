"""
Slack + Telegram 자동 알림 발송
EventBridge에서 {"offset": -7, "event_name": "...", "dday": "YYYY-MM-DD"} 형태로 호출
"""
import json
import os
import urllib.request
import boto3
import yaml

ssm = boto3.client("ssm")
SSM_PREFIX = os.environ.get("SSM_PREFIX", "/workflow-lang-automation")


def get_param(name: str) -> str:
    return ssm.get_parameter(
        Name=f"{SSM_PREFIX}/{name}", WithDecryption=True
    )["Parameter"]["Value"]


def load_messages() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "messages.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)["messages"]


def post(url: str, payload: dict):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)


def lambda_handler(event, context):
    offset = str(event["offset"])
    event_name = event["event_name"]
    dday = event["dday"]
    extra = event.get("extra", {})  # survey_url, meeting_url 등

    messages = load_messages()
    template = messages.get(offset)
    if not template:
        return {"statusCode": 200, "message": f"offset {offset} 에 해당하는 템플릿 없음"}

    fmt = {**{"survey_url": "", "meeting_url": ""}, "event_name": event_name, "dday": dday, **extra}

    # Slack
    slack_url = get_param("SLACK_WEBHOOK_URL")
    post(slack_url, {"text": template["slack"].format_map(fmt)})

    # Telegram
    bot_token = get_param("TELEGRAM_BOT_TOKEN")
    chat_id = get_param("TELEGRAM_CHAT_ID")
    tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    post(tg_url, {"chat_id": chat_id, "text": template["telegram"].format_map(fmt)})

    return {"statusCode": 200}
