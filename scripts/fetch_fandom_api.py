import httpx
import json
import re
from bs4 import BeautifulSoup

API_ENDPOINT = "https://terraria.fandom.com/zh/api.php"

def fetch_page_content(title):
    print(f"Fetching API for: {title}")
    params = {
        "action": "parse",
        "page": title,
        "format": "json",
        "redirects": 1  # 自动处理重定向
    }
    
    headers = {
        "User-Agent": "EchoBot/1.0 (Terraria Assistant Demo)"
    }
    
    try:
        response = httpx.get(API_ENDPOINT, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            print(f"API Error: {data['error'].get('info')}")
            return None
            
        parse = data.get("parse", {})
        raw_html = parse.get("text", {}).get("*", "")
        display_title = parse.get("title", title)
        
        # 简单清洗 HTML 获取纯文本
        soup = BeautifulSoup(raw_html, 'html.parser')
        
        # 移除干扰
        for tag in soup.select("script, style, .mw-editsection, .navbox, .infobox, table.navbox"):
            tag.decompose()
            
        text = soup.get_text(separator="\n")
        # 清洗空行
        clean_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
        
        return {
            "title": display_title,
            "url": f"https://terraria.fandom.com/zh/wiki/{display_title}",
            "content": clean_text
        }
        
    except Exception as e:
        print(f"Error fetching {title}: {e}")
        return None

def main():
    targets = ["Boss", "NPC", "指南:游戏流程", "泰拉瑞亚"]
    
    results = []
    for t in targets:
        res = fetch_page_content(t)
        if res:
            print(f"Success: {res['title']} (Length: {len(res['content'])})")
            # 简单截取预览
            print(f"Preview: {res['content'][:100]}...")
            results.append(res)
        else:
            print(f"Failed: {t}")
            
    # 如果成功，保存一个 raw_data_fandom.json
    if results:
        with open("data/knowledge_base/terraria/raw_data_fandom.json", "w", encoding="utf-8") as f:
            # 转换为 RAG 格式
            rag_data = []
            for item in results:
                rag_data.append({
                    "title": item["title"],
                    "url": item["url"],
                    "sections": [{"heading": "Full Content", "content": item["content"]}]
                })
            json.dump(rag_data, f, ensure_ascii=False, indent=2)
            print("\nSaved to data/knowledge_base/terraria/raw_data_fandom.json")

if __name__ == "__main__":
    main()
