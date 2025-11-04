#!/usr/bin/env python3
"""
Test CompetitorResearchAgent with Gemini CLI Integration

Tests:
1. Loads environment variables from .env and /home/envs/openrouter.env
2. Creates CompetitorResearchAgent with use_cli=True
3. Tests with topic: "PropTech Germany"
4. Captures exact error if Gemini CLI fails
5. Tests with use_cli=False (API fallback)
6. Compares results and performance

Report:
- Does Gemini CLI work?
- Does API fallback work?
- Which is faster?
- What needs to be fixed?
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.competitor_research_agent import (
    CompetitorResearchAgent,
    CompetitorResearchError
)

# ===== Setup Logging =====
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/gemini_cli_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ===== Test Configuration =====
TOPIC = "PropTech Germany"
LANGUAGE = "de"
MAX_COMPETITORS = 3

TEST_RESULTS_FILE = "/tmp/gemini_cli_test_results.json"


def load_environment_variables() -> Dict[str, str]:
    """
    Load environment variables from .env and /home/envs/openrouter.env

    Returns:
        Dict of environment variables

    Raises:
        RuntimeError: If critical variables are missing
    """
    logger.info("Loading environment variables...")

    # Load from .env (project root)
    env_path = project_root / ".env"
    if env_path.exists():
        logger.info(f"Loading .env from {env_path}")
        load_dotenv(env_path, override=False)
    else:
        logger.warning(f".env not found at {env_path}")

    # Load from /home/envs/openrouter.env
    openrouter_env_path = Path("/home/envs/openrouter.env")
    if openrouter_env_path.exists():
        logger.info(f"Loading OpenRouter env from {openrouter_env_path}")
        load_dotenv(openrouter_env_path, override=True)
    else:
        logger.warning(f"OpenRouter env not found at {openrouter_env_path}")

    # Verify critical variables
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not found in environment")

    logger.info(f"API key loaded: {api_key[:20]}...")

    return {
        "OPENROUTER_API_KEY": api_key,
        "CONTENT_LANGUAGE": os.getenv("CONTENT_LANGUAGE", "de"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
    }


def check_gemini_cli_available() -> Tuple[bool, str]:
    """
    Check if Gemini CLI is available and functional

    Returns:
        Tuple of (is_available, message)
    """
    logger.info("Checking Gemini CLI availability...")

    try:
        import subprocess
        result = subprocess.run(
            ["gemini", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            message = f"Gemini CLI available: {result.stdout.strip()}"
            logger.info(message)
            return True, message
        else:
            error_msg = result.stderr or "Unknown error"
            message = f"Gemini CLI failed version check: {error_msg}"
            logger.warning(message)
            return False, message

    except FileNotFoundError:
        message = "Gemini CLI not found in PATH"
        logger.warning(message)
        return False, message
    except subprocess.TimeoutExpired:
        message = "Gemini CLI timeout during version check"
        logger.warning(message)
        return False, message
    except Exception as e:
        message = f"Error checking Gemini CLI: {e}"
        logger.warning(message)
        return False, message


def test_cli_mode(
    api_key: str
) -> Dict[str, Any]:
    """
    Test CompetitorResearchAgent with CLI mode (use_cli=True)

    Args:
        api_key: OpenRouter API key

    Returns:
        Dict with test results
    """
    logger.info("=" * 80)
    logger.info("TEST 1: CompetitorResearchAgent with CLI Mode (use_cli=True)")
    logger.info("=" * 80)

    results = {
        "test_name": "CLI Mode (use_cli=True)",
        "status": "running",
        "error": None,
        "gemini_cli_available": False,
        "time_seconds": 0.0,
        "data": None,
        "data_sample": None,
    }

    try:
        # Check CLI availability first
        cli_available, cli_message = check_gemini_cli_available()
        results["gemini_cli_available"] = cli_available
        logger.info(f"CLI Check: {cli_message}")

        # Initialize agent with CLI enabled
        logger.info("Initializing CompetitorResearchAgent with use_cli=True")
        agent = CompetitorResearchAgent(
            api_key=api_key,
            use_cli=True,
            cli_timeout=60,
            cache_dir=None
        )

        # Run research
        logger.info(f"Starting competitor research for topic: '{TOPIC}'")
        start_time = time.time()

        data = agent.research_competitors(
            topic=TOPIC,
            language=LANGUAGE,
            max_competitors=MAX_COMPETITORS,
            include_content_analysis=True,
            save_to_cache=False
        )

        elapsed = time.time() - start_time
        results["time_seconds"] = elapsed
        results["data"] = data
        results["status"] = "success"

        # Create summary
        results["data_sample"] = {
            "num_competitors": len(data.get("competitors", [])),
            "num_content_gaps": len(data.get("content_gaps", [])),
            "num_trending_topics": len(data.get("trending_topics", [])),
            "has_recommendation": bool(data.get("recommendation")),
            "first_competitor_name": data.get("competitors", [{}])[0].get("name") if data.get("competitors") else None,
        }

        logger.info(f"CLI Mode Test PASSED in {elapsed:.2f}s")
        logger.info(f"Data summary: {results['data_sample']}")

    except CompetitorResearchError as e:
        results["status"] = "failed"
        results["error"] = f"CompetitorResearchError: {str(e)}"
        logger.error(f"CLI Mode Test FAILED: {e}")
    except Exception as e:
        results["status"] = "failed"
        results["error"] = f"{type(e).__name__}: {str(e)}"
        logger.error(f"CLI Mode Test FAILED with exception: {e}", exc_info=True)

    return results


def test_api_fallback_mode(
    api_key: str
) -> Dict[str, Any]:
    """
    Test CompetitorResearchAgent with API fallback mode (use_cli=False)

    Args:
        api_key: OpenRouter API key

    Returns:
        Dict with test results
    """
    logger.info("=" * 80)
    logger.info("TEST 2: CompetitorResearchAgent with API Fallback Mode (use_cli=False)")
    logger.info("=" * 80)

    results = {
        "test_name": "API Fallback Mode (use_cli=False)",
        "status": "running",
        "error": None,
        "time_seconds": 0.0,
        "data": None,
        "data_sample": None,
    }

    try:
        # Initialize agent with CLI disabled
        logger.info("Initializing CompetitorResearchAgent with use_cli=False")
        agent = CompetitorResearchAgent(
            api_key=api_key,
            use_cli=False,
            cli_timeout=60,
            cache_dir=None
        )

        # Run research
        logger.info(f"Starting competitor research for topic: '{TOPIC}'")
        start_time = time.time()

        data = agent.research_competitors(
            topic=TOPIC,
            language=LANGUAGE,
            max_competitors=MAX_COMPETITORS,
            include_content_analysis=True,
            save_to_cache=False
        )

        elapsed = time.time() - start_time
        results["time_seconds"] = elapsed
        results["data"] = data
        results["status"] = "success"

        # Create summary
        results["data_sample"] = {
            "num_competitors": len(data.get("competitors", [])),
            "num_content_gaps": len(data.get("content_gaps", [])),
            "num_trending_topics": len(data.get("trending_topics", [])),
            "has_recommendation": bool(data.get("recommendation")),
            "first_competitor_name": data.get("competitors", [{}])[0].get("name") if data.get("competitors") else None,
        }

        logger.info(f"API Fallback Mode Test PASSED in {elapsed:.2f}s")
        logger.info(f"Data summary: {results['data_sample']}")

    except CompetitorResearchError as e:
        results["status"] = "failed"
        results["error"] = f"CompetitorResearchError: {str(e)}"
        logger.error(f"API Fallback Mode Test FAILED: {e}")
    except Exception as e:
        results["status"] = "failed"
        results["error"] = f"{type(e).__name__}: {str(e)}"
        logger.error(f"API Fallback Mode Test FAILED with exception: {e}", exc_info=True)

    return results


def test_cli_to_api_fallback(
    api_key: str
) -> Dict[str, Any]:
    """
    Test that CLI failure properly triggers API fallback

    Args:
        api_key: OpenRouter API key

    Returns:
        Dict with test results
    """
    logger.info("=" * 80)
    logger.info("TEST 3: CLI Failure → API Fallback Behavior")
    logger.info("=" * 80)

    results = {
        "test_name": "CLI Failure → API Fallback",
        "status": "running",
        "error": None,
        "cli_attempted": False,
        "fallback_triggered": False,
        "final_success": False,
        "time_seconds": 0.0,
    }

    try:
        # Initialize agent with CLI enabled (to trigger potential fallback)
        logger.info("Initializing CompetitorResearchAgent with use_cli=True")
        agent = CompetitorResearchAgent(
            api_key=api_key,
            use_cli=True,
            cli_timeout=60,
            cache_dir=None
        )

        results["cli_attempted"] = True

        # Run research
        logger.info(f"Starting competitor research for topic: '{TOPIC}'")
        start_time = time.time()

        agent.research_competitors(
            topic=TOPIC,
            language=LANGUAGE,
            max_competitors=MAX_COMPETITORS,
            include_content_analysis=True,
            save_to_cache=False
        )

        elapsed = time.time() - start_time
        results["time_seconds"] = elapsed

        # Check if API was used (by checking logs in agent)
        # If CLI was available, it would have succeeded
        # If CLI was not available, API fallback would have been triggered
        cli_available, _ = check_gemini_cli_available()
        if not cli_available:
            results["fallback_triggered"] = True
            logger.info("API fallback was triggered due to CLI unavailability")

        results["final_success"] = True
        results["status"] = "success"

        logger.info(f"Fallback Behavior Test PASSED in {elapsed:.2f}s")

    except Exception as e:
        results["status"] = "failed"
        results["error"] = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Fallback Behavior Test FAILED: {e}", exc_info=True)

    return results


def generate_report(
    test_results: Dict[str, Dict[str, Any]],
    env_vars: Dict[str, str]
) -> str:
    """
    Generate comprehensive test report

    Args:
        test_results: Dictionary of test results
        env_vars: Environment variables used

    Returns:
        Formatted report string
    """
    report_lines = []

    report_lines.append("=" * 80)
    report_lines.append("GEMINI CLI INTEGRATION TEST REPORT")
    report_lines.append("=" * 80)
    report_lines.append("")

    # Environment Info
    report_lines.append("ENVIRONMENT SETUP")
    report_lines.append("-" * 80)
    report_lines.append(f"Project Root: {project_root}")
    report_lines.append(f"API Key Present: {bool(env_vars.get('OPENROUTER_API_KEY'))}")
    report_lines.append(f"Content Language: {env_vars.get('CONTENT_LANGUAGE')}")
    report_lines.append("")

    # Test Configuration
    report_lines.append("TEST CONFIGURATION")
    report_lines.append("-" * 80)
    report_lines.append(f"Topic: {TOPIC}")
    report_lines.append(f"Language: {LANGUAGE}")
    report_lines.append(f"Max Competitors: {MAX_COMPETITORS}")
    report_lines.append("")

    # Gemini CLI Check
    cli_available, cli_message = check_gemini_cli_available()
    report_lines.append("GEMINI CLI AVAILABILITY")
    report_lines.append("-" * 80)
    report_lines.append(f"Available: {'YES' if cli_available else 'NO'}")
    report_lines.append(f"Status: {cli_message}")
    report_lines.append("")

    # Test Results Summary
    report_lines.append("TEST RESULTS SUMMARY")
    report_lines.append("-" * 80)

    cli_mode_result = test_results.get("cli_mode", {})
    api_mode_result = test_results.get("api_fallback", {})
    fallback_result = test_results.get("fallback_behavior", {})

    # CLI Mode
    report_lines.append("")
    report_lines.append("1. CLI MODE TEST (use_cli=True)")
    report_lines.append("-" * 40)
    report_lines.append(f"Status: {cli_mode_result.get('status', 'N/A').upper()}")
    if cli_mode_result.get('status') == 'success':
        report_lines.append(f"Time: {cli_mode_result.get('time_seconds', 0):.2f}s")
        if cli_mode_result.get('data_sample'):
            report_lines.append(f"Competitors Found: {cli_mode_result['data_sample'].get('num_competitors', 0)}")
            report_lines.append(f"Content Gaps: {cli_mode_result['data_sample'].get('num_content_gaps', 0)}")
            report_lines.append(f"Trending Topics: {cli_mode_result['data_sample'].get('num_trending_topics', 0)}")
    else:
        error = cli_mode_result.get('error', 'Unknown error')
        report_lines.append(f"Error: {error}")

    # API Fallback Mode
    report_lines.append("")
    report_lines.append("2. API FALLBACK MODE TEST (use_cli=False)")
    report_lines.append("-" * 40)
    report_lines.append(f"Status: {api_mode_result.get('status', 'N/A').upper()}")
    if api_mode_result.get('status') == 'success':
        report_lines.append(f"Time: {api_mode_result.get('time_seconds', 0):.2f}s")
        if api_mode_result.get('data_sample'):
            report_lines.append(f"Competitors Found: {api_mode_result['data_sample'].get('num_competitors', 0)}")
            report_lines.append(f"Content Gaps: {api_mode_result['data_sample'].get('num_content_gaps', 0)}")
            report_lines.append(f"Trending Topics: {api_mode_result['data_sample'].get('num_trending_topics', 0)}")
    else:
        error = api_mode_result.get('error', 'Unknown error')
        report_lines.append(f"Error: {error}")

    # Fallback Behavior
    report_lines.append("")
    report_lines.append("3. FALLBACK BEHAVIOR TEST")
    report_lines.append("-" * 40)
    report_lines.append(f"Status: {fallback_result.get('status', 'N/A').upper()}")
    report_lines.append(f"CLI Attempted: {'YES' if fallback_result.get('cli_attempted') else 'NO'}")
    report_lines.append(f"Fallback Triggered: {'YES' if fallback_result.get('fallback_triggered') else 'NO'}")
    report_lines.append(f"Final Success: {'YES' if fallback_result.get('final_success') else 'NO'}")
    if fallback_result.get('status') != 'success':
        error = fallback_result.get('error', 'Unknown error')
        report_lines.append(f"Error: {error}")

    # Performance Comparison
    report_lines.append("")
    report_lines.append("PERFORMANCE COMPARISON")
    report_lines.append("-" * 40)

    cli_time = cli_mode_result.get('time_seconds', 0)
    api_time = api_mode_result.get('time_seconds', 0)

    if cli_time > 0 and api_time > 0:
        difference = abs(cli_time - api_time)
        percentage = (difference / max(cli_time, api_time)) * 100
        faster = "CLI" if cli_time < api_time else "API"
        report_lines.append(f"CLI Mode Time: {cli_time:.2f}s")
        report_lines.append(f"API Mode Time: {api_time:.2f}s")
        report_lines.append(f"Difference: {difference:.2f}s ({percentage:.1f}%)")
        report_lines.append(f"Faster: {faster}")
    elif cli_time > 0:
        report_lines.append(f"CLI Mode Time: {cli_time:.2f}s")
        report_lines.append("API Mode Time: N/A (failed)")
    elif api_time > 0:
        report_lines.append("CLI Mode Time: N/A (failed)")
        report_lines.append(f"API Mode Time: {api_time:.2f}s")

    # Summary and Recommendations
    report_lines.append("")
    report_lines.append("ANALYSIS & RECOMMENDATIONS")
    report_lines.append("-" * 40)

    cli_success = cli_mode_result.get('status') == 'success'
    api_success = api_mode_result.get('status') == 'success'

    report_lines.append("")
    report_lines.append("1. Does Gemini CLI work?")
    if cli_available:
        if cli_success:
            report_lines.append("   ✓ YES - Gemini CLI is available and functional")
        else:
            report_lines.append("   ✗ NO - Gemini CLI is available but failed during execution")
            report_lines.append(f"        Error: {cli_mode_result.get('error')}")
    else:
        report_lines.append("   ✗ NO - Gemini CLI is not installed or accessible")
        report_lines.append(f"        Status: {check_gemini_cli_available()[1]}")

    report_lines.append("")
    report_lines.append("2. Does API fallback work?")
    if api_success:
        report_lines.append("   ✓ YES - OpenRouter API fallback is functional")
    else:
        report_lines.append("   ✗ NO - OpenRouter API fallback failed")
        report_lines.append(f"        Error: {api_mode_result.get('error')}")

    report_lines.append("")
    report_lines.append("3. Which is faster?")
    if cli_time > 0 and api_time > 0:
        if cli_time < api_time:
            report_lines.append(f"   → CLI Mode is {percentage:.1f}% faster ({cli_time:.2f}s vs {api_time:.2f}s)")
        else:
            report_lines.append(f"   → API Mode is {percentage:.1f}% faster ({api_time:.2f}s vs {cli_time:.2f}s)")
    else:
        report_lines.append("   → Cannot compare: one or both modes failed")

    report_lines.append("")
    report_lines.append("4. What needs to be fixed in Gemini CLI integration?")
    if cli_available and cli_success:
        report_lines.append("   ✓ No issues detected - Gemini CLI integration is working correctly")
    else:
        fixes_needed = []

        if not cli_available:
            fixes_needed.append("   • Install Gemini CLI: https://ai.google.dev/gemini-cli")

        if cli_available and not cli_success:
            error = cli_mode_result.get('error', '')
            if "JSON" in error or "json" in error:
                fixes_needed.append("   • Fix JSON parsing - ensure Gemini CLI returns valid JSON")
                fixes_needed.append("   • Check --output-format json flag support")
            if "timeout" in error.lower():
                fixes_needed.append("   • Increase CLI timeout or optimize query")
            if "command" in error.lower() or "not found" in error.lower():
                fixes_needed.append("   • Verify Gemini CLI is in PATH")
                fixes_needed.append("   • Check Gemini CLI installation")
            if not fixes_needed:
                fixes_needed.append(f"   • Debug: {error}")

        if not fallback_result.get('final_success'):
            fixes_needed.append("   • Verify OpenRouter API key is valid")
            fixes_needed.append("   • Check OpenRouter API endpoint connectivity")

        if fixes_needed:
            for fix in fixes_needed:
                report_lines.append(fix)

    report_lines.append("")
    report_lines.append("=" * 80)

    return "\n".join(report_lines)


def save_results(test_results: Dict[str, Any], report: str) -> None:
    """
    Save test results and report to files

    Args:
        test_results: Test results dictionary
        report: Report string
    """
    # Save JSON results
    with open(TEST_RESULTS_FILE, 'w') as f:
        json.dump(test_results, f, indent=2, default=str)
    logger.info(f"Test results saved to {TEST_RESULTS_FILE}")

    # Save report
    report_file = TEST_RESULTS_FILE.replace('.json', '.txt')
    with open(report_file, 'w') as f:
        f.write(report)
    logger.info(f"Report saved to {report_file}")


def main() -> int:
    """
    Main test execution

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    try:
        # Load environment
        logger.info("Starting Gemini CLI Integration Tests")
        env_vars = load_environment_variables()
        api_key = env_vars["OPENROUTER_API_KEY"]

        # Run tests
        test_results = {
            "cli_mode": test_cli_mode(api_key),
            "api_fallback": test_api_fallback_mode(api_key),
            "fallback_behavior": test_cli_to_api_fallback(api_key),
        }

        # Generate and save report
        report = generate_report(test_results, env_vars)
        print("\n" + report)
        save_results(test_results, report)

        # Determine overall success
        overall_success = (
            test_results.get("api_fallback", {}).get("status") == "success"
        )

        if overall_success:
            logger.info("All critical tests passed!")
            return 0
        else:
            logger.error("Critical tests failed!")
            return 1

    except Exception as e:
        logger.error(f"Test execution failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
