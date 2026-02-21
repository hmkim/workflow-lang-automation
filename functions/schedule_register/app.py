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

SCHEDULE_OFFSETS = [
    {"offset": -30, "targets": ["notify"]},
    {"offset": -14, "targets": ["notify"]},
    {"offset": -7,  "targets": ["notify", "survey", "meeting"]},
    {"offset": -2,  "targets": ["notify", "meeting"]},
    {"offset":  0,  "targets": ["notify"]},
    {"offset":  2,  "targets": ["notify"]},
    {"offset":  7,  "targets": ["notify", "survey", "youtube"]},
]

FUNCTION_NAMES = {
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


def parse_event_name(title: str) -> str:
    # "[11회 모임] 2026-02-24" → "11-2026-02-24" (ASCII만 허용)
    ascii_only = re.sub(r"[^\x00-\x7F]", "", title)  # 한글 등 비ASCII 제거
    clean = re.sub(r"[^a-zA-Z0-9]", "-", ascii_only)
    clean = re.sub(r"-+", "-", clean).strip("-")
    return clean[:40] or "event"


def cron_expression(dt: datetime) -> str:
    return f"cron({dt.minute} {dt.hour} {dt.day} {dt.month} ? {dt.year})"


def get_function_arn(func_name: str, account_id: str, region: str) -> str:
    return f"arn:aws:lambda:{region}:{account_id}:function:{func_name}"


def ensure_lambda_permission(func_name: str, rule_name: str, rule_arn: str):
    sid = re.sub(r"[^a-zA-Z0-9]", "", rule_name)[:64]
    try:
        lambda_client.add_permission(
            FunctionName=func_name,
            StatementId=sid,
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=rule_arn,
        )
    except lambda_client.exceptions.ResourceConflictException:
        pass  # 이미 존재하면 무시


def lambda_handler(event, context):
    body = event.get("issue", {}).get("body", "")
    title = event.get("issue", {}).get("title", "event")
    event_name = parse_event_name(title)
    dday = parse_date(body)
    account_id = context.invoked_function_arn.split(":")[4]
    region = boto3.session.Session().region_name
    created_rules = []

    for schedule in SCHEDULE_OFFSETS:
        offset = schedule["offset"]
        trigger_date = dday + timedelta(days=offset)
        sign = "p" if offset >= 0 else "m"
        rule_name = f"workflow-lang-{event_name}-D{sign}{abs(offset)}"

        resp = events_client.put_rule(
            Name=rule_name,
            ScheduleExpression=cron_expression(trigger_date),
            State="ENABLED",
            Description=f"D{offset:+d} trigger for {event_name}",
        )
        rule_arn = resp["RuleArn"]

        targets = []
        for func in schedule["targets"]:
            func_name = FUNCTION_NAMES[func]
            func_arn = get_function_arn(func_name, account_id, region)
            ensure_lambda_permission(func_name, rule_name, rule_arn)
            targets.append({
                "Id": func,
                "Arn": func_arn,
                "Input": json.dumps({
                    "offset": offset,
                    "event_name": event_name,
                    "dday": dday.strftime("%Y-%m-%d"),
                }),
            })

        events_client.put_targets(Rule=rule_name, Targets=targets)
        created_rules.append(rule_name)

    return {"statusCode": 200, "rules": created_rules}
