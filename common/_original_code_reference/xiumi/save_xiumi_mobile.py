"""
使用Playwright在iPhone 15 Pro Max设备上打开秀米网页并保存到桌面

功能说明：
- 使用Playwright自动化浏览器操作
- 模拟iPhone 15 Pro Max设备访问指定网页
- 获取页面标题并打印
- 截取完整网页（包括滚动区域）并保存到桌面
- 将网页HTML内容保存到用户桌面

输入参数：
- URL: https://d.xiumius.cn/board/v5/3vIVh/429104433
- 设备: iPhone 15 Pro Max
- 保存路径: 用户桌面

外部依赖：
- playwright (需要先安装: pip install playwright)
- 需要运行: playwright install.webkit 来安装WebKit浏览器

输出结果：
- 在桌面生成保存的网页文件
- 在桌面生成完整网页截图
- 控制台打印页面标题信息
"""

import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright


async def save_xiumi_mobile_page():
    """
    使用Playwright在iPhone 15 Pro Max设备上打开秀米网页并保存
    
    Returns:
        str: 保存文件的完整路径
    """
    # 获取桌面路径
    desktop_path = Path.home() / "Desktop"
    
    # 确保桌面目录存在
    desktop_path.mkdir(exist_ok=True)
    
    # 目标URL
    url = "https://d.xiumius.cn/board/v5/3vIVh/429104433"
    
    async with async_playwright() as p:
        # 启动webkit浏览器（适用于移动端）
        browser = await p.webkit.launch(headless=False)
        
        # 创建iPhone 15 Pro Max设备上下文
        device = p.devices["iPhone 15 Pro Max"]
        context = await browser.new_context(**device)
        
        # 创建新页面
        page = await context.new_page()
        
        try:
            # 导航到目标网页
            print(f"正在打开网页: {url}")
            await page.goto(url, wait_until="networkidle")
            
            # 等待页面加载完成
            await page.wait_for_timeout(5000)
            
            # 1. 获取并打印标题
            title_text = "未获取到标题"
            try:
                # 尝试多种方式智能获取标题
                
                # 方式1: 查找页面中的主要标题元素
                title_selectors = [
                    "h1:first-child",
                    "h1",
                    "h2:first-child", 
                    "h2",
                    ".title:first-child",
                    ".headline:first-child",
                    "[class*='title']:first-child",
                    "[data-testid*='title']",
                    "header h1",
                    ".page-title"
                ]
                
                for selector in title_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.inner_text()
                            if text and len(text.strip()) > 0:
                                title_text = text.strip()
                                print(f"通过选择器 '{selector}' 获取到标题: {title_text}")
                                break
                    except:
                        continue
                
                # 方式2: 如果上述方式都失败，使用页面title
                if title_text == "未获取到标题":
                    page_title = await page.title()
                    if page_title and len(page_title.strip()) > 0:
                        title_text = page_title.strip()
                        print(f"通过页面title获取到标题: {title_text}")
                    else:
                        print("无法获取到有效的页面标题")
                
            except Exception as title_error:
                print(f"获取标题过程异常: {title_error}")
                # 最后的备选方案
                try:
                    page_title = await page.title()
                    title_text = page_title if page_title else "未知标题"
                    print(f"最终备选标题: {title_text}")
                except:
                    title_text = "获取标题失败"
                    print(title_text)
            
            # 生成保存文件名（带时间戳）
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"xiumi_mobile_{timestamp}.html"
            save_path = desktop_path / filename
            
            # 获取页面内容
            content = await page.content()
            
            # 保存到桌面
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"网页已成功保存到: {save_path}")
            
            # 2. 截取整个网页并保存到桌面
            screenshot_results = []
            
            # 方法1: 使用Playwright的full_page截图
            try:
                screenshot_path1 = desktop_path / f"xiumi_mobile_fullpage_{timestamp}.png"
                await page.screenshot(path=str(screenshot_path1), full_page=True)
                screenshot_results.append({
                    'path': screenshot_path1,
                    'type': 'full_page',
                    'size': screenshot_path1.stat().st_size
                })
                print(f"✓ 完整页面截图已保存: {screenshot_path1}")
                print(f"  文件大小: {screenshot_results[-1]['size']} 字节 ({screenshot_results[-1]['size']/1024/1024:.2f} MB)")
            except Exception as e1:
                print(f"⚠ 完整页面截图失败: {e1}")
                
                # 方法2: 如果full_page失败，尝试分段截图
                try:
                    print("正在尝试分段截图方案...")
                    segmented_result = await _segmented_screenshot(page, desktop_path, timestamp)
                    if segmented_result:
                        screenshot_results.extend(segmented_result)
                except Exception as e2:
                    print(f"⚠ 分段截图也失败: {e2}")
                    
                    # 方法3: 最后的备选方案 - 可视区域截图
                    try:
                        screenshot_path3 = desktop_path / f"xiumi_mobile_viewport_{timestamp}.png"
                        await page.screenshot(path=str(screenshot_path3), full_page=False)
                        screenshot_results.append({
                            'path': screenshot_path3,
                            'type': 'viewport_only',
                            'size': screenshot_path3.stat().st_size
                        })
                        print(f"✓ 可视区域截图已保存: {screenshot_path3}")
                    except Exception as e3:
                        print(f"✗ 所有截图方法都失败: {e3}")
            
            # 显示所有成功的截图结果
            if screenshot_results:
                print(f"\n总共生成 {len(screenshot_results)} 个截图文件:")
                for i, result in enumerate(screenshot_results, 1):
                    print(f"  {i}. {result['type']}: {result['path'].name} ({result['size']/1024/1024:.2f} MB)")
            else:
                print("❌ 未能生成任何截图文件")
            
            # 保持页面打开一段时间以便查看
            await page.wait_for_timeout(10000)
            
            return str(save_path)
            
        except Exception as e:
            print(f"保存过程中出现错误: {e}")
            raise
        finally:
            # 关闭浏览器
            await browser.close()


