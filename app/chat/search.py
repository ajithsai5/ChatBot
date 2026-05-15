"""Vector search and LLM response helper functions for chatbot retrieval flows.

Main responsibility:
- Generate embedding vectors via Azure OpenAI.
- Search the Azure AI Search index using vector and keyword strategies.
- Produce final chatbot responses through the LLM completion endpoint.

Not handled here:
- Query routing or tool dispatch (see orchestrator.py, dispatcher.py).
- Persona configuration (see personas.py).
"""

import os
import json
import logging
import time

import httpx
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import VectorizedQuery
import tiktoken

from config import AZURE_AI_Service_KEY, AZURE_Search_Service_KEY


LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Azure service endpoints and clients
# ---------------------------------------------------------------------------

AZURE_SEARCH_SERVICE_ENDPOINT = (
    "https://gpdacq-dev-1-eastus-ai-search-cog-svc.search.windows.net"
)
AZURE_AI_TEXT_EMBEDDING_ENDPOINT = (
    "https://gpdacq-dev-1-eastus-openai.openai.azure.com/openai/"
    "deployments/UHCCP_Vector/embeddings?api-version=2023-05-15"
)
AZURE_OPENAI_ENDPOINT = "https://gpdacq-dev-1-eastus-openai.openai.azure.com"
AZURE_SEARCH_INDEX = "uhccp-vector"

azure_credential = AzureKeyCredential(AZURE_Search_Service_KEY)

search_client = SearchClient(
    endpoint=AZURE_SEARCH_SERVICE_ENDPOINT,
    index_name=AZURE_SEARCH_INDEX,
    credential=azure_credential,
)

index_client = SearchIndexClient(
    endpoint=AZURE_SEARCH_SERVICE_ENDPOINT,
    credential=azure_credential,
)

# Embedding client — used by get_embeddings() for vector generation.
embedding_client = AzureOpenAI(
    azure_endpoint=AZURE_AI_TEXT_EMBEDDING_ENDPOINT,
    api_key=AZURE_AI_Service_KEY,
    api_version="2024-12-01-preview",
)
EMBEDDING_MODEL = "UHCCP_Vector"

# Chat completion client — used by single_chatbot_response() and exported
# to dispatcher.py and ai_priority.py.
openai_chat_client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_AI_Service_KEY,
    api_version="2024-12-01-preview",
)

# Legacy alias so existing imports (``from app.chat.search import openaii``)
# continue to work until every consumer is updated.
openaii = openai_chat_client

# ---------------------------------------------------------------------------
# File link mapping (maps document titles to external URLs)
# ---------------------------------------------------------------------------

with open("file_link.json", "r") as _flink_file:
    file_links: dict[str, str] = json.load(_flink_file)

# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

def get_embeddings(text: str) -> list[float] | dict:
    """Create an embedding vector for the given query text.

    Returns the embedding vector on success, or an error dict on failure.
    """
    try:
        embedding = embedding_client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
        return embedding.data[0].embedding
    except Exception as exc:
        LOGGER.warning("Error fetching embeddings: %s", exc)
        return {"error": f"Error fetching embeddings: {exc}"}


# ---------------------------------------------------------------------------
# Vector query construction
# ---------------------------------------------------------------------------

def _build_vector_query(vector: list[float], vector_field: str | None = None) -> VectorizedQuery:
    """Wrap an embedding vector into an Azure VectorizedQuery object."""
    kwargs = {
        "vector": vector,
        "k_nearest_neighbors": 2,
        "exhaustive": True,
        "kind": "vector",
    }
    if vector_field:
        kwargs["fields"] = vector_field
    return VectorizedQuery(**kwargs)


def _get_index_vector_fields() -> list[str]:
    """Discover vector field names from the Azure Search index schema."""
    try:
        index = index_client.get_index(AZURE_SEARCH_INDEX)
        vector_fields = []
        for field in index.fields:
            dimensions = getattr(field, "vector_search_dimensions", None)
            if dimensions is None:
                dimensions = getattr(field, "vectorSearchDimensions", None)
            if dimensions:
                vector_fields.append(field.name)
        return vector_fields
    except Exception as exc:
        LOGGER.debug("Unable to discover vector fields from index schema: %s", exc)
        return []


