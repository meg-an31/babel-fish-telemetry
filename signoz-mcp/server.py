import os
import json
import logging
from typing import Any
from datetime import datetime, timezone
from mcp.server.fastmcp import FastMCP

from signoz_processor import SignozApiProcessor

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("signoz-mcp")

def get_signoz_processor() -> SignozApiProcessor:
    """Get configured Signoz processor from environment variables"""
    signoz_host = os.environ.get("SIGNOZ_HOST")
    signoz_api_key = os.environ.get("SIGNOZ_API_KEY") 
    ssl_verify = os.environ.get("SIGNOZ_SSL_VERIFY", "true")
    
    if not signoz_host:
        raise ValueError("SIGNOZ_HOST environment variable is required")
    
    return SignozApiProcessor(signoz_host, signoz_api_key, ssl_verify)

def format_response(data: Any, status: str = "success") -> str:
    """Format response data as JSON string"""
    response = {"status": status, "data": data}
    return json.dumps(response, indent=2)

def format_error(message: str) -> str:
    """Format error response"""
    return format_response({"error": message}, "error")

@mcp.tool()
async def test_connection() -> str:
    """Verify connectivity to your Signoz instance and configuration."""
    try:
        processor = get_signoz_processor()
        result = processor.test_connection()
        return format_response({
            "connected": result,
            "message": "Connection successful" if result else "Connection failed"
        })
    except Exception as e:
        return format_error(str(e))

@mcp.tool()
async def fetch_dashboards() -> str:
    """List all available dashboards from Signoz."""
    try:
        processor = get_signoz_processor()
        result = processor.fetch_dashboards()
        return format_response(result)
    except Exception as e:
        return format_error(str(e))

@mcp.tool()
async def fetch_dashboard_details(dashboard_id: str) -> str:
    """Retrieve detailed information about a specific dashboard by its ID. This information contains the metadata of the dashboard, not the live panel data.
    
    Args:
        dashboard_id: The ID of the dashboard to fetch details for
    """
    try:
        processor = get_signoz_processor()
        result = processor.fetch_dashboard_details(dashboard_id)
        if result:
            return format_response(result)
        else:
            return format_error(f"Dashboard {dashboard_id} not found")
    except Exception as e:
        return format_error(str(e))

