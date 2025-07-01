
from api.mock_routes import app
import json

openapi_schema = app.openapi()
with open("openapi.json", "w") as f:
    json.dump(openapi_schema, f)
