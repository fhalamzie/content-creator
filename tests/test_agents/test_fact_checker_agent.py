"""
Tests for LLM-Powered FactCheckerAgent with Web Research

TDD approach: Write failing tests first, then implement FactCheckerAgent.

Test Coverage:
- Claim extraction using LLM (statistics, dates, quotes, sources)
- URL validation via HTTP requests (real vs fake URLs)
- Web research verification using Gemini CLI
- Comprehensive fact-check report generation
- Thoroughness levels (basic, medium, thorough)
- Integration tests with real blog posts
- Error handling and edge cases
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import subprocess

from src.agents.fact_checker_agent import FactCheckerAgent, FactCheckError


# ==================== Fixtures ====================

@pytest.fixture
def sample_blog_post_with_hallucinations():
    """Sample German blog post with mix of real and hallucinated URLs"""
    return """# KI-gestützte Predictive Maintenance in der Immobilienwirtschaft

## Einleitung

Laut einer [Studie von Siemens 2023](https://www.siemens.com/studie-predictive-maintenance-2023)
können Gebäudebetreiber durch KI-gestützte Wartung ihre Kosten um bis zu 30% senken.

Das [Bundesministerium für Wirtschaft](https://www.bmwk.de/gebaeudeenergiegesetz-2023)
hat neue Richtlinien für energieeffiziente Gebäude veröffentlicht.

Eine echte Quelle: [McKinsey Manufacturing Report](https://www.mckinsey.com/industries/manufacturing)

## Quellen

1. https://www.siemens.com/studie-predictive-maintenance-2023 (FAKE)
2. https://www.bmwk.de/gebaeudeenergiegesetz-2023 (FAKE)
3. https://www.mckinsey.com/industries/manufacturing (REAL)
"""


@pytest.fixture
def sample_blog_post_all_real():
    """Sample blog post with all real URLs"""
    return """# Manufacturing Industry Report

Research from [McKinsey](https://www.mckinsey.com/industries/manufacturing)
shows that AI can improve efficiency by 25%.

Source: https://www.mckinsey.com/industries/manufacturing
"""


@pytest.fixture
def sample_blog_post_no_urls():
    """Sample blog post without any URLs"""
    return """# AI in Manufacturing

Artificial intelligence is transforming the manufacturing industry.
Companies can reduce costs by up to 30% through AI-powered systems.
"""


# ==================== Initialization Tests ====================

def test_fact_checker_init_success():
    """Test successful FactCheckerAgent initialization"""
    agent = FactCheckerAgent(api_key="test-key")

    assert agent.agent_type == "fact_checker"
    assert agent.api_key == "test-key"


def test_fact_checker_init_with_invalid_api_key():
    """Test initialization fails with invalid API key"""
    with pytest.raises(Exception):
        agent = FactCheckerAgent(api_key="")


# ==================== Claim Extraction Tests (LLM-Powered) ====================

@patch('src.agents.fact_checker_agent.FactCheckerAgent.generate')
def test_extract_claims_from_blog_post(mock_generate):
    """Test LLM extracts factual claims from blog post"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock LLM response with structured claims
    mock_generate.return_value = {
        'content': json.dumps([
            {
                'claim_text': 'Siemens veröffentlichte 2023 eine Studie über KI',
                'claim_type': 'source',
                'location': 'Section: Einleitung',
                'citation': 'https://www.siemens.com/studie-predictive-maintenance-2023'
            },
            {
                'claim_text': '30% Kostensenkung möglich',
                'claim_type': 'statistic',
                'location': 'Section: Einleitung',
                'citation': None
            }
        ]),
        'tokens': {'total': 500},
        'cost': 0.001
    }

    content = "Sample blog post content"
    claims = agent._extract_claims(content)

    assert len(claims) == 2
    assert claims[0]['claim_type'] == 'source'
    assert claims[0]['citation'] is not None
    assert claims[1]['claim_type'] == 'statistic'


@patch('src.agents.fact_checker_agent.FactCheckerAgent.generate')
def test_extract_claims_handles_empty_content(mock_generate):
    """Test claim extraction from empty content"""
    agent = FactCheckerAgent(api_key="test-key")

    mock_generate.return_value = {
        'content': json.dumps([]),
        'tokens': {'total': 100},
        'cost': 0.0001
    }

    claims = agent._extract_claims("")
    assert claims == []


@patch('src.agents.fact_checker_agent.FactCheckerAgent.generate')
def test_extract_claims_handles_invalid_json(mock_generate):
    """Test claim extraction handles invalid JSON from LLM"""
    agent = FactCheckerAgent(api_key="test-key")

    mock_generate.return_value = {
        'content': 'Not valid JSON',
        'tokens': {'total': 100},
        'cost': 0.0001
    }

    with pytest.raises(FactCheckError, match="Failed to parse claims"):
        agent._extract_claims("content")


@patch('src.agents.fact_checker_agent.FactCheckerAgent.generate')
def test_extract_claims_different_types(mock_generate):
    """Test extraction of different claim types"""
    agent = FactCheckerAgent(api_key="test-key")

    mock_generate.return_value = {
        'content': json.dumps([
            {'claim_text': 'In 2023...', 'claim_type': 'date', 'location': 'Intro', 'citation': None},
            {'claim_text': '25% increase', 'claim_type': 'statistic', 'location': 'Body', 'citation': None},
            {'claim_text': 'Expert said...', 'claim_type': 'quote', 'location': 'Quote', 'citation': None},
            {'claim_text': 'Study shows...', 'claim_type': 'source', 'location': 'Sources', 'citation': 'http://example.com'}
        ]),
        'tokens': {'total': 600},
        'cost': 0.0012
    }

    claims = agent._extract_claims("content")

    assert len(claims) == 4
    claim_types = [c['claim_type'] for c in claims]
    assert 'date' in claim_types
    assert 'statistic' in claim_types
    assert 'quote' in claim_types
    assert 'source' in claim_types


# ==================== URL Validation Tests (HTTP) ====================

@patch('requests.head')
def test_verify_urls_real_url(mock_head):
    """Test HTTP verification of real URL (200 OK)"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock successful HTTP response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_head.return_value = mock_response

    urls = ['https://www.mckinsey.com/industries/manufacturing']
    result = agent._verify_urls_via_http(urls)

    assert result['https://www.mckinsey.com/industries/manufacturing'] is True


@patch('requests.head')
def test_verify_urls_fake_url(mock_head):
    """Test HTTP verification of fake URL (404)"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock 404 response
    mock_response = Mock()
    mock_response.status_code = 404
    mock_head.return_value = mock_response

    urls = ['https://www.siemens.com/fake-study-2024']
    result = agent._verify_urls_via_http(urls)

    assert result['https://www.siemens.com/fake-study-2024'] is False


@patch('requests.head')
def test_verify_urls_network_error(mock_head):
    """Test URL verification handles network errors"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock network error
    mock_head.side_effect = Exception("Network error")

    urls = ['https://example.com/article']
    result = agent._verify_urls_via_http(urls)

    # Should mark as False on error
    assert result['https://example.com/article'] is False


@patch('requests.head')
def test_verify_urls_timeout(mock_head):
    """Test URL verification handles timeouts"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock timeout
    import requests
    mock_head.side_effect = requests.Timeout("Timeout")

    urls = ['https://slow-site.com/article']
    result = agent._verify_urls_via_http(urls)

    assert result['https://slow-site.com/article'] is False


@patch('requests.head')
def test_verify_urls_mixed_real_and_fake(mock_head):
    """Test verification of mix of real and fake URLs"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock different responses
    def side_effect(*args, **kwargs):
        url = args[0]
        mock_response = Mock()
        if 'mckinsey.com' in url:
            mock_response.status_code = 200
        else:
            mock_response.status_code = 404
        return mock_response

    mock_head.side_effect = side_effect

    urls = [
        'https://www.mckinsey.com/industries/manufacturing',
        'https://www.fake-site.com/fake-study'
    ]
    result = agent._verify_urls_via_http(urls)

    assert result['https://www.mckinsey.com/industries/manufacturing'] is True
    assert result['https://www.fake-site.com/fake-study'] is False


@patch('requests.head')
def test_verify_urls_follows_redirects(mock_head):
    """Test URL verification follows redirects"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock redirect (should use allow_redirects=True)
    mock_response = Mock()
    mock_response.status_code = 200
    mock_head.return_value = mock_response

    urls = ['https://example.com/redirect']
    agent._verify_urls_via_http(urls)

    # Verify allow_redirects was used (with headers)
    mock_head.assert_called_with(
        'https://example.com/redirect',
        timeout=5,
        allow_redirects=True,
        headers={'User-Agent': 'Mozilla/5.0 (compatible; FactChecker/1.0)'}
    )


# ==================== Web Research Verification Tests ====================

@patch('src.agents.fact_checker_agent.ResearchAgent')
def test_verify_claim_via_web_research(mock_research_agent_class):
    """Test claim verification using web research"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock ResearchAgent
    mock_research_agent = Mock()
    mock_research_agent.research.return_value = {
        'sources': [
            {'url': 'https://example.com/study', 'title': 'Study', 'snippet': 'Supporting evidence'}
        ],
        'keywords': ['AI', 'study'],
        'summary': 'Research confirms the claim'
    }
    mock_research_agent_class.return_value = mock_research_agent

    # Mock LLM analysis
    with patch.object(agent, 'generate') as mock_generate:
        mock_generate.return_value = {
            'content': json.dumps({
                'verified': True,
                'evidence': 'Web research confirms claim',
                'confidence': 0.85,
                'sources': ['https://example.com/study']
            }),
            'tokens': {'total': 300},
            'cost': 0.0006
        }

        claim = {
            'claim_text': 'AI improves efficiency by 25%',
            'claim_type': 'statistic',
            'location': 'Section: Body',
            'citation': None
        }

        result = agent._verify_claim_via_web_research(claim)

        assert result['verified'] is True
        assert result['confidence'] > 0.8
        assert len(result['sources']) > 0


@patch('src.agents.fact_checker_agent.ResearchAgent')
def test_verify_claim_contradicted_by_research(mock_research_agent_class):
    """Test claim verification when research contradicts claim"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock ResearchAgent
    mock_research_agent = Mock()
    mock_research_agent.research.return_value = {
        'sources': [
            {'url': 'https://example.com/debunk', 'title': 'Debunk', 'snippet': 'No such study exists'}
        ],
        'keywords': ['fake', 'no evidence'],
        'summary': 'No evidence found for this claim'
    }
    mock_research_agent_class.return_value = mock_research_agent

    # Mock LLM analysis
    with patch.object(agent, 'generate') as mock_generate:
        mock_generate.return_value = {
            'content': json.dumps({
                'verified': False,
                'evidence': 'No evidence found, likely hallucination',
                'confidence': 0.90,
                'sources': []
            }),
            'tokens': {'total': 300},
            'cost': 0.0006
        }

        claim = {
            'claim_text': 'Siemens released study in 2023',
            'claim_type': 'source',
            'location': 'Sources',
            'citation': 'https://www.siemens.com/fake-study'
        }

        result = agent._verify_claim_via_web_research(claim)

        assert result['verified'] is False
        assert result['confidence'] > 0.8


@patch('src.agents.fact_checker_agent.ResearchAgent')
def test_verify_claim_no_evidence_found(mock_research_agent_class):
    """Test claim verification when no evidence found"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock ResearchAgent with empty results
    mock_research_agent = Mock()
    mock_research_agent.research.return_value = {
        'sources': [],
        'keywords': [],
        'summary': 'No results found'
    }
    mock_research_agent_class.return_value = mock_research_agent

    # Mock LLM analysis
    with patch.object(agent, 'generate') as mock_generate:
        mock_generate.return_value = {
            'content': json.dumps({
                'verified': False,
                'evidence': 'Insufficient evidence to verify',
                'confidence': 0.5,
                'sources': []
            }),
            'tokens': {'total': 200},
            'cost': 0.0004
        }

        claim = {'claim_text': 'Obscure claim', 'claim_type': 'fact', 'location': 'Body', 'citation': None}
        result = agent._verify_claim_via_web_research(claim)

        assert result['verified'] is False
        assert result['confidence'] < 0.7


# ==================== Comprehensive Report Generation Tests ====================

def test_generate_report_all_verified():
    """Test report generation when all claims verified"""
    agent = FactCheckerAgent(api_key="test-key")

    verification_results = {
        'claims_checked': 3,
        'claims_verified': 3,
        'claims_failed': [],
        'urls_checked': 2,
        'urls_real': 2,
        'urls_fake': [],
        'hallucinations': []
    }

    report = agent._generate_report(verification_results)

    assert 'Fact-Check Report' in report
    assert 'Claims Checked: 3' in report
    assert '✅ Verified: 3' in report
    assert '✅ Real URLs: 2' in report
    assert '✅ ACCEPT' in report or 'passed' in report.lower()


def test_generate_report_with_hallucinations():
    """Test report generation with detected hallucinations"""
    agent = FactCheckerAgent(api_key="test-key")

    verification_results = {
        'claims_checked': 5,
        'claims_verified': 2,
        'claims_failed': [
            {
                'claim': 'Siemens study 2023',
                'evidence': 'No such study found via web search',
                'url': 'https://www.siemens.com/fake-study'
            },
            {
                'claim': 'BMWK new law',
                'evidence': 'Law exists but different URL',
                'url': 'https://www.bmwk.de/fake-url'
            }
        ],
        'urls_checked': 3,
        'urls_real': 1,
        'urls_fake': [
            'https://www.siemens.com/fake-study',
            'https://www.bmwk.de/fake-url'
        ],
        'hallucinations': [
            {'type': 'fake_url', 'url': 'https://www.siemens.com/fake-study'},
            {'type': 'fake_url', 'url': 'https://www.bmwk.de/fake-url'}
        ]
    }

    report = agent._generate_report(verification_results)

    assert 'Fact-Check Report' in report
    assert '❌ Failed: 3' in report or 'Failed' in report
    assert '🚫 Fake URLs: 2' in report or 'Fake' in report
    assert 'siemens.com/fake-study' in report
    assert 'bmwk.de/fake-url' in report
    assert '❌ REJECT' in report or 'reject' in report.lower()


def test_generate_report_includes_evidence():
    """Test report includes evidence for failed claims"""
    agent = FactCheckerAgent(api_key="test-key")

    verification_results = {
        'claims_checked': 1,
        'claims_verified': 0,
        'claims_failed': [
            {
                'claim': 'Fake statistic',
                'evidence': 'Web search found no supporting sources. Real value is different.',
                'url': None
            }
        ],
        'urls_checked': 0,
        'urls_real': 0,
        'urls_fake': [],
        'hallucinations': []
    }

    report = agent._generate_report(verification_results)

    assert 'Evidence:' in report or 'evidence' in report.lower()
    assert 'Web search found no supporting sources' in report


# ==================== Thoroughness Levels Tests ====================

@patch('src.agents.fact_checker_agent.FactCheckerAgent._extract_claims')
@patch('src.agents.fact_checker_agent.FactCheckerAgent._verify_urls_via_http')
@patch('src.agents.fact_checker_agent.FactCheckerAgent._verify_claim_via_web_research')
def test_thoroughness_basic(mock_verify_claim, mock_verify_urls, mock_extract_claims, sample_blog_post_with_hallucinations):
    """Test basic thoroughness (URLs only, no claim verification)"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock URL extraction
    mock_extract_claims.return_value = [
        {'claim_text': 'Test', 'claim_type': 'source', 'location': 'Body',
         'citation': 'https://example.com'}
    ]

    mock_verify_urls.return_value = {
        'https://example.com': False
    }

    result = agent.verify_content(
        content=sample_blog_post_with_hallucinations,
        thoroughness="basic"
    )

    # Basic: should check URLs but NOT verify claims
    assert mock_verify_urls.called
    assert not mock_verify_claim.called
    assert result['urls_checked'] >= 0


@patch('src.agents.fact_checker_agent.FactCheckerAgent._extract_claims')
@patch('src.agents.fact_checker_agent.FactCheckerAgent._verify_urls_via_http')
@patch('src.agents.fact_checker_agent.FactCheckerAgent._verify_claim_via_web_research')
def test_thoroughness_medium(mock_verify_claim, mock_verify_urls, mock_extract_claims, sample_blog_post_with_hallucinations):
    """Test medium thoroughness (URLs + top 5 claims)"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock many claims
    mock_extract_claims.return_value = [
        {'claim_text': f'Claim {i}', 'claim_type': 'fact', 'location': 'Body', 'citation': None}
        for i in range(10)
    ]

    mock_verify_urls.return_value = {}
    mock_verify_claim.return_value = {
        'verified': True,
        'evidence': 'OK',
        'confidence': 0.8,
        'sources': []
    }

    result = agent.verify_content(
        content=sample_blog_post_with_hallucinations,
        thoroughness="medium"
    )

    # Medium: should verify max 5 claims
    assert mock_verify_claim.call_count <= 5


@patch('src.agents.fact_checker_agent.FactCheckerAgent._extract_claims')
@patch('src.agents.fact_checker_agent.FactCheckerAgent._verify_urls_via_http')
@patch('src.agents.fact_checker_agent.FactCheckerAgent._verify_claim_via_web_research')
def test_thoroughness_thorough(mock_verify_claim, mock_verify_urls, mock_extract_claims, sample_blog_post_with_hallucinations):
    """Test thorough mode (URLs + all claims)"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock claims
    claims = [
        {'claim_text': f'Claim {i}', 'claim_type': 'fact', 'location': 'Body', 'citation': None}
        for i in range(8)
    ]
    mock_extract_claims.return_value = claims

    mock_verify_urls.return_value = {}
    mock_verify_claim.return_value = {
        'verified': True,
        'evidence': 'OK',
        'confidence': 0.8,
        'sources': []
    }

    result = agent.verify_content(
        content=sample_blog_post_with_hallucinations,
        thoroughness="thorough"
    )

    # Thorough: should verify ALL claims
    assert mock_verify_claim.call_count == 8


# ==================== Integration Tests ====================

@patch('src.agents.fact_checker_agent.ResearchAgent')
@patch('requests.head')
@patch('src.agents.fact_checker_agent.FactCheckerAgent.generate')
def test_integration_end_to_end_with_hallucinations(
    mock_generate, mock_http, mock_research_agent_class, sample_blog_post_with_hallucinations
):
    """Test end-to-end fact-checking with real hallucinations"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock claim extraction
    mock_generate.side_effect = [
        # First call: extract claims
        {
            'content': json.dumps([
                {
                    'claim_text': 'Siemens veröffentlichte 2023 eine Studie',
                    'claim_type': 'source',
                    'location': 'Einleitung',
                    'citation': 'https://www.siemens.com/studie-predictive-maintenance-2023'
                },
                {
                    'claim_text': 'BMWK neue Richtlinien',
                    'claim_type': 'source',
                    'location': 'Einleitung',
                    'citation': 'https://www.bmwk.de/gebaeudeenergiegesetz-2023'
                }
            ]),
            'tokens': {'total': 500},
            'cost': 0.001
        },
        # Second call: verify first claim
        {
            'content': json.dumps({
                'verified': False,
                'evidence': 'No such study found',
                'confidence': 0.9,
                'sources': []
            }),
            'tokens': {'total': 300},
            'cost': 0.0006
        },
        # Third call: verify second claim
        {
            'content': json.dumps({
                'verified': False,
                'evidence': 'URL does not exist',
                'confidence': 0.85,
                'sources': []
            }),
            'tokens': {'total': 300},
            'cost': 0.0006
        }
    ]

    # Mock HTTP verification (all fake)
    def http_side_effect(*args, **kwargs):
        mock_response = Mock()
        mock_response.status_code = 404
        return mock_response

    mock_http.side_effect = http_side_effect

    # Mock research agent
    mock_research_agent = Mock()
    mock_research_agent.research.return_value = {
        'sources': [],
        'keywords': [],
        'summary': 'No results found'
    }
    mock_research_agent_class.return_value = mock_research_agent

    result = agent.verify_content(
        content=sample_blog_post_with_hallucinations,
        thoroughness="medium"
    )

    # Should detect hallucinations
    assert result['valid'] is False
    assert len(result['urls_fake']) >= 2
    assert len(result['claims_failed']) >= 2
    assert len(result['hallucinations']) >= 2
    assert result['report'] is not None
    assert '❌' in result['report'] or 'REJECT' in result['report']


@patch('src.agents.fact_checker_agent.ResearchAgent')
@patch('requests.head')
@patch('src.agents.fact_checker_agent.FactCheckerAgent.generate')
def test_integration_end_to_end_all_verified(
    mock_generate, mock_http, mock_research_agent_class, sample_blog_post_all_real
):
    """Test end-to-end fact-checking with all verified content"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock claim extraction
    mock_generate.side_effect = [
        # Extract claims
        {
            'content': json.dumps([
                {
                    'claim_text': 'AI can improve efficiency by 25%',
                    'claim_type': 'statistic',
                    'location': 'Body',
                    'citation': 'https://www.mckinsey.com/industries/manufacturing'
                }
            ]),
            'tokens': {'total': 300},
            'cost': 0.0006
        },
        # Verify claim
        {
            'content': json.dumps({
                'verified': True,
                'evidence': 'McKinsey research confirms this',
                'confidence': 0.9,
                'sources': ['https://www.mckinsey.com/industries/manufacturing']
            }),
            'tokens': {'total': 300},
            'cost': 0.0006
        }
    ]

    # Mock HTTP verification (all real)
    mock_response = Mock()
    mock_response.status_code = 200
    mock_http.return_value = mock_response

    # Mock research agent
    mock_research_agent = Mock()
    mock_research_agent.research.return_value = {
        'sources': [
            {'url': 'https://www.mckinsey.com/industries/manufacturing', 'title': 'Report', 'snippet': 'Confirms claim'}
        ],
        'keywords': ['AI', 'efficiency'],
        'summary': 'Research supports the claim'
    }
    mock_research_agent_class.return_value = mock_research_agent

    result = agent.verify_content(
        content=sample_blog_post_all_real,
        thoroughness="medium"
    )

    # Should pass all checks
    assert result['valid'] is True
    assert len(result['urls_fake']) == 0
    assert len(result['claims_failed']) == 0
    assert len(result['hallucinations']) == 0
    assert '✅' in result['report'] or 'ACCEPT' in result['report']


# ==================== Error Handling Tests ====================

def test_verify_content_empty_content():
    """Test verification of empty content"""
    agent = FactCheckerAgent(api_key="test-key")

    result = agent.verify_content(content="", thoroughness="basic")

    # Should pass (nothing to check)
    assert result['valid'] is True
    assert result['claims_checked'] == 0
    assert result['urls_checked'] == 0


def test_verify_content_invalid_thoroughness():
    """Test invalid thoroughness parameter"""
    agent = FactCheckerAgent(api_key="test-key")

    with pytest.raises(FactCheckError, match="Invalid thoroughness"):
        agent.verify_content(content="test", thoroughness="invalid")


@patch('src.agents.fact_checker_agent.FactCheckerAgent.generate')
def test_verify_content_handles_llm_errors(mock_generate):
    """Test handling of LLM errors during claim extraction"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock LLM error
    mock_generate.side_effect = Exception("LLM API error")

    with pytest.raises(FactCheckError):
        agent.verify_content(content="test content", thoroughness="basic")


# ==================== Cost Calculation Tests ====================

@patch('src.agents.fact_checker_agent.FactCheckerAgent._extract_claims')
@patch('src.agents.fact_checker_agent.FactCheckerAgent._verify_urls_via_http')
def test_verify_content_tracks_cost(mock_verify_urls, mock_extract_claims):
    """Test that verification tracks total cost"""
    agent = FactCheckerAgent(api_key="test-key")

    mock_extract_claims.return_value = []
    mock_verify_urls.return_value = {}

    result = agent.verify_content(content="test", thoroughness="basic")

    # Should include cost information
    assert 'cost' in result
    assert isinstance(result['cost'], float)
    assert result['cost'] >= 0


# ==================== Logging Tests ====================

def test_verify_content_logs_start(caplog):
    """Test that verification logs start message"""
    import logging
    caplog.set_level(logging.INFO)

    with patch('src.agents.fact_checker_agent.FactCheckerAgent._extract_claims', return_value=[]):
        with patch('src.agents.fact_checker_agent.FactCheckerAgent._verify_urls_via_http', return_value={}):
            agent = FactCheckerAgent(api_key="test-key")
            agent.verify_content(content="test", thoroughness="basic")

    assert any("fact" in record.message.lower() or "verif" in record.message.lower()
               for record in caplog.records)


def test_verify_content_logs_hallucinations(caplog):
    """Test that hallucinations are logged"""
    import logging
    caplog.set_level(logging.WARNING)

    with patch('src.agents.fact_checker_agent.FactCheckerAgent._extract_claims') as mock_extract:
        with patch('src.agents.fact_checker_agent.FactCheckerAgent._verify_urls_via_http') as mock_verify:
            mock_extract.return_value = [
                {'claim_text': 'Test', 'claim_type': 'source', 'location': 'Body',
                 'citation': 'https://fake.com'}
            ]
            mock_verify.return_value = {'https://fake.com': False}

            agent = FactCheckerAgent(api_key="test-key")
            agent.verify_content(content="test", thoroughness="basic")

    # Should log fake URLs
    assert any("fake" in record.message.lower() or "hallucin" in record.message.lower()
               for record in caplog.records)


# ==================== Layer 1: Internal Consistency Tests ====================

@patch('subprocess.run')
def test_check_internal_consistency_no_issues(mock_subprocess):
    """Test internal consistency check with clean content"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock Gemini CLI response
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "consistent": True,
        "issues": [],
        "score": 0.95
    })
    mock_subprocess.return_value = mock_result

    content = "Simple blog post without contradictions"
    result = agent._check_internal_consistency(content)

    assert result['consistent'] is True
    assert len(result['issues']) == 0
    assert result['score'] >= 0.9


@patch('subprocess.run')
def test_check_internal_consistency_detects_contradictions(mock_subprocess):
    """Test detection of contradictory statements"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock Gemini CLI detecting contradiction
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "consistent": False,
        "issues": [
            {
                "type": "contradiction",
                "description": "First says costs increase, then says costs decrease",
                "location": "paragraph 2"
            }
        ],
        "score": 0.3
    })
    mock_subprocess.return_value = mock_result

    content = """
    Die Kosten steigen um 20%.
    ...
    Die Kosten sinken deutlich.
    """

    result = agent._check_internal_consistency(content)

    assert result['consistent'] is False
    assert len(result['issues']) == 1
    assert result['issues'][0]['type'] == 'contradiction'
    assert result['score'] < 0.5


@patch('subprocess.run')
def test_check_internal_consistency_detects_implausible_claims(mock_subprocess):
    """Test detection of implausible claims"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock Gemini CLI detecting implausible claim
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "consistent": False,
        "issues": [
            {
                "type": "implausible",
                "description": "99% cost reduction is unrealistic",
                "location": "section 2"
            }
        ],
        "score": 0.4
    })
    mock_subprocess.return_value = mock_result

    content = "Kostenreduktion von 99% möglich"

    result = agent._check_internal_consistency(content)

    assert result['consistent'] is False
    assert any(issue['type'] == 'implausible' for issue in result['issues'])


