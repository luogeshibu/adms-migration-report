#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
合并同一变电站的多个 XML 格式 .g 文件。

使用方法：
1. 将脚本放在工作目录中；
2. 在脚本同级创建 input_g_files 文件夹，并放入待处理的 .g 文件；
3. 直接修改脚本开头“用户可修改配置”中的数值；
4. 运行：python merge_g_feeders.py
5. 结果自动输出到脚本同级的 output_g_files 文件夹。

最终处理规则：
1. 文件名按“-”分隔，第三段是变电站名称，第四段开头数字是馈线号；按馈线号数值升序处理。
2. 每个文件必须只有一个直属 Layer。
3. 在任何平移和合并之前，先循环清理每个源文件：
   Layer 下任意图元只要在 x/y、x1/y1、x2/y2、cx/cy、mergex/mergey 或 d 路径中出现负坐标，
   就删除整个图元，并清理 link、node_area、p_FatherObjId 中指向被删除图元的引用。
4. 清理后，将所有位置坐标统一取整：四舍五入，0.5 向远离 0 的方向取整。
5. 完整使用最小馈线文件作为基准文件；后续文件只复制唯一 Layer 下的子图元，不复制后续 G、Layer、Theme。
6. 以第一张基准图最上面的有效水平 Bus 为母线基准；后续馈线只做纵向平移，使母线与基准母线对齐。
7. 相邻馈线按真实坐标范围严格保持 FEEDER_GAP 指定的水平间隔：
      X 偏移 = 当前已合并最大 X + FEEDER_GAP - 当前馈线最小 X
8. 最终 Layer 内图元 id 必须唯一。发生冲突时生成新 ID，并同步修改：
      link、node_area、p_FatherObjId。
   link/node_area 中允许存在没有同名 XML 图元的“虚拟拓扑节点 ID”，但不同馈线之间仍会隔离其命名空间。
9. 所有馈线合并完毕后，再计算整个合并图的最小 X、最小 Y，并整体平移：
      全图 X 偏移 = LEFT_MARGIN - 全图最小 X
      全图 Y 偏移 = TOP_MARGIN - 全图最小 Y
10. 右边框和下边框最后处理：
      G.w = G.width  = 合并后最大 X + RIGHT_MARGIN
      G.h = G.height = 合并后最大 Y + BOTTOM_MARGIN
    所有根节点尺寸统一输出整数。
11. 最终校验：坐标均为整数、无负坐标、图元 ID 唯一、真实图元引用有效、母线保持对齐、相邻馈线间隔正确。

目录结构：
    merge_g_feeders.py
    input_g_files\
        JED-CTL-ADF-15.sln.pic.g
        JED-CTL-ADF-16.sln.pic.g
    output_g_files\
        JED-CTL-ADF-merged-15-16.sln.pic.g
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable, Iterator


# ============================================================================
# 用户可修改配置
# 只需要修改下面这些值，然后直接运行脚本即可。
# 所有数值必须是大于或等于 0 的整数。
# ============================================================================

# 相邻两个馈线图形实际边界之间的水平间隔。
# 例如可修改为：300、400、500。
FEEDER_GAP = 300

# 最终合并图形与画布四个边框之间的实际边距。
LEFT_MARGIN = 300
TOP_MARGIN = 300
RIGHT_MARGIN = 300
BOTTOM_MARGIN = 300

# 输入、输出目录名称。目录都位于本脚本所在目录下。
INPUT_FOLDER_NAME = "input_g_files"
OUTPUT_FOLDER_NAME = "output_g_files"

# 只处理以 .g 结尾的文件，目录中的其他文件会被忽略。
INPUT_FILE_PATTERN = "*.g"

# ============================================================================
# 以下为程序逻辑，一般不需要修改。
# ============================================================================


# 匹配 d 属性中的坐标点，例如：903,625、-12.5,30.25。
POINT_PATTERN = re.compile(
    r"(?P<x>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r"(?P<comma>\s*,\s*)"
    r"(?P<y>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
)

# 需要做水平平移的位置属性。
HORIZONTAL_POSITION_ATTRS = ("x", "x1", "x2", "cx", "mergex")

# 需要做垂直平移的位置属性。
VERTICAL_POSITION_ATTRS = ("y", "y1", "y2", "cy", "mergey")

# 明确包含图元 ID 引用的属性。
REFERENCE_LIST_ATTRS = ("link", "node_area")
REFERENCE_SINGLE_ATTRS = ("p_FatherObjId",)


@dataclass(frozen=True)
class GFileInfo:
    path: Path
    prefix: str
    station: str
    feeder: int


@dataclass
class NegativeCoordinateCleanupResult:
    # 因自身坐标含负数而直接删除的根图元数量。
    removed_root_elements: int = 0
    # 连同被删除根图元的后代，一共移除的 XML 图元数量。
    removed_total_elements: int = 0
    # 被移除的非空图元 ID 数量。
    removed_element_ids: int = 0
    # 从 link/node_area 中删除的失效引用分组数量。
    removed_reference_groups: int = 0
    # 被清空的 p_FatherObjId 数量。
    cleared_single_references: int = 0


@dataclass
class ParsedGFile:
    info: GFileInfo
    tree: ET.ElementTree
    root: ET.Element
    layer: ET.Element
    root_height: Decimal
    root_width: Decimal
    alignment_bus_y: Decimal
    min_x: Decimal
    min_y: Decimal
    max_x: Decimal
    max_y: Decimal
    negative_cleanup: NegativeCoordinateCleanupResult
    rounded_coordinate_attributes: int


@dataclass
class IdUpdateResult:
    # 真正写在元素 id="..." 上且被修改的数量。
    changed_element_ids: int = 0
    # link/node_area/p_FatherObjId 中发生映射的不同 ID token 数量。
    changed_reference_tokens: int = 0
    # 单个源文件 Layer 自身重复的元素 ID 数量。
    source_internal_duplicates: int = 0
    # 源文件中只出现在引用里、没有同名 XML 图元的拓扑节点 ID 数量。
    virtual_reference_tokens: int = 0


def local_name(tag: object) -> str:
    """去掉 XML 命名空间，只保留标签名。"""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def parse_decimal(value: str, context: str) -> Decimal:
    """将 XML 数字安全转换为 Decimal。"""
    try:
        return Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"{context} 不是有效数字：{value!r}") from exc


def try_decimal(value: str | None) -> Decimal | None:
    """尝试转换数字，失败时返回 None。"""
    if value is None:
        return None
    try:
        return Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        return None


