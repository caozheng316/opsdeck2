#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cstcloude - S3/OSS 数据推送工具
基于 Rclone 的交互式文件管理工具
"""

import sys
import os
import subprocess
import json
from typing import List, Dict, Optional, Tuple

from colorama import init, Fore, Style

# ==================== 配置区域 ====================
# S3/OSS 配置信息（中国科技云数据胶囊）
S3_ACCESS_KEY_ID = "AKIARLBCPEX37XPHGW8I"
S3_ACCESS_KEY_SECRET = "3Y6121O8DTHJ050DKAXXXCDZ4I9CQ2UILJB868EW"
S3_ENDPOINT = "s3.cstcloud.cn"
S3_BUCKET_NAME = "c9848a8f343244bdaacb1324ec21d24a"
S3_USE_SSL = True
RCLONE_REMOTE_NAME = "mywork"

# 本地数据源路径
LOCAL_SOURCE_PATH = r"E:\抖音知识库"
PULL_DEST_PATH = r"D:\data\抖音知识库"

# 重试和校验配置
MAX_RETRIES = 3
RETRY_DELAY = 2
ENABLE_CHECKSUM = True
# =================================================


# ==================== Rclone 封装 ====================
class RcloneWrapper:
    """Rclone 命令封装类"""

    def __init__(self):
        self.remote_name = RCLONE_REMOTE_NAME
        self.bucket = S3_BUCKET_NAME

    def is_installed(self) -> bool:
        try:
            result = subprocess.run(["rclone", "--version"], capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def configure_remote(self, access_key: str, secret_key: str, bucket: str) -> bool:
        try:
            result = subprocess.run(["rclone", "config", "file"], capture_output=True, text=True, timeout=10)
            config_path = result.stdout.strip().replace("Configuration file is at: ", "")

            existing_config = ""
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing_config = f.read()

            remote_section = f"[{self.remote_name}]"
            if remote_section in existing_config:
                lines = existing_config.split('\n')
                new_lines = []
                skip_section = False
                for line in lines:
                    if line.strip().startswith('[') and line.strip().endswith(']'):
                        skip_section = (line.strip() == remote_section)
                    if not skip_section:
                        new_lines.append(line)
                existing_config = '\n'.join(new_lines)

            new_config = f"""{existing_config}