@patch('subprocess.run')
def test_check_internal_consistency_detects_date_conflicts(mock_subprocess):
    """Test detection of date/timeline conflicts"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock Gemini CLI detecting date conflict
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "consistent": False,
        "issues": [
            {
                "type": "date_conflict",
                "description": "Study from 2021 cited as 2023",
                "location": "references"
            }
        ],
        "score": 0.6
    })
    mock_subprocess.return_value = mock_result

    content = "Die 2021 Studie... wie die 2023 Studie zeigt"

    result = agent._check_internal_consistency(content)

    assert result['consistent'] is False
    assert any('date' in issue['type'].lower() for issue in result['issues'])


@patch('subprocess.run')
def test_check_internal_consistency_handles_cli_timeout(mock_subprocess):
    """Test handling of Gemini CLI timeout"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock timeout
    mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd=['gemini'], timeout=30)

    with pytest.raises(FactCheckError, match="timeout"):
        agent._check_internal_consistency("content")


@patch('subprocess.run')
def test_check_internal_consistency_handles_cli_error(mock_subprocess):
    """Test handling of Gemini CLI errors"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock CLI error
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "API quota exceeded"
    mock_subprocess.return_value = mock_result

    with pytest.raises(FactCheckError, match="Gemini CLI"):
        agent._check_internal_consistency("content")


@patch('subprocess.run')
def test_check_internal_consistency_handles_invalid_json(mock_subprocess):
    """Test handling of invalid JSON from Gemini CLI"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock invalid JSON
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "Not valid JSON"
    mock_subprocess.return_value = mock_result

    with pytest.raises(FactCheckError, match="parse"):
        agent._check_internal_consistency("content")


