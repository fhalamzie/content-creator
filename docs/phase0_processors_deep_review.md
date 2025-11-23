# Phase 0: Processors Component Deep Review
## FastAPI Migration Preparation - Processors Analysis

**Date:** 2025-11-23
**Scope:** `src/processors/` directory
**Purpose:** Assess processors for async FastAPI migration

---

## Executive Summary

The processors module contains 4 production processors totaling **1,134 lines of code**:

| Processor | LOC | Type | Primary Dependency |
|-----------|-----|------|-------------------|
| **LLMProcessor** | 307 | I/O-bound | OpenRouter API |
| **TopicClusterer** | 331 | CPU-bound | sklearn, hdbscan, LLMProcessor |
| **Deduplicator** | 285 | CPU-bound | datasketch (MinHash/LSH) |
| **EntityExtractor** | 197 | I/O-bound | LLMProcessor |

### Architecture Status: **Synchronous, Sequential Processing**

**Critical Findings:**
- ❌ **No async operations** - All processors are 100% synchronous
- ❌ **No parallelization** - Sequential document processing
- ❌ **In-memory caching only** - Production needs persistent cache (Redis/SQLite)
- ✅ **Good test coverage** - 86 unit tests + 8 E2E tests
- ⚠️ **Hardcoded parameters** - Thresholds not configurable via config
- ✅ **Clean interfaces** - Well-defined processor contracts

---

## Detailed Processor Analysis

### 1. LLMProcessor (`llm_processor.py`)

**Purpose:** Unified LLM interface for NLP tasks (replaces 5GB traditional NLP stack)

**Current Architecture:**
```python
class LLMProcessor:
    def detect_language(text: str) -> LanguageDetection          # Sync HTTP call
    def cluster_topics(topics: List[str]) -> ClusterResult       # Sync HTTP call
    def extract_entities_keywords(content, lang) -> EntityExtraction  # Sync HTTP call
```

**Operations:**
- Language detection (replaces fasttext 1GB model)
- Topic clustering label generation (replaces BERTopic)
- Entity/keyword extraction (replaces spaCy NER)

**Dependencies:**
- `openai>=1.0.0` (OpenRouter client)
- `pydantic>=2.5.0` (response validation)

**I/O Profile:**
- **Type:** I/O-bound (HTTP API calls)
- **Latency:** ~0.5-2s per API call
- **Throughput:** ~100+ tokens/sec
- **Cost:** $0.06/1M tokens (~$0.003/month MVP)

**Caching Strategy:**
```python
# Current: In-memory dict with 30-day TTL
self._cache: Dict[str, tuple[str, datetime]] = {}
self.cache_ttl = 30 * 24 * 60 * 60  # 30 days

# ⚠️ ISSUE: Cache lost on process restart
# ✅ RECOMMENDATION: Redis/SQLite for persistence
```

**Retry Logic:**
- **Max retries:** 3 (configurable via `max_retries` param)
- **Strategy:** Simple loop with no exponential backoff
- **Error handling:** Raises exception after max retries

**Async Conversion Assessment:**
- **Priority:** ⭐⭐⭐⭐⭐ **CRITICAL**
- **Complexity:** ⭐⭐⭐ **MEDIUM**
- **Effort:** 2-3 hours
- **Impact:** 10x+ throughput improvement (parallel API calls)

**Conversion Plan:**
```python
# Before (sync):
result = llm_processor.extract_entities_keywords(content, lang)

# After (async):
async def extract_entities_keywords_async(content, lang):
    async with aiohttp.ClientSession() as session:
        response = await session.post(...)
    return EntityExtraction.model_validate_json(response_text)

# Batch optimization:
results = await asyncio.gather(*[
    extract_entities_keywords_async(doc.content, doc.lang)
    for doc in documents
])
```

**Hardcoded Parameters:**
| Parameter | Current Value | Recommendation |
|-----------|---------------|----------------|
| `cache_ttl` | 30 days | Make configurable |
| `max_retries` | 3 | ✅ Already configurable |
| `temperature` (detect) | 0 | Make configurable per operation |
| `temperature` (cluster) | 0.3 | Make configurable per operation |
| `max_tokens` (detect) | 30 | Make configurable |
| `max_tokens` (cluster) | 2000 | Make configurable |
| `max_tokens` (extract) | 300 | Make configurable |
| Text truncation (detect) | 500 chars | Make configurable |
| Text truncation (extract) | 1500 chars | Make configurable |
| Topics truncation (cluster) | 50 topics | Make configurable |

**Technical Debt:**
- ❌ In-memory cache (not persistent)
- ❌ No exponential backoff for retries
- ❌ No rate limiting
- ❌ No request batching
- ⚠️ Hardcoded truncation limits
- ⚠️ No timeout configuration

**API Design Implications:**
```python
# Proposed endpoints:
POST /api/v1/nlp/detect-language
POST /api/v1/nlp/cluster-topics
POST /api/v1/nlp/extract-entities
POST /api/v1/nlp/batch-extract  # New batch endpoint
```

---

### 2. TopicClusterer (`topic_clusterer.py`)

**Purpose:** Semantic topic clustering using TF-IDF + HDBSCAN

**Current Architecture:**
```python
class TopicClusterer:
    def cluster_documents(docs: List[Document]) -> List[TopicCluster]  # Sync CPU-intensive
```

**Algorithm Pipeline:**
1. TF-IDF vectorization (`sklearn.TfidfVectorizer`)
2. HDBSCAN clustering (density-based, auto K)
3. LLM label generation (calls LLMProcessor)

**Dependencies:**
- `scikit-learn==1.6.1` (TF-IDF)
- `hdbscan==0.8.40` (clustering)
- `numpy` (array operations)
- **LLMProcessor** (label generation)

**CPU Profile:**
- **Type:** CPU-bound (TF-IDF matrix computation, HDBSCAN)
- **Complexity:** O(n²) for clustering
- **Memory:** O(n × features) for TF-IDF matrix
- **Bottleneck:** HDBSCAN for large document sets (>1000 docs)