[{self.remote_name}]
type = s3
provider = Other
access_key_id = {access_key}
secret_access_key = {secret_key}
endpoint = https://s3.cstcloud.cn
region = us-east-1
location_constraint =
acl = private
no_check_bucket = true
force_path_style = true
"""
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(new_config)
            print(f"[OK] 配置文件已更新：{config_path}")
            return True
        except Exception as e:
            print(f"[FAIL] 配置失败：{e}")
            return False

    def is_remote_configured(self) -> bool:
        try:
            result = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True, timeout=10)
            return f"{self.remote_name}:" in result.stdout
        except Exception:
            return False

    def test_connection(self) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                ["rclone", "lsf", f"{self.remote_name}:{self.bucket}", "--max-depth", "1"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return True, "连接成功"
            return False, result.stderr
        except subprocess.TimeoutExpired:
            return False, "连接超时"
        except Exception as e:
            return False, str(e)

    def sync(self, source: str, dest: str, dry_run: bool = False, include_pattern: str = None) -> Tuple[bool, str]:
        args = ["rclone", "sync", source, dest, "-v", "--progress", "--create-empty-src-dirs", "--s3-directory-markers"]
        if include_pattern:
            # 使用 --include 参数：只包含 *.md 文件
            args.extend(["--include", "*.md"])
        if dry_run:
            args.append("--dry-run")
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=600)
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "同步超时"
        except Exception as e:
            return False, str(e)

    def copy(self, source: str, dest: str, include_pattern: str = None, exclude_other: bool = True) -> Tuple[bool, str]:
        args = ["rclone", "copy", source, dest, "-v", "--progress", "--create-empty-src-dirs", "--s3-directory-markers"]
        if include_pattern:
            # 使用 --include 参数：只包含 *.md 文件
            args.extend(["--include", "*.md"])
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=600)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def ls(self, remote_path: str, recursive: bool = True) -> List[Dict]:
        args = ["rclone", "lsf", remote_path]
        if recursive:
            args.append("-R")
        args.extend(["--files-only", "--json"])
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return json.loads(result.stdout)
            return []
        except Exception:
            return []

    def lsd(self, remote_path: str) -> List[Dict]:
        args = ["rclone", "lsf", remote_path, "--dirs-only", "--json"]
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return json.loads(result.stdout)
            return []
        except Exception:
            return []

    def delete(self, remote_path: str) -> Tuple[bool, str]:
        try:
            result = subprocess.run(["rclone", "delete", "-v", remote_path], capture_output=True, text=True, timeout=300)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def purge(self, remote_path: str) -> Tuple[bool, str]:
        try:
            result = subprocess.run(["rclone", "purge", "-v", remote_path], capture_output=True, text=True, timeout=300)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def moveto(self, source: str, dest: str) -> Tuple[bool, str]:
        try:
            result = subprocess.run(["rclone", "moveto", "-v", source, dest], capture_output=True, text=True, timeout=300)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def copyto(self, source: str, dest: str) -> Tuple[bool, str]:
        try:
            result = subprocess.run(["rclone", "copyto", "-v", source, dest], capture_output=True, text=True, timeout=300)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def download(self, source: str, dest: str) -> Tuple[bool, str]:
        args = ["rclone", "copy", source, dest, "-v", "--progress"]
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=None)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def size(self, remote_path: str) -> Optional[Dict]:
        try:
            result = subprocess.run(["rclone", "size", "--json", remote_path], capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return json.loads(result.stdout)
            return None
        except Exception:
            return None

    def check(self, source: str, dest: str) -> Tuple[bool, str]:
        try:
            result = subprocess.run(["rclone", "check", source, dest, "--download", "-v"], capture_output=True, text=True, timeout=300)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def mount(self, mount_point: str, background: bool = True) -> Tuple[bool, str]:
        """
        挂载 S3 为本地磁盘
        Args:
            mount_point: 本地挂载点路径
            background: 是否在后台运行
        """
        args = [
            "rclone", "mount",
            f"{self.remote_name}:{self.bucket}",
            mount_point,
            "--vfs-cache-mode", "full",
            "--allow-non-empty",
            "--s3-directory-markers",
            "--dir-cache-time", "5s",
            "--log-level", "INFO",
        ]
        try:
            if background:
                # 在 Windows 上，使用 start /B 后台运行
                if os.name == 'nt':
                    import subprocess
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    result = subprocess.Popen(
                        args,
                        startupinfo=startupinfo,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    return True, f"挂载已启动 (PID: {result.pid})"
                else:
                    # Unix/Linux/Mac 后台运行
                    import subprocess
                    result = subprocess.Popen(
                        args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        start_new_session=True
                    )
                    return True, f"挂载已启动 (PID: {result.pid})"
            else:
                # 前台运行（阻塞）
                result = subprocess.run(args, capture_output=True, text=True, timeout=None)
                return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "挂载超时"
        except Exception as e:
            return False, str(e)

    def umount(self, mount_point: str) -> Tuple[bool, str]:
        """
        卸载挂载点
        Args:
            mount_point: 本地挂载点路径
        """
        try:
            if os.name == 'nt':
                # Windows: 使用 rclone umount 命令
                result = subprocess.run(
                    ["rclone", "umount", mount_point],
                    capture_output=True, text=True, timeout=30
                )
            else:
                # Unix/Linux/Mac: 使用 fusermount 或 umount
                result = subprocess.run(
                    ["fusermount", "-u", mount_point],
                    capture_output=True, text=True, timeout=30
                )
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)


# ==================== 功能模块 ====================
class PushModule:
    """推送模块 - 将本地文件上传到 S3"""

    def __init__(self):
        self.rclone = RcloneWrapper()
        self.source_path = LOCAL_SOURCE_PATH
        self.bucket = S3_BUCKET_NAME
        self.remote_name = RCLONE_REMOTE_NAME

    def find_md_files(self) -> List[str]:
        md_files = []
        for root, dirs, files in os.walk(self.source_path):
            for file in files:
                if file.endswith('.md'):
                    md_files.append(os.path.join(root, file))
        return sorted(md_files)

    def format_size(self, size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

    def check_before_push(self) -> Tuple[bool, str]:
        print("\n【推送前检查】")
        if not os.path.exists(self.source_path):
            return False, f"本地路径不存在：{self.source_path}"
        print(f"[OK] 本地路径：{self.source_path}")
        if not self.bucket:
            return False, "Bucket 名称未配置"
        print(f"[OK] Bucket: {self.bucket}")
        if not self.rclone.is_remote_configured():
            return False, f"Rclone 远程未配置：{self.remote_name}"
        print(f"[OK] Rclone 远程已配置：{self.remote_name}")
        print("  测试连接中...")
        success, msg = self.rclone.test_connection()
        if not success:
            return False, f"连接测试失败：{msg}"
        print("[OK] 连接测试成功")
        return True, "检查通过"

    def push(self, use_copy: bool = True) -> bool:
        success, msg = self.check_before_push()
        if not success:
            print(f"\n[FAIL] {msg}")
            return False
        print(f"\n[OK] {msg}")

        print("\n【扫描文件】")
        md_files = self.find_md_files()
        if not md_files:
            print("  未找到任何 .md 文件")
            print("\n[SKIP] 跳过推送（没有需要上传的文件）")
            return True
        print(f"[OK] 找到 {len(md_files)} 个 .md 文件")
        total_size = sum(os.path.getsize(f) for f in md_files if os.path.exists(f))
        print(f"[OK] 总大小：{self.format_size(total_size)}")

        print("\n【文件预览】")
        for i, f in enumerate(md_files[:5]):
            rel_path = os.path.relpath(f, self.source_path)
            size = os.path.getsize(f)
            print(f"  {i+1}. {rel_path} ({self.format_size(size)})")
        if len(md_files) > 5:
            print(f"  ... 还有 {len(md_files) - 5} 个文件")

        print("\n【推送模式】")
        if use_copy:
            print("  模式：COPY (复制新增和修改的文件，不删除远程文件)")
        else:
            print("  模式：SYNC (镜像同步，远程会与本地完全一致)")

        confirm = input("\n确认开始推送？(y/n): ").strip().lower()
        if confirm != 'y':
            print("  已取消")
            return False

        dest_base = f"{self.remote_name}:{self.bucket}"
        print("\n【开始推送】")
        print("  请稍候，这可能需要一些时间...")
        print("  按 Ctrl+C 可中断推送")
        print()

        if use_copy:
            success, output = self.rclone.copy(self.source_path, dest_base, include_pattern="*.md")
        else:
            success, output = self.rclone.sync(self.source_path, dest_base, include_pattern="*.md")

        print("\n【推送结果】")
        if success:
            print("[OK] 推送完成!")
        else:
            print("[FAIL] 推送失败")
        print("\n" + "-" * 40)
        print(output[-500:] if len(output) > 500 else output)
        print("-" * 40)

        if success and ENABLE_CHECKSUM:
            check = input("\n是否进行完整性校验？(y/n): ").strip().lower()
            if check == 'y':
                print("\n【完整性校验】")
                check_success, check_msg = self.rclone.check(self.source_path, dest_base)
                if check_success:
                    print("[OK] 完整性校验通过")
                else:
                    print(f"  校验结果：{check_msg[:200]}")

        print("\n按回车键返回主菜单...")
        input()
        return success

    def run(self):
        print("=" * 50)
        print("     推送模式")
        print("=" * 50)
        print("\n请选择推送模式：")
        print("  1. COPY 模式 - 复制新增和修改的文件（推荐，安全）")
        print("  2. SYNC 模式 - 镜像同步（远程会与本地完全一致）")
        choice = input("\n选择 [1-2]: ").strip()
        self.push(use_copy=(choice != '2'))


class PullModule:
    """拉取模块 - 从 S3 下载文件到本地"""

    def __init__(self):
        self.rclone = RcloneWrapper()
        self.dest_path = PULL_DEST_PATH
        self.bucket = S3_BUCKET_NAME
        self.remote_name = RCLONE_REMOTE_NAME

    def format_size(self, size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

    def check_before_pull(self) -> Tuple[bool, str]:
        print("\n【拉取前检查】")
        if not self.bucket:
            return False, "Bucket 名称未配置"
        print(f"[OK] Bucket: {self.bucket}")
        if not self.rclone.is_remote_configured():
            return False, f"Rclone 远程未配置：{self.remote_name}"
        print(f"[OK] Rclone 远程已配置：{self.remote_name}")
        print("  测试连接中...")
        success, msg = self.rclone.test_connection()
        if not success:
            return False, f"连接测试失败：{msg}"
        print("[OK] 连接测试成功")
        if os.path.exists(self.dest_path):
            print(f"[OK] 目标目录存在：{self.dest_path}")
        else:
            print(f"  目标目录不存在，将创建：{self.dest_path}")
            try:
                os.makedirs(self.dest_path, exist_ok=True)
                print("[OK] 目录创建成功")
            except Exception as e:
                return False, f"无法创建目录：{e}"
        return True, "检查通过"

    def pull(self) -> bool:
        success, msg = self.check_before_pull()
        if not success:
            print(f"\n[FAIL] {msg}")
            return False
        print(f"\n[OK] {msg}")

        print("\n【获取远程信息】")
        stats = self.rclone.size(f"{self.remote_name}:{self.bucket}") or {'count': 0, 'bytes': 0}
        print(f"[OK] 远程文件数：{stats.get('count', 0)}")
        print(f"[OK] 远程总大小：{self.format_size(stats.get('bytes', 0))}")
        if stats.get('count', 0) == 0:
            print("  远程没有文件，无需拉取")
            return True

        print("\n【拉取目标】")
        print(f"  源：{self.remote_name}:{self.bucket}/")
        print(f"  目标：{self.dest_path}")

        confirm = input("\n确认开始拉取？(y/n): ").strip().lower()
        if confirm != 'y':
            print("  已取消")
            return False

        print("\n【开始拉取】")
        print("  请稍候，这可能需要一些时间...")
        print("  按 Ctrl+C 可中断拉取")

        success, output = self.rclone.download(f"{self.remote_name}:{self.bucket}", self.dest_path)

        print("\n【拉取结果】")
        if success:
            print("[OK] 拉取完成!")
            print(f"[OK] 文件已保存到：{self.dest_path}")
        else:
            print("[FAIL] 拉取失败")
        print("\n" + "-" * 40)
        print(output[-500:] if len(output) > 500 else output)
        print("-" * 40)

        if success:
            local_count = sum(1 for _, _, files in os.walk(self.dest_path) for _ in files)
            local_size = sum(os.path.getsize(os.path.join(root, f)) for root, _, files in os.walk(self.dest_path) for f in files)
            print("\n【本地统计】")
            print(f"[OK] 本地文件数：{local_count}")
            print(f"[OK] 本地总大小：{self.format_size(local_size)}")

        print("\n按回车键返回主菜单...")
        input()
        return success

    def run(self):
        print("=" * 50)
        print("     拉取模式")
        print("=" * 50)
        print(f"\n从 S3 全量拉取文件到本地目录")
        print(f"目标路径：{self.dest_path}")
        self.pull()


class MountModule:
    """挂载模块 - 挂载 S3 为本地磁盘"""

    def __init__(self):
        self.rclone = RcloneWrapper()
        self.bucket = S3_BUCKET_NAME
        self.remote_name = RCLONE_REMOTE_NAME
        # Windows 默认挂载点
        self.default_mount_point = r"Z:"
        if os.name != 'nt':
            self.default_mount_point = "/tmp/rclone_mount"

    def check_before_mount(self) -> Tuple[bool, str]:
        print("\n【挂载前检查】")
        if not self.bucket:
            return False, "Bucket 名称未配置"
        print(f"[OK] Bucket: {self.bucket}")
        if not self.rclone.is_remote_configured():
            return False, f"Rclone 远程未配置：{self.remote_name}"
        print(f"[OK] Rclone 远程已配置：{self.remote_name}")
        print("  测试连接中...")
        success, msg = self.rclone.test_connection()
        if not success:
            return False, f"连接测试失败：{msg}"
        print("[OK] 连接测试成功")
        return True, "检查通过"

    def mount(self) -> bool:
        success, msg = self.check_before_mount()
        if not success:
            print(f"\n[FAIL] {msg}")
            return False
        print(f"\n[OK] {msg}")

        print("\n【挂载设置】")
        mount_point = input(f"请输入挂载点路径 [默认：{self.default_mount_point}]: ").strip() or self.default_mount_point
        print(f"  挂载点：{mount_point}")
        print(f"  远程：{self.remote_name}:{self.bucket}/")

        print("\n【挂载选项】")
        print("  1. 后台挂载（推荐，持续运行）")
        print("  2. 前台挂载（测试用，按 Ctrl+C 停止）")
        mode = input("\n选择 [1-2]: ").strip() or '1'
        background = (mode == '1')

        if not background:
            print("\n【提示】")
            print("  前台模式将阻塞终端，按 Ctrl+C 可停止挂载")

        confirm = input("\n确认开始挂载？(y/n): ").strip().lower()
        if confirm != 'y':
            print("  已取消")
            return False

        print("\n【开始挂载】")
        success, msg = self.rclone.mount(mount_point, background=background)

        if success:
            print("[OK] 挂载成功!")
            if background:
                print(f"[OK] 挂载点：{mount_point}")
                print("  现在可以像使用本地磁盘一样访问云端文件")
                print("\n  卸载命令：rclone umount " + mount_point)
        else:
            print(f"[FAIL] 挂载失败：{msg}")

        print("\n按回车键返回主菜单...")
        input()
        return success

    def run(self):
        print("=" * 50)
        print("     挂载模式")
        print("=" * 50)
        print()
        print("将 S3 存储桶挂载为本地磁盘")
        print("支持实时读写，自动同步到云端")
        self.mount()


class ManageModule:
    """管理模块 - 查看、删除、移动、复制 S3 文件"""

    def __init__(self):
        self.rclone = RcloneWrapper()
        self.bucket = S3_BUCKET_NAME
        self.remote_name = RCLONE_REMOTE_NAME
        self.current_path = ""

    def get_remote_path(self, path: str = "") -> str:
        base = f"{self.remote_name}:{self.bucket}"
        return f"{base}/{path}" if path else base

    def format_size(self, size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def browse(self):
        print(f"\n【当前路径】 {self.current_path or '/'}")
        dirs = self.rclone.lsd(self.get_remote_path(self.current_path))
        files = self.rclone.ls(self.get_remote_path(self.current_path), recursive=False)

        if dirs:
            print("-" * 70)
            print(f"  {'目录名':<60}")
            print("-" * 70)
            for d in dirs:
                print(f"  [DIR] {d.get('Name', d.get('path', '未知'))}")
            print("-" * 70)
            print(f"  共 {len(dirs)} 个目录")

        print()
        if not files:
            print("  (空目录)")
        else:
            print("-" * 70)
            print(f"  {'文件名':<50} {'大小':>15}")
            print("-" * 70)
            for f in files:
                name = f.get('Name', f.get('path', '未知'))
                size = f.get('Size', 0)
                print(f"  {name:<50} {self.format_size(size):>15}")
            print("-" * 70)
            print(f"  共 {len(files)} 个文件")

    def cd(self, path: str) -> bool:
        if path == "..":
            if self.current_path:
                self.current_path = '/'.join(self.current_path.split('/')[:-1])
            return True
        elif path == "/":
            self.current_path = ""
            return True
        else:
            dirs = self.rclone.lsd(self.get_remote_path(self.current_path))
            for d in dirs:
                if d.get('Name') == path:
                    self.current_path = f"{self.current_path}/{path}" if self.current_path else path
                    return True
            print(f"目录不存在：{path}")
            return False

    def delete(self, path: str) -> bool:
        if not path:
            print("请输入文件路径")
            return False
        remote_path = self.get_remote_path(path)
        print(f"正在删除：{remote_path}")
        if input("确认删除？(y/n): ").strip().lower() != 'y':
            print("已取消")
            return False
        success, msg = self.rclone.delete(remote_path)
        print(f"[OK] 删除成功" if success else f"[FAIL] 删除失败：{msg}")
        return success

    def delete_dir(self, path: str) -> bool:
        if not path:
            print("请输入目录路径")
            return False
        remote_path = self.get_remote_path(path)
        print(f"警告：将删除目录及其所有内容：{remote_path}")
        if input("确认删除？输入目录名确认：").strip() != path.split('/')[-1]:
            print("已取消")
            return False
        success, msg = self.rclone.purge(remote_path)
        print(f"[OK] 删除成功" if success else f"[FAIL] 删除失败：{msg}")
        return success

    def move(self, source: str, dest: str) -> bool:
        if not source or not dest:
            print("请输入源路径和目标路径")
            return False
        print(f"移动：{source} -> {dest}")
        if input("确认移动？(y/n): ").strip().lower() != 'y':
            print("已取消")
            return False
        success, msg = self.rclone.moveto(self.get_remote_path(source), self.get_remote_path(dest))
        print(f"[OK] 移动成功" if success else f"[FAIL] 移动失败：{msg}")
        return success

    def copy(self, source: str, dest: str) -> bool:
        if not source or not dest:
            print("请输入源路径和目标路径")
            return False
        print(f"复制：{source} -> {dest}")
        if input("确认复制？(y/n): ").strip().lower() != 'y':
            print("已取消")
            return False
        success, msg = self.rclone.copyto(self.get_remote_path(source), self.get_remote_path(dest))
        print(f"[OK] 复制成功" if success else f"[FAIL] 复制失败：{msg}")
        return success

    def download(self, remote_path: str) -> bool:
        if not remote_path:
            print("请输入远程文件路径")
            return False
        local_path = os.path.join(os.getcwd(), "downloads")
        os.makedirs(local_path, exist_ok=True)
        print(f"下载：{remote_path} -> {local_path}")
        print("请稍候...")
        success, msg = self.rclone.download(self.get_remote_path(remote_path), local_path)
        print(f"[OK] 下载成功：{local_path}" if success else f"[FAIL] 下载失败：{msg}")
        return success

    def show_info(self, path: str):
        if not path:
            print("请输入路径")
            return
        remote_path = self.get_remote_path(path)
        print(f"\n【信息】 {path}")
        info = self.rclone.size(remote_path)
        if info:
            print(f"  文件数：{info.get('count', 0)}")
            print(f"  总大小：{self.format_size(info.get('bytes', 0))}")
        else:
            print("  无法获取信息")

    def print_help(self):
        print("\n【管理命令】")
        print("-" * 50)
        print("  ls          - 列出当前目录文件")
        print("  cd <目录>    - 进入目录 (cd .. 返回上级，cd / 返回根目录)")
        print("  del <文件>   - 删除文件")
        print("  deldir <目录> - 删除目录及其内容")
        print("  mv <源> <目标> - 移动文件/目录")
        print("  cp <源> <目标> - 复制文件/目录")
        print("  down <文件>  - 下载文件到本地")
        print("  info <路径>  - 显示文件/目录信息")
        print("  help        - 显示帮助")
        print("  quit/exit   - 退出管理模式")
        print("-" * 50)

    def run_command(self, cmd: str, args: List[str]) -> bool:
        if cmd == 'ls':
            self.browse()
        elif cmd == 'cd':
            self.cd(args[0] if args else "")
        elif cmd == 'del':
            self.delete(args[0] if args else "")
        elif cmd == 'deldir':
            self.delete_dir(args[0] if args else "")
        elif cmd == 'mv':
            self.move(args[0] if len(args) >= 1 else "", args[1] if len(args) >= 2 else "")
        elif cmd == 'cp':
            self.copy(args[0] if len(args) >= 1 else "", args[1] if len(args) >= 2 else "")
        elif cmd == 'down':
            self.download(args[0] if args else "")
        elif cmd == 'info':
            self.show_info(args[0] if args else "")
        elif cmd == 'help':
            self.print_help()
        else:
            print(f"未知命令：{cmd}")
            return False
        return True

    def run(self):
        print("=" * 50)
        print("     管理模式")
        print("=" * 50)
        print()
        if not self.rclone.is_remote_configured():
            print(f"Rclone 远程未配置：{self.remote_name}")
            print("请先在主菜单选择 '4. config' 进行配置")
            return
        if not self.bucket:
            print("Bucket 名称未配置")
            return
        print(f"已连接到：{self.remote_name}:{self.bucket}")
        self.print_help()

        while True:
            try:
                path_display = self.current_path or "/"
                cmd_input = input(f"\n[{path_display}]$ ").strip()
                if not cmd_input:
                    continue
                parts = cmd_input.split()
                cmd = parts[0].lower()
                args = parts[1:]
                if cmd in ['quit', 'exit', 'q']:
                    print("\n返回主菜单")
                    break
                self.run_command(cmd, args)
            except KeyboardInterrupt:
                print("\n已中断")
                continue
            except Exception as e:
                print(f"错误：{e}")


# ==================== 主程序 ====================
def init_colorama():
    init()

def print_banner():
    print("=" * 50)
    print("     cstcloude - S3/OSS 数据推送工具")
    print("=" * 50)
    print()

def print_menu():
    print("\n【主菜单】")
    print("-" * 40)
    print("  1. push   - 推送模式 (上传本地文件到 S3)")
    print("  2. pull   - 拉取模式 (从 S3 下载文件到本地)")
    print("  3. manage - 管理模式 (查看/删除/移动/复制)")
    print("  4. mount  - 挂载模式 (挂载 S3 为本地磁盘)")
    print("  5. config - 配置检查")
    print("  0. 退出")
    print("-" * 40)

def check_environment():
    print("\n【环境检查】")
    rclone = RcloneWrapper()
    if not rclone.is_installed():
        print('[FAIL] Rclone 未安装')
        print('  请先安装 Rclone: https://rclone.org/downloads/')
        return False
    print('[OK] Rclone 已安装')
    if os.path.exists(LOCAL_SOURCE_PATH):
        print('[OK] 本地路径存在')
    else:
        print('[FAIL] 本地路径不存在')
        return False
    if rclone.is_remote_configured():
        print('[OK] Rclone 远程配置已存在')
    else:
        print('[WARN] Rclone 远程未配置')
        print('  将在配置向导中帮你配置')
    return True

def config_wizard():
    print("\n【Rclone 配置向导】")
    rclone = RcloneWrapper()
    if rclone.is_remote_configured():
        print(f"远程 '{RCLONE_REMOTE_NAME}' 已配置")
        if input("是否重新配置？(y/n): ").strip().lower() != 'y':
            return True

    print("\n请按照提示输入 S3/OSS 配置信息：")
    print("(直接回车使用默认值)")

    access_key = input(f"Access Key ID [{S3_ACCESS_KEY_ID[:10]}...]: ").strip() or S3_ACCESS_KEY_ID
    secret_key = input(f"Secret Access Key [{S3_ACCESS_KEY_SECRET[:10]}...]: ").strip() or S3_ACCESS_KEY_SECRET
    endpoint = input(f"Endpoint [{S3_ENDPOINT}]: ").strip() or S3_ENDPOINT
    bucket = input(f"Bucket Name [{S3_BUCKET_NAME}]: ").strip() or S3_BUCKET_NAME

    if not bucket:
        print("Bucket 名称不能为空!")
        return False

    if rclone.configure_remote(access_key, secret_key, bucket):
        print('[OK] 配置成功!')
        return True
    else:
        print('[FAIL] 配置失败')
        return False

def main():
    init_colorama()
    print_banner()

    if not check_environment():
        print("\n提示：选择菜单 '5. config' 可以进行配置向导")

    push_module = PushModule()
    manage_module = ManageModule()
    pull_module = PullModule()
    mount_module = MountModule()

    while True:
        print_menu()
        choice = input("\n请选择操作 [0-5]: ").strip().lower()

        if choice == '0':
            print("\n再见!")
            break
        elif choice == '1':
            push_module.run()
        elif choice == '2':
            pull_module.run()
        elif choice == '3':
            manage_module.run()
        elif choice == '4':
            mount_module.run()
        elif choice == '5':
            config_wizard()
        else:
            print("无效的选择，请重新输入")

if __name__ == "__main__":
    main()
