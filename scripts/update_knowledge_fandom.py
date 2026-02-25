import httpx
import json
import os
import sys

# 添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rag_service import RAGService
from bs4 import BeautifulSoup

API_ENDPOINT = "https://terraria.fandom.com/zh/api.php"

# Fandom 中文 Wiki 的核心页面列表
TARGET_TITLES = [
    "Boss",
    "NPC",
    "事件",
    "生物群落",
    "指南:流程攻略", # 尝试这个标题
    "指南:职业搭配",
    "泰拉瑞亚",     # 主页
    "武器",
    "配饰",
    "药水"
]

def fetch_page_content(title):
    print(f"Fetching API for: {title}")
    params = {
        "action": "parse",
        "page": title,
        "format": "json",
        "redirects": 1
    }
    
    headers = {
        "User-Agent": "EchoBot/1.0 (Terraria Assistant Demo)"
    }
    
    try:
        response = httpx.get(API_ENDPOINT, params=params, headers=headers, timeout=20)
        
        # Fandom API 有时会返回 200 但包含 error
        try:
            data = response.json()
        except Exception:
            print(f"Error parsing JSON for {title}")
            return None
            
        if "error" in data:
            print(f"API Error for {title}: {data['error'].get('info')}")
            return None
            
        parse = data.get("parse", {})
        raw_html = parse.get("text", {}).get("*", "")
        display_title = parse.get("title", title)
        
        # 清洗 HTML
        soup = BeautifulSoup(raw_html, 'html.parser')
        
        # 移除干扰
        for tag in soup.select("script, style, .mw-editsection, .navbox, .infobox, table.navbox, .toc"):
            tag.decompose()

        # 按章节切分
        sections = []
        current_heading = "Intro"
        current_content = []
        
        for element in soup.children:
            if element.name in ['h2', 'h3']:
                # 保存上一章
                if current_content:
                    text = "\n".join(current_content).strip()
                    if text:
                        sections.append({
                            "heading": current_heading,
                            "content": text
                        })
                # 新章节
                current_heading = element.get_text().strip()
                current_content = []
            elif element.name: # 忽略纯字符串节点，只处理 Tag
                text = element.get_text(separator="\n", strip=True)
                if text:
                    current_content.append(text)
        
        # 保存最后一章
        if current_content:
            text = "\n".join(current_content).strip()
            if text:
                sections.append({
                    "heading": current_heading,
                    "content": text
                })

        # 如果切分失败（比如没有 h2），则回退到全文
        if not sections:
            text = soup.get_text(separator="\n")
            clean_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
            sections.append({"heading": "Full Content", "content": clean_text})
        
        return {
            "title": display_title,
            "url": f"https://terraria.fandom.com/zh/wiki/{display_title}",
            "sections": sections
        }
        
    except Exception as e:
        print(f"Error fetching {title}: {e}")
        return None

def main():
    print("=== Starting Terraria Knowledge Base Update (Fandom API) ===")
    
    collected_data = []
    
    for t in TARGET_TITLES:
        res = fetch_page_content(t)
        if res:
            print(f"Success: {res['title']} (Length: {len(res['sections'][0]['content'])})")
            collected_data.append(res)
        else:
            print(f"Failed to fetch: {t}")

    if not collected_data:
        print("No data collected.")
        return

    # 保存
    raw_data_path = "data/knowledge_base/terraria/raw_data.json"
    os.makedirs(os.path.dirname(raw_data_path), exist_ok=True)
    
    with open(raw_data_path, 'w', encoding='utf-8') as f:
        json.dump(collected_data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(collected_data)} pages to {raw_data_path}")

    # 重建索引
    print("\nRebuilding RAG Index...")
    index_path = "data/knowledge_base/terraria/knowledge_index.pkl"
    if os.path.exists(index_path):
        os.remove(index_path)
        
    rag = RAGService(knowledge_name="terraria")
    
    print("\n=== Update Complete! ===")
    
    # 测试
    test_q = "肉山怎么召唤"
    print(f"\nTest Search: '{test_q}'")
    results = rag.search(test_q)
    print(rag.format_results(results))

if __name__ == "__main__":
    main()