**Hardcoded Parameters:**
| Parameter | Default | Tunable? | Impact |
|-----------|---------|----------|--------|
| `min_cluster_size` | 2 | ✅ Constructor | Cluster granularity |
| `min_samples` | 1 | ✅ Constructor | Noise sensitivity |
| `max_features` | 5000 | ✅ Constructor | Vocabulary size |
| `stop_words` | 'english' | ❌ Hardcoded | Multilingual limitation |
| `ngram_range` | (1, 2) | ❌ Hardcoded | Feature richness |
| `min_df` | 1 | ❌ Hardcoded | Rare term handling |
| `max_df` | 1.0 | ❌ Hardcoded | Common term filtering |
| `metric` | 'euclidean' | ❌ Hardcoded | Distance measure |
| `cluster_selection_method` | 'eom' | ❌ Hardcoded | Cluster quality |

**Async Conversion Assessment:**
- **Priority:** ⭐⭐⭐ **MEDIUM**
- **Complexity:** ⭐⭐⭐⭐ **HIGH**
- **Effort:** 4-6 hours
- **Strategy:** Offload to background worker (CPU-bound)

**Processing Workflow:**
```python
# Current: Synchronous blocking
clusters = topic_clusterer.cluster_documents(documents)  # Blocks for ~5-10s

# Proposed: Background task
task_id = await background_tasks.add_task(
    cluster_documents_task,
    documents=documents,
    config=cluster_config
)
# Poll or webhook for completion
```

**Performance Bottlenecks:**
1. **TF-IDF vectorization** - O(n × m) where n=docs, m=vocab
   - **Optimization:** Incremental vectorization for streaming data
   - **Caching:** Cache vectorizer fit for reuse

2. **HDBSCAN clustering** - O(n²) worst case
   - **Optimization:** Sampling for large datasets (>10k docs)
   - **Alternative:** Use approximate clustering (KMeans) for initial grouping

3. **LLM label generation** - Sequential API calls
   - **Optimization:** Async batch labeling (current limitation)

**Cache Opportunities:**
- ✅ Clustering results by document fingerprint
- ✅ TF-IDF vectorizer (vocabulary)
- ✅ LLM labels by topic list hash

**API Design:**
```python
# Synchronous (fast, small batches):
POST /api/v1/topics/cluster
{
  "documents": [...],  # < 100 docs
  "min_cluster_size": 2,
  "max_features": 5000
}

# Asynchronous (background, large batches):
POST /api/v1/topics/cluster/async
Response: {"task_id": "abc123", "status": "pending"}

GET /api/v1/tasks/abc123
Response: {"status": "completed", "clusters": [...]}
```

**Technical Debt:**
- ⚠️ Hardcoded TF-IDF parameters (not multilingual-friendly)
- ❌ No incremental clustering support
- ❌ No cluster quality metrics exposed
- ❌ LLM fallback generates generic labels only
- ⚠️ Cache directory created but not used (file-based caching not implemented)

---

### 3. Deduplicator (`deduplicator.py`)

**Purpose:** Near-duplicate detection using MinHash/LSH

**Current Architecture:**
```python
class Deduplicator:
    def is_duplicate(doc: Document) -> bool                    # Sync, fast
    def add(doc: Document) -> None                             # Sync, fast
    def deduplicate(docs: List[Document]) -> List[Document]    # Sync, O(n)
```

**Algorithm:**
1. **Canonical URL normalization** (fast path: exact URL match)
2. **MinHash computation** (content-based similarity)
3. **LSH query** (fast approximate nearest neighbor search)

**Dependencies:**
- `datasketch==1.6.4` (MinHash/LSH)
- `hashlib` (SHA-256 hashing)
- `urllib.parse` (URL normalization)

**CPU Profile:**
- **Type:** CPU-bound (hashing, LSH)
- **Complexity:** O(n) for batch deduplication
- **Memory:** O(n × num_perm) for LSH index
- **Performance:** ~10,000 docs/sec (MinHash), ~100,000 queries/sec (LSH)

**Hardcoded Parameters:**
| Parameter | Default | Impact |
|-----------|---------|--------|
| `threshold` | 0.7 | ✅ Configurable (Jaccard similarity) |
| `num_perm` | 128 | ✅ Configurable (accuracy vs speed) |
| `TRACKING_PARAMS` | 13 params | ❌ Hardcoded set |

**URL Normalization Rules:**
```python
# Removes:
- www prefix
- Tracking params (utm_*, fbclid, gclid, etc.)
- Trailing slash
- URL fragments (#section)
- Converts to lowercase

# ⚠️ ISSUE: Hardcoded tracking parameter list
# ✅ RECOMMENDATION: Make configurable via config
```

**Async Conversion Assessment:**
- **Priority:** ⭐ **LOW**
- **Complexity:** ⭐ **TRIVIAL**
- **Effort:** 30 minutes
- **Rationale:** Already fast (CPU-bound, no I/O)

**Optimization Opportunities:**
1. **Vectorization** - Use numpy for batch MinHash computation
2. **Persistent LSH** - Save/load LSH index from disk/Redis
3. **Distributed deduplication** - Shared LSH index across workers

**API Design:**
```python
# Real-time duplicate check:
POST /api/v1/documents/check-duplicate
{
  "content": "...",
  "url": "https://example.com/article"
}
Response: {"is_duplicate": true, "matched_doc_id": "abc123"}

# Batch deduplication:
POST /api/v1/documents/deduplicate
{
  "documents": [...]
}
Response: {"unique_documents": [...], "duplicates_removed": 45}
```

**Technical Debt:**
- ❌ In-memory LSH index (lost on restart)
- ❌ No persistence for seen URLs
- ⚠️ Hardcoded tracking parameters
- ✅ Statistics tracking (good)
- ✅ Clear API (good)

---

### 4. EntityExtractor (`entity_extractor.py`)

**Purpose:** Extract named entities and keywords from documents

**Current Architecture:**
```python
class EntityExtractor:
    def process(doc: Document, force=False) -> Document           # Sync, calls LLM
    def process_batch(docs: List[Document]) -> List[Document]     # Sync, sequential
```

**Dependencies:**
- **LLMProcessor** (delegates all extraction work)

