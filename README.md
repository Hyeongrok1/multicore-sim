# Problem 1 Docker 연결 시험

x86-64 Linux 컨테이너에서 gem5의 단일 O3 코어로 짧은 반복문을 실행합니다. gem5 통계 두 항목을 McPAT의 ARM A9 예제 XML에 넣고, McPAT이 계산한 전력과 면적으로 HotSpot의 단일 블록 입력을 만듭니다.

이 시험은 파일 전달과 도구 실행을 확인합니다. McPAT의 나머지 설정과 카운터는 ARM A9 예제 값이므로 이 시험의 전력과 온도는 과제 실험값으로 사용할 수 없습니다. PARSEC ROI 실행, 실제 CPU와 캐시 구성의 매핑, 블록별 칩 배치가 과제 실험에 필요합니다.

## PowerShell에서 실행

이 폴더에서 아래 명령을 실행합니다. 기존 Ubuntu 24.04 WSL 배포판에 Docker Engine이 설치되어 있어야 합니다.

```powershell
$linuxPath = (wsl -d Ubuntu-24.04 -- wslpath -a (Get-Location).Path).Trim()
New-Item -ItemType Directory -Force results | Out-Null
wsl -d Ubuntu-24.04 -u root -- docker build --network host -t skku-problem1:smoke $linuxPath
if ($LASTEXITCODE -ne 0) { throw 'Docker build failed' }
wsl -d Ubuntu-24.04 -u root -- docker run --rm --network none --mount "type=bind,source=$linuxPath/results,target=/output" skku-problem1:smoke
```

gem5 소스는 v26.0.0.0을 사용합니다. McPAT과 HotSpot은 기본값으로 각 저장소의 master를 사용합니다. 버전을 고정하려면 빌드 시 `--build-arg MCPAT_REF=<commit>`와 `--build-arg HOTSPOT_REF=<commit>`을 지정합니다. 첫 빌드는 gem5를 컴파일합니다. 병렬 작업 수는 `--build-arg BUILD_JOBS=2` 등으로 조절할 수 있습니다.

결과 폴더에서 `gem5/stats.txt`, `mcpat.xml`, `mcpat.log`, `chip.flp`, `chip.ptrace`, `chip.steady`를 확인할 수 있습니다.

