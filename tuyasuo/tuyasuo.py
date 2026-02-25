#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片压缩工具 - 拖拽即压缩
用法: 运行脚本后输入或拖拽图片/文件夹路径，按回车执行压缩
输出: 压缩后的图片保存在原文件所在目录，文件名加 _ys 后缀

依赖安装:
pip install Pillow
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageOps
import io

# ============== 内嵌参数 ==============
QUALITY = 85          # 压缩质量 (1-100)
MAX_WIDTH = 0         # 最大宽度，0 表示保持原尺寸
MAX_HEIGHT = 0        # 最大高度，0 表示保持原尺寸
PRESERVE_EXIF = True  # 是否保留 EXIF 信息
# =====================================

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


def format_size(bytes_size):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.2f} TB"


class ImageCompressor:
    """图片压缩器 - 核心压缩逻辑（与 common/imgtools/image_compressor.py 一致）"""

    def __init__(self, quality=85, max_width=0, max_height=0, preserve_exif=True):
        self.quality = quality
        self.max_width = max_width
        self.max_height = max_height
        self.preserve_exif = preserve_exif

    def compress(self, input_path):
        """
        压缩单张图片，保存到原目录，文件名加 _ys 后缀

        Args:
            input_path: 输入图片路径

        Returns:
            dict: 包含原始大小、压缩后大小、压缩率等信息
        """
        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在: {input_path}")

        if input_path.suffix.lower() not in SUPPORTED_FORMATS:
            raise ValueError(f"不支持的格式: {input_path.suffix}")

        # 构建输出路径: 原目录/原文件名_ys.后缀
        output_path = input_path.parent / f"{input_path.stem}_ys{input_path.suffix}"

        # 获取原始文件大小
        original_size = input_path.stat().st_size

        # 打开图片
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

        # 确定输出格式（根据输入后缀）
        save_format = self._get_save_format(input_path.suffix)

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

    def _get_save_format(self, suffix):
        """确定保存格式"""
        suffix = suffix.lower()
        if suffix in ('.jpg', '.jpeg'):
            return 'JPEG'
        elif suffix == '.png':
            return 'PNG'
        elif suffix == '.webp':
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


def collect_images(path_str):
    """
    收集所有图片文件（支持文件和文件夹）

    Args:
        path_str: 传入的路径字符串

    Returns:
        list: 图片文件路径列表
    """
    image_files = []

    # 去除可能的引号
    path_str = path_str.strip().strip('"').strip("'")

    if not path_str:
        return image_files

    path = Path(path_str)

    if not path.exists():
        return image_files

    if path.is_file():
        # 单个文件
        if path.suffix.lower() in SUPPORTED_FORMATS:
            image_files.append(path)
    elif path.is_dir():
        # 文件夹：递归查找图片
        for ext in SUPPORTED_FORMATS:
            image_files.extend(path.rglob(f"*{ext}"))

    # 去重并排序
    image_files = sorted(set(image_files))
    return image_files


def safe_print(text):
    """安全打印，处理编码问题"""
    try:
        print(text)
    except UnicodeEncodeError:
        # 尝试替换无法编码的字符
        print(text.encode('gbk', errors='replace').decode('gbk'))


def main():
    """主函数"""
    # 设置控制台编码
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass

    safe_print("=" * 50)
    safe_print("图片压缩工具 - 输入或拖拽路径后按回车")
    safe_print("=" * 50)
    safe_print(f"支持格式: {', '.join(sorted(SUPPORTED_FORMATS))}")
    safe_print(f"压缩质量: {QUALITY}")
    safe_print("输入路径（支持文件或文件夹）: ")

    # 获取用户输入
    try:
        user_input = input()
    except:
        sys.exit(0)

    # 收集所有图片文件
    image_files = collect_images(user_input)

    if not image_files:
        safe_print("\n未找到支持的图片文件，请检查路径是否正确")
        safe_print(f"支持格式: {', '.join(sorted(SUPPORTED_FORMATS))}")
        safe_print("\n按回车键退出...")
        try:
            input()
        except:
            pass
        sys.exit(0)

    # 创建压缩器
    compressor = ImageCompressor(
        quality=QUALITY,
        max_width=MAX_WIDTH,
        max_height=MAX_HEIGHT,
        preserve_exif=PRESERVE_EXIF
    )

    # 开始压缩
    success_count = 0
    fail_count = 0
    total_original = 0
    total_compressed = 0

    safe_print(f"\n找到 {len(image_files)} 个图片，开始压缩...")
    safe_print("-" * 50)

    for img_path in image_files:
        try:
            result = compressor.compress(img_path)
            success_count += 1
            total_original += result['original_size']
            total_compressed += result['compressed_size']
            safe_print(f"[OK] {img_path.name}")
            safe_print(f"     {format_size(result['original_size'])} -> {format_size(result['compressed_size'])} ({result['compression_ratio']})")
            safe_print(f"     -> {result['output_path']}")
        except Exception as e:
            fail_count += 1
            safe_print(f"[FAIL] {img_path.name}: {e}")

    # 统计
    safe_print("-" * 50)
    safe_print(f"压缩完成! 成功: {success_count}, 失败: {fail_count}")
    if success_count > 0:
        total_ratio = (1 - total_compressed / total_original) * 100
        safe_print(f"原始总大小: {format_size(total_original)}")
        safe_print(f"压缩后总大小: {format_size(total_compressed)}")
        safe_print(f"总压缩率: {total_ratio:.1f}%")
    safe_print("=" * 50)

    safe_print("\n按回车键退出...")
    try:
        input()
    except:
        pass


if __name__ == '__main__':
    main()