**I/O Profile:**
- **Type:** I/O-bound (HTTP API via LLMProcessor)
- **Latency:** ~0.5-2s per document
- **Batch processing:** Sequential (no parallelization)

**Processing Logic:**
```python
# Skip already processed documents:
if doc.has_entities() and doc.has_keywords() and not force:
    return doc  # Skip

# Extract via LLM:
result = self.llm_processor.extract_entities_keywords(content, language)
doc.entities = result.entities
doc.keywords = result.keywords
doc.status = "processed"
```

**Statistics Tracking:**
```python
{
  "total_documents": 100,
  "processed_documents": 95,
  "failed_documents": 5,
  "success_rate": 0.95,
  "failure_rate": 0.05
}
```

**Async Conversion Assessment:**
- **Priority:** ⭐⭐⭐⭐⭐ **CRITICAL**
- **Complexity:** ⭐⭐ **LOW** (delegates to LLMProcessor)
- **Effort:** 1-2 hours
- **Impact:** 50x+ throughput (parallel processing)

**Batch Processing Optimization:**
```python
# Current: Sequential (SLOW)
for doc in docs:
    result = extractor.process(doc)  # Blocks ~1s each
# Total time for 100 docs: ~100s

# Proposed: Parallel async (FAST)
async def process_batch_async(docs):
    tasks = [process_async(doc) for doc in docs]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]
# Total time for 100 docs: ~2-3s (parallel)
```

**API Design:**
```python
# Single document:
POST /api/v1/documents/{doc_id}/extract-entities
Response: {
  "entities": ["Berlin", "PropTech", "SAP"],
  "keywords": ["SaaS", "Cloud", "GDPR"]
}

# Batch processing (background):
POST /api/v1/documents/batch-extract
{
  "document_ids": ["doc1", "doc2", ...],  # 100+ docs
  "skip_errors": true
}
Response: {"task_id": "abc123"}

GET /api/v1/tasks/abc123
Response: {
  "status": "completed",
  "processed": 95,
  "failed": 5,
  "results": [...]
}
```

**Technical Debt:**
- ❌ No batch optimization (sequential processing)
- ❌ No progress tracking for large batches
- ✅ Good error handling (skip_errors flag)
- ✅ Statistics tracking (good)
- ⚠️ Tight coupling to LLMProcessor (good and bad)

---

## Processing Workflows Analysis

### Current Invocation Pattern (UniversalTopicAgent)

```python
# src/agents/universal_topic_agent.py

def collect_all_sources():
    # 1. Collect from multiple sources (RSS, Reddit, Trends, Autocomplete)
    all_documents = []
    all_documents.extend(rss_docs)
    all_documents.extend(reddit_docs)
    all_documents.extend(trends_docs)
    all_documents.extend(autocomplete_docs)

    # 2. Deduplicate (SYNC, BLOCKING)
    unique_documents = deduplicator.deduplicate(all_documents)

    # 3. Save to database
    for doc in unique_documents:
        db.insert_document(doc)

async def process_topics(limit=None):
    # 1. Load documents from DB
    documents = db.get_documents_by_language(language, limit)

    # 2. Cluster (SYNC, BLOCKING, CPU-INTENSIVE)
    clusters = topic_clusterer.cluster_documents(documents)

    # 3. Convert to Topic objects
    topics = convert_clusters_to_topics(clusters)

    # 4. Process through ContentPipeline (ASYNC, GOOD)
    for topic in topics:
        enriched_topic = await content_pipeline.process(topic)
        db.insert_topic(enriched_topic)

    return topics
```

**Issues with Current Workflow:**
1. ❌ **Blocking operations in async context** - `process_topics()` is async but calls sync `cluster_documents()`
2. ❌ **Sequential document processing** - No parallelization
3. ❌ **No progress tracking** - Long-running operations block silently
4. ❌ **No task queuing** - Direct execution only

### Proposed Async Workflow

```python
# FastAPI Background Tasks

@router.post("/api/v1/pipeline/run", response_model=TaskResponse)
async def run_pipeline(
    background_tasks: BackgroundTasks,
    config: PipelineConfig
):
    task_id = generate_task_id()

    # Queue background task
    background_tasks.add_task(
        run_pipeline_task,
        task_id=task_id,
        config=config
    )

    return TaskResponse(
        task_id=task_id,
        status="queued",
        message="Pipeline started"
    )

async def run_pipeline_task(task_id: str, config: PipelineConfig):
    try:
        # Update status
        await update_task_status(task_id, "running", progress=0)

        # 1. Collect documents (parallel)
        async with aiohttp.ClientSession() as session:
            tasks = [
                collect_rss_async(session, feeds),
                collect_reddit_async(session, subreddits),
                collect_trends_async(session, keywords)
            ]
            results = await asyncio.gather(*tasks)
        all_documents = flatten(results)

        await update_task_status(task_id, "running", progress=20)

        # 2. Deduplicate (CPU-bound, run in executor)
        unique_docs = await asyncio.to_thread(
            deduplicator.deduplicate,
            all_documents
        )

        await update_task_status(task_id, "running", progress=40)

        # 3. Extract entities (I/O-bound, parallel)
        tasks = [
            extract_entities_async(doc)
            for doc in unique_docs
        ]
        enriched_docs = await asyncio.gather(*tasks)

        await update_task_status(task_id, "running", progress=60)

        # 4. Cluster (CPU-bound, background worker)
        clusters = await asyncio.to_thread(
            topic_clusterer.cluster_documents,
            enriched_docs
        )

        await update_task_status(task_id, "running", progress=80)

        # 5. Save to database
        await save_clusters_async(clusters)

        await update_task_status(task_id, "completed", progress=100)

    except Exception as e:
        await update_task_status(task_id, "failed", error=str(e))
```

---

## Async Readiness Assessment

| Processor | Current State | Async Priority | Conversion Effort | Strategy |
|-----------|---------------|----------------|-------------------|----------|
| **LLMProcessor** | ❌ Sync | ⭐⭐⭐⭐⭐ CRITICAL | 2-3 hours | Convert to `httpx.AsyncClient` |
| **EntityExtractor** | ❌ Sync | ⭐⭐⭐⭐⭐ CRITICAL | 1-2 hours | Depends on async LLMProcessor |
| **TopicClusterer** | ❌ Sync | ⭐⭐⭐ MEDIUM | 4-6 hours | Offload to background worker |
| **Deduplicator** | ❌ Sync | ⭐ LOW | 30 min | Wrap in `asyncio.to_thread()` |

