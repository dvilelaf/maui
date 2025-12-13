import os
import json
import urllib.request
import urllib.error
import sys


def deploy():
    # Load env vars (assuming they are loaded by the runner or .env is sourced)
    # In justfile we use 'set dotenv-load', so they should be available.

    url = os.getenv("PORTAINER_URL")
    token = os.getenv("PORTAINER_API_TOKEN")
    stack_id = os.getenv("STACK_ID")
    endpoint_id = os.getenv("ENDPOINT_ID", "1")  # Default to 1

    if not all([url, token, stack_id]):
        print("ERROR: Missing configuration. Please define in .env:")
        if not url:
            print("  - PORTAINER_URL (e.g. https://portainer.example.com)")
        if not token:
            print("  - PORTAINER_API_TOKEN")
        if not stack_id:
            print("  - STACK_ID")
        sys.exit(1)

    # Clean URL and ensure protocol
    url = url.rstrip("/")
    if not url.startswith("http"):
        url = f"https://{url}"

    headers = {"X-API-Key": token, "Content-Type": "application/json"}

    print(f"Deploying Stack {stack_id} to {url} (Endpoint {endpoint_id})...")

    # 1. Check Stack Info to determine type (Git vs Manual)
    try:
        req = urllib.request.Request(f"{url}/api/stacks/{stack_id}", headers=headers)
        with urllib.request.urlopen(req) as response:
            stack_data = json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"ERROR: Failed to get stack info: {e.code} {e.reason}")
        print(e.read().decode())
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Error connecting to Portainer: {e}")
        sys.exit(1)

    # 2. Trigger Redeploy
    try:
        # Check if Git-based
        if stack_data.get("GitConfig") or stack_data.get("AutoUpdate"):
            print("Detected Git-synced stack. Triggering Git Redeploy...")
            endpoint = (
                f"{url}/api/stacks/{stack_id}/git/redeploy?endpointId={endpoint_id}"
            )
            payload = {"pullImage": True, "prune": False}
        else:
            # Manual/File based
            print("Detected Manual/File stack. Triggering Update with Pull...")
            endpoint = f"{url}/api/stacks/{stack_id}?endpointId={endpoint_id}"

            # For manual stacks, we read the LOCAL docker-compose.yml to force an update
            # of the definition in Portainer.
            try:
                with open("docker-compose.yml", "r") as f:
                    stack_file_content = f.read()
                    print(
                        "   Read local docker-compose.yml to update remote stack definition."
                    )
            except FileNotFoundError:
                print("ERROR: Could not find docker-compose.yml in current directory.")
                sys.exit(1)

            payload = {
                "stackFileContent": stack_file_content,
                "env": stack_data.get("Env", []),
                "prune": False,
                "pullImage": True,
            }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST" if "git/redeploy" in endpoint else "PUT",
        )
        with urllib.request.urlopen(req) as response:
            json.loads(response.read().decode())
            print("Deployment successful!")

    except urllib.error.HTTPError as e:
        print(f"ERROR: Deployment failed: {e.code} {e.reason}")
        print(e.read().decode())
        sys.exit(1)


if __name__ == "__main__":
    deploy()
