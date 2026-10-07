#!/usr/bin/env python3
"""Zenn記事のslugとFront Matterを検証する。"""

from __future__ import annotations

import argparse
from copy import deepcopy
import re
import sys
from pathlib import Path
from typing import Any

import emoji as emoji_lib
import yaml


SLUG_PATTERN = re.compile(r"[a-z0-9_-]{12,50}\Z")
REQUIRED_FIELDS = {"title", "emoji", "type", "topics", "published"}
BOOLEAN_TAG = "tag:yaml.org,2002:bool"


class ArticleLoader(yaml.SafeLoader):
    """YAML 1.2のtrue/falseと重複キー拒否を使う記事用loader。"""


ArticleLoader.yaml_implicit_resolvers = deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for first_character, resolvers in ArticleLoader.yaml_implicit_resolvers.items():
    ArticleLoader.yaml_implicit_resolvers[first_character] = [
        (tag, pattern) for tag, pattern in resolvers if tag != BOOLEAN_TAG
    ]
ArticleLoader.add_implicit_resolver(
    BOOLEAN_TAG,
    re.compile(r"^(?:true|false)$"),
    list("tf"),
)


def _construct_unique_mapping(
    loader: ArticleLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    seen: set[Any] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            hash(key)
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "mapping keys must be hashable",
                key_node.start_mark,
            ) from exc
        if key in seen:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate mapping key {key!r}",
                key_node.start_mark,
            )
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


ArticleLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def validate_article(path: Path) -> list[str]:
    errors: list[str] = []
    if not SLUG_PATTERN.fullmatch(path.stem):
        errors.append("slug must contain 12-50 lowercase letters, digits, hyphens, or underscores")

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return errors + [f"cannot read article as UTF-8: {exc}"]

    if not lines or lines[0].strip() != "---":
        return errors + ["front matter must start with --- on the first line"]

    try:
        closing_index = lines.index("---", 1)
    except ValueError:
        return errors + ["front matter closing --- was not found"]

    try:
        metadata: Any = yaml.load(
            "\n".join(lines[1:closing_index]), Loader=ArticleLoader
        )
    except yaml.YAMLError as exc:
        if isinstance(exc, yaml.constructor.ConstructorError) and exc.problem:
            detail = exc.problem
        else:
            detail = exc.__class__.__name__
        return errors + [f"invalid YAML front matter: {detail}"]

    if not isinstance(metadata, dict):
        return errors + ["front matter must be a YAML mapping"]

    missing = sorted(REQUIRED_FIELDS - metadata.keys())
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    title = metadata.get("title")
    if not isinstance(title, str):
        errors.append("title must be a string")

    emoji = metadata.get("emoji")
    if not isinstance(emoji, str) or not emoji_lib.is_emoji(emoji):
        errors.append("emoji must be one recognized emoji")

    article_type = metadata.get("type")
    if not isinstance(article_type, str) or article_type not in {"tech", "idea"}:
        errors.append("type must be 'tech' or 'idea'")

    topics = metadata.get("topics")
    if not isinstance(topics, list) or any(
        not isinstance(topic, str) or not topic.strip() for topic in topics
    ):
        errors.append("topics must be an array of non-empty strings")
    elif len(topics) > 5:
        errors.append("topics must contain at most 5 entries")

    published = metadata.get("published")
    if type(published) is not bool:
        errors.append("published must be a boolean")
    elif published and isinstance(title, str) and not title.strip():
        errors.append("published articles must have a non-empty title")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("articles_dir", nargs="?", type=Path, default=Path("articles"))
    args = parser.parse_args()

    if not args.articles_dir.is_dir():
        print(f"{args.articles_dir}: articles ディレクトリがありません", file=sys.stderr)
        return 1

    articles = sorted(args.articles_dir.glob("*.md"))
    if not articles:
        print(f"{args.articles_dir}: Markdown記事がありません", file=sys.stderr)
        return 1

    failed = False
    for article in articles:
        for error in validate_article(article):
            print(f"{article}: {error}", file=sys.stderr)
            failed = True

    if failed:
        return 1

    print(f"Zenn記事 {len(articles)} 件を検証しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
