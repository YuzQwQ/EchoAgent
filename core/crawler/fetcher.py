import httpx
from playwright.sync_api import sync_playwright
import time
import random
import logging

logger = logging.getLogger(__name__)

class HybridFetcher:
    def __init__(self, headless: bool = True):
        self.headless = headless
        # 常见动态页面特征
        self.dynamic_indicators = [
            "__NUXT__", "__NEXT_DATA__", "data-reactroot", 
            "window.__INITIAL_STATE__", "<noscript>"
        ]
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]

    def fetch(self, url: str) -> dict:
        """统一抓取入口"""
        logger.info(f"[Fetcher] Fetching: {url}")
        
        # 1. 尝试静态抓取
        static_result = self._fetch_static(url)
        
        if static_result.get("success") and not self._needs_dynamic_rendering(static_result.get("content", "")):
            logger.info("[Fetcher] Static fetch successful.")
            static_result["method"] = "static"
            return static_result
            
        logger.info("[Fetcher] Static fetch failed or detected dynamic content. Switching to dynamic fetch...")
        
        # 2. 回退到动态抓取
        dynamic_result = self._fetch_dynamic(url)
        dynamic_result["method"] = "dynamic"
        return dynamic_result

    def _fetch_static(self, url: str) -> dict:
        """使用 httpx 静态抓取"""
        try:
            headers = {"User-Agent": random.choice(self.user_agents)}
            # 跟随重定向，超时设置
            with httpx.Client(follow_redirects=True, timeout=10.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                
                # 简单的编码猜测
                if response.encoding == 'ISO-8859-1':
                    response.encoding = response.charset_encoding or response.encoding
                    
                return {
                    "success": True,
                    "url": str(response.url),
                    "status": response.status_code,
                    "content": response.text,
                    "headers": dict(response.headers)
                }
        except Exception as e:
            logger.warning(f"[Fetcher] Static fetch error: {e}")
            return {"success": False, "error": str(e)}

    def _needs_dynamic_rendering(self, html: str) -> bool:
        """判断是否需要动态渲染"""
        if not html:
            return True
            
        # 1. 检查内容长度 (太短可能是空壳，但 example.com 很短)
        # 调低阈值到 500 字符，或者检查是否包含 </html>
        if len(html) < 500 and "</html>" not in html:
            return True
            
        # 2. 检查动态特征关键词
        for indicator in self.dynamic_indicators:
            if indicator in html:
                return True
                
        return False

    def _fetch_dynamic(self, url: str) -> dict:
        """使用 Playwright 动态抓取"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                
                # 拟人化 Context
                context = browser.new_context(
                    user_agent=random.choice(self.user_agents),
                    viewport={"width": 1920, "height": 1080},
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai"
                )
                
                # 屏蔽 webdriver 特征
                context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                page = context.new_page()
                
                # 路由拦截：屏蔽图片、字体、媒体
                page.route("**/*", lambda route: self._intercept_route(route))
                
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    
                    # 尝试绕过 Cloudflare 等验证页面的等待
                    # 如果是 Wiki 页面，通常会有 #bodyContent 或 .mw-parser-output
                    try:
                        page.wait_for_selector("#bodyContent, .mw-parser-output, article, main", timeout=10000)
                    except Exception:
                        logger.warning("[Fetcher] Target content selector not found, page might be blocked or loading.")
                    
                    # 模拟人类行为：随机滚动
                    self._simulate_human_behavior(page)
                    
                    # 等待网络空闲 (确保 JS 执行完毕)
                    # page.wait_for_load_state("networkidle", timeout=5000) 
                    
                    content = page.content()
                    final_url = page.url
                    
                    return {
                        "success": True,
                        "url": final_url,
                        "status": 200, # Playwright 不一定能拿到准确的 status code，默认成功
                        "content": content
                    }
                    
                except Exception as e:
                    logger.error(f"[Fetcher] Playwright page error: {e}")
                    return {"success": False, "error": str(e)}
                finally:
                    browser.close()
                    
        except Exception as e:
            logger.error(f"[Fetcher] Playwright launch error: {e}")
            return {"success": False, "error": str(e)}

    def _intercept_route(self, route):
        """拦截高耗资源"""
        resource_type = route.request.resource_type
        if resource_type in ["image", "media", "font", "stylesheet"]:
            route.abort()
        else:
            route.continue_()

    def _simulate_human_behavior(self, page):
        """模拟简单的鼠标滚动"""
        try:
            # 随机滚动几次
            for _ in range(random.randint(2, 5)):
                scroll_y = random.randint(100, 800)
                page.mouse.wheel(0, scroll_y)
                time.sleep(random.uniform(0.1, 0.5))
            
            # 确保滚到底部触发懒加载
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.0)
        except Exception:
            pass
