"""
Analytics Agent (Tier 1) - Processes queries about GA4 data.
Translates natural language to GA4 queries using LLM, executes them, and generates answers.
"""

import logging
from typing import Dict, Any, Optional
from services.llm_service import llm_service
from services.ga4_service import ga4_service
from config.ga4_schema import validate_metrics, validate_dimensions

logger = logging.getLogger(__name__)


class AnalyticsAgent:
    """Agent for handling analytics queries using GA4 data."""
    
    def __init__(self):
        self.llm = llm_service
        self.ga4 = ga4_service
    
    async def process_query(
        self,
        query: str,
        property_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process an analytics query.
        
        Args:
            query: Natural language query
            property_id: GA4 property ID
            request_id: Unique request identifier for tracking
        
        Returns:
            Dictionary with answer and data
        """
        req_prefix = f"[{request_id}]" if request_id else ""
        
        try:
            # Get property ID
            prop_id = property_id or self.ga4.get_default_property_id()
            if not prop_id:
                logger.warning(f"{req_prefix} No property ID available")
                return {
                    "success": False,
                    "error": "No property ID provided and no default configured",
                }
            
            # Step 1: Validate query contains analytics intent
            validation_result = self._validate_query_intent(query)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "QUERY_VALIDATION_FAILED",
                    "answer": validation_result["message"],
                }
            
            # Step 2: Translate NL query to GA4 query plan using LLM
            query_plan = await self._generate_query_plan(query)
            query_plan["property_id"] = prop_id  # Track for error messages
            
            # Step 3: Validate metrics and dimensions
            validation_result = self._validate_query_plan(query_plan)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"Invalid query plan: {validation_result['error']}",
                }
            
            # Step 3: Execute GA4 query
            ga4_data = self.ga4.run_report(
                property_id=prop_id,
                metrics=query_plan.get("metrics", []),
                dimensions=query_plan.get("dimensions", []),
                start_date=query_plan.get("start_date", "30daysAgo"),
                end_date=query_plan.get("end_date", "today"),
                limit=query_plan.get("limit", 100),
            )
            
            # CRITICAL: Guard against ga4_data being a list or None BEFORE any string key access
            if not ga4_data or not isinstance(ga4_data, dict):
                logger.error(f"{req_prefix} GA4 data is not a dict: {type(ga4_data)}")
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
            
            # Step 4: Handle empty data with safe fallback
            logger.info(f"{req_prefix} GA4 query returned {ga4_data.get('row_count', 'UNKNOWN')} rows")
            
            if ga4_data["row_count"] == 0:
                logger.warning("⚠️ FALLBACK TRIGGER: Initial query returned empty data, attempting safe fallback")
                
                # Safe fallback: activeUsers with date dimension, last 30 days
                try:
                    logger.info("🔄 Executing fallback query: metrics=['activeUsers'], dimensions=['date'], last 30 days")
                    fallback_data = self.ga4.run_report(
                        property_id=prop_id,
                        metrics=["activeUsers"],
                        dimensions=["date"],  # Include date dimension
                        start_date="30daysAgo",
                        end_date="today",
                        limit=100,
                    )
                    
                    logger.info(f"📊 Fallback query returned {fallback_data.get('row_count', 'UNKNOWN')} rows")
                    
                    if fallback_data["row_count"] > 0:
                        logger.warning("✅ FALLBACK SUCCESS: Using fallback data")
                        ga4_data = fallback_data
                        query_plan["used_fallback"] = True
                        query_plan["fallback_note"] = "Using available data from the last 30 days"
                    else:
                        logger.warning("❌ FALLBACK EMPTY: Fallback query also returned empty data")
                except Exception as e:
                    logger.error(f"❌ FALLBACK ERROR: Fallback query failed: {e}")
                
                # Still empty after fallback - provide business explanation
                if ga4_data["row_count"] == 0:
                    logger.info("📝 Returning no-data explanation (both original and fallback empty)")
                    explanation = self._generate_empty_data_explanation(query_plan)
                    explanation += "\n\n---\n**Confidence Level:** Low\n**Reason:** No analytics data available for the specified period."
                    return {
                        "success": True,
                        "answer": explanation,
                        "data": ga4_data,
                    }
            
            # Step 4.5: Comparative Period Analysis (if we have data)
            comparative_data = None
            if ga4_data["row_count"] > 0 and not query_plan.get("used_fallback"):
                try:
                    comparative_data = await self._fetch_comparative_period(
                        prop_id, query_plan, req_prefix
                    )
                    # GUARD: Prevent indexing errors if comparative rows are empty/None
                    if comparative_data:
                        comp_rows = comparative_data.get("rows")
                        if not comp_rows or not isinstance(comp_rows, list) or len(comp_rows) == 0:
                            logger.warning(f"{req_prefix} Comparative period has no valid rows, aborting comparison")
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
                        query_plan["comparative_data"] = comparative_data
                        logger.info(f"{req_prefix} Comparative analysis successful")
                except Exception as e:
                    logger.warning(f"{req_prefix} Comparative analysis failed: {e}")
            
            # Step 5: Generate natural language answer from data
            answer = await self._generate_answer(query, query_plan, ga4_data)
            
            
            # Step 5.5: Add trend indicators and alerts
            if comparative_data:
                # GUARD: Validate rows before any indexing in comparison logic
                rows = ga4_data.get("rows")
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
                
                trend_summary = self._generate_trend_summary(ga4_data, comparative_data, query_plan)
                if trend_summary:
                    answer += f"\n\n{trend_summary}"
            
            # Add threshold-based alerts
            alerts = self._generate_threshold_alerts(ga4_data, comparative_data, query_plan)
            if alerts:
                answer += f"\n\n{alerts}"
            
            # Add fallback note if used
            if query_plan.get("used_fallback"):
                answer = f"**Note:** {query_plan['fallback_note']}\n\n{answer}"
            
            # Append confidence level (simplified format)
            confidence = self._determine_confidence(ga4_data, query_plan)
            answer += f"\n\nConfidence: {confidence['level']}"
            
            return {
                "success": True,
                "answer": answer,
                "data": ga4_data,
                "query_plan": query_plan,
            }
        
        except Exception as e:
            logger.error(f"Error in analytics agent: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _generate_query_plan(self, query: str) -> Dict[str, Any]:
        """
        Use LLM to translate natural language query to GA4 query plan.
        
        Args:
            query: Natural language query
        
        Returns:
            Query plan with metrics, dimensions, dates
        """
        system_message = """You are a GA4 query translator. Convert natural language queries into GA4 query plans.

Available metrics include: activeUsers, sessions, pageViews, bounceRate, totalRevenue, conversions, etc.
Available dimensions include: date, country, city, deviceCategory, pagePath, source, medium, etc.

Return a JSON object with:
- metrics: array of metric names
- dimensions: array of dimension names (optional)
- start_date: date in format 'YYYY-MM-DD' or relative like '7daysAgo', '30daysAgo', 'yesterday', 'today'
- end_date: date in same format
- limit: number of rows (default 100)

Example input: "How many users visited last week?"
Example output:
{
  "metrics": ["activeUsers"],
  "dimensions": ["date"],
  "start_date": "7daysAgo",
  "end_date": "yesterday",
  "limit": 100
}"""
        
        prompt = f"Query: {query}\n\nGenerate the GA4 query plan:"
        
        try:
            plan = self.llm.generate_structured_output(
                prompt=prompt,
                system_message=system_message,
                temperature=0.3,
            )
            return plan
        except Exception as e:
            logger.error(f"Failed to generate query plan: {e}")
            # Return a default plan
            return {
                "metrics": ["activeUsers"],
                "dimensions": [],
                "start_date": "30daysAgo",
                "end_date": "today",
                "limit": 100,
            }
    
    def _validate_query_plan(self, query_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate query plan against allowlists.
        
        Args:
            query_plan: Query plan from LLM
        
        Returns:
            Validation result with valid flag and error message
        """
        metrics = query_plan.get("metrics", [])
        dimensions = query_plan.get("dimensions", [])
        
        # Validate metrics
        metrics_valid, invalid_metrics = validate_metrics(metrics)
        if not metrics_valid:
            return {
                "valid": False,
                "error": f"Invalid metrics: {', '.join(invalid_metrics)}",
            }
        
        # Validate dimensions
        if dimensions:
            dims_valid, invalid_dims = validate_dimensions(dimensions)
            if not dims_valid:
                return {
                    "valid": False,
                    "error": f"Invalid dimensions: {', '.join(invalid_dims)}",
                }
        
        return {"valid": True}
    
    async def _generate_answer(
        self,
        original_query: str,
        query_plan: Dict[str, Any],
        ga4_data: Dict[str, Any],
    ) -> str:
        """
        Generate natural language answer from GA4 data.
        
        Args:
            original_query: Original user query
            query_plan: Query plan used
            ga4_data: GA4 response data
        
        Returns:
            Natural language answer
        """
        # Defensive type check: ensure ga4_data is a dict
        if not isinstance(ga4_data, dict):
            logger.error(f"ga4_data is not a dict: {type(ga4_data)}")
            return "Unable to process analytics data due to unexpected data format."
        
        system_message = """You are a data analyst. Convert GA4 data into clear, natural language answers.
Be specific with numbers and insights. If the data shows trends, mention them."""
        
        # Safely access ga4_data fields
        row_count = ga4_data.get('row_count', 0)
        rows = ga4_data.get('rows', [])
        
        # Prepare data summary
        data_summary = f"""
Query: {original_query}

Metrics: {', '.join(query_plan.get('metrics', []))}
Dimensions: {', '.join(query_plan.get('dimensions', []))}
Date Range: {query_plan.get('start_date')} to {query_plan.get('end_date')}

Data ({row_count} rows):
{self._format_data_for_llm(rows[:20])}  # Limit to first 20 rows
"""
        
        prompt = f"{data_summary}\n\nProvide a clear, concise answer to the query:"
        
        try:
            answer = self.llm.generate_text(
                prompt=prompt,
                system_message=system_message,
                temperature=0.5,
            )
            return answer
        except Exception as e:
            logger.error(f"Failed to generate answer: {e}")
            # Fallback to basic summary
            return f"Found {row_count} results for your query."
    
    def _generate_empty_data_explanation(self, query_plan: Dict[str, Any]) -> str:
        """
        Generate a business-friendly explanation when no data is found.
        
        Args:
            query_plan: Query plan that was attempted
        
        Returns:
            User-friendly explanation with possible reasons
        """
        date_range = f"{query_plan.get('start_date', 'N/A')} to {query_plan.get('end_date', 'N/A')}"
        metrics = ', '.join(query_plan.get('metrics', []))
        
        explanation = f"""No analytics data was found for the requested period ({date_range}).

This could be due to several reasons:

• **New GA4 Property**: If your GA4 property was recently created, it may not have accumulated data yet. Data collection typically begins once the tracking code is properly installed.

• **No Website Traffic**: There may have been no visitors to your website during the selected time period, or tracking may not be capturing events.

• **Date Range Issue**: The selected date range might be outside of your property's data collection period. GA4 properties only retain data from their creation date forward.

• **Property Configuration**: Double-check that you're querying the correct GA4 property ID and that data collection is properly configured.

• **Permission Limits**: Your service account may not have sufficient permissions to access all data, or certain filters might be blocking data visibility.

**Recommendations:**
- Verify your GA4 tracking code is properly installed
- Check that the property ID ({query_plan.get('property_id', 'N/A')}) is correct
- Try a broader date range (e.g., last 30 days)
- Ensure your GA4 property is actively collecting data

If you believe this is an error, please verify your GA4 setup and try again."""
        
        return explanation
    
    def _determine_confidence(self, ga4_data: Dict[str, Any], query_plan: Dict[str, Any]) -> Dict[str, str]:
        """
        Determine confidence level based on data completeness.
        
        Args:
            ga4_data: GA4 response data
            query_plan: Query plan executed
        
        Returns:
            Dictionary with confidence level and reason
        """
        row_count = ga4_data.get("row_count", 0)
        metrics = query_plan.get("metrics", [])
        
        # Check if fallback metrics were used
        used_fallback = "sessions" in metrics or "totalUsers" in metrics
        original_had_active_users = query_plan.get("original_metrics") and "activeUsers" in query_plan.get("original_metrics", [])
        
        if row_count == 0:
            return {
                "level": "Low",
                "reason": "No data available for analysis."
            }
        elif row_count < 10:
            return {
                "level": "Medium",
                "reason": "Limited data points available (fewer than 10 rows)."
            }
        elif used_fallback and original_had_active_users:
            return {
                "level": "Medium",
                "reason": "Using fallback metrics (sessions/totalUsers) as primary metrics returned no data."
            }
        elif row_count >= 100:
            return {
                "level": "High",
                "reason": "Comprehensive data available with sufficient sample size."
            }
        else:
            return {
                "level": "High",
                "reason": "Complete data available for the requested period."
            }
    
    def _validate_query_intent(self, query: str) -> Dict[str, Any]:
        """
        Validate that query contains analytics intent before calling GA4.
        
        Args:
            query: Natural language query
        
        Returns:
            Dictionary with validation result and message
        """
        query_lower = query.lower()
        
        # Define metric keywords
        metric_keywords = [
            "users", "user", "sessions", "session", "traffic", "visitors", "visitor",
            "active users", "pageviews", "pageview", "views", "bounce", "conversions",
            "conversion", "revenue", "engagement"
        ]
        
        # Define time indicator keywords
        time_keywords = [
            "today", "yesterday", "last", "past", "previous", "this week", "this month",
            "last week", "last month", "days ago", "daysago", "weeks ago", "months ago",
            "since", "between", "from", "to", "during", "in", "on",
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december"
        ]
        
        # Check for metric presence
        has_metric = any(keyword in query_lower for keyword in metric_keywords)
        
        # Check for time indicator presence
        has_time = any(keyword in query_lower for keyword in time_keywords)
        
        # Validate both are present
        if not has_metric and not has_time:
            return {
                "valid": False,
                "message": """Your query needs to be more specific for analytics analysis.

Please include:
• **A metric** (e.g., users, sessions, traffic, pageviews, conversions)
• **A time period** (e.g., last 7 days, yesterday, this month, last week)

**Examples of valid queries:**
- "How many users visited last week?"
- "Show me sessions for the past 30 days"
- "What was the traffic yesterday?"
- "Total pageviews this month"

Please rephrase your query with both a metric and time period."""
            }
        elif not has_metric:
            return {
                "valid": False,
                "message": """Your query is missing a specific metric to analyze.

Please specify what you want to measure:
• **Users/Visitors**: "How many users..."
• **Sessions**: "How many sessions..."
• **Traffic**: "What was the traffic..."
• **Pageviews**: "Show me pageviews..."
• **Conversions**: "How many conversions..."

**Example:** "How many users visited {your_time_period}?"

Please rephrase your query to include a metric."""
            }
        elif not has_time:
            return {
                "valid": False,
                "message": """Your query is missing a time period.

Please specify when you want to analyze:
• **Recent**: "last 7 days", "yesterday", "today"
• **Specific period**: "last week", "this month", "last month"
• **Date range**: "between Jan 1 and Jan 31"

**Example:** "{your_metric} in the last 7 days"

Please rephrase your query to include a time period."""
            }
        
        return {"valid": True}
    
    def _format_data_for_llm(self, rows: list) -> str:
        """Format data rows for LLM consumption."""
        if not rows:
            return "No data"
        
        # Convert to readable format
        formatted = []
        for row in rows[:10]:  # Limit to 10 rows
            formatted.append(str(row))
        
        return "\n".join(formatted)
    
    async def _fetch_comparative_period(
        self,
        property_id: str,
        query_plan: Dict[str, Any],
        req_prefix: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch data for the comparative (previous) period.
        
        Args:
            property_id: GA4 property ID
            query_plan: Original query plan
            req_prefix: Request ID prefix for logging
            
        Returns:
            Comparative period data or None if unavailable
        """
        try:
            # Calculate previous period dates based on the query plan
            start_date_str = query_plan.get("start_date", "7daysAgo")
            end_date_str = query_plan.get("end_date", "yesterday")
            
            # Simple mapping for common GA4 date formats
            # For now, just use double the period for comparison
            if "7daysAgo" in start_date_str:
                prev_start = "14daysAgo"
                prev_end = "8daysAgo"
            elif "30daysAgo" in start_date_str:
                prev_start = "60daysAgo"
                prev_end = "31daysAgo"
            else:
                # Default fallback
                prev_start = "14daysAgo"
                prev_end = "8daysAgo"
            
            logger.info(f"{req_prefix} Fetching comparative period: {prev_start} to {prev_end}")
            
            # Fetch comparative data with same metrics/dimensions
            comparative_data = self.ga4.run_report(
                property_id=property_id,
                metrics=query_plan.get("metrics", ["activeUsers"]),
                dimensions=[],  # No dimensions for aggregate comparison
                start_date=prev_start,
                end_date=prev_end,
                limit=100,
            )
            
            # Early-exit guard: check if we got valid data
            if not comparative_data:
                logger.debug(f"{req_prefix} Comparative data is None")
                return None
            
            rows = comparative_data.get("rows", [])
            if not rows or len(rows) == 0:
                logger.debug(f"{req_prefix} Comparative period returned no rows")
                return None
            
            return comparative_data
            
        except Exception as e:
            logger.warning(f"{req_prefix} Could not fetch comparative period: {e}")
            return None
    
    def _generate_trend_summary(
        self,
        current_data: Dict[str, Any],
        comparative_data: Dict[str, Any],
        query_plan: Dict[str, Any],
    ) -> str:
        """
        Generate trend summary with percent change and indicators.
        
        Args:
            current_data: Current period data
            comparative_data: Previous period data
            query_plan: Query plan with metrics info
            
        Returns:
            Formatted trend summary string
        """
        try:
            # Extract rows
            current_rows = current_data.get("rows", [])
            prev_rows = comparative_data.get("rows", [])
            
            # Defensive check: need data from both periods
            if not current_rows or not prev_rows:
                logger.debug("Trend summary skipped: missing current or previous period data")
                return ""
            
            # Get metrics from query plan
            metrics = query_plan.get("metrics", [])
            if not metrics:
                logger.debug("Trend summary skipped: no metrics in query plan")
                return ""
            
            # Calculate trends for each metric
            trends = []
            for metric in metrics:
                try:
                    # Sum metric values across all rows (aggregate)
                    # Rows are dicts like: {"date": "20231218", "activeUsers": "500"}
                    current_val = 0.0
                    prev_val = 0.0
                    
                    # Sum current period values
                    for row in current_rows:
                        if metric in row:
                            try:
                                current_val += float(row[metric])
                            except (ValueError, TypeError):
                                logger.debug(f"Could not parse {metric} value: {row.get(metric)}")
                                continue
                    
                    # Sum previous period values
                    for row in prev_rows:
                        if metric in row:
                            try:
                                prev_val += float(row[metric])
                            except (ValueError, TypeError):
                                logger.debug(f"Could not parse {metric} value: {row.get(metric)}")
                                continue
                    
                    # Calculate percent change if we have valid values
                    if prev_val > 0 and current_val >= 0:
                        percent_change = ((current_val - prev_val) / prev_val) * 100
                        
                        # Determine indicator
                        if percent_change > 5:
                            indicator = "↑"
                        elif percent_change < -5:
                            indicator = "↓"
                        else:
                            indicator = "→"
                        
                        trend_text = f"{indicator} {abs(percent_change):.1f}%"
                        trends.append(f"{metric}: {trend_text} vs previous period")
                    else:
                        logger.debug(f"Skipping trend for {metric}: prev_val={prev_val}, current_val={current_val}")
                        
                except Exception as e:
                    logger.debug(f"Could not calculate trend for {metric}: {e}")
                    continue
            
            if trends:
                return "**Trend Analysis:**\n" + "\n".join(f"- {t}" for t in trends)
            
            return ""
            
        except Exception as e:
            logger.warning(f"Error generating trend summary: {e}")
            return ""
    
    def _generate_threshold_alerts(
        self,
        current_data: Dict[str, Any],
        comparative_data: Optional[Dict[str, Any]],
        query_plan: Dict[str, Any],
    ) -> str:
        """
        Generate threshold-based alerts for concerning metrics.
        
        Args:
            current_data: Current period data
            comparative_data: Previous period data (optional)
            query_plan: Query plan with metrics info
            
        Returns:
            Formatted alert string
        """
        alerts = []
        
        try:
            metrics = query_plan.get("metrics", [])
            current_rows = current_data.get("rows", [])
            
            # Defensive check: need current data
            if not current_rows:
                logger.debug("Threshold alerts skipped: no current data")
                return ""
            
            # Check for bounce rate threshold
            if "bounceRate" in metrics:
                try:
                    # Aggregate bounce rate across all rows
                    bounce_sum = 0.0
                    bounce_count = 0
                    
                    for row in current_rows:
                        if "bounceRate" in row:
                            try:
                                bounce_sum += float(row["bounceRate"])
                                bounce_count += 1
                            except (ValueError, TypeError):
                                continue
                    
                    if bounce_count > 0:
                        avg_bounce_rate = bounce_sum / bounce_count
                        if avg_bounce_rate > 0.70:
                            alerts.append("⚠️ **Alert**: Bounce rate exceeds 70% - consider improving page engagement")
                except Exception as e:
                    logger.debug(f"Could not check bounce rate threshold: {e}")
            
            # Check for traffic drop vs previous period
            if comparative_data:
                try:
                    prev_rows = comparative_data.get("rows", [])
                    if not prev_rows:
                        logger.debug("Traffic drop check skipped: no previous period data")
                        return "\n".join(f"- {a}" for a in alerts) if alerts else ""
                    
                    # Look for user/session metrics
                    user_metrics = [m for m in metrics if "user" in m.lower() or m == "sessions"]
                    
                    if user_metrics:
                        metric = user_metrics[0]
                        
                        # Sum current period
                        current_val = 0.0
                        for row in current_rows:
                            if metric in row:
                                try:
                                    current_val += float(row[metric])
                                except (ValueError, TypeError):
                                    continue
                        
                        # Sum previous period
                        prev_val = 0.0
                        for row in prev_rows:
                            if metric in row:
                                try:
                                    prev_val += float(row[metric])
                                except (ValueError, TypeError):
                                    continue
                        
                        # Check for significant drop
                        if prev_val > 0:
                            drop_pct = ((current_val - prev_val) / prev_val) * 100
                            if drop_pct < -20:
                                alerts.append(f"⚠️ **Alert**: {metric} dropped {abs(drop_pct):.1f}% vs previous period")
                        
                except Exception as e:
                    logger.debug(f"Could not check traffic drop: {e}")
            
            if alerts:
                return "**Alerts:**\n" + "\n".join(f"- {a}" for a in alerts)
            
            return ""
            
        except Exception as e:
            logger.warning(f"Error generating threshold alerts: {e}")
            return ""



# Global analytics agent instance
analytics_agent = AnalyticsAgent()
