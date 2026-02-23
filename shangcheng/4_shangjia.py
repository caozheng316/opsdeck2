"""
【极简版】打开网页→自定义操作→等待回车→关闭网页
"""

import json
import os
from playwright.sync_api import sync_playwright

def custom_operations(page, item):
    """
    自定义操作函数 - 在这里添加所有自动操作步骤
    参数：
    - page: 当前页面对象
    - item: 当前循环到的配置项
    """
    # =============================================
    # 等待网页加载成功后再等1秒
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)
    # 点击侧边栏商品元素
    target_loc = page.locator(
        "#app > section > div.layout-columns-aside > div > div.el-scrollbar__wrap.el-scrollbar__wrap--hidden-default > div > ul > li:nth-child(2) > div"
    )
    target_loc.wait_for(state="visible", timeout=15000)
    target_loc.click()
    print("已点击侧边栏商品元素")
    # 点击“添加商品”按钮
    add_btn = page.locator(
        "#app > section > div.layout-columns-warp > section > div > div.el-scrollbar__wrap.el-scrollbar__wrap--hidden-default > div > main > div > div.el-scrollbar__wrap.el-scrollbar__wrap--hidden-default > div > div.h100 > div > div.el-card.box-card.mt14.is-never-shadow > div > button.el-button.el-button--primary.el-button--small"
    )
    add_btn.wait_for(state="visible", timeout=15000)
    add_btn.click()
    print("已点击添加商品按钮")
    # 点击“确定”按钮
    confirm_btn = page.locator(
        "#app > section > div.layout-columns-warp > section > div > div.el-scrollbar__wrap.el-scrollbar__wrap--hidden-default > div > main > div > div.el-scrollbar__wrap.el-scrollbar__wrap--hidden-default > div > div.h100 > div > div:nth-child(5) > div > div > div.el-dialog__footer > span > button.el-button.el-button--primary.el-button--small"
    )
    confirm_btn.wait_for(state="visible", timeout=15000)
    confirm_btn.click()
    print("已点击确定按钮")
    # 定位到“普通商品”输入框并填入商品名称
    # 输入商品名称
    # 等待元素可见并尝试点击后再填充，避免元素未渲染完成导致无效
    input_loc = page.locator(
        "#app > section > div.layout-columns-warp > section > div > div.el-scrollbar__wrap.el-scrollbar__wrap--hidden-default > div > main > div > div.el-scrollbar__wrap.el-scrollbar__wrap--hidden-default > div > div.h100 > div > div.el-card.box-card.mt14.is-never-shadow > div > form > div:nth-child(1) > div:nth-child(2) > div > div > div.from-ipt-width.el-input.el-input--small > input"
    )
    input_loc.wait_for(state="visible", timeout=15000)  # 最多等15秒
    input_loc.click()  # 先点击，确保聚焦
    input_loc.fill("")  # 清空
    input_loc.fill(item.get("线路标题", ""))  # 填入新值
    # 点击商户分类
    category_input = page.locator(
        "#app > section > div.layout-columns-warp > section > div > div.el-scrollbar__wrap.el-scrollbar__wrap--hidden-default > div > main > div > div.el-scrollbar__wrap.el-scrollbar__wrap--hidden-default > div > div.h100 > div > div.el-card.box-card.mt14.is-never-shadow > div > form > div:nth-child(1) > div:nth-child(3) > div > div > div > div.el-input.el-input--small.el-input--suffix > input"
    ).first
    category_input.wait_for(state="visible", timeout=15000)
    category_input.click()
    print("已点击商户分类输入框")
    # 点击"旅游线路"复选框
    print("正在点击\"旅游线路\"复选框...")
    try:
        # 使用JavaScript选中"旅游线路"复选框
        page.evaluate("""
            const labels = document.querySelectorAll('label');
            for (let label of labels) {
                if (label.textContent.includes('旅游线路')) {
                    const checkbox = label.querySelector('span.el-checkbox__inner');
                    if (checkbox) {
                        checkbox.click();
                    }
                    break;
                }
            }
        """)
        print("已成功点击\"旅游线路\"复选框")
    except Exception as e:
        print(f"点击\"旅游线路\"复选框失败: {e}")
# 配置
LOGIN_URL = "https://trip-mer.hydtrip.com.cn/login?redirect=%2Fdashboard"
TARGET_URL = "https://trip-mer.hydtrip.com.cn/dashboard"
STORAGE_STATE_PATH = "login_state.json"
CONFIG_FILENAME = "savexiumi_config.json"

def main():
    print(">>> 极简版脚本运行")
    folder_path = "C:\\Users\\Administrator\\Desktop\\野途"
    # folder_path = input("请输入配置文件路径：")
    
    # 加载配置
    config_path = os.path.join(folder_path, CONFIG_FILENAME)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except:
        print("配置文件加载失败")
        return
    
    # 获取项目数量
    items = []
    if isinstance(config, dict) and "items" in config:
        items = config["items"]
    elif isinstance(config, list):
        items = config
    
    print(f"共 {len(items)} 个项目")
    
    with sync_playwright() as playwright:
        for i, _ in enumerate(items):
            print(f"\n=== 项目 {i+1} ===")
            
            # 尝试加载登录状态
            try:
                print("尝试加载登录状态...")
                browser = playwright.chromium.launch(headless=False)
                context = browser.new_context(storage_state=STORAGE_STATE_PATH)
                page = context.new_page()
                page.goto(TARGET_URL)
                
                # 等待页面加载
                page.wait_for_load_state("networkidle", timeout=15000)
                
                # 检查是否登录成功
                if "login" not in page.url.lower():
                    print("登录状态加载成功！")
                    
                    # 执行自定义操作
                    custom_operations(page, items[i])
                    
                    # 等待用户操作
                    input("按回车键继续...")
                    
                    context.close()
                    browser.close()
                    continue
                else:
                    print("登录状态已过期，需要重新登录")
                    context.close()
                    browser.close()
            except Exception as e:
                print(f"登录状态加载失败: {e}")
                print("需要重新登录")
            
            # 重新登录流程
            print("正在打开登录页面...")
            browser = playwright.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            page.goto(LOGIN_URL)
            
            # 等待登录页面加载
            page.wait_for_load_state("networkidle", timeout=15000)
            print("登录页面已加载，请手动登录...")
            
            input("请手动登录后按回车键...")
            
            # 等待页面跳转
            page.wait_for_load_state("networkidle", timeout=15000)
            
            # 检查是否登录成功
            if "login" not in page.url.lower():
                print("登录成功！")
                
                # 保存登录状态
                context.storage_state(path=STORAGE_STATE_PATH)
                print("登录状态已保存！")
                
                # 执行自定义操作
                custom_operations(page, items[i])
                
                # 等待用户操作
                input("按回车键继续...")
                
                context.close()
                browser.close()
            else:
                print("登录失败，页面未跳转")
                context.close()
                browser.close()
    
    print("\n所有项目处理完成！")

if __name__ == '__main__':
    main()
