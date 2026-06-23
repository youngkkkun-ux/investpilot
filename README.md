# InvestPilot — A股个人投资助手

基于 FastAPI + AKShare + Claude AI 的 A股/基金个人投资管理工具。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据源 | AKShare（免费 A股/基金数据） |
| 前端 | 原生 HTML + Chart.js（无需 Node.js） |
| AI 分析 | Claude API (claude-sonnet-4-6) |
| 数据持久化 | 本地 JSON（data/positions.json） |

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
bash start.sh
# 或手动启动：
cd backend && uvicorn main:app --reload --port 8000

# 3. 访问
# 打开浏览器：http://localhost:8000
```

## 功能模块

### 持仓看板
- 总资产 / 总盈亏 / 今日涨跌 实时汇总
- 持仓明细表（带实时价格更新）
- 今日涨幅榜 Top 10（实时）
- 持仓盈亏构成柱状图

### 股票分析
- 实时行情（价格、涨跌、换手率、PE、PB、总市值）
- 历史 K 线（日K/周K/月K，前复权）
- **Claude AI 智能研报**：估值、技术面、风险、操作建议

### 基金分析
- 混合型基金排行榜（近1年收益排序）
- 任意基金净值走势（近90个交易日）
- **Claude AI 基金解读**：风格、适合人群、持有建议

### 持仓管理
- 添加/删除持仓记录（持久化到本地 JSON）
- 自动计算：成本、市值、盈亏金额、盈亏率
- 启动时自动拉取最新价格更新持仓

### AI 助手
- 多轮对话，由 claude-sonnet-4-6 驱动
- 快捷提问：A股入场时机、板块分析、定投策略等

## API 接口列表

```
GET  /api/market/index          大盘三大指数
GET  /api/market/hot            今日涨幅榜 Top10
GET  /api/stock/quote?code=     单股实时行情
GET  /api/stock/kline?code=     历史K线
GET  /api/fund/rank?category=   基金排行
GET  /api/fund/nav?code=        基金净值走势
GET  /api/positions             获取持仓列表
POST /api/positions             添加持仓
DELETE /api/positions/{id}      删除持仓
GET  /api/health                健康检查
```

## 项目结构

```
investpilot/
├── backend/
│   └── main.py          FastAPI 后端（接口 + 静态文件托管）
├── frontend/
│   └── index.html       前端单页面应用
├── data/
│   └── positions.json   持仓数据（自动创建）
├── requirements.txt
├── start.sh
└── README.md
```

## 风险提示

本项目仅供学习研究使用，数据来源于 AKShare 公开接口，AI 分析结果不构成投资建议。股市有风险，投资需谨慎。
