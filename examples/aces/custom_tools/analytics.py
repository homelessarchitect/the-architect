"""Analytics — performance tracking and data-driven content optimization."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def record_published(
        piece_id: Annotated[str, "UUID of the ContentPiece that was published"],
        platform: Annotated[str, "Platform where the piece was published"],
        published_at: Annotated[str, "ISO datetime when it went live e.g. 2026-05-18T14:00:00Z"],
        url: Annotated[str | None, "Public URL of the published post"] = None,
        platform_post_id: Annotated[
            str | None, "Native platform post ID for metric fetching"
        ] = None,
    ) -> dict[str, Any]:
        """Register a ContentPiece as published. Transitions piece status to 'published'.
        Only one PublishedContent record per piece — returns error if already recorded.
        """
        from sqlalchemy import select

        from factory.core.database import get_session_factory
        from factory.generated.aces.content_piece.repository import ContentPieceRepository
        from factory.generated.aces.published_content.models import PublishedContent
        from factory.generated.aces.published_content.repository import (
            PublishedContentRepository,
        )
        from factory.generated.aces.published_content.serialize import (
            serialize_published_content,
        )

        factory = get_session_factory()
        async with factory() as session:
            existing_result = await session.execute(
                select(PublishedContent).where(
                    PublishedContent.piece_id == UUID(piece_id)
                )
            )
            if existing_result.scalars().first():
                return {
                    "error": "already_published",
                    "detail": f"ContentPiece {piece_id} already has a PublishedContent record.",
                }

            pub = PublishedContent(
                piece_id=UUID(piece_id),
                platform=platform,
                published_at=datetime.fromisoformat(published_at),
                url=url,
                platform_post_id=platform_post_id,
            )
            pub_repo = PublishedContentRepository(session)
            pub = await pub_repo.add(pub)

            piece_repo = ContentPieceRepository(session)
            piece = await piece_repo.get(UUID(piece_id))
            if piece:
                piece.status = "published"
                await session.flush()

            await session.commit()
            await session.refresh(pub)

        return {"published": serialize_published_content(pub)}

    @mcp.tool()
    async def log_metrics(
        published_id: Annotated[str, "UUID of the PublishedContent record"],
        captured_at: Annotated[
            str, "ISO datetime when metrics were captured e.g. 2026-05-20T10:00:00Z"
        ],
        reach: Annotated[int, "Total unique accounts reached"] = 0,
        impressions: Annotated[int, "Total impressions"] = 0,
        engagement_rate: Annotated[float, "Engagement rate as percentage 0-100"] = 0.0,
        likes: Annotated[int, "Number of likes"] = 0,
        comments: Annotated[int, "Number of comments"] = 0,
        shares: Annotated[int, "Number of shares"] = 0,
        saves: Annotated[int, "Number of saves/bookmarks"] = 0,
        clicks: Annotated[int, "Number of link clicks"] = 0,
        completion_rate: Annotated[
            float | None, "Video completion rate 0-100 (video only)"
        ] = None,
        conversions: Annotated[int | None, "Conversion events if tracked"] = None,
    ) -> dict[str, Any]:
        """Log a performance metrics snapshot for a published piece.
        Can be called multiple times — each call creates a new snapshot.
        """
        from factory.core.database import get_session_factory
        from factory.generated.aces.content_metric.models import ContentMetric
        from factory.generated.aces.content_metric.repository import ContentMetricRepository
        from factory.generated.aces.content_metric.serialize import serialize_content_metric

        factory = get_session_factory()
        async with factory() as session:
            metric = ContentMetric(
                published_id=UUID(published_id),
                reach=reach,
                impressions=impressions,
                engagement_rate=engagement_rate,
                likes=likes,
                comments=comments,
                shares=shares,
                saves=saves,
                clicks=clicks,
                completion_rate=completion_rate,
                conversions=conversions,
                captured_at=datetime.fromisoformat(captured_at),
            )
            metric_repo = ContentMetricRepository(session)
            metric = await metric_repo.add(metric)
            await session.commit()
            await session.refresh(metric)

        return {"metrics": serialize_content_metric(metric)}

    @mcp.tool()
    async def analyze_performance(
        brand_id: Annotated[str, "UUID of the brand to analyze"],
        period_start: Annotated[
            str, "Start of analysis period ISO date YYYY-MM-DD (empty for all time)"
        ] = "",
        period_end: Annotated[
            str, "End of analysis period ISO date YYYY-MM-DD (empty for all time)"
        ] = "",
        platform: Annotated[str | None, "Filter by platform (omit for all)"] = None,
    ) -> dict[str, Any]:
        """Fetch aggregated performance data for all published pieces of a brand.
        Returns per-piece metrics history for Claude to identify patterns and top performers.
        """
        from sqlalchemy import select

        from factory.core.database import get_session_factory
        from factory.generated.aces.content_metric.models import ContentMetric
        from factory.generated.aces.content_piece.models import ContentPiece
        from factory.generated.aces.published_content.models import PublishedContent

        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(PublishedContent, ContentPiece)
                .join(ContentPiece, PublishedContent.piece_id == ContentPiece.id)
                .where(ContentPiece.brand_id == UUID(brand_id))
            )
            if platform:
                stmt = stmt.where(PublishedContent.platform == platform)
            if period_start:
                stmt = stmt.where(
                    PublishedContent.published_at >= datetime.fromisoformat(period_start)
                )
            if period_end:
                stmt = stmt.where(
                    PublishedContent.published_at <= datetime.fromisoformat(period_end)
                )

            result = await session.execute(stmt)
            rows = result.all()

            pieces_data = []
            for pub, piece in rows:
                metrics_result = await session.execute(
                    select(ContentMetric)
                    .where(ContentMetric.published_id == pub.id)
                    .order_by(ContentMetric.captured_at.desc())
                )
                metrics = list(metrics_result.scalars().all())

                latest = metrics[0] if metrics else None
                pieces_data.append(
                    {
                        "piece_id": str(piece.id),
                        "title": piece.title,
                        "format": piece.format,
                        "platform": pub.platform,
                        "published_at": pub.published_at.isoformat(),
                        "latest_metrics": (
                            {
                                "reach": latest.reach,
                                "impressions": latest.impressions,
                                "engagement_rate": latest.engagement_rate,
                                "likes": latest.likes,
                                "comments": latest.comments,
                                "shares": latest.shares,
                                "saves": latest.saves,
                                "clicks": latest.clicks,
                                "completion_rate": latest.completion_rate,
                            }
                            if latest
                            else None
                        ),
                        "metrics_snapshots": len(metrics),
                    }
                )

        return {
            "brand_id": brand_id,
            "period": {"start": period_start or "all", "end": period_end or "all"},
            "platform_filter": platform,
            "pieces": pieces_data,
            "total_pieces": len(pieces_data),
        }

    @mcp.tool()
    async def identify_best_performers(
        brand_id: Annotated[str, "UUID of the brand to analyze"],
        metric: Annotated[
            str,
            "Metric to rank by: reach|impressions|engagement_rate|likes|comments|shares|saves|clicks|completion_rate",
        ],
        period_start: Annotated[str, "Start ISO date (empty for all time)"] = "",
        period_end: Annotated[str, "End ISO date (empty for all time)"] = "",
        limit: Annotated[int, "Max results to return (default 10)"] = 10,
    ) -> dict[str, Any]:
        """Identify top-performing content pieces ranked by a specific metric.
        Uses the latest metrics snapshot per piece. Useful for spotting what content
        type drives the most engagement.
        """
        perf = await analyze_performance(brand_id, period_start, period_end)
        if "error" in perf:
            return perf

        pieces = perf["pieces"]
        ranked = [p for p in pieces if p["latest_metrics"] is not None]
        ranked.sort(key=lambda p: p["latest_metrics"].get(metric, 0) or 0, reverse=True)

        return {
            "metric": metric,
            "top_performers": ranked[:limit],
            "total_analyzed": len(ranked),
        }

    @mcp.tool()
    async def suggest_optimizations(
        brand_id: Annotated[str, "UUID of the brand to analyze for optimization"],
    ) -> dict[str, Any]:
        """Context-fetcher for content optimization analysis. Returns all performance data
        plus a reasoning_prompt that instructs Claude to identify patterns and suggest
        actionable next-cycle optimizations.
        """
        perf = await analyze_performance(brand_id)
        if "error" in perf:
            return perf

        reasoning_prompt = (
            f"Analyze the performance data for this brand ({len(perf['pieces'])} pieces). "
            f"Identify: (1) top formats by engagement rate, "
            f"(2) best-performing platforms, "
            f"(3) video completion rate patterns (which archetypes keep viewers?), "
            f"(4) underperforming content pillars, "
            f"(5) optimal posting patterns if date data suggests any. "
            f"Suggest 3-5 actionable optimizations for the next content cycle."
        )

        return {**perf, "reasoning_prompt": reasoning_prompt}