def format_decimal(value: Decimal) -> str:
    """避免输出科学计数法和无意义的 .0。"""
    if value == value.to_integral_value():
        return str(value.to_integral_value())

    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def round_to_integer(value: Decimal) -> Decimal:
    """
    使用统一规则取整：四舍五入，遇到 .5 时向远离 0 的方向取整。

    示例：
        10.4  -> 10
        10.5  -> 11
        -10.4 -> -10
        -10.5 -> -11
    """
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def format_integer(value: Decimal) -> str:
    """按统一规则取整并输出不带小数点的字符串。"""
    return str(round_to_integer(value))


def parse_filename(path: Path) -> GFileInfo:
    """
    例如：JED-CTL-ADF-15.sln.pic.g
      prefix  = JED-CTL-ADF
      station = ADF
      feeder  = 15
    """
    parts = path.name.split("-")
    if len(parts) < 4:
        raise ValueError(
            f"文件名格式不符合要求：{path.name}\n"
            "要求至少类似：JED-CTL-ADF-15.sln.pic.g"
        )

    station = parts[2].strip()
    feeder_match = re.match(r"\s*(\d+)", parts[3])
    if feeder_match is None:
        raise ValueError(
            f"无法从文件名第四段提取馈线号：{path.name}\n"
            f"第四段是：{parts[3]!r}"
        )

    return GFileInfo(
        path=path,
        prefix="-".join(parts[:3]),
        station=station,
        feeder=int(feeder_match.group(1)),
    )


def discover_files(input_dir: Path, pattern: str) -> list[GFileInfo]:
    """发现输入文件、检查站点及重复馈线，并按馈线号排序。"""
    candidates = [
        path
        for path in input_dir.glob(pattern)
        if path.is_file()
        and path.suffix.lower() == ".g"
        and "-merged-" not in path.name.lower()
    ]

    if not candidates:
        raise FileNotFoundError(
            f"目录中未找到匹配的 .g 文件：{input_dir}\n匹配模式：{pattern}"
        )

    infos = [parse_filename(path) for path in candidates]

    prefixes = {info.prefix for info in infos}
    if len(prefixes) != 1:
        details = "\n".join(f"  - {info.path.name}" for info in infos)
        raise ValueError(
            "一次只能合并同一个站点前缀的文件，当前检测到多个前缀：\n"
            f"{details}"
        )

    feeder_files: dict[int, list[Path]] = {}
    for info in infos:
        feeder_files.setdefault(info.feeder, []).append(info.path)

    duplicates = {
        feeder: paths
        for feeder, paths in feeder_files.items()
        if len(paths) > 1
    }
    if duplicates:
        lines = ["检测到同一馈线存在多个文件，请每个馈线只保留一个："]
        for feeder, paths in sorted(duplicates.items()):
            lines.append(f"馈线 {feeder}：")
            lines.extend(f"  - {path.name}" for path in paths)
        raise ValueError("\n".join(lines))

    return sorted(infos, key=lambda item: item.feeder)


def create_xml_parser() -> ET.XMLParser:
    """保留 XML 注释。"""
    return ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))


def parse_xml(path: Path) -> ET.ElementTree:
    try:
        return ET.parse(path, parser=create_xml_parser())
    except ET.ParseError as exc:
        raise ValueError(f"XML 解析失败：{path}\n{exc}") from exc


def get_only_layer(root: ET.Element, filename: str) -> ET.Element:
    """每个文件必须且只能有一个直属 Layer。"""
    layers = [child for child in list(root) if local_name(child.tag) == "Layer"]
    if len(layers) != 1:
        raise ValueError(
            f"文件 {filename} 应当只有一个直属 Layer，实际找到 {len(layers)} 个"
        )
    return layers[0]


def get_root_dimension(
    root: ET.Element,
    short_name: str,
    long_name: str,
    filename: str,
) -> Decimal:
    """
    h/height 或 w/width 表示同一尺寸。
    若二者同时存在但不同，取较大值，避免缩小画布。
    """
    values: list[Decimal] = []
    for name in (short_name, long_name):
        raw = root.get(name)
        if raw is not None:
            values.append(parse_decimal(raw, f"文件 {filename} 的 G.{name}"))

    if not values:
        raise ValueError(
            f"文件 {filename} 的 G 根节点缺少 {short_name}/{long_name} 属性"
        )
    return max(values)


def iter_graph_elements(children_or_layer: Iterable[ET.Element] | ET.Element) -> Iterator[ET.Element]:
    """遍历 Layer 下的全部图元及其后代，不返回 Layer 本身。"""
    if isinstance(children_or_layer, ET.Element):
        roots = list(children_or_layer)
    else:
        roots = list(children_or_layer)

    for root in roots:
        yield root
        yield from root.iterfind(".//*")


def parse_d_points(d_value: str) -> list[tuple[Decimal, Decimal]]:
    """读取 d 属性中所有 x,y 点。"""
    points: list[tuple[Decimal, Decimal]] = []
    for match in POINT_PATTERN.finditer(d_value):
        points.append(
            (
                parse_decimal(match.group("x"), "d 属性中的 x"),
                parse_decimal(match.group("y"), "d 属性中的 y"),
            )
        )
    return points

def element_has_negative_coordinate(element: ET.Element, filename: str) -> bool:
    """
    判断一个图元自身是否包含负数坐标。

    只检查明确表示“位置”的属性和 d 路径坐标，不检查：
      w/h、width/height、rx/ry、rotate、tfr、颜色和状态值。
    因此 tfr="rotate(-0.0)" 不会被误判。
    """
    tag = local_name(element.tag)
    for attr in (*HORIZONTAL_POSITION_ATTRS, *VERTICAL_POSITION_ATTRS):
        raw = element.get(attr)
        if raw is None:
            continue
        value = try_decimal(raw)
        if value is None:
            raise ValueError(
                f"文件 {filename} 中 <{tag}> 的 {attr} 不是有效数字：{raw!r}"
            )
        if value < 0:
            return True

    d_value = element.get("d")
    if d_value:
        for point_x, point_y in parse_d_points(d_value):
            if point_x < 0 or point_y < 0:
                return True

    return False


def collect_subtree_nonempty_ids(element: ET.Element) -> set[str]:
    """收集某个待删除元素及其全部后代的非空 id。"""
    result: set[str] = set()
    for current in element.iter():
        value = current.get("id")
        if value is not None and value.strip():
            result.add(value.strip())
    return result


def count_subtree_graph_elements(element: ET.Element) -> int:
    """统计某个元素子树中的真实 XML 元素数量，不计注释。"""
    return sum(1 for current in element.iter() if local_name(current.tag))


