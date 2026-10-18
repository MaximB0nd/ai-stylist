import asyncio
from datetime import datetime, timedelta, timezone


async def list_objects(storage, prefix: str) -> list[dict]:
    items = []
    continuation = None
    while True:
        args = {"Bucket": storage.settings.bucket, "Prefix": prefix}
        if continuation:
            args["ContinuationToken"] = continuation
        page = await asyncio.to_thread(storage.client.list_objects_v2, **args)
        items.extend(page.get("Contents", []))
        continuation = page.get("NextContinuationToken")
        if not continuation:
            return items

async def cleanup_expired(storage) -> None:
    now = datetime.now(timezone.utc)
    referenced = set()
    async with storage.lock:
        for item in await list_objects(storage, "state/"):
            artifact_id = item["Key"].removeprefix("state/").removesuffix(".json")
            state = await storage.get_state(artifact_id)
            if state is None:
                continue
            blob_key = state.get("blob_key")
            if artifact_id in storage.active or datetime.fromisoformat(state["expires_at"]) > now:
                if blob_key:
                    referenced.add(blob_key)
                continue
            if blob_key:
                await storage.delete_object(blob_key)
            await storage.delete_object(storage.state_key(artifact_id))
        orphan_cutoff = now - timedelta(hours=1)
        for item in await list_objects(storage, "staging/"):
            if item["Key"] not in referenced and item["LastModified"] < orphan_cutoff:
                await storage.delete_object(item["Key"])
        uploads = await asyncio.to_thread(storage.client.list_multipart_uploads, Bucket=storage.settings.bucket)
        for upload in uploads.get("Uploads", []):
            if upload["Initiated"] < orphan_cutoff:
                await asyncio.to_thread(
                    storage.client.abort_multipart_upload,
                    Bucket=storage.settings.bucket,
                    Key=upload["Key"],
                    UploadId=upload["UploadId"],
                )