def get_vectorized_query(search: str, scrum: bool = False) -> VectorizedQuery:
    """Build a VectorizedQuery object for an Azure Search lookup."""
    vector = get_embeddings(search)

    if not vector:
        raise ValueError("Failed to generate embeddings for the search query.")

    configured_vector_field = os.getenv("AZURE_SEARCH_VECTOR_FIELD", "").strip() or None
    return _build_vector_query(vector, configured_vector_field)


# ---------------------------------------------------------------------------
# Document search
# ---------------------------------------------------------------------------

def search_documents(
    search: str,
    vectorized_queries: list,
    scrum: bool = False,
    history: list | None = None,
    doc_count: int = 10,
) -> dict:
    """Search content via vector lookup with keyword fallback.

    Tries multiple vector-field / select-field combinations before
    falling back to a keyword search when vector retrieval fails.
    """

    def try_search(select_fields: str | None, queries):
        # Force execution here so invalid $select fields are caught by the retry loop.
        return list(
            search_client.search(
                search_text=None,
                vector_queries=queries,
                top=doc_count,
                select=select_fields
            )
        )

    def try_keyword_search(select_fields: str | None):
        return list(
            search_client.search(
                search_text=search,
                top=doc_count,
                select=select_fields
            )
        )

    def get_content(doc):
        for key in ("chunk", "content", "text", "page_content", "data"):
            value = doc.get(key)
            if value:
                return str(value).replace("\n", " ").replace("\r", "")
        return ""

    def get_title(doc):
        for key in ("title", "metadata_storage_name", "file_name", "filename"):
            value = doc.get(key)
            if value:
                return str(value)
        return "Unknown File"

    try:
        results = None
        last_error = None
        active_vector_field = None
        search_mode = "vector"

        base_vector = None
        if vectorized_queries:
            try:
                base_vector = getattr(vectorized_queries[0], "vector", None)
            except Exception:
                base_vector = None

        if not base_vector:
            base_vector = get_embeddings(search)
            if not base_vector or isinstance(base_vector, dict):
                raise ValueError("Failed to generate vector for document search.")

        configured_vector_field = os.getenv("AZURE_SEARCH_VECTOR_FIELD", "").strip()
        discovered_vector_fields = _get_index_vector_fields()
        vector_field_candidates = [
            configured_vector_field or None,
            *discovered_vector_fields,
            None,
            "vector",
            "text_vector",
            "content_vector",
            "contentVector",
            "embedding",
            "textVector",
        ]
        deduped_vector_fields = []
        for candidate in vector_field_candidates:
            if candidate not in deduped_vector_fields:
                deduped_vector_fields.append(candidate)

        select_candidates = [
            "chunk,title",
            "content,title",
            "text,title",
            "page_content,title",
            "chunk,metadata_storage_name",
            "content,metadata_storage_name",
            "text,metadata_storage_name",
            None,
        ]

        for vector_field in deduped_vector_fields:
            queries = [_build_vector_query(base_vector, vector_field)]
            for select_fields in select_candidates:
                try:
                    results = try_search(select_fields, queries)
                    active_vector_field = vector_field
                    break
                except Exception as e:
                    last_error = e
                    continue
            if results is not None:
                break

        if results is None:
            LOGGER.info("Vector search failed. Falling back to keyword search.")
            search_mode = "keyword"
            for select_fields in select_candidates:
                try:
                    results = try_keyword_search(select_fields)
                    break
                except Exception as e:
                    last_error = e
                    continue

        if results is None:
            raise last_error or RuntimeError("Search failed without results.")

        LOGGER.debug("vector_field_used: %s", active_vector_field if active_vector_field else '[default]')
        LOGGER.debug("search_mode_used: %s", search_mode)

        data = []
        file_name = "Unknown File"
        for i, doc in enumerate(results):
            chunk = get_content(doc)
            file_name = get_title(doc)
            if chunk.strip():
                data.append(chunk)

        if not data:
            return {"content": "NO info"}

        LOGGER.debug('file_name: %s', file_name)

        formatted_data = " ".join(data)
        if file_name in file_links:
            file_link = file_links[file_name]
        else:
            file_link = "https://gpd-architecture.s3docs.optum.com/uhccp/overview/"

        LOGGER.debug('file_link discovered for retrieval result')
        return_obj = {
            "role": "user",
            "content": "question: " + search + "\nData : " + formatted_data,
            "file_name": file_name,
            "file_link": file_link,
            "search_mode": search_mode,
        }

        if history and len(history) > 0:
            return_obj["content"] += f"\nChat History: {str(history)}"

        return return_obj

    except Exception as e:
        LOGGER.warning("Failed to search documents: %s", e)

    return_obj = {
        "role": "user",
        "content": "question: " + search + "\nData : failed to provide additional data"
    }

    if history and len(history) > 0:
        return_obj["content"] += f"\nChat History: {str(history)}"

    return return_obj


