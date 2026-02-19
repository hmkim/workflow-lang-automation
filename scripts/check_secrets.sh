#!/bin/bash
# git 히스토리 전체에서 민감정보 패턴 스캔
# GitHub Org 이전 전 반드시 실행

set -e

echo "=== 민감정보 스캔 시작 ==="

# truffleHog 설치 확인
if ! command -v trufflehog &> /dev/null; then
  echo "trufflehog 설치 중..."
  pip install trufflehog --quiet
fi

# 현재 파일 스캔
echo "[1/2] 현재 파일 스캔..."
trufflehog filesystem . --only-verified 2>/dev/null || true

# git 히스토리 스캔
echo "[2/2] git 히스토리 스캔..."
trufflehog git file://. --only-verified 2>/dev/null || true

# .env 파일이 실수로 추적되고 있는지 확인
if git ls-files | grep -E "^\.env$|\.env\." | grep -v ".env.example"; then
  echo "❌ 경고: .env 파일이 git에 추적되고 있습니다!"
  exit 1
fi

echo "✅ 민감정보 스캔 완료. public 전환 가능합니다."
