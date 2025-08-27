#!/usr/bin/env python3
"""
Signoz MCP Server - Entry Point

A clean, simplified MCP server for interacting with Signoz API.
Exposes tools for connection testing, dashboard management, APM metrics,
service discovery, and custom queries.

Environment Variables:
- SIGNOZ_HOST: Your Signoz instance URL (required)
- SIGNOZ_API_KEY: Your Signoz API key (optional)
- SIGNOZ_SSL_VERIFY: SSL verification (default: true)
"""

import sys
import os
import logging

def main():
    """Entry point for the Signoz MCP server"""
    logging.basicConfig(level=logging.INFO)
    
    # Check for required environment variables
    if not os.environ.get("SIGNOZ_HOST"):
        print("Error: SIGNOZ_HOST environment variable is required", file=sys.stderr)
        sys.exit(1)
    
    # Import and run the server
    from server import mcp
    mcp.run()

if __name__ == "__main__":
    main()