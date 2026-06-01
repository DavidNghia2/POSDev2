from __future__ import annotations

from typing import Any

from .supabase_client import get_supabase_client


class CloudInventoryError(RuntimeError):
    pass


class CloudInventoryConflict(CloudInventoryError):
    pass


def _data_or_raise(response: Any, action: str) -> Any:
    error = getattr(response, "error", None)
    if error:
        raise CloudInventoryError(f"Supabase {action} failed: {error}")
    return getattr(response, "data", None)


def checkout_sale(
    client_sale_id: str,
    register_id: int | None,
    items: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    total_amount: float,
    note: str = "",
) -> dict[str, Any]:
    response = get_supabase_client().rpc(
        "checkout_sale",
        {
            "p_client_sale_id": client_sale_id,
            "p_register_id": register_id,
            "p_items": items,
            "p_payments": payments,
            "p_total_amount": total_amount,
            "p_note": note,
        },
    ).execute()
    error = getattr(response, "error", None)
    if error:
        raise CloudInventoryError(str(error))
    data = getattr(response, "data", None)
    if isinstance(data, dict) and data.get("status") == "insufficient_stock":
        raise CloudInventoryConflict(str(data.get("message") or "Insufficient stock."))
    if not isinstance(data, dict):
        raise CloudInventoryError("Supabase checkout_sale returned an invalid payload.")
    return data


def fetch_recent_sales(store_id: str, limit: int = 200) -> list[dict[str, Any]]:
    response = (
        get_supabase_client()
        .table("sales")
        .select(
            "id,store_id,client_sale_id,user_id,register_id,total_amount,payment_method,"
            "tendered_amount,change_amount,note,status,created_at"
        )
        .eq("store_id", store_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = _data_or_raise(response, "recent sales fetch")
    return rows if isinstance(rows, list) else []


def fetch_registers(store_id: str) -> list[dict[str, Any]]:
    response = (
        get_supabase_client()
        .table("registers")
        .select("id,store_id,name,location,active,updated_at")
        .eq("store_id", store_id)
        .order("id", desc=False)
        .execute()
    )
    rows = _data_or_raise(response, "register fetch")
    return rows if isinstance(rows, list) else []


def fetch_sale_items(store_id: str, sale_ids: list[str]) -> list[dict[str, Any]]:
    if not sale_ids:
        return []
    response = (
        get_supabase_client()
        .table("sale_items")
        .select("id,store_id,sale_id,product_id,barcode,name,qty,price,subtotal")
        .eq("store_id", store_id)
        .in_("sale_id", sale_ids)
        .order("id", desc=False)
        .execute()
    )
    rows = _data_or_raise(response, "sale items fetch")
    return rows if isinstance(rows, list) else []


def fetch_sale_payments(store_id: str, sale_ids: list[str]) -> list[dict[str, Any]]:
    if not sale_ids:
        return []
    response = (
        get_supabase_client()
        .table("sale_payments")
        .select("id,store_id,sale_id,method,amount,created_at")
        .eq("store_id", store_id)
        .in_("sale_id", sale_ids)
        .order("id", desc=False)
        .execute()
    )
    rows = _data_or_raise(response, "sale payments fetch")
    return rows if isinstance(rows, list) else []
