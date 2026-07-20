import logging

logger = logging.getLogger("memory_provider")


class MemoryProvider:
    """
    Interfaces with active document uploads to extract contextual reference files.
    """

    def __init__(self):
        pass

    def retrieve(self) -> str:
        """
        Fetches active uploaded document context. SQLite database queries are disabled.
        """
        from app.capability_1.api.upload import get_all_documents_text_context

        context_parts = []

        try:
            docs_context = get_all_documents_text_context()
            if docs_context and docs_context.strip():
                context_parts.append(
                    f"=== UPLOADED DOCUMENTS CONTEXT ===\n"
                    f"{docs_context}\n"
                    f"=================================="
                )
        except Exception as e:
            logger.error(f"MemoryProvider failed to extract uploaded files text: {e}")

        return "\n\n".join(context_parts)