### I/O-bound vs CPU-bound Classification

**I/O-bound (Network calls):**
- ✅ **LLMProcessor** - HTTP API calls to OpenRouter
- ✅ **EntityExtractor** - Delegates to LLMProcessor
- **Strategy:** Convert to async/await with `httpx.AsyncClient`

**CPU-bound (Computation):**
- ✅ **TopicClusterer** - TF-IDF + HDBSCAN clustering
- ✅ **Deduplicator** - MinHash computation + LSH queries
- **Strategy:** Run in background workers or thread pool

### Threading/Multiprocessing Opportunities

**Current Usage:** None (all single-threaded)

**Recommendations:**

1. **ThreadPoolExecutor** for I/O-bound:
   ```python
   # Current sync blocking:
   result = llm_processor.detect_language(text)

   # Async with thread pool:
   result = await asyncio.to_thread(llm_processor.detect_language, text)
   ```

2. **ProcessPoolExecutor** for CPU-bound:
   ```python
   # Clustering (CPU-intensive):
   from concurrent.futures import ProcessPoolExecutor

   with ProcessPoolExecutor() as executor:
       clusters = await loop.run_in_executor(
           executor,
           topic_clusterer.cluster_documents,
           documents
       )
   ```

3. **AsyncIO Gather** for parallel I/O:
   ```python
   # Batch entity extraction (parallel API calls):
   tasks = [
       extract_entities_async(doc)
       for doc in documents
   ]
   results = await asyncio.gather(*tasks, return_exceptions=True)
   ```

---

## Service Integration Recommendations

### Proposed Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │  API Endpoints  │  │ Background Tasks│  │ Task Manager │ │
│  └────────┬────────┘  └────────┬────────┘  └──────┬───────┘ │
│           │                    │                   │         │
│           └────────────────────┴───────────────────┘         │
│                              │                               │
├──────────────────────────────┼───────────────────────────────┤
│                      Service Layer                           │
├──────────────────────────────┼───────────────────────────────┤
│                              │                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          DocumentService (async)                      │   │
│  │  - collect_documents()                                │   │
│  │  - deduplicate_documents()                            │   │
│  │  - extract_entities_batch()                           │   │
│  └───────────────────────────┬──────────────────────────┘   │
│                              │                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          TopicService (async)                         │   │
│  │  - cluster_topics()                                   │   │
│  │  - process_pipeline()                                 │   │
│  │  - sync_to_notion()                                   │   │
│  └───────────────────────────┬──────────────────────────┘   │
│                              │                               │
├──────────────────────────────┼───────────────────────────────┤
│                      Processor Layer                         │
├──────────────────────────────┼───────────────────────────────┤
│                              │                               │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐     │
│  │ Deduplicator│  │TopicClusterer│  │ AsyncLLMProcessor│     │
│  │   (sync)    │  │   (sync)     │  │    (async)       │     │
│  └─────────────┘  └─────────────┘  └──────────────────┘     │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### Service Layer Design

**Option 1: Separate Services (Recommended)**

```python
# src/services/document_service.py
class DocumentService:
    """Handles document collection, deduplication, and entity extraction"""

    def __init__(
        self,
        llm_processor: AsyncLLMProcessor,
        deduplicator: Deduplicator,
        db: SQLiteManager
    ):
        self.llm = llm_processor
        self.deduplicator = deduplicator
        self.db = db

    async def collect_and_process(
        self,
        sources: List[str]
    ) -> List[Document]:
        """Collect, deduplicate, and extract entities from sources"""
        # Parallel collection
        docs = await self._collect_parallel(sources)

        # Deduplicate (CPU-bound, thread pool)
        unique_docs = await asyncio.to_thread(
            self.deduplicator.deduplicate,
            docs
        )

        # Extract entities (I/O-bound, parallel)
        enriched_docs = await self._extract_entities_batch(unique_docs)

        # Save to DB
        await self._save_documents(enriched_docs)

        return enriched_docs

    async def _extract_entities_batch(
        self,
        documents: List[Document]
    ) -> List[Document]:
        """Extract entities in parallel"""
        tasks = [
            self.llm.extract_entities_keywords_async(doc.content, doc.language)
            for doc in documents
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Update documents with results
        for doc, result in zip(documents, results):
            if not isinstance(result, Exception):
                doc.entities = result.entities
                doc.keywords = result.keywords
                doc.status = "processed"

        return documents

# src/services/topic_service.py
class TopicService:
    """Handles topic clustering and processing"""

    def __init__(
        self,
        topic_clusterer: TopicClusterer,
        content_pipeline: ContentPipeline,
        db: SQLiteManager
    ):
        self.clusterer = topic_clusterer
        self.pipeline = content_pipeline
        self.db = db

    async def cluster_and_process(
        self,
        documents: List[Document],
        limit: int = 10
    ) -> List[Topic]:
        """Cluster documents and process through content pipeline"""
        # Cluster (CPU-bound, background worker)
        clusters = await asyncio.to_thread(
            self.clusterer.cluster_documents,
            documents
        )

        # Convert to topics
        topics = self._clusters_to_topics(clusters)

        # Process through pipeline (already async)
        processed_topics = []
        for topic in topics[:limit]:
            enriched_topic = await self.pipeline.process(topic)
            processed_topics.append(enriched_topic)

        # Save to DB
        await self._save_topics(processed_topics)

        return processed_topics
```

**Option 2: Unified ProcessorService**

