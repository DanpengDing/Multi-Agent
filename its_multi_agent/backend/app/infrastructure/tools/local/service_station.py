import json
import math
from typing import Any

import stun
from agents import function_tool
from pymysql.cursors import DictCursor

from infrastructure.database.database_pool import pool
from infrastructure.logging.logger import logger
from infrastructure.tools.mcp.mcp_servers import baidu_mcp_client


def bd09mc_to_bd09(lng: float, lat: float) -> tuple[float, float]:
    x = lng
    y = lat

    if abs(y) < 1e-6 or abs(x) < 1e-6:
        return 0.0, 0.0

    out_lng = x / 20037508.34 * 180
    out_lat = y / 20037508.34 * 180
    out_lat = 180 / math.pi * (2 * math.atan(math.exp(out_lat * math.pi / 180)) - math.pi / 2)
    return out_lng, out_lat


def get_ip_via_stun():
    try:
        _, external_ip, _ = stun.get_ip_info()
        return external_ip
    except Exception as exc:
        logger.warning("[Location] STUN failed error=%s", exc)
        return None


def _safe_preview(value: Any, limit: int = 500) -> str:
    text = str(value)
    return text if len(text) <= limit else f"{text[:limit]}...(truncated)"


def _extract_mcp_text(tool_name: str, result: Any) -> str:
    # 百度 MCP 的结果对象结构比较深，这里统一做一层提取和日志记录，
    # 方便我们在失败时看到“到底返回了什么”，而不是只看到 json 解析异常。
    content_list = getattr(result, "content", None)
    if not content_list:
        logger.warning("[BaiduMCP] tool=%s returned empty content result=%s", tool_name, _safe_preview(result))
        return ""

    first_content = content_list[0]
    text = getattr(first_content, "text", "")
    if not text:
        logger.warning(
            "[BaiduMCP] tool=%s first content has no text content=%s",
            tool_name,
            _safe_preview(first_content),
        )
        return ""

    logger.info("[BaiduMCP] tool=%s raw_text=%s", tool_name, _safe_preview(text, 1000))
    return text


def _parse_json_response(tool_name: str, raw_text: str) -> dict:
    if not raw_text:
        raise ValueError(f"{tool_name} 返回空文本，无法解析 JSON")

    try:
        return json.loads(raw_text)
    except Exception as exc:
        logger.error(
            "[BaiduMCP] tool=%s json parse failed error=%s raw_text=%s",
            tool_name,
            exc,
            _safe_preview(raw_text, 1000),
        )
        raise