def remove_reference_groups_to_ids(value: str, removed_ids: set[str]) -> tuple[str, int]:
    """从 link/node_area 中删除目标 ID 已被移除的分组。"""
    if not value or not removed_ids:
        return value, 0

    kept_groups: list[str] = []
    removed_count = 0
    for group in value.split(";"):
        parts = group.split(",", 2)
        if len(parts) >= 3 and parts[2].strip() in removed_ids:
            removed_count += 1
            continue
        kept_groups.append(group)

    return ";".join(kept_groups), removed_count


def remove_negative_coordinate_elements(
    layer: ET.Element,
    filename: str,
) -> NegativeCoordinateCleanupResult:
    """
    删除坐标含负数的图元，并清理其他保留图元中对它们的引用。

    本函数必须在任何平移之前执行，确保源文件原本存在的负坐标不会被后续
    X/Y 偏移掩盖。只检查明确的位置坐标和 d 路径，不检查尺寸、旋转、颜色等。
    """
    result = NegativeCoordinateCleanupResult()
    removed_ids: set[str] = set()

    def recurse(parent: ET.Element) -> None:
        for child in list(parent):
            if not local_name(child.tag):
                continue

            if element_has_negative_coordinate(child, filename):
                result.removed_root_elements += 1
                result.removed_total_elements += count_subtree_graph_elements(child)
                removed_ids.update(collect_subtree_nonempty_ids(child))
                parent.remove(child)
                continue

            recurse(child)

    recurse(layer)

    # 若同一个 ID 在保留元素中仍然存在（源文件本身重复 ID），不能清理该 ID 的引用。
    remaining_ids = set(collect_ids(layer))
    truly_removed_ids = removed_ids - remaining_ids
    result.removed_element_ids = len(truly_removed_ids)

    if truly_removed_ids:
        for element in iter_graph_elements(layer):
            for attr in REFERENCE_LIST_ATTRS:
                value = element.get(attr)
                if value is None:
                    continue
                new_value, removed_count = remove_reference_groups_to_ids(
                    value,
                    truly_removed_ids,
                )
                if removed_count:
                    element.set(attr, new_value)
                    result.removed_reference_groups += removed_count

            for attr in REFERENCE_SINGLE_ATTRS:
                value = element.get(attr)
                if value and value.strip() in truly_removed_ids:
                    element.set(attr, "")
                    result.cleared_single_references += 1

    return result


def get_bus_line(element: ET.Element) -> tuple[Decimal, Decimal, Decimal, Decimal] | None:
    """提取 Bus 的 x1,y1,x2,y2；缺失时尝试读取 d 的前两个点。"""
    x1 = try_decimal(element.get("x1"))
    y1 = try_decimal(element.get("y1"))
    x2 = try_decimal(element.get("x2"))
    y2 = try_decimal(element.get("y2"))

    if None not in (x1, y1, x2, y2):
        return x1, y1, x2, y2  # type: ignore[return-value]

    d_value = element.get("d")
    if d_value:
        points = parse_d_points(d_value)
        if len(points) >= 2:
            return points[0][0], points[0][1], points[1][0], points[1][1]

    return None


def find_top_horizontal_bus_y(layer: ET.Element, filename: str) -> Decimal:
    """
    查找最上面的有效水平 Bus。

    像 d="759,129 759,129" 这种长度为 0 的 Bus 点不作为对齐母线。
    """
    candidates: list[tuple[Decimal, Decimal, str]] = []

    for element in iter_graph_elements(layer):
        if local_name(element.tag) != "Bus":
            continue

        line = get_bus_line(element)
        if line is None:
            continue

        x1, y1, x2, y2 = line
        horizontal_span = abs(x2 - x1)
        vertical_delta = abs(y2 - y1)

        if horizontal_span > 0 and vertical_delta <= Decimal("0.000001"):
            candidates.append((min(y1, y2), horizontal_span, element.get("id", "")))

    if not candidates:
        raise ValueError(
            f"文件 {filename} 中没有找到可用于对齐的非零长度水平 <Bus>"
        )

    # 第一优先：Y 最小，即最上面的母线；同一高度时优先最长母线。
    candidates.sort(key=lambda item: (item[0], -item[1]))
    return candidates[0][0]