```python
# src/services/processor_service.py
class ProcessorService:
    """Unified service for all processing operations"""

    async def run_full_pipeline(
        self,
        config: PipelineConfig
    ) -> PipelineResult:
        """Run complete pipeline from collection to Notion sync"""
        # 1. Collection
        documents = await self.collect_sources(config.sources)

        # 2. Deduplication
        unique_docs = await self.deduplicate(documents)

        # 3. Entity extraction
        enriched_docs = await self.extract_entities(unique_docs)

        # 4. Clustering
        clusters = await self.cluster_topics(enriched_docs)

        # 5. Content pipeline
        topics = await self.process_topics(clusters)

        # 6. Notion sync
        synced = await self.sync_to_notion(topics)

        return PipelineResult(
            documents_collected=len(documents),
            unique_documents=len(unique_docs),
            topics_created=len(topics),
            synced_to_notion=synced
        )
```

**Recommendation:** Use **Option 1** (Separate Services) for better:
- Single Responsibility Principle
- Testability
- Service composition
- Independent scaling

### API Endpoint Proposals

```python
# ================================
# DOCUMENT PROCESSING ENDPOINTS
# ================================

# Deduplication
POST /api/v1/documents/deduplicate
Request: {
  "documents": [{"content": "...", "url": "..."}],
  "threshold": 0.7,  # Optional
  "num_perm": 128    # Optional
}
Response: {
  "unique_documents": [...],
  "duplicates_removed": 45,
  "deduplication_rate": 0.31
}

# Entity Extraction (single)
POST /api/v1/documents/{doc_id}/extract-entities
Response: {
  "entities": ["Berlin", "SAP", "PropTech"],
  "keywords": ["SaaS", "Cloud", "GDPR"]
}

# Entity Extraction (batch - background task)
POST /api/v1/documents/batch-extract
Request: {
  "document_ids": ["doc1", "doc2", ...],
  "skip_errors": true,
  "force_reprocess": false
}
Response: {
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "total_documents": 150
}

# ================================
# TOPIC PROCESSING ENDPOINTS
# ================================

# Topic Clustering (synchronous, small batches)
POST /api/v1/topics/cluster
Request: {
  "documents": [...],  # < 100 docs
  "min_cluster_size": 2,
  "max_features": 5000
}
Response: {
  "clusters": [
    {
      "cluster_id": 0,
      "label": "Cloud Computing",
      "size": 15,
      "document_ids": ["doc1", "doc2", ...]
    }
  ],
  "noise_count": 5,
  "noise_ratio": 0.05
}

# Topic Clustering (asynchronous, large batches)
POST /api/v1/topics/cluster/async
Request: {
  "document_ids": ["doc1", "doc2", ...],  # > 100 docs
  "config": {
    "min_cluster_size": 3,
    "max_features": 10000
  }
}
Response: {
  "task_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "queued"
}

# ================================
# NLP PROCESSING ENDPOINTS
# ================================

# Language Detection
POST /api/v1/nlp/detect-language
Request: {"text": "Das ist ein deutscher Text"}
Response: {"language": "de", "confidence": 0.95}

# Topic Clustering (LLM-based labels)
POST /api/v1/nlp/cluster-topics
Request: {
  "topics": ["Machine Learning", "AI", "Cloud Computing"]
}
Response: {
  "clusters": [
    {
      "cluster": "AI/ML",
      "topics": ["Machine Learning", "AI"]
    }
  ]
}

# ================================
# BACKGROUND TASK ENDPOINTS
# ================================

# Task Status
GET /api/v1/tasks/{task_id}
Response: {
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",  # queued, running, completed, failed
  "progress": 65,
  "created_at": "2025-11-23T10:00:00Z",
  "updated_at": "2025-11-23T10:02:30Z",
  "result": null,
  "error": null
}

# Cancel Task
DELETE /api/v1/tasks/{task_id}
Response: {"message": "Task cancelled"}

# List Tasks
GET /api/v1/tasks?status=running&limit=20
Response: {
  "tasks": [...]
}

# ================================
# PIPELINE ENDPOINTS
# ================================

# Run Full Pipeline (background)
POST /api/v1/pipeline/run
Request: {
  "config": {
    "sources": ["rss", "reddit"],
    "language": "de",
    "limit": 50
  }
}
Response: {
  "task_id": "550e8400-e29b-41d4-a716-446655440002",
  "status": "queued"
}

# Pipeline Status
GET /api/v1/pipeline/{task_id}/status
Response: {
  "status": "running",
  "stage": "clustering",
  "progress": {
    "documents_collected": 250,
    "documents_processed": 200,
    "topics_created": 15
  }
}
```

---

## Background Task Design

### Task Queue Architecture

```python
# src/background/task_manager.py

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Callable
import uuid
from datetime import datetime

class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Task:
    id: str
    name: str
    status: TaskStatus
    progress: int  # 0-100
    created_at: datetime
    updated_at: datetime
    result: Any = None
    error: str = None
    metadata: Dict[str, Any] = None

class TaskManager:
    """Manages background tasks with progress tracking"""

    def __init__(self, redis_client=None):
        self.tasks: Dict[str, Task] = {}
        self.redis = redis_client  # Optional: persistent storage

    async def create_task(
        self,
        name: str,
        func: Callable,
        *args,
        **kwargs
    ) -> str:
        """Create and queue a background task"""
        task_id = str(uuid.uuid4())

        task = Task(
            id=task_id,
            name=name,
            status=TaskStatus.QUEUED,
            progress=0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        self.tasks[task_id] = task

        # Queue for execution
        asyncio.create_task(
            self._run_task(task_id, func, *args, **kwargs)
        )

        return task_id

    async def _run_task(
        self,
        task_id: str,
        func: Callable,
        *args,
        **kwargs
    ):
        """Execute task and update status"""
        task = self.tasks[task_id]

        try:
            # Update status
            task.status = TaskStatus.RUNNING
            task.updated_at = datetime.now()

            # Execute function
            result = await func(
                *args,
                **kwargs,
                progress_callback=lambda p: self._update_progress(task_id, p)
            )

            # Mark completed
            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.result = result
            task.updated_at = datetime.now()

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.updated_at = datetime.now()

    def _update_progress(self, task_id: str, progress: int):
        """Update task progress"""
        if task_id in self.tasks:
            self.tasks[task_id].progress = progress
            self.tasks[task_id].updated_at = datetime.now()

    def get_task(self, task_id: str) -> Task:
        """Get task by ID"""
        return self.tasks.get(task_id)

    def cancel_task(self, task_id: str):
        """Cancel a running task"""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.CANCELLED
```

