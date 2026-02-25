# 图片压缩工具

类似 ImagesTool 的本地图片压缩工具，完全在本地运行，不会上传任何文件。

## 安装依赖

```bash
pip install -r requirements.txt
```

或单独安装：

```bash
pip install Pillow pillow-heif
```

## 使用方法

### 压缩单张图片

```bash
# 基本用法
python image_compressor.py -i input.jpg -o output.jpg

# 指定压缩质量 (1-100, 越小压缩越多)
python image_compressor.py -i photo.jpg -o photo_small.jpg --quality 70

# 限制图片宽度（保持比例）
python image_compressor.py -i photo.jpg -o photo_1920.jpg --max-width 1920

# 转换格式
python image_compressor.py -i photo.png -o photo.webp --output-format WEBP
```

### 批量压缩目录

```bash
# 压缩整个目录
python image_compressor.py --dir ./photos --output-dir ./compressed

# 递归处理子目录
python image_compressor.py --dir ./photos --output-dir ./compressed --recursive

# 指定质量和尺寸限制
python image_compressor.py --dir ./photos --quality 75 --max-width 1920
```

## 压缩参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-q, --quality` | 压缩质量 1-100 | 85 |
| `--max-width` | 最大宽度 (0=保持原尺寸) | 0 |
| `--max-height` | 最大高度 (0=保持原尺寸) | 0 |
| `--output-format` | 输出格式 (JPEG/PNG/WEBP) | 保持原格式 |

## 支持的格式

- JPG/JPEG
- PNG
- WebP
- BMP
- TIFF
- HEIC/HEIF (需要 pillow-heif)

## 压缩技巧

1. **JPG/WebP**: 使用 `--quality` 参数控制压缩率
   - 80-85: 高质量，几乎无损
   - 60-75: 平衡质量和大小
   - 40-60: 高压缩率，适合网页

2. **PNG**: 使用较低的质量值增加压缩级别
   - PNG 压缩使用 compress_level 参数

3. **组合使用**: 限制尺寸 + 压缩质量效果最好
   ```bash
   python image_compressor.py -i photo.jpg --quality 75 --max-width 1920
   ```
