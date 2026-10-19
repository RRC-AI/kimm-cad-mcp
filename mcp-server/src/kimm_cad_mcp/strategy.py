# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""Select a KIMM-CAD geometry generation method from request complexity."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GenerationDecision:
    method: str
    reasons: tuple[str, ...]
    requires_python: bool
    requires_saved_script: bool
    construction: str
    verification: tuple[str, ...]

    def to_dict(self) -> dict:
        value = asdict(self)
        value["reasons"] = list(self.reasons)
        value["verification"] = list(self.verification)
        return value


_TEMPLATES = ("박스", "상자", "직육면체", "정육면체", "원통", "원기둥", "구체", "플랜지", "box", "cube", "cylinder", "sphere", "flange")
_REPEATED = ("반복", "패턴", "배열", "동일한 간격", "등간격", "원형 배열", "array", "pattern", "bolt hole", "블레이드")
_SURFACED = ("비틀림", "트위스트", "곡면", "곡선", "로프트", "스윕", "익형", "가변 단면", "twist", "surface", "curved", "loft", "sweep", "airfoil")
_COMBINED = ("결합", "여러 요소", "조립", "구성", "boolean", "fuse", "cut")
_VERIFY = ("dimensions", "repetition_count", "solid_count", "shape_validity", "visibility")


def _has_repetition(text: str) -> bool:
    return any(term in text for term in _REPEATED) or bool(re.search(r"(?:^|\s)[2-9]\d*\s*개", text))


def select_generation_method(request: str) -> GenerationDecision:
    text = request.strip().lower()
    if not text:
        raise ValueError("형상 요청이 비어 있습니다.")

    has_surface = any(term in text for term in _SURFACED)
    has_repetition = _has_repetition(text)
    has_combination = any(term in text for term in _COMBINED)

    if has_surface:
        reasons = ["비틀림 또는 곡면/가변 단면이 포함됨"]
        if has_repetition:
            reasons.append("동일 요소의 반복 배치가 포함됨")
        if has_combination:
            reasons.append("여러 요소의 결합이 필요함")
        return GenerationDecision(
            method="python_loft_sweep",
            reasons=tuple(reasons),
            requires_python=True,
            requires_saved_script=True,
            construction="Define multiple sections, build one reference with Loft or Sweep, then rotate/array copies when repeated.",
            verification=_VERIFY,
        )

    if has_repetition or has_combination:
        reasons = []
        if has_repetition:
            reasons.append("동일 요소의 반복 배치가 포함됨")
        if has_combination:
            reasons.append("여러 요소의 결합이 필요함")
        return GenerationDecision(
            method="python_pattern",
            reasons=tuple(reasons),
            requires_python=True,
            requires_saved_script=True,
            construction="Create one reference element in a function and place copies with a loop using rotation or an array.",
            verification=_VERIFY,
        )

    if any(term in text for term in _TEMPLATES):
        return GenerationDecision(
            method="parameter_template",
            reasons=("단일 정형 형상으로 파라미터화 가능",),
            requires_python=False,
            requires_saved_script=False,
            construction="Use the matching parametric KIMM-CAD template.",
            verification=_VERIFY,
        )

    return GenerationDecision(
        method="python_pattern",
        reasons=("정형 파라미터 템플릿으로 안전하게 분류되지 않음",),
        requires_python=True,
        requires_saved_script=True,
        construction="Create an explicit Python function for the requested geometry and validate the result.",
        verification=_VERIFY,
    )
