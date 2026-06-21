from langgraph.graph import StateGraph, END
from llama_index.core import VectorStoreIndex, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from langgraph.graph import add_messages
from typing import TypedDict, List, Dict, Any
from config.settings import *

class RAGState(TypedDict):
    query: str
    retrieved_docs: List[Dict]
    context: str
    answer: str

class RAGSubgraph:
    """RAG 检索增强生成子图"""

    def __init__(self):
        # 初始化 LLamaIndex 组件
        self.embed_modal = OllamaEmbedding(
            model_name=EMBED_MODEL,
            base_url=LLM_BASE_URL
        )
        Settings.embed_model=self.embed_modal

        # 初始化 Chroma 向量存储
        # TODO
        # - 连接 Chroma (持久化)
        # - 支持多 collection (按领域分隔)
        # - 添加向量缓存机制
        self.vector_store = ChromaVectorStore(
            persist_dir=str(MEMORY_PATH)
        )

    def build_graph(self) -> StateGraph:
        """构建 RAG 子图"""
        graph = StateGraph(RAGState)

        graph.add_node("retrieve", self.retrieve)
        graph.add_node("generate", self.generate)

        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", END)

        return graph

    async def retrieve(self, state: RAGState) -> RAGState:
        """检索相关文档"""
        # TODO
        # - 使用 LLamaIndex 进行语义检索
        # - 实现混合检索(向量 + 关键词 + 重排序)
        # - 添加检索结果缓存
        # - 实现自适应检索(根据查询复杂度调整 top_k)
        query = state["query"]

        # 检索逻辑框架
        index = VectorStoreIndex.from_vector_store(self.vector_store)
        retriever = index.as_retriever(similarity_top_k=5)
        nodes = retriever.retrieve(query)
        state["retrieved_docs"] = [{"text": n.text, "score": n.score} for n in nodes]
        state["context"] = "\n".join([d["text"] for d in state["retrieved_docs"]])

        return state
    
    async def generate(self, state: RAGState) -> RAGState:
        """基于检索结果生成回答"""
        # TODO
        # - 构建包含上下文的提示词
        # - 调用 LLM 生成回答
        # - 添加引用来源
        # - 生成置信度分数
        return state