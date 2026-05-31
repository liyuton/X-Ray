#!/usr/bin/env python3
"""Export papers with cited_by_count >= threshold from Elasticsearch.

Default target index: acemap.works
Output fields: id, title, cited_by_count
"""

import argparse
import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from elasticsearch import Elasticsearch


ES_HOST = "http://10.10.12.1:9201"
ES_USER = "readonly"
ES_PASS = "readonly"
INDEX_NAME = "acemap.works"


def _first_value(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _to_int(value: Any, default: int = 0) -> int:
    value = _first_value(value)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_str(value: Any, default: str = "") -> str:
    value = _first_value(value)
    if value is None:
        return default
    return str(value)


def create_client(host: str, user: str, password: str) -> Elasticsearch:
    """Create ES client with auth compatible for 7.x and 8.x clients."""
    parsed = urlparse(host)
    if parsed.username is None and user:
        auth_host = f"{parsed.scheme}://{user}:{password}@{parsed.hostname}"
        if parsed.port:
            auth_host += f":{parsed.port}"
    else:
        auth_host = host

    # elasticsearch 7.x does not reliably support basic_auth kwarg.
    try:
        return Elasticsearch(hosts=[auth_host], http_auth=(user, password), timeout=120)
    except TypeError:
        # elasticsearch 8.x
        return Elasticsearch(hosts=[auth_host], basic_auth=(user, password), request_timeout=120)


def fetch_high_citation_papers(
    client: Elasticsearch,
    index_name: str,
    min_cited_by_count: int,
    page_size: int = 1000,
) -> List[Dict[str, Any]]:
    query = {
        "query": {
            "range": {
                "cited_by_count": {
                    "gte": min_cited_by_count,
                }
            }
        },
        "_source": ["id", "title", "cited_by_count"],
        "size": page_size,
        "sort": [{"_doc": "asc"}],
    }

    response = client.search(index=index_name, body=query, scroll="2m")
    scroll_id: Optional[str] = response.get("_scroll_id")
    hits = response.get("hits", {}).get("hits", [])

    results: List[Dict[str, Any]] = []
    try:
        while hits:
            for hit in hits:
                source = hit.get("_source", {})
                item_id = _to_str(source.get("id"), default=hit.get("_id", ""))
                title = _to_str(source.get("title"), default="")
                cited_by_count = _to_int(source.get("cited_by_count"), default=0)
                results.append(
                    {
                        "id": item_id,
                        "title": title,
                        "cited_by_count": cited_by_count,
                    }
                )

            response = client.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = response.get("_scroll_id")
            hits = response.get("hits", {}).get("hits", [])
    finally:
        if scroll_id:
            try:
                client.clear_scroll(scroll_id=scroll_id)
            except Exception:
                pass

    results.sort(key=lambda x: x["cited_by_count"], reverse=True)
    return results


def save_to_json(data: List[Dict[str, Any]], output_file: str) -> None:
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filter papers with high citations from Elasticsearch and export JSON."
    )
    parser.add_argument("--host", default=ES_HOST, help="Elasticsearch host URL")
    parser.add_argument("--user", default=ES_USER, help="Elasticsearch username")
    parser.add_argument("--password", default=ES_PASS, help="Elasticsearch password")
    parser.add_argument("--index", default=INDEX_NAME, help="Elasticsearch index name")
    parser.add_argument(
        "--min-citation",
        type=int,
        default=1000,
        help="Minimum cited_by_count threshold",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=1000,
        help="Scroll page size for each request",
    )
    parser.add_argument(
        "--output",
        default="output/top_papers_cited_by_1000.json",
        help="Output JSON file path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = create_client(args.host, args.user, args.password)
    papers = fetch_high_citation_papers(
        client=client,
        index_name=args.index,
        min_cited_by_count=args.min_citation,
        page_size=args.size,
    )
    save_to_json(papers, args.output)

    print(f"Output file: {args.output}")
    print(f"Total papers with cited_by_count >= {args.min_citation}: {len(papers)}")


if __name__ == "__main__":
    main()
