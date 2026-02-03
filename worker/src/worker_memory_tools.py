"""
Memory Management Tools for Strands Agent

Provides tools for users to manage their memory records in Bedrock AgentCore Memory.
Users can list, search, and delete their own memory records.

These tools use the underlying MemorySessionManager (not the Strands integration wrapper)
to access full CRUD operations on memory records.
"""

from strands import tool
from typing import Optional


def build_memory_tools(memory_config: dict, region_name: str) -> list:
    """
    Build memory management tools bound to a specific user's memory configuration.

    Args:
        memory_config: Dict with memory_id, actor_id, session_id
        region_name: AWS region for memory service

    Returns:
        List of tool functions configured for this user's memory
    """
    from bedrock_agentcore.memory.session import MemorySessionManager

    # Create the memory manager with full CRUD capabilities
    memory_manager = MemorySessionManager(
        memory_id=memory_config["memory_id"],
        region_name=region_name,
    )

    # Extract user-specific identifiers
    actor_id = memory_config["actor_id"]
    session_id = memory_config["session_id"]

    # Default namespace for user preferences
    default_namespace = f"/preferences/{actor_id}"

    @tool
    def list_my_memory_records(
        namespace: Optional[str] = None,
        max_results: int = 20,
    ) -> dict:
        """
        List all long-term memory records stored for the current user.

        Use this tool when the user wants to see what memories or preferences
        have been stored about them. Returns a list of memory records with
        their IDs, content, and metadata.

        Args:
            namespace: Optional namespace to filter records. Defaults to user's preferences namespace.
                       Use "/preferences/{actorId}" for user preferences.
            max_results: Maximum number of records to return (default: 20, max: 100).

        Returns:
            Dictionary with status and list of memory records including their IDs.
        """
        try:
            # Use default namespace if not specified
            search_namespace = namespace or default_namespace

            # Clamp max_results to reasonable bounds
            max_results = min(max(1, max_results), 100)

            records = memory_manager.list_long_term_memory_records(
                namespace_prefix=search_namespace,
                max_results=max_results,
            )

            if not records:
                return {
                    "status": "success",
                    "content": [
                        {
                            "text": f"No memory records found in namespace '{search_namespace}'."
                        }
                    ],
                }

            # Format records as text for LLM visibility
            lines = [
                f"Found {len(records)} memory record(s) in namespace '{search_namespace}':\n"
            ]
            for i, record in enumerate(records, 1):
                # Try multiple possible attribute names for record ID
                record_id = None
                for attr in [
                    "record_id",
                    "id",
                    "recordId",
                    "memory_record_id",
                    "memoryRecordId",
                ]:
                    record_id = getattr(record, attr, None)
                    if record_id:
                        break
                if not record_id and isinstance(record, dict):
                    record_id = (
                        record.get("record_id")
                        or record.get("id")
                        or record.get("recordId")
                    )
                if not record_id:
                    record_id = "unknown"

                content = getattr(record, "content", None)
                if not content and isinstance(record, dict):
                    content = record.get("content")
                if not content:
                    content = str(record)
                content_preview = (
                    content[:200] + "..." if len(content) > 200 else content
                )

                lines.append(f"{i}. RECORD_ID: {record_id}")
                lines.append(f"   Content: {content_preview}")
                if hasattr(record, "created_at") and record.created_at:
                    lines.append(f"   Created: {record.created_at}")
                lines.append("")

            return {
                "status": "success",
                "content": [{"text": "\n".join(lines)}],
            }

        except Exception as e:
            return {
                "status": "error",
                "content": [{"text": f"Failed to list memory records: {str(e)}"}],
            }

    @tool
    def get_memory_record(record_id: str) -> dict:
        """
        Retrieve a specific memory record by its ID.

        Use this tool when the user wants to see the full details of a
        specific memory record. The record_id can be obtained from
        list_my_memory_records or search_my_memories.

        Args:
            record_id: The unique identifier of the memory record to retrieve.

        Returns:
            Dictionary with status and the full memory record content.
        """
        try:
            if not record_id or not record_id.strip():
                return {
                    "status": "error",
                    "content": [{"text": "record_id is required."}],
                }

            record = memory_manager.get_memory_record(record_id=record_id.strip())

            # Format record details as text for LLM visibility
            actual_record_id = getattr(
                record, "record_id", getattr(record, "id", record_id)
            )
            content = getattr(record, "content", str(record))
            namespace = getattr(record, "namespace", "unknown")
            created_at = getattr(record, "created_at", "unknown")
            metadata = getattr(record, "metadata", {})

            lines = [
                f"Memory Record Details:",
                f"  RECORD_ID: {actual_record_id}",
                f"  Content: {content}",
                f"  Namespace: {namespace}",
                f"  Created: {created_at}",
            ]
            if metadata:
                lines.append(f"  Metadata: {metadata}")

            return {
                "status": "success",
                "content": [{"text": "\n".join(lines)}],
            }

        except Exception as e:
            return {
                "status": "error",
                "content": [
                    {"text": f"Failed to get memory record '{record_id}': {str(e)}"}
                ],
            }

    @tool
    def delete_memory_record(record_id: str) -> dict:
        """
        Delete a specific memory record by its ID.

        Use this tool when the user explicitly requests to delete or forget
        a specific memory. The record_id can be obtained from list_my_memory_records
        or search_my_memories.

        IMPORTANT: This action is irreversible. Before calling this tool:
        1. Show the user which memory you are about to delete (use get_memory_record first if needed)
        2. Confirm the user wants to delete THIS specific memory
        3. Only then call this tool

        Args:
            record_id: The unique identifier of the memory record to delete.

        Returns:
            Dictionary with status indicating success or failure.
        """
        try:
            if not record_id or not record_id.strip():
                return {
                    "status": "error",
                    "content": [{"text": "record_id is required."}],
                }

            record_id = record_id.strip()

            # Delete the record
            memory_manager.delete_memory_record(record_id=record_id)

            return {
                "status": "success",
                "content": [
                    {"text": f"Successfully deleted memory record '{record_id}'."}
                ],
            }

        except Exception as e:
            return {
                "status": "error",
                "content": [
                    {"text": f"Failed to delete memory record '{record_id}': {str(e)}"}
                ],
            }

    @tool
    def delete_all_my_memories_in_namespace(
        namespace: Optional[str] = None,
        confirm: bool = False,
    ) -> dict:
        """
        Delete all memory records in a namespace for the current user.

        Use this tool when the user wants to clear all their stored memories
        or preferences. This is a bulk delete operation.

        IMPORTANT: This is a two-step process for safety:
        1. First call with confirm=False - this will prompt you to ask the user for confirmation
        2. After the user explicitly confirms, call again with confirm=True

        Args:
            namespace: The namespace to clear. Defaults to user's preferences namespace.
            confirm: Set to True only AFTER the user has explicitly confirmed deletion
                     in the conversation. Default is False.

        Returns:
            Dictionary with status indicating success or failure.
        """
        try:
            if not confirm:
                # Use default namespace for the message
                target_namespace = namespace or default_namespace
                return {
                    "status": "pending_confirmation",
                    "content": [
                        {
                            "text": f"CONFIRMATION REQUIRED: Before deleting all memories in "
                            f"'{target_namespace}', you must ask the user to confirm. "
                            f"Send a message asking: 'Are you sure you want to delete all "
                            f"your stored preferences? This cannot be undone.' "
                            f"If the user confirms, call this tool again with confirm=True."
                        }
                    ],
                }

            # Use default namespace if not specified
            target_namespace = namespace or default_namespace

            # Perform the bulk delete
            memory_manager.delete_all_long_term_memories_in_namespace(
                namespace_prefix=target_namespace
            )

            return {
                "status": "success",
                "content": [
                    {
                        "text": f"Successfully deleted all memory records in namespace '{target_namespace}'."
                    }
                ],
            }

        except Exception as e:
            return {
                "status": "error",
                "content": [
                    {
                        "text": f"Failed to delete memories in namespace '{target_namespace}': {str(e)}"
                    }
                ],
            }

    @tool
    def search_my_memories(
        query: str,
        namespace: Optional[str] = None,
        top_k: int = 5,
    ) -> dict:
        """
        Search through stored memories using semantic search.

        Use this tool when the user wants to find specific memories or
        check what has been remembered about a particular topic. The search
        uses semantic similarity to find relevant memories.

        Args:
            query: The search query describing what to look for.
                   Example: "timezone preferences", "favorite color", "notification settings"
            namespace: Optional namespace to search within. Defaults to user's preferences.
            top_k: Number of most relevant results to return (default: 5, max: 20).

        Returns:
            Dictionary with status and list of matching memory records ranked by relevance.
        """
        try:
            if not query or not query.strip():
                return {
                    "status": "error",
                    "content": [{"text": "A search query is required."}],
                }

            # Use default namespace if not specified
            search_namespace = namespace or default_namespace

            # Clamp top_k to reasonable bounds
            top_k = min(max(1, top_k), 20)

            records = memory_manager.search_long_term_memories(
                query=query.strip(),
                namespace_prefix=search_namespace,
                top_k=top_k,
            )

            if not records:
                return {
                    "status": "success",
                    "content": [
                        {
                            "text": f"No memories found matching '{query}' in namespace '{search_namespace}'."
                        }
                    ],
                }

            # Format records as text for LLM visibility
            lines = [f"Found {len(records)} memory record(s) matching '{query}':\n"]
            for i, record in enumerate(records, 1):
                # Try multiple possible attribute names for record ID
                record_id = None
                for attr in [
                    "record_id",
                    "id",
                    "recordId",
                    "memory_record_id",
                    "memoryRecordId",
                ]:
                    record_id = getattr(record, attr, None)
                    if record_id:
                        break
                if not record_id and isinstance(record, dict):
                    record_id = (
                        record.get("record_id")
                        or record.get("id")
                        or record.get("recordId")
                    )
                if not record_id:
                    record_id = "unknown"

                content = getattr(record, "content", None)
                if not content and isinstance(record, dict):
                    content = record.get("content")
                if not content:
                    content = str(record)
                content_preview = (
                    content[:200] + "..." if len(content) > 200 else content
                )

                score = getattr(record, "score", None)
                if not score and isinstance(record, dict):
                    score = record.get("score")

                lines.append(f"{i}. RECORD_ID: {record_id}")
                lines.append(f"   Content: {content_preview}")
                if score is not None:
                    lines.append(f"   Relevance: {score}")
                lines.append("")

            return {
                "status": "success",
                "content": [{"text": "\n".join(lines)}],
            }

        except Exception as e:
            return {
                "status": "error",
                "content": [{"text": f"Failed to search memories: {str(e)}"}],
            }

    # Return all tools as a list
    return [
        list_my_memory_records,
        get_memory_record,
        delete_memory_record,
        delete_all_my_memories_in_namespace,
        search_my_memories,
    ]
