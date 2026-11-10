# Problem 1: gem5 → McPAT → HotSpot

PARSEC 3.0의 `simsmall` ROI를 x86 멀티코어 O3 CPU에서 실행하고, 구성별 성능·전력·정상상태 온도를 계산하는 흐름입니다. 실제 PARSEC 실험 결과는 포함하지 않습니다.

## 구현 범위

| 실험 | 변경 | 고정 |
|---|---|---|
| Core sweep | 1, 4, 8 cores | fetch/issue/commit 등 파이프라인 폭 4 |
| Width sweep | 2, 4, 8-wide | 4 cores |

- 워크로드: blackscholes, canneal, freqmine, streamcluster
- 중복 `(4 cores, 4-wide)` 재사용: **20개 실행**, 정규화 결과는 **24행**
- Linux full-system, 2 GHz, 코어별 32 KiB L1I/L1D, 공유 2 MiB L2, 3 GiB dual-channel DDR4
- `gcc-hooks`의 `workbegin`에서 통계 초기화, `workend`에서 저장 후 종료
- PARSEC 스레드 수 및 `OMP_NUM_THREADS`를 코어 수와 일치시킴
- 실제 `config.json`, ROI 통계를 읽어 코어별 McPAT 입력 생성
- 코어 로직/L1/L2/버스/메모리 컨트롤러의 전력 및 면적을 중복 없이 HotSpot에 전달
- 각 sweep의 최소 구성 ROI 시간으로 speedup 정규화, CSV와 그래프 생성

**전력·온도는 아키텍처 모델의 추정치입니다.** 물리 설계와 1:1로 대응하지 않는 부분, 고정 가정과 제외 범위는 [MODEL.md](MODEL.md)를 확인하세요. 예전 `smoke.py`는 도구 연결 확인용으로만 남겨 두었습니다.

## 기본 실행 환경: 로컬 설치

Docker는 선택 사항입니다. Mac/Linux/WSL2의 설치, 네이티브 빌드, 실제 gem5 ROI를
포함한 짧은 연결 검사는 [LOCAL.md](LOCAL.md)를 따라 실행하세요.

```bash
.venv/bin/python scripts/setup_local.py --jobs 4
.venv/bin/python -m problem1.run check --output local-check
```

`check`는 PARSEC 성능 실험을 돌리지 않습니다. gem5의 작은 테스트 프로그램 실행부터
McPAT·HotSpot까지 실제로 연결하며, 결과를 `__smoke__`로 구분해 저장합니다.

## 1. 실험 없이 코드 검증

호스트 Python 3.10 이상에서 저장소 루트로 이동한 뒤:

```bash
python3 -m unittest discover -v
python3 -m compileall -q problem1 tests
python3 -m problem1.run plan
```

위 명령은 gem5나 PARSEC을 실행하지 않고 다운로드도 하지 않습니다. 단위 테스트는 합성 데이터로 ROI 선택, XML 매핑, 전력 중복 계산 방지, 열 입력, 정규화를 검증합니다.

## 2. 선택 사항: Docker 실행 환경 빌드

Docker Engine이 실행 중이어야 합니다. 권장 환경은 Linux x86-64 또는 Windows WSL2의 Linux x86-64입니다.

```bash
docker build --platform linux/amd64 --build-arg BUILD_JOBS=4 -t multicore-sim:problem1 .
```

첫 빌드는 gem5를 컴파일하므로 시간과 메모리가 필요합니다. 메모리가 부족하면 `BUILD_JOBS=2`로 줄이세요. Apple Silicon에서도 amd64 에뮬레이션으로 빌드할 수 있지만 실행은 매우 느릴 수 있습니다. 이 구현은 KVM을 요구하지 않습니다.

버전은 Dockerfile에 고정했습니다.

- gem5: `v26.0.0.0`
- McPAT: `74d4759f3ba2dff8f5a69e07a68efdb46b42fb8c`
- HotSpot: `f18831e48cef5d62580585cca0d7fab6c71bc3cc`

컨테이너 기본 명령은 **실험 계획 출력**입니다. 이미지 빌드나 아래 명령만으로 벤치마크가 시작되지는 않습니다.

```bash
docker run --rm multicore-sim:problem1
```

## 3. 나중에 실험 실행

공식 gem5 리소스 `x86-linux-kernel-4.19.83` 및 `x86-parsec`의 `1.0.0` 버전을 사용합니다. 첫 실행에는 네트워크와 큰 디스크 이미지 다운로드 공간이 필요합니다. `/resources`를 유지하면 재다운로드하지 않습니다. PARSEC 3.0, gcc-hooks, simsmall 입력이 들어 있는 공식 이미지의 경로 `/home/gem5/parsec-benchmark`를 사용합니다.

