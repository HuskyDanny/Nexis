"""Real data sources — news from Alpha Vantage, stock data from Yahoo Finance.

Falls back to mock data when APIs are unavailable or rate-limited.
"""

from typing import Any

import httpx

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger("data_sources")


async def fetch_real_news(limit: int = 10, topics: str = "") -> list[dict]:
    """Fetch news — Perigon first (AI-native, pre-classified), Alpha Vantage fallback."""
    # Try Perigon first (cached, rate-limited)
    try:
        from src.services.perigon import fetch_perigon_news

        query = topics if topics else "economy markets geopolitical finance"
        perigon_news = await fetch_perigon_news(query=query, size=limit)
        if perigon_news:
            log.info(
                "Using Perigon news (%d articles, pre-classified)", len(perigon_news)
            )
            return perigon_news
    except Exception as e:
        log.debug("Perigon unavailable, falling back to Alpha Vantage: %s", e)

    return await _fetch_alpha_vantage_news(limit=limit, topics=topics)


async def _fetch_alpha_vantage_news(limit: int = 10, topics: str = "") -> list[dict]:
    """Fallback: Fetch news from Alpha Vantage NEWS_SENTIMENT endpoint."""
    try:
        params: dict[str, Any] = {
            "function": "NEWS_SENTIMENT",
            "apikey": settings.alpha_vantage_api_key,
            "limit": limit,
            "sort": "LATEST",
        }
        if topics:
            params["topics"] = topics

        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get("https://www.alphavantage.co/query", params=params)
            data = r.json()

        if "feed" not in data:
            log.warning("Alpha Vantage returned no feed: %s", str(data)[:100])
            return []

        articles = []
        for article in data["feed"][:limit]:
            sentiment = float(article.get("overall_sentiment_score", 0))
            direction = (
                "bullish"
                if sentiment > 0.15
                else "bearish" if sentiment < -0.15 else "neutral"
            )
            confidence = min(abs(sentiment) * 200, 95)

            # Extract sector/topic tags
            topics_list = [t.get("topic", "") for t in article.get("topics", [])]

            articles.append(
                {
                    "id": f"av-{hash(article['url']) % 100000:05d}",
                    "type": "news_event",
                    "title": article.get("title", ""),
                    "source": article.get("source", "Unknown"),
                    "url": article.get("url", ""),
                    "summary": article.get("summary", "")[:200],
                    "published_at": article.get("time_published", ""),
                    "direction": direction,
                    "confidence": round(confidence),
                    "sectors": topics_list[:3],
                    "sentiment_score": sentiment,
                }
            )

        log.info("Fetched %d real news articles from Alpha Vantage", len(articles))
        return articles

    except Exception as e:
        log.error("Alpha Vantage news fetch failed: %s", e)
        return []


def fetch_real_stocks(tickers: list[str] | None = None) -> list[dict]:
    """Fetch stock data from Yahoo Finance. No API key needed."""
    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance not installed — pip install yfinance")
        return []

    if not tickers:
        # Default value screening universe
        tickers = [
            "JPM",
            "BAC",
            "INTC",
            "PFE",
            "XOM",
            "NKE",
            "DIS",
            "PYPL",
            "CVS",
            "T",
            "VZ",
            "MRK",
            "BMY",
            "GM",
            "F",
            "WBA",
            "PARA",
            "SNAP",
        ]

    stocks = []
    try:
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                price = info.get("currentPrice", info.get("regularMarketPrice", 0))
                high52 = info.get("fiftyTwoWeekHigh", 0)

                if not price or not high52 or high52 == 0:
                    continue

                discount = round((1 - price / high52) * 100, 1)
                if discount < 15:  # Only stocks ≥15% off 52-week high
                    continue

                pe = info.get("trailingPE")
                pb = info.get("priceToBook")
                div_yield = info.get("dividendYield", 0) or 0

                direction = "bullish" if discount >= 30 else "neutral"
                confidence = min(round(discount * 1.5 + 10), 95)

                stocks.append(
                    {
                        "id": f"yf-{ticker.lower()}",
                        "type": "value_opportunity",
                        "ticker": ticker,
                        "price": round(price, 2),
                        "high_52w": round(high52, 2),
                        "discount_pct": discount,
                        "pe_ratio": round(pe, 1) if pe else None,
                        "pb_ratio": round(pb, 2) if pb else None,
                        "div_yield": round(div_yield * 100, 1),
                        "sector": info.get("sector", "Unknown"),
                        "summary": f"{ticker} at {discount}% discount, PE={f'{pe:.1f}' if pe else 'N/A'}",
                        "direction": direction,
                        "confidence": confidence,
                    }
                )
            except Exception as e:
                log.debug("Failed to fetch %s: %s", ticker, e)
                continue

        log.info(
            "Fetched %d value stocks from Yahoo Finance (from %d tickers)",
            len(stocks),
            len(tickers),
        )
        return stocks

    except Exception as e:
        log.error("Yahoo Finance fetch failed: %s", e)
        return []
