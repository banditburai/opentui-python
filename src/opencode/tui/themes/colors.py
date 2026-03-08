"""Theme color token definitions — all upstream color tokens as a dataclass."""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True, slots=True)
class ThemeColors:
    """Resolved theme colors for a specific mode (dark or light).

    All values are CSS hex color strings (e.g. ``"#1a1b26"``) or
    ``"transparent"`` for fully transparent backgrounds.
    """

    # Core
    primary: str
    secondary: str
    accent: str
    error: str
    warning: str
    success: str
    info: str

    # Text
    text: str
    text_muted: str
    selected_list_item_text: str

    # Backgrounds
    background: str
    background_panel: str
    background_element: str
    background_menu: str

    # Borders
    border: str
    border_active: str
    border_subtle: str

    # Diff (12 tokens)
    diff_added: str
    diff_removed: str
    diff_context: str
    diff_hunk_header: str
    diff_highlight_added: str
    diff_highlight_removed: str
    diff_added_bg: str
    diff_removed_bg: str
    diff_context_bg: str
    diff_line_number: str
    diff_added_line_number_bg: str
    diff_removed_line_number_bg: str

    # Markdown (14 tokens)
    markdown_text: str
    markdown_heading: str
    markdown_link: str
    markdown_link_text: str
    markdown_code: str
    markdown_block_quote: str
    markdown_emph: str
    markdown_strong: str
    markdown_horizontal_rule: str
    markdown_list_item: str
    markdown_list_enumeration: str
    markdown_image: str
    markdown_image_text: str
    markdown_code_block: str

    # Syntax highlighting (9 tokens)
    syntax_comment: str
    syntax_keyword: str
    syntax_function: str
    syntax_variable: str
    syntax_string: str
    syntax_number: str
    syntax_type: str
    syntax_operator: str
    syntax_punctuation: str

    # Meta
    thinking_opacity: float = 0.6

    @classmethod
    def token_names(cls) -> list[str]:
        """Return all color token field names (excludes thinking_opacity)."""
        return [f.name for f in fields(cls) if f.name != "thinking_opacity"]

    @classmethod
    def token_count(cls) -> int:
        """Number of color tokens (excludes thinking_opacity)."""
        return len(cls.token_names())


# camelCase -> snake_case mapping for loading from JSON theme files
_CAMEL_TO_SNAKE: dict[str, str] = {
    "primary": "primary",
    "secondary": "secondary",
    "accent": "accent",
    "error": "error",
    "warning": "warning",
    "success": "success",
    "info": "info",
    "text": "text",
    "textMuted": "text_muted",
    "selectedListItemText": "selected_list_item_text",
    "background": "background",
    "backgroundPanel": "background_panel",
    "backgroundElement": "background_element",
    "backgroundMenu": "background_menu",
    "border": "border",
    "borderActive": "border_active",
    "borderSubtle": "border_subtle",
    "diffAdded": "diff_added",
    "diffRemoved": "diff_removed",
    "diffContext": "diff_context",
    "diffHunkHeader": "diff_hunk_header",
    "diffHighlightAdded": "diff_highlight_added",
    "diffHighlightRemoved": "diff_highlight_removed",
    "diffAddedBg": "diff_added_bg",
    "diffRemovedBg": "diff_removed_bg",
    "diffContextBg": "diff_context_bg",
    "diffLineNumber": "diff_line_number",
    "diffAddedLineNumberBg": "diff_added_line_number_bg",
    "diffRemovedLineNumberBg": "diff_removed_line_number_bg",
    "markdownText": "markdown_text",
    "markdownHeading": "markdown_heading",
    "markdownLink": "markdown_link",
    "markdownLinkText": "markdown_link_text",
    "markdownCode": "markdown_code",
    "markdownBlockQuote": "markdown_block_quote",
    "markdownEmph": "markdown_emph",
    "markdownStrong": "markdown_strong",
    "markdownHorizontalRule": "markdown_horizontal_rule",
    "markdownListItem": "markdown_list_item",
    "markdownListEnumeration": "markdown_list_enumeration",
    "markdownImage": "markdown_image",
    "markdownImageText": "markdown_image_text",
    "markdownCodeBlock": "markdown_code_block",
    "syntaxComment": "syntax_comment",
    "syntaxKeyword": "syntax_keyword",
    "syntaxFunction": "syntax_function",
    "syntaxVariable": "syntax_variable",
    "syntaxString": "syntax_string",
    "syntaxNumber": "syntax_number",
    "syntaxType": "syntax_type",
    "syntaxOperator": "syntax_operator",
    "syntaxPunctuation": "syntax_punctuation",
}
