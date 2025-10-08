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

def download_latest_artifact_to_js_dist():
    DEST_DIR = os.path.join(os.path.dirname(__file__), "js", "dist")
    os.makedirs(DEST_DIR, exist_ok=True)
    zip_resp = requests.get(
        f"https://nightly.link/Tangerie/ComfyUI_CozyGen/workflows/build/master/artifact.zip"
    )
    if zip_resp.ok:
        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as z:
            z.extractall(DEST_DIR)
            print(DEST_DIR)
# Call artifact download before handler definition
download_latest_artifact_to_js_dist()
# --- End artifact block ---

# Mount API routes
for route in api_routes:
    server.PromptServer.instance.app.router.add_route(
        route.method,
        route.path,
        route.handler,
        name=f"cozygen_{route.handler.__name__}"
    )

# Handler to serve the React app's index.html
async def serve_cozygen_app(request: web.Request) -> web.Response:
    index_path = os.path.join(os.path.dirname(__file__), "js", "dist", "index.html")
    if not os.path.exists(index_path):
        return web.Response(text="CozyGen: Build not found. Please run `npm run build` in the `js` directory.", status=500)
    return web.FileResponse(index_path)

# Route to serve the main application
server.PromptServer.instance.app.router.add_get('/cozygen', serve_cozygen_app)
server.PromptServer.instance.app.router.add_get('/cozygen/', serve_cozygen_app)

# Serve the new 'dist' directory which contains the built React app
static_dist_path = os.path.join(os.path.dirname(__file__), "js", "dist")
server.PromptServer.instance.app.router.add_static(
    "/cozygen/assets", path=os.path.join(static_dist_path, "assets"), name="cozygen_assets"
)

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

print("â CozyGen API routes mounted.")
print("â CozyGen web UI served at /cozygen/")

WEB_DIRECTORY = "./js/web"


