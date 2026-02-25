#!/usr/bin/env python3
"""
本地图片压缩工具 - 类似 ImagesTool 的实现
支持 JPG、PNG、WebP 格式的高效压缩

依赖安装:
pip install Pillow pillow-heif  # pillow-heif 用于支持 HEIC 格式

使用方法:
python image_compressor.py -i input.jpg -o output.jpg --quality 80
python image_compressor.py --dir ./images --quality 70 --max-width 1920
"""

import os
import sys
import argparse
from pathlib import Path
from PIL import Image, ImageOps
import io

# 支持的格式
SUPPORTED_FORMATS = {
    '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'
}

# 尝试导入 HEIC 支持
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    SUPPORTED_FORMATS.add('.heic')
    SUPPORTED_FORMATS.add('.heif')
except ImportError:
    pass


class ImageCompressor:
    """图片压缩器 - 核心压缩逻辑"""

    def __init__(self, quality=85, max_width=0, max_height=0,
                 preserve_exif=True, output_format=None):
        """
        初始化压缩器

        Args:
            quality: 压缩质量 (1-100), JPG/WebP 有效
            max_width: 最大宽度, 0 表示保持原尺寸
            max_height: 最大高度, 0 表示保持原尺寸
            preserve_exif: 是否保留 EXIF 信息
            output_format: 输出格式 ('JPEG', 'PNG', 'WEBP', None=保持原格式)
        """
        self.quality = quality
        self.max_width = max_width
        self.max_height = max_height
        self.preserve_exif = preserve_exif
        self.output_format = output_format

    def compress(self, input_path, output_path=None):
        """
        压缩单张图片

        Args:
            input_path: 输入图片路径
            output_path: 输出路径, None 则覆盖原文件

        Returns:
            dict: 包含原始大小、压缩后大小、压缩率等信息
        """
        input_path = Path(input_path)
        if output_path is None:
            output_path = input_path
        else:
            output_path = Path(output_path)

        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在: {input_path}")

        # 获取原始文件大小
        original_size = input_path.stat().st_size

        # 打开图片
        try:
            img = Image.open(input_path)

            # 处理 EXIF 方向信息
            if self.preserve_exif:
                img = ImageOps.exif_transpose(img)

            # 转换 RGBA 为 RGB (JPG 不支持透明)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            # 计算新尺寸
            new_width, new_height = self._calculate_size(img.size)

            if new_width != img.width or new_height != img.height:
                # 使用 LANCZOS 算法进行高质量缩放
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 确定输出格式
            save_format = self._get_save_format(input_path.suffix, output_path.suffix)

            # 准备保存参数
            save_kwargs = self._get_save_kwargs(save_format)

            # 如果是 PNG, 尝试优化
            if save_format == 'PNG':
                save_kwargs['optimize'] = True

            # 保存到内存以获取压缩后大小
            img_bytes = io.BytesIO()
            img.save(img_bytes, format=save_format, **save_kwargs)
            img_bytes.seek(0)

            compressed_size = len(img_bytes.getvalue())

            # 写入文件
            with open(output_path, 'wb') as f:
                f.write(img_bytes.getvalue())

            return {
                'input_path': str(input_path),
                'output_path': str(output_path),
                'original_size': original_size,
                'compressed_size': compressed_size,
                'original_dimensions': f"{img.width}x{img.height}",
                'compression_ratio': f"{(1 - compressed_size / original_size) * 100:.1f}%",
                'format': save_format
            }

        except Exception as e:
            raise Exception(f"压缩失败: {e}")

    def _calculate_size(self, original_size):
        """计算缩放后的尺寸"""
        width, height = original_size

        if self.max_width <= 0 and self.max_height <= 0:
            return width, height

        # 计算缩放比例
        width_ratio = self.max_width / width if self.max_width > 0 else float('inf')
        height_ratio = self.max_height / height if self.max_height > 0 else float('inf')

        ratio = min(width_ratio, height_ratio)

        if ratio >= 1:
            return width, height

        return int(width * ratio), int(height * ratio)

    def _get_save_format(self, input_suffix, output_suffix):
        """确定保存格式"""
        if self.output_format:
            return self.output_format.upper()

        output_suffix = output_suffix.lower()
        if output_suffix in ('.jpg', '.jpeg'):
            return 'JPEG'
        elif output_suffix == '.png':
            return 'PNG'
        elif output_suffix == '.webp':
            return 'WEBP'

        # 根据输入格式决定
        input_suffix = input_suffix.lower()
        if input_suffix in ('.jpg', '.jpeg'):
            return 'JPEG'
        elif input_suffix == '.png':
            return 'PNG'
        elif input_suffix == '.webp':
            return 'WEBP'

        return 'JPEG'  # 默认

    def _get_save_kwargs(self, save_format):
        """获取保存参数"""
        kwargs = {}

        if save_format == 'JPEG':
            kwargs.update({
                'quality': self.quality,
                'progressive': True,  # 渐进式 JPG
                'optimize': True,
            })
        elif save_format == 'WEBP':
            kwargs.update({
                'quality': self.quality,
                'method': 6,  # 压缩方法 (0-6), 6 最慢但压缩率最高
            })
        elif save_format == 'PNG':
            # PNG 压缩级别 (0-9)
            kwargs['compress_level'] = max(0, min(9, (100 - self.quality) // 10))

        return kwargs


def batch_compress(directory, output_dir=None, pattern='*',
                   quality=85, max_width=0, max_height=0,
                   output_format=None, recursive=False):
    """
    批量压缩目录中的图片

    Args:
        directory: 输入目录
        output_dir: 输出目录, None 则覆盖原文件
        pattern: 文件匹配模式
        quality: 压缩质量
        max_width: 最大宽度
        max_height: 最大高度
        output_format: 输出格式
        recursive: 是否递归处理子目录

    Returns:
        list: 压缩结果列表
    """
    directory = Path(directory)
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    compressor = ImageCompressor(
        quality=quality,
        max_width=max_width,
        max_height=max_height,
        output_format=output_format
    )

    results = []
    total_original = 0
    total_compressed = 0

    # 查找图片文件
    if recursive:
        files = directory.rglob(pattern)
    else:
        files = directory.glob(pattern)

    image_files = [f for f in files if f.suffix.lower() in SUPPORTED_FORMATS]

    print(f"找到 {len(image_files)} 张图片")

    for img_file in image_files:
        try:
            # 确定输出路径
            if output_dir:
                rel_path = img_file.relative_to(directory)
                out_file = output_dir / rel_path
                out_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                out_file = img_file

            # 压缩
            result = compressor.compress(img_file, out_file)
            results.append(result)
            total_original += result['original_size']
            total_compressed += result['compressed_size']

            # 打印进度
            print(f"✓ {img_file.name}: {format_size(result['original_size'])} → "
                  f"{format_size(result['compressed_size'])} ({result['compression_ratio']})")

        except Exception as e:
            print(f"✗ {img_file.name}: {e}")

    # 打印统计
    if results:
        total_savings = (1 - total_compressed / total_original) * 100
        print("\n" + "=" * 60)
        print(f"总计: {len(results)} 张图片")
        print(f"原始大小: {format_size(total_original)}")
        print(f"压缩后: {format_size(total_compressed)}")
        print(f"节省: {total_savings:.1f}% ({format_size(total_original - total_compressed)})")
        print("=" * 60)

    return results


def format_size(bytes_size):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.2f} TB"


def main():
    parser = argparse.ArgumentParser(
        description='本地图片压缩工具 - 支持批量压缩',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 压缩单张图片
  python image_compressor.py -i photo.jpg -o photo_compressed.jpg

  # 压缩到指定质量
  python image_compressor.py -i photo.jpg --quality 70

  # 限制宽度并转换格式
  python image_compressor.py -i photo.png -o photo.webp --max-width 1920

  # 批量压缩目录
  python image_compressor.py --dir ./photos --output-dir ./compressed

  # 递归处理所有子目录
  python image_compressor.py --dir ./photos --recursive --quality 75
        """
    )

    # 输入选项
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--input', help='输入图片文件')
    group.add_argument('--dir', help='输入目录 (批量处理)')

    # 输出选项
    parser.add_argument('-o', '--output', help='输出文件 (单张)')
    parser.add_argument('--output-dir', help='输出目录 (批量)')
    parser.add_argument('--output-format', choices=['JPEG', 'PNG', 'WEBP'],
                        help='输出格式')

    # 压缩选项
    parser.add_argument('-q', '--quality', type=int, default=85,
                        help='压缩质量 1-100 (默认: 85)')
    parser.add_argument('--max-width', type=int, default=0,
                        help='最大宽度 (0=保持原尺寸)')
    parser.add_argument('--max-height', type=int, default=0,
                        help='最大高度 (0=保持原尺寸)')

    # 批量处理选项
    parser.add_argument('--recursive', action='store_true',
                        help='递归处理子目录')
    parser.add_argument('--pattern', default='*',
                        help='文件匹配模式 (默认: *)')

    args = parser.parse_args()

    if args.input:
        # 单张图片处理
        compressor = ImageCompressor(
            quality=args.quality,
            max_width=args.max_width,
            max_height=args.max_height,
            output_format=args.output_format
        )
        result = compressor.compress(args.input, args.output)
        print(f"压缩完成!")
        print(f"原始: {format_size(result['original_size'])}")
        print(f"压缩后: {format_size(result['compressed_size'])}")
        print(f"压缩率: {result['compression_ratio']}")

    elif args.dir:
        # 批量处理
        batch_compress(
            directory=args.dir,
            output_dir=args.output_dir,
            pattern=args.pattern,
            quality=args.quality,
            max_width=args.max_width,
            max_height=args.max_height,
            output_format=args.output_format,
            recursive=args.recursive
        )


if __name__ == '__main__':
    main()