def get_graph_extents(
    children_or_layer: Iterable[ET.Element] | ET.Element,
    filename: str,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """
    计算图形内容的最小/最大 X、Y 边界。

    综合考虑：
      x/y、x1/y1、x2/y2、cx/cy、mergex/mergey、d
      x+w、y+h、cx±rx、cy±ry、mergex+w、mergey+h
    """
    x_values: list[Decimal] = []
    y_values: list[Decimal] = []

    for element in iter_graph_elements(children_or_layer):
        tag = local_name(element.tag)

        numeric: dict[str, Decimal] = {}
        for attr in (
            "x", "y", "x1", "y1", "x2", "y2", "cx", "cy",
            "mergex", "mergey", "w", "h", "rx", "ry",
        ):
            raw = element.get(attr)
            if raw is None:
                continue
            value = try_decimal(raw)
            if value is None:
                raise ValueError(
                    f"文件 {filename} 中 <{tag}> 的 {attr} 不是有效数字：{raw!r}"
                )
            numeric[attr] = value

        for attr in ("x", "x1", "x2", "cx", "mergex"):
            if attr in numeric:
                x_values.append(numeric[attr])

        for attr in ("y", "y1", "y2", "cy", "mergey"):
            if attr in numeric:
                y_values.append(numeric[attr])

        if "x" in numeric and "w" in numeric:
            x_values.append(numeric["x"] + numeric["w"])
        if "y" in numeric and "h" in numeric:
            y_values.append(numeric["y"] + numeric["h"])
        if "cx" in numeric and "rx" in numeric:
            x_values.extend((numeric["cx"] - numeric["rx"], numeric["cx"] + numeric["rx"]))
        if "cy" in numeric and "ry" in numeric:
            y_values.extend((numeric["cy"] - numeric["ry"], numeric["cy"] + numeric["ry"]))
        if "mergex" in numeric and "w" in numeric:
            x_values.append(numeric["mergex"] + numeric["w"])
        if "mergey" in numeric and "h" in numeric:
            y_values.append(numeric["mergey"] + numeric["h"])

        d_value = element.get("d")
        if d_value:
            for point_x, point_y in parse_d_points(d_value):
                x_values.append(point_x)
                y_values.append(point_y)

    if not x_values:
        raise ValueError(f"文件 {filename} 的 Layer 中没有找到可计算的 X 坐标")
    if not y_values:
        raise ValueError(f"文件 {filename} 的 Layer 中没有找到可计算的 Y 坐标")

    return min(x_values), min(y_values), max(x_values), max(y_values)


def get_position_coordinate_extents(
    children_or_layer: Iterable[ET.Element] | ET.Element,
    filename: str,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """
    只根据“位置坐标值”计算最小/最大 X、Y。

    用于：
      - 相邻馈线严格间隔；
      - 最终上、左、右、下边距；
      - G.w/width 和 G.h/height。

    这里不把 w/h、rx/ry 当作坐标，因为用户规则明确以最小/最大 x、y
    坐标值为基准。
    """
    x_values: list[Decimal] = []
    y_values: list[Decimal] = []

    for element in iter_graph_elements(children_or_layer):
        tag = local_name(element.tag)

        for attr in HORIZONTAL_POSITION_ATTRS:
            raw = element.get(attr)
            if raw is None:
                continue
            value = try_decimal(raw)
            if value is None:
                raise ValueError(
                    f"文件 {filename} 中 <{tag}> 的 {attr} 不是有效数字：{raw!r}"
                )
            x_values.append(value)

        for attr in VERTICAL_POSITION_ATTRS:
            raw = element.get(attr)
            if raw is None:
                continue
            value = try_decimal(raw)
            if value is None:
                raise ValueError(
                    f"文件 {filename} 中 <{tag}> 的 {attr} 不是有效数字：{raw!r}"
                )
            y_values.append(value)

        d_value = element.get("d")
        if d_value:
            for point_x, point_y in parse_d_points(d_value):
                x_values.append(point_x)
                y_values.append(point_y)

    if not x_values:
        raise ValueError(f"文件 {filename} 的 Layer 中没有找到可计算的 X 坐标")
    if not y_values:
        raise ValueError(f"文件 {filename} 的 Layer 中没有找到可计算的 Y 坐标")

    return min(x_values), min(y_values), max(x_values), max(y_values)


def get_graph_bounds(
    children_or_layer: Iterable[ET.Element] | ET.Element,
    filename: str,
) -> tuple[Decimal, Decimal]:
    """兼容原有调用：仅返回最大 X 和最大 Y。"""
    _min_x, _min_y, max_x, max_y = get_graph_extents(
        children_or_layer,
        filename,
    )
    return max_x, max_y


def ceiling_to_integer(value: Decimal) -> Decimal:
    """向正无穷方向取整，用于保证边距不会小于配置值。"""
    return value.to_integral_value(rounding=ROUND_CEILING)

def shift_d_value(d_value: str, offset_x: Decimal, offset_y: Decimal) -> str:
    """将 d 属性中的每个坐标点同时做 X/Y 平移。"""
    def replace_point(match: re.Match[str]) -> str:
        old_x = parse_decimal(match.group("x"), "d 属性中的 x")
        old_y = parse_decimal(match.group("y"), "d 属性中的 y")
        return (
            f"{format_decimal(old_x + offset_x)}"
            f"{match.group('comma')}"
            f"{format_decimal(old_y + offset_y)}"
        )

    return POINT_PATTERN.sub(replace_point, d_value)


def shift_graph_elements(
    children: Iterable[ET.Element],
    offset_x: Decimal,
    offset_y: Decimal,
) -> None:
    """平移复制出来的全部图元。"""
    for element in iter_graph_elements(children):
        tag = local_name(element.tag)

        for attr in HORIZONTAL_POSITION_ATTRS:
            if attr not in element.attrib:
                continue
            old_value = parse_decimal(
                element.attrib[attr], f"<{tag}> 的 {attr} 属性"
            )
            element.set(attr, format_decimal(old_value + offset_x))

        for attr in VERTICAL_POSITION_ATTRS:
            if attr not in element.attrib:
                continue
            old_value = parse_decimal(
                element.attrib[attr], f"<{tag}> 的 {attr} 属性"
            )
            element.set(attr, format_decimal(old_value + offset_y))

        if "d" in element.attrib:
            element.set(
                "d",
                shift_d_value(element.attrib["d"], offset_x, offset_y),
            )


def normalize_position_coordinates_to_integers(
    children_or_layer: Iterable[ET.Element] | ET.Element,
) -> int:
    """
    将最终 Layer 中的全部位置坐标统一取整。

    为保证同一图元的包围框、端点和实际路径一致，必须同时处理：
      x/y、x1/y1、x2/y2、cx/cy、mergex/mergey，以及 d 中全部点。

    返回实际发生变化的属性数量，便于日志检查。
    """
    changed_count = 0
    position_attrs = (*HORIZONTAL_POSITION_ATTRS, *VERTICAL_POSITION_ATTRS)

    for element in iter_graph_elements(children_or_layer):
        tag = local_name(element.tag)

        for attr in position_attrs:
            raw_value = element.get(attr)
            if raw_value is None:
                continue

            old_value = parse_decimal(raw_value, f"<{tag}> 的 {attr} 属性")
            new_value = format_integer(old_value)
            if new_value != raw_value.strip():
                changed_count += 1
            element.set(attr, new_value)

        d_value = element.get("d")
        if d_value is not None:
            def replace_point(match: re.Match[str]) -> str:
                old_x = parse_decimal(match.group("x"), "d 属性中的 x")
                old_y = parse_decimal(match.group("y"), "d 属性中的 y")
                return (
                    f"{format_integer(old_x)}"
                    f"{match.group('comma')}"
                    f"{format_integer(old_y)}"
                )

            new_d = POINT_PATTERN.sub(replace_point, d_value)
            if new_d != d_value:
                changed_count += 1
            element.set("d", new_d)

    return changed_count


def collect_ids(children_or_layer: Iterable[ET.Element] | ET.Element) -> list[str]:
    """按 XML 顺序收集 Layer 中所有非空的图元 id。"""
    result: list[str] = []
    for element in iter_graph_elements(children_or_layer):
        value = element.get("id")
        if value is not None and value.strip():
            result.append(value.strip())
    return result


def unique_in_order(values: Iterable[str]) -> list[str]:
    """保持首次出现顺序去重。"""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def extract_reference_ids(value: str) -> list[str]:
    """从 link/node_area 中提取每个分组的第三项 ID。"""
    refs: list[str] = []
    for group in value.split(";"):
        parts = group.split(",", 2)
        if len(parts) >= 3 and parts[2].strip():
            refs.append(parts[2].strip())
    return refs


def collect_reference_ids(
    children_or_layer: Iterable[ET.Element] | ET.Element,
) -> list[str]:
    """按 XML 顺序收集已知引用属性中的所有非空 ID。"""
    result: list[str] = []
    for element in iter_graph_elements(children_or_layer):
        for attr in REFERENCE_LIST_ATTRS:
            value = element.get(attr)
            if value:
                result.extend(extract_reference_ids(value))

        for attr in REFERENCE_SINGLE_ATTRS:
            value = element.get(attr)
            if value and value.strip():
                result.append(value.strip())
    return result


def collect_identifier_tokens(
    children_or_layer: Iterable[ET.Element] | ET.Element,
) -> list[str]:
    """
    收集一个 Layer 的完整 ID 命名空间。

    不仅包含元素自身 id，也包含 link/node_area 等引用中的 ID。
    后者可能是没有对应 XML 元素的“虚拟拓扑节点 ID”。
    """
    return unique_in_order(
        [
            *collect_ids(children_or_layer),
            *collect_reference_ids(children_or_layer),
        ]
    )


def generate_unique_id(old_id: str, blocked_ids: set[str]) -> str:
    """
    生成唯一 ID。

    数字 ID 优先在原 ID 后递增，可尽量保留原有类型前缀和长度；
    非数字 ID 使用 _1、_2……后缀。
    """
    if old_id.isdigit():
        width = len(old_id)
        candidate_number = int(old_id) + 1
        while True:
            candidate = str(candidate_number).zfill(width)
            if candidate not in blocked_ids:
                return candidate
            candidate_number += 1

    counter = 1
    while True:
        candidate = f"{old_id}_{counter}"
        if candidate not in blocked_ids:
            return candidate
        counter += 1


def update_list_reference(value: str, id_map: dict[str, str]) -> str:
    """
    更新 link/node_area。

    格式通常为：0,0,30000126;1,0,100000129
    只替换每个分组中的第三项 ID，不修改前两项端点信息。
    """
    groups = value.split(";")
    updated_groups: list[str] = []

    for group in groups:
        parts = group.split(",", 2)
        if len(parts) < 3:
            updated_groups.append(group)
            continue

        original_ref = parts[2]
        stripped_ref = original_ref.strip()
        new_ref = id_map.get(stripped_ref)
        if new_ref is None:
            updated_groups.append(group)
            continue

        leading = original_ref[: len(original_ref) - len(original_ref.lstrip())]
        trailing = original_ref[len(original_ref.rstrip()) :]
        parts[2] = f"{leading}{new_ref}{trailing}"
        updated_groups.append(",".join(parts))

    return ";".join(updated_groups)


def update_single_reference(value: str, id_map: dict[str, str]) -> str:
    """更新 p_FatherObjId 这类单一 ID 引用。"""
    stripped = value.strip()
    if not stripped or stripped not in id_map:
        return value

    leading = value[: len(value) - len(value.lstrip())]
    trailing = value[len(value.rstrip()) :]
    return f"{leading}{id_map[stripped]}{trailing}"


def update_reference_attributes(
    children: Iterable[ET.Element],
    id_map: dict[str, str],
) -> None:
    """根据旧 ID → 新 ID 映射更新所有已知引用属性。"""
    if not id_map:
        return

    for element in iter_graph_elements(children):
        for attr in REFERENCE_LIST_ATTRS:
            value = element.get(attr)
            if value:
                element.set(attr, update_list_reference(value, id_map))

        for attr in REFERENCE_SINGLE_ATTRS:
            value = element.get(attr)
            if value:
                element.set(attr, update_single_reference(value, id_map))


def remap_source_identifier_namespace(
    children: Iterable[ET.Element],
    used_tokens: set[str],
    blocked_tokens: set[str],
) -> tuple[IdUpdateResult, set[str]]:
    """
    将一个后续馈线的完整 ID 命名空间安全并入最终文件。

    这里必须同时考虑两类 ID：
    1. 元素自身的 id；
    2. link/node_area/p_FatherObjId 中引用的 ID。

    第二类中可能有“虚拟拓扑节点 ID”，它们在源文件中没有同名 XML
    图元，但仍然承担多个对象之间的拓扑关联。若它们与其他馈线的元素 ID
    或虚拟 ID 重复，也必须整体重新映射，否则合并后可能错误串联。

    返回：
      - 修改统计；
      - 原本确实指向源文件内部 XML 图元的目标 ID（映射后），用于最终校验。
    """
    result = IdUpdateResult()
    elements = list(iter_graph_elements(children))

    element_ids = [
        element.get("id", "").strip()
        for element in elements
        if element.get("id") and element.get("id", "").strip()
    ]
    element_id_set = set(element_ids)
    reference_ids = collect_reference_ids(children)
    reference_id_set = set(reference_ids)

    result.virtual_reference_tokens = len(reference_id_set - element_id_set)

    # 同一个 token 无论出现在元素 id 还是引用中，都使用同一份映射。
    source_tokens = unique_in_order([*element_ids, *reference_ids])
    token_map: dict[str, str] = {}

    for old_token in source_tokens:
        if old_token in used_tokens:
            new_token = generate_unique_id(
                old_token,
                blocked_tokens | used_tokens,
            )
        else:
            new_token = old_token

        token_map[old_token] = new_token
        used_tokens.add(new_token)
        blocked_tokens.add(new_token)

    result.changed_reference_tokens = sum(
        1
        for token in reference_id_set
        if token_map.get(token, token) != token
    )

    # 修改元素自身 ID。若源 Layer 自身已有重复元素 ID，第一处使用统一映射，
    # 后续重复元素单独生成新 ID；原始引用仍指向第一处，避免凭空猜测。
    source_seen: set[str] = set()
    for element in elements:
        old_id_raw = element.get("id")
        if old_id_raw is None or not old_id_raw.strip():
            continue

        old_id = old_id_raw.strip()
        if old_id in source_seen:
            result.source_internal_duplicates += 1
            new_id = generate_unique_id(
                old_id,
                blocked_tokens | used_tokens,
            )
            element.set("id", new_id)
            used_tokens.add(new_id)
            blocked_tokens.add(new_id)
            result.changed_element_ids += 1
            continue

        source_seen.add(old_id)
        new_id = token_map[old_id]
        if new_id != old_id:
            element.set("id", new_id)
            result.changed_element_ids += 1

    # 对全部 token 应用同一映射，包括没有对应 XML 图元的虚拟拓扑节点 ID。
    update_reference_attributes(children, token_map)

    # 只有源文件中本来就存在同名 XML 图元的引用，才要求最终能找到目标。
    required_target_ids = {
        token_map[ref_id]
        for ref_id in reference_id_set
        if ref_id in element_id_set
    }
    return result, required_target_ids


def normalize_base_layer_duplicate_ids(
    layer: ET.Element,
    blocked_ids: set[str],
) -> IdUpdateResult:
    """
    基准图原则上完全不修改。
    仅当基准 Layer 自身已存在重复 ID 时，为后续重复项生成唯一 ID。
    """
    result = IdUpdateResult()
    seen: set[str] = set()

    for element in iter_graph_elements(layer):
        old_id_raw = element.get("id")
        if old_id_raw is None or not old_id_raw.strip():
            continue
        old_id = old_id_raw.strip()

        if old_id not in seen:
            seen.add(old_id)
            continue

        result.source_internal_duplicates += 1
        new_id = generate_unique_id(old_id, blocked_ids | seen)
        element.set("id", new_id)
        blocked_ids.add(new_id)
        seen.add(new_id)
        result.changed_element_ids += 1

    # 基准图内部重复 ID 的引用在原始文件中存在歧义，维持指向第一处 ID。
    return result


def validate_final_layer(
    layer: ET.Element,
    required_target_ids: set[str],
) -> tuple[int, int, int, int]:
    """
    校验最终 Layer。

    硬性要求：
    - 所有 XML 图元 id 唯一；
    - 原来确实指向源文件内部 XML 图元的引用，映射后仍能找到目标。

    link/node_area 中只存在于引用、没有同名 XML 元素的 ID 被视为
    “虚拟拓扑节点 ID”。这种结构在原始 .g 文件中本来就大量存在，
    因此允许保留，不再误判为错误。
    """
    ids = collect_ids(layer)
    counter = Counter(ids)
    duplicates = sorted(
        id_value for id_value, count in counter.items() if count > 1
    )
    if duplicates:
        preview = ", ".join(duplicates[:20])
        raise ValueError(f"最终 Layer 仍存在重复图元 ID：{preview}")

    id_set = set(ids)
    missing_required = sorted(required_target_ids - id_set)
    if missing_required:
        preview = ", ".join(missing_required[:30])
        raise ValueError(
            "合并后有原本指向真实图元的引用失效，目标 ID："
            f"{preview}"
        )

    reference_ids = collect_reference_ids(layer)
    virtual_reference_occurrences = [
        ref_id for ref_id in reference_ids if ref_id not in id_set
    ]
    virtual_reference_unique = set(virtual_reference_occurrences)

    return (
        len(ids),
        len(id_set),
        len(virtual_reference_unique),
        len(virtual_reference_occurrences),
    )


def parse_g_file(info: GFileInfo) -> ParsedGFile:
    """
    解析单个 .g 文件，并在任何平移之前完成两项预处理：
      1. 删除原始负坐标图元并清理引用；
      2. 将所有位置坐标统一取整。
    """
    tree = parse_xml(info.path)
    root = tree.getroot()

    if local_name(root.tag) != "G":
        raise ValueError(
            f"文件 {info.path.name} 的根节点不是 G，而是 {root.tag!r}"
        )

    layer = get_only_layer(root, info.path.name)
    root_height = get_root_dimension(root, "h", "height", info.path.name)
    root_width = get_root_dimension(root, "w", "width", info.path.name)

    # 必须先删除原始负坐标，再做任何移动或取整。
    negative_cleanup = remove_negative_coordinate_elements(
        layer,
        f"{info.path.name}（原始坐标清理）",
    )

    # 清理完成后统一取整，后续母线对齐、馈线间隔和画布边距都使用整数。
    rounded_coordinate_attributes = normalize_position_coordinates_to_integers(
        layer
    )

    alignment_bus_y = find_top_horizontal_bus_y(layer, info.path.name)
    min_x, min_y, max_x, max_y = get_position_coordinate_extents(
        layer,
        info.path.name,
    )

    return ParsedGFile(
        info=info,
        tree=tree,
        root=root,
        layer=layer,
        root_height=root_height,
        root_width=root_width,
        alignment_bus_y=alignment_bus_y,
        min_x=min_x,
        min_y=min_y,
        max_x=max_x,
        max_y=max_y,
        negative_cleanup=negative_cleanup,
        rounded_coordinate_attributes=rounded_coordinate_attributes,
    )

def merge_g_files(
    infos: list[GFileInfo],
    output_path: Path,
    gap: Decimal,
    left_margin: Decimal,
    top_margin: Decimal,
    right_margin: Decimal,
    bottom_margin: Decimal,
) -> None:
    parsed_files = [parse_g_file(info) for info in infos]

    # 第一个（最小馈线）文件完整作为输出基础。它在合并阶段不单独移动；
    # 最后会与整个合并图一起做统一的上/左边距平移。
    base = parsed_files[0]
    output_tree = base.tree
    output_root = base.root
    target_layer = base.layer
    base_bus_y = base.alignment_bus_y

    # 预留所有清理后输入文件的完整 ID token（元素 ID + 引用/虚拟节点 ID）。
    blocked_tokens: set[str] = set()
    for item in parsed_files:
        blocked_tokens.update(collect_identifier_tokens(item.layer))

    base_fix = normalize_base_layer_duplicate_ids(target_layer, blocked_tokens)
    base_element_ids = set(collect_ids(target_layer))
    base_reference_ids = set(collect_reference_ids(target_layer))
    used_tokens = base_element_ids | base_reference_ids

    # 只校验原本确实指向 XML 图元的引用；虚拟拓扑节点无需同名元素。
    required_target_ids: set[str] = base_element_ids & base_reference_ids

    base_min_x, base_min_y, current_max_x, current_max_y = (
        get_position_coordinate_extents(target_layer, base.info.path.name)
    )

    # 保存各馈线合并后的坐标范围，用于最终验证相邻间隔。
    feeder_ranges: list[tuple[int, Decimal, Decimal]] = [
        (base.info.feeder, base_min_x, current_max_x)
    ]

    print("处理顺序：")
    for item in parsed_files:
        print(f"  馈线 {item.info.feeder}: {item.info.path.name}")

    print("\n源文件预处理：")
    for item in parsed_files:
        cleanup = item.negative_cleanup
        print(
            f"  馈线 {item.info.feeder}: "
            f"删除负坐标根图元 {cleanup.removed_root_elements} 个，"
            f"累计删除元素 {cleanup.removed_total_elements} 个，"
            f"清理引用分组 {cleanup.removed_reference_groups} 个，"
            f"取整坐标属性 {item.rounded_coordinate_attributes} 个"
        )

    print("\n基准图：")
    print(f"  文件：{base.info.path.name}")
    print(f"  基准水平 Bus Y：{format_integer(base_bus_y)}")
    print(f"  合并阶段 X 偏移：0")
    print(f"  合并阶段 Y 偏移：0")
    print(
        "  原始清理后坐标范围："
        f"minX={format_integer(base_min_x)}，"
        f"minY={format_integer(base_min_y)}，"
        f"maxX={format_integer(current_max_x)}，"
        f"maxY={format_integer(current_max_y)}"
    )
    if base_fix.changed_element_ids:
        print(
            f"  基准 Layer 原本存在 {base_fix.source_internal_duplicates} 个重复 ID，"
            f"已修改 {base_fix.changed_element_ids} 个"
        )

    total_changed_element_ids = base_fix.changed_element_ids
    total_changed_reference_tokens = 0

    for source in parsed_files[1:]:
        # 后续文件只复制唯一 Layer 下的直接子元素。
        copied_children = [copy.deepcopy(child) for child in list(source.layer)]

        id_result, source_required_targets = remap_source_identifier_namespace(
            copied_children,
            used_tokens=used_tokens,
            blocked_tokens=blocked_tokens,
        )
        required_target_ids.update(source_required_targets)
        total_changed_element_ids += id_result.changed_element_ids
        total_changed_reference_tokens += id_result.changed_reference_tokens

        source_min_x, source_min_y, source_max_x, source_max_y = (
            get_position_coordinate_extents(copied_children, source.info.path.name)
        )

        # 所有母线对齐到第一张图的母线；第一张图本身在合并阶段不移动。
        offset_y = base_bus_y - source.alignment_bus_y

        # 使用当前图的最小 X，严格保证相邻馈线坐标范围间隔为 gap。
        offset_x = current_max_x + gap - source_min_x

        # 输入坐标、gap、母线 Y 都已整数化，因此偏移也是整数。
        shift_graph_elements(copied_children, offset_x, offset_y)

        shifted_min_x, shifted_min_y, shifted_max_x, shifted_max_y = (
            get_position_coordinate_extents(copied_children, source.info.path.name)
        )

        actual_gap = shifted_min_x - current_max_x
        if actual_gap != gap:
            raise ValueError(
                f"馈线 {source.info.feeder} 间隔计算失败："
                f"目标 {format_integer(gap)}，实际 {format_decimal(actual_gap)}"
            )

        for child in copied_children:
            target_layer.append(child)

        feeder_ranges.append(
            (source.info.feeder, shifted_min_x, shifted_max_x)
        )
        current_max_x = max(current_max_x, shifted_max_x)
        current_max_y = max(current_max_y, shifted_max_y)

        print(f"\n馈线 {source.info.feeder}：")
        print(f"  文件：{source.info.path.name}")
        print(f"  原水平 Bus Y：{format_integer(source.alignment_bus_y)}")
        print(f"  对齐目标 Bus Y：{format_integer(base_bus_y)}")
        print(f"  X 偏移：{format_integer(offset_x)}")
        print(f"  Y 偏移：{format_integer(offset_y)}")
        print(f"  与前面图形实际间隔：{format_integer(actual_gap)}")
        print(
            "  移动后坐标范围："
            f"minX={format_integer(shifted_min_x)}，"
            f"minY={format_integer(shifted_min_y)}，"
            f"maxX={format_integer(shifted_max_x)}，"
            f"maxY={format_integer(shifted_max_y)}"
        )
        print(
            "  发生冲突并修改的图元 ID 数量："
            f"{id_result.changed_element_ids}"
        )
        print(
            "  发生冲突并重新映射的引用 ID token 数量："
            f"{id_result.changed_reference_tokens}"
        )
        print(
            "  源文件虚拟拓扑节点 ID 数量："
            f"{id_result.virtual_reference_tokens}（允许无同名 XML 图元）"
        )

    # 完成全部母线对齐和馈线排列后，才根据整个合并图的最小 X/Y
    # 统一处理上边距和左边距。整体平移不会改变母线相对位置和馈线间隔。
    before_min_x, before_min_y, before_max_x, before_max_y = (
        get_position_coordinate_extents(target_layer, output_path.name)
    )
    canvas_shift_x = left_margin - before_min_x
    canvas_shift_y = top_margin - before_min_y

    shift_graph_elements(
        list(target_layer),
        canvas_shift_x,
        canvas_shift_y,
    )

    final_min_x, final_min_y, final_max_x, final_max_y = (
        get_position_coordinate_extents(target_layer, output_path.name)
    )

    if final_min_x != left_margin or final_min_y != top_margin:
        raise ValueError(
            "最终上/左边距校验失败："
            f"minX={format_decimal(final_min_x)}，"
            f"目标左边距={format_integer(left_margin)}；"
            f"minY={format_decimal(final_min_y)}，"
            f"目标上边距={format_integer(top_margin)}"
        )

    # 所有母线都增加同一个最终 Y 偏移，因此仍然保持对齐。
    expected_final_bus_y = base_bus_y + canvas_shift_y
    final_bus_y = find_top_horizontal_bus_y(target_layer, output_path.name)
    if final_bus_y != expected_final_bus_y:
        raise ValueError(
            f"最终母线对齐校验失败：期望 Y={format_decimal(expected_final_bus_y)}，"
            f"实际 Y={format_decimal(final_bus_y)}"
        )

    # 最后处理右边框和下边框。
    final_width = final_max_x + right_margin
    final_height = final_max_y + bottom_margin

    output_root.set("w", format_integer(final_width))
    output_root.set("width", format_integer(final_width))
    output_root.set("h", format_integer(final_height))
    output_root.set("height", format_integer(final_height))

    actual_left_margin = final_min_x
    actual_top_margin = final_min_y
    actual_right_margin = final_width - final_max_x
    actual_bottom_margin = final_height - final_max_y

    # 校验最终全部位置坐标均为整数且不存在负数。
    final_rounded_changes = normalize_position_coordinates_to_integers(
        target_layer
    )
    if final_rounded_changes != 0:
        raise ValueError(
            "最终文件仍出现非整数位置坐标，已拒绝输出；"
            f"检测到 {final_rounded_changes} 个需要再次取整的属性"
        )

    for element in iter_graph_elements(target_layer):
        if element_has_negative_coordinate(element, output_path.name):
            raise ValueError(
                f"最终 Layer 中仍存在负坐标图元："
                f"<{local_name(element.tag)}> id={element.get('id', '')!r}"
            )

    # 最终重新验证每两个相邻馈线的间隔。全图统一平移不影响间隔。
    for index in range(1, len(feeder_ranges)):
        previous_feeder, _previous_min, previous_max = feeder_ranges[index - 1]
        current_feeder, current_min, _current_max = feeder_ranges[index]
        measured_gap = current_min - previous_max
        if measured_gap != gap:
            raise ValueError(
                f"馈线 {previous_feeder} 与 {current_feeder} 的间隔不是 "
                f"{format_integer(gap)}，实际为 {format_decimal(measured_gap)}"
            )

    (
        final_id_count,
        final_unique_count,
        virtual_reference_unique_count,
        virtual_reference_occurrence_count,
    ) = validate_final_layer(target_layer, required_target_ids)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if hasattr(ET, "indent"):
        ET.indent(output_tree, space="    ")

    output_tree.write(
        output_path,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=True,
    )

    # 写出后重新解析，确保 XML 合法。
    parse_xml(output_path)

    print("\n最终结果：")
    print(f"  最终 Layer 图元 ID 数量：{final_id_count}")
    print(f"  最终唯一 ID 数量：{final_unique_count}")
    print(f"  总计重新编号图元 ID：{total_changed_element_ids}")
    print(
        "  总计重新映射引用 ID token："
        f"{total_changed_reference_tokens}"
    )
    print(
        "  最终虚拟拓扑节点 ID："
        f"{virtual_reference_unique_count} 个唯一值，"
        f"{virtual_reference_occurrence_count} 次引用（允许）"
    )
    print(
        "  全图最终统一平移："
        f"X={format_integer(canvas_shift_x)}，"
        f"Y={format_integer(canvas_shift_y)}"
    )
    print(
        "  最终内容坐标范围："
        f"minX={format_integer(final_min_x)}，"
        f"minY={format_integer(final_min_y)}，"
        f"maxX={format_integer(final_max_x)}，"
        f"maxY={format_integer(final_max_y)}"
    )
    print(
        "  最终实际边距："
        f"左={format_integer(actual_left_margin)}，"
        f"上={format_integer(actual_top_margin)}，"
        f"右={format_integer(actual_right_margin)}，"
        f"下={format_integer(actual_bottom_margin)}"
    )
    print(f"  最终对齐母线 Y：{format_integer(final_bus_y)}")
    print(f"  相邻馈线间隔：{format_integer(gap)}")
    print(f"  G.w / G.width：{format_integer(final_width)}")
    print(f"  G.h / G.height：{format_integer(final_height)}")
    print(f"  输出文件：{output_path.resolve()}")

def build_default_output_path(output_dir: Path, infos: list[GFileInfo]) -> Path:
    """在固定的 output_g_files 目录中生成默认输出文件名。"""
    prefix = infos[0].prefix
    feeder_text = "-".join(str(info.feeder) for info in infos)
    return output_dir / f"{prefix}-MERGED-{feeder_text}.sln.pic.g"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            f"读取脚本同级 {INPUT_FOLDER_NAME} 目录中的全部 .g 文件，"
            f"按馈线号排序合并单 Layer，并将结果输出到同级 {OUTPUT_FOLDER_NAME}。"
            "馈线间隔和四边距请直接修改脚本开头的用户配置常量。"
        )
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "可选的输出文件名，例如 MERGED.g；"
            f"无论是否指定，都输出到脚本同级的 {OUTPUT_FOLDER_NAME} 目录"
        ),
    )
    return parser.parse_args()


