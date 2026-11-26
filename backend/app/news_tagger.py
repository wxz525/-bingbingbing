"""新闻三维标签词典与打标函数。"""
from __future__ import annotations

# 维度二：内容主题（一条新闻可命中多个，逗号拼接）
TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "macro": (
        "美联储", "加息", "降息", "货币政策", "财政", "监管", "国务院", "央行",
        "CPI", "GDP", "通胀", "通缩", "PMI", "利率", "降准", "逆周期",
        "政策", "宏观", "经济数据", "社融", "M2",
    ),
    "tech": (
        "芯片", "半导体", "华为", "AI", "人工智能", "算力", "GPT", "科技股",
        "机器人", "新能源", "光伏", "储能", "锂电池", "宁德时代", "比亚迪",
        "特斯拉", "固态电池", "自动驾驶", "大模型", "数据中心",
    ),
    "pharma": (
        "医药", "ADC", "医疗", "生物", "云南白药", "创新药", "疫苗", "恒瑞",
        "集采", "医疗器械", "CRO", "基因", "肿瘤", "临床", "药企",
    ),
    "energy": (
        "石油", "OPEC", "煤炭", "原油", "铜", "锌", "黄金", "稀土", "大宗商品",
        "铁矿石", "铝", "天然气", "页岩油", "锂矿", "钴", "焦煤", "动力煤",
    ),
    "finance": (
        "银行", "保险", "券商", "融资", "融券", "大宗交易", "回购", "主力资金",
        "北向资金", "融资融券", "IPO", "打新", "基金", "ETF", "资管", "信托",
        "私募", "公募", "债市", "信用债", "可转债",
    ),
    "consumer": (
        "白酒", "泸州老窖", "消费", "旅游", "餐饮", "零售", "免税", "化妆品",
        "食品饮料", "啤酒", "家电", "乳制品", "黄金首饰",
    ),
    "infrastructure": (
        "基建", "港口", "柳钢", "包钢", "中国交建", "路桥", "水泥", "钢铁",
        "中交", "高铁", "工程", "建设", "房地产", "建筑",
    ),
    "event": (
        "大选", "制裁", "战争", "灾害", "一带一路", "峰会", "会谈", "地缘",
        "选举", "冲突", "贸易战", "脱钩",
    ),
    "capital_flow": (
        "资金流", "CTA", "ETF资金", "净流入", "净流出", "资金流入", "资金流出",
        "跨境资金", "新兴市场", "EM资金", "DM资金", "债券基金", "股票基金",
    ),
}

# 维度三：市场层级（三选一）
MACRO_KEYWORDS = (
    "全球", "美国", "欧洲", "日本", "韩国", "印度", "巴西", "新兴市场",
    "发达市场", "美联储", "欧央行", "BOJ", "英格兰银行",
    "国内", "国际", "海外", "境外",
    "经济", "GDP", "CPI", "通胀", "货币政策", "财政政策",
)
SECTOR_HINTS = (
    "板块", "行业", "概念", "指数", "主题", "赛道",
    "主线", "风向", "风口", "龙头", "领涨", "轮动",
    "板块", "概念板块", "行业板块",
)

# 维度四：情绪倾向
BULLISH_KEYWORDS = (
    "大涨", "涨停", "利好", "业绩增长", "净利润增长", "营收增长",
    "回购", "中标", "获关注", "强于", "流入", "新高", "上行", "景气",
    "超预期", "增持", "看多", "看涨", "突破", "飘红", "开门红",
    "净买入", "业绩预增", "盈利", "扭亏",
)
BEARISH_KEYWORDS = (
    "大跌", "跌停", "利空", "业绩下滑", "净利润下滑", "营收下滑",
    "减持", "流出", "下跌", "跳水", "暴跌", "崩", "爆雷", "违规", "制裁",
    "债务违约", "信用风险", "看空", "做空", "抛压", "赎回", "亏损",
    "低于预期", "暴雷", "暴", "衰退", "处罚", "起诉", "退市", "爆仓",
    "净卖出", "业绩预减", "增持计划终止",
)


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def classify_topics(text: str) -> str:
    hits = [key for key, words in TOPIC_KEYWORDS.items() if _has_any(text, words)]
    return ",".join(hits)


def classify_market_level(text: str, source: str) -> str:
    if source and source.startswith("机构"):
        return "macro"
    if _has_any(text, MACRO_KEYWORDS):
        return "macro"
    if _has_any(text, SECTOR_HINTS):
        return "sector"
    return "single"


def classify_sentiment(text: str) -> str:
    bull = sum(1 for w in BULLISH_KEYWORDS if w in text)
    bear = sum(1 for w in BEARISH_KEYWORDS if w in text)
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def tag_row(title: str, source: str, content_text: str = "") -> tuple[str, str, str]:
    hay = f"{title} {content_text[:800]}"
    return (
        classify_topics(hay),
        classify_market_level(title, source),
        classify_sentiment(hay),
    )


# 前端展示用的标签元信息
TOPIC_LABELS: dict[str, str] = {
    "macro": "宏观政策",
    "tech": "科技/半导体",
    "pharma": "医药/医疗",
    "energy": "能源/资源",
    "finance": "金融/资本市场",
    "consumer": "消费/白酒",
    "infrastructure": "基建/周期",
    "event": "事件/地缘",
    "capital_flow": "资金面情报",
}

LEVEL_LABELS: dict[str, str] = {
    "single": "个股/公司",
    "sector": "细分市场/行业",
    "macro": "宏观市场",
}

SENTIMENT_LABELS: dict[str, str] = {
    "bullish": "利好",
    "neutral": "中性",
    "bearish": "利空",
}
