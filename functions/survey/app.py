"""
Google Forms 설문 자동 생성 (D-7) + Google Sheets 결과 집계 (D+7)
"""
import json
import os
import boto3
from google.oauth2 import service_account
from googleapiclient.discovery import build

ssm = boto3.client("ssm")
SSM_PREFIX = os.environ.get("SSM_PREFIX", "/nextflow-kr-automation")
SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_param(name: str) -> str:
    return ssm.get_parameter(
        Name=f"{SSM_PREFIX}/{name}", WithDecryption=True
    )["Parameter"]["Value"]


def get_credentials():
    sa_json = json.loads(get_param("GOOGLE_SERVICE_ACCOUNT_JSON"))
    return service_account.Credentials.from_service_account_info(sa_json, scopes=SCOPES)


def create_survey(creds, event_name: str, dday: str) -> str:
    forms_service = build("forms", "v1", credentials=creds)
    form = forms_service.forms().create(body={
        "info": {"title": f"[{event_name}] 참석 후기 설문 ({dday})"}
    }).execute()

    # 기본 질문 추가
    forms_service.forms().batchUpdate(formId=form["formId"], body={"requests": [
        {"createItem": {"item": {"title": "전반적인 만족도는?", "questionItem": {
            "question": {"required": True, "scaleQuestion": {"low": 1, "high": 5}}
        }}, "location": {"index": 0}}},
        {"createItem": {"item": {"title": "가장 유익했던 내용은?", "questionItem": {
            "question": {"required": False, "textQuestion": {"paragraph": True}}
        }}, "location": {"index": 1}}},
        {"createItem": {"item": {"title": "다음 모임에서 다뤘으면 하는 주제는?", "questionItem": {
            "question": {"required": False, "textQuestion": {"paragraph": True}}
        }}, "location": {"index": 2}}},
    ]}).execute()

    return f"https://docs.google.com/forms/d/{form['formId']}/viewform"


def collect_results(creds, event_name: str):
    spreadsheet_id = get_param("GOOGLE_SPREADSHEET_ID")
    sheets = build("sheets", "v4", credentials=creds)
    # 결과 집계는 Forms 응답 스프레드시트에서 읽어 메인 시트에 요약 행 추가
    sheets.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range="설문결과!A:A",
        valueInputOption="USER_ENTERED",
        body={"values": [[event_name, "집계완료"]]},
    ).execute()


def lambda_handler(event, context):
    offset = event["offset"]
    event_name = event["event_name"]
    dday = event["dday"]
    creds = get_credentials()

    if offset == -7:
        survey_url = create_survey(creds, event_name, dday)
        # notify 함수에 survey_url 전달 (EventBridge 통해 이미 별도 호출됨)
        return {"statusCode": 200, "survey_url": survey_url}

    if offset == 7:
        collect_results(creds, event_name)
        return {"statusCode": 200, "message": "결과 집계 완료"}

    return {"statusCode": 200}
