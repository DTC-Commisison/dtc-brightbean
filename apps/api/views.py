from django.http import JsonResponse
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
            "url": "https://dtc-brightbean-phase0.up.railway.app",
            "description": "Phase 0",
        },
    ],
    "paths": {
        "/api/webhooks/asset-received": {
            "post": {
                "operationId": "receiveAsset",
                "summary": "Webhook receiver — asset from dtc-media-studio",
                "tags": ["webhooks"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["_type", "_id", "url", "platforms"],
                                "properties": {
                                    "_type": {"type": "string", "enum": ["mediaAsset"]},
                                    "_id": {"type": "string"},
                                    "url": {"type": "string", "format": "uri"},
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
                                    "approvalToken": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Asset received",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean"},
                                        "asset_id": {"type": "string"},
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
                    "401": {"description": "Invalid HMAC signature"},
                    "500": {"description": "Server error"},
                },
            }
        }
    },
    "tags": [
        {"name": "webhooks", "description": "Inbound webhooks from dtc-media-studio"},
    ],
}


@require_http_methods(["GET"])
def openapi_spec(request):
    """Serve OpenAPI specification for service discovery"""
    response = JsonResponse(OPENAPI_SPEC)
    response["Cache-Control"] = "public, max-age=3600"
    response["Access-Control-Allow-Origin"] = "*"
    return response
