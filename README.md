# 🛒 쇼핑 리스트

살 물건을 적고, 담을 때마다 체크하는 간단한 웹 앱입니다. Python과 [Streamlit](https://streamlit.io)으로 만들었습니다.

## 기능

- **추가**: 이름, 수량, 단위(개, kg, g, L, mL, 팩, 봉지, 병, 캔), 메모를 입력합니다. Enter로도 추가됩니다.
- **수정**: 항목의 ✏️를 눌러 이름, 수량, 단위, 메모를 고칩니다.
- **삭제**: 항목의 🗑️를 누르면 바로 삭제됩니다.
- **체크**: 체크하면 취소선이 그어지고 목록 아래로 내려갑니다. 해제하면 원래 자리로 돌아옵니다.
- **진행 현황**: "M / N 완료"와 진행률 바를 보여주고, 전부 체크하면 축하 문구가 나옵니다.
- **완료 항목 모두 삭제**: 체크한 항목을 한 번에 지웁니다.
- 새로고침해도 목록이 유지되고, 모바일 화면과 다크 모드를 지원합니다.

## 실행 방법

Python 3.10 이상이 필요합니다.

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

브라우저에서 http://localhost:8501 이 열립니다.

## 입력 규칙

| 항목 | 규칙 |
|---|---|
| 이름 | 필수, 최대 50자 (앞뒤 공백은 제거) |
| 수량 | 1~9999 정수 |
| 메모 | 선택, 최대 200자 |

## 데이터 저장

목록은 프로젝트 폴더의 `data.json`에 저장됩니다. 파일이 없으면 처음 저장할 때 자동으로 만들어집니다.

- `data.json`이 손상됐거나 읽을 수 없는 항목이 섞여 있으면, 덮어쓰기 전에 `data.json.corrupt-<시각>` 또는 `data.json.invalid-entries-<시각>`으로 백업합니다.
- `data.json`과 백업 파일은 `.gitignore`에 들어 있어 저장소에 올라가지 않습니다.

## 배포 (Streamlit Community Cloud)

1. 이 폴더를 GitHub 저장소에 올립니다.
2. [share.streamlit.io](https://share.streamlit.io)에 GitHub 계정으로 로그인합니다.
3. 저장소, 브랜치, 메인 파일 경로(`app.py`)를 지정하고 Deploy를 누릅니다.

**알아 둘 점**: Community Cloud에서는 앱이 재시작되면 `data.json`이 초기화될 수 있고, 모든 방문자가 같은 목록을 공유합니다. 개인용이나 데모용으로 쓰기에는 충분하지만, 영구 보관이나 사용자별 목록이 필요하면 외부 저장소(예: Google Sheets, Supabase)로 바꿔야 합니다.

## 파일 구성

```
├── app.py                  # 앱 본체 (단일 파일)
├── requirements.txt        # streamlit>=1.67
├── .streamlit/config.toml  # 테마 설정 (라이트/다크 포인트 컬러)
├── PRD.md                  # 제품 요구사항 문서
└── PROMPTS.md              # 단계별 개발 프롬프트
```
