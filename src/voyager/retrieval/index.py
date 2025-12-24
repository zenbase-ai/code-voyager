"""ColBERT index manager for skill retrieval.

Provides build and search functionality using RAGatouille/ColBERT.
Gracefully degrades to simple text matching when dependencies are unavailable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from voyager.config import get_skill_index_dir
from voyager.logging import get_logger
from voyager.retrieval.analyzer import SkillMetadata, analyze_skill
from voyager.retrieval.discovery import discover_all_skills
from voyager.retrieval.embedding import (
    generate_embedding_text,
    generate_simple_embedding_text,
)

_logger = get_logger("retrieval.index")

# Check if RAGatouille is available
try:
    from ragatouille import RAGPretrainedModel

    RAGATOUILLE_AVAILABLE = True
except ImportError:
    RAGATOUILLE_AVAILABLE = False
    _logger.debug("RAGatouille not available, will use fallback search")


@dataclass
class SearchResult:
    """A single search result."""

    skill_id: str
    name: str
    purpose: str
    path: str
    score: float
    file_types: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)


@dataclass
class IndexMetadata:
    """Metadata stored alongside the index."""

    skills: dict[str, dict]  # skill_id -> metadata
    version: str = "1"
    index_type: str = "colbert"  # or "simple"


class SkillIndex:
    """Manager for skill search index."""

    def __init__(
        self,
        index_path: Path | None = None,
        model_name: str = "colbert-ir/colbertv2.0",
    ):
        """Initialize the skill index.

        Args:
            index_path: Path to store the index. Defaults to ~/.skill-index/
            model_name: ColBERT model to use.
        """
        self.index_path = index_path or get_skill_index_dir()
        self.model_name = model_name
        self.index_name = "claude_skills"

        self._rag = None
        self._metadata: IndexMetadata | None = None

        # Paths
        self._metadata_path = self.index_path / "metadata.json"
        self._simple_index_path = self.index_path / "simple_index.json"
        self._colbert_index_dir = self.index_path / "colbert" / "indexes" / self.index_name

    def build(
        self,
        skill_roots: list[Path] | None = None,
        *,
        force: bool = False,
        skip_llm: bool = False,
        verbose: bool = False,
    ) -> int:
        """Build the skill index.

        Args:
            skill_roots: Root directories to search for skills.
            force: Rebuild even if index exists.
            skip_llm: Skip LLM analysis (faster but lower quality).
            verbose: Print progress.

        Returns:
            Number of skills indexed.
        """
        # Check if rebuild needed
        if not force and self._index_exists():
            if verbose:
                print(f"Index exists at {self.index_path}. Use --rebuild to recreate.")
            return 0

        # Discover skills
        skills = discover_all_skills(roots=skill_roots)
        if not skills:
            _logger.warning("No skills found to index")
            return 0

        if verbose:
            print(f"Found {len(skills)} skills to index")

        # Analyze each skill
        analyzed: list[SkillMetadata] = []
        for i, skill_path in enumerate(skills, 1):
            if verbose:
                print(f"  [{i}/{len(skills)}] Analyzing {skill_path.name}...", end=" ")
            try:
                metadata = analyze_skill(skill_path, skip_llm=skip_llm)
                analyzed.append(metadata)
                if verbose:
                    print("OK")
            except Exception as e:
                if verbose:
                    print(f"FAIL: {e}")
                _logger.warning("Failed to analyze %s: %s", skill_path.name, e)

        if not analyzed:
            _logger.warning("No skills successfully analyzed")
            return 0

        # Generate embedding text
        documents: list[str] = []
        doc_ids: list[str] = []
        metadata_dict: dict[str, dict] = {}

        for skill in analyzed:
            embed_text = (
                generate_embedding_text(skill) if skill.example_queries else generate_simple_embedding_text(skill)
            )
            documents.append(embed_text)
            doc_ids.append(skill.skill_id)
            metadata_dict[skill.skill_id] = {
                "name": skill.name,
                "purpose": skill.purpose,
                "path": str(skill.path),
                "file_types": skill.file_types,
                "capabilities": skill.capabilities,
                "description": skill.description,
                "example_queries": skill.example_queries,
            }

        # Build index
        if RAGATOUILLE_AVAILABLE:
            self._build_colbert_index(documents, doc_ids, metadata_dict, verbose)
        else:
            self._build_simple_index(documents, doc_ids, metadata_dict, verbose)

        return len(analyzed)

    def _build_colbert_index(
        self,
        documents: list[str],
        doc_ids: list[str],
        metadata_dict: dict[str, dict],
        verbose: bool,
    ) -> None:
        """Build ColBERT index using RAGatouille."""
        if verbose:
            print("Building ColBERT index...")

        # Ensure index directory exists
        self.index_path.mkdir(parents=True, exist_ok=True)

        # Create RAG model and index
        self._rag = RAGPretrainedModel.from_pretrained(self.model_name)
        self._rag.index(
            collection=documents,
            document_ids=doc_ids,
            index_name=self.index_name,
            max_document_length=256,
            split_documents=True,
        )

        # Save metadata
        self._metadata = IndexMetadata(skills=metadata_dict, index_type="colbert")
        self._metadata_path.write_text(json.dumps(asdict(self._metadata), indent=2))

        if verbose:
            print(f"ColBERT index built: {len(doc_ids)} skills")

    def _build_simple_index(
        self,
        documents: list[str],
        doc_ids: list[str],
        metadata_dict: dict[str, dict],
        verbose: bool,
    ) -> None:
        """Build simple text-based index as fallback."""
        if verbose:
            print("Building simple text index (RAGatouille not available)...")

        # Ensure index directory exists
        self.index_path.mkdir(parents=True, exist_ok=True)

        # Build simple index: document text + metadata
        simple_index = {
            "documents": dict(zip(doc_ids, documents, strict=True)),
            "metadata": metadata_dict,
        }
        self._simple_index_path.write_text(json.dumps(simple_index, indent=2))

        # Save metadata
        self._metadata = IndexMetadata(skills=metadata_dict, index_type="simple")
        self._metadata_path.write_text(json.dumps(asdict(self._metadata), indent=2))

        if verbose:
            print(f"Simple index built: {len(doc_ids)} skills")

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        """Search for skills matching a query.

        Args:
            query: Natural language search query.
            k: Number of results to return.

        Returns:
            List of SearchResult objects, sorted by relevance.

        Raises:
            RuntimeError: If no index exists.
        """
        if not self._index_exists():
            raise RuntimeError(
                f"No index found. Run `voyager skill index` first.\nExpected index at: {self.index_path}"
            )

        # Load metadata if needed
        if self._metadata is None:
            self._load_metadata()

        # Use appropriate search method
        if self._metadata.index_type == "colbert" and RAGATOUILLE_AVAILABLE:
            return self._search_colbert(query, k)
        else:
            return self._search_simple(query, k)

    def _search_colbert(self, query: str, k: int) -> list[SearchResult]:
        """Search using ColBERT index."""
        if self._rag is None:
            self._rag = RAGPretrainedModel.from_index(str(self._colbert_index_dir))

        results = self._rag.search(query=query, k=k)

        output: list[SearchResult] = []
        for r in results:
            skill_id = r.get("document_id", r.get("doc_id", ""))
            meta = self._metadata.skills.get(skill_id, {})

            output.append(
                SearchResult(
                    skill_id=skill_id,
                    name=meta.get("name", skill_id),
                    purpose=meta.get("purpose", ""),
                    path=meta.get("path", ""),
                    score=r.get("score", 0.0),
                    file_types=meta.get("file_types", []),
                    capabilities=meta.get("capabilities", []),
                )
            )

        return output

    def _search_simple(self, query: str, k: int) -> list[SearchResult]:
        """Search using simple text matching."""
        # Load simple index
        if not self._simple_index_path.exists():
            raise RuntimeError("Simple index file not found")

        index_data = json.loads(self._simple_index_path.read_text())
        documents = index_data["documents"]

        # Simple scoring: count query term matches
        query_terms = set(query.lower().split())
        scores: list[tuple[str, float]] = []

        for skill_id, doc_text in documents.items():
            doc_lower = doc_text.lower()
            # Count term matches + bonus for exact phrase match
            match_count = sum(1 for term in query_terms if term in doc_lower)
            exact_bonus = 2.0 if query.lower() in doc_lower else 0.0
            score = match_count + exact_bonus
            scores.append((skill_id, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        output: list[SearchResult] = []
        for skill_id, score in scores[:k]:
            if score == 0:
                continue
            meta = self._metadata.skills.get(skill_id, {})
            output.append(
                SearchResult(
                    skill_id=skill_id,
                    name=meta.get("name", skill_id),
                    purpose=meta.get("purpose", ""),
                    path=meta.get("path", ""),
                    score=score,
                    file_types=meta.get("file_types", []),
                    capabilities=meta.get("capabilities", []),
                )
            )

        return output

    def _index_exists(self) -> bool:
        """Check if an index exists."""
        return self._metadata_path.exists() or self._simple_index_path.exists()

    def _load_metadata(self) -> None:
        """Load index metadata from disk."""
        if not self._metadata_path.exists():
            # Try to infer from simple index
            if self._simple_index_path.exists():
                index_data = json.loads(self._simple_index_path.read_text())
                self._metadata = IndexMetadata(
                    skills=index_data.get("metadata", {}),
                    index_type="simple",
                )
            else:
                self._metadata = IndexMetadata(skills={}, index_type="unknown")
            return

        data = json.loads(self._metadata_path.read_text())
        self._metadata = IndexMetadata(
            skills=data.get("skills", {}),
            version=data.get("version", "1"),
            index_type=data.get("index_type", "simple"),
        )
