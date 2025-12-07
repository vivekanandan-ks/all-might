import subprocess
import json
import urllib.request
import base64
import xml.etree.ElementTree as ET
import re
from state import state

# --- Logic: Search ---

def execute_nix_search(query, channel):
    if not query:
        return []

    try:
        limit_val = int(state.search_limit)
    except (ValueError, TypeError):
        limit_val = 20

    # Map "nixos-unstable" or specific versions to the backend index format
    # nh logic: if channel starts with nixos-, use it. if it's unstable, use nixos-unstable.
    # The URL format in nh is: https://search.nixos.org/backend/latest-44-{channel}/_search
    # Example: latest-44-nixos-unstable or latest-44-nixos-24.05
    
    url = f"https://search.nixos.org/backend/latest-44-{channel}/_search"

    # Construct the ElasticSearch query matching nh's implementation
    query_dsl = {
        "from": 0,
        "size": limit_val,
        "query": {
            "bool": {
                "filter": {
                    "term": {
                        "type": "package"
                    }
                },
                "must": {
                    "dis_max": {
                        "tie_breaker": 0.7,
                        "queries": [
                            {
                                "multi_match": {
                                    "fields": [
                                        "package_attr_name^9",
                                        "package_attr_name.*^5.4",
                                        "package_programs^9",
                                        "package_programs.*^5.4",
                                        "package_pname^6",
                                        "package_pname.*^3.6",
                                        "package_description^1.3",
                                        "package_description.*^0.78",
                                        "package_longDescription^1",
                                        "package_longDescription.*^0.6",
                                        "flake_name^0.5",
                                        "flake_name.*^0.3"
                                    ],
                                    "query": query,
                                    "type": "cross_fields",
                                    "analyzer": "whitespace",
                                    "auto_generate_synonyms_phrase_query": False,
                                    "operator": "and"
                                }
                            },
                            {
                                "wildcard": {
                                    "package_attr_name": {
                                        "value": f"*{query}*",
                                        "case_insensitive": True
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    }

    # Auth credentials from nh source
    user = "aWVSALXpZv"
    password = "X8gPHnzL52wFEekuxsfQ9cSh"
    auth_str = f"{user}:{password}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "nh/0.0.0", # Mimic nh
        "Authorization": f"Basic {b64_auth}"
    }

    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(query_dsl).encode('utf-8'), 
            headers=headers, 
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                print(f"Nix Search HTTP Error: {response.status}")
                return [{"error": f"HTTP Error: {response.status}"}]

            response_body = response.read()
            data = json.loads(response_body)
            
            # The 'hits' array contains the documents in '_source'
            hits = data.get("hits", {}).get("hits", [])
            raw_results = [hit["_source"] for hit in hits]

            seen = set()
            unique_results = []
            for pkg in raw_results:
                # Use safely .get in case fields are missing
                pname = pkg.get("package_pname", "")
                pversion = pkg.get("package_pversion", "")
                sig = (pname, pversion)
                
                if sig not in seen:
                    seen.add(sig)
                    unique_results.append(pkg)

            return unique_results

    except Exception as e:
        print(f"Nix Search Failed: {e}")
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