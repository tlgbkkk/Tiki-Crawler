import re
import html

def normalize(description):
    if not description:
        return ""

    clean_description = re.sub(r'<img.*?>', '', description)
    block_tags = ['p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr']
    for tag in block_tags:
        clean_description = re.sub(f'<{tag}.*?>|</{tag}>', ' ', clean_description)
    clean_description = re.sub(r'<.*?>', '', clean_description)
    clean_description = html.unescape(clean_description)
    clean_description = re.sub(r'[ \t]+', ' ', clean_description)
    clean_description = re.sub(r'\n\s*\n+', '\n\n', clean_description)

    return clean_description.strip()
