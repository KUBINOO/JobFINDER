import re
from typing import Optional, Union, List
from selectolax.parser import HTMLParser, Node

class DOMCleaner:
    """
    Nástroj pro čištění a sanitizaci DOM stromu před extrakcí textu z inzerátů.
    Odstraňuje nepotřebné tagy a boilerplate prvky (menu, patičky, cookies atd.).
    """
    
    # Seznam tagů, které chceme zcela odstranit z DOM stromu
    UNWANTED_TAGS: List[str] = [
        "nav", "footer", "header", "script", "style", 
        "noscript", "svg", "img", "form", "iframe", 
        "aside", "head"
    ]
    
    # CSS selektory pro odstranění běžných boilerplate prvků podle tříd a ID
    BOILERPLATE_SELECTORS: List[str] = [
        '[class*="cookie"]', '[class*="social"]', '[class*="footer"]', 
        '[class*="menu"]', '[class*="navigation"]', '[class*="header"]',
        '[class*="banner"]', '[class*="popup"]', '[class*="modal"]',
        '[id*="cookie"]', '[id*="social"]', '[id*="footer"]', 
        '[id*="menu"]', '[id*="navigation"]', '[id*="header"]'
    ]
    
    # Sémantické tagy určené pro spolehlivou záložní extrakci odstavců
    SEMANTIC_CONTENT_TAGS: List[str] = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6"]

    @classmethod
    def clean_tree(cls, tree: HTMLParser) -> HTMLParser:
        """
        Vyčistí HTML strom od nežádoucích tagů a boilerplate prvků přímo v paměti.
        """
        # 1. Odstranění nežádoucích HTML tagů
        for tag_name in cls.UNWANTED_TAGS:
            for node in tree.css(tag_name):
                node.decompose()
                
        # 2. Odstranění elementů odpovídajících boilerplate selektorům
        for selector in cls.BOILERPLATE_SELECTORS:
            for node in tree.css(selector):
                node.decompose()
                
        return tree

    @classmethod
    def clean_node(cls, node: Node) -> Node:
        """
        Vyčistí konkrétní uzel (např. kontejner inzerátu) od vnitřních nežádoucích elementů.
        """
        # Odstranění nežádoucích vnitřních tagů
        for tag_name in cls.UNWANTED_TAGS:
            for sub_node in node.css(tag_name):
                sub_node.decompose()
                
        # Odstranění vnitřních boilerplate elementů
        for selector in cls.BOILERPLATE_SELECTORS:
            for sub_node in node.css(selector):
                sub_node.decompose()
                
        return node

    @classmethod
    def normalize_whitespace(cls, text: str) -> str:
        """
        Normalizuje bílé znaky, odstraní přebytečné mezery a sjednotí odřádkování.
        """
        if not text:
            return ""
            
        # Nahrazení vícenásobných prázdných řádků maximálně dvěma novými řádky
        text = re.sub(r'\r\n|\r', '\n', text)
        # Odstranění vícenásobných horizontálních mezer a tabulátorů
        lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.split('\n')]
        # Odstranění po sobě jdoucích prázdných řádků
        cleaned_text = '\n'.join(lines)
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
        return cleaned_text.strip()

    @classmethod
    def extract_clean_text(cls, element: Union[HTMLParser, Node]) -> str:
        """
        Extrahuje čistý normalizovaný text z HTMLParseru nebo konkrétního Node uzlu.
        """
        if element is None:
            return ""
            
        raw_text = element.text(separator="\n", strip=True)
        return cls.normalize_whitespace(raw_text)

    @classmethod
    def extract_semantic_text(cls, element: Union[HTMLParser, Node]) -> str:
        """
        Záložní extrakce: získá text POUZE ze sémantických obsahových tagů (<p>, <li>, <h3>, <h4> atd.),
        čímž zabrání extrakci stromů odkazů a obecného navigačního smetí.
        """
        if element is None:
            return ""
            
        semantic_paragraphs: List[str] = []
        
        # Procházíme sémantické tagy v daném elementu
        for tag in cls.SEMANTIC_CONTENT_TAGS:
            for node in element.css(tag):
                text = node.text(strip=True)
                # Zahrneme pouze netriviální bloky textu (více než 1 slovo / znak)
                if text and len(text) > 3:
                    # Formátování pro odrážky seznamu
                    if node.tag == "li":
                        semantic_paragraphs.append(f"• {text}")
                    elif node.tag.startswith("h"):
                        semantic_paragraphs.append(f"\n{text}\n")
                    else:
                        semantic_paragraphs.append(text)
                        
        combined_text = "\n\n".join(semantic_paragraphs)
        return cls.normalize_whitespace(combined_text)

    @classmethod
    def find_iframe_src(cls, tree: HTMLParser) -> Optional[str]:
        """
        Zkontroluje, zda inzerát neobsahuje vložený iframe s tělem inzerátu
        (častý případ u vlastních firemních šablon na Jobs.cz / Prace.cz).
        """
        # Hledáme iframe s typickými identifikátory nebo jakýkoliv iframe s obsahem
        iframe_selectors = [
            'iframe[data-qa="job-ad-iframe"]',
            'iframe.cp-iframe',
            'iframe#cp-iframe',
            'iframe[src*="ad"]',
            'iframe[src*="job"]',
            'iframe[src*="detail"]',
            '.standalone.cp iframe',
            'iframe'
        ]
        
        for selector in iframe_selectors:
            iframe_node = tree.css_first(selector)
            if iframe_node:
                src = iframe_node.attributes.get("src")
                if src and not src.startswith("javascript:") and not src.startswith("about:blank"):
                    return src.strip()
                    
        return None
