"""
InvestPilot 后端服务
运行方式：uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import akshare as ak
import pandas as pd
import json
import os
import httpx
from datetime import datetime, timedelta
from typing import Optional, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="InvestPilot API", version="1.0.0")

# CORS 配置（允许前端跨域请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 挂载前端静态文件 ──────────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ── 持仓数据本地存储 ──────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "positions.json")

def load_positions():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_positions(positions):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)


# ── 数据模型 ──────────────────────────────────────────────────────────
class Position(BaseModel):
    id: Optional[int] = None
    name: str
    code: str
    buy_price: float
    quantity: int
    current_price: Optional[float] = None


# ═══════════════════════════════════════════════════════════════
#  股票接口
# ═══════════════════════════════════════════════════════════════

@app.get("/api/stock/quote")
def get_stock_quote(code: str = Query(..., description="股票代码，如 300750")):
    """获取单只股票实时行情"""
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if row.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票 {code}")
        r = row.iloc[0]
        return {
            "code": code,
            "name": str(r.get("名称", "")),
            "price": round(float(r.get("最新价", 0)), 2),
            "change_pct": round(float(r.get("涨跌幅", 0)), 2),
            "change": round(float(r.get("涨跌额", 0)), 2),
            "volume": int(r.get("成交量", 0)),
            "amount": round(float(r.get("成交额", 0)) / 1e8, 2),
            "high": round(float(r.get("最高", 0)), 2),
            "low": round(float(r.get("最低", 0)), 2),
            "open": round(float(r.get("今开", 0)), 2),
            "pre_close": round(float(r.get("昨收", 0)), 2),
            "market_cap": round(float(r.get("总市值", 0)) / 1e8, 2),
            "pe": round(float(r.get("市盈率-动态", 0) or 0), 2),
            "pb": round(float(r.get("市净率", 0) or 0), 2),
            "turnover": round(float(r.get("换手率", 0) or 0), 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_stock_quote error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/kline")
def get_kline(
    code: str = Query(...),
    period: str = Query("daily", description="daily/weekly/monthly"),
    adjust: str = Query("qfq", description="复权：qfq前复权/hfq后复权/不填不复权"),
    limit: int = Query(60, description="返回条数"),
):
    """获取历史K线数据"""
    try:
        end = datetime.today().strftime("%Y%m%d")
        start = (datetime.today() - timedelta(days=limit * 2)).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(
            symbol=code, period=period, start_date=start,
            end_date=end, adjust=adjust
        )
        df = df.tail(limit)
        result = []
        for _, row in df.iterrows():
            result.append({
                "date": str(row["日期"]),
                "open": round(float(row["开盘"]), 2),
                "close": round(float(row["收盘"]), 2),
                "high": round(float(row["最高"]), 2),
                "low": round(float(row["最低"]), 2),
                "volume": int(row["成交量"]),
            })
        return {"code": code, "period": period, "data": result}
    except Exception as e:
        logger.error(f"get_kline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/fundamental")
def get_fundamental(code: str = Query(...)):
    """获取股票基本面（财务指标）"""
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="暂无财务数据")
        latest = df.iloc[0]
        row = {}
        for col in df.columns:
            val = latest[col]
            try:
                row[col] = round(float(val), 4) if val not in (None, "", "nan") else None
            except Exception:
                row[col] = str(val)
        return {"code": code, "data": row, "columns": list(df.columns[:10])}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_fundamental error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/market/index")
def get_market_index():
    """获取主要指数（上证/深证/创业板）"""
    try:
        df = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
        result = []
        targets = {"000001": "上证指数", "399001": "深证成指", "399006": "创业板指"}
        for code, name in targets.items():
            row = df[df["代码"] == code]
            if not row.empty:
                r = row.iloc[0]
                result.append({
                    "code": code,
                    "name": name,
                    "price": round(float(r.get("最新价", 0)), 2),
                    "change_pct": round(float(r.get("涨跌幅", 0)), 2),
                })
        return {"data": result}
    except Exception as e:
        logger.error(f"get_market_index error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/market/hot")
def get_hot_stocks():
    """获取今日涨幅榜 Top10"""
    try:
        df = ak.stock_zh_a_spot_em()
        df = df[df["涨跌幅"].notna()]
        df = df[df["最新价"] > 0]
        top = df.nlargest(10, "涨跌幅")[["代码", "名称", "最新价", "涨跌幅", "成交额"]]
        result = []
        for _, r in top.iterrows():
            result.append({
                "code": str(r["代码"]),
                "name": str(r["名称"]),
                "price": round(float(r["最新价"]), 2),
                "change_pct": round(float(r["涨跌幅"]), 2),
                "amount": round(float(r["成交额"]) / 1e8, 2),
            })
        return {"data": result}
    except Exception as e:
        logger.error(f"get_hot_stocks error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
#  基金接口
# ═══════════════════════════════════════════════════════════════

@app.get("/api/fund/info")
def get_fund_info(code: str = Query(..., description="基金代码，如 110011")):
    """获取基金基本信息"""
    try:
        df = ak.fund_open_fund_info_em(fund=code, indicator="基本概况")
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"未找到基金 {code}")
        info = {}
        for _, row in df.iterrows():
            info[str(row.iloc[0])] = str(row.iloc[1])
        return {"code": code, "info": info}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_fund_info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fund/nav")
def get_fund_nav(
    code: str = Query(...),
    limit: int = Query(90, description="返回条数")
):
    """获取基金净值历史"""
    try:
        df = ak.fund_open_fund_info_em(fund=code, indicator="单位净值走势")
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="暂无净值数据")
        df = df.tail(limit)
        result = []
        for _, row in df.iterrows():
            result.append({
                "date": str(row.iloc[0]),
                "nav": round(float(row.iloc[1]), 4),
            })
        return {"code": code, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_fund_nav error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fund/rank")
def get_fund_rank(category: str = Query("混合型", description="基金类型")):
    """获取基金排行（近1年）"""
    try:
        df = ak.fund_open_fund_rank_em(symbol=category)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="暂无排行数据")
        result = []
        for _, r in df.head(20).iterrows():
            try:
                result.append({
                    "code": str(r.get("基金代码", "")),
                    "name": str(r.get("基金简称", "")),
                    "nav": str(r.get("单位净值", "")),
                    "return_1y": str(r.get("近1年", "")),
                    "return_3y": str(r.get("近3年", "")),
                    "manager": str(r.get("基金经理人", "")),
                })
            except Exception:
                continue
        return {"category": category, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_fund_rank error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
#  持仓管理接口（本地 JSON 持久化）
# ═══════════════════════════════════════════════════════════════

@app.get("/api/positions")
def get_positions():
    """获取所有持仓"""
    positions = load_positions()
    # 尝试补充实时价格
    try:
        if positions:
            df = ak.stock_zh_a_spot_em()
            for p in positions:
                row = df[df["代码"] == p["code"]]
                if not row.empty:
                    p["current_price"] = round(float(row.iloc[0]["最新价"]), 2)
    except Exception as e:
        logger.warning(f"realtime price fetch failed: {e}")
    return {"data": positions}


@app.post("/api/positions")
def add_position(pos: Position):
    """添加持仓记录"""
    positions = load_positions()
    new_pos = pos.dict()
    new_pos["id"] = int(datetime.now().timestamp() * 1000)
    new_pos["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    positions.append(new_pos)
    save_positions(positions)
    return {"success": True, "data": new_pos}


@app.delete("/api/positions/{pos_id}")
def delete_position(pos_id: int):
    """删除持仓记录"""
    positions = load_positions()
    before = len(positions)
    positions = [p for p in positions if p.get("id") != pos_id]
    if len(positions) == before:
        raise HTTPException(status_code=404, detail="持仓记录不存在")
    save_positions(positions)
    return {"success": True}


@app.put("/api/positions/{pos_id}")
def update_position(pos_id: int, pos: Position):
    """更新持仓记录"""
    positions = load_positions()
    for i, p in enumerate(positions):
        if p.get("id") == pos_id:
            updated = pos.dict()
            updated["id"] = pos_id
            updated["created_at"] = p.get("created_at", "")
            positions[i] = updated
            save_positions(positions)
            return {"success": True, "data": updated}
    raise HTTPException(status_code=404, detail="持仓记录不存在")


# ═══════════════════════════════════════════════════════════════
#  AI 接口（转发到本地 Ollama）
# ═══════════════════════════════════════════════════════════════

OLLAMA_BASE   = "http://localhost:11434"
OLLAMA_MODEL  = "deepseek-r1"   # 与本地 ollama run 的模型名一致
AI_SYSTEM_PROMPT = (
    "你是专业的A股及基金投资分析助手，回答专业、简洁、结构清晰。"
    "始终在末尾提醒：⚠️ 以上内容仅供学习参考，不构成投资建议，股市有风险，投资需谨慎。"
)


class ChatMessage(BaseModel):
    role: str       # "user" | "assistant"
    content: str


class AiRequest(BaseModel):
    messages: List[ChatMessage]
    system: Optional[str] = None   # 可覆盖默认 system prompt
    stream: bool = False


@app.post("/api/ai/chat")
async def ai_chat(req: AiRequest):
    """
    将前端消息转发给本地 Ollama（deepseek-r1），返回模型回复。
    兼容 Ollama /api/chat 接口（OpenAI 格式）。
    """
    system = req.system or AI_SYSTEM_PROMPT
    messages = [{"role": "system", "content": system}]
    messages += [{"role": m.role, "content": m.content} for m in req.messages]

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 1024,
        }
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            reply = data.get("message", {}).get("content", "")
            # deepseek-r1 会在 <think>...</think> 块中输出推理过程，前端不需要展示
            import re
            reply_clean = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
            return {
                "reply": reply_clean,
                "model": data.get("model", OLLAMA_MODEL),
                "done": data.get("done", True),
            }
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="无法连接到 Ollama 服务（localhost:11434），请确认 ollama serve 已启动"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Ollama 返回错误：{e.response.text}")
    except Exception as e:
        logger.error(f"ai_chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/status")
async def ai_status():
    """检查 Ollama 服务和模型是否可用"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 查询已加载的模型列表
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            model_ready = any(OLLAMA_MODEL in m for m in models)
            return {
                "ollama_running": True,
                "model": OLLAMA_MODEL,
                "model_ready": model_ready,
                "available_models": models,
            }
    except Exception:
        return {
            "ollama_running": False,
            "model": OLLAMA_MODEL,
            "model_ready": False,
            "available_models": [],
        }


# ═══════════════════════════════════════════════════════════════
#  健康检查
# ═══════════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
