from simhash import Simhash
import sqlite3
import os
import logging
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

logger = logging.getLogger(__name__)

class Deduplicator:
    def __init__(self, db_path: str = "data/crawler.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """初始化 SQLite 数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # 创建表：存储 URL 和 SimHash
        c.execute('''CREATE TABLE IF NOT EXISTS pages
                     (url TEXT PRIMARY KEY, simhash TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()

    def normalize_url(self, url: str) -> str:
        """URL 标准化"""
        try:
            parsed = urlparse(url)
            # 1. 转小写 scheme 和 netloc
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            
            # 2. 移除默认端口
            if (scheme == 'http' and netloc.endswith(':80')) or \
               (scheme == 'https' and netloc.endswith(':443')):
                netloc = netloc.rsplit(':', 1)[0]
                
            # 3. 移除追踪参数 (utm_, spm, etc.)
            query = parsed.query
            if query:
                params = parse_qsl(query)
                filtered_params = []
                blacklist = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 
                             'spm', 'fbclid', 'gclid', '_ga', 'ref']
                for k, v in params:
                    if k.lower() not in blacklist:
                        filtered_params.append((k, v))
                # 排序参数以保证一致性
                filtered_params.sort()
                query = urlencode(filtered_params)
            
            # 4. 移除 fragment (锚点)
            return urlunparse((scheme, netloc, parsed.path, parsed.params, query, ''))
            
        except Exception:
            return url

    def is_duplicate(self, url: str, content: str) -> bool:
        """检查是否重复"""
        norm_url = self.normalize_url(url)
        content_simhash = str(Simhash(content).value)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 1. URL 级去重
        c.execute("SELECT simhash FROM pages WHERE url = ?", (norm_url,))
        row = c.fetchone()
        if row:
            conn.close()
            logger.info(f"[Dedup] URL duplicate: {norm_url}")
            return True
            
        # 2. 内容级去重 (SimHash 汉明距离)
        # 注意：SQLite 不支持高效的汉明距离查找，数据量大时需要遍历或使用专门的向量库/LSH
        # 这里为了演示，做一个简单的全表扫描 (仅适合小规模数据)
        # 实际生产中应使用 Redis 或 ElasticSearch
        
        c.execute("SELECT simhash FROM pages")
        all_hashes = c.fetchall()
        
        obj_simhash = Simhash(content)
        
        for (h_str,) in all_hashes:
            try:
                other_val = int(h_str)
                # 计算距离
                dist = obj_simhash.distance(Simhash(other_val))
                if dist <= 3: # 阈值：海明距离 <= 3 视为相似
                    conn.close()
                    logger.info(f"[Dedup] Content duplicate (dist={dist}): {norm_url}")
                    return True
            except Exception:
                continue
                
        # 不重复，写入数据库
        try:
            c.execute("INSERT INTO pages (url, simhash) VALUES (?, ?)", (norm_url, content_simhash))
            conn.commit()
        except sqlite3.IntegrityError:
            pass # 并发时可能发生
            
        conn.close()
        return False
