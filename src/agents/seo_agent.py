"""
SEO Agent (Tier 2) - Processes queries about SEO data from Google Sheets.
Analyzes Screaming Frog data with filtering, grouping, and aggregation.
"""

import logging
from typing import Dict, Any, Optional, List
from services.llm_service import llm_service
from services.sheets_service import sheets_service

logger = logging.getLogger(__name__)


class SEOAgent:
    """Agent for handling SEO queries using Google Sheets data."""
    
    def __init__(self):
        self.llm = llm_service
        self.sheets = sheets_service
    
    async def process_query(
        self,
        query: str,
        spreadsheet_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process an SEO query.
        
        Args:
            query: Natural language query
            spreadsheet_id: Google Sheets spreadsheet ID
            request_id: Unique request identifier for tracking
        
        Returns:
            Dictionary with answer and data
        """
        req_prefix = f"[{request_id}]" if request_id else ""
        
        try:
            # Step 1: Read SEO data from Google Sheets
            logger.info(f"{req_prefix} Reading SEO data from Sheets")
            seo_data = self.sheets.read_sheet(spreadsheet_id=spreadsheet_id)
            
            # Step 2: Explicit empty data detection (NO_SEO_DATA case)
            if not seo_data or len(seo_data) == 0:
                return {
                    "success": True,
                    "answer": self._generate_no_data_explanation(),
                    "data": [],
                    "data_status": "NO_SEO_DATA"
                }
            
            # Step 3: Detect available columns and validate
            available_columns = list(seo_data[0].keys()) if seo_data else []
            column_analysis = self._analyze_available_columns(available_columns)
            
            # Step 4: Generate scoped insight message if columns are limited
            if column_analysis["limited_scope"]:
                logger.warning(f"Limited SEO data: {column_analysis['scope_message']}")
            
            # Step 5: Understand query intent with column awareness
            operations = await self._understand_query(query, seo_data, column_analysis)
            
            # Step 6: Apply operations (filter, group, aggregate)
            processed_data = self._apply_operations(seo_data, operations)
            
            # Step 7: Generate answer with column scope awareness
            answer = await self._generate_answer(
                query, 
                processed_data, 
                operations, 
                column_analysis
            )
            
            # Step 7.5: Compute SEO risk scores and append summary (ADDITIVE ONLY)
            try:
                # Only score if we have list data (not aggregated dicts)
                if isinstance(processed_data, list) and len(processed_data) > 0:
                    risk_scores = self._compute_seo_risk_scores(processed_data)
                    if risk_scores:
                        risk_summary = self._generate_risk_summary(risk_scores)
                        if risk_summary:
                            answer += risk_summary
            except Exception as e:
                # Never fail the request due to scoring logic
                logger.debug(f"SEO risk scoring skipped: {e}")
            
            # Append confidence level (simplified format)
            confidence = self._determine_seo_confidence(column_analysis, processed_data)
            answer += f"\n\nConfidence: {confidence['level']}"
            
            return {
                "success": True,
                "answer": answer,
                "data": processed_data,
                "operations": operations,
                "column_scope": column_analysis["available_categories"],
            }
        
        except Exception as e:
            logger.error(f"Error in SEO agent: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _understand_query(
        self,
        query: str,
        sample_data: List[Dict[str, Any]],
        column_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Use LLM to understand query intent and determine operations.
        
        Args:
            query: Natural language query
            sample_data: Sample rows from the sheet
            column_analysis: Analysis of available columns
        
        Returns:
            Operations to perform (filter, group, aggregate)
        """
        # Get available columns from data
        columns = list(sample_data[0].keys()) if sample_data else []
        
        # Build system message with column limitations
        column_scope_note = ""
        if column_analysis["limited_scope"]:
            column_scope_note = f"\n\nIMPORTANT: {column_analysis['scope_message']}"
        
        system_message = f"""You are an SEO data analyst. Analyze queries about Screaming Frog SEO data.

Available columns: {', '.join(columns)}

Common SEO columns include:
- Address/URL: Page URL
- Status Code: HTTP status (200, 404, etc.)
- Title: Page title
- Meta Description: Meta description
- H1: H1 heading
- Word Count: Content length
- Indexability: Whether page is indexable{column_scope_note}

Return a JSON object with:
- filters: object with column->value pairs (optional)
- group_by: column name to group by (optional)
- aggregate_column: column to aggregate (optional)
- operation: 'count', 'sum', 'avg', 'min', 'max' (default: 'count')
- limit: number of results (default: 100)

Example input: "Show me pages with 404 errors"
Example output:
{{
  "filters": {{"Status Code": "404"}},
  "limit": 100
}}"""
        
        prompt = f"Query: {query}\n\nDetermine the operations needed:"
        
        try:
            operations = self.llm.generate_structured_output(
                prompt=prompt,
                system_message=system_message,
                temperature=0.3,
            )
            return operations
        except Exception as e:
            logger.error(f"Failed to understand query: {e}")
            # Return default operations
            return {"limit": 100}
    
    def _apply_operations(
        self,
        data: List[Dict[str, Any]],
        operations: Dict[str, Any],
    ) -> Any:
        """
        Apply filtering, grouping, and aggregation operations.
        
        Args:
            data: Raw data from sheets
            operations: Operations to apply
        
        Returns:
            Processed data
        """
        result = data
        
        # Apply filters
        if operations.get("filters"):
            result = self.sheets.filter_data(result, operations["filters"])
        
        # Apply grouping/aggregation
        if operations.get("group_by"):
            result = self.sheets.aggregate_data(
                data=result,
                group_by=operations["group_by"],
                aggregate_column=operations.get("aggregate_column"),
                operation=operations.get("operation", "count"),
            )
        else:
            # Apply limit
            limit = operations.get("limit", 100)
            result = result[:limit]
        
        return result
    
    async def _generate_answer(
        self,
        original_query: str,
        processed_data: Any,
        operations: Dict[str, Any],
        column_analysis: Dict[str, Any],
    ) -> str:
        """
        Generate natural language answer from processed data.
        
        Args:
            original_query: Original user query
            processed_data: Processed data
            operations: Operations applied
            column_analysis: Analysis of available columns
        
        Returns:
            Natural language answer
        """
        # Build scope-aware system message
        base_message = """You are an SEO analyst. Convert SEO data into clear, actionable insights."""
        
        if column_analysis["limited_scope"]:
            scope_restriction = f"""

CRITICAL CONSTRAINTS:
{column_analysis['scope_message']}

You MUST:
- Base insights ONLY on columns that exist in the data
- NEVER mention or infer data about: {', '.join(column_analysis['unavailable_categories'])}
- Focus exclusively on: {', '.join(column_analysis['available_categories'])}
- If asked about unavailable data, clearly state it's not in the dataset"""
        else:
            scope_restriction = "\n\nHighlight important issues and provide specific recommendations when relevant."
        
        system_message = base_message + scope_restriction
        
        # Format data for LLM
        if isinstance(processed_data, dict):
            data_summary = f"Aggregated results:\n{processed_data}"
        elif isinstance(processed_data, list):
            data_count = len(processed_data)
            sample = processed_data[:5]
            data_summary = f"Found {data_count} results. Sample:\n{sample}"
        else:
            data_summary = str(processed_data)
        
        prompt = f"""
Query: {original_query}

Operations applied: {operations}

Data:
{data_summary}

Provide a clear, actionable answer to the query:"""
        
        try:
            answer = self.llm.generate_text(
                prompt=prompt,
                system_message=system_message,
                temperature=0.5,
            )
            return answer
        except Exception as e:
            logger.error(f"Failed to generate answer: {e}")
            # Fallback
            if isinstance(processed_data, list):
                return f"Found {len(processed_data)} results matching your query."
            else:
                return f"Analysis complete: {processed_data}"
    
    def _analyze_available_columns(self, columns: List[str]) -> Dict[str, Any]:
        """
        Analyze available columns to determine SEO data scope.
        
        Args:
            columns: List of column names from spreadsheet
        
        Returns:
            Dictionary with column analysis and scope constraints
        """
        # Normalize column names for comparison (case-insensitive)
        normalized_cols = [col.lower() for col in columns]
        
        # Define column categories
        crawlability_cols = ["status code", "address", "url", "status"]
        content_cols = ["title", "meta description", "h1", "h2", "word count", "content"]
        performance_cols = ["psi", "pagespeed", "load time", "speed", "performance"]
        accessibility_cols = ["wcag", "accessibility", "aria", "alt text", "contrast"]
        
        # Detect available categories
        has_crawlability = any(col in normalized_cols for col in crawlability_cols)
        has_content = any(col in normalized_cols for col in content_cols)
        has_performance = any(col in normalized_cols for col in performance_cols)
        has_accessibility = any(col in normalized_cols for col in accessibility_cols)
        
        # Determine available and unavailable categories
        available_categories = []
        unavailable_categories = []
        
        if has_crawlability:
            available_categories.append("Crawlability/Status Codes")
        else:
            unavailable_categories.append("Crawlability/Status Codes")
        
        if has_content:
            available_categories.append("Content/Meta Tags")
        else:
            unavailable_categories.append("Content/Meta Tags")
        
        if has_performance:
            available_categories.append("Performance/PageSpeed")
        else:
            unavailable_categories.append("Performance/PageSpeed")
        
        if has_accessibility:
            available_categories.append("Accessibility/WCAG")
        else:
            unavailable_categories.append("Accessibility/WCAG")
        
        # Determine if scope is limited
        limited_scope = len(available_categories) < 4
        
        # Generate scope message
        if not available_categories:
            scope_message = "No recognized SEO columns found. Analysis will be limited to basic data structure."
        elif limited_scope:
            scope_message = f"Only {', '.join(available_categories)} data available. Cannot provide insights about {', '.join(unavailable_categories)}."
        else:
            scope_message = "Full SEO dataset available."
        
        return {
            "available_categories": available_categories,
            "unavailable_categories": unavailable_categories,
            "limited_scope": limited_scope,
            "scope_message": scope_message,
            "column_count": len(columns),
            "has_crawlability": has_crawlability,
            "has_content": has_content,
            "has_performance": has_performance,
            "has_accessibility": has_accessibility,
        }
    
    def _determine_seo_confidence(self, column_analysis: Dict[str, Any], processed_data: Any) -> Dict[str, str]:
        """
        Determine confidence level based on SEO data completeness.
        
        Args:
            column_analysis: Analysis of available columns
            processed_data: Processed SEO data
        
        Returns:
            Dictionary with confidence level and reason
        """
        available_count = len(column_analysis["available_categories"])
        
        # Determine data size
        if isinstance(processed_data, list):
            data_count = len(processed_data)
        else:
            data_count = 1  # Aggregated data
        
        if available_count == 0:
            return {
                "level": "Low",
                "reason": "No recognized SEO data categories available."
            }
        elif available_count == 1 and column_analysis["has_crawlability"]:
            return {
                "level": "Medium",
                "reason": "Only crawlability/status code data available. Cannot assess content, performance, or accessibility."
            }
        elif available_count <= 2:
            return {
                "level": "Medium",
                "reason": f"Limited SEO data scope. Only {', '.join(column_analysis['available_categories'])} available."
            }
        elif data_count < 10:
            return {
                "level": "Medium",
                "reason": "Full SEO categories available but limited data points (fewer than 10 URLs)."
            }
        else:
            return {
                "level": "High",
                "reason": f"Comprehensive SEO data available across {available_count} categories with sufficient sample size."
            }
    
    def _generate_no_data_explanation(self) -> str:
        """
        Generate explanation for empty spreadsheet.
        
        Returns:
            User-friendly explanation
        """
        return """NO_SEO_DATA: The Google Sheets spreadsheet appears to be empty or contains no data rows.

This could be due to several reasons:

• **Empty Spreadsheet**: The sheet may not have been populated with SEO crawl data yet.

• **Wrong Sheet Selection**: If the spreadsheet has multiple tabs, the default tab might be empty. Specify the correct sheet name if needed.

• **Export Issue**: If you exported from Screaming Frog or another tool, the export may not have completed successfully.

• **Permission Issue**: The service account may not have access to the correct spreadsheet or specific sheets within it.

**Recommendations:**
- Verify the spreadsheet ID is correct
- Check that the spreadsheet contains SEO crawl data (from Screaming Frog, Sitebulb, etc.)
- Ensure the service account has "Viewer" access to the spreadsheet
- If using multiple sheets/tabs, specify the sheet name in your query

**Expected Data Format:**
A typical SEO crawl export should include columns like:
- Address/URL
- Status Code
- Title
- Meta Description
- H1/H2 headings
- Word Count
- Indexability status

Please populate the spreadsheet with SEO data and try again."""
    
    def _compute_seo_risk_scores(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute SEO risk scores for URLs using deterministic rules.
        
        Scoring Rules:
        - +3 if PSI Error is present
        - +2 if ANY WCAG violation field is non-empty
        - +1 if Best Practice Violations is non-empty
        - 0 if none of the above
        
        Classification:
        - Score ≥3 → High SEO Risk
        - Score = 1–2 → Medium SEO Risk
        - Score = 0 → Low SEO Risk
        
        Args:
            data: List of SEO data rows
        
        Returns:
            Dictionary with risk scores and classification
        """
        if not data or len(data) == 0:
            return None
        
        risk_data = []
        high_count = 0
        medium_count = 0
        low_count = 0
        
        for row in data:
            try:
                score = 0
                url = row.get("Address") or row.get("URL") or row.get("address") or row.get("url") or "Unknown URL"
                
                # +3 if PSI Error is present
                psi_error = row.get("PSI Error") or row.get("psi error") or ""
                if psi_error and str(psi_error).strip() and str(psi_error).strip().lower() not in ["", "0", "none", "n/a"]:
                    score += 3
                
                # +2 if ANY WCAG violation field is non-empty
                wcag_fields = [
                    "WCAG* Violations",
                    "WCAG Violations", 
                    "wcag* violations",
                    "wcag violations",
                    "All Violations"  # Often contains WCAG violations
                ]
                for field in wcag_fields:
                    wcag_val = row.get(field) or ""
                    if wcag_val and str(wcag_val).strip() and str(wcag_val).strip().lower() not in ["", "0", "none", "n/a"]:
                        score += 2
                        break  # Only count once
                
                # +1 if Best Practice Violations is non-empty
                best_practice = row.get("Best Practice Violations") or row.get("best practice violations") or ""
                if best_practice and str(best_practice).strip() and str(best_practice).strip().lower() not in ["", "0", "none", "n/a"]:
                    score += 1
                
                # Classify risk
                if score >= 3:
                    risk_level = "High"
                    high_count += 1
                elif score >= 1:
                    risk_level = "Medium"
                    medium_count += 1
                else:
                    risk_level = "Low"
                    low_count += 1
                
                risk_data.append({
                    "url": url,
                    "score": score,
                    "risk_level": risk_level
                })
            
            except Exception as e:
                logger.debug(f"Error scoring URL: {e}")
                continue
        
        # Sort by score descending
        risk_data.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "scored_urls": risk_data,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "total_count": len(risk_data)
        }
    
    def _generate_risk_summary(self, risk_scores: Dict[str, Any]) -> str:
        """
        Generate business-friendly SEO risk summary.
        
        Args:
            risk_scores: Risk scoring results from _compute_seo_risk_scores
        
        Returns:
            Formatted risk summary text
        """
        if not risk_scores:
            return ""
        
        high_count = risk_scores["high_count"]
        medium_count = risk_scores["medium_count"]
        low_count = risk_scores["low_count"]
        scored_urls = risk_scores["scored_urls"]
        
        # If ALL URLs are Low Risk
        if high_count == 0 and medium_count == 0:
            return "\n\n---\n**SEO Risk Summary:**\nNo critical SEO risks detected. Crawlability is healthy, but ongoing monitoring is recommended."
        
        # Build summary
        summary_parts = ["\n\n---\n**SEO Risk Summary:**"]
        
        # Aggregate counts
        risk_breakdown = []
        if high_count > 0:
            risk_breakdown.append(f"**{high_count} High-risk URL(s)**")
        if medium_count > 0:
            risk_breakdown.append(f"{medium_count} Medium-risk URL(s)")
        if low_count > 0:
            risk_breakdown.append(f"{low_count} Low-risk URL(s)")
        
        summary_parts.append(" | ".join(risk_breakdown))
        
        # Top 3 highest-risk URLs
        top_3 = [url for url in scored_urls if url["risk_level"] in ["High", "Medium"]][:3]
        if top_3:
            summary_parts.append("\n\n**Top Priority URLs:**")
            for i, url_info in enumerate(top_3, 1):
                url_display = url_info["url"]
                if len(url_display) > 60:
                    url_display = url_display[:57] + "..."
                summary_parts.append(f"{i}. [{url_info['risk_level']}] {url_display} (Score: {url_info['score']})")
        
        # Actionable insight
        if high_count > 0:
            summary_parts.append("\n**Recommendation:** Prioritize high-risk URLs to prevent accessibility and performance issues from impacting user experience and search visibility.")
        elif medium_count > 0:
            summary_parts.append("\n**Recommendation:** Address medium-risk URLs to improve overall site quality and maintain competitive search performance.")
        
        return "\n".join(summary_parts)


# Global SEO agent instance
seo_agent = SEOAgent()
