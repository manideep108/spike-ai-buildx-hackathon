"""
Intent detection for routing queries to appropriate agents.
Uses rule-based detection with LLM fallback.
"""

import logging
from typing import Literal, Optional
from services.llm_service import llm_service

logger = logging.getLogger(__name__)

IntentType = Literal["analytics", "seo", "multi"]


class IntentDetector:
    """Detects query intent to route to appropriate agent(s)."""
    
    def __init__(self):
        self.llm = llm_service
        
        # Keyword patterns for rule-based detection
        self.analytics_keywords = {
            "users", "sessions", "traffic", "visits", "visitors",
            "pageviews", "bounce", "conversion", "revenue",
            "ga4", "google analytics", "analytics",
            "how many", "what's the", "show me traffic",
        }
        
        self.seo_keywords = {
            "seo", "pages", "404", "broken", "links",
            "meta", "title", "description", "heading",
            "indexability", "crawl", "sitemap",
            "screaming frog", "technical seo",
        }
    
    async def detect_intent(self, query: str) -> IntentType:
        """
        Detect the intent of a query.
        
        Args:
            query: Natural language query
        
        Returns:
            Intent type: 'analytics', 'seo', or 'multi'
        """
        # Try rule-based detection first
        rule_based_intent = self._rule_based_detection(query)
        
        if rule_based_intent:
            logger.info(f"Rule-based intent detected: {rule_based_intent}")
            return rule_based_intent
        
        # Fallback to LLM-based detection
        logger.info("Using LLM for intent detection")
        return await self._llm_based_detection(query)
    
    def _rule_based_detection(self, query: str) -> Optional[IntentType]:
        """
        Rule-based intent detection using keyword matching.
        
        Args:
            query: Natural language query
        
        Returns:
            Intent type or None if ambiguous
        """
        query_lower = query.lower()
        
        # Check for keyword matches
        analytics_match = any(kw in query_lower for kw in self.analytics_keywords)
        seo_match = any(kw in query_lower for kw in self.seo_keywords)
        
        # Determine intent
        if analytics_match and seo_match:
            return "multi"
        elif analytics_match:
            return "analytics"
        elif seo_match:
            return "seo"
        else:
            # Ambiguous - return None to trigger LLM detection
            return None
    
    async def _llm_based_detection(self, query: str) -> IntentType:
        """
        LLM-based intent detection for ambiguous queries.
        
        Args:
            query: Natural language query
        
        Returns:
            Intent type
        """
        system_message = """You are an intent classifier for a multi-agent analytics system.

Classify queries into one of these intents:
- "analytics": Questions about website traffic, user behavior, sessions, conversions (GA4 data)
- "seo": Questions about page issues, broken links, meta tags, technical SEO (Screaming Frog data)
- "multi": Questions that require both analytics and SEO data

Return a JSON object with:
- intent: one of "analytics", "seo", or "multi"
- confidence: number between 0 and 1

Examples:
- "How many users visited last week?" → analytics
- "Show me pages with 404 errors" → seo
- "Which high-traffic pages have SEO issues?" → multi"""
        
        prompt = f"Query: {query}\n\nClassify the intent:"
        
        try:
            result = self.llm.generate_structured_output(
                prompt=prompt,
                system_message=system_message,
                temperature=0.2,
            )
            
            intent = result.get("intent", "analytics")
            
            # Validate intent
            if intent not in ["analytics", "seo", "multi"]:
                logger.warning(f"Invalid intent from LLM: {intent}, defaulting to analytics")
                return "analytics"
            
            return intent
        
        except Exception as e:
            logger.error(f"LLM intent detection failed: {e}")
            # Default to analytics
            return "analytics"


# Global intent detector instance
intent_detector = IntentDetector()

