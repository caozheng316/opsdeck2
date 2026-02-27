# imgtool - 图片工具合集

包含两个实用图片处理工具：
- **imgzip** - 图片压缩工具
- **imgjion** - 图片纵向拼接工具

---

## 快速开始

### 步骤 1：复制文件夹

将整个 `imgtool` 文件夹复制到目标电脑的任何位置。

### 步骤 2：一键安装

双击运行 `setup.bat`

这将自动：
1. 检查 Python 环境
2. 安装 Pillow 库
3. 安装右键菜单

### 步骤 3：开始使用

- **压缩图片**：右键单个图片 → "用 imgzip 压缩"
- **压缩文件夹**：右键文件夹 → "用 imgzip 压缩此文件夹图片"
- **拼接图片**：文件夹空白处右键 → "用 imgjion 拼接图片"

---

## 文件清单

| 文件名 | 说明 |
|--------|------|
| `imgjion.py` | 拼接工具主程序 |
| `imgjion_drop.bat` | 拼接工具启动脚本 |
| `imgzip.py` | 压缩工具主程序 |
| `imgzip.bat` | 压缩工具启动脚本 |
| `setup.bat` | 一键安装脚本 ⭐ |
| `install_context_menu.bat` | 安装右键菜单 |
| `uninstall_context_menu.bat` | 卸载右键菜单 |
| `requirements.txt` | Python 依赖 |
| `README.md` | 本文档 |

---

## 工具一：imgjion 图片拼接

### 功能
- 智能识别"前缀 + 序号"格式的文件名
- 自动分组相同前缀的图片
- 自然排序：1, 2, 3... 9, 10, 11
- 输出文件名自动匹配原文件前缀

### 文件名规则
| 格式示例 | 说明 |
|----------|------|
| `详情_01.jpg`, `详情_02.jpg` | 中文前缀 + 下划线 + 数字 |
| `image1.png`, `image2.png` | 英文前缀 + 数字 |
| `pic-001.jpg`, `pic-002.jpg` | 前缀 + 连字符 + 数字 |

### 输出示例
```
详情_01.jpg + 详情_02.jpg + 详情_03.jpg → 详情_拼接.jpg
主图_1.jpg + 主图_2.jpg → 主图_拼接.jpg
```

### 命令行用法
```bash
# 文件夹扫描模式
python imgjion.py --folder ./images -i

# 指定文件
python imgjion.py 详情_01.jpg 详情_02.jpg 详情_03.jpg
```

---

## 工具二：imgzip 图片压缩

### 功能
- 压缩 JPEG、PNG、WebP 格式
- PNG 自动转为 JPEG 格式压缩
- 保留 EXIF 信息
- 支持覆盖/另存两种模式

### 命令行用法
```bash
# 单张图片
python imgzip.py 图片.jpg -q 85

# 整个文件夹
python imgzip.py ./photos -r
```

### 参数
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-q, --quality` | 压缩质量 1-100 | 85 |
| `-r, --recursive` | 递归处理子文件夹 | 否 |

---

## 右键菜单说明

### 安装后的菜单项

| 右键位置 | 菜单项 | 功能 |
|----------|--------|------|
| 图片文件 | "用 imgzip 压缩" | 压缩单张图片 |
| 文件夹 | "用 imgzip 压缩此文件夹图片" | 压缩文件夹内所有图片 |
| 文件夹空白处 | "用 imgjion 拼接图片" | 扫描并拼接图片 |

### 卸载右键菜单

双击运行 `uninstall_context_menu.bat`

---

## 移植到其他电脑

1. 复制整个 `imgtool` 文件夹
2. 运行 `setup.bat` 一键安装
3. 完成！

---

## 注意事项

1. **Python 环境**：需要安装 Python 3.6+ 和 Pillow 库
2. **路径空格**：支持路径中包含空格
3. **中文支持**：完全支持中文文件名
4. **移动位置**：移动文件夹后需重新运行 `setup.bat` 或 `install_context_menu.bat`

---

## 常见问题

**Q: 右键菜单没有显示？**
A: 双击运行 `setup.bat` 或 `install_context_menu.bat` 安装。

**Q: 提示找不到 Python？**
A: 确保 Python 已安装并添加到系统 PATH。

**Q: 拼接结果不对？**
A: 确保文件名符合"前缀 + 序号"格式，如 `详情_01.jpg`、`详情_02.jpg`。
