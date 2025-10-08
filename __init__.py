import os
import sys
import server
from aiohttp import web # Import web for static files
from .api import routes as api_routes
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# --- Artifact download before handler definition ---
import requests
import zipfile
import io

FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "js", "dist")
def download_latest_artifact_to_js_dist():
    os.makedirs(FRONTEND_PATH, exist_ok=True)
    zip_resp = requests.get(
        f"https://nightly.link/Tangerie/ComfyUI_CozyGen/workflows/build/master/artifact.zip"
    )
    if zip_resp.ok:
        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as z:
            z.extractall(FRONTEND_PATH)

# Call artifact download before handler definition
if not os.path.isdir(FRONTEND_PATH): 
    download_latest_artifact_to_js_dist()
# --- End artifact block ---

async def serve_cozygen_app(request: web.Request) -> web.Response:
    index_path = os.path.join(FRONTEND_PATH, "index.html")
    if not os.path.exists(index_path):
        return web.Response(text="CozyGen: Build not found. Please run `npm run build` in the `js` directory.", status=500)
    return web.FileResponse(index_path)

try:
    # Mount API routes
    for route in api_routes:
        server.PromptServer.instance.app.router.add_route(
            route.method,
            route.path,
            route.handler,
            name=f"cozygen_{route.handler.__name__}"
        )
        
    # Route to serve the main application
    server.PromptServer.instance.app.router.add_get('/cozygen', serve_cozygen_app)
    server.PromptServer.instance.app.router.add_get('/cozygen/', serve_cozygen_app)

    # Serve the new 'dist' directory which contains the built React app
    server.PromptServer.instance.app.router.add_static(
        "/cozygen/assets", path=os.path.join(FRONTEND_PATH, "assets"), name="cozygen_assets"
    )
except:
    pass


__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

print("â CozyGen API routes mounted.")
print("â CozyGen web UI served at /cozygen/")

WEB_DIRECTORY = "./js/web"