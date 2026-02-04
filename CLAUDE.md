# YouTube Summary Telegram Bot

YouTube 채널을 모니터링하고 새 영상의 자막을 Claude CLI로 요약하여 텔레그램으로 전송하는 봇입니다.

## 프로젝트 구조

```
youtube-summary-bot/
├── src/
│   ├── main.py           # 애플리케이션 진입점
│   ├── config.py         # 환경변수 및 설정 관리
│   ├── bot/
│   │   ├── handlers.py   # 텔레그램 명령어 핸들러
│   │   ├── middleware.py # 인증 미들웨어
│   │   └── formatters.py # 메시지 포맷팅
│   ├── services/
│   │   ├── scheduler.py  # JobQueue 기반 스케줄러
│   │   ├── youtube.py    # YouTube Data API 연동
│   │   ├── transcript.py # 자막 추출
│   │   ├── summarizer.py # 요약 오케스트레이션
│   │   └── claude_cli.py # Claude CLI 호출
│   ├── db/
│   │   ├── database.py   # SQLite 연결 관리
│   │   ├── models.py     # 데이터 모델
│   │   └── repositories.py # CRUD 작업
│   └── prompts/
│       ├── structured.txt # 30분 미만 영상용 프롬프트
│       └── detailed.txt   # 30분 이상 영상용 프롬프트
├── data/
│   └── bot.db            # SQLite 데이터베이스
├── .env                  # 환경변수 (생성 필요)
├── .env.example          # 환경변수 예시
├── requirements.txt      # 의존성
└── CLAUDE.md             # 이 파일
```

## 실행 방법

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일 편집하여 실제 값 입력

# 실행
python -m src.main
```

## 봇 명령어

- `/start` - 도움말 표시
- `/add_channel <URL>` - YouTube 채널 추가
- `/remove_channel <채널ID>` - 채널 삭제
- `/list_channels` - 등록된 채널 목록
- `/summarize <URL>` - 특정 영상 즉시 요약
- `/set_time <시> <분>` - 스케줄 시간 변경
- `/pause` - 스케줄러 일시정지
- `/resume` - 스케줄러 재개
- `/status` - 현재 상태 확인
- `/run_now` - 수동 실행

## 핵심 로직

### 요약 분기
- 30분 미만: 구조화된 요약 (핵심 주제, 주요 포인트, 인사이트)
- 30분 이상: 상세 요약 (구간별 타임스탬프 요약)

### 스케줄러
- python-telegram-bot의 JobQueue 사용 (내장 APScheduler 래퍼)
- 매일 지정된 시간에 등록된 채널의 새 영상 확인
- 새 영상 발견 시 자막 추출 → Claude 요약 → 텔레그램 전송

### 인증
- ADMIN_CHAT_ID로 지정된 사용자만 명령어 실행 가능
- 요약 결과는 TARGET_CHAT_ID로 전송

## 환경변수

| 변수 | 설명 |
|------|------|
| TELEGRAM_BOT_TOKEN | 텔레그램 봇 토큰 |
| ADMIN_CHAT_ID | 관리자 채팅 ID |
| TARGET_CHAT_ID | 요약 결과 전송 대상 |
| YOUTUBE_API_KEY | YouTube Data API 키 |
| SCHEDULE_HOUR | 스케줄 실행 시 (0-23) |
| SCHEDULE_MINUTE | 스케줄 실행 분 (0-59) |

## 주의사항

- Claude CLI가 PATH에 설치되어 있어야 함
- YouTube API 할당량 제한 주의 (하루 10,000 단위)
- 텔레그램 메시지 4096자 제한으로 자동 분할
