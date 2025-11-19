"""BM25 检索器封装。"""

from typing import List
import jieba
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document


class SimpleBM25Retriever:
    """简单的内存级 BM25 检索器。"""

    def __init__(self, documents: List[Document]):
        self.documents = documents
        # 预处理：中文分词
        self.corpus = [self._tokenize(doc.page_content) for doc in documents]
        self.bm25 = BM25Okapi(self.corpus)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """使用 Jieba 进行中文分词。"""
        return list(jieba.cut(text))

    def search(self, query: str, k: int = 3) -> List[Document]:
        """执行检索。"""
        tokenized_query = self._tokenize(query)
        # 获取 top_k 文档
        top_docs = self.bm25.get_top_n(tokenized_query, self.documents, n=k)
        return top_docs