```bash
mkdir -p results resources
docker run --rm \
  --mount "type=bind,source=$(pwd)/results,target=/output" \
  --mount "type=bind,source=$(pwd)/resources,target=/resources" \
  multicore-sim:problem1 \
  python3 -m problem1.run run --output /output --resource-directory /resources \
  --workload blackscholes --cores 1 --width 4
```

전체 실행은 마지막 줄의 `--workload ... --cores ... --width ...` 필터를 제거합니다. O3로 Linux 부팅부터 실행하므로 KVM 없이 동작하지만 상당히 느립니다. ROI 통계에는 부팅 시간이 포함되지 않습니다. 워밍업은 ROI 이전의 실제 프로그램 실행이며 ROI 시작 시 캐시는 유지합니다.

직접 준비한 이미지도 사용 가능합니다. Linux 커널과 디스크를 `/inputs` 등에 마운트하고 아래 인자를 추가하세요.

```text
--kernel /inputs/vmlinux --disk /inputs/parsec.img --root-partition 1
```

사용자 이미지는 공식 이미지와 같은 PARSEC 경로, `gcc-hooks`, simsmall 입력, `m5 readfile` 부팅 스크립트가 필요합니다. ROI가 없는 이미지/빌드는 성공으로 처리하지 않습니다. 자동 다운로드를 사용할 때는 오래된 리소스의 gem5 버전 메타데이터 필터만 해제하며, 리소스 버전과 해시 검증은 유지합니다.

이미 존재하는 실행 디렉터리는 덮어쓰지 않습니다. 실패 후 다시 시뮬레이션할 때는 새 `--output`을 지정하거나 해당 실패 디렉터리를 직접 정리하세요. 기본 시간 제한은 호스트 7일/실행, 시뮬레이션 10,000초(부팅 포함)이며 `--simulation-timeout`, `--max-ticks`로 바꿀 수 있습니다.

## 4. 후처리 재실행 및 집계

gem5가 완료되어 `gem5/roi.json`, `config.json`, `stats.txt`가 있으면 다시 시뮬레이션할 필요가 없습니다. 위 컨테이너 명령에서 `run`을 `postprocess`로 바꾸고 같은 필터를 사용하세요.

```bash
python3 -m problem1.run postprocess --output /output --workload blackscholes --cores 1 --width 4
python3 -m problem1.run summarize --output /output
```

`postprocess`는 McPAT/HotSpot이 설치된 컨테이너에서 실행합니다. `summarize`는 전체 20개 결과를 요구하며 누락된 구성을 임의로 정규화하지 않습니다. 호스트에서 집계하려면 `python3 -m pip install -r requirements.txt`가 필요합니다.

## 출력

각 `results/<workload>/c<cores>-w<width>/`에 다음이 저장됩니다.

- `command.json`, `gem5.log`: 실행 인자와 진단 로그
- `gem5/config.json`, `gem5/stats.txt`, `gem5/roi.json`: 실제 구성, 통계, ROI/SimObject 경로
- `mcpat.xml`, `mapping.json`, `mcpat.log`: 전력 입력, 매핑 감사 정보, 원본 출력
- `power.json`: 칩 전체 및 블록별 dynamic/static 전력·면적
- `chip.flp`, `chip.ptrace`, `chip.steady`, `hotspot.log`: 열 모델 입력·출력
- `result.json`: 모든 단계 성공 후에만 생성되는 결과

전체 결과 루트에는 `summary.csv`, `components.csv`, `cores.png/pdf`, `width.png/pdf`가 생성됩니다. 온도 대표값은 **칩 블록의 최고 정상상태 온도**이며 면적 가중 평균도 함께 저장합니다. 패키지·히트싱크 노드는 최고 온도 계산에서 제외합니다.

## 파일 구성 및 검증 한계

- `problem1/gem5_config.py`: gem5 full-system 구성 및 ROI 제어
- `problem1/mcpat.py`, `stats.py`: 실제 구성/통계 매핑
- `problem1/thermal.py`: McPAT 상세 출력 파싱, HotSpot 입력 및 결과
- `problem1/run.py`, `plots.py`: 실행 자동화, CSV, 그래프
- `tests/`: 합성 데이터 단위 테스트와 실제 후처리 도구 연결 검사

검증한 환경, 실제 실행 범위와 남은 제한은 [VALIDATION.md](VALIDATION.md)에 기록합니다.
단위 테스트, 짧은 gem5 실행 검사, Linux/PARSEC 전체 실행을 구분합니다.

합성 통계로 실제 McPAT/HotSpot만 검사하려면(벤치마크 실행 없음):

```bash
python3 -m tests.check_tools --mcpat /opt/mcpat/mcpat --hotspot /opt/HotSpot/hotspot
```