# ---------------------------------------------------------------------------
# Token truncation
# ---------------------------------------------------------------------------

def truncate_text(text: str, max_tokens: int, encoding: tiktoken.Encoding) -> str:
    """Trim text to a maximum token count using the given tiktoken encoding."""
    encoded_text = encoding.encode(text)
    return encoding.decode(encoded_text[:max_tokens])


# ---------------------------------------------------------------------------
# LLM response generation
# ---------------------------------------------------------------------------

def single_chatbot_response(
    messages: list[dict],
    outdata: str = "",
    long_res: bool = False,
    scrum: bool = False,
    logger=None,
    rally: bool = False,
    rally_messages=None,
    prt_data: dict | None = None,
) -> str:
    """Generate the final assistant response, including optional follow-up prompts.

    When ``prt_data`` is supplied, a secondary LLM call extracts follow-up
    questions and related links before the main completion runs.
    """

    if prt_data is not None:
        search_links = False
        # Build the follow-up prompt depending on whether link extraction is active.
        link_msg = (
            "You find related questions for follow up and links that will be used in "
            "the response. Use the user's question asked and the following data to "
            "provide a response. Take all links in the data and create a key name for "
            "the link. The key will be shown as the text for the link, keep them short. "
            "Pass the name as the key and the url as the value. Only respond in the "
            'format {"questions":["question","question","question"],'
            '"links":{"keyword":"url","keyword":"url"}}. '
            "Respond with three follow up questions only using the supporting data. "
            "Keep rally id's in their format, such as US12345, F12345, DE12345."
        )
        plain_msg = (
            "You find related questions for follow up that will be used in the response. "
            "Use the user's question asked and the following data to provide a response. "
            'Only respond in the format {"questions":["question","question","question"]}. '
            "Respond with three follow up questions only using the supporting data."
        )
        follow_up_messages = [
            {"role": "system", "content": link_msg if search_links else plain_msg},
            messages[1],
        ]

        try:
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            follow_up_messages[1]["content"] = truncate_text(
                follow_up_messages[1]["content"], 13000, encoding
            )

            follow_up_completion = openai_chat_client.chat.completions.create(
                model="UHCCP_ChatBot",
                messages=follow_up_messages,
                max_tokens=400,
                temperature=0.3,
                top_p=1,
            )

            prt_res = json.loads(follow_up_completion.choices[0].message.content)

            if "questions" not in prt_data:
                prt_data["questions"] = []
            for question in prt_res["questions"]:
                prt_data["questions"].append(question)

            if "links" not in prt_data:
                prt_data["links"] = {}
            if "links" in prt_res:
                for key, value in prt_res["links"].items():
                    prt_data["links"][key] = value
                # Annotate links inside message content so the LLM can reference them.
                for key, value in prt_data["links"].items():
                    messages[1]["content"] = messages[1]["content"].replace(
                        value, f"~Treat this as a link: {key}~"
                    )

            time.sleep(1)

        except Exception as exc:
            LOGGER.warning("Error while generating follow-up questions: %s", exc)

    # Main LLM completion call.
    completion = openai_chat_client.chat.completions.create(
        model="UHCCP_ChatBot",
        messages=messages,
        max_tokens=800,
        temperature=0.3,
        top_p=1,
    )
    respond_message = completion.choices[0].message.content

    if scrum:
        tokens = outdata.split("\n")
    respond_message += outdata

    if logger:
        logger.set_answer(respond_message)
        logger.send_to_logstash()

    if rally and rally_messages:
        rally_messages.set_messages({"role": "assistant", "content": respond_message})

    return respond_message
