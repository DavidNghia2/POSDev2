from __future__ import annotations

import mimetypes
import re
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from app_paths import PROJECT_ROOT, cache_dir

from .supabase_client import get_supabase_client, is_supabase_configured


PRODUCT_IMAGE_BUCKET = "product-images"


class CloudProductError(RuntimeError):
    pass


def cloud_products_available() -> bool:
    return is_supabase_configured()


def _data_or_raise(response: Any, action: str) -> Any:
    error = getattr(response, "error", None)
    if error:
        raise CloudProductError(f"Supabase {action} failed: {error}")
    return getattr(response, "data", None)


def _clean_storage_part(value: str) -> str:
    clean_value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return clean_value.strip(".-") or "file"


def _resolve_local_image(image_path: str) -> Path | None:
    if not image_path or image_path.startswith(("http://", "https://")):
        return None
    path = Path(image_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path if path.exists() else None


def _file_name_from_url(url: str, fallback: str) -> str:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name
    return _clean_storage_part(name or fallback)


def public_url_for_storage_path(storage_path: str) -> str:
    if not storage_path:
        return ""
    return str(get_supabase_client().storage.from_(PRODUCT_IMAGE_BUCKET).get_public_url(storage_path))


def upload_product_image(
    store_id: str,
    product_key: str,
    image_path: str,
) -> tuple[str, str] | tuple[None, None]:
    local_path = _resolve_local_image(image_path)
    if local_path is None:
        return None, None

    file_name = _clean_storage_part(local_path.name)
    storage_path = f"{store_id}/products/{_clean_storage_part(product_key)}/{file_name}"
    mime_type = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"
    bucket = get_supabase_client().storage.from_(PRODUCT_IMAGE_BUCKET)
    file_options = {
        "content-type": mime_type,
        "upsert": "true",
    }

    try:
        bucket.upload(storage_path, str(local_path), file_options)
    except Exception:
        bucket.update(storage_path, str(local_path), file_options)
    return storage_path, str(bucket.get_public_url(storage_path))


def download_product_image(
    store_id: str,
    cloud_product_id: str,
    image_url: str,
    storage_path: str = "",
) -> str:
    if not image_url:
        return ""

    file_name = _file_name_from_url(image_url, f"product-{cloud_product_id}.img")
    if storage_path:
        file_name = _clean_storage_part(Path(storage_path).name or file_name)
    target_dir = cache_dir("product-images", _clean_storage_part(store_id), _clean_storage_part(cloud_product_id))
    target_path = target_dir / file_name

    if target_path.exists():
        return str(target_path)

    try:
        urllib.request.urlretrieve(image_url, target_path)
    except Exception as error:
        raise CloudProductError(f"Could not download product image: {error}") from error
    return str(target_path)


def fetch_products(store_id: str | None = None) -> list[dict[str, Any]]:
    query = (
        get_supabase_client()
        .table("products")
        .select(
            "id,store_id,barcode,sku,name,price,category,stock_qty,"
            "requires_weight,active,storage_path,image_url,updated_at"
        )
    )
    if store_id:
        query = query.eq("store_id", store_id)
    response = query.order("id", desc=False).execute()
    rows = _data_or_raise(response, "product fetch")
    return rows if isinstance(rows, list) else []


def fetch_product_barcodes(store_id: str | None = None) -> list[dict[str, Any]]:
    query = (
        get_supabase_client()
        .table("product_barcodes")
        .select("id,store_id,product_id,barcode,is_primary")
    )
    if store_id:
        query = query.eq("store_id", store_id)
    response = query.order("id", desc=False).execute()
    rows = _data_or_raise(response, "product barcode fetch")
    return rows if isinstance(rows, list) else []


def upsert_product(payload: dict[str, Any], cloud_id: str | None = None) -> dict[str, Any]:
    client = get_supabase_client()
    if cloud_id:
        response = (
            client.table("products")
            .update(payload)
            .eq("id", cloud_id)
            .select(
                "id,store_id,barcode,sku,name,price,category,stock_qty,"
                "requires_weight,active,storage_path,image_url,updated_at"
            )
            .single()
            .execute()
        )
    else:
        response = (
            client.table("products")
            .insert(payload)
            .select(
                "id,store_id,barcode,sku,name,price,category,stock_qty,"
                "requires_weight,active,storage_path,image_url,updated_at"
            )
            .single()
            .execute()
        )
    data = _data_or_raise(response, "product upsert")
    if not isinstance(data, dict):
        raise CloudProductError("Supabase product upsert returned an invalid payload.")
    return data


def fetch_product_stock(cloud_id: str) -> dict[str, Any] | None:
    response = (
        get_supabase_client()
        .table("products")
        .select("id,store_id,stock_qty")
        .eq("id", cloud_id)
        .limit(1)
        .execute()
    )
    rows = _data_or_raise(response, "product stock fetch")
    if isinstance(rows, list) and rows:
        row = rows[0]
        return row if isinstance(row, dict) else None
    return None


def record_inventory_adjustment(
    store_id: str,
    cloud_product_id: str,
    qty_delta: float,
    reason: str = "adjustment",
) -> None:
    if abs(qty_delta) < 0.0005:
        return
    _data_or_raise(
        get_supabase_client()
        .table("inventory_movements")
        .insert(
            {
                "store_id": store_id,
                "product_id": int(cloud_product_id),
                "qty_delta": qty_delta,
                "reason": reason,
            }
        )
        .execute(),
        "inventory adjustment insert",
    )


def set_product_active(cloud_id: str, active: bool) -> dict[str, Any]:
    response = (
        get_supabase_client()
        .table("products")
        .update({"active": active})
        .eq("id", cloud_id)
        .select("id,store_id,active,updated_at")
        .single()
        .execute()
    )
    data = _data_or_raise(response, "product active update")
    if not isinstance(data, dict):
        raise CloudProductError("Supabase product active update returned an invalid payload.")
    return data


def replace_product_barcodes(
    store_id: str,
    cloud_product_id: str,
    barcodes: list[str],
) -> None:
    client = get_supabase_client()
    _data_or_raise(
        client.table("product_barcodes")
        .delete()
        .eq("store_id", store_id)
        .eq("product_id", cloud_product_id)
        .execute(),
        "product barcode delete",
    )
    rows = [
        {
            "store_id": store_id,
            "product_id": int(cloud_product_id),
            "barcode": barcode,
            "is_primary": index == 0,
        }
        for index, barcode in enumerate(barcodes)
        if barcode.strip()
    ]
    if rows:
        _data_or_raise(client.table("product_barcodes").insert(rows).execute(), "product barcode insert")
