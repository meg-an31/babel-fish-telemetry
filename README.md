# babel fish telemetry
MCP servers for both Axiom and Signoz, for use in claudecode - predominantly to develop [slarti](https://github.com/Cygnusfear/slarti) :)

## setting up 

#### 1. Axiom

Set up the Axiom database as described [here](https://github.com/axiomhq/mcp-server-axiom).

#### 2. Signoz 

1. Download the source code from inside signoz-mcp
2. Run from inside the source code directory: `uv sync`

#### 3. Integration with claudecode

From inside the directory you want to run claudecode, run the following: 

```zsh
# Signoz MCP connection
# replace <your-url>, <your-api-key>, and /path/to with their relevant values
claude mcp add signoz uv run python main.py —-cwd /path/to/signoz-mcp --env SIGNOZ_HOST=<your-url> --env SIGNOZ_API_KEY=<your-api-key> --env SIGNOZ_SSL_VERIFY=true

# Axiom MCP connection
# replace <your-axiom-token>, <your-axiom-url>, and /path/to/ with their relevant values 
claude mcp add axiom /path/to/axiom-mcp --env AXIOM_TOKEN=<your-axiom-token> --env AXIOM_URL=<your-axiom-url> --env AXIOM_QUERY_RATE=1 --env AXIOM_QUERY_BURST=1 --env AXIOM_DATASETS_RATE=1 --env AXIOM_DATASETS_BURST=1 --env AXIOM_MONITORS_RATE=1 --env AXIOM_MONITORS_BURST=1
```
You can check this is all now set up correctly by running:
```
claude mcp list
```
And you should see a response:
```
Checking MCP server health...

signoz: uv run python main.py —-cwd /path/to/signoz-mcp - ✓ Connected
axiom: /path/to/axiom-mcp  - ✓ Connected
```

By default, these MCP tools will be only available to the local instance of claudecode. To access them globally, use the flag `--i need to check this actually`. 
