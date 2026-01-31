import json
import os
import pickle
import numpy as np
from typing import List, Dict, Any
from config import config
from openai import OpenAI

class RAGService:
    def __init__(self, knowledge_name: str = "terraria"):
        self.knowledge_name = knowledge_name
        self.base_dir = os.path.join("data", "knowledge_base", knowledge_name)
        self.raw_data_path = os.path.join(self.base_dir, "raw_data.json")
        self.index_path = os.path.join(self.base_dir, "knowledge_index.pkl")
        
        self.client = OpenAI(
            api_key=config.EMBEDDING_API_KEY, 
            base_url=config.EMBEDDING_BASE_URL
        )
        self.embedding_model = config.EMBEDDING_MODEL_ID
        
        self.chunks = []
        self.embeddings = None
        
        self._load_or_build_index()

    def _load_or_build_index(self):
        """加载索引，如果不存在则构建"""
        if os.path.exists(self.index_path):
            print(f"[RAG] Loading index from {self.index_path}...")
            with open(self.index_path, 'rb') as f:
                data = pickle.load(f)
                self.chunks = data["chunks"]
                self.embeddings = data["embeddings"]
        else:
            print(f"[RAG] Index not found. Building from {self.raw_data_path}...")
            self.build_index()

    def build_index(self):
        """从 raw_data.json 构建索引"""
        if not os.path.exists(self.raw_data_path):
            print(f"[RAG] Warning: Raw data not found at {self.raw_data_path}")
            return

        with open(self.raw_data_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        chunks = []
        texts_to_embed = []

        # 1. 切分 Chunks
        for page in raw_data:
            page_title = page["title"]
            page_url = page["url"]
            
            for section in page["sections"]:
                heading = section["heading"]
                content = section["content"]
                
                # 简单切分：如果段落太长，可以进一步切分（这里暂略，假设段落适中）
                # 构造包含丰富上下文的文本用于 Embedding
                embed_text = f"{page_title} - {heading}: {content}"
                
                chunk = {
                    "text": content,
                    "metadata": {
                        "source": page_title,
                        "section": heading,
                        "url": page_url
                    }
                }
                chunks.append(chunk)
                texts_to_embed.append(embed_text)

        if not chunks:
            print("[RAG] No chunks to index.")
            return

        # 2. 计算 Embeddings (批量)
        print(f"[RAG] Embedding {len(chunks)} chunks...")
        try:
            # 注意：如果数据量大，需要分批调用。这里假设量小。
            response = self.client.embeddings.create(
                input=texts_to_embed,
                model=self.embedding_model
            )
            embeddings = [data.embedding for data in response.data]
            
            # 转为 numpy 数组
            self.chunks = chunks
            self.embeddings = np.array(embeddings).astype('float32')
            
            # 3. 保存索引
            with open(self.index_path, 'wb') as f:
                pickle.dump({
                    "chunks": self.chunks,
                    "embeddings": self.embeddings
                }, f)
            print(f"[RAG] Index saved to {self.index_path}")
            
        except Exception as e:
            print(f"[RAG] Error building index: {e}")

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """检索相关知识"""
        if self.embeddings is None or len(self.chunks) == 0:
            return []

        try:
            # 1. 计算 Query Embedding
            response = self.client.embeddings.create(
                input=[query],
                model=self.embedding_model
            )
            query_vec = np.array(response.data[0].embedding).astype('float32')
            
            # 2. 计算余弦相似度
            # Cosine Similarity = (A . B) / (|A| * |B|)
            # OpenAI embeddings are normalized to length 1, so dot product is enough
            scores = np.dot(self.embeddings, query_vec)
            
            # 3. 获取 Top K
            top_indices = np.argsort(scores)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                score = scores[idx]
                if score < 0.3: # 阈值过滤，避免不相关的噪音
                    continue
                    
                chunk = self.chunks[idx]
                results.append({
                    "text": chunk["text"],
                    "metadata": chunk["metadata"],
                    "score": float(score)
                })
                
            return results
            
        except Exception as e:
            print(f"[RAG] Search error: {e}")
            return []

    def format_results(self, results: List[Dict[str, Any]]) -> str:
        """将检索结果格式化为 Prompt 文本"""
        if not results:
            return ""
            
        lines = ["【知识库参考信息】"]
        for i, res in enumerate(results, 1):
            meta = res["metadata"]
            lines.append(f"{i}. 来源: {meta['source']} > {meta['section']}")
            lines.append(f"   内容: {res['text']}")
        
        return "\n".join(lines)
