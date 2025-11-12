#!/usr/bin/env python3
"""
Quick test script to compare DALL-E 3 image generation with natural style
"""
import asyncio
import sys
sys.path.insert(0, '/home/projects/content-creator')

from src.media.image_generator import ImageGenerator

async def test_image_generation():
    """Generate test images to verify natural style works better"""

    print("🧪 Testing DALL-E 3 with style='natural'")
    print("=" * 60)

    # Initialize generator
    generator = ImageGenerator()

    # Test topics (German real estate/property management)
    test_topics = [
        "Versicherungsschäden in der Hausverwaltung",
        "Digitale Schadensabwicklung",
    ]

    for i, topic in enumerate(test_topics, 1):
        print(f"\n📸 Test {i}/{len(test_topics)}: {topic}")
        print("-" * 60)

        # Generate hero image
        print(f"Generating hero image...")
        result = await generator.generate_hero_image(
            topic=topic,
            brand_tone=["Professional"],
            domain="Real Estate"
        )

        if result.get('success'):
            print(f"✅ Success!")
            print(f"   URL: {result['url'][:80]}...")
            print(f"   Cost: ${result['cost']}")
        else:
            print(f"❌ Failed")

        # Small delay between requests
        await asyncio.sleep(2)

    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("\nThe images should now look more like real photographs")
    print("instead of 3D-rendered stock art.")

if __name__ == "__main__":
    asyncio.run(test_image_generation())
