"""
SQLite Performance Benchmark

Tests the 60K RPS optimizations applied to SQLiteManager:
1. Read throughput (readonly connections)
2. Write throughput (BEGIN IMMEDIATE)
3. Concurrent read/write (WAL mode)
4. Cache effectiveness (20MB RAM cache)

Based on: https://x.com/meln1k/status/1813314113705062774
Expected: 60K RPS on $5 VPS
"""

import time
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime

from src.database.sqlite_manager import SQLiteManager
from src.models.topic import Topic, TopicSource, TopicStatus


def benchmark_sequential_reads(db: SQLiteManager, iterations: int = 1000) -> float:
    """
    Benchmark sequential read operations using readonly connections.

    Returns:
        Operations per second
    """
    print(f"\n{'='*60}")
    print("Benchmark 1: Sequential Reads (readonly=True)")
    print(f"{'='*60}")

    # Insert test data
    print(f"Preparing {iterations} test topics...")
    for i in range(iterations):
        topic = Topic(
            id=f"test-topic-{i}",
            title=f"Test Topic {i}",
            description=f"Description for topic {i}",
            source=TopicSource.MANUAL,
            source_url=None,
            discovered_at=datetime.utcnow(),
            domain="test",
            market="test",
            language="en",
            intent=None,
            engagement_score=0,
            trending_score=0.0,
            priority=5,
            content_score=None,
            research_report=None,
            citations=[],
            word_count=0,
            minhash_signature=None,
            status=TopicStatus.DISCOVERED,
            notion_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            published_at=None
        )
        db.insert_topic(topic)

    # Benchmark reads
    print(f"Reading {iterations} topics sequentially...")
    start = time.time()

    for i in range(iterations):
        topic = db.get_topic(f"test-topic-{i}")
        assert topic is not None

    elapsed = time.time() - start
    ops_per_sec = iterations / elapsed

    print(f"  Time: {elapsed:.2f}s")
    print(f"  Throughput: {ops_per_sec:,.0f} ops/sec")

    # Cleanup
    print("Cleaning up test data...")
    for i in range(iterations):
        with db._get_connection() as conn:
            conn.execute("DELETE FROM topics WHERE id = ?", (f"test-topic-{i}",))

    return ops_per_sec


def benchmark_sequential_writes(db: SQLiteManager, iterations: int = 1000) -> float:
    """
    Benchmark sequential write operations using BEGIN IMMEDIATE.

    Returns:
        Operations per second
    """
    print(f"\n{'='*60}")
    print("Benchmark 2: Sequential Writes (BEGIN IMMEDIATE)")
    print(f"{'='*60}")

    print(f"Writing {iterations} topics sequentially...")
    start = time.time()

    for i in range(iterations):
        topic = Topic(
            id=f"write-test-{i}",
            title=f"Write Test {i}",
            description=f"Description for write test {i}",
            source=TopicSource.MANUAL,
            source_url=None,
            discovered_at=datetime.utcnow(),
            domain="test",
            market="test",
            language="en",
            intent=None,
            engagement_score=0,
            trending_score=0.0,
            priority=5,
            content_score=None,
            research_report=None,
            citations=[],
            word_count=0,
            minhash_signature=None,
            status=TopicStatus.DISCOVERED,
            notion_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            published_at=None
        )
        db.insert_topic(topic)

    elapsed = time.time() - start
    ops_per_sec = iterations / elapsed

    print(f"  Time: {elapsed:.2f}s")
    print(f"  Throughput: {ops_per_sec:,.0f} ops/sec")

    # Cleanup
    print("Cleaning up test data...")
    for i in range(iterations):
        with db._get_connection() as conn:
            conn.execute("DELETE FROM topics WHERE id = ?", (f"write-test-{i}",))

    return ops_per_sec