def require_nonnegative_integer(value: Decimal, option_name: str) -> Decimal:
    if value < 0:
        raise ValueError(f"{option_name} 不能小于 0")
    if value != value.to_integral_value():
        raise ValueError(f"{option_name} 必须是整数，当前值：{format_decimal(value)}")
    return value


def main() -> int:
    args = parse_args()

    try:
        # 输入、输出目录都固定在脚本文件所在目录下，
        # 因此从任意 PowerShell/CMD 路径启动脚本都能找到正确目录。
        script_dir = Path(__file__).resolve().parent
        input_dir = script_dir / INPUT_FOLDER_NAME
        output_dir = script_dir / OUTPUT_FOLDER_NAME

        if not input_dir.is_dir():
            raise NotADirectoryError(
                f"输入目录不存在：{input_dir}\n"
                f"请在脚本同级目录创建 {INPUT_FOLDER_NAME}，并放入待处理的 .g 文件。"
            )

        # 输出目录不存在时自动创建。
        output_dir.mkdir(parents=True, exist_ok=True)

        # 从脚本开头的用户配置区域读取数值。
        gap = require_nonnegative_integer(
            parse_decimal(str(FEEDER_GAP), "FEEDER_GAP"),
            "FEEDER_GAP",
        )
        left_margin = require_nonnegative_integer(
            parse_decimal(str(LEFT_MARGIN), "LEFT_MARGIN"),
            "LEFT_MARGIN",
        )
        top_margin = require_nonnegative_integer(
            parse_decimal(str(TOP_MARGIN), "TOP_MARGIN"),
            "TOP_MARGIN",
        )
        right_margin = require_nonnegative_integer(
            parse_decimal(str(RIGHT_MARGIN), "RIGHT_MARGIN"),
            "RIGHT_MARGIN",
        )
        bottom_margin = require_nonnegative_integer(
            parse_decimal(str(BOTTOM_MARGIN), "BOTTOM_MARGIN"),
            "BOTTOM_MARGIN",
        )

        print("当前用户配置：")
        print(f"  相邻馈线间隔：{format_integer(gap)}")
        print(
            "  最终画布边距："
            f"左={format_integer(left_margin)}，"
            f"上={format_integer(top_margin)}，"
            f"右={format_integer(right_margin)}，"
            f"下={format_integer(bottom_margin)}"
        )
        print(f"  输入目录：{input_dir}")
        print(f"  输出目录：{output_dir}")

        # 固定只读取输入目录下所有以 .g 结尾的文件。
        # 目录中的 .py、.txt、.xml 等其他文件不会参与处理。
        infos = discover_files(input_dir, INPUT_FILE_PATTERN)

        if args.output:
            output_name = Path(args.output).name
            if not output_name.lower().endswith(".g"):
                output_name += ".g"
            output_path = output_dir / output_name
        else:
            output_path = build_default_output_path(output_dir, infos)

        merge_g_files(
            infos=infos,
            output_path=output_path,
            gap=gap,
            left_margin=left_margin,
            top_margin=top_margin,
            right_margin=right_margin,
            bottom_margin=bottom_margin,
        )
        return 0

    except Exception as exc:
        print(f"\n错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
