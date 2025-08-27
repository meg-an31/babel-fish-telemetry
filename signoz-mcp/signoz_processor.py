import json
import logging
import re
from datetime import datetime, timedelta, timezone

import requests
from dateutil import parser as dateparser

logger = logging.getLogger(__name__)

class SignozApiProcessor:
    def __init__(self, signoz_host, signoz_api_key=None, ssl_verify="true"):
        self.__host = signoz_host
        self.__api_key = signoz_api_key
        self.__ssl_verify = not (ssl_verify and ssl_verify.lower() == "false")
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.__api_key:
            self.headers["SIGNOZ-API-KEY"] = f"{self.__api_key}"

    def test_connection(self):
        # Try multiple common health endpoints
        health_endpoints = [
            "/api/v1/health",
            "/api/v1/version", 
            "/api/v2/health",
            "/api/v3/health",
            "/api/v4/health",
            "/health",
            "/ping"
        ]
        
        last_error = None
        for endpoint in health_endpoints:
            try:
                url = f"{self.__host}{endpoint}"
                logger.info(f"Trying endpoint: {url}")
                response = requests.get(url, headers=self.headers, verify=self.__ssl_verify, timeout=20)
                logger.info(f"Response from {endpoint}: Status={response.status_code}, Text={response.text[:200]}")
                
                if response and response.status_code == 200:
                    logger.info(f"Successfully connected using endpoint: {endpoint}")
                    return True
                    
            except Exception as e:
                logger.warning(f"Failed to connect to {endpoint}: {e}")
                last_error = e
                continue
        
        # If all endpoints failed, try to get more info about the server
        try:
            base_url = f"{self.__host}"
            response = requests.get(base_url, headers=self.headers, verify=self.__ssl_verify, timeout=20)
            logger.info(f"Base URL response: Status={response.status_code}, Text={response.text[:200]}")
        except Exception as e:
            logger.warning(f"Could not reach base URL: {e}")
        
        raise Exception(f"Failed to connect to Signoz. Tried endpoints: {health_endpoints}. Last error: {last_error}")

    def fetch_dashboards(self):
        try:
            url = f"{self.__host}/api/v1/dashboards"
            response = requests.get(url, headers=self.headers, verify=self.__ssl_verify, timeout=60)
            logger.debug(f"Dashboard fetch response: {response}")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch dashboards: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Exception when fetching dashboards: {e}")
            raise e

    def fetch_dashboard_details(self, dashboard_id):
        try:
            url = f"{self.__host}/api/v1/dashboards/{dashboard_id}"
            response = requests.get(url, headers=self.headers, verify=self.__ssl_verify, timeout=30)

            if response.status_code == 200:
                response_data = response.json()
                return response_data.get("data", response_data)
            else:
                logger.error(f"Failed to fetch dashboard details: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Exception when fetching dashboard details: {e}")
            raise e

    def fetch_services(self, start_time=None, end_time=None, duration=None):
        start_dt, end_dt = self._get_time_range(start_time, end_time, duration, default_hours=24)
        start_ns = int(start_dt.timestamp() * 1_000_000_000)
        end_ns = int(end_dt.timestamp() * 1_000_000_000)

        try:
            url = f"{self.__host}/api/v1/services"
            payload = {"start": str(start_ns), "end": str(end_ns), "tags": []}
            response = requests.post(url, headers=self.headers, json=payload, verify=self.__ssl_verify, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch services: {response.status_code} - {response.text}")
                return {"status": "error", "message": f"Failed to fetch services: {response.status_code}", "details": response.text}
        except Exception as e:
            logger.error(f"Exception when fetching services: {e}")
            return {"status": "error", "message": str(e)}

    def _post_query_range(self, payload):
        url = f"{self.__host}/api/v4/query_range"
        logger.debug(f"Querying: {payload}")
        logger.debug(f"URL: {url}")
        try:
            response = requests.post(url, headers=self.headers, json=payload, verify=self.__ssl_verify, timeout=30)
            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    logger.debug(f"Response JSON: {resp_json}")
                    return resp_json
                except Exception as e:
                    logger.error(f"Failed to parse JSON: {e}, response text: {response.text}")
                    return {"error": f"Failed to parse JSON: {e}", "raw_response": response.text}
            else:
                logger.error(f"Failed to query metrics: {response.status_code} - {response.text}")
                return {"error": f"HTTP {response.status_code}", "raw_response": response.text}
        except Exception as e:
            logger.error(f"Exception when posting to query_range: {e}")
            raise e

    def fetch_dashboard_data(self, dashboard_name, start_time=None, end_time=None, step=None, variables_json=None, duration=None):
        start_dt, end_dt = self._get_time_range(start_time, end_time, duration, default_hours=3)
        from_time = int(start_dt.timestamp() * 1000)
        to_time = int(end_dt.timestamp() * 1000)

        try:
            dashboards = self.fetch_dashboards()
            if not dashboards or "data" not in dashboards:
                return {"status": "error", "message": "No dashboards found"}

            dashboard_id = None
            for d in dashboards["data"]:
                dashboard_data = d.get("data", {})
                if dashboard_data.get("title") == dashboard_name:
                    dashboard_id = d.get("id")
                    break

            if not dashboard_id:
                return {"status": "error", "message": f"Dashboard '{dashboard_name}' not found"}

            dashboard_details = self.fetch_dashboard_details(dashboard_id)
            if not dashboard_details:
                return {"status": "error", "message": f"Dashboard details not found for '{dashboard_name}'"}

            panels = dashboard_details.get("data", {}).get("widgets", [])
            if not panels:
                return {"status": "error", "message": f"No panels found in dashboard '{dashboard_name}'"}

            variables = {}
            if variables_json:
                try:
                    variables = json.loads(variables_json)
                    if not isinstance(variables, dict):
                        variables = {}
                except Exception:
                    variables = {}

            global_step = step if step is not None else 60
            query_builder = SignozDashboardQueryBuilder(global_step, variables)
            panel_results = {}

            for panel in panels:
                panel_title = panel.get("title") or f"Panel_{panel.get('id', '')}"
                panel_type = panel.get("panelTypes") or panel.get("panelType") or panel.get("type") or "graph"
                queries = []

                if (
                    isinstance(panel.get("query"), dict)
                    and panel["query"].get("queryType") == "builder"
                    and isinstance(panel["query"].get("builder"), dict)
                    and isinstance(panel["query"]["builder"].get("queryData"), list)
                ):
                    queries = panel["query"]["builder"]["queryData"]

                if not queries:
                    panel_results[panel_title] = {"status": "skipped", "message": "No builder queries in panel"}
                    continue

                built_queries = {}
                for query_data in queries:
                    if not isinstance(query_data, dict):
                        continue
                    letter, query_dict = query_builder.build_query_dict(query_data)
                    built_queries[letter] = query_dict

                if not built_queries:
                    panel_results[panel_title] = {"status": "skipped", "message": "No valid builder queries in panel"}
                    continue

                payload = query_builder.build_panel_payload(panel_type, built_queries, from_time, to_time)
                try:
                    result = self._post_query_range(payload)
                    panel_results[panel_title] = {"status": "success", "data": result}
                except Exception as e:
                    panel_results[panel_title] = {"status": "error", "message": str(e)}

            return {"status": "success", "dashboard": dashboard_name, "results": panel_results}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def fetch_apm_metrics(self, service_name, start_time=None, end_time=None, window="1m", operation_names=None, metrics=None, duration=None):
        start_dt, end_dt = self._get_time_range(start_time, end_time, duration, default_hours=3)
        from_time = int(start_dt.timestamp() * 1000)
        to_time = int(end_dt.timestamp() * 1000)
        step_val = self._parse_step(window)

        if not metrics:
            metrics = ["request_rate", "error_rate", "latency_avg"]

        builder_queries = {}
        query_name_counter = 65  # ASCII 'A'

        for metric_key in metrics:
            if metric_key == "latency_avg":
                for subkey, template in APM_METRIC_QUERIES["latency"].items():
                    import copy
                    q = copy.deepcopy(template)
                    q["stepInterval"] = step_val

                    filters = [
                        {
                            "key": {"key": "service.name", "dataType": "string", "isColumn": False, "type": "resource"},
                            "op": "IN",
                            "value": [service_name],
                        }
                    ]
                    if operation_names:
                        filters.append(
                            {
                                "key": {"key": "operation", "dataType": "string", "isColumn": False, "type": "tag"},
                                "op": "IN",
                                "value": operation_names,
                            }
                        )
                    if subkey in ("sum", "count"):
                        q["filters"] = {"items": filters, "op": "AND"}
                    q["queryName"] = q.get("expression")
                    builder_queries[q["queryName"]] = q

            elif metric_key in APM_METRIC_QUERIES:
                import copy
                q = copy.deepcopy(APM_METRIC_QUERIES[metric_key])
                q["stepInterval"] = step_val
                filters = [
                    {"key": {"key": "service.name", "dataType": "string", "isColumn": False, "type": "resource"}, "op": "IN", "value": [service_name]}
                ]
                if operation_names:
                    filters.append(
                        {"key": {"key": "operation", "dataType": "string", "isColumn": False, "type": "tag"}, "op": "IN", "value": operation_names}
                    )
                q["filters"] = {"items": filters, "op": "AND"}
                q["queryName"] = chr(query_name_counter)
                query_name_counter += 1
                builder_queries[q["queryName"]] = q

        payload = {
            "start": from_time,
            "end": to_time,
            "step": step_val,
            "variables": {},
            "compositeQuery": {"queryType": "builder", "panelType": "graph", "builderQueries": builder_queries},
        }
        return self._post_query_range(payload)

    def execute_clickhouse_query_tool(self, query, time_geq, time_lt, panel_type="table", fill_gaps=False, step=60):
        from_time = int(time_geq * 1000)
        to_time = int(time_lt * 1000)
        payload = {
            "start": from_time,
            "end": to_time,
            "step": step,
            "variables": {},
            "formatForWeb": True,
            "compositeQuery": {
                "queryType": "clickhouse_sql",
                "panelType": panel_type,
                "fillGaps": fill_gaps,
                "chQueries": {
                    "A": {
                        "name": "A",
                        "legend": "",
                        "disabled": False,
                        "query": query,
                    }
                },
            },
        }
        return self._post_query_range(payload)

    def execute_builder_query_tool(self, builder_queries, time_geq, time_lt, panel_type="table", step=60):
        from_time = int(time_geq * 1000)
        to_time = int(time_lt * 1000)
        payload = {
            "start": from_time,
            "end": to_time,
            "step": step,
            "variables": {},
            "compositeQuery": {
                "queryType": "builder",
                "panelType": panel_type,
                "builderQueries": builder_queries,
            },
        }
        return self._post_query_range(payload)

    def _get_time_range(self, start_time=None, end_time=None, duration=None, default_hours=3):
        now_dt = datetime.now(timezone.utc)
        if start_time and end_time:
            start_dt = self._parse_time(start_time)
            end_dt = self._parse_time(end_time)
            if not start_dt or not end_dt:
                start_dt = now_dt - timedelta(hours=default_hours)
                end_dt = now_dt
        elif duration:
            dur_ms = self._parse_duration(duration)
            if dur_ms is None:
                dur_ms = default_hours * 60 * 60 * 1000
            start_dt = now_dt - timedelta(milliseconds=dur_ms)
            end_dt = now_dt
        else:
            start_dt = now_dt - timedelta(hours=default_hours)
            end_dt = now_dt
        return start_dt, end_dt

    def _parse_step(self, step):
        if isinstance(step, int):
            return step
        if isinstance(step, str):
            match = re.match(r"^(\d+)([smhd])$", step)
            if match:
                value, unit = match.groups()
                value = int(value)
                if unit == "s":
                    return value
                elif unit == "m":
                    return value * 60
                elif unit == "h":
                    return value * 3600
                elif unit == "d":
                    return value * 86400
            else:
                try:
                    return int(step)
                except Exception:
                    logger.error(f"Failed to parse step: {step}")
                    pass
        return 60

    def _parse_duration(self, duration_str):
        if not duration_str or not isinstance(duration_str, str):
            return None
        match = re.match(r"^(\d+)([hm])$", duration_str.strip().lower())
        if match:
            value, unit = match.groups()
            value = int(value)
            if unit == "h":
                return value * 60 * 60 * 1000
            elif unit == "m":
                return value * 60 * 1000
        try:
            value = int(duration_str)
            return value * 60 * 1000
        except Exception as e:
            logger.error(f"_parse_duration: Exception parsing '{duration_str}': {e}")
        return None

    def _parse_time(self, time_str):
        if not time_str or not isinstance(time_str, str):
            logger.error(f"_parse_time: Invalid input (not a string): {time_str}")
            return None
        time_str_orig = time_str
        time_str = time_str.strip().lower()
        if time_str.startswith("now"):
            if "-" in time_str:
                match = re.match(r"now-(\d+)([smhd])", time_str)
                if match:
                    value, unit = match.groups()
                    value = int(value)
                    if unit == "s":
                        delta = timedelta(seconds=value)
                    elif unit == "m":
                        delta = timedelta(minutes=value)
                    elif unit == "h":
                        delta = timedelta(hours=value)
                    elif unit == "d":
                        delta = timedelta(days=value)
                    else:
                        delta = timedelta()
                    logger.debug(f"_parse_time: Parsed relative time '{time_str_orig}' as now - {value}{unit}")
                    return datetime.now(timezone.utc) - delta
            logger.debug(f"_parse_time: Parsed 'now' as current UTC time for input '{time_str_orig}'")
            return datetime.now(timezone.utc)
        else:
            try:
                dt = dateparser.parse(time_str_orig)
                if dt is None:
                    logger.error(f"_parse_time: dateparser.parse returned None for input '{time_str_orig}'")
                    return None
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                logger.debug(f"_parse_time: Successfully parsed '{time_str_orig}' as {dt.isoformat()}")
                return dt.astimezone(timezone.utc)
            except Exception as e:
                logger.error(f"_parse_time: Exception parsing '{time_str_orig}': {e}")
                return None

# Dashboard Query Builder
class SignozDashboardQueryBuilder:
    def __init__(self, global_step, variables):
        self.global_step = global_step
        self.variables = variables
        self.query_letter_ord = ord("A")

    def _get_next_query_letter(self):
        letter = chr(self.query_letter_ord)
        self.query_letter_ord += 1
        if self.query_letter_ord > ord("Z"):
            self.query_letter_ord = ord("A")
        return letter

    def build_query_dict(self, query_data):
        query_dict = dict(query_data)
        current_letter = self._get_next_query_letter()
        query_dict.pop("step_interval", None)
        query_dict["stepInterval"] = self.global_step
        if "group_by" in query_dict:
            query_dict["groupBy"] = query_dict.pop("group_by")
        query_dict["queryName"] = current_letter
        query_dict["expression"] = current_letter
        query_dict["disabled"] = query_dict.get("disabled", False)
        if query_dict.get("dataSource") == "metrics":
            query_dict["pageSize"] = 10
        return current_letter, query_dict

    def build_panel_payload(self, panel_type, panel_queries, start_time, end_time):
        def to_ms(ts):
            return int(ts * 1000) if ts < 1e12 else int(ts)

        payload = {
            "start": to_ms(start_time),
            "end": to_ms(end_time),
            "step": self.global_step,
            "variables": self.variables,
            "formatForWeb": False,
            "compositeQuery": {
                "queryType": "builder",
                "panelType": panel_type,
                "fillGaps": False,
                "builderQueries": panel_queries,
            },
        }
        return json.loads(json.dumps(payload, ensure_ascii=False, indent=None))

# APM Metric Query Templates
APM_METRIC_QUERIES = {
    "request_rate": {
        "dataSource": "metrics",
        "aggregateOperator": "sum_rate",
        "aggregateAttribute": {"key": "signoz_latency.count", "dataType": "float64", "isColumn": True, "type": ""},
        "timeAggregation": "rate",
        "spaceAggregation": "sum",
        "functions": [],
        "filters": None,
        "expression": "A",
        "disabled": False,
        "stepInterval": None,
        "having": [],
        "limit": None,
        "orderBy": [],
        "groupBy": [],
        "legend": "Request Rate",
        "reduceTo": "avg",
    },
    "error_rate": {
        "dataSource": "metrics",
        "aggregateOperator": "sum_rate",
        "aggregateAttribute": {"key": "signoz_errors.count", "dataType": "float64", "isColumn": True, "type": ""},
        "timeAggregation": "rate",
        "spaceAggregation": "sum",
        "functions": [],
        "filters": None,
        "expression": "B",
        "disabled": False,
        "stepInterval": None,
        "having": [],
        "limit": None,
        "orderBy": [],
        "groupBy": [],
        "legend": "Error Rate",
        "reduceTo": "avg",
    },
    "latency": {
        "sum": {
            "dataSource": "metrics",
            "aggregateOperator": "sum",
            "aggregateAttribute": {"key": "signoz_latency.sum", "dataType": "float64", "isColumn": True, "type": ""},
            "timeAggregation": "sum",
            "spaceAggregation": "sum",
            "functions": [],
            "filters": None,
            "expression": "C",
            "disabled": False,
            "stepInterval": None,
            "having": [],
            "limit": None,
            "orderBy": [],
            "groupBy": [],
            "legend": "Latency Sum",
            "reduceTo": "avg",
        },
        "count": {
            "dataSource": "metrics",
            "aggregateOperator": "sum",
            "aggregateAttribute": {"key": "signoz_latency.count", "dataType": "float64", "isColumn": True, "type": ""},
            "timeAggregation": "sum",
            "spaceAggregation": "sum",
            "functions": [],
            "filters": None,
            "expression": "D",
            "disabled": False,
            "stepInterval": None,
            "having": [],
            "limit": None,
            "orderBy": [],
            "groupBy": [],
            "legend": "Latency Count",
            "reduceTo": "avg",
        },
        "avg": {
            "dataSource": "metrics",
            "aggregateOperator": "divide",
            "aggregateAttribute": {"key": "signoz_latency.sum", "dataType": "float64", "isColumn": True, "type": ""},
            "timeAggregation": "avg",
            "spaceAggregation": "avg",
            "functions": [],
            "filters": None,
            "expression": "C/D",
            "disabled": False,
            "stepInterval": None,
            "having": [],
            "limit": None,
            "orderBy": [],
            "groupBy": [],
            "legend": "Latency Avg",
            "reduceTo": "avg",
        },
    },
}

# Example usage:
#
# processor = SignozApiProcessor(
#     signoz_host="https://your-signoz-instance.com",
#     signoz_api_key="your-api-key",  # optional
#     ssl_verify="true"
# )
#
# # Test connection
# processor.test_connection()
#
# # Fetch services
# services = processor.fetch_services(duration="24h")
#
# # Fetch APM metrics
# metrics = processor.fetch_apm_metrics(
#     service_name="your-service",
#     duration="3h",
#     window="1m"
# )
#
# # Execute custom queries
# result = processor.execute_clickhouse_query_tool(
#     query="SELECT * FROM your_table LIMIT 10",
#     time_geq=start_timestamp,
#     time_lt=end_timestamp
# )