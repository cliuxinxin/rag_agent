import os
import requests
import concurrent.futures
from typing import List, Optional
from langchain_core.embeddings import Embeddings

class HunyuanEmbeddings(Embeddings):
    """
    自定义腾讯混元 Embedding 适配器 (支持并发加速)
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("HUNYUAN_API_KEY")
        self.api_url = "https://api.hunyuan.cloud.tencent.com/v1/embeddings"
        self.model_name = "hunyuan-embedding"
        # 设置并发线程数，建议 5-10
        self.max_workers = 5 # 降低并发数，防止触发腾讯 API 限流导致大量失败

    def _call_api_single(self, text: str) -> Optional[List[float]]:
        """单次 API 调用"""
        if not text or not text.strip():
            return None
            
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model_name,
            "input": text.replace("\n", " ")
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["embedding"]
            return None
        except Exception as e:
            print(f"Embedding Error: {e}")
            return None

    def embed_documents(self, texts: List[str], progress_callback=None) -> List[List[float]]:
        """
        并发为文档列表生成向量。
        progress_callback: 可选的回调函数，用于更新 UI 进度条
        """
        embeddings = [None] * len(texts)
        
        # 使用线程池并发处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_index = {executor.submit(self._call_api_single, text): i for i, text in enumerate(texts)}
            
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    emb = future.result()
                    embeddings[index] = emb
                except Exception as e:
                    print(f"Worker Error at index {index}: {e}")
                    embeddings[index] = None
                
                # 更新进度
                completed_count += 1
                if progress_callback:
                    progress_callback(completed_count, len(texts))
                    
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        return self._call_api_single(text)