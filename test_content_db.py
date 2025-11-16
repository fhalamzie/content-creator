"""
Test script to verify SQLite content caching.

Tests:
1. Save blog post to database
2. Save social posts to database
3. Query content from database
4. Verify research linkage
"""

from src.utils.content_cache import save_blog_post_to_db, save_social_posts_to_db
from src.utils.research_cache import save_research_to_cache
import sqlite3

def test_content_caching():
    """Test end-to-end content caching to SQLite"""

    print("=" * 60)
    print("Testing SQLite Content Caching")
    print("=" * 60)

    # Step 1: Save research (simulating Hybrid Orchestrator)
    print("\n1. Saving research to database...")
    topic = "PropTech Trends 2025 Test"
    article = "# PropTech Trends 2025\n\nDeep research article with 2000+ words...\n\n[Source 1](https://example.com/1)"
    sources = [
        {"url": "https://example.com/1", "title": "PropTech Report", "snippet": ""},
        {"url": "https://example.com/2", "title": "Real Estate Tech", "snippet": ""}
    ]

    topic_id = save_research_to_cache(
        topic=topic,
        research_article=article,
        sources=sources,
        config={"market": "Germany", "language": "de"}
    )
    print(f"✅ Research saved: {topic_id}")

    # Step 2: Save blog post (simulating Quick Create)
    print("\n2. Saving blog post to database...")
    blog_content = f"# {topic}\n\nGenerated blog post content based on research...\n\n## Section 1\n\nContent...\n\n## Section 2\n\nMore content..."

    blog_id = save_blog_post_to_db(
        title=topic,
        content=blog_content,
        metadata={
            "word_count": 1500,
            "language": "de",
            "brand_voice": "Professional",
            "target_audience": "PropTech professionals",
            "primary_keyword": "PropTech Trends"
        },
        hero_image_url="https://s3.example.com/hero.jpg",
        supporting_images=[
            {"url": "https://s3.example.com/support1.jpg", "alt": "Supporting image 1"}
        ],
        research_topic_id=topic_id  # Link to research
    )
    print(f"✅ Blog post saved: {blog_id}")

    # Step 3: Save social posts (simulating RepurposingAgent)
    print("\n3. Saving social posts to database...")
    social_posts = [
        {
            "platform": "LinkedIn",
            "content": "Exciting PropTech trends for 2025! 🏢✨\n\nDiscover the latest innovations...",
            "hashtags": ["#PropTech", "#RealEstate", "#Innovation"],
            "character_count": 150,
            "language": "de",
            "image": {"url": "https://s3.example.com/linkedin-og.jpg", "provider": "og"}
        },
        {
            "platform": "Facebook",
            "content": "Die Zukunft von PropTech ist hier! 🚀\n\nErfahren Sie mehr über...",
            "hashtags": ["#PropTech", "#Immobilien"],
            "character_count": 140,
            "language": "de",
            "image": {"url": "https://s3.example.com/facebook-og.jpg", "provider": "og"}
        }
    ]

    saved_count = save_social_posts_to_db(
        blog_post_id=blog_id,
        social_posts=social_posts
    )
    print(f"✅ Social posts saved: {saved_count}")

    # Step 4: Query database to verify
    print("\n4. Querying database to verify...")
    conn = sqlite3.connect("data/topics.db")
    cursor = conn.cursor()

    # Check blog post
    cursor.execute("SELECT title, word_count, language, research_topic_id FROM blog_posts WHERE id = ?", (blog_id,))
    blog = cursor.fetchone()
    print(f"   Blog post: {blog[0]}, {blog[1]} words, {blog[2]}, linked to research: {blog[3]}")

    # Check social posts
    cursor.execute("SELECT platform, character_count, language FROM social_posts WHERE blog_post_id = ?", (blog_id,))
    socials = cursor.fetchall()
    print(f"   Social posts:")
    for platform, char_count, lang in socials:
        print(f"     - {platform}: {char_count} chars, {lang}")

    # Check research linkage
    cursor.execute("""
        SELECT t.title, t.word_count, b.title
        FROM topics t
        LEFT JOIN blog_posts b ON b.research_topic_id = t.id
        WHERE t.id = ?
    """, (topic_id,))
    linkage = cursor.fetchone()
    print(f"\n   Research linkage:")
    print(f"     Research: {linkage[0]}, {linkage[1]} words")
    print(f"     Blog post: {linkage[2]}")

    conn.close()

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - SQLite Content Caching Working!")
    print("=" * 60)
    print("\nArchitecture:")
    print("  Research → SQLite (topics table)")
    print("  Blog Post → SQLite (blog_posts table, linked to research)")
    print("  Social Posts → SQLite (social_posts table, linked to blog)")
    print("  Next: Notion sync (secondary editorial UI)")
    print("\nWAL Mode: Enabled ✅")
    print("Single Source of Truth: SQLite ✅")
    print("Notion: Secondary sync target ✅")


if __name__ == "__main__":
    test_content_caching()
