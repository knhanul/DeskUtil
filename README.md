# PdfDiff

PyQt6 기반의 Windows 데스크톱 문서 유틸리티 애플리케이션입니다. PDF 비교, PDF 생성, 문서 검색 기능을 하나의 통합된 UI에서 제공합니다. 동일한 코드베이스에서 빌드 타겟(`posid`, `post`, `nuni`)에 따라 앱 이름/아이콘/테마 색상을 분리하여 배포할 수 있습니다.

## 주요 기능

| 기능 | 메뉴명 | 설명 |
| --- | --- | --- |
| PDF 지정 영역 비교 | 📄 PDF 지정 영역 비교 | 두 PDF에서 사용자가 지정한 영역(AREA)을 추출해 정규화 후 문자열 단위로 정밀 비교 |
| PDF 전체 비교 | 📄 PDF 전체 비교 | 페이지 단위 전체 비교. 헤더/푸터 영역을 드래그로 제외 영역으로 설정 가능 |
| 문서 찾기 | 🔍 문서 찾기 | 디렉터리를 색인화하여 PDF/DOCX/HWP/HWPX/XLSX 등의 본문 텍스트를 전문 검색(FTS5) |

### 지원 문서 포맷 (문서 찾기)
`.txt`, `.md`, `.py`, `.js`, `.html`, `.css`, `.json`, `.xml`, `.pdf`, `.docx`, `.doc`, `.hwp`, `.hwpx`, `.cell`, `.xlsx`, `.xls`

## 프로젝트 구조

```
PdfDiff/
├── main.py                      # 엔트리포인트
├── build.py                     # PyInstaller 빌드 스크립트
├── requirements.txt             # 의존성 목록
├── app/
│   ├── main_window.py           # 메인 윈도우(사이드바 + 도구 컨테이너)
│   ├── common/
│   │   ├── resources.py         # 타겟별 리소스/버전 로딩
│   │   ├── styles.py            # QSS 스타일
│   │   ├── pdf_compare_worker.py# PDF 비교 백그라운드 스레드
│   │   ├── pdf_search_helper.py # PDF 텍스트 검색 헬퍼
│   │   └── loading_dialog.py    # 로딩 다이얼로그
│   └── tools/
│       ├── pdf_compare.py           # PDF 지정 영역 비교
│       ├── pdf_header_footer_compare.py  # PDF 전체 비교
│       ├── document_search_ui.py    # 문서 찾기 UI
│       └── integrated_previewer.py  # 통합 문서 미리보기
├── configs/
│   ├── settings.py              # 타겟 로딩 로직 (환경변수/실행파일명에서 타겟 추출)
│   ├── target_posid.py          # posid 타겟 설정
│   ├── target_post.py           # post 타겟 설정
│   ├── target_nuni.py           # nuni 타겟 설정
│   └── target_qamate.py         # qamate 타겟 설정(빌드 대상 아님)
├── doc_search/                  # 문서 검색 엔진
│   ├── scanner.py               # 파일 스캐너
│   ├── indexer.py               # 색인 관리자
│   ├── search.py                # 검색 API
│   ├── database/fts5_db.py      # SQLite FTS5 백엔드
│   └── extractors/              # 포맷별 텍스트 추출기
│       ├── pdf_extractor.py
│       ├── docx_extractor.py
│       ├── hwp_extractor.py
│       ├── xlsx_extractor.py
│       ├── cell_extractor.py
│       └── text_extractor.py
├── assets/                      # 타겟별 아이콘/로고
│   ├── posid/
│   ├── post/
│   ├── nuni/
│   └── qamate/
└── doc_search.db                # 색인 DB (실행 시 생성)
```

## 빌드 타겟

`configs/settings.py`가 실행 환경에 따라 타겟을 자동으로 로딩합니다.

1. 환경변수 `BUILD_TARGET` (빌드 시 `build.py`가 설정)
2. 실행 파일 이름에서 추출 (예: `nunidesk_posid.exe` → `posid`)
3. 기본값: `posid`

