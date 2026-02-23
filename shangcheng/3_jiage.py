"""
价格信息采集工具
用于遍历 savexiumi_config.json 中的 items，为每个 item 录入价格信息

功能说明：
- 读取指定目录下的 savexiumi_config.json 文件
- 遍历所有 items，跳过已有价格的 item
- 使用系统默认应用打开详情页图片供用户查看
- 在控制台输入价格信息
- 保存价格信息到配置文件
- 录入完成后自动关闭图片查看器
"""

import json
import os
import sys
import subprocess
import time
from pathlib import Path


# 全局变量存储图片查看器进程信息
_image_viewer_pid = None


def get_directory_path() -> Path:
    """获取用户输入的目录路径"""
    print("=" * 60)
    print("价格信息采集工具")
    print("=" * 60)
    print("\n请输入工作目录路径（包含 savexiumi_config.json 的目录）")
    print("示例: C:\\Users\\Administrator\\Desktop\\野途")
    print("直接回车使用默认路径: C:\\Users\\Administrator\\Desktop\\野途")
    print("-" * 60)
    
    default_path = r"C:\Users\Administrator\Desktop\野途"
    user_input = input(f"目录路径: ").strip()
    
    if not user_input:
        user_input = default_path
    
    # 去除可能的引号
    user_input = user_input.strip('"').strip("'")
    path = Path(user_input)
    
    if not path.exists():
        print(f"❌ 错误: 目录不存在 - {path}")
        sys.exit(1)
    
    if not path.is_dir():
        print(f"❌ 错误: 不是有效的目录 - {path}")
        sys.exit(1)
    
    print(f"✓ 使用目录: {path}")
    return path


def load_config(storage_path: Path) -> dict:
    """加载配置文件"""
    config_path = storage_path / "savexiumi_config.json"
    
    if not config_path.exists():
        print(f"❌ 错误: 配置文件不存在 - {config_path}")
        print("请确保目录中包含 savexiumi_config.json 文件")
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✓ 成功加载配置文件")
        return config
    except json.JSONDecodeError as e:
        print(f"❌ 错误: JSON 格式错误 - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: 读取配置文件失败 - {e}")
        sys.exit(1)


def save_config(storage_path: Path, config: dict) -> bool:
    """保存配置文件"""
    config_path = storage_path / "savexiumi_config.json"
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ 保存配置文件失败: {e}")
        return False