@function_tool
async def resolve_user_location_from_text(user_input: str) -> str:
    logger.info("[Location] resolve start raw_input=%s", user_input)

    relative_locations = {
        "附近",
        "这里",
        "当前",
        "当前位置",
        "我这里",
        "离我最近",
        "我附近",
        "nearby",
        "here",
    }

    normalized_input = user_input.strip() if user_input else ""
    if normalized_input in relative_locations:
        logger.info("[Location] relative term detected input=%s", normalized_input)
        normalized_input = ""

    if normalized_input:
        try:
            logger.info("[Location] geocode start address=%s", normalized_input)
            geo_result = await baidu_mcp_client.call_tool(
                tool_name="map_geocode",
                arguments={"address": normalized_input},
            )
            raw_text = _extract_mcp_text("map_geocode", geo_result)
            data = _parse_json_response("map_geocode", raw_text)
            result = data["result"]

            if isinstance(result, dict) and "location" in result:
                lat = float(result["location"]["lat"])
                lng = float(result["location"]["lng"])
                payload = json.dumps(
                    {
                        "ok": True,
                        "lat": lat,
                        "lng": lng,
                        "source": "geocode",
                        "original_input": normalized_input,
                    },
                    ensure_ascii=False,
                )
                logger.info("[Location] geocode success result=%s", payload)
                return payload

            logger.warning("[Location] geocode invalid result=%s", _safe_preview(data, 1000))
        except Exception as exc:
            logger.warning("[Location] geocode failed address=%s error=%s", normalized_input, exc, exc_info=True)

    user_ip = get_ip_via_stun()
    logger.info("[Location] detected external_ip=%s", user_ip)

    if user_ip and user_ip not in ("127.0.0.1", "localhost", "::1"):
        try:
            logger.info("[Location] ip location start ip=%s", user_ip)
            ip_result = await baidu_mcp_client.call_tool("map_ip_location", {"ip": user_ip})
            raw_text = _extract_mcp_text("map_ip_location", ip_result)
            data = _parse_json_response("map_ip_location", raw_text)
            if data.get("status") != 0:
                raise ValueError(f"ip location status={data.get('status')} message={data.get('message')}")

            point = data.get("content", {}).get("point", {})
            x_str = point.get("x")
            y_str = point.get("y")
            if not x_str or not y_str:
                raise ValueError("missing x/y coordinates")

            lng, lat = bd09mc_to_bd09(float(x_str), float(y_str))
            payload = json.dumps(
                {
                    "ok": True,
                    "lat": lat,
                    "lng": lng,
                    "source": "ip",
                    "original_input": normalized_input,
                },
                ensure_ascii=False,
            )
            logger.info("[Location] ip location success result=%s", payload)
            return payload
        except Exception as exc:
            logger.warning("[Location] ip location failed ip=%s error=%s", user_ip, exc, exc_info=True)

    payload = json.dumps(
        {
            "ok": False,
            "error": "无法可靠解析用户当前位置，已回退到默认坐标。",
            "lat": 39.9042,
            "lng": 116.4074,
            "source": "fallback",
            "original_input": normalized_input,
        },
        ensure_ascii=False,
    )
    logger.info("[Location] fallback result=%s", payload)
    return payload


@function_tool
def query_nearest_repair_shops_by_coords(lat: float, lng: float, limit: int = 3) -> str:
    connection = None
    cursor = None
    try:
        logger.info("[NearestShops] query start lat=%s lng=%s limit=%s", lat, lng, limit)
        connection = pool.connection()
        cursor = connection.cursor(DictCursor)

        sql = """
        SELECT
            id,
            service_station_name,
            province,
            city,
            district,
            address,
            phone,
            manager,
            manager_phone,
            opening_hours,
            repair_types,
            repair_specialties,
            repair_services,
            supported_brands,
            rating,
            established_year,
            employee_count,
            service_station_description,
            latitude,
            longitude,
            (
                6371 * acos(
                    cos(radians(%s)) *
                    cos(radians(latitude)) *
                    cos(radians(longitude) - radians(%s)) +
                    sin(radians(%s)) *
                    sin(radians(latitude))
                )
            ) AS distance_km
        FROM repair_shops
        WHERE
            latitude IS NOT NULL
            AND longitude IS NOT NULL
            AND ABS(latitude) <= 90
            AND ABS(longitude) <= 180
        ORDER BY distance_km ASC
        LIMIT %s
        """

        cursor.execute(sql, (lat, lng, lat, limit))
        rows = cursor.fetchall()
        logger.info("[NearestShops] found count=%s lat=%s lng=%s", len(rows), lat, lng)
        if rows:
            logger.debug("[NearestShops] first_row=%s", rows[0])

        payload = json.dumps(
            {
                "ok": True,
                "count": len(rows),
                "data": rows,
                "query": {
                    "lat": lat,
                    "lng": lng,
                    "limit": limit,
                },
            },
            ensure_ascii=False,
            default=str,
        )
        logger.info("[NearestShops] query result=%s", payload[:1200])
        return payload

    except Exception as exc:
        logger.error("[NearestShops] DB query failed error=%s", exc, exc_info=True)
        payload = json.dumps(
            {
                "ok": False,
                "error": f"查询附近服务站失败: {exc}",
                "query": {"lat": lat, "lng": lng, "limit": limit},
            },
            ensure_ascii=False,
        )
        logger.info("[NearestShops] query result=%s", payload)
        return payload
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