@mcp.tool()
async def fetch_dashboard_data(
    dashboard_name: str,
    start_time: str | None = None,
    end_time: str | None = None,
    duration: str | None = None,
    step: int | None = None,
    variables_json: str | None = None
) -> str:
    """Fetch all panel data for a given dashboard by name and time range.
    
    Args:
        dashboard_name: The name of the dashboard to fetch data for
        start_time: Start time in RFC3339 or relative string (e.g., 'now-2h')
        end_time: End time in RFC3339 or relative string (e.g., 'now')  
        duration: Duration string for the time window (e.g., '2h', '90m')
        step: Step interval for the query (seconds, optional)
        variables_json: Optional variable overrides as a JSON object
    """
    try:
        processor = get_signoz_processor()
        result = processor.fetch_dashboard_data(
            dashboard_name, start_time, end_time, step, variables_json, duration
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return format_error(str(e))

@mcp.tool()
async def fetch_apm_metrics(
    service_name: str,
    start_time: str | None = None,
    end_time: str | None = None,
    duration: str | None = None,
    window: str = "1m"
) -> str:
    """Retrieve standard APM metrics (request rate, error rate, latency, apdex, etc.) for a given service and time range.
    
    Args:
        service_name: The name of the service to fetch APM metrics for
        start_time: Start time in RFC3339 or relative string (e.g., 'now-2h')
        end_time: End time in RFC3339 or relative string (e.g., 'now')
        duration: Duration string for the time window (e.g., '2h', '90m')
        window: Query window (e.g., '1m', '5m'). Default: '1m'
    """
    try:
        processor = get_signoz_processor()
        result = processor.fetch_apm_metrics(
            service_name, start_time, end_time, window, duration=duration
        )
        return format_response({
            "service_name": service_name,
            "metrics": result
        })
    except Exception as e:
        return format_error(str(e))

@mcp.tool()
async def fetch_services(
    start_time: str | None = None,
    end_time: str | None = None,
    duration: str | None = None
) -> str:
    """Fetch all instrumented services from Signoz with optional time range filtering.
    
    Args:
        start_time: Start time in RFC3339 or relative string (e.g., 'now-2h')
        end_time: End time in RFC3339 or relative string (e.g., 'now')
        duration: Duration string for the time window (e.g., '2h', '90m'). Defaults to last 24 hours.
    """
    try:
        processor = get_signoz_processor()
        result = processor.fetch_services(start_time, end_time, duration)
        if isinstance(result, dict) and result.get("status") == "error":
            return json.dumps(result, indent=2)
        return format_response(result)
    except Exception as e:
        return format_error(str(e))

@mcp.tool() 
async def execute_clickhouse_query(
    query: str,
    start_time: str | None = None,
    end_time: str | None = None,
    duration: str | None = None,
    panel_type: str = "table",
    step: int = 60
) -> str:
    """Execute custom Clickhouse SQL queries via the Signoz API with time range support.
    
    Args:
        query: The ClickHouse SQL query to execute
        start_time: Start time in RFC3339 or relative string (e.g., 'now-2h')
        end_time: End time in RFC3339 or relative string (e.g., 'now')
        duration: Duration string for the time window (e.g., '2h', '90m')
        panel_type: Panel type (e.g., 'table', 'graph')
        step: Step interval in seconds
    """
    try:
        processor = get_signoz_processor()
        start_dt, end_dt = processor._get_time_range(start_time, end_time, duration, default_hours=3)
        result = processor.execute_clickhouse_query_tool(
            query, start_dt.timestamp(), end_dt.timestamp(), panel_type, False, step
        )
        return format_response({
            "query": query,
            "result": result
        })
    except Exception as e:
        return format_error(str(e))

@mcp.tool()
async def execute_builder_query(
    builder_queries: dict[str, Any],
    start_time: str | None = None,
    end_time: str | None = None,
    duration: str | None = None,
    panel_type: str = "table", 
    step: int = 60
) -> str:
    """Execute Signoz builder queries for custom metrics and aggregations with time range support.
    
    Args:
        builder_queries: Dictionary of builder queries with keys like 'A', 'B', etc.
        start_time: Start time in RFC3339 or relative string (e.g., 'now-2h')
        end_time: End time in RFC3339 or relative string (e.g., 'now')
        duration: Duration string for the time window (e.g., '2h', '90m')
        panel_type: Panel type (e.g., 'table', 'graph')
        step: Step interval in seconds
    """
    try:
        processor = get_signoz_processor()
        start_dt, end_dt = processor._get_time_range(start_time, end_time, duration, default_hours=3)
        result = processor.execute_builder_query_tool(
            builder_queries, start_dt.timestamp(), end_dt.timestamp(), panel_type, step
        )
        return format_response({
            "builder_queries": builder_queries,
            "result": result
        })
    except Exception as e:
        return format_error(str(e))

@mcp.tool()
async def fetch_traces_or_logs(
    data_type: str,
    start_time: str | None = None,
    end_time: str | None = None,
    duration: str | None = None,
    service_name: str | None = None,
    limit: int = 100
) -> str:
    """Fetch traces or logs from SigNoz using ClickHouse SQL. Specify data_type ('traces' or 'logs'), time range, service name, and limit. Returns tabular results for traces or logs.
    
    Args:
        data_type: 'traces' or 'logs' (required)
        start_time: Start time (RFC3339, 'now-2h', etc.)
        end_time: End time (RFC3339, 'now', etc.)
        duration: Duration string (e.g., '2h', '90m')
        service_name: Filter by service name (optional)
        limit: Max number of records to return (default 100)
    """
    try:
        if data_type not in ["traces", "logs"]:
            return format_error(f"Invalid data_type: {data_type}. Must be 'traces' or 'logs'.")
            
        processor = get_signoz_processor()
        start_dt, end_dt = processor._get_time_range(start_time, end_time, duration, default_hours=3)

        if data_type == "traces":
            table = "signoz_traces.distributed_signoz_index_v3"
            select_cols = "traceID, serviceName, name, durationNano, statusCode, timestamp"
            where_clauses = [
                f"timestamp >= toDateTime64({int(start_dt.timestamp())}, 9)",
                f"timestamp < toDateTime64({int(end_dt.timestamp())}, 9)"
            ]
            if service_name:
                where_clauses.append(f"serviceName = '{service_name}'")
        elif data_type == "logs":
            table = "signoz_logs.distributed_logs"
            select_cols = "timestamp, body, severity_text, resource_attributes, trace_id, span_id"
            where_clauses = [
                f"timestamp >= toDateTime64({int(start_dt.timestamp())}, 9)",
                f"timestamp < toDateTime64({int(end_dt.timestamp())}, 9)"
            ]
            if service_name:
                where_clauses.append(f"JSONExtractString(resource_attributes, 'service.name') = '{service_name}'")

        where_sql = " AND ".join(where_clauses)
        query = f"SELECT {select_cols} FROM {table} WHERE {where_sql} LIMIT {limit}"

        result = processor.execute_clickhouse_query_tool(
            query, start_dt.timestamp(), end_dt.timestamp(), "table", False, 60
        )
        return format_response({
            "data_type": data_type,
            "query": query,
            "result": result
        })
    except Exception as e:
        return format_error(str(e))

if __name__ == "__main__":
    mcp.run()