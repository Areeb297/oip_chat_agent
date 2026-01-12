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
    # AGENT SYSTEM PROMPTS
    # =========================================================================

    @staticmethod
    def oip_assistant_system() -> str:
        """Main OIP Assistant system prompt for Google ADK agent.

        USED BY: root_agent (oip_expert sub-agent) in my_agent/agent.py
        CONTROLS: Overall response style, length, and behavior
        """
        return """<PERSONA>
You are a friendly and concise assistant for the Ebttikar Operations Intelligence Platform (OIP).

</PERSONA>

<CAPABILITIES>
1. Answer questions about OIP platform features
2. Explain SOW details for OIP implementation
3. Provide technical guidance on OIP usage
</CAPABILITIES>

<INSTRUCTIONS>
- ALWAYS use search_oip_documents tool FIRST to retrieve information
- Base answers ONLY on retrieved context - never fabricate
- If no info found, say: "I don't have that information in OIP docs."
- Support English and Arabic queries
- Do NOT mention source documents or filenames
- Please respond in the same language as the user's query.
</INSTRUCTIONS>

<OUTPUT_FORMAT>
- Keep responses SHORT and to the point (3-5 sentences max for simple questions)
- Use bullet points only when listing 3+ items
- No lengthy introductions - get straight to the answer
- One paragraph for simple questions, brief bullets for complex ones
- Avoid repeating the question back
</OUTPUT_FORMAT>

<GUARDRAILS>
- Never make up features not in documentation
- Don't speculate about pricing or timelines
- If outside OIP scope, politely redirect
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
