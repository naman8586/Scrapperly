import re
import time
import json
import sys
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Supported fields for user selection
SUPPORTED_FIELDS = [
    'url', 'title', 'currency', 'exact_price', 'description', 'min_order',
    'supplier', 'feedback', 'image_url', 'images', 'videos', 'dimensions',
    'website_name', 'discount_information', 'brand_name', 'origin'
]

# Get command-line arguments
if len(sys.argv) != 5:
    print("Usage: python ebay_scraper.py <search_keyword> <page_count> <retries> <fields>")
    sys.exit(1)

search_keyword = sys.argv[1].strip()
try:
    page_count = int(sys.argv[2])
    retries = int(sys.argv[3])
    if page_count < 1 or retries < 1:
        raise ValueError("page_count and retries must be positive integers")
except ValueError as e:
    print(f"Error: {e}")
    sys.exit(1)

# Parse and validate fields
fields = [f.strip() for f in sys.argv[4].split(',') if f.strip()]
desired_fields = ['url', 'website_name'] + [f for f in fields if f in SUPPORTED_FIELDS]
invalid_fields = [f for f in fields if f not in SUPPORTED_FIELDS]
if invalid_fields:
    print(f"Error: Invalid fields: {', '.join(invalid_fields)}. Supported fields: {', '.join(SUPPORTED_FIELDS)}")
    sys.exit(1)
if not desired_fields:
    print("Error: No valid fields specified")
    sys.exit(1)

# Setup output file
output_file = f"products_{search_keyword.replace(' ', '_').lower()}_ebay.json"

