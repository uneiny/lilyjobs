# 잡아채용

여러 공공 채용공고 사이트와 지자체 게시판의 채용 관련 공고를 한 번에 수집하는 Streamlit 앱입니다.

## 주요 기능

- 기본 공공 채용 사이트 수집: 나라일터, 클린아이잡플러스, 잡알리오, 잡아바
- 지자체 채용 관련 게시판 수집: 광명시청, 구로구청, 금천구청, 강북구청, 노원구청, 도봉구청, 성북구청, 시흥시청, 부천시청, 안양시청
- 기관별 선택 UI와 게시판별 실제 수집 URL 분리
- 출처, 지역, 마감여부 필터
- 마감 공고 회색 표시
- 엑셀 다운로드
- 중복 공고 제거

## 프로젝트 구조

```text
.
├── app.py
├── requirements.txt
├── sites_config.json
├── collectors/
│   ├── base.py
│   ├── common_static.py
│   ├── local_gov_board.py
│   ├── narailter.py
│   ├── cleaneye_jobplus.py
│   ├── job_alio.py
│   └── jobaba.py
├── services/
│   ├── config_loader.py
│   └── runner.py
└── .streamlit/
    └── config.toml
```

## 실행 방법

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

macOS 또는 Linux에서는 가상환경 활성화 명령만 아래처럼 바꿔 실행합니다.

```bash
source .venv/bin/activate
```

## Streamlit Community Cloud 배포

1. 이 프로젝트 폴더를 GitHub 저장소에 업로드합니다.
2. Streamlit Community Cloud에서 새 앱을 생성합니다.
3. Repository를 선택합니다.
4. Main file path에 `app.py`를 입력합니다.
5. 배포를 실행합니다.

현재 활성 수집기는 `requests`, `beautifulsoup4` 기반입니다. Playwright 또는 Selenium 브라우저 드라이버는 배포 필수가 아니므로 별도의 `packages.txt`나 Playwright install script가 필요하지 않습니다.

## 설정 파일

수집 대상 사이트와 게시판 URL은 `sites_config.json`에서 관리합니다.

지자체는 화면에서는 기관명만 보이지만, 내부적으로는 기관에 속한 여러 게시판을 순회합니다.

예:

```json
{
  "name": "성북구청 > 채용공고",
  "collector": "local_gov_board",
  "list_url": "https://www.sb.go.kr/www/selectEminwonList.do?key=6483&searchCnd=employment"
}
```

## 엑셀 다운로드

수집 결과는 서버 파일로 저장하지 않고 Streamlit의 `st.download_button`을 통해 브라우저에서 직접 다운로드합니다.

## 보안 및 업로드 제외

이 프로젝트는 API 키, 비밀번호, 개인 인증 토큰을 사용하지 않습니다.

GitHub에 올리지 않을 파일은 `.gitignore`에 포함되어 있습니다.

- `.venv/`
- `__pycache__/`
- `logs/`
- `data/output/`
- `.streamlit/secrets.toml`
- 로컬 백업 파일

## 참고

외부 사이트 구조가 바뀌면 일부 수집기가 0건을 반환하거나 오류를 표시할 수 있습니다. 이 경우 `sites_config.json`의 URL 또는 테이블 컬럼 설정을 수정해야 합니다.
