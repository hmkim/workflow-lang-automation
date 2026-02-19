# 기여 가이드

## 민감정보 정책 (필수)

- API 키, 토큰, 이메일, 전화번호 등은 **절대 커밋하지 않는다**
- 모든 시크릿은 AWS Parameter Store (SSM)에 저장한다
- 새 환경변수 추가 시 `.env.example`에 **키만** 추가한다 (값 없음)
- PR 전 반드시 실행: `bash scripts/check_secrets.sh`

## SSM 파라미터 등록

```bash
aws ssm put-parameter \
  --name "/workflow-lang-automation/파라미터명" \
  --value "실제값" \
  --type SecureString
```

## 로컬 개발

```bash
pip install aws-sam-cli google-api-python-client google-auth pyyaml
sam local invoke NotifyFunction --event events/notify_test.json
```

## PR 체크리스트

- [ ] 민감정보가 코드에 없음
- [ ] `.env.example`에 새 환경변수 키 추가됨
- [ ] `sam validate` 통과
- [ ] `bash scripts/check_secrets.sh` 실행 완료
