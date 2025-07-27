import os
import time
import sys
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth.sync_api import stealth_sync # <--- 【已修正】导入 stealth

# --- 全局配置 (无变动) ---
HIDENCLOUD_COOKIE = os.environ.get('HIDENCLOUD_COOKIE')
HIDENCLOUD_EMAIL = os.environ.get('HIDENCLOUD_EMAIL')
HIDENCLOUD_PASSWORD = os.environ.get('HIDENCLOUD_PASSWORD')
BASE_URL = "https://dash.hidencloud.com"
LOGIN_URL = f"{BASE_URL}/auth/login"
SERVICE_URL = f"{BASE_URL}/service/62037/manage"
COOKIE_NAME = "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"

# --- log, login, renew_service 函数 (无变动) ---
def log(message):
    """打印带时间戳的日志"""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)

def login(page):
    """
    处理登录逻辑。
    1. 优先尝试使用 Cookie 登录。
    2. 如果 Cookie 失效或不存在，则使用账号密码进行登录。
    """
    log("开始登录流程...")

    # --- 方案一：Cookie 登录 ---
    if HIDENCLOUD_COOKIE:
        log("检测到 HIDENCLOUD_COOKIE，尝试使用 Cookie 登录。")
        try:
            # 设置 Cookie
            cookie = {
                'name': COOKIE_NAME,
                'value': HIDENCLOUD_COOKIE,
                'domain': 'dash.hidencloud.com',
                'path': '/',
                'expires': int(time.time()) + 3600 * 24 * 365, # 设置一年有效期
                'httpOnly': True,
                'secure': True,
                'sameSite': 'Lax'
            }
            page.context.add_cookies([cookie])
            log("Cookie 已设置。正在访问服务管理页面...")
            page.goto(SERVICE_URL, wait_until="networkidle", timeout=60000)

            # 验证登录是否成功
            # 如果页面 URL 包含 "auth/login"，说明 Cookie 失效，需要重新登录
            if "auth/login" in page.url:
                log("Cookie 登录失败或会话已过期，将回退到账号密码登录。")
                page.context.clear_cookies() # 清除无效的 Cookie
            else:
                log("✅ Cookie 登录成功！")
                return True
        except Exception as e:
            log(f"使用 Cookie 访问时发生错误: {e}")
            log("将回退到账号密码登录。")
            page.context.clear_cookies()
    else:
        log("未提供 HIDENCLOUD_COOKIE，直接使用账号密码登录。")

    # --- 方案二：账号密码登录 ---
    if not HIDENCLOUD_EMAIL or not HIDENCLOUD_PASSWORD:
        log("❌ 错误: Cookie 无效/未提供，且未提供邮箱和密码。无法继续登录。")
        return False

    log("正在尝试使用邮箱和密码登录...")
    try:
        page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)
        log("登录页面已加载。")

        # 填写邮箱和密码
        page.fill('input[name="email"]', HIDENCLOUD_EMAIL)
        log("邮箱已填写。")
        page.fill('input[name="password"]', HIDENCLOUD_PASSWORD)
        log("密码已填写。")

        # 处理 Cloudflare Turnstile 人机验证
        log("正在处理 Cloudflare Turnstile 人机验证...")
        turnstile_frame = page.frame_locator('iframe[src*="challenges.cloudflare.com"]')
        checkbox = turnstile_frame.locator('input[type="checkbox"]')
        
        # 等待复选框可见并点击
        checkbox.wait_for(state="visible", timeout=30000)
        checkbox.click()
        
        log("已点击人机验证复选框，等待验证结果...")
        
        # 等待验证成功，Cloudflare 会添加一个 'cf-turnstile-response'
        page.wait_for_function("""
            () => document.querySelector('[name="cf-turnstile-response"]') && document.querySelector('[name="cf-turnstile-response"]').value
        """, timeout=60000)
        log("✅ 人机验证成功！")

        # 点击登录按钮
        page.click('button[type="submit"]:has-text("Sign in to your account")')
        log("已点击登录按钮，等待页面跳转...")

        # 等待导航完成
        page.wait_for_url(f"{BASE_URL}/dashboard", timeout=60000)

        if "auth/login" in page.url:
            log("❌ 账号密码登录失败，请检查凭据是否正确。")
            page.screenshot(path="login_failure.png")
            return False

        log("✅ 账号密码登录成功！")
        return True

    except PlaywrightTimeoutError as e:
        log(f"❌ 登录过程中超时: {e}")
        page.screenshot(path="login_timeout_error.png")
        return False
    except Exception as e:
        log(f"❌ 登录过程中发生未知错误: {e}")
        page.screenshot(path="login_general_error.png")
        return False

def renew_service(page):
    """
    执行续费流程：
    1. 访问服务管理页面
    2. 点击 Renew
    3. 点击 Create Invoice
    4. 等待 Cloudflare 验证通过
    5. 点击 Pay
    """
    try:
        log("开始执行续费任务...")
        # 确保在正确的服务页面
        if page.url != SERVICE_URL:
            log(f"当前不在目标页面，正在导航至: {SERVICE_URL}")
            page.goto(SERVICE_URL, wait_until="networkidle", timeout=60000)
        
        log