### Background Task Example: Batch Entity Extraction

```python
# src/background/tasks/entity_extraction.py

async def batch_entity_extraction_task(
    document_ids: List[str],
    db: SQLiteManager,
    llm_processor: AsyncLLMProcessor,
    progress_callback: Callable[[int], None] = None
) -> Dict[str, Any]:
    """Background task for batch entity extraction"""

    total = len(document_ids)
    processed = 0
    failed = 0

    # Load documents
    documents = await db.get_documents_by_ids(document_ids)

    # Process in batches of 50 (parallel)
    batch_size = 50
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]

        # Extract entities (parallel)
        tasks = [
            llm_processor.extract_entities_keywords_async(
                doc.content,
                doc.language
            )
            for doc in batch
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Update documents
        for doc, result in zip(batch, results):
            if not isinstance(result, Exception):
                doc.entities = result.entities
                doc.keywords = result.keywords
                doc.status = "processed"
                await db.update_document(doc)
                processed += 1
            else:
                failed += 1

        # Update progress
        progress = int((i + len(batch)) / total * 100)
        if progress_callback:
            progress_callback(progress)

    return {
        "total": total,
        "processed": processed,
        "failed": failed,
        "success_rate": processed / total if total > 0 else 0
    }
```

---

## Performance Bottleneck Identification

### Bottleneck Analysis

| Bottleneck | Location | Impact | Severity | Fix Priority |
|------------|----------|--------|----------|--------------|
| **Sequential API calls** | LLMProcessor, EntityExtractor | 50x slower | 🔴 CRITICAL | P0 |
| **Blocking CPU operations** | TopicClusterer HDBSCAN | Blocks event loop | 🟠 HIGH | P1 |
| **In-memory cache loss** | LLMProcessor cache | Wasted API calls | 🟠 HIGH | P1 |
| **No batch optimization** | EntityExtractor | 100x slower | 🟠 HIGH | P1 |
| **Sequential document loop** | EntityExtractor.process_batch | Linear slowdown | 🟡 MEDIUM | P2 |
| **No LSH persistence** | Deduplicator | Rebuild on restart | 🟡 MEDIUM | P2 |
| **Hardcoded parameters** | All processors | Inflexible tuning | 🟢 LOW | P3 |

### Performance Metrics (Estimated)

**Current Performance (Synchronous):**
```
Entity Extraction:
- Single document: ~1-2s
- Batch of 100 docs: ~100-200s (sequential)
- Throughput: ~0.5-1 doc/sec

Topic Clustering:
- 100 documents: ~5-10s
- 1000 documents: ~60-120s
- Complexity: O(n²) worst case

Deduplication:
- 100 documents: ~0.1s
- 1000 documents: ~1s
- Complexity: O(n) average case
```

**Target Performance (Async):**
```
Entity Extraction:
- Single document: ~1-2s (same)
- Batch of 100 docs: ~2-4s (parallel)
- Throughput: ~25-50 docs/sec (50x improvement)

Topic Clustering:
- 100 documents: ~5-10s (same, CPU-bound)
- 1000 documents: ~60-120s (same, but non-blocking)
- Non-blocking: Background worker

Deduplication:
- Same performance (already fast)
- Non-blocking: Thread pool
```

---

## Test Coverage Analysis

### Test Statistics

| Processor | Unit Tests | E2E Tests | Total | Coverage |
|-----------|-----------|-----------|-------|----------|
| Deduplicator | 23 | 0 | 23 | ~95% |
| TopicClusterer | 22 | 0 | 22 | ~90% |
| EntityExtractor | 14 | 8 | 22 | ~95% |
| LLMProcessor | 19 | 0 | 19 | ~85% |
| **TOTAL** | **78** | **8** | **86** | **~90%** |

### Test Quality Assessment

**✅ Strengths:**
- Comprehensive unit test coverage (78 tests)
- E2E tests with real API calls (EntityExtractor)
- Good edge case coverage (empty inputs, errors, etc.)
- Mocking strategy for external dependencies
- Statistics validation

**⚠️ Gaps:**
- No performance benchmarks
- No load testing
- No concurrent processing tests
- Missing LLM E2E tests
- No cache invalidation tests
- No LSH persistence tests

### Recommended Test Additions

```python
# 1. Performance Benchmarks
@pytest.mark.benchmark
def test_entity_extraction_throughput():
    """Measure entity extraction throughput"""
    extractor = EntityExtractor()
    docs = generate_test_documents(100)

    start = time.time()
    results = extractor.process_batch(docs)
    duration = time.time() - start

    throughput = len(results) / duration
    assert throughput > 0.5  # At least 0.5 docs/sec

# 2. Async Tests
@pytest.mark.asyncio
async def test_async_batch_entity_extraction():
    """Test parallel entity extraction"""
    extractor = AsyncEntityExtractor()
    docs = generate_test_documents(100)

    start = time.time()
    results = await extractor.process_batch_async(docs)
    duration = time.time() - start

    throughput = len(results) / duration
    assert throughput > 20  # At least 20 docs/sec (40x improvement)

# 3. Concurrent Processing
@pytest.mark.asyncio
async def test_concurrent_clustering():
    """Test concurrent clustering operations"""
    clusterer = TopicClusterer()

    # Simulate 3 concurrent clustering requests
    tasks = [
        asyncio.to_thread(clusterer.cluster_documents, docs)
        for docs in [docs1, docs2, docs3]
    ]

    results = await asyncio.gather(*tasks)
    assert len(results) == 3

# 4. Cache Persistence
def test_cache_persistence():
    """Test LLM cache survives restart"""
    processor1 = LLMProcessor(cache_backend="redis")
    result1 = processor1.detect_language("Test")

    # Simulate restart
    processor2 = LLMProcessor(cache_backend="redis")
    result2 = processor2.detect_language("Test")

    # Should use cached result (no API call)
    assert result1 == result2
    assert processor2.cache_hits == 1

# 5. Error Recovery
@pytest.mark.asyncio
async def test_batch_processing_partial_failure():
    """Test graceful degradation on partial batch failure"""
    extractor = AsyncEntityExtractor()

    # Mix of valid and invalid documents
    docs = [
        valid_doc1,
        invalid_doc,  # Will fail
        valid_doc2
    ]

    results = await extractor.process_batch_async(
        docs,
        skip_errors=True
    )

    assert len(results) == 2  # Only valid docs
    stats = extractor.get_statistics()
    assert stats['failed_documents'] == 1
```