def benchmark_concurrent_reads(db: SQLiteManager, iterations: int = 1000, workers: int = 10) -> float:
    """
    Benchmark concurrent read operations (WAL mode allows concurrent reads).

    Args:
        iterations: Total number of reads
        workers: Number of concurrent threads

    Returns:
        Operations per second
    """
    print(f"\n{'='*60}")
    print(f"Benchmark 3: Concurrent Reads (WAL mode, {workers} threads)")
    print(f"{'='*60}")

    # Insert test data
    print(f"Preparing {iterations} test topics...")
    for i in range(iterations):
        topic = Topic(
            id=f"concurrent-test-{i}",
            title=f"Concurrent Test {i}",
            description=f"Description for concurrent test {i}",
            source=TopicSource.MANUAL,
            source_url=None,
            discovered_at=datetime.utcnow(),
            domain="test",
            market="test",
            language="en",
            intent=None,
            engagement_score=0,
            trending_score=0.0,
            priority=5,
            content_score=None,
            research_report=None,
            citations=[],
            word_count=0,
            minhash_signature=None,
            status=TopicStatus.DISCOVERED,
            notion_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            published_at=None
        )
        db.insert_topic(topic)

    # Benchmark concurrent reads
    print(f"Reading {iterations} topics with {workers} concurrent threads...")

    def read_topic(i: int):
        topic = db.get_topic(f"concurrent-test-{i}")
        assert topic is not None
        return i

    start = time.time()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(read_topic, i) for i in range(iterations)]
        for future in as_completed(futures):
            future.result()  # Wait for completion

    elapsed = time.time() - start
    ops_per_sec = iterations / elapsed

    print(f"  Time: {elapsed:.2f}s")
    print(f"  Throughput: {ops_per_sec:,.0f} ops/sec")
    print(f"  Per-thread: {ops_per_sec / workers:,.0f} ops/sec")

    # Cleanup
    print("Cleaning up test data...")
    for i in range(iterations):
        with db._get_connection() as conn:
            conn.execute("DELETE FROM topics WHERE id = ?", (f"concurrent-test-{i}",))

    return ops_per_sec


def benchmark_mixed_workload(db: SQLiteManager, iterations: int = 500, workers: int = 10) -> dict:
    """
    Benchmark mixed read/write workload (WAL mode allows reads during writes).

    Args:
        iterations: Total number of operations (50% reads, 50% writes)
        workers: Number of concurrent threads

    Returns:
        Dict with read_ops_per_sec and write_ops_per_sec
    """
    print(f"\n{'='*60}")
    print(f"Benchmark 4: Mixed Read/Write (WAL mode, {workers} threads)")
    print(f"{'='*60}")

    # Insert test data for reads
    print(f"Preparing {iterations} test topics for reads...")
    for i in range(iterations):
        topic = Topic(
            id=f"mixed-read-{i}",
            title=f"Mixed Read {i}",
            description=f"Description for mixed read {i}",
            source=TopicSource.MANUAL,
            source_url=None,
            discovered_at=datetime.utcnow(),
            domain="test",
            market="test",
            language="en",
            intent=None,
            engagement_score=0,
            trending_score=0.0,
            priority=5,
            content_score=None,
            research_report=None,
            citations=[],
            word_count=0,
            minhash_signature=None,
            status=TopicStatus.DISCOVERED,
            notion_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            published_at=None
        )
        db.insert_topic(topic)

    print(f"Running {iterations * 2} mixed operations ({iterations} reads + {iterations} writes)...")

    def read_operation(i: int):
        topic = db.get_topic(f"mixed-read-{i}")
        assert topic is not None
        return ("read", i)

    def write_operation(i: int):
        topic = Topic(
            id=f"mixed-write-{i}",
            title=f"Mixed Write {i}",
            description=f"Description for mixed write {i}",
            source=TopicSource.MANUAL,
            source_url=None,
            discovered_at=datetime.utcnow(),
            domain="test",
            market="test",
            language="en",
            intent=None,
            engagement_score=0,
            trending_score=0.0,
            priority=5,
            content_score=None,
            research_report=None,
            citations=[],
            word_count=0,
            minhash_signature=None,
            status=TopicStatus.DISCOVERED,
            notion_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            published_at=None
        )
        db.insert_topic(topic)
        return ("write", i)

    start = time.time()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit interleaved read/write operations
        futures = []
        for i in range(iterations):
            futures.append(executor.submit(read_operation, i))
            futures.append(executor.submit(write_operation, i))

        read_count = 0
        write_count = 0
        for future in as_completed(futures):
            op_type, _ = future.result()
            if op_type == "read":
                read_count += 1
            else:
                write_count += 1

    elapsed = time.time() - start
    total_ops = iterations * 2
    total_ops_per_sec = total_ops / elapsed
    read_ops_per_sec = read_count / elapsed
    write_ops_per_sec = write_count / elapsed

    print(f"  Time: {elapsed:.2f}s")
    print(f"  Total throughput: {total_ops_per_sec:,.0f} ops/sec")
    print(f"  Read throughput: {read_ops_per_sec:,.0f} ops/sec")
    print(f"  Write throughput: {write_ops_per_sec:,.0f} ops/sec")

    # Cleanup
    print("Cleaning up test data...")
    for i in range(iterations):
        with db._get_connection() as conn:
            conn.execute("DELETE FROM topics WHERE id IN (?, ?)",
                         (f"mixed-read-{i}", f"mixed-write-{i}"))

    return {
        "total_ops_per_sec": total_ops_per_sec,
        "read_ops_per_sec": read_ops_per_sec,
        "write_ops_per_sec": write_ops_per_sec
    }


