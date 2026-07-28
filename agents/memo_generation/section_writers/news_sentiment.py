"""
Module:  news_sentiment.py
Agent:   Memo Generation Agent
Purpose: Generates Section 12: News Sentiment & Media Analysis.
Inputs:  data dictionary containing news_sentiment and market_intel_summary.
Outputs: HTML string for the section.
"""

import logging
from collections import defaultdict
from agents.memo_generation import chart_engine

logger = logging.getLogger(__name__)

class Section12Writer:
    def __init__(self, data: dict):
        self.data = data

    def generate(self) -> str:
        logger.info("Generating Section 12: News Sentiment & Media Analysis")
        news = self.data.get('news_sentiment', [])
        summary = self.data.get('market_intel_summary', {}).get('NEWS_SENTIMENT', {})
        
        narrative = summary.get('llm_narrative', 'N/A')
        trend = summary.get('sentiment_trend', 'N/A')
        
        total_articles = len(news)
        pos = sum(1 for n in news if n.get('vader_label') == 'POSITIVE')
        neu = sum(1 for n in news if n.get('vader_label') == 'NEUTRAL')
        neg = sum(1 for n in news if n.get('vader_label') == 'NEGATIVE')
        
        crisis_flags = [n for n in news if n.get('crisis_flag')]
        
        crisis_html = ""
        if crisis_flags:
            crisis_html = f"""
            <div class="callout callout-danger">
                <h4>Crisis Alert</h4>
                <p>Detected {len(crisis_flags)} crisis flags in recent news.</p>
            </div>
            """
            
        # Charts
        pie_html = chart_engine.pie_chart(
            labels=['Positive', 'Neutral', 'Negative'],
            data=[pos, neu, neg],
            title="Sentiment Breakdown",
            colors=['#10B981', '#94A3B8', '#EF4444']
        )
        
        daily_scores = defaultdict(list)
        for n in news:
            raw_date = n.get('published_date', 'Unknown')
            if raw_date != 'Unknown':
                date = str(raw_date)[:10] # extract YYYY-MM-DD
                daily_scores[date].append(n.get('vader_score', 0))
                
        sorted_dates = sorted(daily_scores.keys())
        avg_scores = [sum(daily_scores[d])/len(daily_scores[d]) for d in sorted_dates]
        
        timeline_html = chart_engine.line_chart(
            labels=sorted_dates,
            datasets=[{"label": "Avg VADER Score", "data": avg_scores, "color": "#4A90D9"}],
            title="30-Day Sentiment Timeline",
            y_label="VADER Score"
        )
        
        # Tables for Top 10 Positive / Negative
        sorted_news = sorted(news, key=lambda x: x.get('vader_score', 0), reverse=True)
        top_positive = [n for n in sorted_news if n.get('vader_score', 0) > 0][:10]
        top_negative = [n for n in reversed(sorted_news) if n.get('vader_score', 0) < 0][:10]
        
        def render_news_rows(news_list):
            r = []
            for n in news_list:
                d = str(n.get('published_date', 'N/A'))[:10]
                r.append(f"""
                <tr>
                    <td>{d}</td>
                    <td>{n.get('source_name', 'N/A')}</td>
                    <td>{n.get('headline', 'N/A')}</td>
                    <td><span class="badge {'badge-proceed' if n.get('vader_score', 0)>0 else 'badge-critical'}">{n.get('vader_label', 'N/A')}</span></td>
                    <td class="num">{n.get('vader_score', 0):.2f}</td>
                </tr>
                """)
            if not r:
                return "<tr><td colspan='5' class='text-center text-muted'>No news available</td></tr>"
            return ''.join(r)
            
        pos_rows = render_news_rows(top_positive)
        neg_rows = render_news_rows(top_negative)
            
        html = f"""
        <div class="section" id="section-12">
            <div class="section-header">
                <div class="section-number">12</div>
                <h2>News Sentiment & Media Analysis</h2>
            </div>
            
            <div class="grid-2">
                <div class="card">
                    <div class="card-header">Sentiment Overview</div>
                    <div class="card-value">{total_articles}</div>
                    <div class="card-footer">Total Articles | Trend: {trend}</div>
                </div>
            </div>
            
            <div class="content-block">
                <h4>Analysis Narrative</h4>
                <p>{narrative}</p>
            </div>
            
            {crisis_html}
            
            <div class="grid-2">
                {pie_html}
                {timeline_html}
            </div>
            
            <h3>Top 10 Positive News</h3>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Source</th>
                            <th>Headline</th>
                            <th>Sentiment</th>
                            <th class="num">Score</th>
                        </tr>
                    </thead>
                    <tbody>
                        {pos_rows}
                    </tbody>
                </table>
            </div>

            <h3 style="margin-top:24px;">Top 10 Negative News</h3>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Source</th>
                            <th>Headline</th>
                            <th>Sentiment</th>
                            <th class="num">Score</th>
                        </tr>
                    </thead>
                    <tbody>
                        {neg_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """
        return html