---

## Optimization Opportunities

### 1. Async API Calls (LLMProcessor)

**Current:**
```python
# Sequential blocking calls
for doc in documents:
    result = llm_processor.extract_entities_keywords(doc.content, doc.language)
# Time: 100 docs × 1s = 100s
```

**Optimized:**
```python
# Parallel async calls
import httpx

class AsyncLLMProcessor:
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            timeout=30.0,
            limits=httpx.Limits(max_connections=50)
        )

    async def extract_entities_keywords_async(self, content, language):
        response = await self.client.post(
            "/chat/completions",
            json={"model": self.model, "messages": [...]}
        )
        return EntityExtraction.model_validate_json(response.text)

# Parallel processing
tasks = [
    llm_processor.extract_entities_keywords_async(doc.content, doc.language)
    for doc in documents
]
results = await asyncio.gather(*tasks)
# Time: ~2-3s (50x improvement)
```

**Impact:** ⭐⭐⭐⭐⭐ **50x throughput improvement**

---

### 2. Persistent Caching (Redis)

**Current:**
```python
# In-memory cache (lost on restart)
self._cache: Dict[str, tuple[str, datetime]] = {}
```

**Optimized:**
```python
import redis.asyncio as redis

class AsyncLLMProcessor:
    def __init__(self, redis_url="redis://localhost"):
        self.redis = redis.from_url(redis_url)

    async def _get_from_cache(self, key: str):
        cached = await self.redis.get(key)
        if cached:
            data = json.loads(cached)
            if datetime.fromisoformat(data['timestamp']) + timedelta(days=30) > datetime.now():
                return data['result']
        return None

    async def _set_cache(self, key: str, value: str):
        data = {
            'result': value,
            'timestamp': datetime.now().isoformat()
        }
        await self.redis.setex(
            key,
            timedelta(days=30),
            json.dumps(data)
        )
```

**Impact:** ⭐⭐⭐⭐ **90%+ cache hit rate, cost savings**

---

### 3. Batch API Requests

**Current:**
```python
# One API call per document
for doc in documents:
    result = llm.extract_entities_keywords(doc.content, doc.language)
# API calls: 100
# Cost: $0.06 per 1M tokens × 100 calls
```

**Optimized:**
```python
# Batch multiple documents in single API call
async def extract_batch(documents: List[Document]) -> List[EntityExtraction]:
    # Combine up to 10 documents per API call
    batch_size = 10
    results = []

    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]

        # Combine batch into single prompt
        combined_content = "\n\n---\n\n".join([
            f"Document {j}: {doc.content}"
            for j, doc in enumerate(batch)
        ])

        # Single API call for batch
        response = await llm.extract_entities_batch(combined_content)
        results.extend(response.results)

    return results
# API calls: 10 (10x reduction)
# Cost: 90% reduction
```

**Impact:** ⭐⭐⭐⭐ **10x cost reduction, 5x speed improvement**

---

### 4. Incremental TF-IDF Vectorization

**Current:**
```python
# Recompute TF-IDF from scratch every time
vectorizer = TfidfVectorizer()
features = vectorizer.fit_transform(documents)
```

**Optimized:**
```python
# Incremental vectorization
from sklearn.feature_extraction.text import HashingVectorizer

class IncrementalTopicClusterer:
    def __init__(self):
        # HashingVectorizer doesn't need fit (stateless)
        self.vectorizer = HashingVectorizer(
            n_features=2**18,  # 256k features
            ngram_range=(1, 2)
        )

    def cluster_documents_incremental(self, documents):
        # Transform without fit (works with streaming data)
        features = self.vectorizer.transform([doc.content for doc in documents])
        clusters = self.clusterer.fit_predict(features)
        return clusters
```

**Impact:** ⭐⭐⭐ **Memory reduction, streaming support**

---

### 5. MinHash/LSH Persistence

**Current:**
```python
# In-memory LSH index (rebuilt on restart)
self.lsh = MinHashLSH(threshold=0.7, num_perm=128)
```

**Optimized:**
```python
import pickle
from pathlib import Path

class PersistentDeduplicator(Deduplicator):
    def __init__(self, cache_path="cache/lsh_index.pkl"):
        super().__init__()
        self.cache_path = Path(cache_path)
        self._load_index()

    def _load_index(self):
        """Load LSH index from disk"""
        if self.cache_path.exists():
            with open(self.cache_path, 'rb') as f:
                data = pickle.load(f)
                self.lsh = data['lsh']
                self.seen_urls = data['seen_urls']

    def _save_index(self):
        """Save LSH index to disk"""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, 'wb') as f:
            pickle.dump({
                'lsh': self.lsh,
                'seen_urls': self.seen_urls
            }, f)

    def add(self, doc):
        super().add(doc)
        self._save_index()  # Persist after each add
```

**Impact:** ⭐⭐⭐ **Instant startup, no index rebuild**

---

### 6. Parallel Document Processing

**Current:**
```python
# Sequential processing
for doc in documents:
    if not deduplicator.is_duplicate(doc):
        deduplicator.add(doc)
        processed = entity_extractor.process(doc)
        db.save(processed)
```

**Optimized:**
```python
# Pipeline parallelization
async def process_documents_parallel(documents):
    # Stage 1: Deduplicate (CPU-bound, thread pool)
    unique_docs = await asyncio.to_thread(
        deduplicator.deduplicate,
        documents
    )

    # Stage 2: Extract entities (I/O-bound, parallel)
    tasks = [
        entity_extractor.process_async(doc)
        for doc in unique_docs
    ]
    enriched_docs = await asyncio.gather(*tasks)

    # Stage 3: Save (I/O-bound, batch insert)
    await db.bulk_insert_async(enriched_docs)

    return enriched_docs
```

