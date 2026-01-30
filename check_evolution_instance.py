
import requests
import json

url = "http://72.61.249.204:8080/instance/fetchInstances"
headers = {
    "apikey": "Watchvine8401",
    "Content-Type": "application/json"
}

output = []

try:
    output.append(f"Checking URL: {url}")
    response = requests.get(url, headers=headers, timeout=10)
    output.append(f"List Instances Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        output.append("Found Instances:")
        found_watchvine = False
        
        if isinstance(data, list):
            for inst in data:
                # Evolution API structure varies, try to be robust
                name = inst.get('instance', {}).get('instanceName') or inst.get('name') or "UNKNOWN"
                output.append(f" - '{name}' (Type: {type(name)})")
                
                if name == "watchvine":
                    found_watchvine = True
                    output.append(f"   MATCH FOUND! Attempting test send to '{name}'...")
                    send_url = f"http://72.61.249.204:8080/message/sendText/{name}"
                    payload = {
                        "number": "919274497524",
                        "text": "Antigravity Debug Test Message"
                    }
                    try:
                        send_resp = requests.post(send_url, json=payload, headers=headers, timeout=10)
                        output.append(f"   Send Status: {send_resp.status_code}")
                        output.append(f"   Send Response: {send_resp.text[:200]}") # Truncate log
                    except Exception as e:
                        output.append(f"   Send Failed: {e}")
        else:
            output.append(f"Unexpected data format: {type(data)}")
    else:
        output.append(f"Listing failed: {response.text}")

except Exception as e:
    output.append(f"Script Error: {e}")

with open("instance_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("Report generated.")
