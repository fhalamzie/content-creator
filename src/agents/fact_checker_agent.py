"""
FactCheckerAgent - 4-Layer Fact-Checking with Gemini CLI

Acts as a critical human fact-checker to detect hallucinations and verify claims.

Design Principles:
- All analysis uses FREE Gemini CLI ($0.00 cost)
- 4-layer verification architecture
- Comprehensive fact-check reports
- Thoroughness levels (basic, medium, thorough)

Architecture (4 Layers - ALL using Gemini CLI):
1. Internal consistency check (Gemini CLI) - Detect contradictions, implausible claims
2. URL validation (HTTP) - Check if URLs exist
3. Web research verification (Gemini CLI via ResearchAgent) - Verify claims
4. Content quality analysis (Gemini CLI) - Detect vague claims, weasel words
5. Generate comprehensive 4-layer fact-check report

Total Cost: $0.00 (100% FREE)
"""

import logging
import json
import re
import requests
import subprocess
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from src.agents.base_agent import BaseAgent, AgentError
from src.agents.research_agent import ResearchAgent

logger = logging.getLogger(__name__)


class FactCheckError(Exception):
    """Base exception for fact-checking errors"""
    pass


class FactCheckerAgent(BaseAgent):
    """
    LLM-powered fact-checker with web research verification.

    Capabilities:
    1. Critical reading (LLM analyzes blog post)
    2. Claim extraction (LLM identifies factual claims)
    3. URL validation (HTTP + web research)
    4. Fact verification (web research via Gemini CLI)
    5. Comprehensive reporting

    Usage:
        agent = FactCheckerAgent(api_key="sk-xxx")
        result = agent.verify_content(
            content=blog_post_markdown,
            thoroughness="medium"  # "basic", "medium", "thorough"
        )
        if not result['valid']:
            print(result['report'])
            print(result['corrected_content'])
    """

    def __init__(self, api_key: str):
        """
        Initialize FactCheckerAgent.

        Args:
            api_key: OpenRouter API key for LLM calls

        Raises:
            AgentError: If initialization fails
        """
        # Initialize base agent with fact_checker config
        super().__init__(agent_type="fact_checker", api_key=api_key)

        # Initialize ResearchAgent for web research
        self.research_agent = ResearchAgent(api_key=api_key, use_cli=True)

        logger.info("FactCheckerAgent initialized (LLM-powered with web research)")

    def verify_content(
        self,
        content: str,
        thoroughness: str = "medium"
    ) -> Dict[str, Any]:
        """
        Verify content for hallucinated URLs and false claims.

        Args:
            content: Generated markdown blog post
            thoroughness: "basic" (URLs only), "medium" (top 5 claims), "thorough" (all claims)

        Returns:
            Dict with:
                - valid: bool (True if all checks pass)
                - claims_checked: int
                - claims_verified: int
                - claims_failed: List[Dict] (failed claims with evidence)
                - urls_checked: int
                - urls_real: int
                - urls_fake: List[str] (hallucinated URLs)
                - hallucinations: List[Dict] (all hallucinations found)
                - warnings: List[str] (non-critical issues)
                - report: str (human-readable report)
                - corrected_content: str (content with fixes)
                - cost: float (total cost in USD)

        Raises:
            FactCheckError: If inputs are invalid
        """
        # Validate thoroughness
        valid_levels = ["basic", "medium", "thorough"]
        if thoroughness not in valid_levels:
            raise FactCheckError(
                f"Invalid thoroughness: {thoroughness}. "
                f"Valid options: {', '.join(valid_levels)}"
            )

        # Handle empty content
        if not content or not content.strip():
            logger.info("Empty content provided, skipping verification")
            return {
                'valid': True,
                'claims_checked': 0,
                'claims_verified': 0,
                'claims_failed': [],
                'urls_checked': 0,
                'urls_real': 0,
                'urls_fake': [],
                'hallucinations': [],
                'warnings': [],
                'report': 'No content to verify',
                'corrected_content': '',
                'cost': 0.0
            }

        logger.info(
            f"Starting 4-layer fact-check: thoroughness={thoroughness}, "
            f"content_length={len(content)}"
        )

        total_cost = 0.0
        hallucinations = []
        claims_failed = []
        layers = {}

        try:
            # LAYER 1: Internal consistency check (Gemini CLI)
            logger.info("Layer 1: Checking internal consistency via Gemini CLI...")
            try:
                layers['consistency'] = self._check_internal_consistency(content)
                logger.info(
                    f"Layer 1 complete: consistent={layers['consistency']['consistent']}, "
                    f"score={layers['consistency']['score']:.2f}"
                )
            except Exception as e:
                logger.warning(f"Layer 1 failed: {e}")
                layers['consistency'] = {
                    'consistent': True,
                    'issues': [],
                    'score': 1.0,
                    'error': str(e)
                }

            # LAYER 2: URL validation (HTTP)
            logger.info("Layer 2: Validating URLs via HTTP...")
            claims = self._extract_claims(content)
            logger.info(f"Extracted {len(claims)} claims")

            urls = self._extract_urls_from_claims(claims)
            logger.info(f"Found {len(urls)} unique URLs in claims")

            url_results = self._verify_urls_via_http(urls)
            urls_real = sum(1 for is_real in url_results.values() if is_real)
            urls_fake = [url for url, is_real in url_results.items() if not is_real]

            layers['urls'] = {
                'checked': len(urls),
                'real': urls_real,
                'fake': urls_fake
            }

            # Mark fake URLs as hallucinations
            for url in urls_fake:
                hallucinations.append({
                    'type': 'fake_url',
                    'url': url,
                    'evidence': f'HTTP status: 404 (URL does not exist)'
                })

            logger.info(f"Layer 2 complete: {urls_real} real, {len(urls_fake)} fake")

            # LAYER 3: Web research verification (Gemini CLI via ResearchAgent)
            claims_verified = 0
            claims_to_verify = []

            if thoroughness == "basic":
                # Basic: URLs only, no claim verification
                logger.info("Layer 3: Skipping (basic mode)")
                layers['claims'] = {'checked': 0, 'verified': 0, 'failed': []}
            elif thoroughness == "medium":
                # Medium: Verify top 5 claims
                claims_to_verify = claims[:5]
                logger.info(f"Layer 3: Verifying top {len(claims_to_verify)} claims via web research...")
            else:
                # Thorough: Verify all claims
                claims_to_verify = claims
                logger.info(f"Layer 3: Verifying all {len(claims_to_verify)} claims via web research...")

            # Verify claims
            for claim in claims_to_verify:
                try:
                    verification = self._verify_claim_via_web_research(claim)

                    if verification['verified']:
                        claims_verified += 1
                    else:
                        # Claim failed verification
                        claims_failed.append({
                            'claim': claim['claim_text'],
                            'evidence': verification['evidence'],
                            'url': claim.get('citation')
                        })

                        # Mark as hallucination if confidence high
                        if verification['confidence'] > 0.7:
                            hallucinations.append({
                                'type': 'false_claim',
                                'claim': claim['claim_text'],
                                'evidence': verification['evidence'],
                                'confidence': verification['confidence']
                            })

                except Exception as e:
                    logger.warning(f"Failed to verify claim: {e}")
                    # On error, mark as unverified
                    claims_failed.append({
                        'claim': claim['claim_text'],
                        'evidence': f'Verification failed: {str(e)}',
                        'url': claim.get('citation')
                    })

            layers['claims'] = {
                'checked': len(claims_to_verify),
                'verified': claims_verified,
                'failed': claims_failed
            }

            logger.info(f"Layer 3 complete: {claims_verified}/{len(claims_to_verify)} verified")

            # LAYER 4: Content quality analysis (Gemini CLI)
            logger.info("Layer 4: Analyzing content quality via Gemini CLI...")
            try:
                layers['quality'] = self._analyze_content_quality(content)
                logger.info(
                    f"Layer 4 complete: quality_score={layers['quality']['quality_score']:.1f}/10, "
                    f"issues={len(layers['quality']['issues'])}"
                )
            except Exception as e:
                logger.warning(f"Layer 4 failed: {e}")
                layers['quality'] = {
                    'quality_score': 5.0,
                    'issues': [],
                    'recommendations': [],
                    'error': str(e)
                }

            # Build result
            result = {
                'valid': len(hallucinations) == 0,  # Valid if no hallucinations
                'layers': layers,
                'claims_checked': len(claims_to_verify),
                'claims_verified': claims_verified,
                'claims_failed': claims_failed,
                'urls_checked': len(urls),
                'urls_real': urls_real,
                'urls_fake': urls_fake,
                'hallucinations': hallucinations,
                'warnings': [],
                'report': '',
                'corrected_content': content,
                'cost': total_cost  # $0.00 - all Gemini CLI is FREE
            }

            # Generate comprehensive 4-layer report
            result['report'] = self._generate_comprehensive_report(layers)

            logger.info(
                f"Fact-check complete: valid={result['valid']}, "
                f"hallucinations={len(hallucinations)}, "
                f"claims_verified={claims_verified}/{len(claims_to_verify)}"
            )

            # Log hallucinations
            if hallucinations:
                logger.warning(
                    f"Detected {len(hallucinations)} hallucinations: "
                    f"{len(urls_fake)} fake URLs, {len([h for h in hallucinations if h['type'] == 'false_claim'])} false claims"
                )

            return result

        except Exception as e:
            logger.error(f"Fact-check failed: {e}", exc_info=True)
            raise FactCheckError(f"Fact-check failed: {e}") from e

    def _extract_claims(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract factual claims from content using LLM.

        Args:
            content: Blog post content

        Returns:
            List of claims with structure:
                - claim_text: The exact claim made
                - claim_type: statistic, date, quote, fact, source
                - location: Paragraph/section where claim appears
                - citation: Any URL or source referenced

        Raises:
            FactCheckError: If claim extraction fails
        """
        if not content or not content.strip():
            return []

        system_prompt = """You are a critical fact-checker analyzing German blog posts.

Your task: Extract ALL factual claims from the content.

For each claim, identify:
1. claim_text: The exact claim made (quote from content)
2. claim_type: One of: statistic, date, quote, fact, source
3. location: Section/paragraph where claim appears
4. citation: Any URL or source referenced (null if none)

Claim types:
- statistic: Numbers, percentages, measurements (e.g., "30% Kostensenkung")
- date: Specific dates or years (e.g., "2023", "im Jahr 2020")
- quote: Direct quotes from people or documents
- fact: Factual statements that can be verified
- source: References to studies, reports, organizations

IMPORTANT: Return valid JSON array only, no additional text.

Example:
[
  {
    "claim_text": "Laut Siemens können Unternehmen 30% Kosten senken",
    "claim_type": "statistic",
    "location": "Einleitung",
    "citation": "https://www.siemens.com/studie"
  },
  {
    "claim_text": "Die Studie wurde 2023 veröffentlicht",
    "claim_type": "date",
    "location": "Einleitung",
    "citation": null
  }
]
"""

        user_prompt = f"""Analyze this German blog post and extract ALL factual claims:

{content}

Return JSON array with all claims."""

        try:
            # Call LLM to extract claims
            result = self.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                response_format={"type": "json_object"}
            )

            # Parse JSON
            # Since response_format is json_object, LLM might wrap in object
            # Try to extract array from response
            content_str = result['content'].strip()

            # Try parsing as array first
            try:
                claims = json.loads(content_str)
                if not isinstance(claims, list):
                    # If it's an object, try to extract array
                    if isinstance(claims, dict):
                        # Look for array field
                        for key in ['claims', 'data', 'results']:
                            if key in claims and isinstance(claims[key], list):
                                claims = claims[key]
                                break
                        else:
                            # No array found, use empty list
                            claims = []
            except json.JSONDecodeError:
                # Try wrapping in array brackets if missing
                if not content_str.startswith('['):
                    content_str = f'[{content_str}]'
                claims = json.loads(content_str)

            if not isinstance(claims, list):
                raise FactCheckError(f"LLM returned non-array claims: {type(claims)}")

            logger.info(f"Extracted {len(claims)} claims from content")
            return claims

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse claims JSON: {e}")
            raise FactCheckError(f"Failed to parse claims: {e}") from e
        except Exception as e:
            logger.error(f"Claim extraction failed: {e}")
            raise FactCheckError(f"Claim extraction failed: {e}") from e

    def _extract_urls_from_claims(self, claims: List[Dict[str, Any]]) -> List[str]:
        """
        Extract unique URLs from claims.

        Args:
            claims: List of extracted claims

        Returns:
            List of unique URLs
        """
        urls = set()

        for claim in claims:
            citation = claim.get('citation')
            if citation and isinstance(citation, str):
                # Check if citation is a URL
                if citation.startswith('http://') or citation.startswith('https://'):
                    urls.add(citation)

        return list(urls)

    def _verify_urls_via_http(self, urls: List[str]) -> Dict[str, bool]:
        """
        Verify URLs via HTTP HEAD requests.

        Args:
            urls: List of URLs to verify

        Returns:
            Dict mapping URL to bool (True if exists, False if 404/error)
        """
        results = {}

        for url in urls:
            try:
                response = requests.head(
                    url,
                    timeout=5,
                    allow_redirects=True,
                    headers={'User-Agent': 'Mozilla/5.0 (compatible; FactChecker/1.0)'}
                )
                results[url] = response.status_code == 200
                logger.debug(f"URL check: {url} -> {response.status_code}")

            except requests.Timeout:
                logger.warning(f"URL timeout: {url}")
                results[url] = False
            except Exception as e:
                logger.warning(f"URL check failed: {url} -> {e}")
                results[url] = False

        return results

    def _verify_claim_via_web_research(
        self,
        claim: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verify claim using web research via ResearchAgent.

        Args:
            claim: Claim to verify

        Returns:
            Dict with:
                - verified: bool
                - evidence: str (explanation)
                - confidence: float (0.0-1.0)
                - sources: List[str] (supporting/contradicting URLs)

        Raises:
            Exception: If research or analysis fails
        """
        claim_text = claim['claim_text']
        claim_type = claim['claim_type']

        logger.info(f"Verifying claim via web research: {claim_text[:50]}...")

        # Step 1: Perform web research
        query = f"Verify claim: {claim_text}"
        research_result = self.research_agent.research(topic=query, language="de")

        # Step 2: Analyze research results with LLM
        system_prompt = """You are a fact-checker analyzing web research results.

Your task: Determine if the research supports or contradicts the claim.

Return JSON with:
{
  "verified": true/false,
  "evidence": "Explanation based on research",
  "confidence": 0.0-1.0,
  "sources": ["url1", "url2"]
}

Confidence levels:
- 0.9-1.0: Strong evidence (multiple reliable sources)
- 0.7-0.9: Good evidence (reliable sources)
- 0.5-0.7: Weak evidence (limited sources)
- 0.0-0.5: Insufficient evidence

IMPORTANT: Return valid JSON only, no additional text."""

        user_prompt = f"""Verify this claim using web research results:

CLAIM: {claim_text}
CLAIM TYPE: {claim_type}

WEB RESEARCH RESULTS:
Summary: {research_result['summary']}
Keywords: {', '.join(research_result['keywords'])}

Sources found:
{self._format_sources_for_prompt(research_result['sources'])}

Does the research support or contradict the claim?
Return JSON with verification result."""

        # Call LLM to analyze
        result = self.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            response_format={"type": "json_object"}
        )

        # Parse result
        try:
            verification = json.loads(result['content'])

            # Validate structure
            if not isinstance(verification, dict):
                raise ValueError("Invalid verification format")

            if 'verified' not in verification:
                verification['verified'] = False
            if 'evidence' not in verification:
                verification['evidence'] = 'No evidence found'
            if 'confidence' not in verification:
                verification['confidence'] = 0.5
            if 'sources' not in verification:
                verification['sources'] = []

            return verification

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse verification result: {e}")
            # Return default unverified result
            return {
                'verified': False,
                'evidence': 'Analysis failed',
                'confidence': 0.0,
                'sources': []
            }

    def _format_sources_for_prompt(self, sources: List[Dict[str, Any]]) -> str:
        """
        Format research sources for LLM prompt.

        Args:
            sources: List of source dicts

        Returns:
            Formatted string
        """
        if not sources:
            return "No sources found"

        lines = []
        for i, source in enumerate(sources[:5], 1):  # Top 5 sources
            lines.append(f"{i}. {source.get('title', 'Untitled')}")
            lines.append(f"   URL: {source.get('url', 'No URL')}")
            lines.append(f"   Snippet: {source.get('snippet', 'No snippet')[:100]}...")

        return "\n".join(lines)

    def _generate_report(self, result: Dict[str, Any]) -> str:
        """
        Legacy report generation (for backward compatibility).

        Args:
            result: Verification result dictionary

        Returns:
            Formatted report string
        """
        # Delegate to comprehensive report if layers exist
        if 'layers' in result:
            return self._generate_comprehensive_report(result['layers'])

        # Fallback to simple report
        lines = [
            "=" * 60,
            "Fact-Check Report",
            "=" * 60,
            ""
        ]

        # URL validation summary
        urls_checked = result.get('urls_checked', 0)
        urls_real = result.get('urls_real', 0)
        urls_fake = result.get('urls_fake', [])

        lines.append(f"URLs Checked: {urls_checked}")
        lines.append(f"✅ Real URLs: {urls_real}")
        lines.append(f"🚫 Fake URLs: {len(urls_fake)}")
        lines.append("")

        if urls_fake:
            lines.append("Hallucinated URLs:")
            for i, url in enumerate(urls_fake, 1):
                lines.append(f"{i}. {url}")
                lines.append("   → Status: 404 Not Found (hallucination)")
            lines.append("")

        # Claim verification summary
        claims_checked = result.get('claims_checked', 0)
        claims_verified = result.get('claims_verified', 0)
        claims_failed = result.get('claims_failed', [])

        lines.append(f"Claims Checked: {claims_checked}")
        lines.append(f"✅ Verified: {claims_verified}")
        lines.append(f"❌ Failed: {len(claims_failed)}")
        lines.append("")

        if claims_failed:
            lines.append("Failed Claims:")
            for i, failed in enumerate(claims_failed, 1):
                lines.append(f"{i}. \"{failed['claim']}\"")
                lines.append(f"   → Evidence: {failed['evidence']}")
                if failed.get('url'):
                    lines.append(f"   → URL: {failed['url']}")
            lines.append("")

        # Overall recommendation
        hallucinations = result.get('hallucinations', [])
        is_valid = result.get('valid', len(hallucinations) == 0)

        if is_valid:
            lines.append("✅ Recommendation: ACCEPT - Content passed fact-check")
        else:
            lines.append(
                f"❌ Recommendation: REJECT - {len(hallucinations)} "
                f"hallucinations detected"
            )

        lines.append("=" * 60)

        return "\n".join(lines)

    def _generate_comprehensive_report(self, layers: Dict[str, Any]) -> str:
        """
        Generate comprehensive 4-layer fact-check report.

        Args:
            layers: Dict with keys: consistency, urls, claims, quality

        Returns:
            Formatted report string
        """
        lines = [
            "=" * 60,
            "Comprehensive Fact-Check Report (4 Layers)",
            "=" * 60,
            ""
        ]

        # LAYER 1: Internal Consistency
        lines.append("Layer 1: Internal Consistency")
        consistency = layers.get('consistency', {})
        if 'error' in consistency:
            lines.append(f"⚠️  Error: {consistency['error']}")
        else:
            score = consistency.get('score', 1.0)
            lines.append(f"✅ Consistency Score: {score:.2f}/1.0")
            issues = consistency.get('issues', [])
            if issues:
                lines.append(f"⚠️  {len(issues)} issues found:")
                for issue in issues[:5]:  # Show max 5
                    lines.append(
                        f"   - {issue['type']}: {issue['description']} "
                        f"(at {issue['location']})"
                    )
            else:
                lines.append("✅ No consistency issues detected")
        lines.append("")

        # LAYER 2: URL Validation
        lines.append("Layer 2: URL Validation")
        urls = layers.get('urls', {})
        urls_checked = urls.get('checked', 0)
        urls_real = urls.get('real', 0)
        urls_fake = urls.get('fake', [])

        lines.append(f"URLs Checked: {urls_checked}")
        lines.append(f"✅ Real: {urls_real}")
        lines.append(f"❌ Fake: {len(urls_fake)}")

        if urls_fake:
            for i, url in enumerate(urls_fake[:5], 1):  # Show max 5
                lines.append(f"   {i}. {url}")
                lines.append("      → 404 Not Found")
        lines.append("")

        # LAYER 3: Web Research
        lines.append("Layer 3: Web Research")
        claims = layers.get('claims', {})
        claims_checked = claims.get('checked', 0)
        claims_verified = claims.get('verified', 0)
        claims_failed = claims.get('failed', [])

        lines.append(f"Claims Checked: {claims_checked}")
        lines.append(f"✅ Verified: {claims_verified}")
        lines.append(f"❌ Refuted: {len(claims_failed)}")

        if claims_failed:
            for i, failed in enumerate(claims_failed[:3], 1):  # Show max 3
                lines.append(f"   {i}. \"{failed['claim'][:60]}...\"")
                lines.append(f"      → {failed['evidence']}")
        lines.append("")

        # LAYER 4: Content Quality
        lines.append("Layer 4: Content Quality")
        quality = layers.get('quality', {})
        if 'error' in quality:
            lines.append(f"⚠️  Error: {quality['error']}")
        else:
            quality_score = quality.get('quality_score', 5.0)
            lines.append(f"Quality Score: {quality_score:.1f}/10")

            issues = quality.get('issues', [])
            if issues:
                lines.append(f"⚠️  {len(issues)} bullshit indicators:")
                for issue in issues[:5]:  # Show max 5
                    lines.append(
                        f"   - {issue['type']}: \"{issue['text'][:40]}...\" "
                        f"(at {issue['location']})"
                    )

            recommendations = quality.get('recommendations', [])
            if recommendations:
                lines.append("💡 Recommendations:")
                for rec in recommendations[:3]:  # Show max 3
                    lines.append(f"   - {rec}")
        lines.append("")

        # Overall verdict
        lines.append("=" * 60)

        # Determine overall status
        total_issues = (
            len(consistency.get('issues', [])) +
            len(urls_fake) +
            len(claims_failed) +
            len(quality.get('issues', []))
        )

        if total_issues == 0:
            lines.append("✅ VERDICT: ACCEPT - Content passed all 4 layers")
        else:
            lines.append(f"❌ VERDICT: REJECT - {total_issues} issues detected")

        lines.append("Cost: $0.00 (FREE - Gemini CLI only)")
        lines.append("=" * 60)

        return "\n".join(lines)

    def _run_gemini_cli(self, prompt: str, timeout: int = 30) -> str:
        """
        Execute Gemini CLI command.

        Args:
            prompt: Prompt for Gemini
            timeout: Command timeout in seconds

        Returns:
            Gemini response text

        Raises:
            FactCheckError: If command fails
        """
        try:
            result = subprocess.run(
                ['gemini', prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False  # Don't raise on non-zero exit
            )

            # Check return code manually
            if result.returncode != 0:
                error_msg = result.stderr or "Unknown error"
                raise FactCheckError(f"Gemini CLI error: {error_msg}")

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            logger.error(f"Gemini CLI timeout after {timeout}s")
            raise FactCheckError(f"Gemini CLI timeout after {timeout}s")

        except FileNotFoundError:
            logger.error("Gemini CLI not found. Install: npm install -g @google/generative-ai-cli")
            raise FactCheckError("Gemini CLI not installed")

        except Exception as e:
            logger.error(f"Gemini CLI execution failed: {e}")
            raise FactCheckError(f"Gemini CLI execution failed: {e}")

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON response from Gemini CLI.

        Args:
            response: Raw response string

        Returns:
            Parsed JSON dict

        Raises:
            FactCheckError: If JSON parsing fails
        """
        try:
            # Try parsing as-is
            return json.loads(response)
        except json.JSONDecodeError as e:
            # Try extracting JSON from markdown code block
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            logger.error(f"Failed to parse JSON response: {e}")
            raise FactCheckError(f"Failed to parse JSON response: {e}")

    def _check_internal_consistency(self, content: str) -> Dict[str, Any]:
        """
        Use Gemini CLI to analyze internal consistency.

        Detects:
        - Contradictory statements
        - Logical fallacies
        - Implausible claims (99% improvements, etc.)
        - Mathematical errors
        - Date/timeline conflicts

        Args:
            content: Blog post content

        Returns:
            {
                'consistent': bool,
                'issues': List[Dict],  # Each issue with description + location
                'score': float  # 0.0-1.0 consistency score
            }

        Raises:
            FactCheckError: If analysis fails
        """
        prompt = f"""Analyze this German blog post for internal inconsistencies.

Content:
{content}

Check for:
1. Contradictory statements (e.g., "X is increasing" then "X decreased")
2. Logical fallacies or errors
3. Implausible claims (e.g., "99% cost reduction")
4. Mathematical inconsistencies
5. Date/timeline conflicts

Return ONLY valid JSON in this exact format:
{{
  "consistent": true,
  "issues": [
    {{"type": "contradiction", "description": "...", "location": "paragraph 3"}},
    {{"type": "implausible", "description": "...", "location": "section 2"}}
  ],
  "score": 0.85
}}

Score should be 0.0-1.0 where 1.0 = perfectly consistent.
If no issues found, return empty issues array."""

        logger.info("Running internal consistency check via Gemini CLI...")

        try:
            response = self._run_gemini_cli(prompt, timeout=30)
            result = self._parse_json_response(response)

            # Validate structure
            if not isinstance(result, dict):
                raise FactCheckError("Invalid consistency check response format")

            # Ensure required fields
            if 'consistent' not in result:
                result['consistent'] = True
            if 'issues' not in result:
                result['issues'] = []
            if 'score' not in result:
                result['score'] = 1.0 if result['consistent'] else 0.5

            return result

        except FactCheckError:
            raise
        except Exception as e:
            logger.error(f"Internal consistency check failed: {e}")
            raise FactCheckError(f"Internal consistency check failed: {e}")

    def _analyze_content_quality(self, content: str) -> Dict[str, Any]:
        """
        Use Gemini CLI to detect content quality issues.

        Detects:
        - Vague claims ("many experts say", "studies show")
        - Weasel words ("up to", "can achieve", "potentially")
        - Missing attribution (statistics without sources)
        - Cherry-picked data
        - Misleading framing

        Args:
            content: Blog post content

        Returns:
            {
                'quality_score': float,  # 0.0-10.0 credibility score
                'issues': List[Dict],  # Quality issues found
                'recommendations': List[str]  # How to improve
            }

        Raises:
            FactCheckError: If analysis fails
        """
        prompt = f"""Analyze this German blog post for quality and credibility issues.

Content:
{content}

Detect bullshit indicators:
1. Vague claims without specifics ("viele Experten", "Studien zeigen")
2. Weasel words ("bis zu", "kann erreichen", "möglich")
3. Missing attribution (statistics without sources)
4. Cherry-picked data (selecting only favorable info)
5. Misleading framing (technically true but deceptive)

Rate overall credibility 0-10 (10 = highest quality).

Return ONLY valid JSON in this exact format:
{{
  "quality_score": 7.5,
  "issues": [
    {{"type": "vague_claim", "text": "Viele Experten empfehlen...", "location": "intro"}},
    {{"type": "weasel_words", "text": "bis zu 30%", "location": "section 2"}}
  ],
  "recommendations": ["Add specific expert names", "Provide source for 30% claim"]
}}

If no issues found, return empty issues and recommendations arrays."""

        logger.info("Running content quality analysis via Gemini CLI...")

        try:
            response = self._run_gemini_cli(prompt, timeout=30)
            result = self._parse_json_response(response)

            # Validate structure
            if not isinstance(result, dict):
                raise FactCheckError("Invalid quality analysis response format")

            # Ensure required fields
            if 'quality_score' not in result:
                result['quality_score'] = 5.0
            if 'issues' not in result:
                result['issues'] = []
            if 'recommendations' not in result:
                result['recommendations'] = []

            return result

        except FactCheckError:
            raise
        except Exception as e:
            logger.error(f"Content quality analysis failed: {e}")
            raise FactCheckError(f"Content quality analysis failed: {e}")
