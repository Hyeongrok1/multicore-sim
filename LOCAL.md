# Docker 없이 실행하기

이 프로젝트는 호스트용 gem5, McPAT, HotSpot을 빌드해 직접 실행할 수 있습니다.
ARM Mac에서도 gem5 프로그램 자체는 ARM으로 실행하고, 그 안에서 x86 CPU를
시뮬레이션합니다. 도구 버전은 고정하고 각 팀원의 절대 경로는 Git에 넣지 않습니다.

## 1. OS 의존성

### macOS (Apple Silicon)

Xcode Command Line Tools가 필요합니다. 설치되어 있지 않다면 `xcode-select --install`을 실행합니다.

```bash
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install python@3.12 pkgconf
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-local.txt
```

gem5는 Linux를 주로 검증하는 upstream 프로젝트입니다. Mac 검증 결과와 남은 제한은
`VALIDATION.md`를 확인하세요. 로컬 빌드가 된다는 사실과 PARSEC 전체 실험을 완료했다는
사실은 구분해야 합니다.

### Ubuntu / Windows WSL2 Ubuntu

Windows에서는 PowerShell용 Python 대신 WSL2 Ubuntu 안에서 다음 명령을 실행합니다.

```bash
sudo apt update
sudo apt install build-essential git m4 python3-dev python3-venv zlib1g-dev pkg-config
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-local.txt
```

Python 3.10 이상과 C++20 컴파일러가 필요합니다. 제공하는 빌드 절차는 Python 3.12를
기준으로 검증합니다. KVM, GUI, protobuf 추적, HDF5 출력은 이 프로젝트의 필수 기능이
아니므로 최소 의존성만 설치할 수 있습니다.

## 2. 도구 빌드

저장소 루트에서 실행합니다.

```bash
.venv/bin/python scripts/setup_local.py --jobs 4
```

- `.tools/`에 고정된 버전의 소스를 가져와 네이티브 빌드합니다.
- `.local-tools.json`에 이 컴퓨터의 실행 파일 경로를 저장합니다.
- McPAT의 x86 32비트/SSE 전용 빌드 옵션을 사용하지 않습니다.
- Clang용 McPAT 생성자 선언 호환성 수정을 자동으로 적용합니다. 모델 계산식은 바꾸지 않습니다.
- gem5의 `PYTHON_CONFIG`는 환경 변수로 전달합니다. SCons 명령 뒤에 붙이는 변수 할당은
  v26에서 무시될 수 있으므로 이 스크립트를 사용하는 것이 편리합니다.
- 처음 빌드는 시간이 걸립니다. 이후에는 빌드 산출물을 유지한 채 증분 빌드합니다.
- 메모리가 부족하면 `--jobs 2`를 사용하세요.

이미 고정 버전 소스가 있으면 재사용할 수 있습니다.

```bash
.venv/bin/python scripts/setup_local.py \
  --gem5-source /absolute/path/to/gem5 \
  --mcpat-source /absolute/path/to/mcpat \
  --hotspot-source /absolute/path/to/HotSpot \
  --python-config /absolute/path/to/python3.12-config
```

기존 소스의 커밋이 고정 버전과 다르면 자동으로 덮어쓰지 않고 중단합니다.

## 3. 실제 gem5 실행을 포함하는 짧은 검사

```bash
.venv/bin/python -m problem1.run check --output local-check
```

이 명령은 필수 5개 CPU 구성에 대해 다음을 수행합니다.

1. 별도 크로스 컴파일러 없이 작은 정적 x86-64 ELF 테스트 프로그램을 생성합니다.
2. gem5 O3 코어와 실제 캐시·메모리 계층에서 프로그램을 실행합니다.
3. 프로그램의 `m5_work_begin/end`로 ROI 통계를 수집합니다.
4. 이 **실제 gem5 통계**를 McPAT 및 HotSpot으로 전달합니다.
5. 블록별 전력·온도와 성공 결과를 `local-check/_smoke/`에 저장합니다.

한 구성만 확인하려면 `--cores 1 --width 4`를 추가합니다. 기존 결과 디렉터리는
덮어쓰지 않으므로 재검사할 때는 `--output local-check-2`처럼 새 경로를 사용합니다.

**이 검사는 PARSEC 실험이 아닙니다.** 각 코어에 독립된 작은 프로세스를 올려 하드웨어,
ROI 처리, 실제 통계 스키마와 후처리 연결을 검사합니다. Linux 부팅, pthread/OpenMP,
PARSEC 작업 완료까지 검증했다는 의미는 아닙니다. 결과는 `__smoke__` / `selftest`로
표시되며 실험 집계에 포함되지 않습니다.

## 4. PARSEC 실행 (실험을 시작할 때만)

```bash
.venv/bin/python -m problem1.run plan
.venv/bin/python -m problem1.run run --output results \
  --workload blackscholes --cores 1 --width 4
```

첫 PARSEC 실행은 공식 kernel/disk 리소스를 `resources/`에 다운로드합니다.
로컬 이미지가 있으면 `--kernel`, `--disk`, `--root-partition`을 지정할 수 있습니다.
전체 sweep은 workload/core/width 필터를 제거합니다. 출력과 모델 범위는 README.md와
MODEL.md에 설명되어 있습니다.

실행 파일 경로 탐색 순서는 CLI `--gem5/--mcpat/--hotspot` → 환경 변수
`GEM5_BINARY/MCPAT_BINARY/HOTSPOT_BINARY` → `.local-tools.json` → PATH → 기존 Docker
경로입니다. 팀원이 동일한 디렉터리 이름을 쓸 필요는 없습니다.

## 협업

- Git에 공유: Python 코드, 설정, 고정 버전, 테스트, 문서.
- Git에서 제외: `.venv`, `.tools`, `.local-tools.json`, `resources`, 실험 출력.
- 팀원마다 1~3단계를 실행하고 검증 로그를 공유합니다.
- 성능 지표는 gem5의 **시뮬레이션 시간**입니다. 호스트 실행 시간이나 Mac/PC의
  실측 속도를 speedup으로 쓰지 않습니다.

Upstream 빌드 기준: https://www.gem5.org/documentation/general_docs/building
