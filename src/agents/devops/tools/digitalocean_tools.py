"""DigitalOcean tools for the DevOps agent."""
from __future__ import annotations

from src.agents.devops.tools import devops_tool
from src.agents.devops.tools._http import do_client, json_block, text_block


def _token() -> str:
    from config.settings import settings

    if not settings.DIGITALOCEAN_TOKEN:
        raise RuntimeError(
            "DIGITALOCEAN_TOKEN is not set; the DigitalOcean tools cannot be used."
        )
    return settings.DIGITALOCEAN_TOKEN


# ---- Read-only -------------------------------------------------------------


@devops_tool(
    server="do",
    name="do_list_droplets",
    description="List DigitalOcean droplets in the account.",
    input_schema={"type": "object", "properties": {}},
    read_only=True,
)
async def do_list_droplets(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.get("/droplets")
        r.raise_for_status()
        droplets = [
            {
                "id": d["id"],
                "name": d["name"],
                "status": d["status"],
                "region": d["region"]["slug"],
                "size": d["size_slug"],
                "ip": next((n["ip_address"] for n in d["networks"]["v4"] if n["type"] == "public"), None),
            }
            for d in r.json().get("droplets", [])
        ]
        return json_block(droplets)


@devops_tool(
    server="do",
    name="do_get_droplet",
    description="Get details for one droplet.",
    input_schema={
        "type": "object",
        "properties": {"droplet_id": {"type": "integer"}},
        "required": ["droplet_id"],
    },
    read_only=True,
)
async def do_get_droplet(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.get(f"/droplets/{args['droplet_id']}")
        r.raise_for_status()
        return json_block(r.json().get("droplet"))


@devops_tool(
    server="do",
    name="do_list_apps",
    description="List App Platform apps.",
    input_schema={"type": "object", "properties": {}},
    read_only=True,
)
async def do_list_apps(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.get("/apps")
        r.raise_for_status()
        apps = [
            {"id": a["id"], "name": a["spec"]["name"], "live_url": a.get("live_url")}
            for a in r.json().get("apps", [])
        ]
        return json_block(apps)


@devops_tool(
    server="do",
    name="do_get_app",
    description="Get details (including spec and active deployment) for an App Platform app.",
    input_schema={
        "type": "object",
        "properties": {"app_id": {"type": "string"}},
        "required": ["app_id"],
    },
    read_only=True,
)
async def do_get_app(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.get(f"/apps/{args['app_id']}")
        r.raise_for_status()
        return json_block(r.json().get("app"))


@devops_tool(
    server="do",
    name="do_get_app_logs",
    description="Get a log download URL for an App Platform deployment component.",
    input_schema={
        "type": "object",
        "properties": {
            "app_id": {"type": "string"},
            "deployment_id": {"type": "string"},
            "component_name": {"type": "string"},
            "type": {
                "type": "string",
                "enum": ["BUILD", "DEPLOY", "RUN"],
                "default": "RUN",
            },
        },
        "required": ["app_id", "deployment_id", "component_name"],
    },
    read_only=True,
)
async def do_get_app_logs(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.get(
            f"/apps/{args['app_id']}/deployments/{args['deployment_id']}"
            f"/components/{args['component_name']}/logs",
            params={"type": args.get("type", "RUN")},
        )
        r.raise_for_status()
        return json_block(r.json())


@devops_tool(
    server="do",
    name="do_list_databases",
    description="List managed database clusters.",
    input_schema={"type": "object", "properties": {}},
    read_only=True,
)
async def do_list_databases(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.get("/databases")
        r.raise_for_status()
        dbs = [
            {
                "id": d["id"],
                "name": d["name"],
                "engine": d["engine"],
                "size": d["size"],
                "region": d["region"],
                "status": d["status"],
            }
            for d in r.json().get("databases", [])
        ]
        return json_block(dbs)


@devops_tool(
    server="do",
    name="do_get_database",
    description="Get details for one managed database cluster.",
    input_schema={
        "type": "object",
        "properties": {"database_id": {"type": "string"}},
        "required": ["database_id"],
    },
    read_only=True,
)
async def do_get_database(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.get(f"/databases/{args['database_id']}")
        r.raise_for_status()
        return json_block(r.json().get("database"))


@devops_tool(
    server="do",
    name="do_list_kubernetes_clusters",
    description="List DigitalOcean Kubernetes clusters.",
    input_schema={"type": "object", "properties": {}},
    read_only=True,
)
async def do_list_kubernetes_clusters(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.get("/kubernetes/clusters")
        r.raise_for_status()
        clusters = [
            {
                "id": k["id"],
                "name": k["name"],
                "region": k["region"],
                "version": k["version"],
                "status": k["status"]["state"],
            }
            for k in r.json().get("kubernetes_clusters", [])
        ]
        return json_block(clusters)


@devops_tool(
    server="do",
    name="do_get_kubeconfig",
    description=(
        "Fetch the kubeconfig for a Kubernetes cluster. The agent will see "
        "only a redacted summary; do not print or echo the full file."
    ),
    input_schema={
        "type": "object",
        "properties": {"cluster_id": {"type": "string"}},
        "required": ["cluster_id"],
    },
    read_only=True,
)
async def do_get_kubeconfig(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.get(f"/kubernetes/clusters/{args['cluster_id']}/kubeconfig")
        r.raise_for_status()
        size = len(r.content)
        return text_block(
            f"Kubeconfig fetched for cluster {args['cluster_id']} ({size} bytes). "
            f"Stored in operator-side cache; not shown to agent."
        )


# ---- Mutating --------------------------------------------------------------


@devops_tool(
    server="do",
    name="do_create_droplet",
    description="Create a new droplet.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "region": {"type": "string", "default": "nyc3"},
            "size": {"type": "string", "default": "s-1vcpu-1gb"},
            "image": {"type": "string", "default": "ubuntu-22-04-x64"},
            "ssh_keys": {"type": "array", "items": {"type": "string"}},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name"],
    },
    read_only=False,
)
async def do_create_droplet(args: dict) -> dict:
    payload = {
        "name": args["name"],
        "region": args.get("region", "nyc3"),
        "size": args.get("size", "s-1vcpu-1gb"),
        "image": args.get("image", "ubuntu-22-04-x64"),
    }
    if "ssh_keys" in args:
        payload["ssh_keys"] = args["ssh_keys"]
    if "tags" in args:
        payload["tags"] = args["tags"]
    async with do_client(_token()) as c:
        r = await c.post("/droplets", json=payload)
        r.raise_for_status()
        d = r.json()["droplet"]
        return text_block(f"Created droplet {d['name']} (id={d['id']}).")


@devops_tool(
    server="do",
    name="do_destroy_droplet",
    description="Destroy a droplet. Irreversible.",
    input_schema={
        "type": "object",
        "properties": {"droplet_id": {"type": "integer"}},
        "required": ["droplet_id"],
    },
    read_only=False,
)
async def do_destroy_droplet(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.delete(f"/droplets/{args['droplet_id']}")
        r.raise_for_status()
        return text_block(f"Destroyed droplet {args['droplet_id']}.")


@devops_tool(
    server="do",
    name="do_droplet_action",
    description="Perform an action on a droplet (power_on, power_off, reboot, shutdown, snapshot).",
    input_schema={
        "type": "object",
        "properties": {
            "droplet_id": {"type": "integer"},
            "action": {
                "type": "string",
                "enum": ["power_on", "power_off", "reboot", "shutdown", "snapshot"],
            },
            "snapshot_name": {"type": "string"},
        },
        "required": ["droplet_id", "action"],
    },
    read_only=False,
)
async def do_droplet_action(args: dict) -> dict:
    body = {"type": args["action"]}
    if args["action"] == "snapshot" and "snapshot_name" in args:
        body["name"] = args["snapshot_name"]
    async with do_client(_token()) as c:
        r = await c.post(f"/droplets/{args['droplet_id']}/actions", json=body)
        r.raise_for_status()
        return text_block(f"Action {args['action']} initiated on {args['droplet_id']}.")


@devops_tool(
    server="do",
    name="do_create_deployment",
    description="Trigger a new deployment for an App Platform app.",
    input_schema={
        "type": "object",
        "properties": {
            "app_id": {"type": "string"},
            "force_build": {"type": "boolean", "default": False},
        },
        "required": ["app_id"],
    },
    read_only=False,
)
async def do_create_deployment(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.post(
            f"/apps/{args['app_id']}/deployments",
            json={"force_build": args.get("force_build", False)},
        )
        r.raise_for_status()
        dep = r.json().get("deployment", {})
        return text_block(f"Deployment {dep.get('id')} started for {args['app_id']}.")


@devops_tool(
    server="do",
    name="do_update_app_spec",
    description=(
        "Update the spec of an App Platform app. Pass the full spec object; "
        "DigitalOcean will create a new deployment from it."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "app_id": {"type": "string"},
            "spec": {"type": "object"},
        },
        "required": ["app_id", "spec"],
    },
    read_only=False,
)
async def do_update_app_spec(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.put(f"/apps/{args['app_id']}", json={"spec": args["spec"]})
        r.raise_for_status()
        return text_block(f"Updated spec for app {args['app_id']}.")


@devops_tool(
    server="do",
    name="do_resize_database",
    description="Resize a managed database cluster.",
    input_schema={
        "type": "object",
        "properties": {
            "database_id": {"type": "string"},
            "size": {"type": "string"},
            "num_nodes": {"type": "integer", "default": 1},
        },
        "required": ["database_id", "size"],
    },
    read_only=False,
)
async def do_resize_database(args: dict) -> dict:
    async with do_client(_token()) as c:
        r = await c.put(
            f"/databases/{args['database_id']}/resize",
            json={"size": args["size"], "num_nodes": args.get("num_nodes", 1)},
        )
        r.raise_for_status()
        return text_block(f"Resize requested for database {args['database_id']} -> {args['size']}.")
