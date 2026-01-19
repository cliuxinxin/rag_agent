import sys
import requests
from bs4 import BeautifulSoup

def get_stock_finviz(symbol):
    """
    通过爬取 Finviz 网站获取美股数据，不依赖 yfinance
    """
    try:
        url = f"https://finviz.com/quote.ashx?t={symbol}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # 请求网站
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 404:
            print(f"Error: Symbol '{symbol}' not found on Finviz.")
            return

        soup = BeautifulSoup(response.content, 'html.parser')

        # 1. 获取股价 (Finviz 的股价通常在一个特定的 class 里，或者表格里)
        # Finviz 的页面结构中，当前价格通常在 snapshot-table2 里
        price = "N/A"
        
        # 方法 A: 尝试直接抓取大字体的价格
        quote_price = soup.find(class_="quote-header_ticker-price-toggle")
        if quote_price:
            price = quote_price.text.strip()
        else:
            # 方法 B: 从表格抓取
            snapshot_table = soup.find(class_="snapshot-table2")
            if snapshot_table:
                rows = snapshot_table.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    for i, col in enumerate(cols):
                        if "Price" in col.text and i + 1 < len(cols):
                            price = cols[i+1].text.strip()
                            break

        # 2. 获取公司名称
        title = soup.find("title")
        company_name = title.text.split("Stock Quote")[0].strip() if title else symbol

        # 3. 获取行业
        links = soup.find_all("a", class_="tab-link")
        industry = "N/A"
        if len(links) > 2:
            industry = links[2].text # 通常第3个链接是行业

        print(f"--- {company_name} ---")
        print(f"Source: Finviz")
        print(f"Current Price: {price} USD")
        print(f"Industry: {industry}")
        print(f"Status: Online")

    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper().strip().replace(",", "")
        get_stock_finviz(symbol)
    else:
        print("Error: No stock symbol provided.")