def initialize_driver():
    """Configure and return a Selenium WebDriver instance."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.set_page_load_timeout(30)
        return driver
    except WebDriverException as e:
        print(f"Error initializing Chrome browser: {e}")
        sys.exit(1)

def retry_extraction(func, attempts=3, delay=1, default=None):
    """Retries an extraction function up to 'attempts' times."""
    for i in range(attempts):
        try:
            result = func()
            if result is not None:
                return result
        except Exception as e:
            if i < attempts - 1:
                time.sleep(delay + random.uniform(0, 0.5))
    return default

def filter_product_data(product_data):
    """Filter product data to include only desired fields."""
    return {field: product_data[field] for field in desired_fields if field in product_data}

def scrape_ebay_products():
    """Main scraping function."""
    browser = initialize_driver()
    scraped_products = {}
    try:
        for page in range(1, page_count + 1):
            for attempt in range(retries):
                try:
                    search_url = f"https://www.ebay.com/sch/i.html?_nkw={search_keyword.replace(' ', '+')}&_sacat=0&_pgn={page}"
                    print(f"Scraping page {page}, attempt {attempt + 1}/{retries}: {search_url}")
                    browser.get(search_url)
                    WebDriverWait(browser, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "ul.srp-results"))
                    )

                    # Parse product cards
                    soup = BeautifulSoup(browser.page_source, "html.parser")
                    product_cards = soup.select("div.s-item__wrapper")
                    if not product_cards:
                        print(f"No product cards found on page {page}")
                        break

                    for product in product_cards:
                        product_data = {
                            "url": "",
                            "title": "",
                            "currency": "",
                            "exact_price": "",
                            "description": "",
                            "min_order": "1 unit",
                            "supplier": "",
                            "feedback": {"rating": "", "review": ""},
                            "image_url": "",
                            "images": [],
                            "videos": [],
                            "dimensions": "",
                            "website_name": "eBay.com",
                            "discount_information": "",
                            "brand_name": "",
                            "origin": ""
                        }

                        # Extract URL and title
                        title_link = product.select_one("a.s-item__link")
                        if title_link:
                            if 'title' in desired_fields:
                                title = retry_extraction(
                                    lambda: title_link.select_one("span[role='heading']").get_text(strip=True),
                                    default=""
                                )
                                product_data["title"] = title
                            if 'url' in desired_fields:
                                url = title_link.get("href", "").split('?')[0]
                                product_data["url"] = url
                                print(f"Product URL: {url}")

                        # Skip duplicates
                        if product_data["url"] in scraped_products:
                            continue

                        # Extract currency and price
                        if 'currency' in desired_fields or 'exact_price' in desired_fields:
                            price_elem = product.select_one("span.s-item__price")
                            if price_elem:
                                price_text = retry_extraction(lambda: price_elem.get_text(strip=True), default="")
                                if price_text:
                                    currency_match = re.match(r"([A-Z$€£]+)", price_text)
                                    price_match = re.search(r'\d+(?:\.\d+)?', price_text.replace(",", ""))
                                    if currency_match:
                                        product_data["currency"] = currency_match.group(1).strip()
                                        print(f"Currency: {product_data['currency']}")
                                    if price_match:
                                        product_data["exact_price"] = price_match.group(0)
                                        print(f"Exact price: {product_data['exact_price']}")

                        # Extract origin
                        if 'origin' in desired_fields:
                            origin_elem = product.select_one("span.s-item__location")
                            if origin_elem:
                                origin_text = origin_elem.get_text(strip=True)
                                if origin_text.startswith("from "):
                                    product_data["origin"] = origin_text[5:].strip()
                                    print(f"Origin: {product_data['origin']}")

                        # Scrape product page for additional details
                        if product_data["url"] and any(field in desired_fields for field in [
                            'description', 'supplier', 'feedback', 'image_url', 'images', 'dimensions',
                            'discount_information', 'brand_name'
                        ]):
                            try:
                                browser.get(product_data["url"])
                                WebDriverWait(browser, 10).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, "div#viTabs_0_is"))
                                )
                                product_soup = BeautifulSoup(browser.page_source, "html.parser")

                                # Re-extract price
                                if 'currency' in desired_fields or 'exact_price' in desired_fields:
                                    price_elem = product_soup.select_one("div.x-price-primary span.ux-textspans")
                                    if price_elem:
                                        price_text = retry_extraction(lambda: price_elem.get_text(strip=True), default="")
                                        if price_text:
                                            currency_match = re.match(r"([A-Z$€£]+)", price_text)
                                            price_match = re.search(r'\d+(?:\.\d+)?', price_text.replace(",", ""))
                                            if currency_match:
                                                product_data["currency"] = currency_match.group(1).strip()
                                                print(f"Currency (product page): {product_data['currency']}")
                                            if price_match:
                                                product_data["exact_price"] = price_match.group(0)
                                                print(f"Exact price (product page): {product_data['exact_price']}")

                                # Extract description
                                if 'description' in desired_fields:
                                    desc_elem = product_soup.select_one("div#viTabs_0_is")
                                    if desc_elem:
                                        product_data["description"] = retry_extraction(
                                            lambda: desc_elem.get_text(strip=True), default=""
                                        )
                                        print(f"Description: {product_data['description'][:100]}...")

                                # Extract supplier
                                if 'supplier' in desired_fields:
                                    supplier_elem = product_soup.select_one("a[href*='ebay.com/str/'] span.ux-textspans--BOLD")
                                    if supplier_elem:
                                        product_data["supplier"] = retry_extraction(
                                            lambda: supplier_elem.get_text(strip=True), default=""
                                        )
                                        print(f"Supplier: {product_data['supplier']}")

                                # Extract feedback
                                if 'feedback' in desired_fields:
                                    feedback_elem = product_soup.select_one("div.ux-seller-card")
                                    if feedback_elem:
                                        review_elem = feedback_elem.select_one("span.SECONDARY")
                                        if review_elem:
                                            review_text = retry_extraction(lambda: review_elem.get_text(strip=True), default="")
                                            review_match = re.search(r'\((\d+(?:,\d+)*)\)', review_text)
                                            if review_match:
                                                product_data["feedback"]["review"] = review_match.group(1).replace(",", "")
                                        rating_elem = feedback_elem.select_one("span.ux-textspans--PSEUDOLINK")
                                        if rating_elem:
                                            rating_text = retry_extraction(lambda: rating_elem.get_text(strip=True), default="")
                                            rating_match = re.search(r"(\d+(?:\.\d+)?)%", rating_text)
                                            if rating_match:
                                                rating = round(1 + 4 * (float(rating_match.group(1)) / 100), 1)
                                                product_data["feedback"]["rating"] = str(rating)
                                                print(f"Rating: {rating}, Reviews: {product_data['feedback']['review']}")

                                # Extract images
                                if 'image_url' in desired_fields or 'images' in desired_fields:
                                    image_urls = set()
                                    carousel_items = product_soup.select("div.ux-image-carousel-item img")
                                    for item in carousel_items:
                                        src = retry_extraction(lambda: item.get("src"), default="")
                                        if src:
                                            image_urls.add(src)
                                        zoom_src = retry_extraction(lambda: item.get("data-zoom-src"), default="")
                                        if zoom_src:
                                            image_urls.add(zoom_src)
                                    if image_urls:
                                        image_urls = sorted(list(image_urls), key=lambda x: int(re.search(r's-l(\d+)', x).group(1)) if re.search(r's-l(\d+)', x) else 0, reverse=True)
                                        if 'image_url' in desired_fields:
                                            product_data["image_url"] = image_urls[0]
                                        if 'images' in desired_fields:
                                            product_data["images"] = image_urls
                                        print(f"Primary image URL: {product_data['image_url']}")

                                # Extract dimensions
                                if 'dimensions' in desired_fields:
                                    spec_section = product_soup.select_one("div.ux-layout-section-evo")
                                    if spec_section:
                                        labels = spec_section.select("div.ux-labels-values__labels")
                                        dimensions = []
                                        for label in labels:
                                            label_text = label.get_text(strip=True).lower()
                                            if "size" in label_text or "dimensions" in label_text:
                                                value_elem = label.find_parent().find_next_sibling("div.ux-labels-values__values")
                                                if value_elem:
                                                    dim_text = retry_extraction(
                                                        lambda: value_elem.select_one("span.ux-textspans").get_text(strip=True),
                                                        default=""
                                                    )
                                                    if dim_text:
                                                        dimensions.append(f"{label_text}: {dim_text}")
                                        if dimensions:
                                            product_data["dimensions"] = "; ".join(dimensions)
                                            print(f"Dimensions: {product_data['dimensions']}")

                                # Extract discount
                                if 'discount_information' in desired_fields:
                                    discount_elem = product_soup.select_one("span.ux-textspans--STRIKETHROUGH")
                                    if discount_elem:
                                        original_price = retry_extraction(lambda: discount_elem.get_text(strip=True), default="")
                                        current_price = product_data.get("exact_price", "")
                                        if original_price and current_price:
                                            try:
                                                orig_val = float(re.search(r'\d+(?:\.\d+)?', original_price.replace(",", "")).group(0))
                                                curr_val = float(current_price)
                                                if orig_val > curr_val:
                                                    discount = ((orig_val - curr_val) / orig_val) * 100
                                                    product_data["discount_information"] = f"{discount:.2f}% off"
                                                    print(f"Discount: {product_data['discount_information']}")
                                            except (ValueError, AttributeError):
                                                pass

                                # Extract brand
                                if 'brand_name' in desired_fields:
                                    brand_elem = product_soup.select_one("div.ux-labels-values__labels:-soup-contains('Brand')")
                                    if brand_elem:
                                        brand_name = retry_extraction(
                                            lambda: brand_elem.find_next_sibling("div").select_one("span.ux-textspans").get_text(strip=True),
                                            default=""
                                        )
                                        product_data["brand_name"] = brand_name
                                        print(f"Brand: {brand_name}")

                            except Exception as e:
                                print(f"Error scraping product page {product_data['url']}: {e}")

                        # Save filtered product
                        if product_data["url"]:
                            scraped_products[product_data["url"]] = filter_product_data(product_data)

                    # Random delay to avoid rate limiting
                    time.sleep(random.uniform(1, 3))
                    break
                except (TimeoutException, WebDriverException) as e:
                    print(f"Attempt {attempt + 1}/{retries}: Error scraping page {page}: {e}")
                    time.sleep(5 + random.uniform(0, 2))
            else:
                print(f"Failed to scrape page {page} after {retries} attempts.")

        # Save to JSON
        if scraped_products:
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(list(scraped_products.values()), f, ensure_ascii=False, indent=4)
                print(f"Scraped {len(scraped_products)} products. Saved to {output_file}")
            except Exception as e:
                print(f"Error saving JSON file: {e}")
        else:
            print("No products scraped. JSON file not created.")

    finally:
        browser.quit()

if __name__ == "__main__":
    scrape_ebay_products()