| 타겟 | 앱 이름 | 회사명 | 테마색 | 아이콘 |
| --- | --- | --- | --- | --- |
| `posid` | Posid 데스크 | 우체국금융개발원 | `#004b93` | `posid_icon.ico` |
| `post` | nunidesk | 우정정보관리원 | `#6b46c1` | `post_icon.ico` |
| `nuni` | nunidesk | Nuni | `#0f766e` | `nuni_icon.ico` |

## 요구사항

- Windows 10/11
- Python 3.12+
- 의존성: `requirements.txt` 참조
  - PyQt6, PyMuPDF, python-docx, openpyxl, pandas, pyxlsb, pyhwpx, olefile, Pillow
  - 빌드 시 추가: `pyinstaller`

## 개발 환경 설정

```powershell
# 1. 가상환경 생성 및 활성화
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 의존성 설치 (가상환경 활성화 상태에서)
pip install -r requirements.txt
pip install pyinstaller

# 3. 개발 모드 실행 (기본 타겟: posid)
python main.py

# 특정 타겟으로 개발 실행
$env:BUILD_TARGET = "post"; python main.py
$env:BUILD_TARGET = "nuni"; python main.py
```

> **주의**: `pip install -r requirements.txt` 실행 시 프롬프트가 `(.venv)`로 표시되어 있는지 반드시 확인하세요. 가상환경이 활성화되지 않은 상태에서 설치하면 전역 Python에 패키지가 설치되어 빌드 시 `ModuleNotFoundError`가 발생합니다.

## 빌드 (PyInstaller)

`build.py`를 사용해 타겟별 실행 파일을 생성합니다.

```powershell
# 가상환경 활성화 상태에서 실행
python build.py --target posid --version 2.0.1 --release-date 2026-08-20
```

### 인자
| 인자 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `--target` | O | - | `posid` / `post` / `nuni` 중 하나 |
| `--version` | X | `1.2.0` | 앱 버전 |
| `--release-date` | X | 오늘 날짜 | 출시일자 (YYYY-MM-DD) |

### 빌드 과정
1. `app/common/build_version.txt`에 버전/출시일 기록
2. 환경변수 `BUILD_TARGET`, `APP_VERSION`, `PDF_COMPARE_RELEASE_DATE` 설정
3. PyInstaller로 `main.py`를 엔트리포인트로 `nunidesk_<target>.exe` 생성
   - `--windowed` (콘솔 창 없음)
   - 타겟 아이콘 적용 (`assets/<target>/<target>_icon.ico`)
   - `assets/`, `assets/<target>/`, `app/common/build_version.txt` 번들링
   - `configs.*`, `app.tools.*` 모듈을 hidden-import로 명시

### 결과물
- `dist/nunidesk_<target>/nunidesk_<target>.exe` — 실행 파일
- `build/` — 중간 산출물
- `nunidesk_<target>.spec` — PyInstaller 스펙 파일 (자동 생성)

### 빌드 시 주의사항
- 빌드 로그에 `Processing standard module hook 'hook-PyQt6.py' ...` 라인이 나타나야 PyQt6가 정상 번들링된 것입니다. 해당 라인이 없다면 venv에 PyQt6가 설치되지 않은 것입니다.
- `dist/<app>` 디렉터리 삭제 시 `PermissionError: [WinError 5]`가 발생하면 이전 빌드의 실행 파일이 실행 중인 것입니다. 앱을 종료한 후 다시 빌드하세요.

## 라이선스 메뉴 / 내부 보고서

타겟 설정의 `ENABLE_LICENSE_MENU`, `ENABLE_INTERNAL_REPORT` 플래그로 메뉴 노출을 타겟별로 제어합니다 (`configs/target_*.py` 참조).

## 문제 해결

### `ModuleNotFoundError: No module named 'PyQt6'` (빌드된 exe 실행 시)
venv에 PyQt6가 설치되지 않은 상태에서 빌드했을 때 발생합니다. 가상환경을 활성화한 후 `pip install -r requirements.txt`를 다시 실행하세요.

### `PermissionError: [WinError 5]` (빌드 중)
이전 버전의 실행 파일이 실행 중이어서 `dist/` 디렉터리를 삭제하지 못한 경우입니다. 실행 중인 앱을 모두 종료하세요.
