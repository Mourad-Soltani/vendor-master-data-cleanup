"""Runtime configuration constants.

Author: Mourad.Soltani
"""

PROJECT_NAME = "Vendor Master Data Cleanup"
VERSION = "1.0.0"
AUTHOR = "Mourad.Soltani"
SIGNATURE = "Mourad.Soltani"

# Request body cap sized for enterprise vendor lists (bulk uploads of ~500 records).
MAX_CONTENT_LENGTH = 512 * 1024  # 512 KB

# Upper bound on vendors per dedupe request (n^2 pair scan).
MAX_VENDORS_PER_REQUEST = 500
