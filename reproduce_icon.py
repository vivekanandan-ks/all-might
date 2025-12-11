import urllib.request
from urllib.parse import urlparse, urljoin
import re

def fetch_icon(homepage_url):
    print(f"Testing URL: {homepage_url}")
    icon_url = None

    # 1. Prioritize favicon.ico at the root
    try:
        parsed_url = urlparse(homepage_url)
        favicon_ico_url = f"{parsed_url.scheme}://{parsed_url.netloc}/favicon.ico"
        print(f"Trying favicon.ico: {favicon_ico_url}")
        
        # Adding User-Agent to mimic browser/app, some sites block python-urllib
        req = urllib.request.Request(
            favicon_ico_url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            info = response.info()
            content_type = info.get_content_type() if info else None
            print(f"favicon.ico content-type: {content_type}")
            if content_type and content_type.startswith('image/'):
                icon_url = favicon_ico_url
                print(f"Found favicon.ico: {icon_url}")
            else:
                 print("favicon.ico found but not image")
    except Exception as e:
        print(f"favicon.ico failed: {e}")

    # 2. Parse HTML for other icons if favicon.ico not found or invalid
    if not icon_url:
        try:
            print(f"Fetching HTML from: {homepage_url}")
            req = urllib.request.Request(
                homepage_url, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                html = response.read().decode('utf-8', errors='ignore')
            
            print(f"HTML fetched. Length: {len(html)}")

            icons = []
            # Find all potential icons
            # Relaxed regex to catch attributes in any order
            # Looking for <link ... rel="icon" ... href="..." ...>
            
            link_regex = re.compile(r'<link\s+[^>]*?>', re.IGNORECASE)
            
            for match in link_regex.finditer(html):
                tag = match.group(0)
                if 'rel=' in tag and 'href=' in tag:
                    # Check rel
                    rel_match = re.search(r'rel=["\'](.*?)["\']', tag, re.IGNORECASE)
                    if not rel_match: continue
                    rel_val = rel_match.group(1).lower()
                    
                    if any(r in rel_val for r in ["icon", "shortcut icon", "apple-touch-icon"]):
                        # Extract href
                        href_match = re.search(r'href=["\'](.*?)["\']', tag, re.IGNORECASE)
                        if href_match:
                            href = href_match.group(1)
                            
                            # Extract size
                            sizes_match = re.search(r'sizes=["\'](\d+x\d+)["\']', tag, re.IGNORECASE)
                            size = sizes_match.group(1) if sizes_match else "0x0"
                            
                            print(f"Found potential icon: rel={rel_val}, href={href}, size={size}")
                            icons.append({"href": href, "size": size})

            if icons:
                # Sort icons by size (smallest first)
                icons.sort(key=lambda x: int(x['size'].split('x')[0]) if x['size'] != "0x0" else 999)
                
                # Get the best icon (smallest, but not 0x0 if possible)
                best_icon = icons[0]
                icon_url = best_icon['href']
                
                if not icon_url.startswith(('http:', 'https:')):
                    icon_url = urljoin(homepage_url, icon_url)
                print(f"Selected icon URL: {icon_url}")
            else:
                print("No icons found in HTML")

        except Exception as e:
            print(f"Error parsing HTML: {e}")

fetch_icon("https://signal.org")
