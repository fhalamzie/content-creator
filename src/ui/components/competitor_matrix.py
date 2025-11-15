"""
Competitor Comparison Matrix Component

Provides 3 views for analyzing competitor data:
1. Strategy Comparison: Side-by-side sortable table
2. Coverage Heatmap: Color-coded topic coverage matrix
3. Gap Analysis: Content gap vs competitor matrix
"""

from typing import List, Dict, Any
import pandas as pd
import streamlit as st


def prepare_strategy_table(competitors: List[Dict]) -> pd.DataFrame:
    """
    Prepare strategy comparison table data.

    Args:
        competitors: List of competitor dictionaries

    Returns:
        DataFrame with columns: Competitor, Website, Topics Count,
        Posting Frequency, Social Channels
    """
    if not competitors:
        return pd.DataFrame(columns=[
            "Competitor", "Website", "Topics Count",
            "Posting Frequency", "Social Channels"
        ])

    rows = []
    for comp in competitors:
        # Count non-empty social channels
        social_handles = comp.get("social_handles", {})
        social_count = sum(1 for url in social_handles.values() if url)

        rows.append({
            "Competitor": comp.get("name", "Unknown"),
            "Website": comp.get("website", "N/A"),
            "Topics Count": len(comp.get("content_topics", [])),
            "Posting Frequency": comp.get("posting_frequency", "N/A"),
            "Social Channels": social_count
        })

    return pd.DataFrame(rows)


def prepare_coverage_matrix(competitors: List[Dict]) -> pd.DataFrame:
    """
    Prepare topic coverage heatmap matrix.

    Args:
        competitors: List of competitor dictionaries

    Returns:
        DataFrame with competitors as rows, topics as columns,
        boolean values indicating coverage
    """
    if not competitors:
        return pd.DataFrame()

    # Extract all unique topics
    all_topics = set()
    for comp in competitors:
        topics = comp.get("content_topics", [])
        all_topics.update(topics)

    all_topics = sorted(all_topics)

    # Create matrix
    matrix_data = {}
    for topic in all_topics:
        matrix_data[topic] = []

    competitor_names = []

    for comp in competitors:
        competitor_names.append(comp.get("name", "Unknown"))
        comp_topics = set(comp.get("content_topics", []))

        for topic in all_topics:
            matrix_data[topic].append(topic in comp_topics)

    df = pd.DataFrame(matrix_data, index=competitor_names)
    return df


def prepare_gap_matrix(
    competitors: List[Dict],
    content_gaps: List[str]
) -> pd.DataFrame:
    """
    Prepare gap analysis matrix.

    Args:
        competitors: List of competitor dictionaries
        content_gaps: List of content gap opportunities

    Returns:
        DataFrame with content gaps as rows, competitors as columns,
        boolean values indicating if competitor addresses gap
    """
    if not content_gaps:
        return pd.DataFrame()

    if not competitors:
        return pd.DataFrame(index=content_gaps)

    # Create matrix with gaps as rows, competitors as columns
    competitor_names = [comp.get("name", "Unknown") for comp in competitors]
    matrix_data = {name: [] for name in competitor_names}

    for gap in content_gaps:
        gap_lower = gap.lower()

        for comp in competitors:
            # Check if competitor covers this gap (similarity check)
            comp_topics = comp.get("content_topics", [])
            comp_topics_lower = [topic.lower() for topic in comp_topics]

            # Simple keyword matching - if any topic contains gap keywords
            gap_keywords = gap_lower.split()
            covers_gap = False

            for topic in comp_topics_lower:
                # Check if any significant keyword from gap appears in topic
                topic_words = topic.split()
                matching_words = [kw for kw in gap_keywords if kw in topic_words]
                if len(matching_words) >= 2:  # At least 2 matching keywords
                    covers_gap = True
                    break

            comp_name = comp.get("name", "Unknown")
            matrix_data[comp_name].append(covers_gap)

    df = pd.DataFrame(matrix_data, index=content_gaps)
    return df


def export_to_csv(df: pd.DataFrame, filename: str) -> bytes:
    """
    Export dataframe to CSV bytes.

    Args:
        df: DataFrame to export
        filename: Name for the CSV file (unused, kept for API consistency)

    Returns:
        CSV data as bytes
    """
    return df.to_csv(index=True).encode('utf-8')


def render_strategy_comparison(competitors: List[Dict]) -> None:
    """
    View 1: Render strategy comparison table.

    Features:
    - Sortable by any column
    - Shows key metrics (topics count, posting freq, social presence)
    - Color-coded social presence strength
    """
    st.markdown("### 📊 Strategy Comparison")
    st.caption("Compare competitor strategies side-by-side. Click column headers to sort.")

    if not competitors:
        st.info("No competitor data available")
        return

    df = prepare_strategy_table(competitors)

    # Add color styling function for social channels
    def color_social_channels(val):
        """Color code social channel count."""
        if val >= 3:
            return 'background-color: #90EE90'  # Light green
        elif val >= 2:
            return 'background-color: #FFD700'  # Gold
        elif val >= 1:
            return 'background-color: #FFA500'  # Orange
        else:
            return 'background-color: #FFB6C1'  # Light red

    # Style the dataframe
    styled_df = df.style.applymap(
        color_social_channels,
        subset=['Social Channels']
    )

    st.dataframe(styled_df, use_container_width=True)

    # Summary stats
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        avg_topics = df["Topics Count"].mean()
        st.metric("Avg Topics per Competitor", f"{avg_topics:.1f}")
    with col2:
        avg_social = df["Social Channels"].mean()
        st.metric("Avg Social Channels", f"{avg_social:.1f}")
    with col3:
        max_social = df["Social Channels"].max()
        st.metric("Max Social Presence", f"{max_social}")

    # Export button
    st.divider()
    csv = export_to_csv(df, "strategy_comparison.csv")
    st.download_button(
        label="📥 Download Strategy Comparison (CSV)",
        data=csv,
        file_name="strategy_comparison.csv",
        mime="text/csv",
        use_container_width=True
    )


