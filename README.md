# workflow-lang-automation

Nextflow 한국어 커뮤니티 월간 운영 워크플로 자동화 프로젝트

## 목적

매달 반복되는 커뮤니티 운영 작업(설문조사, 홍보, 미팅, 결과 취합, 유튜브 업로드)을
사람의 개입 없이 자동화한다.

## 아키텍처

```
GitHub Issue (label: event, body: YYYY-MM-DD)
        ↓ GitHub Actions
AWS Lambda: schedule-register
        ↓ EventBridge Rules (D-30, D-14, D-7, D-2, D+0, D+2, D+7)
        ↓
┌─────────────────────────────────────┐
│ notify   → Slack + Telegram         │
│ survey   → Google Forms + Sheets    │
│ meeting  → Zoom + Gmail             │
│ youtube  → YouTube upload + notify  │
└─────────────────────────────────────┘
```

## 디렉토리 구조

```
workflow-lang-automation/
├── .github/workflows/          # GitHub Actions
├── functions/
│   ├── schedule_register/      # Issue → EventBridge 스케줄 등록
│   ├── notify/                 # Slack + Telegram 발송
│   ├── survey/                 # Google Forms + Sheets
│   ├── meeting/                # Zoom + Gmail
│   └── youtube/                # YouTube 업로드
├── config/
│   ├── messages.yaml           # 알림 메시지 템플릿
│   ├── survey_template.yaml    # 설문 질문 템플릿
│   ├── email_template.yaml     # 이메일 본문 템플릿
│   └── youtube_template.yaml  # YouTube 제목/설명 템플릿
├── scripts/
│   └── check_secrets.sh        # 민감정보 스캔 스크립트
├── template.yaml               # AWS SAM 정의
├── .env.example                # 환경변수 키 목록 (값 없음)
└── CONTRIBUTING.md
```

## 사용 방법

### 1. 행사 일정 등록

GitHub Issue를 생성한다:
- Label: `event`
- Title: `[이벤트명] YYYY-MM-DD`
- Body 첫 줄: `date: YYYY-MM-DD`

GitHub Actions가 자동으로 EventBridge 스케줄을 등록한다.

### 2. 로컬 테스트

```bash
# 의존성 설치
pip install aws-sam-cli

# 특정 함수 로컬 실행
sam local invoke NotifyFunction --event events/notify_test.json
```

### 3. 배포

```bash
sam build
sam deploy --guided
```

## 시크릿 관리

모든 민감정보는 **AWS Parameter Store (SSM)** 에 저장한다.
코드와 git 히스토리에는 절대 포함하지 않는다.

```bash
# SSM에 시크릿 등록 예시
aws ssm put-parameter \
  --name "/workflow-lang-automation/SLACK_WEBHOOK_URL" \
  --value "https://hooks.slack.com/..." \
  --type SecureString
```

필요한 파라미터 목록은 `.env.example` 참고.

## 민감정보 정책

- `.env` 파일은 `.gitignore` 처리되어 있으며 절대 커밋하지 않는다
- PR 전 반드시 `bash scripts/check_secrets.sh` 실행
- 새 환경변수 추가 시 `.env.example`에 키만 추가
- GitHub Org 이전 전 전체 히스토리 스캔 필수

## 기술 스택

| 역할 | 도구 |
|---|---|
| 오케스트레이터 | AWS EventBridge + Lambda (Python 3.12) |
| IaC | AWS SAM |
| 시크릿 | AWS Parameter Store (SSM) |
| 알림 | Slack Incoming Webhook, Telegram Bot API |
| 설문 | Google Forms API + Google Sheets API |
| 미팅 | Zoom API + Gmail API |
| 영상 | YouTube Data API v3 (S3 → YouTube) |
