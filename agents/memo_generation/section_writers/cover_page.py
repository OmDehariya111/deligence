"""
Module: cover_page.py
Agent: Memo Generation Agent
Purpose: Generates the Cover Page (Section 0) of the investment memo.
Inputs: Data dictionary containing company metadata (name, ticker, exchange, etc.).
Outputs: HTML string for the cover page section.
"""
import logging
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)

class Section0Writer:
    def __init__(self, data: dict):
        self.data = data
        
    def generate(self) -> str:
        company_name = self.data.get('company_name', 'N/A')
        ticker = self.data.get('ticker', 'N/A')
        exchange = self.data.get('exchange', 'N/A')
        industry_name = self.data.get('industry_name', 'N/A')
        sic_code = self.data.get('sic_code', 'N/A')
        run_id = self.data.get('run_id', 'N/A')
        
        # Initials logo (up to 3 letters)
        initials = "".join([w[0].upper() for w in company_name.split() if w.isalpha()])[:3]
        if not initials:
            initials = company_name[:3].upper()
            
        report_date = datetime.now().strftime("%B %d, %Y")
        
        html = f"""
        <div class="cover-page">
            <div class="cover-logo">{initials}</div>
            <div class="cover-title">{company_name}</div>
            <div class="cover-subtitle">Investment Due Diligence Memorandum</div>
            
            <div class="cover-meta">
                <div class="cover-meta-item">
                    <span class="cover-meta-label">Ticker</span>
                    <span class="cover-meta-value">{ticker}</span>
                </div>
                <div class="cover-meta-item">
                    <span class="cover-meta-label">Exchange</span>
                    <span class="cover-meta-value">{exchange}</span>
                </div>
                <div class="cover-meta-item">
                    <span class="cover-meta-label">Industry / SIC</span>
                    <span class="cover-meta-value">{industry_name} ({sic_code})</span>
                </div>
            </div>
            
            <div class="cover-meta" style="margin-top: 2rem;">
                <div class="cover-meta-item">
                    <span class="cover-meta-label">Report Date</span>
                    <span class="cover-meta-value">{report_date}</span>
                </div>
                <div class="cover-meta-item">
                    <span class="cover-meta-label">Run ID</span>
                    <span class="cover-meta-value">{run_id}</span>
                </div>
                <div class="cover-meta-item">
                    <span class="cover-meta-label">Platform</span>
                    <span class="cover-meta-value">DeligenX</span>
                </div>
            </div>
            
            <div class="cover-confidential">
                Confidential — For Authorized Recipients Only
            </div>
        </div>
        """
        return html
