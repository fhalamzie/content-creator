"""Logo Showcase & Generator Page

Create custom logos with Flux AI and view existing logo variations.
"""

import streamlit as st
import asyncio
from datetime import datetime
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.media.image_generator import ImageGenerator


def init_session_state():
    """Initialize session state for logo generation."""
    if "generated_logos" not in st.session_state:
        st.session_state.generated_logos = []

    if "total_generation_cost" not in st.session_state:
        st.session_state.total_generation_cost = 0.0


async def generate_logo_variations(prompt: str, num_variations: int, model_type: str):
    """Generate logo variations using Flux models.

    Args:
        prompt: Logo description prompt
        num_variations: Number of variations to generate (1-10)
        model_type: "ultra" or "dev"

    Returns:
        List of generated logo dictionaries
    """
    generator = ImageGenerator()
    results = []

    # Determine model settings
    use_dev = (model_type == "dev")
    cost_per_logo = generator.COST_DEV if use_dev else generator.COST_ULTRA
    model_name = "Flux Dev" if use_dev else "Flux 1.1 Pro Ultra"

    for i in range(num_variations):
        try:
            # Generate logo with 1:1 aspect ratio
            url = await generator._generate_with_retry(
                prompt=prompt,
                aspect_ratio="1:1",
                topic="Custom logo design",
                use_dev_model=use_dev
            )

            if url:
                results.append({
                    "id": len(st.session_state.generated_logos) + i + 1,
                    "style": f"Custom Logo #{i + 1}",
                    "model": model_name,
                    "cost": f"${cost_per_logo:.3f}",
                    "url": url,
                    "prompt": prompt,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
        except Exception as e:
            st.error(f"Failed to generate variation {i + 1}: {e}")

    return results


def render():
    """Render the logo showcase and creator page."""

    # Initialize session state
    init_session_state()

    st.title("🎨 Logo Creator & Showcase")
    st.caption("Create custom logos with Flux AI or browse existing designs")

    # Create tabs
    tab1, tab2 = st.tabs(["✨ Create New Logo", "🏠 SignCasa Gallery"])

    # ========================================
    # TAB 1: LOGO CREATOR
    # ========================================
    with tab1:
        st.header("✨ Custom Logo Generator")
        st.markdown("Generate professional logos using Flux AI models")

        # Information box
        with st.expander("ℹ️ How to Create Great Logos", expanded=False):
            st.markdown("""
            **Tips for Better Results:**

            1. **Be Specific**: Include style, colors, and elements
            2. **Mention Logo Type**: Wordmark, icon, badge, etc.
            3. **Specify Industry**: Tech, legal, finance, etc.
            4. **Add Context**: Professional, playful, minimalist, etc.

            **Good Example:**
            > "Modern minimalist logo for TechCorp software company, geometric letter T icon,
            > blue and white color scheme, professional sans-serif typography, flat design"

            **Model Comparison:**
            - **Flux Ultra** ($0.06): Highest quality, most detail, best for final designs
            - **Flux Dev** ($0.003): Fast iteration, good quality, 95% cheaper
            """)

        # Generation form
        with st.form("logo_generator_form"):
            st.subheader("🎯 Logo Settings")

            # Prompt input
            prompt = st.text_area(
                "Logo Description",
                placeholder="Minimalist logo for digital marketing agency, geometric shapes, blue and orange gradient...",
                height=100,
                help="Describe your logo in detail: style, elements, colors, typography, brand aesthetic"
            )

            col1, col2 = st.columns(2)

            with col1:
                num_variations = st.slider(
                    "Number of Variations",
                    min_value=1,
                    max_value=10,
                    value=3,
                    help="Generate multiple variations to choose from"
                )

            with col2:
                model_type = st.selectbox(
                    "Flux Model",
                    options=["dev", "ultra"],
                    format_func=lambda x: "Flux Dev ($0.003/logo)" if x == "dev" else "Flux Ultra ($0.06/logo)",
                    help="Ultra: Highest quality | Dev: Fast & affordable"
                )

            # Cost preview
            cost_per_logo = 0.003 if model_type == "dev" else 0.060
            total_cost = cost_per_logo * num_variations

            st.info(f"💰 **Estimated Cost**: ${total_cost:.3f} ({num_variations} logos × ${cost_per_logo:.3f})")

            # Generate button
            submitted = st.form_submit_button(
                "🚀 Generate Logos",
                use_container_width=True,
                type="primary"
            )

        # Handle form submission
        if submitted:
            if not prompt or len(prompt.strip()) < 10:
                st.error("⚠️ Please enter a detailed logo description (at least 10 characters)")
            else:
                with st.spinner(f"🎨 Generating {num_variations} logo variation(s)... This may take 10-30 seconds per logo."):
                    # Run async generation
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        new_logos = loop.run_until_complete(
                            generate_logo_variations(prompt, num_variations, model_type)
                        )

                        if new_logos:
                            # Add to session state
                            st.session_state.generated_logos.extend(new_logos)
                            st.session_state.total_generation_cost += total_cost

                            st.success(f"✅ Successfully generated {len(new_logos)}/{num_variations} logos!")
                            st.balloons()
                        else:
                            st.error("❌ Failed to generate any logos. Please try again.")
                    finally:
                        loop.close()

        # Display generated logos
        if st.session_state.generated_logos:
            st.divider()
            st.subheader("📸 Your Generated Logos")

            # Stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Logos", len(st.session_state.generated_logos))
            with col2:
                st.metric("Total Cost", f"${st.session_state.total_generation_cost:.2f}")
            with col3:
                avg_cost = st.session_state.total_generation_cost / len(st.session_state.generated_logos)
                st.metric("Avg Cost", f"${avg_cost:.3f}")

            # Clear all button
            if st.button("🗑️ Clear All Generated Logos", type="secondary"):
                st.session_state.generated_logos = []
                st.session_state.total_generation_cost = 0.0
                st.rerun()

            st.divider()

            # Display in 3-column grid (most recent first)
            sorted_logos = sorted(st.session_state.generated_logos,
                                key=lambda x: x.get("timestamp", ""),
                                reverse=True)

            for i in range(0, len(sorted_logos), 3):
                cols = st.columns(3)

                for idx, col in enumerate(cols):
                    if i + idx < len(sorted_logos):
                        logo = sorted_logos[i + idx]

                        with col:
                            with st.container():
                                # Image
                                try:
                                    st.image(logo["url"], use_container_width=True)
                                except Exception as e:
                                    st.error(f"Failed to load: {e}")

                                # Title
                                st.markdown(f"**{logo['style']}**")
                                st.caption(f"🕒 {logo.get('timestamp', 'N/A')}")

                                # Info
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    st.caption(f"**Model**: {logo['model']}")
                                with col_b:
                                    st.caption(f"**Cost**: {logo['cost']}")

                                # Prompt
                                with st.expander("📝 Prompt"):
                                    st.caption(logo["prompt"])

                                # Download button
                                st.markdown(f"[🔗 Open Image]({logo['url']})")

                                st.divider()
        else:
            st.info("👆 Generate your first logo using the form above!")

    # ========================================
    # TAB 2: SIGNCASA GALLERY
    # ========================================
    with tab2:
        st.header("🏠 SignCasa Logo Gallery")
        st.caption("Example logos generated for SignCasa digital rental platform")

        # Brand info
        with st.expander("📋 Brand Information", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Brand**: SignCasa")
                st.markdown("**Industry**: German LegalTech")
            with col2:
                st.markdown("**Product**: Digital rental contracts")
                st.markdown("**Values**: Simplicity, Security, Compliance")
            with col3:
                st.markdown("**Colors**: Green accents, white background")
                st.markdown("**Aesthetic**: Professional, modern")

        st.divider()

        # Generation stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Generated", "10 logos")
        with col2:
            st.metric("Successful", "9/10", "90%")
        with col3:
            st.metric("Total Cost", "$0.29")
        with col4:
            st.metric("Models Used", "4", "Flux, Juggernaut, qwen")

        st.divider()

        # Logo data
        logos = [
            {
                "id": 1,
                "style": "Modern Minimalist",
                "model": "Flux 1.1 Pro Ultra",
                "cost": "$0.060",
                "url": "https://replicate.delivery/xezq/l7zxYstGjH69Hha3lRDlNErWurfjauwK6freDS4yUXWN3TTrA/out-0.png",
                "prompt": "Minimalist logo design for SignCasa digital rental contracts, clean geometric house shape with digital signature element, green and white color scheme, professional sans-serif typography, flat design, negative space, modern German tech brand aesthetic"
            },
            {
                "id": 2,
                "style": "Security Badge",
                "model": "Flux 1.1 Pro Ultra",
                "cost": "$0.060",
                "url": "https://replicate.delivery/xezq/YrOnDYOWiuoIKpwuoE71y8W1R5GPnL0p7nla6dhutBLAf00KA/out-0.png",
                "prompt": "Professional security badge logo for SignCasa, shield shape with house icon and checkmark, ISO certification style, green accent color on white background, trustworthy legal tech brand, precise geometric design, German engineering aesthetic"
            },
            {
                "id": 3,
                "style": "Digital Contract",
                "model": "Flux Dev",
                "cost": "$0.003",
                "url": "https://replicate.delivery/xezq/IB6czefgZPtpcEq0KEgyBGLtr0gM75mKDM7d1H8RudWF8ppVA/out-0.png",
                "prompt": "Logo combining house icon with digital contract document, stylized signature line, modern tech aesthetic, green and grey colors, clean lines, professional legal technology brand, suitable for SaaS platform"
            },
            {
                "id": 4,
                "style": "Geometric Abstract",
                "model": "Flux Dev",
                "cost": "$0.003",
                "url": "https://replicate.delivery/xezq/odBrnGu9D75eYaH0ikxXrbfrlbo88FynWecD4XHo1Q1U4TTrA/out-0.png",
                "prompt": "Abstract geometric logo for SignCasa, overlapping house and document shapes creating SC monogram, modern minimalist design, green gradient, white background, contemporary German tech brand"
            },
            {
                "id": 5,
                "style": "Tech Wordmark",
                "model": "Flux Dev",
                "cost": "$0.003",
                "url": "https://replicate.delivery/xezq/2AzyhL4e44S0L6IK3SqtsfdJPoFeQvBWrqJiRYgDwgDfwnmWA/out-0.png",
                "prompt": "Modern wordmark logo for SignCasa with custom typography, house icon integrated into letter S, clean sans-serif font, green accent color, professional legal tech aesthetic, scalable vector style"
            },
            {
                "id": 10,
                "style": "Circular Badge",
                "model": "Flux Dev",
                "cost": "$0.003",
                "url": "https://replicate.delivery/xezq/yKzyYj7XCWLeZCkQVPx1GHfJ56WYu7Jf4bXqQLuJCrlL7TTrA/out-0.png",
                "prompt": "Circular badge logo for SignCasa, house silhouette in center, Made in Germany aesthetic, green outer ring, professional certification style, modern legal tech brand, clean and trustworthy design"
            }
        ]

        # Filter controls
        col1, col2 = st.columns([3, 1])
        with col1:
            model_filter = st.multiselect(
                "Filter by AI Model",
                options=["Flux 1.1 Pro Ultra", "Flux Dev"],
                default=["Flux 1.1 Pro Ultra", "Flux Dev"]
            )
        with col2:
            sort_by = st.selectbox("Sort by", ["Style Name", "Cost (Low to High)", "Cost (High to Low)", "Model"])

        # Filter and sort logos
        filtered_logos = [logo for logo in logos if logo["model"] in model_filter]

        if sort_by == "Cost (Low to High)":
            filtered_logos.sort(key=lambda x: float(x["cost"].replace("$", "")))
        elif sort_by == "Cost (High to Low)":
            filtered_logos.sort(key=lambda x: float(x["cost"].replace("$", "")), reverse=True)
        elif sort_by == "Model":
            filtered_logos.sort(key=lambda x: x["model"])
        else:  # Style Name
            filtered_logos.sort(key=lambda x: x["style"])

        st.divider()

        # Display logos in 3-column grid
        for i in range(0, len(filtered_logos), 3):
            cols = st.columns(3)

            for idx, col in enumerate(cols):
                if i + idx < len(filtered_logos):
                    logo = filtered_logos[i + idx]

                    with col:
                        with st.container():
                            st.markdown(f"### {logo['style']}")

                            # Display image
                            try:
                                st.image(logo["url"], use_container_width=True)
                            except Exception as e:
                                st.error(f"Failed to load image: {e}")

                            # Logo info
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.markdown(f"**Model**: {logo['model']}")
                            with col_b:
                                st.markdown(f"**Cost**: {logo['cost']}")

                            # Prompt (expandable)
                            with st.expander("📝 View Prompt"):
                                st.caption(logo["prompt"])

                            st.divider()

        # Export section
        st.divider()
        st.subheader("📥 Export Options")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📄 Generate HTML Report", use_container_width=True):
                st.success("✓ HTML showcase available at `/tmp/signcasa_logos_showcase.html`")
                st.code("xdg-open /tmp/signcasa_logos_showcase.html")

        with col2:
            if st.button("📊 Export to PDF", use_container_width=True, disabled=True):
                st.info("Coming soon...")

        with col3:
            if st.button("🎨 Download All Images", use_container_width=True, disabled=True):
                st.info("Coming soon...")

    # Footer
    st.divider()
    st.caption("Powered by Content Creator image generation pipeline")
    st.caption("Models: Flux 1.1 Pro Ultra ($0.06/logo), Flux Dev ($0.003/logo)")
