"""
Google Forms 설문 자동 생성 (D-7) + Google Sheets 결과 집계 (D+7)
"""
import json
import os
import boto3
import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build

ssm = boto3.client("ssm")
SSM_PREFIX = os.environ.get("SSM_PREFIX", "/workflow-lang-automation")
SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/spreadsheets",
]

QUESTION_TYPE_MAP = {
    "scale":     lambda q: {"scaleQuestion": {"low": q["low"], "high": q["high"],
                             "lowLabel": q.get("low_label", ""), "highLabel": q.get("high_label", "")}},
    "paragraph": lambda q: {"textQuestion": {"paragraph": True}},
    "radio":     lambda q: {"choiceQuestion": {"type": "RADIO",
                             "options": [{"value": o} for o in q["options"]]}},
    "checkbox":  lambda q: {"choiceQuestion": {"type": "CHECKBOX",
                             "options": [{"value": o} for o in q["options"]]}},
}


def get_param(name: str) -> str:
    return ssm.get_parameter(Name=f"{SSM_PREFIX}/{name}", WithDecryption=True)["Parameter"]["Value"]


def get_credentials():
    sa_json = json.loads(get_param("GOOGLE_SERVICE_ACCOUNT_JSON"))
    return service_account.Credentials.from_service_account_info(sa_json, scopes=SCOPES)


def load_survey_template() -> list:
    path = os.path.join(os.path.dirname(__file__), "../../config/survey_template.yaml")
    with open(path) as f:
        return yaml.safe_load(f)["questions"]


def create_survey(creds, event_name: str, dday: str) -> str:
    forms = build("forms", "v1", credentials=creds)
    form = forms.forms().create(body={"info": {"title": f"[{event_name}] 참석 후기 ({dday})"}}).execute()

    requests = []
    for i, q in enumerate(load_survey_template()):
        question_body = {"required": q.get("required", False), **QUESTION_TYPE_MAP[q["type"]](q)}
        requests.append({"createItem": {
            "item": {"title": q["title"], "questionItem": {"question": question_body}},
            "location": {"index": i},
        }})

    forms.forms().batchUpdate(formId=form["formId"], body={"requests": requests}).execute()
    return f"https://docs.google.com/forms/d/{form['formId']}/viewform"


def collect_results(creds, event_name: str, dday: str):
    spreadsheet_id = get_param("GOOGLE_SPREADSHEET_ID")
    sheets = build("sheets", "v4", credentials=creds)
    sheets.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range="설문결과!A:C",
        valueInputOption="USER_ENTERED",
        body={"values": [[dday, event_name, "집계완료"]]},
    ).execute()


def lambda_handler(event, context):
    offset = event["offset"]
    event_name = event["event_name"]
    dday = event["dday"]
    creds = get_credentials()

    if offset == -7:
        survey_url = create_survey(creds, event_name, dday)
        return {"statusCode": 200, "survey_url": survey_url}

    if offset == 7:
        collect_results(creds, event_name, dday)
        return {"statusCode": 200}

    return {"statusCode": 200}
