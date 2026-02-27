#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
imgzip - 本地图片压缩工具
仿照 imagestool.com 的纯本地图片压缩工具

使用方法:
    1. 交互模式：python imgzip.py
    2. 命令行模式：python imgzip.py [文件/文件夹路径...]
    3. 拖拽模式：直接把图片拖到 imgzip.bat 上

支持格式：JPEG, PNG, WebP, BMP, GIF
"""

import argparse
import os
import sys
import tempfile
import shutil
import io

# 设置 Windows 控制台输出 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass

try:
    from PIL import Image
except ImportError:
    print("错误：未找到 Pillow 库")
    print("请运行：pip install Pillow")
    sys.exit(1)


# 支持的图片格式
SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}


@dataclass
class CompressResult:
    """压缩结果数据类"""
    src_path: Path
    dst_path: Path
    src_size: int
    dst_size: int
    success: bool
    error: str = ""

    @property
    def ratio(self) -> float:
        """压缩率（缩小百分比）"""
        if self.src_size == 0:
            return 0.0
        return (1 - self.dst_size / self.src_size) * 100

    @property
    def src_size_str(self) -> str:
        return format_size(self.src_size)

    @property
    def dst_size_str(self) -> str:
        return format_size(self.dst_size)


def format_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    if size_bytes < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def clean_path(path_str: str) -> str:
    r"""
    清理拖拽路径时终端自动添加的引号、空格、特殊字符
    支持多种格式：
    - "C:\Users\test\img.jpg"
    - 'C:\Users\test\img.jpg'
    - C:\Users\test\img.jpg
    - file:///C:/Users/test/img.jpg
    """
    path_str = path_str.strip()

    # 去除 file:// 前缀 (某些浏览器拖拽会产生)
    if path_str.startswith('file:///'):
        path_str = path_str[8:].replace('/', '\\')
    elif path_str.startswith('file://'):
        path_str = path_str[7:].replace('/', '\\')

    # 去除首尾引号（可能有多层）
    while path_str and path_str[0] in '"\'':
        path_str = path_str[1:]
    while path_str and path_str[-1] in '"\'':
        path_str = path_str[:-1]

    # 去除 Windows 拖拽可能产生的特殊字符
    path_str = path_str.strip('\x00\r\n')

    return path_str.strip()


def parse_user_input(user_input: str) -> List[str]:
    """
    解析用户输入，支持多种格式：
    - 单个路径（带引号或不带）
    - 多个路径（空格分隔）
    - 直接拖拽的多个文件
    """
    paths = []
    user_input = user_input.strip()

    if not user_input:
        return paths

    # 尝试使用 shlex 解析（处理带引号的路径）
    try:
        import shlex
        parsed = shlex.split(user_input)
        if parsed:
            paths = [clean_path(p) for p in parsed if clean_path(p)]
    except:
        # 如果 shlex 失败，按空格分割
        parts = user_input.split()
        paths = [clean_path(p) for p in parts if clean_path(p)]

    return paths


def is_image_file(path: Path) -> bool:
    """判断是否为支持的图片文件"""
    return path.suffix.lower() in SUPPORTED_EXTS


def get_image_files(paths: List[str], recursive: bool = False) -> List[Path]:
    """从路径列表获取所有图片文件"""
    image_files = []

    for path_str in paths:
        path_str = clean_path(path_str)
        if not path_str:
            continue

        path = Path(path_str)

        if not path.exists():
            print(f"警告：路径不存在 - {path}")
            continue

        if path.is_file() and is_image_file(path):
            image_files.append(path)
        elif path.is_dir():
            if recursive:
                for ext in ['**/*.jpg', '**/*.jpeg', '**/*.png', '**/*.webp', '**/*.bmp', '**/*.gif']:
                    image_files.extend(path.glob(ext))
            else:
                for ext in ['*.jpg', '*.jpeg', '*.png', '**/*.webp', '*.bmp', '*.gif']:
                    image_files.extend(path.glob(ext))

    # 去重并保持顺序
    seen = set()
    unique_files = []
    for f in image_files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_files.append(f)

    return unique_files


def compress_jpeg(src_path: Path, dst_path: Path, quality: int, keep_exif: bool = True) -> Tuple[bool, str]:
    """压缩 JPEG 图片"""
    try:
        with Image.open(src_path) as img:
            # 转换为 RGB（处理 RGBA 和带透明的图片）
            if img.mode in ('RGBA', 'LA', 'P'):
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

            # 保存参数
            save_kwargs = {
                'quality': quality,
                'optimize': True,
                'progressive': True,
            }

            # 保留 EXIF 信息
            if keep_exif:
                try:
                    exif_data = img.info.get('exif', b'')
                    if exif_data:
                        save_kwargs['exif'] = exif_data
                except:
                    pass

            img.save(dst_path, 'JPEG', **save_kwargs)
            return True, ""
    except Exception as e:
        return False, str(e)


def compress_png(src_path: Path, dst_path: Path, quality: int) -> Tuple[bool, str]:
    """压缩 PNG 图片"""
    try:
        with Image.open(src_path) as img:
            # 检查是否有透明度
            has_alpha = img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)

            if has_alpha:
                # 保持透明度
                if img.mode == 'P':
                    img = img.convert('RGBA')
                img.save(dst_path, 'PNG', optimize=True)
            else:
                # 无透明度，可以量化压缩
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # 质量参数映射到 PNG 压缩级别
                if quality < 50:
                    # 低质量：量化到 64 色
                    img_quantized = img.quantize(colors=64, method=Image.Quantize.MEDIANCUT)
                    img_quantized.save(dst_path, 'PNG', optimize=True)
                elif quality < 80:
                    # 中等质量：量化到 256 色
                    img_quantized = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
                    img_quantized.save(dst_path, 'PNG', optimize=True)
                else:
                    # 高质量：保持原色
                    img.save(dst_path, 'PNG', optimize=True)

            return True, ""
    except Exception as e:
        return False, str(e)


def compress_webp(src_path: Path, dst_path: Path, quality: int) -> Tuple[bool, str]:
    """压缩 WebP 图片"""
    try:
        with Image.open(src_path) as img:
            # 检查是否有透明度
            has_alpha = img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)

            if has_alpha:
                if img.mode == 'P':
                    img = img.convert('RGBA')
                img.save(dst_path, 'WebP', quality=quality, method=6)
            else:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(dst_path, 'WebP', quality=quality, method=6)

            return True, ""
    except Exception as e:
        return False, str(e)


def compress_image(src_path: Path, dst_path: Path, quality: int, target_format: str = 'keep') -> CompressResult:
    """压缩单张图片"""
    src_size = src_path.stat().st_size
    ext = src_path.suffix.lower()

    # 特殊处理：PNG 格式强制转为 JPEG
    if ext == '.png':
        target_format = 'jpeg'
        # 覆盖模式：将扩展名改为.jpg
        if dst_path == src_path:  # 覆盖模式
            dst_path = src_path.with_suffix('.jpg')
        else:  # 另存模式：保持 _zipimg 后缀，但扩展名为.jpg
            dst_path = dst_path.with_suffix('.jpg')
    elif target_format == 'keep':
        if ext in ('.jpg', '.jpeg'):
            target_format = 'jpeg'
        elif ext == '.png':
            target_format = 'png'
        elif ext == '.webp':
            target_format = 'webp'
        else:
            target_format = 'jpeg'  # 默认转为 JPEG
    else:
        # 如果指定了目标格式，修改输出扩展名
        if target_format == 'jpeg' and dst_path.suffix.lower() not in ('.jpg', '.jpeg'):
            dst_path = dst_path.with_suffix('.jpg')
        elif target_format == 'webp' and dst_path.suffix.lower() != '.webp':
            dst_path = dst_path.with_suffix('.webp')
        elif target_format == 'png' and dst_path.suffix.lower() != '.png':
            dst_path = dst_path.with_suffix('.png')

    success = False
    error = ""

    if target_format == 'jpeg':
        success, error = compress_jpeg(src_path, dst_path, quality)
    elif target_format == 'png':
        success, error = compress_png(src_path, dst_path, quality)
    elif target_format == 'webp':
        success, error = compress_webp(src_path, dst_path, quality)
    else:
        error = f"不支持的格式：{target_format}"

    dst_size = dst_path.stat().st_size if dst_path.exists() else 0

    return CompressResult(
        src_path=src_path,
        dst_path=dst_path,
        src_size=src_size,
        dst_size=dst_size,
        success=success,
        error=error
    )


def get_destination_path(src_path: Path, mode: str) -> Path:
    """根据模式获取目标路径"""
    if mode == 'overwrite':
        return src_path
    else:  # separate
        # 在文件名后添加 _zipimg 后缀
        new_name = f"{src_path.stem}_zipimg{src_path.suffix}"
        return src_path.parent / new_name


def print_table(results: List[CompressResult]):
    """打印结果表格"""
    if not results:
        return

    print("\n" + "=" * 80)
    print(f"{'源文件':<40} {'原大小':>10} {'新大小':>10} {'压缩率':>12} {'状态':>6}")
    print("=" * 80)

    for r in results:
        src_name = r.src_path.name
        if len(src_name) > 38:
            src_name = src_name[:35] + "..."

        ratio_str = f"{r.ratio:+.1f}%" if r.success else "N/A"
        status = "✓" if r.success else "✗"

        print(f"{src_name:<40} {r.src_size_str:>10} {r.dst_size_str:>10} {ratio_str:>12} {status:>6}")

    print("=" * 80)

    # 统计
    total_src = sum(r.src_size for r in results if r.success)
    total_dst = sum(r.dst_size for r in results if r.success)
    total_ratio = (1 - total_dst / total_src) * 100 if total_src > 0 else 0
    success_count = sum(1 for r in results if r.success)
    saved = total_src - total_dst

    print(f"总计：{len(results)} 个文件 | 成功：{success_count} | 原始：{format_size(total_src)} | "
          f"压缩后：{format_size(total_dst)} | 节省：{format_size(saved)} | 压缩率：{total_ratio:+.1f}%")
    print()


def show_help():
    """显示帮助信息"""
    print("\n" + "=" * 60)
    print("imgzip - 图片压缩工具")
    print("=" * 60)
    print("\n【使用方式】")
    print("  1. 拖拽：直接把图片/文件夹拖到本窗口或 imgzip.bat 上")
    print("  2. 粘贴：复制文件路径后粘贴到本窗口")
    print("  3. 命令：python imgzip.py 图片.jpg -q 85 -o separate")
    print("\n【支持格式】JPG, PNG, WebP, BMP, GIF")
    print("\n【快捷命令】")
    print("  q     - 退出程序")
    print("  h     - 显示帮助")
    print("  set q - 设置默认质量 (如：set q 90)")
    print("=" * 60)


def interactive_mode(args):
    """交互模式主循环"""
    print("\n" + "═" * 60)
    print("   imgzip - 图片压缩工具 (仿 imagestool.com)")
    print("═" * 60)
    print("\n📌 使用方法:")
    print("   • 拖拽图片/文件夹 到本窗口")
    print("   • 粘贴文件路径 或 文件夹路径")
    print("   • 多个文件可用空格分隔")
    print("\n💡 输入 'h' 看帮助，输入 'q' 退出")
    print("═" * 60)

    current_quality = args.quality
    current_recursive = args.recursive
    current_format = args.format

    while True:
        try:
            # 获取用户输入
            user_input = input("\n👉 请输入路径：").strip()

            if not user_input:
                continue

            cmd = user_input.lower()

            if cmd == 'q' or cmd == 'quit' or cmd == 'exit':
                print("\n👋 再见！")
                break

            if cmd == 'h' or cmd == 'help':
                show_help()
                continue

            # 设置命令
            if cmd.startswith('set '):
                parts = cmd.split()
                if len(parts) >= 3 and parts[1] == 'q':
                    try:
                        new_q = int(parts[2])
                        if 1 <= new_q <= 100:
                            current_quality = new_q
                            print(f"✓ 质量已设置为：{new_q}")
                        else:
                            print("✗ 质量必须在 1-100 之间")
                    except:
                        print("✗ 无效的质量值")
                elif len(parts) >= 3 and parts[1] == 'r':
                    current_recursive = parts[2].lower() in ('true', '1', 'yes', 'on')
                    print(f"✓ 递归模式：{'开启' if current_recursive else '关闭'}")
                elif len(parts) >= 3 and parts[1] == 'f':
                    fmt = parts[2].lower()
                    if fmt in ['keep', 'jpeg', 'png', 'webp']:
                        current_format = fmt
                        print(f"✓ 输出格式：{fmt}")
                    else:
                        print("✗ 不支持的格式")
                continue

            # 解析路径
            paths = parse_user_input(user_input)

            # 获取图片文件列表
            image_files = get_image_files(paths, recursive=current_recursive)

            if not image_files:
                print("❌ 未找到有效的图片文件。")
                print("   提示：直接拖拽图片文件到窗口，或粘贴文件路径")
                continue

            print(f"\n✅ 找到 {len(image_files)} 个图片文件:")
            for i, f in enumerate(image_files[:10], 1):
                print(f"   {i}. {f}")
            if len(image_files) > 10:
                print(f"   ... 还有 {len(image_files) - 10} 个文件")
            print()

            # 询问保存方式
            print("请选择保存方式:")
            print("   [1] 覆盖原文件 (危险)")
            print("   [2] 另存为 (添加 _zipimg 后缀)")

            while True:
                save_choice = input("\n选择 (1/2，默认 2): ").strip()
                if save_choice in ('1', '2', ''):
                    break
                print("请输入 1 或 2")

            save_mode = 'overwrite' if save_choice == '1' else 'separate'

            if save_mode == 'overwrite':
                print("\n⚠️  警告：覆盖模式将修改原始文件！")
                confirm = input("确认覆盖？(y/N): ").strip().lower()
                if confirm != 'y':
                    print("已取消，返回选择。")
                    continue

            # 询问压缩质量
            print(f"\n当前质量：{current_quality} (1-100)")
            quality_input = input(f"按 Enter 使用 {current_quality}，或输入新质量：").strip()
            if quality_input:
                try:
                    quality = int(quality_input)
                    quality = max(1, min(100, quality))
                    current_quality = quality
                except:
                    quality = current_quality
            else:
                quality = current_quality

            # 询问输出格式
            print(f"\n输出格式：{current_format} (keep/jpeg/png/webp)")
            fmt_input = input(f"按 Enter 使用 {current_format}，或输入新格式：").strip().lower()
            if fmt_input and fmt_input in ['keep', 'jpeg', 'png', 'webp']:
                current_format = fmt_input

            print(f"\n开始压缩 (质量：{quality}, 格式：{current_format})...")
            print()

            # 执行压缩
            results = []
            for i, src_path in enumerate(image_files, 1):
                dst_path = get_destination_path(src_path, save_mode)

                print(f"[{i}/{len(image_files)}] {src_path.name}...", end=" ")

                result = compress_image(src_path, dst_path, quality, current_format)
                results.append(result)

                if result.success:
                    ratio = result.ratio
                    # 根据压缩率显示颜色提示
                    if ratio > 50:
                        print(f"{result.src_size_str} → {result.dst_size_str} ({ratio:+.1f}%) ✓✓")
                    elif ratio > 20:
                        print(f"{result.src_size_str} → {result.dst_size_str} ({ratio:+.1f}%) ✓")
                    else:
                        print(f"{result.src_size_str} → {result.dst_size_str} ({ratio:+.1f}%)")
                else:
                    print(f"失败：{result.error}")

            # 打印结果汇总
            print_table(results)

        except KeyboardInterrupt:
            print("\n\n👋 中断，再见！")
            break
        except EOFError:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生错误：{e}")


def batch_mode(paths: List[str], args):
    """批处理模式（直接从命令行启动）"""
    image_files = get_image_files(paths, args.recursive)

    if not image_files:
        print("❌ 未找到有效的图片文件。")
        sys.exit(1)

    print(f"✅ 找到 {len(image_files)} 个图片文件:")
    for f in image_files:
        print(f"   {f}")
    print()

    print(f"开始压缩 (质量：{args.quality}, 模式：{args.output})...")
    print()

    results = []
    for i, src_path in enumerate(image_files, 1):
        dst_path = get_destination_path(src_path, args.output)

        print(f"[{i}/{len(image_files)}] {src_path.name}...", end=" ")

        result = compress_image(src_path, dst_path, args.quality, args.format)
        results.append(result)

        if result.success:
            ratio = result.ratio
            print(f"{result.src_size_str} → {result.dst_size_str} ({ratio:+.1f}%)")
        else:
            print(f"失败：{result.error}")

    print_table(results)

    # 检查是否有失败
    failed = sum(1 for r in results if not r.success)
    if failed > 0:
        sys.exit(1)


def drop_file_mode():
    """
    拖拽文件模式
    当用户直接把文件拖到 imgzip.bat 上时，会通过命令行参数传入
    这个函数处理这种情况
    """
    # 检查是否有命令行参数（拖拽文件会产生参数）
    if len(sys.argv) > 1:
        # 有参数，说明是拖拽或命令行启动
        parser = argparse.ArgumentParser(description='imgzip - 图片压缩工具')
        parser.add_argument('paths', nargs='*', help='图片文件或文件夹路径')
        parser.add_argument('-q', '--quality', type=int, default=85)
        parser.add_argument('-o', '--output', choices=['overwrite', 'separate'], default='separate')
        parser.add_argument('-r', '--recursive', action='store_true')
        parser.add_argument('-f', '--format', choices=['keep', 'jpeg', 'png', 'webp'], default='keep')

        args = parser.parse_args()
        batch_mode(args.paths, args)
        return True
    return False


def main():
    # 检查是否是拖拽文件启动（有参数但没有 - 开头的）
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        # 拖拽文件模式
        parser = argparse.ArgumentParser(description='imgzip - 图片压缩工具')
        parser.add_argument('paths', nargs='*', help='图片文件或文件夹路径')
        parser.add_argument('-q', '--quality', type=int, default=85)
        parser.add_argument('-o', '--output', choices=['overwrite', 'separate'], default='separate')
        parser.add_argument('-r', '--recursive', action='store_true')
        parser.add_argument('-f', '--format', choices=['keep', 'jpeg', 'png', 'webp'], default='keep')

        args = parser.parse_args()

        if args.paths:
            batch_mode(args.paths, args)
            return

    # 检查是否有命令行参数
    parser = argparse.ArgumentParser(
        description='imgzip - 图片压缩工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python imgzip.py photo.jpg                    # 压缩单张图片
  python imgzip.py ./photos -r                  # 递归压缩文件夹
  python imgzip.py img1.jpg img2.png -q 90      # 高质量压缩
  python imgzip.py ./pics -o separate -r        # 另存为模式

交互模式:
  python imgzip.py                              # 启动交互模式
  然后拖拽文件到窗口或粘贴路径
        """
    )

    parser.add_argument('paths', nargs='*', help='图片文件或文件夹路径')
    parser.add_argument('-q', '--quality', type=int, default=85,
                        help='压缩质量 (1-100, 默认：85)')
    parser.add_argument('-o', '--output', choices=['overwrite', 'separate'],
                        default='separate', help='输出模式 (默认：separate)')
    parser.add_argument('-r', '--recursive', action='store_true',
                        help='递归处理子文件夹')
    parser.add_argument('-f', '--format', choices=['keep', 'jpeg', 'png', 'webp'],
                        default='keep', help='目标格式 (默认：keep 保持原格式)')

    args = parser.parse_args()

    if args.paths:
        batch_mode(args.paths, args)
    else:
        interactive_mode(args)


if __name__ == '__main__':
    main()
