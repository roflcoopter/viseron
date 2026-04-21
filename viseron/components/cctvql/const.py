"""Constants for the cctvQL Viseron component."""

COMPONENT = "cctvql"

CONFIG_HOST = "host"
CONFIG_PORT = "port"
CONFIG_API_KEY = "api_key"
CONFIG_SCAN_INTERVAL = "scan_interval"
CONFIG_AUTO_ENRICH = "auto_enrich"

DESC_HOST = "Hostname or IP of the cctvQL server"
DESC_PORT = "Port the cctvQL REST API listens on"
DESC_API_KEY = "Optional API key (set CCTVQL_API_KEY on the cctvQL server to enable)"
DESC_SCAN_INTERVAL = "How often (seconds) to poll cctvQL for events"
DESC_AUTO_ENRICH = "Automatically query cctvQL when Viseron detects an object"

DEFAULT_PORT = 8000
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_AUTO_ENRICH = False
