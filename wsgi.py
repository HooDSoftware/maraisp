import os
import sys
import asyncio

# Assume the app is located in the same directory
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.append(path)

# Load environment variables, PythonAnywhere runs this script differently
from dotenv import load_dotenv
load_dotenv(os.path.join(path, '.env'))

# Ensure there is an event loop available in the main thread for ASGI conversion
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from main import app as fastapi_app
from a2wsgi import ASGIMiddleware

# Convert FastAPI ASGI application to WSGI for PythonAnywhere
application = ASGIMiddleware(fastapi_app)
