"""
RAG (Retrieval-Augmented Generation) for Long Context Management.

Features:
- Vector embeddings for code/documents
- Semantic search for relevant context
- Incremental indexing
- Hybrid search (keyword + semantic)
- Code-aware chunking
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

import numpy as np
from ..workspace import WorkspaceManager, get_workspace, Project


# ═════════════════════════════════════════════════════════════════════════════
# Data Models
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class DocumentChunk:
    """A chunk of text with its embedding."""
    id: str
    project_id: str
    file_path: str
    content: str
    start_line: int
    end_line: int
    language: str
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    hash: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.hash:
            self.hash = hashlib.sha256(self.content.encode()).hexdigest()[:16]


@dataclass
class SearchResult:
    """Result from semantic search."""
    chunk: DocumentChunk
    score: float
    match_type: str  # "semantic", "keyword", "hybrid"


@dataclass
class IndexStats:
    """Statistics about the index."""
    total_chunks: int
    total_files: int
    total_tokens: int
    languages: Dict[str, int]
    index_size_mb: float
    last_updated: Optional[datetime] = None


# ═════════════════════════════════════════════════════════════════════════════
# Embedding Provider
# ═════════════════════════════════════════════════════════════════════════════

class EmbeddingProvider:
    """Abstract base for embedding providers."""
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a list of texts."""
        raise NotImplementedError()
    
    def embed_single(self, text: str) -> np.ndarray:
        return self.embed([text])[0]
    
    @property
    def dimension(self) -> int:
        raise NotImplementedError()
    
    @property
    def name(self) -> str:
        raise NotImplementedError()


class SentenceTransformerEmbedding(EmbeddingProvider):
    """SentenceTransformer-based embeddings (local, free)."""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)
        except ImportError:
            raise ImportError("sentence-transformers not installed. Install with: pip install sentence-transformers")
    
    def embed(self, texts: List[str]) -> np.ndarray:
        return self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    
    @property
    def dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()
    
    @property
    def name(self) -> str:
        return "sentence-transformers"


class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI embeddings API."""
    
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        import openai
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model
    
    def embed(self, texts: List[str]) -> np.ndarray:
        response = self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        embeddings = [np.array(d.embedding) for d in response.data]
        return np.array(embeddings)
    
    @property
    def dimension(self) -> int:
        return 1536 if "small" in self._model else 3072
    
    @property
    def name(self) -> str:
        return f"openai-{self._model}"


class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI embeddings API."""
    
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        import openai
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model
    
    def embed(self, texts: List[str]) -> np.ndarray:
        response = self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        embeddings = [np.array(d.embedding) for d in response.data]
        return np.array(embeddings)
    
    @property
    def dimension(self) -> int:
        return 1536 if "small" in self._model else 3072
    
    @property
    def name(self) -> str:
        return f"openai-{self._model}"


# ══════════════════════════════════════════════════════════════════════════════
# Vector Index (FAISS-based)
# ═════════════════════════════════════════════════════════════════════════════

