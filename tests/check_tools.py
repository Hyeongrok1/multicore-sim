"""Optional synthetic integration check. Does NOT launch gem5/PARSEC."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from problem1.run import postprocess
from tests.fixture import fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcpat", required=True)
    parser.add_argument("--hotspot", required=True)
    parser.add_argument("--cores", type=int, choices=(1, 4, 8), default=4)
    parser.add_argument("--width", type=int, choices=(2, 4, 8), default=4)
    args = parser.parse_args()
    config, manifest, stats = fixture(args.cores, args.width)
    with TemporaryDirectory(prefix="problem1-synthetic-") as temp:
        directory = Path(temp)
        gem5 = directory / "gem5"
        gem5.mkdir()
        (gem5 / "config.json").write_text(json.dumps(config))
        (gem5 / "roi.json").write_text(json.dumps(manifest))
        (gem5 / "stats.txt").write_text(stats)
        tools = SimpleNamespace(mcpat=str(Path(args.mcpat).resolve()),
                                hotspot=str(Path(args.hotspot).resolve()), tool_timeout=1800)
        try:
            result = postprocess(directory, tools)
        except Exception:
            for name in ("mcpat.log", "hotspot.log"):
                if (directory / name).exists():
                    print((directory / name).read_text()[-3000:])
            raise
        assert len(result["power"]["blocks"]) == 3*args.cores + 4
        assert (directory / "result.json").is_file()
        print(f"PASS: synthetic {args.cores}-core/{args.width}-wide McPAT -> HotSpot pipeline; no benchmark executed")


if __name__ == "__main__":
    main()