def verify_pragmas(db: SQLiteManager):
    """Verify that all performance PRAGMAs are correctly applied."""
    print(f"\n{'='*60}")
    print("PRAGMA Verification")
    print(f"{'='*60}")

    with db._get_connection(readonly=True) as conn:
        # Check all PRAGMAs
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]
        cache_size = conn.execute("PRAGMA cache_size").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        temp_store = conn.execute("PRAGMA temp_store").fetchone()[0]

        print(f"  journal_mode        : {journal_mode} {'✅' if journal_mode.lower() == 'wal' else '❌'}")
        print(f"  busy_timeout        : {busy_timeout} {'✅' if busy_timeout == 5000 else '❌'}")
        print(f"  synchronous         : {synchronous} {'✅' if synchronous == 1 else '❌'}")
        print(f"  cache_size          : {cache_size} {'✅' if cache_size == -20000 else '❌'}")
        print(f"  foreign_keys        : {foreign_keys} {'✅' if foreign_keys == 1 else '❌'}")
        print(f"  temp_store          : {temp_store} {'✅' if temp_store == 2 else '❌'}")

        all_correct = (
            journal_mode.lower() == 'wal' and
            busy_timeout == 5000 and
            synchronous == 1 and
            cache_size == -20000 and
            foreign_keys == 1 and
            temp_store == 2
        )

        if all_correct:
            print("\n✅ All PRAGMAs correctly configured!")
        else:
            print("\n❌ Some PRAGMAs are incorrect!")

        return all_correct


def main():
    """Run all benchmarks and report results."""
    print("\n" + "="*60)
    print("SQLite Performance Benchmark")
    print("="*60)
    print("Based on: https://x.com/meln1k/status/1813314113705062774")
    print("Target: 60K RPS on $5 VPS")
    print("="*60)

    # Create test database
    test_db_path = "test_performance.db"
    if Path(test_db_path).exists():
        Path(test_db_path).unlink()

    db = SQLiteManager(db_path=test_db_path)

    try:
        # Verify PRAGMAs
        if not verify_pragmas(db):
            print("\n❌ PRAGMA verification failed! Benchmark results may be inaccurate.")
            return

        # Run benchmarks
        results = {}

        # Benchmark 1: Sequential reads
        results["sequential_reads"] = benchmark_sequential_reads(db, iterations=1000)

        # Benchmark 2: Sequential writes
        results["sequential_writes"] = benchmark_sequential_writes(db, iterations=1000)

        # Benchmark 3: Concurrent reads
        results["concurrent_reads"] = benchmark_concurrent_reads(db, iterations=1000, workers=10)

        # Benchmark 4: Mixed workload
        mixed = benchmark_mixed_workload(db, iterations=500, workers=10)
        results["mixed_total"] = mixed["total_ops_per_sec"]
        results["mixed_reads"] = mixed["read_ops_per_sec"]
        results["mixed_writes"] = mixed["write_ops_per_sec"]

        # Summary
        print(f"\n{'='*60}")
        print("BENCHMARK SUMMARY")
        print(f"{'='*60}")
        print(f"Sequential Reads:      {results['sequential_reads']:>10,.0f} ops/sec")
        print(f"Sequential Writes:     {results['sequential_writes']:>10,.0f} ops/sec")
        print(f"Concurrent Reads:      {results['concurrent_reads']:>10,.0f} ops/sec")
        print(f"Mixed Workload Total:  {results['mixed_total']:>10,.0f} ops/sec")
        print(f"  - Reads:             {results['mixed_reads']:>10,.0f} ops/sec")
        print(f"  - Writes:            {results['mixed_writes']:>10,.0f} ops/sec")
        print(f"{'='*60}")

        # Performance assessment
        max_ops = max(results['sequential_reads'], results['concurrent_reads'])
        target = 60000

        if max_ops >= target:
            print(f"\n🎉 EXCELLENT! Achieved {max_ops:,.0f} ops/sec (target: {target:,} ops/sec)")
        elif max_ops >= target * 0.5:
            print(f"\n✅ GOOD! Achieved {max_ops:,.0f} ops/sec (target: {target:,} ops/sec)")
        else:
            print(f"\n⚠️  Performance below target: {max_ops:,.0f} ops/sec (target: {target:,} ops/sec)")

        print("\nNote: Performance depends on hardware. Results on $5 VPS may differ.")

    finally:
        # Cleanup
        db.close()
        if Path(test_db_path).exists():
            Path(test_db_path).unlink()

        # Remove WAL files if they exist
        for suffix in ["-wal", "-shm"]:
            wal_file = Path(test_db_path + suffix)
            if wal_file.exists():
                wal_file.unlink()

        print("\nCleanup complete.")


if __name__ == "__main__":
    main()