# ==================== Layer 4: Content Quality Tests ====================

@patch('subprocess.run')
def test_analyze_content_quality_high_score(mock_subprocess):
    """Test content quality analysis with high credibility"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock Gemini CLI response
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "quality_score": 8.5,
        "issues": [],
        "recommendations": []
    })
    mock_subprocess.return_value = mock_result

    content = "Well-sourced blog post with specific citations"
    result = agent._analyze_content_quality(content)

    assert result['quality_score'] >= 8.0
    assert len(result['issues']) == 0


@patch('subprocess.run')
def test_analyze_content_quality_detects_vague_claims(mock_subprocess):
    """Test detection of vague claims"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock Gemini CLI detecting vague claims
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "quality_score": 5.5,
        "issues": [
            {
                "type": "vague_claim",
                "text": "Viele Experten empfehlen...",
                "location": "intro"
            }
        ],
        "recommendations": ["Add specific expert names and credentials"]
    })
    mock_subprocess.return_value = mock_result

    content = "Viele Experten empfehlen diese Lösung"
    result = agent._analyze_content_quality(content)

    assert result['quality_score'] < 7.0
    assert len(result['issues']) > 0
    assert any(issue['type'] == 'vague_claim' for issue in result['issues'])


@patch('subprocess.run')
def test_analyze_content_quality_detects_weasel_words(mock_subprocess):
    """Test detection of weasel words"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock Gemini CLI detecting weasel words
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "quality_score": 6.0,
        "issues": [
            {
                "type": "weasel_words",
                "text": "bis zu 30%",
                "location": "section 2"
            }
        ],
        "recommendations": ["Provide actual average, not just maximum"]
    })
    mock_subprocess.return_value = mock_result

    content = "Bis zu 30% Kostenreduktion"
    result = agent._analyze_content_quality(content)

    assert any(issue['type'] == 'weasel_words' for issue in result['issues'])
    assert len(result['recommendations']) > 0


@patch('subprocess.run')
def test_analyze_content_quality_detects_missing_attribution(mock_subprocess):
    """Test detection of missing attribution"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock Gemini CLI detecting missing source
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "quality_score": 4.5,
        "issues": [
            {
                "type": "missing_attribution",
                "text": "Studien zeigen 50% Verbesserung",
                "location": "paragraph 3"
            }
        ],
        "recommendations": ["Cite specific study with author, year, journal"]
    })
    mock_subprocess.return_value = mock_result

    content = "Studien zeigen 50% Verbesserung"
    result = agent._analyze_content_quality(content)

    assert result['quality_score'] < 6.0
    assert any('attribution' in issue['type'] for issue in result['issues'])


@patch('subprocess.run')
def test_analyze_content_quality_score_range(mock_subprocess):
    """Test quality score is in valid range (0-10)"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock response
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "quality_score": 7.3,
        "issues": [],
        "recommendations": []
    })
    mock_subprocess.return_value = mock_result

    result = agent._analyze_content_quality("content")

    assert 0.0 <= result['quality_score'] <= 10.0


@patch('subprocess.run')
def test_analyze_content_quality_provides_recommendations(mock_subprocess):
    """Test that recommendations are actionable"""
    agent = FactCheckerAgent(api_key="test-key")

    # Mock response with recommendations
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "quality_score": 5.0,
        "issues": [
            {"type": "vague_claim", "text": "many say", "location": "intro"}
        ],
        "recommendations": [
            "Add specific sources",
            "Include expert credentials",
            "Provide study details"
        ]
    })
    mock_subprocess.return_value = mock_result

    result = agent._analyze_content_quality("content")

    assert len(result['recommendations']) > 0
    assert all(isinstance(rec, str) for rec in result['recommendations'])
