"""
Unit tests for competitor matrix UI component.

Tests the 3 matrix views:
1. Strategy comparison table
2. Coverage heatmap
3. Gap analysis matrix
"""

import pytest
import pandas as pd
from typing import List, Dict


# Test fixtures
@pytest.fixture
def sample_competitors() -> List[Dict]:
    """Sample competitor data for testing."""
    return [
        {
            "name": "CompetitorA",
            "website": "https://competitor-a.com",
            "description": "Leading PropTech solution",
            "social_handles": {
                "linkedin": "https://linkedin.com/company/competitor-a",
                "twitter": "https://twitter.com/competitor_a",
                "facebook": ""
            },
            "content_topics": ["AI automation", "Smart buildings", "IoT sensors"],
            "posting_frequency": "Daily"
        },
        {
            "name": "CompetitorB",
            "website": "https://competitor-b.com",
            "description": "Property management platform",
            "social_handles": {
                "linkedin": "https://linkedin.com/company/competitor-b",
                "twitter": "",
                "facebook": "https://facebook.com/competitor-b"
            },
            "content_topics": ["Property management", "DSGVO compliance"],
            "posting_frequency": "Weekly"
        },
        {
            "name": "CompetitorC",
            "website": "https://competitor-c.com",
            "description": "Real estate analytics",
            "social_handles": {
                "linkedin": "",
                "twitter": "",
                "facebook": ""
            },
            "content_topics": ["Smart buildings", "Data analytics", "Market trends"],
            "posting_frequency": "Monthly"
        }
    ]


@pytest.fixture
def sample_content_gaps() -> List[str]:
    """Sample content gap data for testing."""
    return [
        "Blockchain in real estate",
        "Virtual property tours",
        "Tenant engagement platforms",
        "Energy efficiency tracking"
    ]


@pytest.fixture
def sample_result(sample_competitors, sample_content_gaps) -> Dict:
    """Complete competitor analysis result."""
    return {
        "competitors": sample_competitors,
        "content_gaps": sample_content_gaps,
        "trending_topics": ["PropTech AI", "Smart cities", "ESG compliance"]
    }


class TestStrategyComparisonDataPreparation:
    """Test data preparation for strategy comparison table."""

    def test_prepare_strategy_table_basic(self, sample_competitors):
        """Test basic strategy table preparation."""
        from src.ui.components.competitor_matrix import prepare_strategy_table

        df = prepare_strategy_table(sample_competitors)

        # Check structure
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "Competitor" in df.columns
        assert "Website" in df.columns
        assert "Topics Count" in df.columns
        assert "Posting Frequency" in df.columns
        assert "Social Channels" in df.columns

    def test_prepare_strategy_table_values(self, sample_competitors):
        """Test strategy table contains correct values."""
        from src.ui.components.competitor_matrix import prepare_strategy_table

        df = prepare_strategy_table(sample_competitors)

        # Check first row values
        assert df.iloc[0]["Competitor"] == "CompetitorA"
        assert df.iloc[0]["Topics Count"] == 3
        assert df.iloc[0]["Posting Frequency"] == "Daily"
        assert df.iloc[0]["Social Channels"] == 2  # linkedin + twitter

    def test_prepare_strategy_table_social_count(self, sample_competitors):
        """Test social channels count calculation."""
        from src.ui.components.competitor_matrix import prepare_strategy_table

        df = prepare_strategy_table(sample_competitors)

        # CompetitorA: 2 channels
        assert df.iloc[0]["Social Channels"] == 2
        # CompetitorB: 2 channels
        assert df.iloc[1]["Social Channels"] == 2
        # CompetitorC: 0 channels
        assert df.iloc[2]["Social Channels"] == 0

    def test_prepare_strategy_table_empty_competitors(self):
        """Test strategy table with empty competitor list."""
        from src.ui.components.competitor_matrix import prepare_strategy_table

        df = prepare_strategy_table([])

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


