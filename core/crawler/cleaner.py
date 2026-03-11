from bs4 import BeautifulSoup, Comment, Tag
import logging

logger = logging.getLogger(__name__)

class HTMLCleaner:
    def __init__(self):
        # 标签黑名单
        self.tag_blacklist = [
            'script', 'style', 'iframe', 'noscript', 'header', 'footer', 
            'nav', 'aside', 'svg', 'button', 'input', 'form', 'select', 'textarea'
        ]
        
        # 类名/ID 黑名单关键词 (语义过滤)
        self.class_blacklist = [
            'ad-', 'ads', 'advert', 'banner', 'popup', 'modal', 
            'cookie', 'login', 'signup', 'share', 'social', 'comment', 
            'sidebar', 'menu', 'navigation', 'copyright', 'related'
        ]

    def clean(self, html: str) -> dict:
        """清洗 HTML，提取正文和元数据"""
        if not html:
            return {"title": "", "text": "", "html": ""}
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. 提取标题
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        
        # 2. 移除干扰元素
        for tag in self.tag_blacklist:
            for element in soup.find_all(tag):
                element.decompose()
                
        # 3. 移除注释
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
            
        # 4. 基于语义的黑名单过滤 (class/id)
        # 注意：这步比较激进，可能会误删，需谨慎。简单起见，这里只对明显的广告块下手。
        # 使用 list() 强制生成列表，避免迭代时修改树结构导致的问题
        elements_to_remove = []
        for element in soup.find_all(True):
            if not isinstance(element, Tag):
                continue
                
            # 安全获取 attrs
            if not hasattr(element, 'attrs') or not element.attrs:
                continue
                
            classes_value = element.get('class')
            if isinstance(classes_value, str):
                classes = [classes_value]
            elif classes_value is None:
                classes = []
            else:
                classes = list(classes_value)

            ids_value = element.get('id')
            ids = ids_value if isinstance(ids_value, str) else ""

            check_str = " ".join(classes) + " " + ids
            check_str = check_str.lower()
            
            for keyword in self.class_blacklist:
                if keyword in check_str:
                    # 如果是主要内容容器，不要删
                    if 'content' in check_str or 'article' in check_str or 'main' in check_str:
                        continue
                    elements_to_remove.append(element)
                    break
        
        # 统一删除
        for el in elements_to_remove:
            # 再次检查是否还在树中 (可能被父元素删除了)
            if el.parent:
                el.decompose()

        # 5. 提取正文
        # 简单策略：获取 body 文本，去除多余空白
        text = soup.get_text(separator='\n')
        
        # 清洗空白行
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)
        
        return {
            "title": title,
            "text": clean_text,
            # "html": str(soup) # 可选：返回清洗后的 HTML
        }
