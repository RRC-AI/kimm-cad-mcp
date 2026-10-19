# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""Deterministic Korean/English parser for supported basic CAD shapes."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ShapeRequest:
    shape: str
    params: dict[str, float]


_NUMBER = r"(\d+(?:\.\d+)?)"


def _labeled(text: str, labels: tuple[str, ...]) -> float | None:
    names = "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
    before = re.search(rf"(?:{names})\s*[:=]?\s*{_NUMBER}\s*(?:mm|밀리미터)?", text, re.I)
    if before:
        return float(before.group(1))
    after = re.search(rf"{_NUMBER}\s*(?:mm|밀리미터)?\s*(?:의\s*)?(?:{names})(?!\w)", text, re.I)
    return float(after.group(1)) if after else None


def _require(value: float | None, label: str) -> float:
    if value is None:
        raise ValueError(f"필수 치수가 없습니다: {label}. 모든 치수는 mm로 지정해 주세요.")
    return value


def parse_shape_request(text: str) -> ShapeRequest:
    normalized = text.strip().lower().replace("×", "x")
    if not normalized:
        raise ValueError("형상 요청이 비어 있습니다.")

    numbers = [float(value) for value in re.findall(_NUMBER, normalized)]

    if any(word in normalized for word in ("플랜지", "flange")):
        outer_diameter = _labeled(normalized, ("외경", "바깥지름", "outer diameter", "od"))
        inner_diameter = _labeled(normalized, ("내경", "안지름", "inner diameter", "id"))
        thickness = _labeled(normalized, ("두께", "thickness"))
        outer_diameter = outer_diameter if outer_diameter is not None else (numbers[0] if numbers else None)
        inner_diameter = inner_diameter if inner_diameter is not None else (numbers[1] if len(numbers) > 1 else None)
        thickness = thickness if thickness is not None else (numbers[2] if len(numbers) > 2 else None)
        outer_diameter = _require(outer_diameter, "외경")
        inner_diameter = _require(inner_diameter, "내경")
        thickness = _require(thickness, "두께")
        if inner_diameter >= outer_diameter:
            raise ValueError("플랜지 내경은 외경보다 작아야 합니다.")
        return _validated(
            "flange",
            {
                "outer_diameter": outer_diameter,
                "inner_diameter": inner_diameter,
                "thickness": thickness,
            },
        )

    if any(word in normalized for word in ("원기둥", "원통", "실린더", "cylinder")):
        radius = _labeled(normalized, ("반지름", "radius"))
        diameter = _labeled(normalized, ("지름", "직경", "diameter", "dia"))
        height = _labeled(normalized, ("높이", "길이", "height", "length"))
        if radius is None and diameter is not None:
            radius = diameter / 2.0
        radius = radius if radius is not None else (numbers[0] if numbers else None)
        height = height if height is not None else (numbers[1] if len(numbers) > 1 else None)
        return _validated(
            "cylinder",
            {"radius": _require(radius, "반지름 또는 지름"), "height": _require(height, "높이")},
        )

    if any(word in normalized for word in ("구체", "구형", "구 모양", "sphere", "ball")):
        radius = _labeled(normalized, ("반지름", "radius"))
        diameter = _labeled(normalized, ("지름", "직경", "diameter", "dia"))
        if radius is None and diameter is not None:
            radius = diameter / 2.0
        radius = radius if radius is not None else (numbers[0] if numbers else None)
        return _validated("sphere", {"radius": _require(radius, "반지름 또는 지름")})

    if any(
        word in normalized
        for word in ("박스", "상자", "직육면체", "정육면체", "큐브", "box", "cube")
    ):
        length = _labeled(normalized, ("가로", "길이", "length"))
        width = _labeled(normalized, ("세로", "폭", "너비", "width"))
        height = _labeled(normalized, ("높이", "height"))
        is_cube = any(word in normalized for word in ("정육면체", "큐브", "cube"))
        if is_cube:
            side = length or width or height or (numbers[0] if numbers else None)
            side = _require(side, "한 변")
            length = width = height = side
        else:
            length = length if length is not None else (numbers[0] if numbers else None)
            width = width if width is not None else (numbers[1] if len(numbers) > 1 else None)
            height = height if height is not None else (numbers[2] if len(numbers) > 2 else None)
        return _validated(
            "box",
            {
                "length": _require(length, "가로/길이"),
                "width": _require(width, "세로/폭"),
                "height": _require(height, "높이"),
            },
        )

    raise ValueError(
        "지원 형상을 찾지 못했습니다. 현재 기본 형상은 박스/정육면체, 원기둥, 구체, 플랜지입니다."
    )


def _validated(shape: str, params: dict[str, float]) -> ShapeRequest:
    if any(value <= 0 or value > 1_000_000 for value in params.values()):
        raise ValueError("모든 치수는 0보다 크고 1,000,000 mm 이하여야 합니다.")
    return ShapeRequest(shape=shape, params=params)
