# Signoz MCP Server

A Model Context Protocol (MCP) server that provides tools for interacting with Signoz observability platform. This server exposes various tools for dashboard management, APM metrics, service discovery, and custom queries.

## Setup

### Environment Variables

Set the following environment variables:

```bash
export SIGNOZ_HOST="https://your-signoz-instance.com"
export SIGNOZ_API_KEY="your-api-key"  
export SIGNOZ_SSL_VERIFY="true"       # Optional, defaults to true
```

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

Or using uv:
```bash
uv sync
```

## Development

A lot of what is seen here is based off the MCP server implementation found [here](https://github.com/DrDroidLab/signoz-mcp-server). I was running into a lot of issues with using their MCP queries however, and the server was running using Flask, and claude was interpreting the logs as commands + failing to parse them. 

This server is almost a wrapper around the original implementation, using the simple mcp protocol to communicate tool use. 


## Tools Available

| Tool Name | Description |
|-----------|-------------|
| `test_connection` | Verify connectivity to your Signoz instance and configuration |
| `fetch_dashboards` | List all available dashboards from Signoz |
| `fetch_dashboard_details` | Retrieve detailed information about a specific dashboard by its ID |
| `fetch_dashboard_data` | Fetch all panel data for a given dashboard by name and time range |
| `fetch_apm_metrics` | Retrieve standard APM metrics for a given service and time range |
| `fetch_services` | Fetch all instrumented services from Signoz with optional time range filtering |
| `execute_clickhouse_query` | Execute custom Clickhouse SQL queries via the Signoz API |
| `execute_builder_query` | Execute Signoz builder queries for custom metrics and aggregations |
| `fetch_traces_or_logs` | Fetch traces or logs from SigNoz using ClickHouse SQL |


## Usage Examples

### Example Tool Calls

#### Test Connection
```json
{
  "name": "test_connection",
  "arguments": {}
}
```

#### Fetch Services
```json
{
  "name": "fetch_services", 
  "arguments": {
    "duration": "24h"
  }
}
```

#### Fetch APM Metrics
```json
{
  "name": "fetch_apm_metrics",
  "arguments": {
    "service_name": "my-service",
    "duration": "2h",
    "window": "1m"
  }
}
```

#### Execute ClickHouse Query
```json
{
  "name": "execute_clickhouse_query",
  "arguments": {
    "query": "SELECT serviceName, count() as requests FROM signoz_traces.distributed_signoz_index_v3 WHERE timestamp >= now() - INTERVAL 1 HOUR GROUP BY serviceName",
    "duration": "1h"
  }
}
```

#### Fetch Traces or Logs
```json
{
  "name": "fetch_traces_or_logs",
  "arguments": {
    "data_type": "traces",
    "service_name": "my-service", 
    "duration": "1h",
    "limit": 50
  }
}
```

## Configuration

The server reads configuration from environment variables:

- `SIGNOZ_HOST`: Your Signoz instance URL (required)
- `SIGNOZ_API_KEY`: API key for authentication (optional)
- `SIGNOZ_SSL_VERIFY`: Enable/disable SSL verification (default: true)
