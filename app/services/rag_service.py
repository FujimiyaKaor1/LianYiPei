"""PDF RAG 入库服务：加载、切分、向量化并写入本地 Chroma。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List

try:
    from langchain.chains import create_retrieval_chain
    from langchain.chains.combine_documents import create_stuff_documents_chain
except ModuleNotFoundError:  # LangChain 1.x moved legacy chains to langchain_classic.
    from langchain_classic.chains import create_retrieval_chain
    from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ModuleNotFoundError:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from app.services.mimo_client import create_mimo_chat_model_from_env


DEFAULT_EMBEDDING_MODEL = os.getenv(
    "RAG_EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
DEFAULT_CHROMA_DIR = os.getenv("RAG_CHROMA_DIR", "data/chroma_db")
DEFAULT_COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "pdf_knowledge")
DEFAULT_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "800"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
DEFAULT_MAX_PROMPT_TOKENS = int(os.getenv("RAG_MAX_PROMPT_TOKENS", "3000"))
DEFAULT_TOP_K = int(os.getenv("RAG_RETRIEVE_TOP_K", "3"))
FALLBACK_NOTICE = "【系统提示：因文档较长，已自动为您切换至云端 MiMo 深度思考引擎】"


def _build_text_splitter(
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> RecursiveCharacterTextSplitter:
    """创建文本切分器，优先适配中英文混合 PDF 内容。"""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
        keep_separator=True,
    )


def ingest_pdf(
    file_path: str,
    persist_directory: str = DEFAULT_CHROMA_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> Dict[str, Any]:
    """
    读取 PDF，切分为 chunks，计算向量后存入本地 Chroma。

    Args:
        file_path: PDF 文件路径。
        persist_directory: Chroma 本地持久化目录。
        collection_name: Chroma 集合名称。
        embedding_model_name: 轻量级 embedding 模型名称。
        chunk_size: 每个文本块最大字符数。
        chunk_overlap: 邻接文本块重叠字符数。

    Returns:
        Dict[str, Any]: 入库结果摘要信息。
    """
    pdf_path = Path(file_path).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"仅支持 PDF 文件，当前后缀: {pdf_path.suffix}")

    # 1) PDF 加载：按页读取，保留页级元数据
    loader = PyPDFLoader(str(pdf_path))
    page_docs = loader.load()
    if not page_docs:
        raise ValueError(f"PDF 解析结果为空: {pdf_path}")

    # 2) 文本切分：参考 Langchain-Chatchat 的“先文档后切块”策略
    splitter = _build_text_splitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(page_docs)
    if not chunks:
        raise ValueError(f"文本切分结果为空: {pdf_path}")

    # 补充来源信息，方便后续检索结果追溯
    for chunk in chunks:
        chunk.metadata["source"] = str(pdf_path)

    # 3) 向量化 + 本地入库：使用轻量开源 embedding 模型与持久化 Chroma
    embeddings = HuggingFaceEmbeddings(model_name=embedding_model_name)
    db_dir = Path(persist_directory).expanduser().resolve()
    db_dir.mkdir(parents=True, exist_ok=True)

    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(db_dir),
    )
    inserted_ids: List[str] = vector_store.add_documents(chunks)
    vector_store.persist()

    return {
        "file_path": str(pdf_path),
        "pages": len(page_docs),
        "chunks": len(chunks),
        "inserted_ids": len(inserted_ids),
        "persist_directory": str(db_dir),
        "collection_name": collection_name,
        "embedding_model": embedding_model_name,
    }


def _build_embeddings(
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> HuggingFaceEmbeddings:
    """构建轻量向量模型实例。"""
    return HuggingFaceEmbeddings(model_name=embedding_model_name)


def _load_vector_store(
    persist_directory: str = DEFAULT_CHROMA_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> Chroma:
    """加载本地持久化 Chroma。"""
    db_dir = Path(persist_directory).expanduser().resolve()
    if not db_dir.exists():
        raise FileNotFoundError(f"Chroma 目录不存在: {db_dir}")
    return Chroma(
        collection_name=collection_name,
        embedding_function=_build_embeddings(embedding_model_name),
        persist_directory=str(db_dir),
    )


def _estimate_tokens(text: str) -> int:
    """
    估算文本 token 数，优先使用 tiktoken，失败时使用启发式估算。
    说明：中文 1 字符约 1 token，英文大致 3~4 字符约 1 token。
    """
    if not text:
        return 0

    try:
        import tiktoken

        encoder = tiktoken.get_encoding("cl100k_base")
        return len(encoder.encode(text))
    except Exception:
        cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        non_cjk_chars = max(len(text) - cjk_chars, 0)
        return cjk_chars + max(non_cjk_chars // 4, 1)


def _mimo_fallback_llm() -> BaseChatModel:
    """创建云端 MiMo 对话模型，用于长文档保护降级。"""
    return create_mimo_chat_model_from_env()


def _stream_answer(
    llm: BaseChatModel,
    query: str,
    retriever_docs: Iterable[Document],
) -> Generator[str, None, None]:
    """把检索上下文交给问答链，并以流式增量返回。"""
    qa_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是链易配知识助手。请仅基于给定上下文回答；"
                "如果上下文不足，请明确说明无法从文档中确定。",
            ),
            (
                "human",
                "问题：{input}\n\n"
                "上下文：\n{context}\n\n"
                "请给出准确、简洁的中文回答。",
            ),
        ]
    )
    combine_chain = create_stuff_documents_chain(llm, qa_prompt)

    # 使用 create_retrieval_chain 的等价链式范式：
    # 先完成检索，再将文档喂给 combine chain，并保持流式输出。
    for chunk in combine_chain.stream({"input": query, "context": list(retriever_docs)}):
        if not chunk:
            continue
        yield str(chunk)


def ask_with_context(
    query: str,
    llm_instance: BaseChatModel,
    persist_directory: str = DEFAULT_CHROMA_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
    top_k: int = DEFAULT_TOP_K,
    max_prompt_tokens: int = DEFAULT_MAX_PROMPT_TOKENS,
) -> Generator[str, None, None]:
    """
    从 Chroma 检索 Top-K 文本块，并进行流式问答。

    关键策略：
    1) 在拼接 Prompt 前先估算 query + context token 总量；
    2) 若超过阈值，则强制降级到 MiMo，避免本地 8GB 显存 OOM；
    3) 首条返回系统提示，告知已自动切换云端引擎。
    """
    clean_query = (query or "").strip()
    if not clean_query:
        raise ValueError("query 不能为空")

    vector_store = _load_vector_store(
        persist_directory=persist_directory,
        collection_name=collection_name,
        embedding_model_name=embedding_model_name,
    )

    retriever = vector_store.as_retriever(search_kwargs={"k": top_k})
    docs = retriever.invoke(clean_query)
    if not docs:
        yield "知识库中暂无相关内容，请先导入文档后再试。"
        return

    context_tokens = sum(_estimate_tokens(doc.page_content) for doc in docs)
    query_tokens = _estimate_tokens(clean_query)
    total_tokens = context_tokens + query_tokens

    answer_llm: BaseChatModel = llm_instance
    if total_tokens > max_prompt_tokens:
        # 显存保护：超阈值即强制走云端 MiMo
        answer_llm = _mimo_fallback_llm()
        yield FALLBACK_NOTICE

    # 保留 retrieval chain 的构建逻辑，便于后续扩展重排器/过滤器
    _ = create_retrieval_chain(retriever, create_stuff_documents_chain(answer_llm, ChatPromptTemplate.from_messages([
        ("system", "请基于检索到的上下文回答用户问题。"),
        ("human", "{input}\n\n{context}"),
    ])))

    yield from _stream_answer(
        llm=answer_llm,
        query=clean_query,
        retriever_docs=docs,
    )
