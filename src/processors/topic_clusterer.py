"""
Topic Clustering Component

Uses TF-IDF + HDBSCAN for semantic topic clustering without embeddings.
Generates human-readable labels using LLM (qwen-turbo).

Features:
- TF-IDF vectorization (no embeddings required)
- HDBSCAN density-based clustering (auto-determines cluster count)
- LLM-based cluster labeling (explainable, cheap)
- Statistics tracking (noise ratio, cluster sizes)
- Cache support for repeat clustering

Pattern: Per-config isolation (single language per config = no language mixing)
"""

from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import hdbscan

from src.models.document import Document
from src.processors.llm_processor import LLMProcessor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ClusteringError(Exception):
    """Topic clustering related errors"""
    pass


@dataclass
class TopicCluster:
    """
    Represents a discovered topic cluster

    Contains document IDs, cluster label, and metadata.
    """
    cluster_id: int
    label: str
    document_ids: List[str]
    topic_titles: List[str]
    size: int
    representative_title: str
    created_at: datetime = field(default_factory=datetime.now)


class TopicClusterer:
    """
    Topic clustering using TF-IDF + HDBSCAN + LLM labeling

    Pipeline:
    1. Extract TF-IDF features from document content
    2. Cluster using HDBSCAN (density-based, auto K)
    3. Generate human-readable labels using LLM

    No embeddings required (per-config = single language isolation).
    """

    def __init__(
        self,
        cache_dir: str = "cache/topic_clustering",
        min_cluster_size: int = 2,
        min_samples: int = 1,
        max_features: int = 5000,
        model: str = "qwen/qwen-2.5-7b-instruct"
    ):
        """
        Initialize Topic Clusterer

        Args:
            cache_dir: Directory for caching clustering results
            min_cluster_size: Minimum documents per cluster (HDBSCAN param)
            min_samples: Minimum samples for core point (HDBSCAN param)
            max_features: Maximum TF-IDF features (vocabulary size)
            model: LLM model for cluster labeling
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.max_features = max_features

        # Initialize TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            stop_words='english',  # Basic stop words (multilingual OK)
            ngram_range=(1, 2),    # Unigrams + bigrams
            min_df=1,              # Minimum document frequency (count, not ratio)
            max_df=1.0             # Maximum document frequency (allow all terms)
        )

        # Initialize HDBSCAN clusterer
        self.clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric='euclidean',
            cluster_selection_method='eom'  # Excess of Mass (more stable)
        )

        # Initialize LLM processor for labeling
        self.llm_processor = LLMProcessor(model=model)

        # Statistics tracking
        self.last_cluster_labels = None
        self.last_stats = {
            "total_documents": 0,
            "total_clusters": 0,
            "noise_count": 0,
            "noise_ratio": 0.0,
            "largest_cluster_size": 0
        }

        logger.info(
            "TopicClusterer initialized",
            cache_dir=str(self.cache_dir),
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            max_features=max_features
        )

    def _extract_features(self, documents: List[Document]) -> tuple[np.ndarray, List[str]]:
        """
        Extract TF-IDF features from documents

        Args:
            documents: List of Document objects

        Returns:
            Tuple of (feature_matrix, titles)

        Raises:
            ClusteringError: If fewer than 2 documents provided
        """
        if len(documents) < 2:
            raise ClusteringError("Clustering requires at least 2 documents")

        # Combine title + content for better semantic understanding
        texts = [f"{doc.title} {doc.content}" for doc in documents]
        titles = [doc.title for doc in documents]

        # Fit and transform documents to TF-IDF matrix
        try:
            features = self.vectorizer.fit_transform(texts)
            logger.info(
                "TF-IDF features extracted",
                num_documents=len(documents),
                num_features=features.shape[1]
            )
            return features, titles

        except Exception as e:
            logger.error("TF-IDF extraction failed", error=str(e))
            raise ClusteringError(f"TF-IDF extraction failed: {e}")

    def _cluster_features(self, features: np.ndarray) -> np.ndarray:
        """
        Cluster documents using HDBSCAN

        Args:
            features: TF-IDF feature matrix

        Returns:
            Cluster labels (cluster_id for each document, -1 = noise)
        """
        try:
            # Fit HDBSCAN
            labels = self.clusterer.fit_predict(features)

            # Count clusters (excluding noise -1)
            num_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            noise_count = list(labels).count(-1)

            logger.info(
                "HDBSCAN clustering complete",
                num_clusters=num_clusters,
                noise_count=noise_count,
                noise_ratio=noise_count / len(labels) if len(labels) > 0 else 0.0
            )

            return labels

        except Exception as e:
            logger.error("HDBSCAN clustering failed", error=str(e))
            raise ClusteringError(f"HDBSCAN clustering failed: {e}")

    def _generate_cluster_labels(self, topics_by_cluster: Dict[int, List[str]]) -> Dict[int, str]:
        """
        Generate human-readable labels for clusters using LLM

        Args:
            topics_by_cluster: Map of cluster_id -> list of topic titles

        Returns:
            Map of cluster_id -> human-readable label

        Fallback: If LLM fails, generates generic labels ("Cluster 0", "Cluster 1", etc.)
        """
        labels = {}

        try:
            # Group all topics for batch labeling
            all_topics = []
            cluster_ids = []

            for cluster_id, topics in topics_by_cluster.items():
                all_topics.extend(topics[:10])  # Limit to first 10 topics per cluster
                cluster_ids.append(cluster_id)

            # Call LLM to generate labels
            result = self.llm_processor.cluster_topics(all_topics)

            # Parse LLM response
            if "clusters" in result:
                for i, cluster_data in enumerate(result["clusters"]):
                    if i < len(cluster_ids):
                        cluster_id = cluster_ids[i]
                        labels[cluster_id] = cluster_data.get("cluster", f"Cluster {cluster_id}")

            # Fill missing labels
            for cluster_id in topics_by_cluster.keys():
                if cluster_id not in labels:
                    labels[cluster_id] = f"Cluster {cluster_id}"

            logger.info("Cluster labels generated", num_labels=len(labels))

        except Exception as e:
            logger.warning("LLM label generation failed, using fallback", error=str(e))

            # Fallback to generic labels
            for cluster_id in topics_by_cluster.keys():
                labels[cluster_id] = f"Cluster {cluster_id}"

        return labels

    def cluster_documents(self, documents: List[Document]) -> List[TopicCluster]:
        """
        Cluster documents by semantic similarity

        Args:
            documents: List of Document objects to cluster

        Returns:
            List of TopicCluster objects (excluding noise points)

        Raises:
            ClusteringError: If clustering fails or < 2 documents provided
        """
        if len(documents) < 2:
            raise ClusteringError("Clustering requires at least 2 documents")

        logger.info("Starting topic clustering", num_documents=len(documents))

        # Step 1: Extract TF-IDF features
        features, titles = self._extract_features(documents)

        # Step 2: Cluster with HDBSCAN
        cluster_labels = self._cluster_features(features.toarray())  # Convert sparse to dense

        # Step 3: Group documents by cluster
        clusters_dict: Dict[int, List[int]] = {}  # cluster_id -> list of doc indices
        for idx, cluster_id in enumerate(cluster_labels):
            if cluster_id != -1:  # Exclude noise
                if cluster_id not in clusters_dict:
                    clusters_dict[cluster_id] = []
                clusters_dict[cluster_id].append(idx)

        # Step 4: Generate cluster labels using LLM
        topics_by_cluster = {
            cluster_id: [titles[idx] for idx in doc_indices]
            for cluster_id, doc_indices in clusters_dict.items()
        }

        cluster_label_map = self._generate_cluster_labels(topics_by_cluster)

        # Step 5: Create TopicCluster objects
        clusters = []
        for cluster_id, doc_indices in clusters_dict.items():
            cluster_docs = [documents[idx] for idx in doc_indices]
            cluster_titles = [titles[idx] for idx in doc_indices]

            cluster = TopicCluster(
                cluster_id=cluster_id,
                label=cluster_label_map.get(cluster_id, f"Cluster {cluster_id}"),
                document_ids=[doc.id for doc in cluster_docs],
                topic_titles=cluster_titles,
                size=len(cluster_docs),
                representative_title=cluster_titles[0]  # First title as representative
            )
            clusters.append(cluster)

        # Update statistics
        self.last_cluster_labels = cluster_labels
        noise_count = list(cluster_labels).count(-1)
        self.last_stats = {
            "total_documents": len(documents),
            "total_clusters": len(clusters),
            "noise_count": noise_count,
            "noise_ratio": noise_count / len(documents) if len(documents) > 0 else 0.0,
            "largest_cluster_size": max([c.size for c in clusters]) if clusters else 0
        }

        logger.info(
            "Topic clustering complete",
            total_clusters=len(clusters),
            noise_count=noise_count,
            noise_ratio=self.last_stats["noise_ratio"]
        )

        return clusters

    def get_stats(self) -> Dict:
        """
        Get clustering statistics

        Returns:
            Dictionary with statistics:
            - total_documents: Number of documents clustered
            - total_clusters: Number of clusters discovered
            - noise_count: Number of noise points (unclustered)
            - noise_ratio: Ratio of noise points (0-1)
            - largest_cluster_size: Size of largest cluster
        """
        return self.last_stats.copy()