async def _segmented_screenshot(page, desktop_path, timestamp):
    """
    分段截图方法 - 当完整截图受限时使用
    通过滚动页面并拼接多个截图来获得完整页面视图
    """
    results = []
    
    # 获取页面总高度
    total_height = await page.evaluate("document.body.scrollHeight")
    viewport_height = await page.evaluate("window.innerHeight")
    scroll_step = int(viewport_height * 0.8)  # 每次滚动80%视口高度以确保重叠
    
    print(f"页面总高度: {total_height}px, 视口高度: {viewport_height}px")
    
    # 计算需要截图的段数
    segments = []
    current_y = 0
    
    while current_y < total_height:
        segments.append(current_y)
        current_y += scroll_step
        if current_y + viewport_height >= total_height:
            segments.append(total_height - viewport_height)
            break
    
    print(f"需要截取 {len(segments)} 个片段")
    
    # 逐段截图
    segment_files = []
    for i, y_pos in enumerate(segments):
        # 滚动到指定位置
        await page.evaluate(f"window.scrollTo(0, {y_pos})")
        await page.wait_for_timeout(500)  # 等待滚动完成和动画结束
        
        # 截图
        segment_path = desktop_path / f"xiumi_mobile_segment_{i+1:03d}_{timestamp}.png"
        await page.screenshot(path=str(segment_path), full_page=False)
        segment_files.append(segment_path)
        print(f"  ✓ 已保存片段 {i+1}/{len(segments)}: {segment_path.name}")
    
    # 如果生成了多个片段，尝试合并它们
    if len(segment_files) > 1:
        try:
            merged_path = await _merge_screenshots(segment_files, desktop_path, timestamp)
            if merged_path:
                results.append({
                    'path': merged_path,
                    'type': 'merged_segments',
                    'size': merged_path.stat().st_size
                })
                print(f"✓ 合并后的完整截图: {merged_path.name}")
        except Exception as merge_error:
            print(f"⚠ 合并截图失败: {merge_error}")
            # 即使合并失败，也保留各个片段
            for seg_file in segment_files:
                results.append({
                    'path': seg_file,
                    'type': 'segment',
                    'size': seg_file.stat().st_size
                })
    elif len(segment_files) == 1:
        # 只有一个片段的情况
        results.append({
            'path': segment_files[0],
            'type': 'single_segment',
            'size': segment_files[0].stat().st_size
        })
    
    return results


async def _merge_screenshots(segment_files, desktop_path, timestamp):
    """
    合并多个截图片段为一个完整图片
    需要安装pillow库: pip install pillow
    """
    try:
        from PIL import Image
        
        # 读取第一个图片获取宽度
        first_img = Image.open(segment_files[0])
        width = first_img.width
        total_height = 0
        
        # 计算总高度
        images = []
        for file_path in segment_files:
            img = Image.open(file_path)
            images.append(img)
            total_height += img.height
        
        # 创建新的大图
        merged_image = Image.new('RGB', (width, total_height), (255, 255, 255))
        
        # 粘贴各个片段
        current_y = 0
        for img in images:
            merged_image.paste(img, (0, current_y))
            current_y += img.height
            img.close()
        
        # 保存合并后的图片
        merged_path = desktop_path / f"xiumi_mobile_merged_{timestamp}.png"
        merged_image.save(merged_path, 'PNG', optimize=True)
        merged_image.close()
        
        # 清理临时片段文件
        for file_path in segment_files:
            try:
                file_path.unlink()
            except:
                pass
        
        return merged_path
        
    except ImportError:
        print("⚠ 需要安装Pillow库才能合并截图: pip install pillow")
        return None
    except Exception as e:
        print(f"⚠ 合并图片时出错: {e}")
        return None


def main():
    """主函数"""
    print("开始执行秀米移动端网页保存任务...")
    
    try:
        # 运行异步函数
        result = asyncio.run(save_xiumi_mobile_page())
        print(f"任务完成！文件保存位置: {result}")
    except Exception as e:
        print(f"任务执行失败: {e}")


if __name__ == "__main__":
    main()