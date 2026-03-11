from core.crawler.fetcher import HybridFetcher
from core.crawler.cleaner import HTMLCleaner
from core.crawler.dedup import Deduplicator
import logging
import os
import json
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrawlerManager:
    def __init__(self):
        self.fetcher = HybridFetcher()
        self.cleaner = HTMLCleaner()
        self.dedup = Deduplicator()
        
        # 数据存储路径
        self.data_dir = "data/crawler_output"
        os.makedirs(self.data_dir, exist_ok=True)

    def crawl(self, url: str) -> dict:
        """
        执行完整爬取流程：
        1. Fetch (Static -> Dynamic)
        2. Clean
        3. Dedup
        4. Save
        """
        logger.info(f"Starting crawl task for: {url}")
        
        # 1. Fetch
        fetch_result = self.fetcher.fetch(url)
        if not fetch_result["success"]:
            logger.error(f"Fetch failed: {fetch_result.get('error')}")
            return {"success": False, "error": fetch_result.get("error")}
            
        raw_html = fetch_result["content"]
        final_url = fetch_result["url"]
        
        # 2. Clean
        clean_result = self.cleaner.clean(raw_html)
        text_content = clean_result["text"]
        title = clean_result["title"]
        
        if not text_content:
            logger.warning("Cleaned content is empty.")
            return {"success": False, "error": "Empty content"}
            
        # 3. Dedup
        if self.dedup.is_duplicate(final_url, text_content):
            logger.info("Page skipped due to duplication.")
            return {"success": True, "status": "skipped_duplicate", "title": title}
            
        result_data = {
            "url": final_url,
            "title": title,
            "content": text_content,
            "fetched_at": datetime.now().isoformat(),
            "method": fetch_result["method"]
        }
        
        self._save_to_disk(result_data)
        
        logger.info(f"Crawl finished successfully: {title}")
        return {"success": True, "data": result_data}

    def _save_to_disk(self, data: dict):
        """保存到本地文件"""
        import hashlib
        # 使用 URL hash 作为文件名
        filename = hashlib.md5(data["url"].encode()).hexdigest() + ".json"
        filepath = os.path.join(self.data_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    # 简单测试
    manager = CrawlerManager()
    # 测试一个静态页面
    manager.crawl("https://example.com") 
    # 测试一个可能需要动态渲染的页面 (如果 example.com 也是静态的，那只会触发 static)