class TestCoverageHeatmapDataPreparation:
    """Test data preparation for coverage heatmap."""

    def test_prepare_coverage_matrix_basic(self, sample_competitors):
        """Test basic coverage matrix preparation."""
        from src.ui.components.competitor_matrix import prepare_coverage_matrix

        df = prepare_coverage_matrix(sample_competitors)

        # Check structure
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3  # 3 competitors
        # Should have all unique topics as columns
        assert "AI automation" in df.columns
        assert "Smart buildings" in df.columns

    def test_prepare_coverage_matrix_values(self, sample_competitors):
        """Test coverage matrix contains correct boolean values."""
        from src.ui.components.competitor_matrix import prepare_coverage_matrix

        df = prepare_coverage_matrix(sample_competitors)

        # CompetitorA covers "AI automation"
        assert df.loc["CompetitorA", "AI automation"] == True
        # CompetitorB does not cover "AI automation"
        assert df.loc["CompetitorB", "AI automation"] == False
        # Both A and C cover "Smart buildings"
        assert df.loc["CompetitorA", "Smart buildings"] == True
        assert df.loc["CompetitorC", "Smart buildings"] == True

    def test_prepare_coverage_matrix_all_topics(self, sample_competitors):
        """Test all unique topics are included as columns."""
        from src.ui.components.competitor_matrix import prepare_coverage_matrix

        df = prepare_coverage_matrix(sample_competitors)

        expected_topics = {
            "AI automation", "Smart buildings", "IoT sensors",
            "Property management", "DSGVO compliance",
            "Data analytics", "Market trends"
        }

        assert set(df.columns) == expected_topics

    def test_prepare_coverage_matrix_empty_competitors(self):
        """Test coverage matrix with empty competitor list."""
        from src.ui.components.competitor_matrix import prepare_coverage_matrix

        df = prepare_coverage_matrix([])

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


class TestGapAnalysisMatrixDataPreparation:
    """Test data preparation for gap analysis matrix."""

    def test_prepare_gap_matrix_basic(self, sample_competitors, sample_content_gaps):
        """Test basic gap analysis matrix preparation."""
        from src.ui.components.competitor_matrix import prepare_gap_matrix

        df = prepare_gap_matrix(sample_competitors, sample_content_gaps)

        # Check structure
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 4  # 4 content gaps
        assert "CompetitorA" in df.columns
        assert "CompetitorB" in df.columns
        assert "CompetitorC" in df.columns

    def test_prepare_gap_matrix_gap_detection(self, sample_competitors, sample_content_gaps):
        """Test gap detection logic (no competitor should cover gaps)."""
        from src.ui.components.competitor_matrix import prepare_gap_matrix

        df = prepare_gap_matrix(sample_competitors, sample_content_gaps)

        # All values should be False (gaps are topics NOT covered by competitors)
        # Since our sample gaps are truly gaps, all should be False
        assert df.loc["Blockchain in real estate", "CompetitorA"] == False
        assert df.loc["Virtual property tours", "CompetitorB"] == False

    def test_prepare_gap_matrix_empty_gaps(self, sample_competitors):
        """Test gap matrix with empty gaps list."""
        from src.ui.components.competitor_matrix import prepare_gap_matrix

        df = prepare_gap_matrix(sample_competitors, [])

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


class TestCSVExport:
    """Test CSV export functionality."""

    def test_export_to_csv_basic(self):
        """Test basic CSV export."""
        from src.ui.components.competitor_matrix import export_to_csv

        df = pd.DataFrame({
            "A": [1, 2, 3],
            "B": ["x", "y", "z"]
        })

        csv_bytes = export_to_csv(df, "test.csv")

        assert isinstance(csv_bytes, bytes)
        assert len(csv_bytes) > 0

    def test_export_to_csv_content(self):
        """Test CSV export contains correct data."""
        from src.ui.components.competitor_matrix import export_to_csv

        df = pd.DataFrame({
            "A": [1, 2],
            "B": ["x", "y"]
        })

        csv_bytes = export_to_csv(df, "test.csv")
        csv_str = csv_bytes.decode('utf-8')

        assert "A,B" in csv_str
        assert "1,x" in csv_str
        assert "2,y" in csv_str

    def test_export_to_csv_empty_dataframe(self):
        """Test CSV export with empty dataframe."""
        from src.ui.components.competitor_matrix import export_to_csv

        df = pd.DataFrame()
        csv_bytes = export_to_csv(df, "test.csv")

        assert isinstance(csv_bytes, bytes)
