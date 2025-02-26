import argparse
import re

def parse_curl_command(curl_cmd):
    """Convert a cURL command string into a raw HTTP request."""
    # Extract the method (GET by default, POST if --data or -d is present)
    method = "GET"
    if "--data" in curl_cmd or "-d" in curl_cmd or "--data-raw" in curl_cmd:
        method = "POST"
    elif "-X" in curl_cmd:
        method_match = re.search(r"-X\s+(\w+)", curl_cmd)
        if method_match:
            method = method_match.group(1)

    # Extract the URL and path
    url_match = re.search(r"curl\s+['\"]?(https?://[^/\s]+)(/[^'\"\s]*)['\"]? ", curl_cmd)
    if not url_match:
        raise ValueError("Could not extract URL from cURL command")
    host = url_match.group(1).replace("http://", "").replace("https://", "")
    path = url_match.group(2) if url_match.group(2) else "/"

    # Extract headers
    headers = []
    header_matches = re.findall(r"-H\s+['\"]([^:'\"]+): ([^'\"]+)['\"]", curl_cmd)
    for key, value in header_matches:
        headers.append(f"{key}: {value}")
    headers.append(f"Host: {host}")  # Add Host header if not already present

    # Extract data (body)
    body = ""
    data_match = re.search(r"(?:--data-raw|--data|-d)\s+['\"]([^'\"]+)['\"]", curl_cmd)
    if data_match:
        body = data_match.group(1)

    # Construct the raw HTTP request
    request_lines = [f"{method} {path} HTTP/1.1"]
    request_lines.extend(headers)
    if body:
        request_lines.append(f"Content-Length: {len(body)}")
        request_lines.append("")  # Blank line before body
        request_lines.append(body)
    else:
        request_lines.append("")  # Blank line to end headers

    return "\n".join(request_lines)

def main():
    parser = argparse.ArgumentParser(description="Convert cURL command to sqlmap-compatible HTTP request")
    parser.add_argument("curl", help="cURL command string or file path", nargs="?")
    parser.add_argument("--file", help="Output file (default: request.txt)", default="request.txt")
    args = parser.parse_args()

    # If no curl command provided, use example
    if not args.curl:
        curl_cmd = (
            """curl 'http://localhost:5000/api/v1/auth' -H 'Accept: application/json, text/plain, */*' """
            """-H 'Content-Type: application/json' --data-raw '{"username":"admin1","password":"secret1234"}'"""
        )
        print("No cURL command provided, using example:")
        print(curl_cmd)
    else:
        # Check if input is a file
        try:
            with open(args.curl, "r") as f:
                curl_cmd = f.read().strip()
        except FileNotFoundError:
            curl_cmd = args.curl

    try:
        http_request = parse_curl_command(curl_cmd)
        print("Generated HTTP request:")
        print(http_request)
        with open(args.file, "w") as f:
            f.write(http_request)
        print(f"Saved to {args.file}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()