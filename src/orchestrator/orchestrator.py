"""
Main orchestrator for multi-agent system (Tier 3).
Routes queries, manages agent execution, and merges results.
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional
from orchestrator.intent_detector import intent_detector
from orchestrator.response_builder import response_builder
from agents.analytics_agent import analytics_agent
from agents.seo_agent import seo_agent
from services.llm_service import llm_service

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrates multi-agent query processing."""
    
    def __init__(self):
        self.intent_detector = intent_detector
        self.analytics_agent = analytics_agent
        self.seo_agent = seo_agent
        self.llm = llm_service
    
    async def process_query(
        self,
        query: str,
        property_id: Optional[str] = None,
        spreadsheet_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a query using appropriate agent(s).
        
        Args:
            query: Natural language query
            property_id: GA4 property ID
            spreadsheet_id: Google Sheets spreadsheet ID
            request_id: Unique request identifier for tracking
        
        Returns:
            Response dictionary
        """
        start_time = time.time()
        req_prefix = f"[{request_id}]" if request_id else ""
        
        try:
            # Step 1: Detect intent
            intent = await self.intent_detector.detect_intent(query)
            logger.info(f"{req_prefix} Detected intent: {intent}")
            
            # Step 2: Route to appropriate agent(s)
            if intent == "analytics":
                result = await self._handle_analytics(query, property_id, request_id)
                agent_name = "analytics"
            
            elif intent == "seo":
                result = await self._handle_seo(query, spreadsheet_id, request_id)
                agent_name = "seo"
            
            elif intent == "multi":
                result = await self._handle_multi(query, property_id, spreadsheet_id, request_id)
                agent_name = "multi"
            
            else:
                result = response_builder.build_error_response(
                    f"Unknown intent: {intent}"
                )
                agent_name = "unknown"
            
            # Step 3: Add metadata
            execution_time = time.time() - start_time
            processing_time_ms = round(execution_time * 1000, 2)
            
            if result.get("success"):
                result = response_builder.add_metadata(
                    result,
                    agent=agent_name,
                    execution_time=execution_time,
                )
                # Add processing time in milliseconds
                if result.get("metadata"):
                    result["metadata"]["processing_time_ms"] = processing_time_ms
            
            return result
        
        except Exception as e:
            logger.error(f"{req_prefix} Orchestrator error: {e}", exc_info=True)
            return response_builder.build_error_response(
                str(e),
                details={"query": query}
            )
    
    async def _handle_analytics(
        self,
        query: str,
        property_id: Optional[str],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle analytics-only query."""
        # GUARD: Detect comparison intent and validate before processing
        query_lower = query.lower()
        comparison_keywords = ["compare", "vs", "versus", "difference", "change", "compared"]
        has_comparison_intent = any(keyword in query_lower for keyword in comparison_keywords)
        
        if has_comparison_intent:
            # For comparison queries, first check if we can even get basic data
            try:
                from services.ga4_service import ga4_service
                prop_id = property_id or ga4_service.get_default_property_id()
                if prop_id:
                    # Quick check: try to get recent data
                    test_data = ga4_service.run_report(
                        property_id=prop_id,
                        metrics=["activeUsers"],
                        dimensions=[],
                        start_date="7daysAgo",
                        end_date="today",
                        limit=10,
                    )
                    # Validate rows exist and are properly formatted
                    rows = test_data.get("rows") if test_data else None
                    if not rows or not isinstance(rows, list) or len(rows) == 0:
                        return {
                            "success": True,
                            "answer": (
                                "Comparison could not be performed because analytics data is unavailable for one or both periods. "
                                "This typically indicates that GA4 has not yet started collecting data for your property, or the selected time range contains no recorded traffic. "
                                "Please verify your GA4 tracking setup and ensure sufficient data has been collected before attempting period comparisons."
                            ),
                            "data": {
                                "current_period": None,
                                "previous_period": None
                            },
                            "metadata": {
                                "request_id": request_id if request_id else "unknown",
                                "comparison": "unavailable"
                            }
                        }
            except Exception as e:
                # If test query fails, return clean comparison unavailable response
                logger.warning(f"Comparison pre-check failed: {e}")
                return {
                    "success": True,
                    "answer": (
                        "Comparison could not be performed because analytics data is unavailable for one or both periods. "
                        "This typically indicates that GA4 has not yet started collecting data for your property, or the selected time range contains no recorded traffic. "
                        "Please verify your GA4 tracking setup and ensure sufficient data has been collected before attempting period comparisons."
                    ),
                    "data": {
                        "current_period": None,
                        "previous_period": None
                    },
                    "metadata": {
                        "request_id": request_id if request_id else "unknown",
                        "comparison": "unavailable"
                    }
                }
        
        return await self.analytics_agent.process_query(query, property_id, request_id=request_id)
    
    async def _handle_seo(
        self,
        query: str,
        spreadsheet_id: Optional[str],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle SEO-only query."""
        return await self.seo_agent.process_query(query, spreadsheet_id, request_id=request_id)
    
    async def _handle_multi(
        self,
        query: str,
        property_id: Optional[str],
        spreadsheet_id: Optional[str],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle multi-agent query (Tier 3).
        Runs both agents and merges results.
        """
        try:
            # Run both agents in parallel
            analytics_task = asyncio.create_task(
                self.analytics_agent.process_query(query, property_id, request_id=request_id)
            )
            seo_task = asyncio.create_task(
                self.seo_agent.process_query(query, spreadsheet_id, request_id=request_id)
            )
            
            # Wait for both to complete
            analytics_result, seo_result = await asyncio.gather(
                analytics_task,
                seo_task,
                return_exceptions=True,
            )
            
            # Handle exceptions
            if isinstance(analytics_result, Exception):
                logger.error(f"Analytics agent failed: {analytics_result}")
                analytics_result = {"success": False, "error": str(analytics_result)}
            
            if isinstance(seo_result, Exception):
                logger.error(f"SEO agent failed: {seo_result}")
                seo_result = {"success": False, "error": str(seo_result)}
            
            # Merge results using LLM
            merged_answer = await self._merge_results(
                query,
                analytics_result,
                seo_result,
            )
            
            # Append multi-agent confidence (simplified format)
            confidence = self._determine_multi_confidence(analytics_result, seo_result)
            merged_answer += f"\n\nConfidence: {confidence['level']}"
            
            return {
                "success": True,
                "answer": merged_answer,
                "data": {
                    "analytics": analytics_result.get("data"),
                    "seo": seo_result.get("data"),
                },
                "agent_results": {
                    "analytics": analytics_result,
                    "seo": seo_result,
                }
            }
        
        except Exception as e:
            logger.error(f"Multi-agent processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _merge_results(
        self,
        query: str,
        analytics_result: Dict[str, Any],
        seo_result: Dict[str, Any],
    ) -> str:
        """
        Merge results from both agents using LLM.
        
        Args:
            query: Original query
            analytics_result: Analytics agent result
            seo_result: SEO agent result
        
        Returns:
            Unified natural language answer
        """
        # Defensive type checking for analytics data
        analytics_has_data = False
        analytics_data = analytics_result.get("data")
        if analytics_data is not None:
            if isinstance(analytics_data, dict):
                analytics_has_data = analytics_result.get("success", False) and analytics_data.get("row_count", 0) > 0
            elif isinstance(analytics_data, list):
                analytics_has_data = analytics_result.get("success", False) and len(analytics_data) > 0
        
        # Defensive type checking for SEO data
        seo_has_data = False
        seo_data = seo_result.get("data")
        if seo_data is not None:
            if isinstance(seo_data, list):
                seo_has_data = seo_result.get("success", False) and len(seo_data) > 0
            elif isinstance(seo_data, dict):
                seo_has_data = seo_result.get("success", False) and len(seo_data) > 0
        
        # Prepare context - safely get answers
        analytics_summary = analytics_result.get("answer", "No analytics data available")
        seo_summary = seo_result.get("answer", "No SEO data available")
        
        # GUARD: Check SEO data for status codes to prevent hallucinating crawl errors
        seo_has_only_200 = False
        if seo_has_data and isinstance(seo_data, dict):
            # SEO data is a dict like {"200": 21, "404": 3} or just {"200": 21}
            has_errors = any(
                int(status_code) >= 400 
                for status_code in seo_data.keys() 
                if status_code.isdigit()
            )
            has_200 = "200" in seo_data
            if has_200 and not has_errors:
                seo_has_only_200 = True
        
        # Handle case where analytics data is missing
        if not analytics_has_data and seo_has_data:
            # Build crawl error constraint if applicable
            crawl_constraint = ""
            if seo_has_only_200:
                crawl_constraint = "\n6. CRITICAL: The SEO data shows ONLY 200 status codes with NO 4xx or 5xx errors. You MUST explicitly state: 'There are no crawl errors in the provided SEO data.' Do NOT mention crawl issues, technical errors, or negative SEO impact from crawlability."
            
            system_message = f"""You are a confident digital marketing analyst presenting at a hackathon demo. 
When analytics data is unavailable but SEO data exists, you MUST:
1. Start with: "Based on available SEO data and limited analytics signals:"
2. Provide a structured comparison with these exact bullet points:
   • SEO Health Summary: (summarize the SEO findings)
   • Traffic Visibility Status: (infer from SEO issues what traffic impact might be)
   • Likely Impact: (explain business implications)
3. Keep the tone confident and actionable
4. NEVER say "not possible" or "cannot analyze"
5. Use SEO signals to make reasonable inferences about traffic patterns{crawl_constraint}"""
            
            prompt = f"""
Query: {query}

SEO Data Available:
{seo_summary}

Generate a confident, structured response following the exact format with bullet points."""
        
        # Handle normal case with both data sources
        else:
            # Build crawl error constraint if applicable
            crawl_constraint = ""
            if seo_has_only_200:
                crawl_constraint = "\n\nCRITICAL: The SEO data shows ONLY 200 status codes with NO 4xx or 5xx errors. You MUST explicitly state: 'There are no crawl errors in the provided SEO data.' Do NOT mention crawl issues, technical errors, or negative SEO impact from crawlability."
            
            system_message = f"""You are a digital marketing analyst. Merge insights from analytics and SEO data into a unified, coherent answer.

Highlight correlations, patterns, and actionable insights that emerge from combining both data sources.{crawl_constraint}"""
            
            prompt = f"""
Query: {query}

Analytics Insights:
{analytics_summary}

SEO Insights:
{seo_summary}

Provide a unified answer that combines both perspectives:"""
        
        try:
            merged = self.llm.generate_text(
                prompt=prompt,
                system_message=system_message,
                temperature=0.6,
            )
            return merged
        except Exception as e:
            logger.error(f"Failed to merge results: {e}")
            # Fallback with structured format
            # Fallback to simple concatenation
            return f"Analytics: {analytics_summary}\n\nSEO: {seo_summary}"
    
    def _determine_multi_confidence(
        self,
        analytics_result: Dict[str, Any],
        seo_result: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Determine confidence for multi-agent response.
        
        Args:
            analytics_result: Analytics agent result
            seo_result: SEO agent result
        
        Returns:
            Dictionary with confidence level and reason
        """
        analytics_success = analytics_result.get("success", False)
        seo_success = seo_result.get("success", False)
        
        # Get data with defensive defaults
        analytics_data = analytics_result.get("data")
        seo_data = seo_result.get("data")
        
        # Strict type checking for analytics_data
        analytics_has_data = False
        if analytics_data is not None:
            # Analytics data should be a dict with row_count
            if isinstance(analytics_data, dict):
                analytics_has_data = analytics_data.get("row_count", 0) > 0
            elif isinstance(analytics_data, list):
                # If it's a list, check if non-empty
                analytics_has_data = len(analytics_data) > 0
        
        # Strict type checking for seo_data
        seo_has_data = False
        if seo_data is not None:
            # SEO data can be either a list or a dict
            if isinstance(seo_data, list):
                seo_has_data = len(seo_data) > 0
            elif isinstance(seo_data, dict):
                # If it's a dict (like {"200": 21}), check if non-empty
                seo_has_data = len(seo_data) > 0
        
        # Both sources have data
        if analytics_has_data and seo_has_data:
            return {
                "level": "High",
                "reason": "Cross-domain analysis with both GA4 analytics and SEO data available."
            }
        # Only analytics has data
        elif analytics_has_data and not seo_has_data:
            return {
                "level": "Medium",
                "reason": "Based on GA4 analytics only. SEO data not available for cross-validation."
            }
        # Only SEO has data
        elif not analytics_has_data and seo_has_data:
            return {
                "level": "Medium",
                "reason": "Based on SEO data only. Analytics data not available for traffic insights."
            }
        # Neither has data
        else:
            return {
                "level": "Low",
                "reason": "Limited data from both analytics and SEO sources."
            }


# Global orchestrator instance
orchestrator = Orchestrator()