def open_image_with_default_app(image_path: Path) -> bool:
    """使用系统默认应用打开图片文件"""
    global _image_viewer_pid
    
    try:
        # Windows 使用 start 命令
        if sys.platform == 'win32':
            # 方法1: 使用 os.startfile 打开图片（最可靠的方式）
            try:
                os.startfile(str(image_path))
                print(f"  ✓ 已使用系统默认应用打开图片")
                # 给系统一点时间来启动进程
                time.sleep(0.5)
                return True
            except Exception as e:
                print(f"  ⚠️ os.startfile 失败: {e}")
                # 方法2: 备用方案使用 start 命令
                subprocess.Popen(['start', '', str(image_path)], shell=True)
                print(f"  ✓ 已使用系统默认应用打开图片 (备用方案)")
                return True
                
        # macOS 使用 open 命令
        elif sys.platform == 'darwin':
            proc = subprocess.Popen(['open', str(image_path)])
            _image_viewer_pid = proc.pid
            print(f"  ✓ 已使用系统默认应用打开图片")
            return True
        # Linux 使用 xdg-open 命令
        else:
            proc = subprocess.Popen(['xdg-open', str(image_path)])
            _image_viewer_pid = proc.pid
            print(f"  ✓ 已使用系统默认应用打开图片")
            return True
        
        return True
    except Exception as e:
        print(f"  ⚠️ 打开图片失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def close_image_viewer():
    """关闭图片查看器"""
    global _image_viewer_pid
    
    if _image_viewer_pid is None:
        # 如果没有记录 PID，尝试通过进程名关闭常见的图片查看器
        try:
            if sys.platform == 'win32':
                # 尝试关闭 Windows 照片应用 (Photos.exe) 和画图 (mspaint.exe)
                subprocess.run(['taskkill', '/F', '/IM', 'Photos.exe'], 
                             capture_output=True, shell=True)
                subprocess.run(['taskkill', '/F', '/IM', 'mspaint.exe'], 
                             capture_output=True, shell=True)
                subprocess.run(['taskkill', '/F', '/IM', 'dllhost.exe'], 
                             capture_output=True, shell=True)
        except:
            pass
        return
    
    try:
        if sys.platform == 'win32':
            # 使用 taskkill 关闭指定 PID 的进程
            subprocess.run(['taskkill', '/F', '/PID', str(_image_viewer_pid)], 
                         capture_output=True, shell=True)
            print(f"  ✓ 已关闭图片查看器 (PID: {_image_viewer_pid})")
        else:
            # macOS 和 Linux 使用 kill 命令
            subprocess.run(['kill', str(_image_viewer_pid)], 
                         capture_output=True)
            print(f"  ✓ 已关闭图片查看器")
        
        _image_viewer_pid = None
    except Exception as e:
        print(f"  ⚠️ 关闭图片查看器失败: {e}")
        _image_viewer_pid = None


def input_price(title: str) -> str:
    """在控制台输入价格"""
    print(f"\n  {'-' * 50}")
    print(f"  线路: {title}")
    print(f"  {'-' * 50}")
    print("  请输入价格 (直接回车跳过此项):")
    
    while True:
        price = input("  价格: ").strip()
        
        # 直接回车表示跳过
        if not price:
            return None
        
        # 返回输入的价格
        return price


def check_item_files(storage_path: Path, config: dict) -> None:
    """检查所有 items 中的详情页路径和首图路径文件是否存在"""
    items = config.get("items", [])
    
    if not items:
        print("⚠️ 配置文件中没有 items 数据")
        return
    
    print("\n" + "=" * 80)
    print("文件存在性检查")
    print("=" * 80)
    
    missing_files = []
    
    for index, item in enumerate(items, 1):
        unique_id = item.get("唯一码", "无唯一码")
        title = item.get("线路标题", "未命名")
        detail_page_path = item.get("详情页路径", "")
        main_image_path = item.get("首图路径", "")
        
        # 检查详情页路径
        if detail_page_path:
            full_detail_path = storage_path / detail_page_path
            if not full_detail_path.exists():
                missing_files.append({
                    "唯一码": unique_id,
                    "标题": title,
                    "缺失文件": "详情页路径",
                    "路径": str(full_detail_path)
                })
        
        # 检查首图路径
        if main_image_path:
            full_main_image_path = storage_path / main_image_path
            if not full_main_image_path.exists():
                missing_files.append({
                    "唯一码": unique_id,
                    "标题": title,
                    "缺失文件": "首图路径",
                    "路径": str(full_main_image_path)
                })
    
    if missing_files:
        print(f"\n⚠️  共发现 {len(missing_files)} 个缺失文件:")
        print("-" * 80)
        for missing in missing_files:
            print(f"\n唯一码: {missing['唯一码']}")
            print(f"标题: {missing['标题']}")
            print(f"缺失文件: {missing['缺失文件']}")
            print(f"路径: {missing['路径']}")
            print("-" * 40)
    else:
        print("\n✅ 所有文件路径都存在")
    
    # 暂停让用户查看检查结果
    input("\n请按回车键继续执行后续流程...")
    
    print("\n" + "=" * 80)
    print("文件检查完成，开始录入价格环节")
    print("=" * 80)


def process_items(storage_path: Path, config: dict) -> dict:
    """处理所有 items，录入价格信息"""
    items = config.get("items", [])
    
    if not items:
        print("⚠️ 配置文件中没有 items 数据")
        return config
    
    print(f"\n共发现 {len(items)} 个 items")
    print("-" * 60)
    print("提示: 图片将使用系统默认的图片查看器打开")
    print("      查看图片后，在控制台输入价格即可")
    print("-" * 60)
    
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    for index, item in enumerate(items, 1):
        print(f"\n[{index}/{len(items)}] 处理中...")
        
        # 检查是否已有价格
        current_price = item.get("价格", "")
        if current_price:
            print(f"  ℹ 已有价格: {current_price}，跳过")
            skipped_count += 1
            continue
        
        title = item.get("线路标题", "未命名")
        detail_page_path = item.get("详情页路径", "")
        
        print(f"  线路标题: {title}")
        print(f"  详情页路径: {detail_page_path}")
        
        if not detail_page_path:
            print(f"  ⚠️ 详情页路径为空，跳过")
            error_count += 1
            continue
        
        # 构建完整的图片路径
        full_image_path = storage_path / detail_page_path
        
        if not full_image_path.exists():
            print(f"  ⚠️ 图片文件不存在: {full_image_path}")
            error_count += 1
            continue
        
        try:
            # 使用系统默认应用打开图片
            success = open_image_with_default_app(full_image_path)
            if not success:
                print(f"  ⚠️ 无法打开图片，跳过")
                error_count += 1
                continue
            
            # 在控制台输入价格
            price = input_price(title)
            
            if price is None:
                print(f"  ℹ 用户选择跳过")
                skipped_count += 1
                # 关闭图片查看器
                close_image_viewer()
                continue
            
            # 更新价格
            item["价格"] = price
            print(f"  ✓ 已录入价格: {price}")
            processed_count += 1
            
            # 立即保存配置（防止意外中断丢失数据）
            if save_config(storage_path, config):
                print(f"  ✓ 配置已保存")
            
            # 关闭图片查看器
            close_image_viewer()
            
            # 稍微延迟，让用户有时间看到保存成功的提示
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  ❌ 处理出错: {e}")
            # 出错时也尝试关闭图片查看器
            close_image_viewer()
            error_count += 1
            continue
    
    print("\n" + "=" * 60)
    print("处理完成统计:")
    print(f"  - 成功录入: {processed_count} 个")
    print(f"  - 已跳过（已有价格或用户跳过）: {skipped_count} 个")
    print(f"  - 错误跳过: {error_count} 个")
    print("=" * 60)
    
    return config


def main():
    """主函数"""
    try:
        # 1. 获取目录路径
        storage_path = get_directory_path()
        
        # 2. 加载配置文件
        config = load_config(storage_path)
        
        # 3. 检查文件存在性
        check_item_files(storage_path, config)
        
        # 4. 处理 items
        config = process_items(storage_path, config)
        
        # 5. 最终保存
        if save_config(storage_path, config):
            print("\n✓ 所有数据已保存到 savexiumi_config.json")
        else:
            print("\n❌ 最终保存失败")
        
        print("\n按回车键退出...")
        input()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
        print("\n按回车键退出...")
        input()
        sys.exit(1)


if __name__ == "__main__":
    main()
