"""
GitHub Issue(label: event) → EventBridge Rules 동적 생성
Issue body 첫 줄: date: YYYY-MM-DD
"""
import json
import re
import boto3
from datetime import datetime, timedelta

events_client = boto3.client("events")
lambda_client = boto3.client("lambda")

# D-Day 기준 오프셋 및 타겟 함수 매핑
SCHEDULE_OFFSETS = [
    {"offset": -30, "targets": ["notify"]},
    {"offset": -14, "targets": ["notify"]},
    {"offset": -7,  "targets": ["notify", "survey", "meeting"]},
    {"offset": -2,  "targets": ["notify", "meeting"]},
    {"offset":  0,  "targets": ["notify"]},
    {"offset":  2,  "targets": ["notify"]},
    {"offset":  7,  "targets": ["notify", "survey", "youtube"]},
]

FUNCTION_ARNS = {
    "notify":  "workflow-lang-notify",
    "survey":  "workflow-lang-survey",
    "meeting": "workflow-lang-meeting",
    "youtube": "workflow-lang-youtube",
}


def parse_date(body: str) -> datetime:
    match = re.search(r"date:\s*(\d{4}-\d{2}-\d{2})", body or "")
    if not match:
        raise ValueError("Issue body에 'date: YYYY-MM-DD' 형식이 없습니다")
    return datetime.strptime(match.group(1), "%Y-%m-%d")


def cron_expression(dt: datetime) -> str:
    return f"cron({dt.minute} {dt.hour} {dt.day} {dt.month} ? {dt.year})"


def lambda_handler(event, context):
    body = event.get("issue", {}).get("body", "")
    title = event.get("issue", {}).get("title", "event")
    event_name = re.sub(r"[^a-zA-Z0-9-]", "-", title)[:40]

    dday = parse_date(body)
    created_rules = []

    for schedule in SCHEDULE_OFFSETS:
        offset = schedule["offset"]
        trigger_date = dday + timedelta(days=offset)
        sign = "p" if offset >= 0 else "m"
        rule_name = f"workflow-lang-{event_name}-D{sign}{abs(offset)}"

        events_client.put_rule(
            Name=rule_name,
            ScheduleExpression=cron_expression(trigger_date),
            State="ENABLED",
            Description=f"D{offset:+d} trigger for {event_name}",
        )

        targets = []
        for func in schedule["targets"]:
            func_name = FUNCTION_ARNS[func]
            targets.append({
                "Id": func,
                "Arn": f"arn:aws:lambda:{boto3.session.Session().region_name}:"
                       f"{context.invoked_function_arn.split(':')[4]}:function:{func_name}",
                "Input": json.dumps({"offset": offset, "event_name": event_name, "dday": dday.isoformat()}),
            })

        events_client.put_targets(Rule=rule_name, Targets=targets)
        created_rules.append(rule_name)

    return {"statusCode": 200, "rules": created_rules}
