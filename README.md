# OpsDeck2

重构后的独立工具集，每个 Python 脚本都可以独立运行，无需外部依赖。

## 📁 项目结构

```
opsdeck2/
├── common/                          # 原始代码参考库（只读）
│   └── _original_code_reference/
│       ├── ach/                     # ACH 自动化脚本
│       ├── api4/                    # API4 接口封装
│       ├── jimeng/                  # 即梦相关
│       └── xiumi/                   # 秀米相关
│
├── banana/                          # Banana 图片处理工具
│   ├── CT_FILE.py                   # 单张图片处理
│   └── CT_DIR.py                    # 批量目录处理
│
├── shangcheng/                      # 商城工具
│   ├── 1_savexiumi.py              # 秀米网页截图
│   ├── 2_poster_background_extractor.py
│   ├── 3_jiage.py
│   └── 4_shangjia.py
│
└── gongzhonghao/                    # 公众号工具
    ├── 1_lvyou_txt.py              # 旅游文章生成
    ├── 2_xhs_img.py
    ├── 3_image_restyle.py          # 图片风格重构
    ├── 4_airport_img_generator.py
    ├── 5_generate_html.py
    ├── 6_copy_to_clipboard.py
    └── 7_copy_html_clipboard.py
```

## ✨ 特点

- ✅ **完全独立** — 每个 `.py` 文件都可以单独运行
- ✅ **自动配置** — 首次运行自动生成 JSON 配置文件
- ✅ **代码参考** — 保留原始 common 代码供参考

## 🚀 使用方法

每个工具都可以直接运行：

```bash
# Banana 工具
python banana/CT_FILE.py      # 单张图片处理
python banana/CT_DIR.py       # 批量目录处理

# 公众号工具
python gongzhonghao/1_lvyou_txt.py       # 旅游文章生成
python gongzhonghao/3_image_restyle.py    # 图片风格重构

# 商城工具
python shangcheng/1_savexiumi.py  # 秀米网页截图
```

## 📦 依赖安装

```bash
pip install playwright pillow requests opencv-python qrcode pyzbar pyperclip
playwright install
```

## 📄 许可证

本项目仅供个人学习使用。
