import os
import sys

# Assume the app is located in the same directory
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.append(path)

# Load environment variables, PythonAnywhere runs this script differently
from dotenv import load_dotenv
load_dotenv(os.path.join(path, '.env'))

from main import app as fastapi_app
from a2wsgi import ASGIMiddleware

# Convert FastAPI ASGI application to WSGI for PythonAnywhere
application = ASGIMiddleware(fastapi_app)