def render_coverage_heatmap(competitors: List[Dict]) -> None:
    """
    View 2: Render topic coverage heatmap.

    Features:
    - Rows: Competitors
    - Columns: All unique content topics
    - Cells: Color-coded coverage (green = covered, red = not covered)
    """
    st.markdown("### 🎨 Topic Coverage Heatmap")
    st.caption("Green = Covered by competitor, Red = Not covered. Reveals strengths and weaknesses.")

    if not competitors:
        st.info("No competitor data available")
        return

    df = prepare_coverage_matrix(competitors)

    if df.empty:
        st.info("No content topics found")
        return

    # Convert boolean to numeric for styling
    df_numeric = df.astype(int)

    # Style the heatmap
    styled_df = df_numeric.style.background_gradient(
        cmap='RdYlGn',  # Red-Yellow-Green colormap
        vmin=0,
        vmax=1,
        axis=None
    ).format("{:.0f}")  # Show as 0/1 instead of True/False

    st.dataframe(styled_df, use_container_width=True)

    # Coverage statistics
    st.divider()
    st.markdown("#### 📈 Coverage Statistics")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Most Covered Topics:**")
        topic_coverage = df.sum(axis=0).sort_values(ascending=False)
        for topic, count in topic_coverage.head(5).items():
            st.caption(f"• {topic}: {count}/{len(competitors)} competitors")

    with col2:
        st.markdown("**Least Covered Topics (Opportunities):**")
        for topic, count in topic_coverage.tail(5).items():
            st.caption(f"• {topic}: {count}/{len(competitors)} competitors")

    # Export button
    st.divider()
    csv = export_to_csv(df, "coverage_heatmap.csv")
    st.download_button(
        label="📥 Download Coverage Heatmap (CSV)",
        data=csv,
        file_name="coverage_heatmap.csv",
        mime="text/csv",
        use_container_width=True
    )


def render_gap_analysis_matrix(
    competitors: List[Dict],
    content_gaps: List[str]
) -> None:
    """
    View 3: Render gap analysis matrix.

    Features:
    - Rows: Content gaps (opportunities)
    - Columns: Competitors
    - Cells: Whether competitor addresses this gap
    - Highlights underserved opportunities
    """
    st.markdown("### 🎯 Gap Analysis Matrix")
    st.caption("Green = Competitor addresses gap, Red = Opportunity. Target red rows for differentiation.")

    if not content_gaps:
        st.info("No content gaps identified")
        return

    if not competitors:
        st.info("No competitor data available")
        return

    df = prepare_gap_matrix(competitors, content_gaps)

    if df.empty:
        st.info("No gap analysis data available")
        return

    # Convert boolean to numeric for styling
    df_numeric = df.astype(int)

    # Style the matrix (inverted colors - red is good for gaps)
    styled_df = df_numeric.style.background_gradient(
        cmap='RdYlGn_r',  # Reversed: Red = not covered (good opportunity)
        vmin=0,
        vmax=1,
        axis=None
    ).format("{:.0f}")

    st.dataframe(styled_df, use_container_width=True)

    # Gap opportunity ranking
    st.divider()
    st.markdown("#### 🏆 Top Gap Opportunities")
    st.caption("Gaps with the fewest competitors (biggest opportunities)")

    gap_scores = df.sum(axis=1).sort_values()  # Fewer = better opportunity

    for i, (gap, competitors_covering) in enumerate(gap_scores.head(5).items(), 1):
        total_comps = len(competitors)
        coverage_pct = (competitors_covering / total_comps) * 100
        st.markdown(f"{i}. **{gap}** - {competitors_covering}/{total_comps} competitors ({coverage_pct:.0f}% coverage)")

    # Export button
    st.divider()
    csv = export_to_csv(df, "gap_analysis.csv")
    st.download_button(
        label="📥 Download Gap Analysis (CSV)",
        data=csv,
        file_name="gap_analysis.csv",
        mime="text/csv",
        use_container_width=True
    )


def render_competitor_matrix(result: Dict[str, Any]) -> None:
    """
    Main entry point - renders all 3 matrix views in tabs.

    Args:
        result: Competitor analysis result dict with:
            - competitors: List[Dict]
            - content_gaps: List[str]
            - trending_topics: List[str]
    """
    st.divider()
    st.subheader("🔍 Competitor Comparison Matrix")
    st.caption("Analyze competitor strategies, topic coverage, and gap opportunities across 3 interactive views.")

    competitors = result.get("competitors", [])
    content_gaps = result.get("content_gaps", [])

    if not competitors:
        st.warning("⚠️ No competitor data available. Run competitor analysis first.")
        return

    # Create 3 tabs for the views
    tab1, tab2, tab3 = st.tabs([
        "📊 Strategy Comparison",
        "🎨 Coverage Heatmap",
        "🎯 Gap Analysis"
    ])

    with tab1:
        render_strategy_comparison(competitors)

    with tab2:
        render_coverage_heatmap(competitors)

    with tab3:
        render_gap_analysis_matrix(competitors, content_gaps)
