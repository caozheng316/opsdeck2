# cstcloude - 中国科技云数据胶囊推送工具

基于 Rclone 的交互式 S3 文件管理工具，专为中国科技云数据胶囊设计。

## 功能特性

### 推送模式 (push)
- 将本地文件上传到 S3
- **保留完整的文件夹结构**（最重要）
- 支持两种模式：
  - **COPY 模式**: 只复制新增和修改的文件（安全，推荐）
  - **SYNC 模式**: 镜像同步，远程与本地完全一致
- 断点续传（Rclone 自动处理）
- 进度显示
- 完整性校验（MD5/SHA1）
- 失败重试

### 拉取模式 (pull)
- 从 S3 下载文件到本地
- **保留完整的文件夹结构**
- 全量拉取
- 进度显示
- 默认下载到：`D:\data\抖音知识库`

### 管理模式 (manage)
交互式命令行界面，支持：
- `ls` - 查看文件列表
- `cd` - 切换目录
- `del` - 删除文件
- `deldir` - 删除目录
- `mv` - 移动/重命名
- `cp` - 复制
- `down` - 下载到本地
- `info` - 显示文件/目录信息

## 快速开始

### 1. 安装依赖

```bash
cd cstcloude
pip install -r requirements.txt
```

### 2. 安装 Rclone

Windows 用户：
- 下载地址：https://rclone.org/downloads/
- 安装后确保 `rclone` 命令在 PATH 中

验证安装：
```bash
rclone --version
```

### 3. 配置连接参数

编辑 `config.py` 文件，填入你的 S3 配置：

```python
# 中国科技云数据胶囊配置
S3_ACCESS_KEY_ID = "你的 AccessKey ID"
S3_ACCESS_KEY_SECRET = "你的 AccessKey Secret"
S3_ENDPOINT = "s3.cstcloud.cn"
S3_BUCKET_NAME = "你的 Bucket 名称"  # 从数据胶囊后台获取

# 本地数据源路径
LOCAL_SOURCE_PATH = r"E:\抖音知识库"
```

### 4. 运行

```bash
python main.py
```

## 使用流程

### 首次使用

1. 启动程序后，选择 `3. config` 进行配置向导
2. 输入 AccessKey、Secret、Bucket 等信息
3. 配置完成后，选择 `1. push` 开始推送

### 推送文件

1. 选择 `1. push` 推送模式
2. 选择推送模式：
   - **COPY 模式**（推荐）：只上传新增和修改的文件，不会删除远程文件
   - **SYNC 模式**：镜像同步，远程会与本地完全一致（会删除远程多出的文件）
3. 确认后开始推送
4. 推送完成后可选择进行完整性校验

### 拉取文件

1. 选择 `2. pull` 拉取模式
2. 确认拉取
3. 文件会下载到 `D:\data\抖音知识库`

### 管理文件

1. 选择 `2. manage` 进入管理模式
2. 使用类似 FTP 的命令管理文件：

```
[/]$ ls              # 列出文件
[/]$ cd 目录名        # 进入目录
[/]$ cd ..           # 返回上级
[/]$ del 文件名.md    # 删除文件
[/]$ mv 旧名 新名     # 重命名
[/]$ down 文件.md    # 下载到本地
[/]$ help            # 查看帮助
[/]$ quit            # 退出
```

## 配置说明

### config.py 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `S3_ACCESS_KEY_ID` | AccessKey ID | 必填 |
| `S3_ACCESS_KEY_SECRET` | AccessKey Secret | 必填 |
| `S3_ENDPOINT` | S3 端点 | s3.cstcloud.cn |
| `S3_BUCKET_NAME` | Bucket 名称 | 必填 |
| `LOCAL_SOURCE_PATH` | 本地数据源路径 | E:\抖音知识库 |
| `RCLONE_REMOTE_NAME` | Rclone 配置名称 | mywork |
| `MAX_RETRIES` | 最大重试次数 | 3 |
| `RETRY_DELAY` | 重试间隔（秒） | 2 |
| `ENABLE_CHECKSUM` | 启用完整性校验 | True |

## 常见问题

### Q: 如何获取 Bucket 名称？
A: 登录中国科技云数据胶囊 → 我的数据 → 选择数据集 → S3 访问管理 → 查看 Bucket 信息

### Q: 推送中断了怎么办？
A: 重新执行推送即可，Rclone 会自动断点续传

### Q: 如何确保文件结构一致？
A: 工具会自动保留本地文件夹结构，远程路径与本地完全一致

### Q: 推送速度太慢？
A: 可以尝试：
1. 检查网络连接
2. 使用 SYNC 模式（只传差异）
3. 联系数据胶囊技术支持确认带宽限制

## 技术栈

- Python 3.8+
- Rclone（底层引擎）
- tqdm（进度条）
- colorama（彩色输出）

## 许可证

MIT License
