"""Prompt templates for agents and tools.

Context Engineering Best Practices (2025):
- Clear role and persona definition
- Structured context with markers
- Explicit output format requirements
- Guardrails and constraints
- Support for prompt chaining

Reference: https://www.promptingguide.ai/guides/context-engineering-guide
"""
from typing import List, Dict, Optional


class Prompts:
    """Centralized prompt templates with f-string parameters.

    SHARED CONSTANTS:
    =================
    - HTML_OUTPUT_FORMAT: Include this in any agent that needs HTML output

    FUNCTION-TO-PROMPT MAPPING:
    ===========================
    - oip_assistant_system()     -> Used by: root_agent in agent.py (main system prompt)
    - format_rag_context()       -> Used by: search_oip_documents tool (formats retrieved docs)
    - rag_qa_prompt()            -> Used by: direct LLM calls outside ADK (optional)
    - rag_qa_with_history()      -> Used by: multi-turn conversations (optional)
    - query_rewrite_prompt()     -> Used by: advanced RAG pipeline (optional)
    - query_expansion_prompt()   -> Used by: fusion retrieval (optional)
    - query_classification_prompt() -> Used by: adaptive retrieval (optional)
    - summarize_chunk_prompt()   -> Used by: long document summarization (optional)
    - synthesize_documents_prompt() -> Used by: multi-doc synthesis (optional)
    - no_results_response()      -> Used by: rag_tool.py when no docs found
    - error_response()           -> Used by: rag_tool.py on errors
    - extract_data_prompt()      -> Used by: future chart/data features
    """

    # =========================================================================
    # SHARED OUTPUT FORMAT - Reuse in all agent instructions
    # =========================================================================
    HTML_OUTPUT_FORMAT = """
<OUTPUT_FORMAT>
You MUST format ALL responses using clean HTML. NEVER use markdown (**bold**, *italic*, etc.).

REQUIRED HTML TAGS:
- <p>text</p> — every paragraph (never bare text)
- <strong>text</strong> — key terms, counts, labels, status names
- <em>text</em> — percentages, descriptions, recommendations
- <ul><li>item</li></ul> — bullet lists (USE FOR ALL breakdowns)
- <ol><li>item</li></ol> — numbered steps
- <u>text</u> — underline critical values or important warnings

STYLING FOR VISUAL POLISH:
- <span style='color:#1a73e8'><strong>Section Title:</strong></span> — blue bold for section headers
- <span style='color:#1a73e8'>important term</span> — blue accent for key values or highlights
- Use color spans for status values (see color codes below)
- Use <u> to underline critical numbers like SLA breaches or completion rates

STRUCTURE EVERY RESPONSE AS:
1. Brief summary sentence in <p> with the total count highlighted
2. Bullet list <ul> with color-coded status breakdown
3. Warnings or recommendations in closing <p>

FOR TICKET STATUS RESPONSES (follow this exact pattern):
<p>You have <span style='color:#1a73e8; font-weight:600'>19 tickets</span> in the <strong>ANB</strong> project:</p>

<p><span style='color:#1a73e8'><strong>Status Breakdown:</strong></span></p>
<ul>
<li><span style='color:#3b82f6'><strong>Open:</strong> 12</span></li>
<li><span style='color:#f59e0b'><strong>Suspended:</strong> 5</span></li>
<li><span style='color:#22c55e'><strong>Completed:</strong> 2</span> <em>(<u>10.53%</u> completion rate)</em></li>
<li><span style='color:#8b5cf6'><strong>Pending Approval:</strong> 2</span></li>
</ul>
<p><span style='color:#dc2626'>⚠️ <u>12 tickets</u> have breached their SLA deadlines.</span></p>
<p><em>Focus on closing open tickets to improve your completion rate.</em></p>

COMMUNICATION RULES:
- NEVER mention ACTIVE_TEAM_FILTER, ACTIVE_PROJECT_FILTER, or any internal tags
- NEVER expose database column names or developer terms
- Keep language professional and user-friendly
</OUTPUT_FORMAT>
"""

    # =========================================================================
    # AGENT SYSTEM PROMPTS
    # =========================================================================

    @staticmethod
    def oip_assistant_system() -> str:
        """Main OIP Assistant system prompt for Google ADK agent.

        USED BY: root_agent (oip_expert sub-agent) in my_agent/agent.py
        CONTROLS: Overall response style, length, and behavior

        PROMPT STRUCTURE: Uses ReAct pattern (Reason + Act)
        - Thought: Analyze query intent and plan retrieval
        - Action: Use search_oip_documents tool
        - Observation: Process retrieved context
        - Response: Generate formatted HTML output
        """
        return """<PERSONA>
You are a professional, knowledgeable assistant for the Ebttikar Operations Intelligence Platform (OIP).
You communicate clearly and structure information so it's easy to scan and understand.
</PERSONA>

<INSTRUCTIONS>
- ALWAYS use search_oip_documents tool FIRST to retrieve information
- Base answers ONLY on retrieved context — never fabricate
- If no info found, say: "I don't have that information in OIP docs."
- Support English and Arabic queries — respond in the user's language
- Do NOT mention source documents, filenames, or internal technical details
- NEVER mention ACTIVE_TEAM_FILTER, ACTIVE_PROJECT_FILTER, ACTIVE_REGION_FILTER or any internal system tags
- NEVER expose database columns, stored procedure names, or developer terms
</INSTRUCTIONS>

<OUTPUT_FORMAT>
You MUST format ALL responses using clean HTML. NEVER use markdown syntax like **bold** or *italic*.

REQUIRED STRUCTURE FOR EVERY RESPONSE:
1. Start with a brief summary sentence wrapped in <p>
2. Use <ul> bullet lists for ALL details (this is mandatory — never write plain text lists)
3. Bold key terms with <strong> and use <em> for secondary emphasis
4. End with a brief closing <p> if helpful

HTML TAGS TO USE:
- <p>text</p> — every paragraph
- <strong>text</strong> — key terms, feature names, labels (renders as bold)
- <em>text</em> — descriptions, secondary info
- <ul><li>item</li></ul> — bullet lists (USE GENEROUSLY for readability)
- <ol><li>item</li></ol> — numbered steps
- <br> — line breaks

STYLING FOR VISUAL APPEAL:
- Use <span style='color:#1a73e8'> for section headers and important category labels (blue accent)
- Use <span style='color:#1a73e8'><strong>text</strong></span> to make section titles pop in blue + bold
- Use <strong> for feature names and key terms within bullet items
- Use <em> for definitions, descriptions, and technical terms in parentheses
- Use <u>text</u> sparingly to underline critical terms or warnings the user should notice
- Every list item should follow: <li><strong>Label</strong> — Description text</li>

EXAMPLE RESPONSE — DETAILED (follow this pattern closely):
<p><strong>Daily Activity Approval</strong> in OIP ensures data integrity through structured workflows where engineers submit logs for <u>Team Lead review</u> before management visibility.</p>

<p><span style='color:#1a73e8'><strong>Key Workflow Elements:</strong></span></p>
<ul>
<li><strong>Log Entry</strong> — Engineers use a spreadsheet-style interface to input daily activities including <em>Site Name, Ticket Number, Time Started/Ended</em>, and Remarks</li>
<li><strong>Approval Chain</strong> — Logs require <u>Team Lead approval</u> before becoming visible to management</li>
<li><strong>Visibility Rule</strong> — Pending logs are hidden from management until approved, ensuring data accuracy</li>
<li><strong>Delegation</strong> — Supports temporary reassignment of approvals via a built-in system</li>
<li><strong>Notifications</strong> — Alerts sent via <em>email</em> or <em>WhatsApp</em> for pending approvals</li>
</ul>

<p>This is part of <span style='color:#1a73e8'><strong>Phase One</strong></span> implementation, centralizing monitoring and productivity tracking across all teams.</p>

EXAMPLE RESPONSE — SHORT:
<p><strong>OIP</strong> (<em>Operations Intelligence Platform</em>) is a centralized system for managing tickets, <span style='color:#1a73e8'>SLA monitoring</span>, and approval workflows across Ebttikar's operations.</p>

EXAMPLE RESPONSE — MULTI-SECTION:
<p><strong>Ticket Management</strong> in OIP covers the full lifecycle from creation to closure.</p>

<p><span style='color:#1a73e8'><strong>Ticket Creation:</strong></span></p>
<ul>
<li><strong>Sources</strong> — Created from <em>client requests</em>, internal needs, or <u>bulk upload</u></li>
<li><strong>Assignment</strong> — Auto-assigned to engineers based on region and team</li>
</ul>

<p><span style='color:#1a73e8'><strong>Ticket Closure:</strong></span></p>
<ul>
<li><strong>Approval Required</strong> — Team Lead must approve before closure</li>
<li><strong>SLA Tracking</strong> — System calculates <em>delay days</em> excluding weekends with a <u>24-hour grace period</u></li>
</ul>
</OUTPUT_FORMAT>

<GUARDRAILS>
- Never make up features not in documentation
- Don't speculate about pricing or timelines
- If outside OIP scope, politely redirect
- Always use HTML formatting — never plain text or markdown
- Never expose internal system details to users
</GUARDRAILS>"""

    # =========================================================================
    # RAG CONTEXT FORMATTING
    # =========================================================================

    @staticmethod
    def format_rag_context(
        results: List[Dict],
        query: str,
        include_scores: bool = True
    ) -> str:
        """Format retrieved documents into structured context.

        USED BY: search_oip_documents() in my_agent/tools/rag_tool.py
        PURPOSE: Wraps retrieved FAISS results in XML tags for LLM consumption

        Args:
            results: List of dicts with 'text', 'source', 'score', 'rank' keys
            query: Original user query (for context)
            include_scores: Whether to show relevance scores

        Returns:
            Formatted context string with clear structure
        """
        if not results:
            return "<NO_DOCUMENTS_FOUND/>"

        context_parts = [
            f"<RETRIEVED_CONTEXT query=\"{query}\" num_results=\"{len(results)}\">"
        ]

        for result in results:
            rank = result.get("rank", "?")
            source = result.get("source", "Unknown")
            text = result.get("text", "")
            score = result.get("score", 0)

            if include_scores:
                header = f"<DOCUMENT rank=\"{rank}\" source=\"{source}\" relevance=\"{score:.2f}\">"
            else:
                header = f"<DOCUMENT rank=\"{rank}\" source=\"{source}\">"

            context_parts.append(f"{header}\n{text}\n</DOCUMENT>")

        context_parts.append("</RETRIEVED_CONTEXT>")

        return "\n\n".join(context_parts)

    # =========================================================================
    # RAG QA PROMPTS (for prompt chaining if needed)
    # =========================================================================

    @staticmethod
    def rag_qa_prompt(context: str, question: str) -> str:
        """Generate answer from retrieved context (for direct LLM calls).

        USED BY: Optional - direct OpenRouter/LLM calls outside ADK
        PURPOSE: Standalone RAG QA without agent framework
        NOT USED BY: ADK agents (they use oip_assistant_system instead)
        """
        return f"""<TASK>
Answer the question based ONLY on the provided context.
</TASK>

<CONTEXT>
{context}
</CONTEXT>

<QUESTION>
{question}
</QUESTION>

<INSTRUCTIONS>
1. Answer based ONLY on information in the context above
2. If the context doesn't contain enough information, say "The provided documents don't contain information about this."
3. Cite sources using [Source: document_name] format
4. Be concise and direct
5. Structure complex answers with bullet points
</INSTRUCTIONS>

<ANSWER>"""

    @staticmethod
    def rag_qa_with_history(
        context: str,
        question: str,
        chat_history: Optional[List[Dict]] = None
    ) -> str:
        """RAG QA prompt with conversation history for follow-up questions.

        USED BY: Optional - multi-turn direct LLM calls
        PURPOSE: Maintains context across conversation turns
        NOT USED BY: ADK agents (ADK handles history internally)
        """
        history_section = ""
        if chat_history:
            history_parts = []
            for msg in chat_history[-5:]:  # Last 5 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_parts.append(f"{role.upper()}: {content}")
            history_section = f"""<CONVERSATION_HISTORY>
{chr(10).join(history_parts)}
</CONVERSATION_HISTORY>

"""

        return f"""{history_section}<CONTEXT>
{context}
</CONTEXT>

<CURRENT_QUESTION>
{question}
</CURRENT_QUESTION>

<INSTRUCTIONS>
1. Consider the conversation history for context
2. Answer based on the retrieved documents
3. Reference previous discussion if relevant
4. Cite sources: [Source: document_name]
</INSTRUCTIONS>

<ANSWER>"""

    # =========================================================================
    # QUERY PROCESSING (for advanced RAG pipelines)
    # =========================================================================

    @staticmethod
    def query_rewrite_prompt(query: str) -> str:
        """Rewrite query for better retrieval (prompt chaining step 1).

        USED BY: Optional - advanced RAG pipeline with query preprocessing
        PURPOSE: Improves retrieval by expanding/clarifying user queries
        """
        return f"""<TASK>
Rewrite the following user query to improve document retrieval.
Make it more specific and include relevant technical terms.
</TASK>

<ORIGINAL_QUERY>
{query}
</ORIGINAL_QUERY>

<INSTRUCTIONS>
- Expand abbreviations
- Add relevant synonyms
- Make implicit context explicit
- Keep the core intent
</INSTRUCTIONS>

<REWRITTEN_QUERY>"""

    @staticmethod
    def query_expansion_prompt(query: str, num_variations: int = 3) -> str:
        """Generate query variations for fusion retrieval.

        USED BY: Optional - hybrid/fusion search implementations
        PURPOSE: Creates multiple query variants for broader retrieval
        """
        return f"""<TASK>
Generate {num_variations} alternative phrasings of this query for document search.
Each variation should capture the same intent but use different words.
</TASK>

<ORIGINAL_QUERY>
{query}
</ORIGINAL_QUERY>

<INSTRUCTIONS>
- Use synonyms and related terms
- Vary sentence structure
- Include technical and non-technical versions
- One query per line
</INSTRUCTIONS>

<ALTERNATIVE_QUERIES>"""

    @staticmethod
    def query_classification_prompt(query: str) -> str:
        """Classify query intent for adaptive retrieval.

        USED BY: Optional - intent-based routing systems
        PURPOSE: Categorizes queries to adjust retrieval strategy
        """
        return f"""<TASK>
Classify the query intent into exactly one category.
</TASK>

<QUERY>
{query}
</QUERY>

<CATEGORIES>
- FACTUAL: Looking for specific facts, definitions, or data
- PROCEDURAL: Asking how to do something, steps, process
- CONCEPTUAL: Asking about concepts, explanations, comparisons
- TROUBLESHOOTING: Asking about problems, errors, debugging
- EXPLORATORY: Open-ended exploration, overview requests
</CATEGORIES>

<CLASSIFICATION>"""

    # =========================================================================
    # SUMMARIZATION (for long contexts)
    # =========================================================================

    @staticmethod
    def summarize_chunk_prompt(text: str, max_sentences: int = 3) -> str:
        """Summarize a single document chunk.

        USED BY: Optional - long document processing
        PURPOSE: Condenses chunks before final synthesis
        """
        return f"""<TASK>
Summarize the following text in {max_sentences} sentences or less.
Preserve key facts, numbers, and technical terms.
</TASK>

<TEXT>
{text}
</TEXT>

<SUMMARY>"""

    @staticmethod
    def synthesize_documents_prompt(documents: List[str]) -> str:
        """Synthesize multiple documents into coherent summary.

        USED BY: Optional - multi-document aggregation
        PURPOSE: Combines multiple sources into unified response
        """
        docs_formatted = "\n\n".join(
            f"<DOC_{i+1}>\n{doc}\n</DOC_{i+1}>"
            for i, doc in enumerate(documents)
        )

        return f"""<TASK>
Synthesize the following documents into a coherent summary.
Identify key themes, agreements, and any contradictions.
</TASK>

<DOCUMENTS>
{docs_formatted}
</DOCUMENTS>

<INSTRUCTIONS>
- Combine information logically
- Note where documents agree or differ
- Preserve important details
- Cite document numbers: [Doc 1], [Doc 2], etc.
</INSTRUCTIONS>

<SYNTHESIS>"""

    # =========================================================================
    # ERROR HANDLING
    # =========================================================================

    @staticmethod
    def no_results_response(query: str) -> str:
        """Response when no documents are found.

        USED BY: search_oip_documents() in my_agent/tools/rag_tool.py
        PURPOSE: Fallback message when FAISS returns empty results
        """
        return f"""I searched the OIP documentation but couldn't find specific information about "{query}".

Possible reasons:
1. The topic isn't covered in the current documentation
2. Try rephrasing with different terms (e.g., technical vs. general)
3. The information might be in a document not yet indexed

Would you like me to help rephrase your question?"""

    @staticmethod
    def error_response(error_type: str, details: str = "") -> str:
        """Response when an error occurs.

        USED BY: search_oip_documents() in my_agent/tools/rag_tool.py
        PURPOSE: User-friendly error messages for system failures
        """
        detail_line = f"\nDetails: {details}" if details else ""
        return f"""I encountered an issue while processing your request.

Error: {error_type}{detail_line}

Please try:
1. Rephrasing your question
2. Being more specific
3. Trying again in a moment

If the problem persists, contact support."""

    # =========================================================================
    # FUTURE: CHART/DATA PROMPTS
    # =========================================================================

    @staticmethod
    def extract_data_prompt(text: str, data_type: str = "metrics") -> str:
        """Extract structured data from text for visualization.

        USED BY: Future - chart/data extraction features
        PURPOSE: Converts text to structured JSON for visualizations
        """
        return f"""<TASK>
Extract {data_type} from the following text.
Return as JSON format.
</TASK>

<TEXT>
{text}
</TEXT>

<OUTPUT_FORMAT>
{{
  "data_type": "{data_type}",
  "items": [
    {{"label": "...", "value": ..., "unit": "..."}}
  ],
  "source": "extracted from text"
}}
</OUTPUT_FORMAT>

<EXTRACTED_DATA>"""
