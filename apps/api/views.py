import hashlib
import hmac
import json
import os
import urllib.request

from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "dtc-brightbean",
        "description": "DTC Commission — Social publishing dock for 10 platforms",
        "version": "1.0.0",
    },
    "servers": [
        {
            "url": "https://brightbean-studio-web-dtccommission-phase0.up.railway.app",
            "description": "Phase 0 (Railway)",
        },
    ],
    "paths": {
        "/api/webhooks/asset-received": {
            "post": {
                "operationId": "receiveAsset",
                "summary": "Inbound asset from Pencil / dtc-media-studio",
                "description": (
                    "Receives a rendered media asset, stores it in the workspace media library,"
                    " and creates a draft Post with PlatformPost entries for each connected"
                    " social account matching the requested platforms."
                    " HMAC-verified via X-Pencil-Signature header."
                ),
                "tags": ["webhooks"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["_type", "_id", "url", "workspace_id"],
                                "properties": {
                                    "_type": {"type": "string", "enum": ["mediaAsset"]},
                                    "_id": {
                                        "type": "string",
                                        "description": "Pencil asset identifier",
                                    },
                                    "url": {
                                        "type": "string",
                                        "format": "uri",
                                        "description": "Public URL of the rendered asset",
                                    },
                                    "workspace_id": {
                                        "type": "string",
                                        "format": "uuid",
                                        "description": "Brightbean workspace to create the draft in",
                                    },
                                    "city": {
                                        "type": "string",
                                        "description": "FIFA corridor city key (e.g. vancouver)",
                                    },
                                    "caption": {
                                        "type": "string",
                                        "description": "Post caption; auto-generated if omitted",
                                    },
                                    "platforms": {
                                        "type": "array",
                                        "items": {
                                            "type": "string",
                                            "enum": [
                                                "facebook",
                                                "instagram",
                                                "linkedin",
                                                "tiktok",
                                                "youtube",
                                                "pinterest",
                                                "threads",
                                                "bluesky",
                                                "mastodon",
                                                "google_business",
                                            ],
                                        },
                                    },
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Draft post created",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean"},
                                        "asset_id": {"type": "string"},
                                        "post_id": {"type": "string"},
                                        "draft_posts": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "platform": {"type": "string"},
                                                    "post_id": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "400": {"description": "Bad request"},
                    "401": {"description": "Invalid HMAC signature"},
                    "404": {"description": "Workspace not found"},
                    "502": {"description": "Failed to fetch asset from URL"},
                },
            }
        }
    },
    "tags": [
        {
            "name": "webhooks",
            "description": "Inbound webhooks from Pencil and dtc-media-studio",
        },
    ],
}

_MIME_TO_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "video/mp4": "mp4",
    "video/webm": "webm",
}


@require_http_methods(["GET"])
def openapi_spec(request):
    """Serve OpenAPI specification for service discovery."""
    response = JsonResponse(OPENAPI_SPEC)
    response["Cache-Control"] = "public, max-age=3600"
    response["Access-Control-Allow-Origin"] = "*"
    return response


@csrf_exempt
@require_http_methods(["POST"])
def asset_received(request):
    """Inbound webhook: rendered asset from Pencil / dtc-media-studio.

    1. Verify HMAC (X-Pencil-Signature: sha256=<hex>).
    2. Download asset from URL.
    3. Store in workspace MediaAsset (R2/S3 via Django storage).
    4. Create Post draft + PlatformPost entries for connected accounts.
    """
    # ── HMAC verification ────────────────────────────────────────────────
    secret = os.environ.get("PENCIL_WEBHOOK_SECRET", "")
    if secret:
        sig_header = request.headers.get("X-Pencil-Signature", "")
        expected = (
            "sha256="
            + hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
        )
        if not hmac.compare_digest(sig_header, expected):
            return JsonResponse({"error": "invalid signature"}, status=401)

    # ── Parse payload ────────────────────────────────────────────────────
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)

    required_fields = {"_type", "_id", "url", "workspace_id"}
    missing = required_fields - payload.keys()
    if missing:
        return JsonResponse({"error": f"missing fields: {sorted(missing)}"}, status=400)

    if payload["_type"] != "mediaAsset":
        return JsonResponse({"error": "unsupported _type"}, status=400)

    from apps.composer.models import Post, PlatformPost
    from apps.media_library.models import MediaAsset
    from apps.social_accounts.models import SocialAccount
    from apps.workspaces.models import Workspace

    # ── Resolve workspace ────────────────────────────────────────────────
    try:
        workspace = Workspace.objects.select_related("organization").get(
            id=payload["workspace_id"]
        )
    except (Workspace.DoesNotExist, ValueError):
        return JsonResponse({"error": "workspace not found"}, status=404)

    asset_url = payload["url"]
    city = payload.get("city", "")
    caption = payload.get("caption", "")
    platforms = payload.get("platforms", [])
    asset_id_str = payload["_id"]

    # ── Download asset ───────────────────────────────────────────────────
    try:
        req = urllib.request.Request(
            asset_url, headers={"User-Agent": "dtc-brightbean-webhook/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            content_type = (
                resp.headers.get("Content-Type", "image/png").split(";")[0].strip()
            )
    except Exception as exc:
        return JsonResponse({"error": f"asset fetch failed: {exc}"}, status=502)

    ext = _MIME_TO_EXT.get(content_type, "bin")
    filename = f"pencil-{asset_id_str}.{ext}"
    media_type = (
        MediaAsset.MediaType.VIDEO
        if content_type.startswith("video")
        else MediaAsset.MediaType.IMAGE
    )
    asset_title = f"Pencil — {city or asset_id_str}"

    # ── Store in media library ───────────────────────────────────────────
    asset = MediaAsset(
        organization=workspace.organization,
        workspace=workspace,
        filename=filename,
        media_type=media_type,
        mime_type=content_type,
        file_size=len(content),
        source="pencil",
        source_url=asset_url,
        title=asset_title,
        processing_status=MediaAsset.ProcessingStatus.COMPLETED,
    )
    asset.file.save(filename, ContentFile(content), save=False)
    asset.save()

    # ── Create Post draft ────────────────────────────────────────────────
    default_caption = f"FIFA 2026 Wine Corridor — {city.title()}" if city else ""
    post = Post.objects.create(
        workspace=workspace,
        caption=caption or default_caption,
        internal_notes=f"Auto-generated by Pencil. City: {city}. Source: {asset_url}",
    )

    # ── Wire PlatformPosts for connected accounts ─────────────────────────
    draft_posts = []
    if platforms:
        for account in SocialAccount.objects.filter(
            workspace=workspace, platform__in=platforms
        ):
            pp = PlatformPost.objects.create(
                post=post,
                social_account=account,
                platform_specific_media=[str(asset.id)],
            )
            draft_posts.append({"platform": account.platform, "post_id": str(pp.id)})

    return JsonResponse(
        {
            "success": True,
            "asset_id": str(asset.id),
            "post_id": str(post.id),
            "draft_posts": draft_posts,
        }
    )
