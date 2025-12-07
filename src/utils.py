import subprocess
import json
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
