"""Polymarket Gamma API `/public-search` 请求与响应对象。

使用 pydantic 定义请求参数（query params）和响应模型，包含中文注释，
并提供从 API 原始响应解析为模型的辅助方法，兼容数组/分页两种常见返回格式。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# 辅助 / 嵌套模型
# ---------------------------------------------------------------------------


class ImageOptimization(BaseModel):
    """图片优化信息。"""
    id: str
    imageUrlSource: Optional[str] = None
    imageUrlOptimized: Optional[str] = None
    imageSizeKbSource: Optional[float] = None
    imageSizeKbOptimized: Optional[float] = None
    imageOptimizedComplete: Optional[bool] = None
    imageOptimizedLastUpdated: Optional[str] = None
    relID: Optional[int] = None
    field: Optional[str] = None
    relname: Optional[str] = None


class Tag(BaseModel):
    """市场/事件标签。"""
    id: str
    label: Optional[str] = None
    slug: Optional[str] = None
    forceShow: Optional[bool] = None
    publishedAt: Optional[str] = None
    createdBy: Optional[int] = None
    updatedBy: Optional[int] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    forceHide: Optional[bool] = None
    isCarousel: Optional[bool] = None


class Category(BaseModel):
    """分类信息。"""
    id: str
    label: Optional[str] = None
    parentCategory: Optional[str] = None
    slug: Optional[str] = None
    publishedAt: Optional[str] = None
    createdBy: Optional[str] = None
    updatedBy: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class Chat(BaseModel):
    """聊天频道信息。"""
    id: str
    channelId: Optional[str] = None
    channelName: Optional[str] = None
    channelImage: Optional[str] = None
    live: Optional[bool] = None
    startTime: Optional[datetime] = None
    endTime: Optional[datetime] = None


class Template(BaseModel):
    """事件模板信息。"""
    id: str
    eventTitle: Optional[str] = None
    eventSlug: Optional[str] = None
    eventImage: Optional[str] = None
    marketTitle: Optional[str] = None
    description: Optional[str] = None
    resolutionSource: Optional[str] = None
    negRisk: Optional[bool] = None
    sortBy: Optional[str] = None
    showMarketImages: Optional[bool] = None
    seriesSlug: Optional[str] = None
    outcomes: Optional[str] = None


class Collection(BaseModel):
    """集合（Collection）信息。"""
    id: str
    ticker: Optional[str] = None
    slug: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    collectionType: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    image: Optional[str] = None
    icon: Optional[str] = None
    headerImage: Optional[str] = None
    layout: Optional[str] = None
    active: Optional[bool] = None
    closed: Optional[bool] = None
    archived: Optional[bool] = None
    new: Optional[bool] = None
    featured: Optional[bool] = None
    restricted: Optional[bool] = None
    isTemplate: Optional[bool] = None
    templateVariables: Optional[str] = None
    publishedAt: Optional[str] = None
    createdBy: Optional[str] = None
    updatedBy: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    commentsEnabled: Optional[bool] = None
    imageOptimized: Optional[ImageOptimization] = None
    iconOptimized: Optional[ImageOptimization] = None
    headerImageOptimized: Optional[ImageOptimization] = None


class EventCreator(BaseModel):
    """事件创建者信息。"""
    id: str
    creatorName: Optional[str] = None
    creatorHandle: Optional[str] = None
    creatorUrl: Optional[str] = None
    creatorImage: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Market（市场）模型 — 与 Event 互相嵌套（循环引用），稍后 model_rebuild()
# ---------------------------------------------------------------------------


class Market(BaseModel):
    """单个预测市场。"""
    id: str
    question: Optional[str] = None
    conditionId: Optional[str] = None
    slug: Optional[str] = None
    twitterCardImage: Optional[str] = None
    resolutionSource: Optional[str] = None
    endDate: Optional[datetime] = None
    category: Optional[str] = None
    ammType: Optional[str] = None
    liquidity: Optional[str] = None
    sponsorName: Optional[str] = None
    sponsorImage: Optional[str] = None
    startDate: Optional[datetime] = None
    xAxisValue: Optional[str] = None
    yAxisValue: Optional[str] = None
    denominationToken: Optional[str] = None
    fee: Optional[str] = None
    image: Optional[str] = None
    icon: Optional[str] = None
    lowerBound: Optional[str] = None
    upperBound: Optional[str] = None
    description: Optional[str] = None
    outcomes: Optional[str] = None
    outcomePrices: Optional[str] = None
    volume: Optional[str] = None
    active: Optional[bool] = None
    marketType: Optional[str] = None
    formatType: Optional[str] = None
    lowerBoundDate: Optional[str] = None
    upperBoundDate: Optional[str] = None
    closed: Optional[bool] = None
    marketMakerAddress: Optional[str] = None
    createdBy: Optional[int] = None
    updatedBy: Optional[int] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    closedTime: Optional[str] = None
    wideFormat: Optional[bool] = None
    new: Optional[bool] = None
    mailchimpTag: Optional[str] = None
    featured: Optional[bool] = None
    archived: Optional[bool] = None
    resolvedBy: Optional[str] = None
    restricted: Optional[bool] = None
    marketGroup: Optional[int] = None
    groupItemTitle: Optional[str] = None
    groupItemThreshold: Optional[str] = None
    questionID: Optional[str] = None
    umaEndDate: Optional[str] = None
    enableOrderBook: Optional[bool] = None
    orderPriceMinTickSize: Optional[float] = None
    orderMinSize: Optional[float] = None
    umaResolutionStatus: Optional[str] = None
    curationOrder: Optional[int] = None
    volumeNum: Optional[float] = None
    liquidityNum: Optional[float] = None
    endDateIso: Optional[str] = None
    startDateIso: Optional[str] = None
    umaEndDateIso: Optional[str] = None
    hasReviewedDates: Optional[bool] = None
    readyForCron: Optional[bool] = None
    commentsEnabled: Optional[bool] = None
    volume24hr: Optional[float] = None
    volume1wk: Optional[float] = None
    volume1mo: Optional[float] = None
    volume1yr: Optional[float] = None
    gameStartTime: Optional[str] = None
    secondsDelay: Optional[int] = None
    clobTokenIds: Optional[str] = None
    disqusThread: Optional[str] = None
    shortOutcomes: Optional[str] = None
    teamAID: Optional[str] = None
    teamBID: Optional[str] = None
    umaBond: Optional[str] = None
    umaReward: Optional[str] = None
    fpmmLive: Optional[bool] = None
    volume24hrAmm: Optional[float] = None
    volume1wkAmm: Optional[float] = None
    volume1moAmm: Optional[float] = None
    volume1yrAmm: Optional[float] = None
    volume24hrClob: Optional[float] = None
    volume1wkClob: Optional[float] = None
    volume1moClob: Optional[float] = None
    volume1yrClob: Optional[float] = None
    volumeAmm: Optional[float] = None
    volumeClob: Optional[float] = None
    liquidityAmm: Optional[float] = None
    liquidityClob: Optional[float] = None
    makerBaseFee: Optional[int] = None
    takerBaseFee: Optional[int] = None
    customLiveness: Optional[int] = None
    acceptingOrders: Optional[bool] = None
    notificationsEnabled: Optional[bool] = None
    score: Optional[int] = None
    imageOptimized: Optional[ImageOptimization] = None
    iconOptimized: Optional[ImageOptimization] = None
    events: Optional[List["Event"]] = None
    categories: Optional[List[Category]] = None
    tags: Optional[List[Tag]] = None
    creator: Optional[str] = None
    ready: Optional[bool] = None
    funded: Optional[bool] = None
    pastSlugs: Optional[str] = None
    readyTimestamp: Optional[datetime] = None
    fundedTimestamp: Optional[datetime] = None
    acceptingOrdersTimestamp: Optional[datetime] = None
    competitive: Optional[float] = None
    rewardsMinSize: Optional[float] = None
    rewardsMaxSpread: Optional[float] = None
    spread: Optional[float] = None
    automaticallyResolved: Optional[bool] = None
    oneDayPriceChange: Optional[float] = None
    oneHourPriceChange: Optional[float] = None
    oneWeekPriceChange: Optional[float] = None
    oneMonthPriceChange: Optional[float] = None
    oneYearPriceChange: Optional[float] = None
    lastTradePrice: Optional[float] = None
    bestBid: Optional[float] = None
    bestAsk: Optional[float] = None
    automaticallyActive: Optional[bool] = None
    clearBookOnStart: Optional[bool] = None
    chartColor: Optional[str] = None
    seriesColor: Optional[str] = None
    showGmpSeries: Optional[bool] = None
    showGmpOutcome: Optional[bool] = None
    manualActivation: Optional[bool] = None
    negRiskOther: Optional[bool] = None
    gameId: Optional[str] = None
    groupItemRange: Optional[str] = None
    sportsMarketType: Optional[str] = None
    line: Optional[float] = None
    umaResolutionStatuses: Optional[str] = None
    pendingDeployment: Optional[bool] = None
    deploying: Optional[bool] = None
    deployingTimestamp: Optional[datetime] = None
    scheduledDeploymentTimestamp: Optional[datetime] = None
    rfqEnabled: Optional[bool] = None
    eventStartTime: Optional[datetime] = None


class Series(BaseModel):
    """系列赛事信息。"""
    id: str
    ticker: Optional[str] = None
    slug: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    seriesType: Optional[str] = None
    recurrence: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    icon: Optional[str] = None
    layout: Optional[str] = None
    active: Optional[bool] = None
    closed: Optional[bool] = None
    archived: Optional[bool] = None
    new: Optional[bool] = None
    featured: Optional[bool] = None
    restricted: Optional[bool] = None
    isTemplate: Optional[bool] = None
    templateVariables: Optional[bool] = None
    publishedAt: Optional[str] = None
    createdBy: Optional[str] = None
    updatedBy: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    commentsEnabled: Optional[bool] = None
    competitive: Optional[str] = None
    volume24hr: Optional[float] = None
    volume: Optional[float] = None
    liquidity: Optional[float] = None
    startDate: Optional[datetime] = None
    pythTokenID: Optional[str] = None
    cgAssetName: Optional[str] = None
    score: Optional[int] = None
    events: Optional[List["Event"]] = None
    collections: Optional[List[Collection]] = None
    categories: Optional[List[Category]] = None
    tags: Optional[List[Tag]] = None
    commentCount: Optional[int] = None
    chats: Optional[List[Chat]] = None


# ---------------------------------------------------------------------------
# Event（事件）模型
# ---------------------------------------------------------------------------


class Event(BaseModel):
    """Polymarket 事件（一个事件可包含多个市场）。"""
    id: str
    ticker: Optional[str] = None
    slug: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    resolutionSource: Optional[str] = None
    startDate: Optional[datetime] = None
    creationDate: Optional[datetime] = None
    endDate: Optional[datetime] = None
    image: Optional[str] = None
    icon: Optional[str] = None
    active: Optional[bool] = None
    closed: Optional[bool] = None
    archived: Optional[bool] = None
    new: Optional[bool] = None
    featured: Optional[bool] = None
    restricted: Optional[bool] = None
    liquidity: Optional[float] = None
    volume: Optional[float] = None
    openInterest: Optional[float] = None
    sortBy: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    isTemplate: Optional[bool] = None
    templateVariables: Optional[str] = None
    published_at: Optional[str] = None
    createdBy: Optional[str] = None
    updatedBy: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    commentsEnabled: Optional[bool] = None
    competitive: Optional[float] = None
    volume24hr: Optional[float] = None
    volume1wk: Optional[float] = None
    volume1mo: Optional[float] = None
    volume1yr: Optional[float] = None
    featuredImage: Optional[str] = None
    disqusThread: Optional[str] = None
    parentEvent: Optional[str] = None
    enableOrderBook: Optional[bool] = None
    liquidityAmm: Optional[float] = None
    liquidityClob: Optional[float] = None
    negRisk: Optional[bool] = None
    negRiskMarketID: Optional[str] = None
    negRiskFeeBips: Optional[int] = None
    commentCount: Optional[int] = None
    imageOptimized: Optional[ImageOptimization] = None
    iconOptimized: Optional[ImageOptimization] = None
    featuredImageOptimized: Optional[ImageOptimization] = None
    subEvents: Optional[List[str]] = None
    markets: Optional[List[Market]] = None
    series: Optional[List[Series]] = None
    categories: Optional[List[Category]] = None
    collections: Optional[List[Collection]] = None
    tags: Optional[List[Tag]] = None
    cyom: Optional[bool] = None
    closedTime: Optional[datetime] = None
    showAllOutcomes: Optional[bool] = None
    showMarketImages: Optional[bool] = None
    automaticallyResolved: Optional[bool] = None
    enableNegRisk: Optional[bool] = None
    automaticallyActive: Optional[bool] = None
    eventDate: Optional[str] = None
    startTime: Optional[datetime] = None
    eventWeek: Optional[int] = None
    seriesSlug: Optional[str] = None
    score: Optional[str] = None
    elapsed: Optional[str] = None
    period: Optional[str] = None
    live: Optional[bool] = None
    ended: Optional[bool] = None
    finishedTimestamp: Optional[datetime] = None
    gmpChartMode: Optional[str] = None
    eventCreators: Optional[List[EventCreator]] = None
    tweetCount: Optional[int] = None
    chats: Optional[List[Chat]] = None
    featuredOrder: Optional[int] = None
    estimateValue: Optional[bool] = None
    cantEstimate: Optional[bool] = None
    estimatedValue: Optional[str] = None
    templates: Optional[List[Template]] = None
    spreadsMainLine: Optional[float] = None
    totalsMainLine: Optional[float] = None
    carouselMap: Optional[str] = None
    pendingDeployment: Optional[bool] = None
    deploying: Optional[bool] = None
    deployingTimestamp: Optional[datetime] = None
    scheduledDeploymentTimestamp: Optional[datetime] = None
    gameStatus: Optional[str] = None


# 解决 Market / Series / Event 之间的循环引用
Market.model_rebuild()
Series.model_rebuild()


# ---------------------------------------------------------------------------
# 搜索专用 Tag / Profile 模型
# ---------------------------------------------------------------------------


class SearchTag(BaseModel):
    """搜索结果中的标签条目。"""
    id: str
    label: str
    slug: str
    event_count: int


class Profile(BaseModel):
    """用户/交易者公开画像。"""
    model_config = ConfigDict(extra="allow")

    id: str
    name: Optional[str] = None
    user: Optional[int] = None
    referral: Optional[str] = None
    createdBy: Optional[int] = None
    updatedBy: Optional[int] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    utmSource: Optional[str] = None
    utmMedium: Optional[str] = None
    utmCampaign: Optional[str] = None
    utmContent: Optional[str] = None
    utmTerm: Optional[str] = None
    walletActivated: Optional[bool] = None
    pseudonym: Optional[str] = None
    displayUsernamePublic: Optional[bool] = None
    profileImage: Optional[str] = None
    bio: Optional[str] = None
    proxyWallet: Optional[str] = None
    profileImageOptimized: Optional[ImageOptimization] = None
    isCloseOnly: Optional[bool] = None
    isCertReq: Optional[bool] = None
    certReqDate: Optional[datetime] = None


# ---------------------------------------------------------------------------
# 分页信息
# ---------------------------------------------------------------------------


class Pagination(BaseModel):
    """分页元数据。"""
    hasMore: bool
    totalResults: int


# ---------------------------------------------------------------------------
# 请求参数模型
# ---------------------------------------------------------------------------


class PublicSearchRequest(BaseModel):
    """
    GET /public-search 查询参数。

    用法示例:
        params = PublicSearchRequest(q="bitcoin", limit_per_type=5)
        resp = httpx.get(
            "https://gamma-api.polymarket.com/public-search",
            params=params.model_dump(exclude_none=True),
        )
    """
    q: str = Field(..., description="搜索关键词（必填）")
    cache: Optional[bool] = Field(None, description="是否使用缓存结果")
    events_status: Optional[str] = Field(None, description="事件状态过滤，如 'active'/'closed'")
    limit_per_type: Optional[int] = Field(None, description="每种类型返回的最大条数")
    page: Optional[int] = Field(None, description="分页页码（从 1 开始）")
    events_tag: Optional[List[str]] = Field(None, description="按标签 slug 过滤事件")
    keep_closed_markets: Optional[int] = Field(None, description="是否保留已关闭的市场（1=保留）")
    sort: Optional[str] = Field(None, description="排序字段，如 'volume'/'liquidity'")
    ascending: Optional[bool] = Field(None, description="是否升序排列")
    search_tags: Optional[bool] = Field(None, description="是否在结果中包含标签")
    search_profiles: Optional[bool] = Field(None, description="是否在结果中包含用户画像")
    recurrence: Optional[str] = Field(None, description="系列重复频率过滤")
    exclude_tag_id: Optional[List[int]] = Field(None, description="排除指定标签 ID 的事件")
    optimized: Optional[bool] = Field(None, description="是否返回优化后的图片字段")

    @field_validator("q")
    @classmethod
    def _validate_q(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("q must not be empty")
        return v

    @classmethod
    def build(
            cls,
            q: str,
            cache: Optional[bool] = None,
            events_status: Optional[str] = None,
            limit_per_type: Optional[int] = None,
            page: Optional[int] = None,
            events_tag: Optional[List[str]] = None,
            keep_closed_markets: Optional[int] = None,
            sort: Optional[str] = None,
            ascending: Optional[bool] = None,
            search_tags: Optional[bool] = None,
            search_profiles: Optional[bool] = None,
            recurrence: Optional[str] = None,
            exclude_tag_id: Optional[List[int]] = None,
            optimized: Optional[bool] = None,
    ) -> "PublicSearchRequest":
        """兼容 IDE 的构造辅助函数：显式将可选字段设为默认 None，
        可以在 IDE 中避免参数未填提示。
        """
        return cls(
            q=q,
            cache=cache,
            events_status=events_status,
            limit_per_type=limit_per_type,
            page=page,
            events_tag=events_tag,
            keep_closed_markets=keep_closed_markets,
            sort=sort,
            ascending=ascending,
            search_tags=search_tags,
            search_profiles=search_profiles,
            recurrence=recurrence,
            exclude_tag_id=exclude_tag_id,
            optimized=optimized,
        )


# ---------------------------------------------------------------------------
# 响应模型
# ---------------------------------------------------------------------------


class PublicSearchResponse(BaseModel):
    """
    GET /public-search 响应体。

    包含三类搜索结果：
    - events：预测事件列表
    - tags：标签列表
    - profiles：用户画像列表
    以及 pagination 分页信息。
    """
    events: Optional[List[Event]] = None
    tags: Optional[List[SearchTag]] = None
    profiles: Optional[List[Profile]] = None
    pagination: Optional[Pagination] = None

    @classmethod
    def from_api_response(cls, data: Any) -> "PublicSearchResponse":
        """从 API 原始响应字典解析为模型实例。

        兼容常见返回格式：
        - 标准对象根：{"events": [...], "tags": [...], "profiles": [...], "pagination": {...}}
        - 直接事件数组：[ {...}, {...} ]
        - 包裹在 data 字段：{"data": [ {...}, ... ]}
        """
        if isinstance(data, list):
            # 直接返回的事件数组
            return cls(events=[Event.model_validate(item) for item in data])

        if isinstance(data, dict):
            # 标准返回结构
            if any(k in data for k in ("events", "tags", "profiles", "pagination")):
                return cls.model_validate(data)

            # 包裹 data: [...]
            maybe = data.get("data")
            if isinstance(maybe, list):
                return cls(events=[Event.model_validate(item) for item in maybe])

        raise TypeError("Unsupported /public-search response format")


# ---------------------------------------------------------------------------
# 单资源 GET 请求模型（包含 path 标识与常见可选 query 参数）
# ---------------------------------------------------------------------------


class SeriesGetRequest(BaseModel):
    """Request model for GET /series/{id}.

    - `id`: path parameter
    - optional query params are provided as explicit fields to improve IDE discoverability
    """
    id: str
    include_chat: Optional[bool] = None

    @classmethod
    def build(cls, id: str, include_chat: Optional[bool] = None) -> "SeriesGetRequest":
        return cls(id=id, include_chat=include_chat)


class EventGetBySlugRequest(BaseModel):
    """Request model for GET /events/{slug}.

    Fields:
    - `slug`: path parameter
    - `optimized`: whether to return optimized images
    - `include_markets`: include nested markets in response
    """
    slug: str
    include_chat: Optional[bool] = None
    include_template: Optional[bool] = None

    @classmethod
    def build(cls, slug: str, include_chat: Optional[bool] = None,
              include_template: Optional[bool] = None) -> "EventGetBySlugRequest":
        return cls(slug=slug, include_chat=include_chat, include_template=include_template)


class EventGetByIdRequest(BaseModel):
    id: str
    optimized: Optional[bool] = None
    include_markets: Optional[bool] = None

    @classmethod
    def build(cls, id: str, optimized: Optional[bool] = None,
              include_markets: Optional[bool] = None) -> "EventGetByIdRequest":
        return cls(id=id, optimized=optimized, include_markets=include_markets)


class MarketGetBySlugRequest(BaseModel):
    slug: str
    optimized: Optional[bool] = None
    include_event: Optional[bool] = None

    @classmethod
    def build(cls, slug: str, optimized: Optional[bool] = None,
              include_event: Optional[bool] = None) -> "MarketGetBySlugRequest":
        return cls(slug=slug, optimized=optimized, include_event=include_event)


class MarketGetByIdRequest(BaseModel):
    id: str
    optimized: Optional[bool] = None
    include_event: Optional[bool] = None

    @classmethod
    def build(cls, id: str, optimized: Optional[bool] = None,
              include_event: Optional[bool] = None) -> "MarketGetByIdRequest":
        return cls(id=id, optimized=optimized, include_event=include_event)


# ---------------------------------------------------------------------------
# 简单的解析/转换助手（用于 /series, /events, /markets GET 返回）
# ---------------------------------------------------------------------------


def parse_series_response(data: Any) -> Series:
    """Parse API response for a Series GET endpoint into a Series model.

    Accepts either a dict representing the Series, or a wrapper like {"data": {...}}.
    Raises TypeError when the format is unsupported, ValueError when validation fails.
    """
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        payload = data["data"]
    elif isinstance(data, dict):
        payload = data
    else:
        raise TypeError("Unsupported series response format")

    return Series.model_validate(payload)


def parse_event_response(data: Any) -> Event:
    """Parse API response for an Event GET endpoint into an Event model.

    Accepts either a dict representing the Event, or a wrapper like {"data": {...}}.
    """
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        payload = data["data"]
    elif isinstance(data, dict):
        payload = data
    else:
        raise TypeError("Unsupported event response format")

    return Event.model_validate(payload)


def parse_market_response(data: Any) -> Market:
    """Parse API response for a Market GET endpoint into a Market model.

    Accepts either a dict representing the Market, or a wrapper like {"data": {...}}.
    """
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        payload = data["data"]
    elif isinstance(data, dict):
        payload = data
    else:
        raise TypeError("Unsupported market response format")

    return Market.model_validate(payload)
