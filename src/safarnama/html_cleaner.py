import re


class HTMLCleaner:
    SCRIPT_PATTERN = r"<[ ]*script.*?\/[ ]*script[ ]*>"
    STYLE_PATTERN = r"<[ ]*style.*?\/[ ]*style[ ]*>"
    META_PATTERN = r"<[ ]*meta.*?>"
    COMMENT_PATTERN = r"<[ ]*!--.*?--[ ]*>"
    LINK_PATTERN = r"<[ ]*link.*?>"
    BASE64_IMG_PATTERN = r'<img[^>]+src="data:image/[^;]+;base64,[^"]+"[^>]*>'
    SVG_PATTERN = r"(<svg[^>]*>)(.*?)(<\/svg>)"

    @classmethod
    def replace_svg(cls, html: str, new_content: str = "this is a placeholder") -> str:
        return re.sub(
            cls.SVG_PATTERN,
            lambda match: f"{match.group(1)}{new_content}{match.group(3)}",
            html,
            flags=re.DOTALL,
        )

    @classmethod
    def replace_base64_images(cls, html: str, new_image_src: str = "#") -> str:
        return re.sub(cls.BASE64_IMG_PATTERN, f'<img src="{new_image_src}"/>', html)

    @classmethod
    def clean_html(
        cls,
        html: str,
        clean_svg: bool = False,
        clean_base64: bool = False,
        exclude_patterns: list = None,
    ) -> str:
        html = re.sub(
            cls.SCRIPT_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        html = re.sub(
            cls.STYLE_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        html = re.sub(
            cls.META_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        html = re.sub(
            cls.COMMENT_PATTERN,
            "",
            html,
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        html = re.sub(
            cls.LINK_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        if clean_svg:
            html = cls.replace_svg(html)
        if clean_base64:
            html = cls.replace_base64_images(html)
        if exclude_patterns:
            for pattern in exclude_patterns:
                html = re.sub(pattern, "", html, flags=re.IGNORECASE)
        return html
