# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
from kimm_cad_mcp.strategy import select_generation_method


def test_box_uses_parameter_template():
    result = select_generation_method("가로 40 세로 30 높이 20 박스")
    assert result.method == "parameter_template"
    assert not result.requires_python


def test_repeated_holes_use_python_pattern():
    result = select_generation_method("직경 10 mm 홀 6개를 동일한 간격으로 배열")
    assert result.method == "python_pattern"
    assert result.requires_saved_script
    assert "동일 요소의 반복 배치가 포함됨" in result.reasons


def test_twisted_repeated_blades_use_loft_sweep_first():
    result = select_generation_method("비틀림 곡면 블레이드 3개를 원형 배열")
    assert result.method == "python_loft_sweep"
    assert result.requires_saved_script
    assert "Loft or Sweep" in result.construction


def test_unknown_shape_defaults_to_saved_python():
    result = select_generation_method("특수한 기계 형상을 생성")
    assert result.method == "python_pattern"
    assert result.requires_saved_script