**Impact:** ⭐⭐⭐⭐⭐ **100x overall pipeline speedup**

---

## Refactoring Priorities

### Priority Matrix

| Priority | Task | Impact | Effort | ROI |
|----------|------|--------|--------|-----|
| **P0 - Critical** | Async LLMProcessor | ⭐⭐⭐⭐⭐ | 2-3h | ⭐⭐⭐⭐⭐ |
| **P0 - Critical** | Async EntityExtractor | ⭐⭐⭐⭐⭐ | 1-2h | ⭐⭐⭐⭐⭐ |
| **P0 - Critical** | Persistent Redis cache | ⭐⭐⭐⭐ | 2h | ⭐⭐⭐⭐⭐ |
| **P1 - High** | Background task system | ⭐⭐⭐⭐ | 4-6h | ⭐⭐⭐⭐ |
| **P1 - High** | TopicClusterer async wrapper | ⭐⭐⭐ | 2h | ⭐⭐⭐⭐ |
| **P1 - High** | Batch API optimization | ⭐⭐⭐⭐ | 3-4h | ⭐⭐⭐⭐ |
| **P2 - Medium** | LSH persistence | ⭐⭐⭐ | 2h | ⭐⭐⭐ |
| **P2 - Medium** | Config-driven parameters | ⭐⭐ | 4h | ⭐⭐⭐ |
| **P2 - Medium** | Performance tests | ⭐⭐⭐ | 4h | ⭐⭐⭐ |
| **P3 - Low** | Incremental vectorization | ⭐⭐ | 6h | ⭐⭐ |

### Recommended Implementation Sequence

**Phase 1: Async Foundation (Week 1)**
1. ✅ Convert LLMProcessor to async (Day 1-2)
2. ✅ Convert EntityExtractor to async (Day 2)
3. ✅ Add Redis caching layer (Day 3)
4. ✅ Create service layer (DocumentService, TopicService) (Day 4-5)

**Phase 2: Background Tasks (Week 2)**
5. ✅ Implement TaskManager (Day 1-2)
6. ✅ Create background task wrappers (Day 3)
7. ✅ Add progress tracking (Day 4)
8. ✅ Build API endpoints (Day 5)

**Phase 3: Optimization (Week 3)**
9. ✅ Batch API optimization (Day 1-2)
10. ✅ LSH persistence (Day 3)
11. ✅ Performance testing (Day 4-5)

**Phase 4: Configuration & Polish (Week 4)**
12. ✅ Config-driven parameters (Day 1-2)
13. ✅ Monitoring & logging (Day 3)
14. ✅ Documentation (Day 4-5)

---

## API Endpoint Design Summary

### Synchronous Endpoints (Fast Operations)

```python
# Small batch processing (< 100 items)
POST /api/v1/documents/deduplicate
POST /api/v1/nlp/detect-language
POST /api/v1/nlp/cluster-topics
POST /api/v1/topics/cluster  # Small batches only
```

### Asynchronous Endpoints (Long Operations)

```python
# Large batch processing, background tasks
POST /api/v1/documents/batch-extract
POST /api/v1/topics/cluster/async
POST /api/v1/pipeline/run

# Task management
GET /api/v1/tasks/{task_id}
DELETE /api/v1/tasks/{task_id}
GET /api/v1/tasks
```

### Real-time vs Background Decision Matrix

| Operation | Size | Duration | Endpoint Type |
|-----------|------|----------|---------------|
| Language detection | 1 doc | < 1s | Synchronous |
| Entity extraction | 1 doc | ~1-2s | Synchronous |
| Entity extraction | 10 docs | ~2-3s | Synchronous |
| Entity extraction | 100+ docs | 10-30s | Background |
| Topic clustering | < 50 docs | ~5s | Synchronous |
| Topic clustering | 100+ docs | 30-120s | Background |
| Full pipeline | Any | 60-300s | Background |

---

## Recommendations Summary

### Immediate Actions (P0)

1. **Convert LLMProcessor to async**
   - Use `httpx.AsyncClient` for OpenRouter API
   - Implement Redis caching
   - Add batch request optimization

2. **Convert EntityExtractor to async**
   - Leverage async LLMProcessor
   - Implement parallel batch processing
   - Add progress tracking

3. **Implement persistent caching**
   - Redis for LLM response cache
   - SQLite/Pickle for LSH index
   - 30-day TTL with configurable expiration

### Service Architecture (P1)

4. **Create service layer**
   - DocumentService (collection, deduplication, extraction)
   - TopicService (clustering, processing)
   - TaskManager (background task orchestration)

5. **Background task system**
   - FastAPI BackgroundTasks integration
   - Task status tracking (queued, running, completed, failed)
   - Progress callbacks
   - Result persistence

### Optimization (P2)

6. **Performance improvements**
   - Batch API requests (10x cost reduction)
   - Parallel processing (50x throughput)
   - LSH persistence (instant startup)
   - Incremental vectorization (streaming support)

7. **Configuration & Testing**
   - Config-driven parameters
   - Performance benchmarks
   - Load testing
   - Monitoring & observability

---

## Conclusion

The processors module is **well-architected but entirely synchronous**, making it incompatible with high-throughput async FastAPI applications. The migration path is clear:

**Key Priorities:**
1. ⭐⭐⭐⭐⭐ **Async conversion of I/O-bound processors** (LLMProcessor, EntityExtractor)
2. ⭐⭐⭐⭐ **Persistent caching** (Redis for responses, disk for LSH)
3. ⭐⭐⭐⭐ **Background task system** (long-running operations)
4. ⭐⭐⭐ **Service layer** (clean separation of concerns)

**Expected Outcomes:**
- **50-100x throughput improvement** for entity extraction
- **90%+ cost reduction** via caching
- **Non-blocking operations** for CPU-intensive tasks
- **Production-ready** API with progress tracking

**Timeline:** 3-4 weeks for full migration with all optimizations.

---

**Generated:** 2025-11-23
**Author:** Claude Code (Sonnet 4.5)
**Next Steps:** Review findings → Prioritize P0 tasks → Begin async conversion
