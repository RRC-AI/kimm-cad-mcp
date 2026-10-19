# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
import pytest

from kimm_cad_mcp.parser import parse_shape_request


def test_korean_box_with_labels():
    result = parse_shape_request("가로 40mm, 세로 30mm, 높이 20mm 직육면체를 만들어줘")
    assert result.shape == "box"
    assert result.params == {"length": 40.0, "width": 30.0, "height": 20.0}


def test_korean_box_compact_dimensions():
    result = parse_shape_request("40x30x20 mm 박스")
    assert result.params == {"length": 40.0, "width": 30.0, "height": 20.0}


def test_korean_cylinder_diameter():
    result = parse_shape_request("직경 20mm 높이 50mm 원기둥")
    assert result.shape == "cylinder"
    assert result.params == {"radius": 10.0, "height": 50.0}


def test_cube_single_dimension():
    result = parse_shape_request("25 mm cube")
    assert result.params == {"length": 25.0, "width": 25.0, "height": 25.0}


def test_korean_flange_dimensions():
    result = parse_shape_request("외경 120 mm, 내경 50 mm, 두께 12 mm인 원형 플랜지")
    assert result.shape == "flange"
    assert result.params == {"outer_diameter": 120.0, "inner_diameter": 50.0, "thickness": 12.0}


def test_missing_dimensions_rejected_instead_of_invented():
    with pytest.raises(ValueError, match="필수 치수"):
        parse_shape_request("박스를 만들어줘")


def test_unknown_shape_rejected():
    with pytest.raises(ValueError):
        parse_shape_request("기어를 만들어줘")
