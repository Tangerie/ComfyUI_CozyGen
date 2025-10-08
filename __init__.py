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
    OWNER = "Tangerie"
    REPO = "ComfyUI_CozyGen"
    BRANCH = "master"
    DEST_DIR = os.path.join(os.path.dirname(__file__), "js", "dist")

    # Get workflows (assume only one)
    wf_resp = requests.get(f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows")
    print(f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows")
    if wf_resp.ok:
        print(wf_resp.json())
        workflows = wf_resp.json().get("workflows", [])
        if workflows:
            workflow_path = workflows[0]["path"]
            print(f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{workflow_path}/runs")
            # Get latest successful run
            run_resp = requests.get(
                f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{workflow_path}/runs",
                params={
                    "per_page": 1,
                    "branch": BRANCH,
                    "event": "push",
                    "status": "success",
                }
            )
            if run_resp.ok:
                print(run_resp.json())
                runs = run_resp.json().get("workflow_runs", [])
                if runs:
                    run_id = runs[0]["id"]
                    # Get artifacts
                    art_resp = requests.get(
                        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs/{run_id}/artifacts"
                    )
                    if art_resp.ok:
                        artifacts = art_resp.json().get("artifacts", [])
                        if artifacts:
                            artifact_id = artifacts[0]["id"]
                            # Download artifact ZIP
                            zip_resp = requests.get(
                                f"https://api.github.com/repos/{OWNER}/{REPO}/actions/artifacts/{artifact_id}/zip"
                            )
                            if zip_resp.ok:
                                with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as z:
                                    os.makedirs(DEST_DIR, exist_ok=True)
                                    z.extractall(DEST_DIR)
                                print(f"✅ Downloaded and extracted latest artifact to {DEST_DIR}/")
                            else:
                                print("❌ Failed to download artifact ZIP.")
                        else:
                            print("❌ No artifacts found for run.")
                    else:
                        print("❌ Failed to get artifacts for run.")
                else:
                    print("❌ No successful workflow runs found.")
            else:
                print("❌ Failed to get workflow runs.")
        else:
            print("❌ No workflows found for repository.")
    else:
        print("❌ Failed to get workflows from GitHub.")

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

print("✅ CozyGen API routes mounted.")
print("✅ CozyGen web UI served at /cozygen/")

WEB_DIRECTORY = "./js/web"

