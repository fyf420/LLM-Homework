"""pet_hospital_mcp.py

宠物医院 MCP Server — 基于 MCP 2026-07-28 规范 · Streamable HTTP 传输。
首轮仅实现 list_pets 工具。
"""

import logging
from typing import Annotated, Literal

import httpx2
from mcp.server import CacheHint, MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

logging.basicConfig(level=logging.INFO)  # 日志走 stderr，勿用 print
logger = logging.getLogger("pet-hospital-mcp")

REST_BASE_URL = "http://127.0.0.1:8080/api/v1"

mcp = MCPServer(
    "pet-hospital-mcp",
    version="1.0.0",
    cache_hints={"tools/list": CacheHint(ttl_ms=60_000, scope="private")},
)


async def _call_pets_api(params: dict) -> dict:
    """调用宠物医院 REST API 的 GET /pets 端点。

    Args:
        params: 查询参数字典（仅含非 None 值）。

    Returns:
        响应信封中的 data 字段（dict）。

    Raises:
        Exception: 网络错误、非 200 状态码或业务 code != 200。
    """
    async with httpx2.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{REST_BASE_URL}/pets", params=params)
        response.raise_for_status()
        envelope = response.json()
        if envelope.get("code") != 200:
            raise RuntimeError(f"API 错误: {envelope.get('message', '未知错误')}")
        return envelope.get("data", {})


def _format_pets(data: dict, page: int, page_size: int) -> str:
    """把 REST 响应 data 格式化为紧凑表格。

    注意：每个 item 内嵌完整 records/charges，体量很大，
    这里只摘要展示顶层字段，避免浪费模型上下文。
    """
    items = data.get("items", [])
    total = data.get("total", len(items))
    current_page = data.get("page", page)
    total_pages = data.get("totalPages", 1)

    if not items:
        return f"未找到符合条件的宠物档案（共 {total} 条）。"

    lines = [f"找到 {total} 只宠物（当前第 {current_page} 页，共 {total_pages} 页）：", ""]
    header = ("编号", "名称", "种类", "医生", "状态", "疾病", "总花费", "就诊")
    widths = (11, 8, 4, 7, 6, 14, 9, 4)
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    lines.append(sep)
    lines.append("| " + " | ".join(h.ljust(w) for h, w in zip(header, widths)) + " |")
    lines.append(sep)
    for pet in items:
        row = (
            str(pet.get("id", ""))[: widths[0]],
            str(pet.get("name", ""))[: widths[1]],
            str(pet.get("species", ""))[: widths[2]],
            str(pet.get("doctor", ""))[: widths[3]],
            str(pet.get("status", ""))[: widths[4]],
            str(pet.get("disease", ""))[: widths[5]],
            f"{float(pet.get('totalCost', 0)):,.0f}"[: widths[6]],
            str(pet.get("visitCount", 0))[: widths[7]],
        )
        lines.append("| " + " | ".join(c.ljust(w) for c, w in zip(row, widths)) + " |")
    lines.append(sep)
    return "\n".join(lines)


@mcp.tool(
    title="查询宠物列表",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
async def list_pets(
    q: Annotated[str | None, Field(description="全文检索关键词，空格分词 AND 匹配姓名/主人/疾病等字段")] = None,
    species: Annotated[Literal["犬", "猫", "兔", "鸟", "仓鼠", "爬宠", "其他"] | None,
                       Field(description="按种类筛选")] = None,
    doctor: Annotated[str | None, Field(description="按主治医生筛选")] = None,
    status: Annotated[Literal["待就诊", "就诊中", "住院中", "已康复", "慢性病随访"] | None,
                      Field(description="按就诊状态筛选")] = None,
    disease: Annotated[str | None, Field(description="按疾病筛选")] = None,
    owner_name: Annotated[str | None, Field(description="按主人姓名筛选")] = None,
    min_cost: Annotated[float | None, Field(description="最低总花费")] = None,
    max_cost: Annotated[float | None, Field(description="最高总花费")] = None,
    sort_by: Annotated[
        Literal["id", "name", "ownerName", "species", "doctor", "disease",
                "status", "totalCost", "visitCount", "createdAt", "updatedAt"] | None,
        Field(description="排序字段")] = None,
    order: Annotated[Literal["asc", "desc"] | None, Field(description="排序方向")] = None,
    page: Annotated[int, Field(ge=1, description="页码，从 1 开始")] = 1,
    page_size: Annotated[int, Field(ge=1, le=50, description="每页条数，1-50")] = 5,
) -> str:
    """
    查询宠物档案列表，支持搜索、筛选、排序和分页。

    调用宠物医院 REST API 的 GET /api/v1/pets，返回符合条件的宠物档案摘要列表。
    """
    api_params: dict = {}
    if q is not None:
        api_params["q"] = q
    if species is not None:
        api_params["species"] = species
    if doctor is not None:
        api_params["doctor"] = doctor
    if status is not None:
        api_params["status"] = status
    if disease is not None:
        api_params["disease"] = disease
    if owner_name is not None:
        api_params["ownerName"] = owner_name
    if min_cost is not None:
        api_params["min"] = min_cost
    if max_cost is not None:
        api_params["max"] = max_cost
    if sort_by is not None:
        api_params["sortBy"] = sort_by
    if order is not None:
        api_params["order"] = order
    api_params["page"] = page
    api_params["pageSize"] = page_size

    try:
        data = await _call_pets_api(api_params)
        return _format_pets(data, page, page_size)
    except httpx2.ConnectError:
        logger.error("无法连接到宠物医院 REST API")
        return "错误：无法连接到宠物医院服务器（http://127.0.0.1:8080），请确认服务是否已启动。"
    except Exception as e:  # noqa: BLE001
        logger.error(f"查询失败: {e}")
        return f"查询失败: {e}"


if __name__ == "__main__":
    # 直接运行（自定义端口必须走这里）：
    #   python pet_hospital_mcp.py
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8082,
        stateless_http=True,
        json_response=True,
    )