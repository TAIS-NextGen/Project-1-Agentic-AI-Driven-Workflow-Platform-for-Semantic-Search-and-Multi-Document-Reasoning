from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import uuid
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from backend.nodes.ingestion.document_parser import DocumentParserNode
from backend.sdk import BaseNode, ConfigField, ExecutionContext, NodeResult, Port, PortType


class TopicClusteringNode(BaseNode):
    type = "topic-clustering"
    name = "Topic Clustering"
    category = "clustering"
    icon = "🧠"
    color = "#a855f7"
    description = "Group a folder of documents by topic and list the documents in each cluster"
    version = "1.0.0"

    inputs = [
        Port(
            name="corpus",
            type=PortType.CORPUS,
            label="Document Corpus",
            description="Corpus produced by Corpus Input",
            required=True,
        ),
    ]
    outputs = [
        Port(
            name="clusters",
            type=PortType.JSON,
            label="Topic Clusters",
            description="Named clusters with their documents and similarity scores",
        ),
        Port(
            name="assignments",
            type=PortType.TABLE,
            label="Document Assignments",
            description="One row per document with its assigned cluster",
        ),
        Port(
            name="metadata",
            type=PortType.JSON,
            label="Clustering Metadata",
            description="Algorithm, quality score, parsed and skipped document counts",
        ),
        Port(
            name="downloads",
            type=PortType.JSON,
            label="Downloadable Results",
            description="JSON, CSV, and ZIP downloads for the full clustering result",
        ),
    ]

    config_fields = [
        ConfigField(
            key="number_of_clusters",
            label="Number of Clusters",
            type="number",
            default=0,
            description="0 selects the cluster count automatically; otherwise choose 2 or more.",
        ),
        ConfigField(
            key="max_automatic_clusters",
            label="Maximum Automatic Clusters",
            type="number",
            default=8,
            description="Upper bound used only in automatic mode.",
        ),
        ConfigField(
            key="create_downloads",
            label="Create Downloadable Results",
            type="boolean",
            default=True,
            description="Create JSON, CSV, and ZIP result files.",
        ),
    ]

    _SUPPORTED = {".pdf", ".docx", ".xlsx", ".xlsm", ".csv", ".txt", ".md"}
    _STOP_WORDS = {
        # English
        "the", "and", "for", "with", "from", "that", "this", "are", "was", "were", "have", "has",
        "document", "page", "section", "table", "into", "their", "about", "your", "you", "our", "not",
        # French
        "les", "des", "une", "dans", "pour", "avec", "sur", "par", "est", "sont", "plus", "cette", "ces",
        "document", "page", "section", "tableau", "entre", "comme", "mais", "qui", "que", "aux", "du", "de",
        # Arabic common function words
        "من", "في", "على", "إلى", "الى", "عن", "هذا", "هذه", "ذلك", "التي", "الذي", "مع", "كان", "كانت",
        "هو", "هي", "ثم", "أو", "او", "كل", "بعد", "قبل", "بين", "عند", "ما", "لا", "تم", "قد",
    }

    @staticmethod
    def _storage_dir() -> Path:
        return Path(os.getenv("STORAGE_DIR") or os.getenv("SYMPACT_STORAGE_DIR") or "data/storage")

    @staticmethod
    def _safe_stem(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
        return cleaned or "topic-clusters"

    @classmethod
    def _resolve_corpus(cls, ctx: ExecutionContext) -> dict[str, Any] | None:
        direct = ctx.get_input("corpus")
        if isinstance(direct, dict) and isinstance(direct.get("documents"), list):
            return direct
        if isinstance(direct, list):
            return {"name": "Document corpus", "documents": direct, "document_count": len(direct)}

        # Backward-compatible search for a corpus connected under a generic target port.
        for key, value in ctx.inputs.items():
            if key.startswith("__"):
                continue
            if isinstance(value, dict) and isinstance(value.get("documents"), list):
                return value
        return None

    @classmethod
    def _extract_document_text(cls, document: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        path_value = document.get("path") or document.get("file_path")
        if not path_value:
            raise ValueError("missing file path")
        path = Path(str(path_value))
        if not path.exists() or not path.is_file():
            raise ValueError("file not found")
        extension = path.suffix.lower()
        if extension not in cls._SUPPORTED:
            raise ValueError(f"unsupported extension {extension or 'unknown'}")

        if extension == ".pdf":
            text, data = DocumentParserNode._parse_pdf(path, preserve_page_breaks=False)
            if not text.strip() and data.get("requires_ocr"):
                raise ValueError("PDF has no text layer; OCR is required")
            engine = "pypdf"
        elif extension == ".docx":
            text, data = DocumentParserNode._parse_docx(path, include_tables=True, include_headers_footers=True)
            engine = "python-docx"
        elif extension in {".xlsx", ".xlsm"}:
            text, data = DocumentParserNode._parse_xlsx(path, include_tables=True, sheet_name="", max_rows=None)
            engine = "openpyxl"
        elif extension == ".csv":
            text, data = DocumentParserNode._parse_csv(path, include_tables=True, max_rows=None)
            engine = "python-csv"
        else:
            text = DocumentParserNode._read_text_file(path)
            data = {"line_count": len(text.splitlines())}
            engine = "python-text"

        metadata = {
            "engine": engine,
            "character_count": len(text),
            "extension": extension,
            "parser_data": data,
        }
        return text, metadata

    @classmethod
    def _label_terms(cls, word_matrix: Any, feature_names: Any, labels: Any, cluster_id: int) -> list[str]:
        import numpy as np

        indexes = np.where(labels == cluster_id)[0]
        if len(indexes) == 0:
            return []
        weights = np.asarray(word_matrix[indexes].sum(axis=0)).ravel()
        ordered = weights.argsort()[::-1]
        terms: list[str] = []
        for index in ordered:
            if weights[index] <= 0:
                break
            term = str(feature_names[index]).strip()
            normalized = term.casefold()
            if not term or normalized in cls._STOP_WORDS:
                continue
            if all(part.casefold() in cls._STOP_WORDS for part in term.split()):
                continue
            if re.fullmatch(r"[\W\d_]+", term, flags=re.UNICODE):
                continue
            terms.append(term)
            if len(terms) >= 5:
                break
        return terms

    @staticmethod
    def _fit_clusterer(matrix: Any, cluster_count: int, document_count: int) -> tuple[Any, Any]:
        if document_count > 200:
            from sklearn.cluster import MiniBatchKMeans

            model = MiniBatchKMeans(
                n_clusters=cluster_count,
                random_state=42,
                n_init=10,
                batch_size=min(256, document_count),
            )
        else:
            from sklearn.cluster import KMeans

            model = KMeans(n_clusters=cluster_count, random_state=42, n_init=10)
        labels = model.fit_predict(matrix)
        return model, labels

    @classmethod
    def _automatic_cluster_count(cls, matrix: Any, document_count: int, max_clusters: int) -> tuple[int, float | None]:
        from sklearn.metrics import silhouette_score
        from sklearn.metrics.pairwise import cosine_similarity

        if document_count <= 1:
            return 1, None
        if document_count == 2:
            similarity = float(cosine_similarity(matrix[0], matrix[1])[0, 0])
            return (1 if similarity >= 0.42 else 2), None

        upper = min(max(2, max_clusters), document_count - 1)
        best_count = 2
        best_score = -1.0
        for count in range(2, upper + 1):
            _model, labels = cls._fit_clusterer(matrix, count, document_count)
            if len(set(int(label) for label in labels)) < 2:
                continue
            score = float(silhouette_score(matrix, labels, metric="cosine"))
            if score > best_score:
                best_count = count
                best_score = score

        # When every split is extremely weak, a single topic is more honest.
        if best_score < 0.035:
            return 1, best_score
        return best_count, best_score

    @classmethod
    def _create_downloads(
        cls,
        *,
        corpus_name: str,
        clusters: list[dict[str, Any]],
        assignments: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        output_root = cls._storage_dir() / "clustering_outputs"
        output_root.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex[:8]
        stem = cls._safe_stem(corpus_name)
        json_path = output_root / f"{stem}-clusters-{token}.json"
        csv_path = output_root / f"{stem}-assignments-{token}.csv"
        zip_path = output_root / f"{stem}-topic-clustering-{token}.zip"

        json_path.write_text(
            json.dumps({"metadata": metadata, "clusters": clusters, "assignments": assignments}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["cluster_id", "cluster_label", "filename", "relative_path", "similarity", "keywords"],
            )
            writer.writeheader()
            for assignment in assignments:
                writer.writerow({
                    **assignment,
                    "keywords": ", ".join(assignment.get("keywords") or []),
                })

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(json_path, arcname=json_path.name)
            archive.write(csv_path, arcname=csv_path.name)

        def descriptor(path: Path, mime_type: str) -> dict[str, Any]:
            relative = path.relative_to(cls._storage_dir()).as_posix()
            return {
                "filename": path.name,
                "path": str(path),
                "download_url": f"/data/storage/{relative}",
                "mime_type": mime_type,
                "size_bytes": path.stat().st_size,
            }

        return {
            "json": descriptor(json_path, "application/json"),
            "csv": descriptor(csv_path, "text/csv; charset=utf-8"),
            "bundle": descriptor(zip_path, "application/zip"),
        }

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            corpus = self._resolve_corpus(ctx)
            if not corpus:
                result.fail("No document corpus found. Connect a Corpus Input node containing a selected folder.")
                return result

            raw_documents = corpus.get("documents")
            if not isinstance(raw_documents, list) or not raw_documents:
                result.fail("The connected corpus does not contain any documents.")
                return result

            parsed: list[dict[str, Any]] = []
            skipped: list[dict[str, str]] = []
            for raw_document in raw_documents:
                if not isinstance(raw_document, dict):
                    skipped.append({"filename": "unknown", "reason": "invalid document descriptor"})
                    continue
                filename = str(raw_document.get("filename") or Path(str(raw_document.get("path") or "document")).name)
                try:
                    text, parser_metadata = self._extract_document_text(raw_document)
                    cleaned = re.sub(r"\s+", " ", text).strip()
                    if len(cleaned) < 20:
                        raise ValueError("document contains too little text to cluster")
                    parsed.append({
                        "document": raw_document,
                        "filename": filename,
                        "relative_path": str(raw_document.get("relative_path") or filename),
                        "text": cleaned,
                        "parser": parser_metadata,
                    })
                except Exception as exc:
                    skipped.append({"filename": filename, "reason": str(exc)})

            if not parsed:
                result.fail("No parseable text was found in the corpus. Scanned PDFs require OCR before clustering.")
                return result

            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.pipeline import FeatureUnion
            from sklearn.preprocessing import normalize

            texts = [item["text"][:250_000] for item in parsed]
            word_vectorizer = TfidfVectorizer(
                lowercase=True,
                strip_accents="unicode",
                ngram_range=(1, 2),
                max_features=16_000,
                min_df=1,
                max_df=1.0,
                sublinear_tf=True,
                token_pattern=r"(?u)\b[^\W\d_][\w'-]{1,}\b",
            )
            char_vectorizer = TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                max_features=10_000,
                min_df=1,
                max_df=1.0,
                sublinear_tf=True,
            )
            union = FeatureUnion(
                [("words", word_vectorizer), ("characters", char_vectorizer)],
                transformer_weights={"words": 1.0, "characters": 0.35},
            )
            matrix = normalize(union.fit_transform(texts), norm="l2", copy=False)
            word_matrix = word_vectorizer.transform(texts)

            requested = int(config.get("number_of_clusters", 0) or 0)
            max_automatic = max(2, int(config.get("max_automatic_clusters", 8) or 8))
            automatic_score: float | None = None
            if requested <= 0:
                cluster_count, automatic_score = self._automatic_cluster_count(matrix, len(parsed), max_automatic)
                mode = "automatic"
            else:
                cluster_count = max(1, min(requested, len(parsed)))
                mode = "manual"

            if cluster_count == 1:
                import numpy as np

                labels = np.zeros(len(parsed), dtype=int)
                centroid = np.asarray(matrix.mean(axis=0))
                centroids = centroid
                model = None
            else:
                model, labels = self._fit_clusterer(matrix, cluster_count, len(parsed))
                centroids = model.cluster_centers_

            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            similarities = cosine_similarity(matrix, centroids)
            feature_names = word_vectorizer.get_feature_names_out()
            clusters: list[dict[str, Any]] = []
            assignments: list[dict[str, Any]] = []

            for cluster_id in range(cluster_count):
                member_indexes = [index for index, label in enumerate(labels) if int(label) == cluster_id]
                keywords = self._label_terms(word_matrix, feature_names, labels, cluster_id)
                label = " · ".join(keywords[:3]) if keywords else f"Topic {cluster_id + 1}"
                member_documents: list[dict[str, Any]] = []
                for index in member_indexes:
                    item = parsed[index]
                    similarity = float(similarities[index, cluster_id]) if similarities.size else 1.0
                    member = {
                        "file_id": item["document"].get("file_id"),
                        "filename": item["filename"],
                        "relative_path": item["relative_path"],
                        "mime_type": item["document"].get("mime_type"),
                        "extension": item["document"].get("extension") or Path(item["filename"]).suffix.lower(),
                        "similarity": round(max(0.0, min(1.0, similarity)), 4),
                        "character_count": int(item["parser"].get("character_count", len(item["text"]))),
                    }
                    member_documents.append(member)
                    assignments.append({
                        "cluster_id": cluster_id + 1,
                        "cluster_label": label,
                        "filename": item["filename"],
                        "relative_path": item["relative_path"],
                        "similarity": member["similarity"],
                        "keywords": keywords,
                    })

                member_documents.sort(key=lambda item: float(item.get("similarity", 0)), reverse=True)
                clusters.append({
                    "cluster_id": cluster_id + 1,
                    "label": label,
                    "keywords": keywords,
                    "document_count": len(member_documents),
                    "representative_document": member_documents[0]["filename"] if member_documents else None,
                    "documents": member_documents,
                })

            clusters.sort(key=lambda item: (-int(item["document_count"]), str(item["label"])))
            assignments.sort(key=lambda item: (int(item["cluster_id"]), -float(item["similarity"]), str(item["filename"])))

            metadata: dict[str, Any] = {
                "corpus_name": str(corpus.get("name") or "Document corpus"),
                "input_document_count": len(raw_documents),
                "clustered_document_count": len(parsed),
                "skipped_document_count": len(skipped),
                "cluster_count": cluster_count,
                "cluster_count_mode": mode,
                "algorithm": "TF-IDF word/character features + K-Means",
                "quality_score": round(automatic_score, 4) if automatic_score is not None and math.isfinite(automatic_score) else None,
                "skipped_documents": skipped,
            }
            downloads: dict[str, dict[str, Any]] = {}
            if bool(config.get("create_downloads", True)):
                downloads = self._create_downloads(
                    corpus_name=metadata["corpus_name"],
                    clusters=clusters,
                    assignments=assignments,
                    metadata=metadata,
                )

            result.succeed({
                "clusters": clusters,
                "assignments": assignments,
                "metadata": metadata,
                "downloads": downloads,
            })
        except ImportError as exc:
            result.fail(f"Topic clustering dependency missing: {exc}. Install scikit-learn and numpy.")
        except ValueError as exc:
            if "empty vocabulary" in str(exc).lower():
                result.fail("The corpus does not contain enough meaningful text to build topic clusters.")
            else:
                result.fail(str(exc))
        except Exception as exc:
            result.fail(str(exc))

        return result
