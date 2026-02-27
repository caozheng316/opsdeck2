#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
imgjion - 图片纵向拼接工具
支持智能文件名识别和自然排序

使用方法:
    1. 右键菜单：多选图片 → 右键 → "用 imgjion 拼接"
    2. 拖拽：多选图片拖到 imgjion.bat 上
    3. 命令行：python imgjion.py 图 1.jpg 图 2.jpg 图 3.jpg
"""

import argparse
import os
import re
import sys
import io
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
from dataclasses import dataclass

# 设置 Windows 控制台输出 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    from PIL import Image
except ImportError:
    print("错误：未找到 Pillow 库")
    print("请运行：pip install Pillow")
    sys.exit(1)


# 支持的图片格式
SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}


@dataclass
class ParsedFilename:
    """解析后的文件名"""
    original: str
    prefix: str       # 前缀部分
    number: int       # 数字部分
    extension: str    # 扩展名
    sort_key: tuple   # 排序键


def natural_sort_key(s: str) -> tuple:
    """
    自然排序键：将数字部分转为整数比较
    解决 '2' > '10' 的字典序问题

    示例:
        "详情_02.jpg" -> (("详情_", 2, ".jpg"),)
        "详情_10.jpg" -> (("详情_", 10, ".jpg"),)
    """
    parts = []
    # 分离数字和非数字部分
    for part in re.split(r'(\d+)', s):
        if part.isdigit():
            parts.append((0, int(part)))  # 数字部分，标记为 0 确保数字在最后
        else:
            parts.append((1, part.lower()))  # 非数字部分
    return tuple(parts)


def parse_filename(filename: str) -> Optional[ParsedFilename]:
    """
    解析文件名，提取前缀和数字
    支持格式:
        - 详情_01.jpg
        - image2.png
        - pic-003.jpg
        - 图 10.jpeg
    """
    name = Path(filename).stem
    ext = Path(filename).suffix.lower()

    # 匹配：前缀 + 数字结尾
    # 贪婪匹配前缀，确保数字在最后
    match = re.match(r'^(.+?)(\d+)$', name)

    if match:
        prefix = match.group(1)
        number = int(match.group(2))
        return ParsedFilename(
            original=filename,
            prefix=prefix,
            number=number,
            extension=ext,
            sort_key=(prefix, number)
        )
    else:
        # 没有数字的文件名
        return ParsedFilename(
            original=filename,
            prefix=name,
            number=0,
            extension=ext,
            sort_key=(name, 0)
        )


def group_images(files: List[Path]) -> List[List[Path]]:
    """
    将图片按前缀分组
    返回：分组后的文件列表
    """
    from collections import defaultdict

    groups = defaultdict(list)

    for f in files:
        parsed = parse_filename(f.name)
        if parsed:
            groups[parsed.prefix].append((f, parsed.number))

    # 对每组按数字自然排序
    result = []
    for prefix, items in groups.items():
        # 按数字排序
        items.sort(key=lambda x: x[1])
        result.append([item[0] for item in items])

    return result


def scan_folder(folder_path: Path) -> List[Path]:
    """
    扫描文件夹，识别符合"相同字符串 + 序号"规律的图片文件

    Args:
        folder_path: 文件夹路径

    Returns:
        找到的图片文件列表
    """
    # 使用 set 去重
    seen_paths = set()

    for ext in SUPPORTED_EXTS:
        # 匹配小写和大写扩展名
        for pattern in [f"*{ext}", f"*{ext.upper()}"]:
            for f in folder_path.glob(pattern):
                # 只处理文件，排除子文件夹
                if f.is_file() and f not in seen_paths:
                    seen_paths.add(f)

    # 转换为列表
    all_files = list(seen_paths)

    # 过滤出有数字后缀的文件（序号 > 0）
    valid_files = []
    for f in all_files:
        parsed = parse_filename(f.name)
        if parsed and parsed.number > 0:
            valid_files.append(f)

    return valid_files


def detect_image_groups(files: List[Path]) -> List[Tuple[str, List[Path]]]:
    """
    检测并分组图片

    Returns:
        分组列表，每项为 (prefix, [files...])

    如果所有文件都有相同前缀，返回单组
    否则按前缀分组
    """
    # 解析所有文件名
    parsed_files = []
    for f in files:
        parsed = parse_filename(f.name)
        if parsed:
            parsed_files.append((f, parsed))

    if not parsed_files:
        return []

    # 检查是否所有文件前缀相同
    prefixes = set(p.prefix for _, p in parsed_files)

    if len(prefixes) == 1:
        # 单组：按数字排序
        parsed_files.sort(key=lambda x: x[1].number)
        return [(prefixes.pop(), [f for f, _ in parsed_files])]
    else:
        # 多组：按前缀分组
        from collections import defaultdict
        groups = defaultdict(list)
        for f, p in parsed_files:
            groups[p.prefix].append((f, p.number))

        result = []
        for prefix, items in groups.items():
            items.sort(key=lambda x: x[1])
            result.append((prefix, [item[0] for item in items]))

        return result


def stitch_images_vertically(images: List[Path], output_dir: Path, output_prefix: Optional[str] = None) -> Path:
    """
    纵向拼接图片

    Args:
        images: 图片路径列表
        output_dir: 输出目录
        output_prefix: 输出文件名前缀，如果为 None 则使用时间戳格式

    Returns:
        输出文件路径

    Examples:
        >>> # 详情_01.jpg + 详情_02.jpg → 详情_拼接.jpg
        >>> stitch_images_vertically(images, output_dir, output_prefix="详情")
    """
    if not images:
        raise ValueError("没有图片需要拼接")

    # 读取所有图片
    img_objects = []
    max_width = 0

    for img_path in images:
        try:
            with Image.open(img_path) as img:
                # 转为 RGB 模式（处理 RGBA、P 等）
                if img.mode in ('RGBA', 'P', 'LA'):
                    # 创建白色背景
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode in ('RGBA', 'LA'):
                        background.paste(img, mask=img.split()[-1])
                    else:
                        background.paste(img)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                img_objects.append(img.copy())
                max_width = max(max_width, img.width)
        except Exception as e:
            print(f"警告：无法读取 {img_path.name}: {e}")
            continue

    if not img_objects:
        raise ValueError("没有有效的图片可以拼接")

    # 计算总高度
    total_height = sum(img.height for img in img_objects)

    # 创建新画布
    result = Image.new('RGB', (max_width, total_height), (255, 255, 255))

    # 从上往下粘贴
    y_offset = 0
    for img in img_objects:
        # 居中放置（如果图片宽度小于最大宽度）
        x_offset = (max_width - img.width) // 2
        result.paste(img, (x_offset, y_offset))
        y_offset += img.height

    # 生成输出文件名
    if output_prefix:
        # 使用前缀 + 拼接后缀：详情_01.jpg + 详情_02.jpg → 详情_拼接.jpg
        output_name = f"{output_prefix}_拼接.jpg"
    else:
        # 使用时间戳格式（向后兼容）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"拼接结果_{timestamp}.jpg"
    output_path = output_dir / output_name

    # 保存
    result.save(output_path, 'JPEG', quality=90, optimize=True, progressive=True)

    # 清理
    for img in img_objects:
        img.close()
    result.close()

    return output_path


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def select_groups_interactive(groups: List[Tuple[str, List[Path]]]) -> List[Tuple[str, List[Path]]]:
    """
    交互式选择要合并的分组

    Args:
        groups: 分组列表，每项为 (prefix, files)

    Returns:
        用户选择的分组
    """
    if len(groups) == 1:
        # 只有一个分组，直接返回
        return groups

    print("\n" + "═" * 60)
    print("   检测到多个分组，请选择要合并的分组")
    print("═" * 60)
    print()

    for i, (prefix, files) in enumerate(groups, 1):
        print(f"  [{i}] {prefix}  ({len(files)} 个文件)")

    print()
    print("═" * 60)
    print("提示：")
    print("  - 输入序号选择单个分组（如：1）")
    print("  - 输入多个序号用逗号分隔（如：1,2,3）")
    print("  - 输入 a 选择全部")
    print("  - 输入 q 退出")
    print("═" * 60)

    while True:
        try:
            choice = input("\n请选择：").strip().lower()

            if not choice:
                continue

            if choice == 'q':
                return []

            if choice == 'a':
                return groups

            # 解析序号
            indices = []
            for c in choice.split(','):
                c = c.strip()
                if c.isdigit():
                    idx = int(c)
                    if 1 <= idx <= len(groups):
                        indices.append(idx - 1)
                    else:
                        print(f"❌ 无效的序号：{idx}，请输入 1-{len(groups)} 之间的数字")
                        break
                else:
                    print(f"❌ 无效的输入：{c}")
                    break

            if len(indices) == len(choice.split(',')):
                # 所有序号都有效
                return [groups[i] for i in indices]

        except KeyboardInterrupt:
            print("\n👋 中断，再见！")
            return []
        except EOFError:
            print("\n👋 再见！")
            return []


def process_images(files: List[Path], output_dir: Path = None, output_prefix: Optional[str] = None, interactive: bool = False) -> List[Path]:
    """
    处理图片拼接

    Args:
        files: 图片文件列表
        output_dir: 输出目录
        output_prefix: 输出文件名前缀（可选）
        interactive: 是否启用交互式选择分组

    Returns:
        输出文件列表
    """
    if output_dir is None:
        output_dir = Path(__file__).parent

    output_dir.mkdir(parents=True, exist_ok=True)

    # 检测图片分组 (返回 List[Tuple[str, List[Path]]])
    groups = detect_image_groups(files)

    if not groups:
        raise ValueError("没有找到有效的图片文件")

    # 交互式选择分组
    if interactive:
        selected_groups = select_groups_interactive(groups)
        if not selected_groups:
            print("未选择任何分组")
            return []
        groups = selected_groups

    output_files = []

    print(f"\n检测到 {len(groups)} 组:")

    for i, (prefix, group) in enumerate(groups, 1):
        print(f"\n第 {i} 组：{prefix}  ({len(group)} 个文件)")

        # 确定输出文件名前缀
        # 如果传入了 output_prefix，使用传入的
        # 否则从分组文件自动提取前缀
        prefix_for_output = output_prefix if output_prefix else prefix

        # 拼接
        output_path = stitch_images_vertically(group, output_dir, output_prefix=prefix_for_output)
        output_files.append(output_path)

        output_size = output_path.stat().st_size
        print(f"  → {output_path.name} ({format_size(output_size)})")

    return output_files


def interactive_mode():
    """交互模式：让用户输入或拖拽图片路径"""
    print("\n" + "═" * 60)
    print("   imgjion - 图片拼接工具")
    print("═" * 60)
    print("\n📌 使用方法:")
    print("   • 拖拽图片文件到本窗口")
    print("   • 粘贴图片路径（多个用空格分隔）")
    print("   • 按回车键开始拼接")
    print("\n💡 输入 'q' 退出")
    print("═" * 60)

    while True:
        try:
            user_input = input("\n👉 请输入或拖拽图片路径：").strip()

            if not user_input:
                continue

            if user_input.lower() in ('q', 'quit', 'exit'):
                print("\n👋 再见！")
                break

            # 解析路径
            files = []
            for f in user_input.split():
                path = Path(f.strip().strip('"').strip("'"))
                if path.exists() and path.suffix.lower() in SUPPORTED_EXTS:
                    files.append(path)
                else:
                    print(f"警告：跳过无效文件 - {f}")

            if not files:
                print("❌ 未找到有效的图片文件。")
                continue

            # 使用当前目录作为输出目录
            output_dir = Path.cwd()

            try:
                result_paths = process_images(files, output_dir)
                print("\n✅ 全部完成！")
                print(f"\n输出文件位置：")
                for p in result_paths:
                    print(f"  - {p}")
            except Exception as e:
                print(f"\n❌ 错误：{e}")

        except KeyboardInterrupt:
            print("\n\n👋 中断，再见！")
            break
        except EOFError:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生错误：{e}")


def main():
    parser = argparse.ArgumentParser(
        description='imgjion - 图片纵向拼接工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python imgjion.py 详情_01.jpg 详情_02.jpg 详情_03.jpg
  python imgjion.py ./images/*.jpg -o ./output
  python imgjion.py 图 1.png 图 2.png 图 3.png
  python imgjion.py --folder ./images  (文件夹扫描模式)

文件名规则:
  支持 "前缀 + 数字" 格式，如:
  - 详情_01.jpg, 详情_02.jpg
  - image1.png, image2.png
  - pic-001.jpg, pic-002.jpg

  自动按数字自然排序：1, 2, 3... 9, 10, 11
        """
    )

    parser.add_argument('files', nargs='*', help='图片文件路径')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='输出目录（默认保存在第一张图片所在文件夹）')
    parser.add_argument('-s', '--single', action='store_true',
                        help='强制作为单组处理（不分组）')
    parser.add_argument('--folder', type=str, default=None,
                        help='文件夹扫描模式：扫描指定文件夹中的图片')
    parser.add_argument('-i', '--interactive', action='store_true',
                        help='交互模式：允许选择要合并的分组')

    args = parser.parse_args()

    # 文件夹模式
    if args.folder:
        folder_path = Path(args.folder)
        if not folder_path.exists():
            print(f"错误：文件夹不存在 - {folder_path}")
            sys.exit(1)

        print(f"\n扫描文件夹：{folder_path}")

        files = scan_folder(folder_path)

        if not files:
            print(f"警告：未找到有效的图片文件")
            sys.exit(0)

        # 按前缀分组显示（使用 detect_image_groups 函数）
        groups = detect_image_groups(files)

        print(f"找到 {len(files)} 张图片，分为 {len(groups)} 组:")
        print()
        for prefix, group_files in groups:
            print(f"  {prefix}  ({len(group_files)} 个文件)")
        print()

        # 输出目录：默认使用文件夹本身
        output_dir = Path(args.output) if args.output else folder_path

        try:
            result_paths = process_images(files, output_dir, interactive=args.interactive)
            if result_paths:
                print("\n完成！")
                print(f"\n输出文件：")
                for p in result_paths:
                    print(f"  - {p}")
            else:
                print("\n未执行拼接")
        except Exception as e:
            print(f"\n❌ 错误：{e}")
            sys.exit(1)

    # 文件模式：有参数
    elif args.files:
        # 转换路径
        files = []
        for f in args.files:
            path = Path(f.strip().strip('"').strip("'"))
            if path.exists() and path.suffix.lower() in SUPPORTED_EXTS:
                files.append(path)
            else:
                print(f"警告：跳过无效文件 - {f}")

        if not files:
            print("错误：没有有效的图片文件")
            sys.exit(1)

        # 输出目录：默认为第一张图片所在文件夹
        if args.output:
            output_dir = Path(args.output)
        else:
            output_dir = files[0].parent  # 使用第一张图片的文件夹

        try:
            result_paths = process_images(files, output_dir, interactive=args.interactive)
            print("\n✅ 全部完成！")
            print(f"\n输出文件位置：")
            for p in result_paths:
                print(f"  - {p}")
        except Exception as e:
            print(f"\n❌ 错误：{e}")
            sys.exit(1)

    else:
        # 没有参数，进入交互模式
        interactive_mode()


if __name__ == '__main__':
    main()
