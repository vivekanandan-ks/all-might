import subprocess
import json
import urllib.request
import xml.etree.ElementTree as ET
import re
from state import state

# --- Logic: Search ---

def execute_nix_search(query, channel):
    if not query:
        return []

    limit_val = str(state.search_limit)

    command = [
        "nix", "run", "nixpkgs#nh", "--",
        "search", "--channel", channel, "-j", "--limit", limit_val, query
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        raw_results = data.get("results", [])

        seen = set()
        unique_results = []
        for pkg in raw_results:
            sig = (pkg.get("package_pname"), pkg.get("package_pversion"))
            if sig not in seen:
                seen.add(sig)
                unique_results.append(pkg)

        return unique_results
    except subprocess.CalledProcessError as e:
        print(f"Nix Search Failed: {e.stderr}")
        return [{"error": str(e.stderr)}]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Execution Error: {e}")
        return [{"error": f"Execution Error: {str(e)}"}]

def get_mastodon_quote(account, tag):
    clean_account = account.strip()
    clean_tag = tag.strip()
    
    url = f"https://mstdn.social/@{clean_account}/tagged/{clean_tag}.rss"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            rss_content = response.read()
            
        root = ET.fromstring(rss_content)
        
        # RSS structure: rss > channel > item
        channel = root.find("channel")
        if channel is None:
            return None
            
        item = channel.find("item")
        if item is None:
            return None
            
        description_elem = item.find("description")
        link_elem = item.find("link")
        
        description = description_elem.text if description_elem is not None else ""
        link = link_elem.text if link_elem is not None else ""
        
        # Clean HTML from description
        # Replace <br> and <p> with newlines
        description = re.sub(r'<br\s*/?>|</p>', '\n', description)
        # Remove all other HTML tags
        description = re.sub(r'<[^>]+>', '', description)
        # Trim whitespace
        description = description.strip()
        
        if description:
            return {"text": description, "link": link, "author": f"@{clean_account}"}
        else:
            return None

    except Exception as e:
        print(f"Error fetching Mastodon quote: {e}")
        return None