class VectorIndex:
    """
    FAISS-based vector index for semantic search.
    
    Features:
    - IVF (Inverted File) for fast approximate search
    - HNSW for high-recall exact search
    - Incremental updates
    - Persistence to disk
    """
    
    def __init__(
        self,
        dimension: int,
        index_path: Optional[str] = None,
        use_hnsw: bool = True,
    ):
        try:
            import faiss
            self._faiss = faiss
        except ImportError:
            raise ImportError("faiss not installed. Install with: pip install faiss-cpu")
        
        self._dimension = dimension
        self._index_path = Path(index_path) if index_path else None
        
        if use_hnsw:
            # HNSW for high-recall, fast search
            self._index = faiss.IndexHNSWFlat(dimension, 32)
            self._index.hnsw.efConstruction = 200
            self._index.hnsw.efSearch = 128
        else:
            # IVF for larger datasets
            nlist = 100
            quantizer = faiss.IndexFlatL2(dimension)
            self._index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_L2)
        
        self._id_to_chunk: Dict[int, str] = {}  # faiss_id -> chunk_id
        self._chunk_ids: List[str] = []
        
        if self._index_path and self._index_path.exists():
            self.load()
    
    def add(self, embeddings: np.ndarray, chunk_ids: List[str]) -> None:
        """Add embeddings to the index."""
        if len(embeddings) != len(chunk_ids):
            raise ValueError("Embeddings and chunk_ids must have same length")
        
        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Add to index
        start_id = len(self._chunk_ids)
        self._index.add(embeddings)
        
        # Track chunk IDs
        for i, chunk_id in enumerate(chunk_ids):
            self._id_to_chunk[start_id + i] = chunk_id
        self._chunk_ids.extend(chunk_ids)
    
    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
    ) -> List[Tuple[str, float]]:
        """Search for nearest neighbors."""
        if len(self._chunk_ids) == 0:
            return []
        
        # Normalize query
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(query_embedding)
        
        # Search
        distances, indices = self._index.search(query_embedding, min(k, len(self._chunk_ids)))
        
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx >= 0 and idx < len(self._chunk_ids):
                chunk_id = self._chunk_ids[idx]
                # Convert L2 distance to similarity score (0-1)
                score = 1.0 / (1.0 + dist)
                results.append((chunk_id, score))
        
        return results
    
    def remove(self, chunk_ids: List[str]) -> None:
        """Remove chunks from index (mark as deleted, rebuild if needed)."""
        # FAISS doesn't support efficient removal, mark for rebuild
        # In production, use a tombstone approach or periodic rebuild
        pass
    
    def save(self, path: Optional[str] = None) -> None:
        """Save index to disk."""
        path = Path(path) if path else self._index_path
        if not path:
            return
        
        import faiss
        faiss.write_index(self._index, str(path))
        
        # Save metadata
        meta_path = path.with_suffix(".meta.json")
        meta = {
            "chunk_ids": self._chunk_ids,
            "dimension": self._dimension,
        }
        path.with_suffix(".meta.json").write_text(json.dumps(meta))
    
    def load(self, path: Optional[str] = None) -> None:
        """Load index from disk."""
        path = Path(path) if path else self._index_path
        if not path or not path.exists():
            return
        
        import faiss
        self._index = faiss.read_index(str(path))
        
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            self._chunk_ids = meta.get("chunk_ids", [])
            self._dimension = meta.get("dimension", self._dimension)
            
            # Rebuild id_to_chunk
            self._id_to_chunk = {i: cid for i, cid in enumerate(self._chunk_ids)}
    
    @property
    def size(self) -> int:
        return len(self._chunk_ids)
    
    @property
    def dimension(self) -> int:
        return self._dimension


# ══════════════════════════════════════════════════════════════════════════════
# Code-Aware Chunking
# ═════════════════════════════════════════════════════════════════════════════

