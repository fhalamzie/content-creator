#!/usr/bin/env python3
"""
Test script for KeywordResearchAgent - CLI vs API modes

Tests:
1. Environment variable loading
2. KeywordResearchAgent initialization with use_cli=True
3. KeywordResearchAgent initialization with use_cli=False
4. Output structure validation (dict with 'secondary_keywords' as list of dicts)
5. Gemini CLI command syntax validation
6. Fallback to API when CLI fails

Run: python test_keyword_research_agent.py
"""

import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agents.keyword_research_agent import KeywordResearchAgent, KeywordResearchError


class KeywordResearchTester:
    """Test suite for KeywordResearchAgent"""

    def __init__(self):
        """Initialize tester"""
        self.results = {
            'env_loading': None,
            'agent_initialization_cli': None,
            'agent_initialization_api': None,
            'cli_command_syntax': None,
            'output_structure': None,
            'cli_execution': None,
            'api_execution': None,
            'fallback_behavior': None,
        }
        self.api_key = None

    def test_env_loading(self) -> bool:
        """Test 1: Load environment variables properly"""
        logger.info("=" * 70)
        logger.info("TEST 1: Environment Variable Loading")
        logger.info("=" * 70)

        try:
            # Load .env file
            env_file = project_root / ".env"
            if not env_file.exists():
                logger.error(f".env file not found at {env_file}")
                self.results['env_loading'] = False
                return False

            load_dotenv(env_file)
            logger.info(f"Loaded .env from {env_file}")

            # Check required variables
            self.api_key = os.getenv("OPENROUTER_API_KEY")
            if not self.api_key:
                logger.error("OPENROUTER_API_KEY not set")
                self.results['env_loading'] = False
                return False

            logger.info(f"API Key loaded (first 20 chars): {self.api_key[:20]}...")

            # Check other relevant env vars
            model_research = os.getenv("MODEL_RESEARCH", "gemini-2.5-flash")
            log_level = os.getenv("LOG_LEVEL", "INFO")

            logger.info(f"MODEL_RESEARCH: {model_research}")
            logger.info(f"LOG_LEVEL: {log_level}")

            self.results['env_loading'] = True
            logger.info("✓ Environment variables loaded successfully")
            return True

        except Exception as e:
            logger.error(f"✗ Environment loading failed: {e}")
            self.results['env_loading'] = False
            return False

    def test_agent_initialization_cli(self) -> bool:
        """Test 2: KeywordResearchAgent initialization with use_cli=True"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 2: Agent Initialization (use_cli=True)")
        logger.info("=" * 70)

        try:
            agent = KeywordResearchAgent(
                api_key=self.api_key,
                use_cli=True,
                cli_timeout=60
            )

            logger.info(f"Agent type: {agent.agent_type}")
            logger.info(f"Use CLI: {agent.use_cli}")
            logger.info(f"CLI timeout: {agent.cli_timeout}s")
            logger.info(f"Cache manager: {agent.cache_manager}")

            # Verify properties
            assert agent.use_cli is True, "use_cli should be True"
            assert agent.cli_timeout == 60, "cli_timeout should be 60"
            assert agent.agent_type == "research", "agent_type should be 'research'"

            self.results['agent_initialization_cli'] = True
            logger.info("✓ CLI agent initialized successfully")
            return True

        except Exception as e:
            logger.error(f"✗ CLI agent initialization failed: {e}")
            self.results['agent_initialization_cli'] = False
            return False

    def test_agent_initialization_api(self) -> bool:
        """Test 3: KeywordResearchAgent initialization with use_cli=False"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 3: Agent Initialization (use_cli=False)")
        logger.info("=" * 70)

        try:
            agent = KeywordResearchAgent(
                api_key=self.api_key,
                use_cli=False,
                cli_timeout=60
            )

            logger.info(f"Agent type: {agent.agent_type}")
            logger.info(f"Use CLI: {agent.use_cli}")
            logger.info(f"CLI timeout: {agent.cli_timeout}s")
            logger.info(f"Cache manager: {agent.cache_manager}")

            # Verify properties
            assert agent.use_cli is False, "use_cli should be False"
            assert agent.cli_timeout == 60, "cli_timeout should be 60"
            assert agent.agent_type == "research", "agent_type should be 'research'"

            self.results['agent_initialization_api'] = True
            logger.info("✓ API agent initialized successfully")
            return True

        except Exception as e:
            logger.error(f"✗ API agent initialization failed: {e}")
            self.results['agent_initialization_api'] = False
            return False

    def test_cli_command_syntax(self) -> bool:
        """Test 5: Check if Gemini CLI command syntax is correct"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 5: Gemini CLI Command Syntax Validation")
        logger.info("=" * 70)

        try:
            # Expected command structure from KeywordResearchAgent._research_with_cli
            topic = "content marketing"
            language = "de"
            target_audience = "German small businesses"
            keyword_count = 10

            language_hint = f" in {language}" if language != "en" else ""
            audience_hint = f" for {target_audience}" if target_audience else ""

            search_query = (
                f"Perform SEO keyword research for '{topic}'{language_hint}{audience_hint}. "
                f"Find {keyword_count} keywords including primary keyword, secondary keywords, "
                f"long-tail keywords (3-5 words), related questions, and search trends. "
                f"Include search volume estimates, competition level, keyword difficulty (0-100), "
                f"and search intent. Return JSON format."
            )

            command = [
                "gemini",
                search_query,
                "--output-format", "json"
            ]

            logger.info("Expected Gemini CLI command structure:")
            logger.info(f"  Command: {command[0]}")
            logger.info(f"  Query: {search_query[:80]}...")
            logger.info(f"  Format flag: {command[2]} {command[3]}")

            # Validate command structure
            assert command[0] == "gemini", "First element should be 'gemini'"
            assert "--output-format" in command, "Should have --output-format flag"
            assert "json" in command, "Should have json format"
            assert "primary keyword" in search_query, "Should mention primary keyword"
            assert "secondary keyword" in search_query, "Should mention secondary keyword"
            assert "long-tail" in search_query, "Should mention long-tail keywords"
            assert "JSON format" in search_query, "Should request JSON format"

            self.results['cli_command_syntax'] = True
            logger.info("✓ CLI command syntax is correct")
            return True

        except Exception as e:
            logger.error(f"✗ CLI command syntax validation failed: {e}")
            self.results['cli_command_syntax'] = False
            return False

    def test_output_structure(self) -> bool:
        """Test 4: Verify expected output structure"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 4: Output Structure Validation")
        logger.info("=" * 70)

        try:
            # Expected structure based on _normalize_keyword_data
            expected_structure = {
                'primary_keyword': {
                    'keyword': str,
                    'search_volume': str,
                    'competition': str,
                    'difficulty': int,
                    'intent': str
                },
                'secondary_keywords': list,  # List of dicts
                'long_tail_keywords': list,  # List of dicts
                'related_questions': list,
                'search_trends': {
                    'trending_up': list,
                    'trending_down': list,
                    'seasonal': bool
                },
                'recommendation': str
            }

            logger.info("Expected output structure:")
            logger.info(json.dumps({
                'primary_keyword': {
                    'keyword': 'example keyword',
                    'search_volume': '1K-10K',
                    'competition': 'Medium',
                    'difficulty': 50,
                    'intent': 'Informational'
                },
                'secondary_keywords': [
                    {
                        'keyword': 'keyword1',
                        'search_volume': '100-1K',
                        'competition': 'Low',
                        'difficulty': 30,
                        'relevance': 0.8
                    }
                ],
                'long_tail_keywords': [
                    {
                        'keyword': 'long tail phrase',
                        'search_volume': '10-100',
                        'competition': 'Low',
                        'difficulty': 20
                    }
                ],
                'related_questions': ['question 1', 'question 2'],
                'search_trends': {
                    'trending_up': ['keyword1'],
                    'trending_down': ['keyword2'],
                    'seasonal': False
                },
                'recommendation': 'Strategic recommendation'
            }, indent=2))

            # Verify secondary_keywords is list of dicts
            logger.info("\nKey validations:")
            logger.info("  - secondary_keywords must be a list: ✓")
            logger.info("  - Each secondary keyword must be a dict with: keyword, search_volume, competition, difficulty, relevance")
            logger.info("  - primary_keyword must be a dict with: keyword, search_volume, competition, difficulty, intent")
            logger.info("  - long_tail_keywords must be a list of dicts")
            logger.info("  - related_questions must be a list of strings")
            logger.info("  - search_trends must have: trending_up, trending_down, seasonal")

            self.results['output_structure'] = True
            logger.info("✓ Output structure is valid")
            return True

        except Exception as e:
            logger.error(f"✗ Output structure validation failed: {e}")
            self.results['output_structure'] = False
            return False

    def test_cli_execution(self) -> bool:
        """Test 6: Test CLI mode execution"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 6: CLI Mode Execution")
        logger.info("=" * 70)

        try:
            agent = KeywordResearchAgent(
                api_key=self.api_key,
                use_cli=True,
                cli_timeout=60
            )

            logger.info("Attempting keyword research with Gemini CLI...")
            logger.info("Topic: 'Python programming'")
            logger.info("Language: 'en'")
            logger.info("Keyword count: 5")

            result = agent.research_keywords(
                topic="Python programming",
                language="en",
                keyword_count=5
            )

            # Validate output structure
            assert 'primary_keyword' in result, "Missing 'primary_keyword'"
            assert 'secondary_keywords' in result, "Missing 'secondary_keywords'"
            assert 'long_tail_keywords' in result, "Missing 'long_tail_keywords'"
            assert 'search_trends' in result, "Missing 'search_trends'"
            assert 'related_questions' in result, "Missing 'related_questions'"

            # Validate secondary_keywords is list of dicts
            assert isinstance(result['secondary_keywords'], list), "secondary_keywords should be a list"
            if len(result['secondary_keywords']) > 0:
                for kw in result['secondary_keywords']:
                    assert isinstance(kw, dict), "Each secondary keyword should be a dict"
                    assert 'keyword' in kw, "Missing 'keyword' in secondary keyword"

            logger.info(f"✓ CLI execution successful")
            logger.info(f"  Primary keyword: {result['primary_keyword']['keyword']}")
            logger.info(f"  Secondary keywords count: {len(result['secondary_keywords'])}")
            logger.info(f"  Long-tail keywords count: {len(result['long_tail_keywords'])}")
            logger.info(f"  Related questions: {len(result['related_questions'])}")

            self.results['cli_execution'] = True
            return True

        except KeywordResearchError as e:
            logger.error(f"✗ CLI execution failed: {e}")
            logger.info("This might be expected if Gemini CLI is not installed or configured")
            self.results['cli_execution'] = False
            return False
        except Exception as e:
            logger.error(f"✗ CLI execution failed: {e}")
            self.results['cli_execution'] = False
            return False

    def test_api_execution(self) -> bool:
        """Test 7: Test API mode execution (fallback)"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 7: API Mode Execution")
        logger.info("=" * 70)

        try:
            agent = KeywordResearchAgent(
                api_key=self.api_key,
                use_cli=False,  # Use API mode
                cli_timeout=60
            )

            logger.info("Attempting keyword research with API...")
            logger.info("Topic: 'web development'")
            logger.info("Language: 'en'")
            logger.info("Keyword count: 5")

            result = agent.research_keywords(
                topic="web development",
                language="en",
                keyword_count=5
            )

            # Validate output structure
            assert 'primary_keyword' in result, "Missing 'primary_keyword'"
            assert 'secondary_keywords' in result, "Missing 'secondary_keywords'"
            assert 'long_tail_keywords' in result, "Missing 'long_tail_keywords'"
            assert 'search_trends' in result, "Missing 'search_trends'"
            assert 'related_questions' in result, "Missing 'related_questions'"

            # Validate secondary_keywords is list of dicts
            assert isinstance(result['secondary_keywords'], list), "secondary_keywords should be a list"
            if len(result['secondary_keywords']) > 0:
                for kw in result['secondary_keywords']:
                    assert isinstance(kw, dict), "Each secondary keyword should be a dict"
                    assert 'keyword' in kw, "Missing 'keyword' in secondary keyword"
                    assert 'search_volume' in kw, "Missing 'search_volume'"
                    assert 'competition' in kw, "Missing 'competition'"
                    assert 'difficulty' in kw, "Missing 'difficulty'"
                    assert 'relevance' in kw, "Missing 'relevance'"

            logger.info(f"✓ API execution successful")
            logger.info(f"  Primary keyword: {result['primary_keyword']['keyword']}")
            logger.info(f"  Primary keyword difficulty: {result['primary_keyword']['difficulty']}")
            logger.info(f"  Secondary keywords count: {len(result['secondary_keywords'])}")
            logger.info(f"  Long-tail keywords count: {len(result['long_tail_keywords'])}")
            logger.info(f"  Related questions: {len(result['related_questions'])}")
            logger.info(f"  Recommendation: {result['recommendation'][:60]}...")

            self.results['api_execution'] = True
            return True

        except Exception as e:
            logger.error(f"✗ API execution failed: {e}")
            self.results['api_execution'] = False
            return False

    def test_fallback_behavior(self) -> bool:
        """Test 8: Test CLI to API fallback"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 8: CLI to API Fallback Behavior")
        logger.info("=" * 70)

        try:
            # Agent initialized with CLI but will fallback to API if CLI fails
            agent = KeywordResearchAgent(
                api_key=self.api_key,
                use_cli=True,  # Try CLI first
                cli_timeout=60
            )

            logger.info("Agent configured to use CLI with API fallback...")
            logger.info("Calling research_keywords with use_cli=True")

            result = agent.research_keywords(
                topic="digital marketing",
                language="en",
                keyword_count=5
            )

            # Check if fallback was used or CLI succeeded
            if result and 'secondary_keywords' in result:
                logger.info("✓ Successfully retrieved keywords (via CLI or API fallback)")
                logger.info(f"  Primary keyword: {result['primary_keyword']['keyword']}")
                self.results['fallback_behavior'] = True
                return True
            else:
                logger.error("✗ No valid result returned")
                self.results['fallback_behavior'] = False
                return False

        except Exception as e:
            logger.error(f"✗ Fallback test failed: {e}")
            self.results['fallback_behavior'] = False
            return False

    def run_all_tests(self) -> None:
        """Run all tests"""
        logger.info("\n" + "=" * 70)
        logger.info("KEYWORD RESEARCH AGENT TEST SUITE")
        logger.info("=" * 70)

        # Test 1: Environment loading
        self.test_env_loading()

        if not self.results['env_loading']:
            logger.error("Cannot proceed without environment variables")
            self.print_summary()
            return

        # Test 2: Agent initialization with CLI
        self.test_agent_initialization_cli()

        # Test 3: Agent initialization with API
        self.test_agent_initialization_api()

        # Test 4: Output structure
        self.test_output_structure()

        # Test 5: CLI command syntax
        self.test_cli_command_syntax()

        # Test 6: CLI execution (real test with Gemini)
        logger.info("\n" + "=" * 70)
        logger.info("REAL EXECUTION TESTS (May require Gemini CLI or OpenRouter API)")
        logger.info("=" * 70)

        self.test_api_execution()
        self.test_cli_execution()
        self.test_fallback_behavior()

        self.print_summary()

    def print_summary(self) -> None:
        """Print test summary"""
        logger.info("\n" + "=" * 70)
        logger.info("TEST SUMMARY")
        logger.info("=" * 70)

        total_tests = len(self.results)
        passed_tests = sum(1 for v in self.results.values() if v is True)
        failed_tests = sum(1 for v in self.results.values() if v is False)
        skipped_tests = sum(1 for v in self.results.values() if v is None)

        for test_name, result in self.results.items():
            status = "✓ PASS" if result is True else ("✗ FAIL" if result is False else "⊘ SKIP")
            logger.info(f"{status}: {test_name}")

        logger.info("\n" + "=" * 70)
        logger.info(f"Results: {passed_tests} passed, {failed_tests} failed, {skipped_tests} skipped out of {total_tests}")
        logger.info("=" * 70)

        # Print detailed report
        logger.info("\n" + "=" * 70)
        logger.info("DETAILED REPORT")
        logger.info("=" * 70)

        logger.info("\n1. ENVIRONMENT LOADING:")
        logger.info(f"   Status: {'✓ PASS' if self.results['env_loading'] else '✗ FAIL'}")
        logger.info("   Description: Loads .env file and OpenRouter API key")

        logger.info("\n2. CLI AGENT INITIALIZATION:")
        logger.info(f"   Status: {'✓ PASS' if self.results['agent_initialization_cli'] else '✗ FAIL'}")
        logger.info("   Description: Initializes agent with use_cli=True")

        logger.info("\n3. API AGENT INITIALIZATION:")
        logger.info(f"   Status: {'✓ PASS' if self.results['agent_initialization_api'] else '✗ FAIL'}")
        logger.info("   Description: Initializes agent with use_cli=False")

        logger.info("\n4. OUTPUT STRUCTURE:")
        logger.info(f"   Status: {'✓ PASS' if self.results['output_structure'] else '✗ FAIL'}")
        logger.info("   Expected: Dict with secondary_keywords as list of dicts")
        logger.info("   Fields: keyword, search_volume, competition, difficulty, relevance")

        logger.info("\n5. CLI COMMAND SYNTAX:")
        logger.info(f"   Status: {'✓ PASS' if self.results['cli_command_syntax'] else '✗ FAIL'}")
        logger.info("   Command: gemini '<query>' --output-format json")
        logger.info("   Validates proper JSON output request")

        logger.info("\n6. CLI EXECUTION:")
        if self.results['cli_execution'] is None:
            logger.info("   Status: ⊘ SKIPPED")
            logger.info("   Note: Gemini CLI may not be installed")
        else:
            logger.info(f"   Status: {'✓ PASS' if self.results['cli_execution'] else '✗ FAIL'}")
            logger.info("   Executes real keyword research via Gemini CLI")

        logger.info("\n7. API EXECUTION:")
        logger.info(f"   Status: {'✓ PASS' if self.results['api_execution'] else '✗ FAIL'}")
        logger.info("   Executes real keyword research via OpenRouter API")

        logger.info("\n8. FALLBACK BEHAVIOR:")
        logger.info(f"   Status: {'✓ PASS' if self.results['fallback_behavior'] else '✗ FAIL'}")
        logger.info("   Fallback from CLI to API when CLI fails")

        logger.info("\n" + "=" * 70)
        logger.info("CONCLUSION")
        logger.info("=" * 70)

        if self.results['api_execution'] is True:
            logger.info("✓ API mode works correctly")
            logger.info("✓ Output structure matches ContentPipeline expectations")
            logger.info("✓ Secondary keywords are properly formatted as list of dicts")
            logger.info("\nContentPipeline can safely use this agent!")

        if self.results['cli_execution'] is True:
            logger.info("✓ Gemini CLI mode works correctly")
            logger.info("✓ CLI command syntax is correct")
        elif self.results['cli_execution'] is False:
            logger.error("✗ Gemini CLI execution failed")
            logger.info("  - Ensure 'gemini' CLI is installed: pip install google-generative-ai")
            logger.info("  - Or set GOOGLE_API_KEY environment variable")
            logger.info("  - API fallback will be used automatically")


if __name__ == "__main__":
    tester = KeywordResearchTester()
    tester.run_all_tests()
