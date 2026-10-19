#!/usr/bin/env python
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""Create a translucent-view copy of a FreeCAD/KIMM-CAD FCStd file.

The solid geometry is left untouched. Only the per-object Transparency value in
GuiDocument.xml is changed, so STEP/STL export accuracy is not affected.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path


EXTERIOR_PATTERNS = (
    "*casing*",
    "*shell*",
    "*housing*",
    "*cover*",
    "*enclosure*",
    "*cabinet*",
    "*frameplate*",
    "*pressureplate*",
    "wall*",
    "*slab*",
)

VIEW_PROVIDER_RE = re.compile(
    rb'(<ViewProvider\b[^>]*\bname="([^"]+)"[^>]*>.*?</ViewProvider>)',
    re.DOTALL,
)
TRANSPARENCY_RE = re.compile(
    rb'(<Property\s+name="Transparency"[^>]*>\s*'
    rb'<Integer\s+value=")\d+("\s*/>\s*</Property>)',
    re.DOTALL,
)


def _split_names(values: list[str]) -> list[str]:
    names: list[str] = []
    for value in values:
        names.extend(item.strip() for item in value.split(",") if item.strip())
    return names


def _matches(name: str, patterns: list[str], apply_all: bool) -> bool:
    if apply_all:
        return True
    lowered = name.casefold()
    return any(fnmatch.fnmatchcase(lowered, pattern.casefold()) for pattern in patterns)


def _update_gui_xml(
    data: bytes, patterns: list[str], transparency: int, apply_all: bool
) -> tuple[bytes, list[str]]:
    changed: list[str] = []

    def replace_view(match: re.Match[bytes]) -> bytes:
        block = match.group(1)
        name = match.group(2).decode("utf-8", errors="replace")
        if not _matches(name, patterns, apply_all):
            return block
        updated, count = TRANSPARENCY_RE.subn(
            lambda item: item.group(1)
            + str(transparency).encode("ascii")
            + item.group(2),
            block,
            count=1,
        )
        if count:
            changed.append(name)
        return updated

    return VIEW_PROVIDER_RE.sub(replace_view, data), changed


def create_translucent_copy(
    source: Path,
    destination: Path,
    patterns: list[str],
    transparency: int,
    apply_all: bool,
) -> list[str]:
    if source.suffix.casefold() != ".fcstd":
        raise ValueError("FCStd 파일만 지원합니다.")
    if not source.is_file() or source.stat().st_size == 0:
        raise FileNotFoundError(f"파일을 찾을 수 없거나 비어 있습니다: {source}")
    if source.resolve() == destination.resolve():
        raise ValueError("원본과 출력 경로는 다르게 지정해 주세요.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_handle = tempfile.NamedTemporaryFile(
        prefix=destination.stem + "_", suffix=".tmp", dir=destination.parent, delete=False
    )
    temp_path = Path(temp_handle.name)
    temp_handle.close()
    changed: list[str] = []

    try:
        with zipfile.ZipFile(source, "r") as input_zip, zipfile.ZipFile(
            temp_path, "w"
        ) as output_zip:
            if "GuiDocument.xml" not in input_zip.namelist():
                raise ValueError(
                    "GuiDocument.xml이 없습니다. KIMM-CAD에서 한 번 열고 FCStd로 저장한 후 다시 실행하세요."
                )
            for info in input_zip.infolist():
                payload = input_zip.read(info.filename)
                if info.filename == "GuiDocument.xml":
                    payload, changed = _update_gui_xml(
                        payload, patterns, transparency, apply_all
                    )
                output_zip.writestr(info, payload)

        if not changed:
            requested = "모든 객체" if apply_all else ", ".join(patterns)
            raise ValueError(f"조건에 맞는 객체가 없습니다: {requested}")

        with zipfile.ZipFile(temp_path, "r") as check_zip:
            bad_entry = check_zip.testzip()
            if bad_entry is not None:
                raise ValueError(f"생성된 FCStd 압축 검증 실패: {bad_entry}")
        os.replace(temp_path, destination)
        return changed
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FCStd 형상은 유지하고 표시 투명도만 조절합니다."
    )
    parser.add_argument("input", type=Path, help="원본 .FCStd 파일")
    parser.add_argument(
        "--output", type=Path, help="출력 .FCStd (기본: <이름>_내부보기.FCStd)"
    )
    parser.add_argument(
        "--transparency",
        type=int,
        default=60,
        choices=range(0, 101),
        metavar="0..100",
        help="0=불투명, 100=완전 투명 (기본 60)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--all", action="store_true", help="모든 객체에 적용")
    mode.add_argument(
        "--exterior",
        action="store_true",
        help="일반적인 외피/커버 이름에만 자동 적용",
    )
    mode.add_argument(
        "--objects",
        action="append",
        default=[],
        metavar="NAME[,NAME...]",
        help="객체명 또는 와일드카드(*, ?) 패턴",
    )
    args = parser.parse_args()

    source = args.input.expanduser().resolve()
    destination = (
        args.output.expanduser().resolve()
        if args.output
        else source.with_name(source.stem + "_내부보기.FCStd")
    )
    patterns = list(EXTERIOR_PATTERNS) if args.exterior else _split_names(args.objects)

    try:
        changed = create_translucent_copy(
            source, destination, patterns, args.transparency, args.all
        )
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1

    print(f"[완료] 투명도 {args.transparency}%: {', '.join(changed)}")
    print(f"[출력] {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
