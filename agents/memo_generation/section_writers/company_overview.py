"""
Module: company_overview.py
Agent: Memo Generation Agent
Purpose: Generates the Company & Business Overview (Section 2) of the investment memo.
Inputs: Data dictionary containing ingestion summaries and chromadb chunks.
Outputs: HTML string for the company overview section.
"""
import logging
from typing import Any
from agents.memo_generation import chart_engine
from agents.memo_generation import llm_narrator

logger = logging.getLogger(__name__)

class Section2Writer:
    def __init__(self, data: dict):
        self.data = data
        
    def generate(self) -> str:
        c_name = self.data.get('company_name', 'N/A')
        cik = self.data.get('cik', 'N/A')
        sic = self.data.get('sic_code', 'N/A')
        exchange = self.data.get('exchange', 'N/A')
        fye = self.data.get('fiscal_year_end', 'N/A')
        state = self.data.get('state_of_incorp', 'N/A')
        
        ingestion = self.data.get('ingestion_summary', {})
        vdb_stats = self.data.get('vector_db_stats', {})
        total_chunks = vdb_stats.get('total_chunks', 0) if isinstance(vdb_stats, dict) else 0
        ingestion_status = ingestion.get('status', 'N/A')
        duration = self.data.get('ingestion_duration', 'N/A')
        
        fields_with_data = self.data.get('fields_with_data', 0)
        fields_missing = self.data.get('fields_missing', 0)
        total_fields = self.data.get('total_fields', 0)
        coverage_pct = (fields_with_data / total_fields * 100) if total_fields > 0 else 0
        
        gauge_html = chart_engine.gauge_svg(score=coverage_pct, max_score=100, label="Data Coverage %")
        
        # Map ChromaDB keys for narrator
        narrator_data = dict(self.data)
        narrator_data['business_description_chunks'] = self.data.get('chromadb_item_1', '')
        narrator_data['mda_chunks'] = self.data.get('chromadb_item_7', '')
        narrative = llm_narrator.generate_company_overview_narrative(narrator_data)
        
        vdb_stats = self.data.get('vector_db_stats', self.data.get('vector_database_stats', {}))
        total_chunks = vdb_stats.get('total_chunks', 0) if isinstance(vdb_stats, dict) else 0

        filings_processed = vdb_stats.get('filings_processed', {}) if isinstance(vdb_stats, dict) else {}
        filing_rows = ""
        
        # Map filing types to their chunk count keys
        chunk_keys = {
            '10-K': 'chunks_from_10k',
            '10-Q': 'chunks_from_10q',
            '8-K': 'chunks_from_8k',
            'DEF_14A': 'chunks_from_proxy'
        }
        
        for f_type, count in filings_processed.items():
            if f_type == 'failed' or count == 0:
                continue
            chunk_key = chunk_keys.get(f_type, '')
            f_chunks = vdb_stats.get(chunk_key, 'N/A') if chunk_key else 'N/A'
            filing_rows += f"<tr><td>{f_type}</td><td class='num'>{count} files</td><td class='num'>{f_chunks}</td></tr>"
            
        if not filing_rows:
            filing_rows = "<tr><td colspan='3' class='text-center text-muted'>No filing data available</td></tr>"
            
        html = f"""
        <div class="section" id="section-2">
            <div class="section-header">
                <span class="section-number">2</span>
                <h2>Company & Business Overview</h2>
            </div>
            
            <div class="card" style="margin-bottom: 1rem;">
                <div class="card-header">Business Description</div>
                <div class="narrative-content">
                    {narrative}
                </div>
            </div>
            
            <div class="grid-2">
                <div class="card">
                    <div class="card-header">Corporate Identity</div>
                    <table class="compact">
                        <tbody>
                            <tr><td><strong>Name</strong></td><td>{c_name}</td></tr>
                            <tr><td><strong>CIK</strong></td><td>{cik}</td></tr>
                            <tr><td><strong>SIC</strong></td><td>{sic}</td></tr>
                            <tr><td><strong>Exchange</strong></td><td>{exchange}</td></tr>
                            <tr><td><strong>State of Inc.</strong></td><td>{state}</td></tr>
                            <tr><td><strong>Fiscal Year End</strong></td><td>{fye}</td></tr>
                        </tbody>
                    </table>
                </div>
                
                <div class="card">
                    <div class="card-header">Data Coverage & Ingestion</div>
                    <div style="display: flex; gap: 1rem; align-items: center;">
                        <div style="flex: 1;">
                            {gauge_html}
                        </div>
                        <div style="flex: 2;">
                            <ul style="list-style-type: none; padding: 0; font-size: 0.85rem;">
                                <li><strong>Status:</strong> {ingestion_status}</li>
                                <li><strong>Duration:</strong> {duration}s</li>
                                <li><strong>Total Chunks:</strong> {total_chunks}</li>
                                <li><strong>Fields Found:</strong> {fields_with_data}</li>
                                <li><strong>Missing:</strong> {fields_missing}</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card" style="margin-top: 1rem;">
                <div class="card-header">Filing History</div>
                <table class="compact">
                    <thead>
                        <tr><th>Filing Type</th><th class="num">Files Processed</th><th class="num">Chunks Extracted</th></tr>
                    </thead>
                    <tbody>
                        {filing_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """
        return html
