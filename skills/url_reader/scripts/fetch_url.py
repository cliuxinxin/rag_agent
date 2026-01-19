import sys
import requests
from bs4 import BeautifulSoup

def fetch_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text()
        
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        print(f"--- Content from {url} ---")
        print(clean_text[:3000] + "...\n(Truncated)")
        
    except Exception as e:
        print(f"Error fetching URL: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        fetch_text(sys.argv[1])
    else:
        print("Error: No URL provided.")