class CodeChunker:
    """
    Language-aware code chunking.
    
    Strategies:
    - AST-based for Python, JavaScript, TypeScript
    - Regex-based for other languages
    - Preserves function/class boundaries
    - Overlapping chunks for context
    """
    
    # Language-specific patterns
    LANGUAGE_PATTERNS = {
        "python": {
            "class": r"^class\s+\w+",
            "function": r"^\s*def\s+\w+",
            "async_function": r"^\s*async\s+def\s+\w+",
        },
        "javascript": {
            "class": r"^\s*class\s+\w+",
            "function": r"^\s*(async\s+)?function\s+\w+",
            "arrow_function": r"^\s*(const|let|var)\s+\w+\s*=\s*(async\s+)?\s*\(",
        },
        "typescript": {
            "class": r"^\s*class\s+\w+",
            "function": r"^\s*(async\s+)?function\s+\w+",
            "arrow_function": r"^\s*(const|let|var)\s+\w+\s*:\s*\w+\s*=\s*(async\s+)?\s*\(",
            "interface": r"^\s*interface\s+\w+",
            "type": r"^\s*type\s+\w+",
        },
        "rust": {
            "struct": r"^\s*struct\s+\w+",
            "enum": r"^\s*enum\s+\w+",
            "fn": r"^\s*(async\s+)?fn\s+\w+",
            "impl": r"^\s*impl\s+\w+",
            "trait": r"^\s*trait\s+\w+",
        },
        "go": {
            "func": r"^\s*func\s+\w+",
            "struct": r"^\s*type\s+\w+\s+struct",
            "interface": r"^\s*type\s+\w+\s+interface",
        },
    }
    
    def __init__(
        self,
        max_chunk_size: int = 2000,
        overlap: int = 200,
        min_chunk_size: int = 100,
    ):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size
    
    def chunk_file(
        self,
        file_path: str,
        content: str,
        language: str,
    ) -> List[Dict[str, Any]]:
        """
        Chunk a file into logical segments.
        
        Returns:
            List of chunks with start_line, end_line, content
        """
        lines = content.split("\n")
        patterns = self.LANGUAGE_PATTERNS.get(language.lower(), {})
        
        # Find all definition boundaries
        boundaries = []
        for i, line in enumerate(lines):
            for pattern in patterns.values():
                import re
                if re.match(pattern, line):
                    boundaries.append(i)
        
        if not boundaries:
            # Fallback: simple chunking by size
            return self._chunk_by_size(lines)
        
        # Create chunks from boundaries
        chunks = []
        for i, start in enumerate(boundaries):
            end = boundaries[i + 1] - 1 if i + 1 < len(boundaries) else len(lines) - 1
            
            chunk_lines = lines[start:end + 1]
            content = "\n".join(chunk_lines)
            
            if len(content) > self.max_chunk_size:
                # Split large chunks
                sub_chunks = self._chunk_by_size(chunk_lines)
                for j, sub in enumerate(sub_chunks):
                    chunks.append({
                        "start_line": start + sum(len(s.split("\n")) for s in chunks[-j:] if isinstance(s, str)),
                        "end_line": end,
                        "content": sub,
                    })
            else:
                chunks.append({
                    "start_line": start + 1,
                    "end_line": end + 1,
                    "content": content,
                })
        
        return chunks
    
    def _chunk_by_size(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Simple size-based chunking with overlap."""
        chunks = []
        content = "\n".join(lines)
        
        for i in range(0, len(content), self.max_chunk_size - self.overlap):
            chunk = content[i:i + self.max_chunk_size]
            if len(chunk) >= self.min_chunk_size:
                chunks.append({
                    "start_line": 1,  # Approximate
                    "end_line": len(lines),
                    "content": chunk,
                })
        
        return chunks


# ══════════════════════════════════════════════════════════════════════════════
# RAG Manager
# ═════════════════════════════════════════════════════════════════════════════

class RAGManager:
    """
    Main RAG (Retrieval-Augmented Generation) manager.
    
    Features:
    - Incremental indexing of project files
    - Semantic + keyword hybrid search
    - Code-aware chunking
    - Incremental updates
    - Selective context injection
    """
    
    def __init__(
        self,
        project: Project,
        embedding_provider: Optional[EmbeddingProvider] = None,
        workspace: Optional[WorkspaceManager] = None,
    ):
        self._project = project
        self._workspace = workspace or get_workspace()
        self._project_dir = Path(project.root_dir)
        
        # Initialize embedding provider
        self._embedding = embedding_provider or SentenceTransformerEmbedding()
        
        # Initialize components
        self._index = VectorIndex(self._embedding.dimension)
        self._chunker = CodeChunker()
        
        # Chunk storage
        self._chunks: Dict[str, DocumentChunk] = {}
        self._chunk_metadata: Dict[str, Dict] = {}
        
        # Load existing index
        self._load_index()
    
    # ----------------------------------------------------------------------
    # Index Management
    # ----------------------------------------------------------------------
    
    def _get_index_path(self) -> Path:
        return self._project_dir / ".emergentsh" / "rag_index"
    
    def _load_index(self) -> None:
        """Load existing index from disk."""
        index_path = self._get_index_path()
        if index_path.exists():
            try:
                self._index.load(index_path)
                # Load chunk metadata
                meta_path = index_path.with_suffix(".chunks.json")
                if meta_path.exists():
                    data = json.loads(meta_path.read_text())
                    self._chunks = {k: DocumentChunk(**v) for k, v in data.items()}
            except Exception as e:
                print(f"Failed to load RAG index: {e}")
    
    def _save_index(self) -> None:
        """Save index to disk."""
        index_path = self._get_index_path()
        index_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._index.save(index_path)
        
        # Save chunk metadata
        meta_path = index_path.with_suffix(".chunks.json")
        meta_path.write_text(json.dumps({
            k: {
                "id": c.id,
                "project_id": c.project_id,
                "file_path": c.file_path,
                "content": c.content,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "language": c.language,
                "embedding": c.embedding.tolist() if c.embedding is not None else None,
                "metadata": c.metadata,
                "hash": c.hash,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for k, c in self._chunks.items()
        }, indent=2))
    
    # ----------------------------------------------------------------------
    # Indexing
    # ----------------------------------------------------------------------
    
    def index_project(self, force: bool = False) -> int:
        """
        Index all files in the project.
        
        Returns:
            Number of chunks indexed
        """
        files = self._get_project_files()
        indexed = 0
        
        for file_path in files:
            try:
                indexed += self._index_file(file_path, force)
            except Exception as e:
                print(f"Failed to index {file_path}: {e}")
        
        self._save_index()
        return indexed
    
    def _get_project_files(self) -> List[str]:
        """Get all indexable files in the project."""
        files = []
        exclude_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".expo"}
        exclude_exts = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".zip", ".tar", ".gz"}
        
        for root, dirs, files in os.walk(self._project_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
            
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in exclude_exts:
                    continue
                
                full_path = Path(root) / file
                try:
                    rel_path = full_path.relative_to(self._project_dir)
                    files.append(str(rel_path))
                except ValueError:
                    pass
        
        return files
    
    def _index_file(self, file_path: str, force: bool = False) -> int:
        """Index a single file."""
        full_path = self._project_dir / file_path
        if not full_path.exists():
            return 0
        
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return 0
        
        # Check if file changed
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        existing = self._chunks.get(file_path)
        if existing and existing.hash == file_hash and not force:
            return 0
        
        # Determine language
        language = self._detect_language(file_path)
        
        # Chunk the file
        chunks = self._chunker.chunk_file(file_path, content, language)
        
        if not chunks:
            return 0
        
        # Create chunk objects
        chunk_ids = []
        chunk_contents = []
        
        for i, chunk_data in enumerate(chunks):
            chunk_id = f"{file_path}#{i}"
            chunk = DocumentChunk(
                id=chunk_id,
                project_id=self._project.id,
                file_path=file_path,
                content=chunk_data["content"],
                start_line=chunk_data["start_line"],
                end_line=chunk_data["end_line"],
                language=language,
                metadata={"file_hash": file_hash},
            )
            self._chunks[chunk_id] = chunk
            chunk_ids.append(chunk_id)
            chunk_contents.append(chunk_data["content"])
        
        # Generate embeddings
        if chunk_contents:
            embeddings = self._embedding.embed(chunk_contents)
            for chunk_id, embedding in zip(chunk_ids, embeddings):
                self._chunks[chunk_id].embedding = embedding
            
            # Add to vector index
            self._index.add(embeddings, chunk_ids)
        
        return len(chunks)
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".clj": "clojure",
            ".rs": "rust",
            ".dart": "dart",
        }
        return lang_map.get(ext, "text")
    
    # ----------------------------------------------------------------------
    # Search
    # ----------------------------------------------------------------------
    
    def search(
        self,
        query: str,
        k: int = 10,
        filter_languages: Optional[List[str]] = None,
        filter_file_paths: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """
        Hybrid search: semantic + keyword.
        """
        # Semantic search
        query_embedding = self._embedding.embed_single(query)
        semantic_results = self._index.search(query_embedding, k * 3)
        
        # Filter results
        results = []
        for chunk_id, score in semantic_results:
            chunk = self._chunks.get(chunk_id)
            if not chunk:
                continue
            
            # Apply filters
            if filter_languages and chunk.language not in filter_languages:
                continue
            if filter_file_paths and chunk.file_path not in filter_file_paths:
                continue
            
            # Keyword boost
            keyword_score = self._keyword_score(query, chunk.content)
            hybrid_score = 0.7 * score + 0.3 * keyword_score
            
            results.append(SearchResult(
                chunk=chunk,
                score=hybrid_score,
                match_type="hybrid",
            ))
        
        # Sort by hybrid score
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:k]
    
    def _keyword_score(self, query: str, content: str) -> float:
        """Simple keyword matching score."""
        query_terms = set(query.lower().split())
        content_terms = set(content.lower().split())
        
        if not query_terms:
            return 0.0
        
        matches = len(query_terms & content_terms)
        return matches / len(query_terms)
    
    def search_by_file(self, file_path: str, k: int = 5) -> List[SearchResult]:
        """Search within a specific file."""
        return self.search("", k=k, filter_file_paths=[file_path])
    
    def get_file_chunks(self, file_path: str) -> List[DocumentChunk]:
        """Get all chunks for a file."""
        return [c for c in self._chunks.values() if c.file_path == file_path]
    
    # ----------------------------------------------------------------------
    # Selective Context Injection
    # ----------------------------------------------------------------------
    
    def get_relevant_context(
        self,
        query: str,
        max_tokens: int = 8000,
        agent_role: Optional[str] = None,
    ) -> str:
        """
        Get relevant context for a query, optimized for token budget.
        
        Strategy:
        1. Search for relevant chunks
        2. Prioritize by agent role
        3. Fit within token budget
        4. Return formatted context
        """
        # Adjust search based on agent role
        search_query = query
        if agent_role == "frontend":
            search_query += " component UI react"
        elif agent_role == "backend":
            search_query += " api database"
        elif agent_role == "devops":
            search_query += " docker kubernetes deploy"
        
        # Search for relevant chunks
        results = self.search(query, k=20)
        
        # Filter by role-relevant languages
        role_languages = {
            "frontend": ["typescript", "javascript", "tsx", "jsx", "css", "scss"],
            "backend": ["python", "go", "rust", "java", "sql"],
            "devops": ["yaml", "dockerfile", "tf", "hcl"],
        }
        
        filter_langs = role_languages.get(agent_role, None)
        
        # Build context within token budget
        context_parts = []
        token_count = 0
        
        for result in results:
            if filter_langs and result.chunk.language not in filter_langs:
                continue
            
            chunk_text = self._format_chunk(result.chunk)
            chunk_tokens = len(chunk_text) // 4  # Rough estimate
            
            if token_count + chunk_tokens > max_tokens:
                break
            
            context_parts.append(chunk_text)
            token_count += chunk_tokens
        
        return "\n\n---\n\n".join(context_parts)
    
    def _format_chunk(self, chunk: DocumentChunk) -> str:
        """Format a chunk for context injection."""
        return f"// {chunk.file_path}:{chunk.start_line}-{chunk.end_line}\n{chunk.content}"
    
    # ----------------------------------------------------------------------
    # Incremental Updates
    # ----------------------------------------------------------------------
    
    def update_file(self, file_path: str) -> int:
        """Re-index a single file."""
        full_path = self._project_dir / file_path
        if not full_path.exists():
            # File deleted, remove chunks
            self._remove_file_chunks(file_path)
            return 0
        
        # Re-index
        return self._index_file(file_path, force=True)
    
    def _remove_file_chunks(self, file_path: str) -> None:
        """Remove all chunks for a file."""
        to_remove = [cid for cid, c in self._chunks.items() if c.file_path == file_path]
        for cid in to_remove:
            del self._chunks[cid]
    
    # ----------------------------------------------------------------------
    # Stats
    # ----------------------------------------------------------------------
    
    def get_stats(self) -> IndexStats:
        """Get index statistics."""
        languages = {}
        for chunk in self._chunks.values():
            languages[chunk.language] = languages.get(chunk.language, 0) + 1
        
        index_size = 0
        if self._get_index_path().exists():
            index_size = self._get_index_path().stat().st_size
        
        return IndexStats(
            total_chunks=len(self._chunks),
            total_files=len(set(c.file_path for c in self._chunks.values())),
            total_tokens=sum(len(c.content) // 4 for c in self._chunks.values()),
            languages=languages,
            index_size_mb=index_size / (1024 * 1024),
            last_updated=datetime.now(),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Context Selector
# ═════════════════════════════════════════════════════════════════════════════

class ContextSelector:
    """
    Selects and formats relevant context for agent tasks.
    
    Features:
    - Role-based context prioritization
    - Token budget management
    - Context compression
    - Relevance scoring
    """
    
    def __init__(self, rag_manager: RAGManager):
        self._rag = rag_manager
    
    def get_context_for_task(
        self,
        task_description: str,
        agent_role: str,
        max_tokens: int = 8000,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> str:
        """Get optimized context for a specific task."""
        # Search for relevant context
        results = self._rag.search(
            task_description,
            k=50,
        )
        
        # Filter by relevance to role
        filtered = self._filter_by_role(results, agent_role)
        
        # Apply include/exclude patterns
        if include_patterns:
            filtered = [r for r in filtered if any(p in r.chunk.file_path for p in include_patterns)]
        if exclude_patterns:
            filtered = [r for r in filtered if not any(p in r.chunk.file_path for p in exclude_patterns)]
        
        # Build context within token budget
        context_parts = []
        token_count = 0
        
        for result in filtered:
            chunk_text = self._format_chunk_with_metadata(result.chunk)
            chunk_tokens = len(chunk_text) // 4
            
            if token_count + chunk_tokens > max_tokens:
                break
            
            context_parts.append(chunk_text)
            token_count += chunk_tokens
        
        return "\n\n---\n\n".join(context_parts)
    
    def _filter_by_role(self, results: List[SearchResult], role: str) -> List[SearchResult]:
        """Filter and re-rank results based on agent role."""
        role_keywords = {
            "planner": ["plan", "task", "design", "architecture"],
            "architect": ["architecture", "design", "pattern", "decision"],
            "designer": ["ui", "ux", "component", "style", "theme"],
            "frontend": ["component", "react", "vue", "ui", "css", "component"],
            "backend": ["api", "database", "model", "service", "endpoint"],
            "integration": ["webhook", "api", "third-party", "external"],
            "devops": ["docker", "kubernetes", "deploy", "ci", "cd", "pipeline"],
            "qa": ["test", "spec", "mock", "assert", "coverage"],
            "docs": ["readme", "documentation", "guide", "tutorial"],
        }
        
        keywords = role_keywords.get(role.lower(), [])
        if not keywords:
            return results
        
        # Boost scores for role-relevant results
        for result in results:
            content_lower = result.chunk.content.lower()
            boost = sum(1 for kw in keywords if kw in content_lower)
            if boost > 0:
                result.score = min(1.0, result.score + 0.1 * boost)
        
        # Re-sort
        return sorted(results, key=lambda r: r.score, reverse=True)
    
    def _format_chunk(self, chunk) -> str:
        """Format chunk with metadata for context."""
        return f"// File: {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})\n{chunk.content}"
    
    def _format_chunk_with_metadata(self, chunk) -> str:
        """Format chunk with full metadata."""
        return (
            f"// ==========================================\n"
            f"// File: {chunk.file_path}\n"
            f"// Lines: {chunk.start_line}-{chunk.end_line}\n"
            f"// Language: {chunk.language}\n"
            f"// Hash: {chunk.hash[:8]}\n"
            f"// ==========================================\n"
            f"{chunk.content}"
        )