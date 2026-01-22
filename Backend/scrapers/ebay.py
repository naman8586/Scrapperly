#!/usr/bin/env python3
"""
eBay Scraper - Integrated with Node.js Backend
Modified to work with the backend scraper executor
"""

import re
import time
import json
import sys
import random
import logging
import argparse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ebay_scraper.log'),
    ]
)

# Supported fields
SUPPORTED_FIELDS = [
    'url', 'title', 'currency', 'exact_price', 'description', 'min_order',
    'supplier', 'feedback', 'image_url', 'images', 'videos', 'dimensions',
    'website_name', 'discount_information', 'brand_name', 'origin'
]

# Field mapping for frontend compatibility
FIELD_MAPPING = {
    'price': 'exact_price',
    'seller': 'supplier',
    'condition': 'description',
    'rating': 'feedback',
    'shipping': 'dimensions',
    'location': 'origin'
}


class EbayScraper:
    def __init__(self, query, fields, max_items, job_id):
        self.query = query
        self.fields = self._map_fields(fields)
        self.max_items = max_items
        self.job_id = job_id
        self.scraped_count = 0
        self.browser = None
        
    def _map_fields(self, fields):
        """Map frontend field names to backend field names"""
        mapped = []
        for field in fields:
            field = field.strip()
            mapped_field = FIELD_MAPPING.get(field, field)
            mapped.append(mapped_field)
        # Always include url and website_name
        return list(set(['url', 'website_name'] + mapped))
    
    def send_progress(self, scraped, total):
        """Send progress update to Node.js backend"""
        progress_data = {
            "type": "progress",
            "scraped": scraped,
            "total": total
        }
        print(json.dumps(progress_data), flush=True)
    
    def send_item(self, item, url, index):
        """Send scraped item to Node.js backend"""
        item_data = {
            "type": "item",
            "item": item,
            "url": url,
            "index": index
        }
        print(json.dumps(item_data), flush=True)
    
    def send_error(self, message):
        """Send error message to stderr"""
        error_data = {
            "type": "error",
            "message": message
        }
        print(json.dumps(error_data), file=sys.stderr, flush=True)
    
    def init_browser(self):
        """Initialize Selenium browser"""
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
            self.browser = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
            self.browser.set_page_load_timeout(30)
            logging.info("Chrome browser initialized successfully")
        except WebDriverException as e:
            raise Exception(f"Error initializing Chrome browser: {str(e)}")
    
    def retry_extraction(self, func, attempts=3, delay=1, default=None):
        """Retries an extraction function up to 'attempts' times"""
        for i in range(attempts):
            try:
                result = func()
                if result is not None:
                    return result
            except Exception as e:
                if i < attempts - 1:
                    time.sleep(delay + random.uniform(0, 0.5))
        return default
    
    def filter_product_data(self, product_data):
        """Filter product data to include only desired fields"""
        return {field: product_data[field] for field in self.fields if field in product_data}
    
    def scrape_product_list_page(self, page_num):
        """Scrape a single search results page"""
        products = []
        
        try:
            search_url = f"https://www.ebay.com/sch/i.html?_nkw={self.query.replace(' ', '+')}&_sacat=0&_pgn={page_num}"
            logging.info(f"Scraping page {page_num}: {search_url}")
            
            self.browser.get(search_url)
            WebDriverWait(self.browser, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ul.srp-results"))
            )
            
            # Parse product cards
            soup = BeautifulSoup(self.browser.page_source, "html.parser")
            product_cards = soup.select("div.s-item__wrapper")
            
            if not product_cards:
                logging.warning(f"No product cards found on page {page_num}")
                return products
            
            for product in product_cards:
                if self.scraped_count >= self.max_items:
                    break
                
                product_data = self.scrape_product_card(product)
                if product_data:
                    products.append(product_data)
            
            # Random delay to avoid rate limiting
            time.sleep(random.uniform(1, 2))
            
            return products
            
        except (TimeoutException, WebDriverException) as e:
            logging.error(f"Error scraping page {page_num}: {str(e)}")
            return products
    
    def scrape_product_card(self, product):
        """Extract data from a product card"""
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
        
        try:
            # Extract URL and title
            title_link = product.select_one("a.s-item__link")
            if title_link:
                if 'title' in self.fields:
                    title = self.retry_extraction(
                        lambda: title_link.select_one("span[role='heading']").get_text(strip=True),
                        default=""
                    )
                    product_data["title"] = title
                
                if 'url' in self.fields:
                    url = title_link.get("href", "").split('?')[0]
                    product_data["url"] = url
            
            if not product_data["url"]:
                return None
            
            # Extract currency and price
            if 'currency' in self.fields or 'exact_price' in self.fields:
                price_elem = product.select_one("span.s-item__price")
                if price_elem:
                    price_text = self.retry_extraction(
                        lambda: price_elem.get_text(strip=True),
                        default=""
                    )
                    if price_text:
                        currency_match = re.match(r"([A-Z$€£]+)", price_text)
                        price_match = re.search(r'\d+(?:\.\d+)?', price_text.replace(",", ""))
                        if currency_match:
                            product_data["currency"] = currency_match.group(1).strip()
                        if price_match:
                            product_data["exact_price"] = price_match.group(0)
            
            # Extract origin
            if 'origin' in self.fields:
                origin_elem = product.select_one("span.s-item__location")
                if origin_elem:
                    origin_text = origin_elem.get_text(strip=True)
                    if origin_text.startswith("from "):
                        product_data["origin"] = origin_text[5:].strip()
            
            # Scrape product page for additional details if needed
            if any(field in self.fields for field in [
                'description', 'supplier', 'feedback', 'image_url', 'images',
                'dimensions', 'discount_information', 'brand_name'
            ]):
                self.scrape_product_page_details(product_data)
            
            return self.filter_product_data(product_data)
            
        except Exception as e:
            logging.error(f"Error scraping product card: {str(e)}")
            return None
    
    def scrape_product_page_details(self, product_data):
        """Visit product page and extract detailed information"""
        try:
            self.browser.get(product_data["url"])
            WebDriverWait(self.browser, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div#viTabs_0_is"))
            )
            product_soup = BeautifulSoup(self.browser.page_source, "html.parser")
            
            # Re-extract price from product page (more accurate)
            if 'currency' in self.fields or 'exact_price' in self.fields:
                price_elem = product_soup.select_one("div.x-price-primary span.ux-textspans")
                if price_elem:
                    price_text = self.retry_extraction(
                        lambda: price_elem.get_text(strip=True),
                        default=""
                    )
                    if price_text:
                        currency_match = re.match(r"([A-Z$€£]+)", price_text)
                        price_match = re.search(r'\d+(?:\.\d+)?', price_text.replace(",", ""))
                        if currency_match:
                            product_data["currency"] = currency_match.group(1).strip()
                        if price_match:
                            product_data["exact_price"] = price_match.group(0)
            
            # Extract description
            if 'description' in self.fields:
                desc_elem = product_soup.select_one("div#viTabs_0_is")
                if desc_elem:
                    product_data["description"] = self.retry_extraction(
                        lambda: desc_elem.get_text(strip=True)[:500],  # Limit to 500 chars
                        default=""
                    )
            
            # Extract supplier
            if 'supplier' in self.fields:
                supplier_elem = product_soup.select_one("a[href*='ebay.com/str/'] span.ux-textspans--BOLD")
                if supplier_elem:
                    product_data["supplier"] = self.retry_extraction(
                        lambda: supplier_elem.get_text(strip=True),
                        default=""
                    )
            
            # Extract feedback
            if 'feedback' in self.fields:
                feedback_elem = product_soup.select_one("div.ux-seller-card")
                if feedback_elem:
                    review_elem = feedback_elem.select_one("span.SECONDARY")
                    if review_elem:
                        review_text = self.retry_extraction(
                            lambda: review_elem.get_text(strip=True),
                            default=""
                        )
                        review_match = re.search(r'\((\d+(?:,\d+)*)\)', review_text)
                        if review_match:
                            product_data["feedback"]["review"] = review_match.group(1).replace(",", "")
                    
                    rating_elem = feedback_elem.select_one("span.ux-textspans--PSEUDOLINK")
                    if rating_elem:
                        rating_text = self.retry_extraction(
                            lambda: rating_elem.get_text(strip=True),
                            default=""
                        )
                        rating_match = re.search(r"(\d+(?:\.\d+)?)%", rating_text)
                        if rating_match:
                            rating = round(1 + 4 * (float(rating_match.group(1)) / 100), 1)
                            product_data["feedback"]["rating"] = str(rating)
            
            # Extract images
            if 'image_url' in self.fields or 'images' in self.fields:
                image_urls = set()
                carousel_items = product_soup.select("div.ux-image-carousel-item img")
                for item in carousel_items:
                    src = self.retry_extraction(lambda: item.get("src"), default="")
                    if src:
                        image_urls.add(src)
                    zoom_src = self.retry_extraction(lambda: item.get("data-zoom-src"), default="")
                    if zoom_src:
                        image_urls.add(zoom_src)
                
                if image_urls:
                    image_urls = sorted(
                        list(image_urls),
                        key=lambda x: int(re.search(r's-l(\d+)', x).group(1)) if re.search(r's-l(\d+)', x) else 0,
                        reverse=True
                    )
                    if 'image_url' in self.fields:
                        product_data["image_url"] = image_urls[0]
                    if 'images' in self.fields:
                        product_data["images"] = image_urls
            
            # Extract dimensions
            if 'dimensions' in self.fields:
                spec_section = product_soup.select_one("div.ux-layout-section-evo")
                if spec_section:
                    labels = spec_section.select("div.ux-labels-values__labels")
                    dimensions = []
                    for label in labels:
                        label_text = label.get_text(strip=True).lower()
                        if "size" in label_text or "dimensions" in label_text:
                            value_elem = label.find_parent().find_next_sibling("div.ux-labels-values__values")
                            if value_elem:
                                dim_text = self.retry_extraction(
                                    lambda: value_elem.select_one("span.ux-textspans").get_text(strip=True),
                                    default=""
                                )
                                if dim_text:
                                    dimensions.append(f"{label_text}: {dim_text}")
                    if dimensions:
                        product_data["dimensions"] = "; ".join(dimensions)
            
            # Extract discount
            if 'discount_information' in self.fields:
                discount_elem = product_soup.select_one("span.ux-textspans--STRIKETHROUGH")
                if discount_elem:
                    original_price = self.retry_extraction(
                        lambda: discount_elem.get_text(strip=True),
                        default=""
                    )
                    current_price = product_data.get("exact_price", "")
                    if original_price and current_price:
                        try:
                            orig_val = float(re.search(r'\d+(?:\.\d+)?', original_price.replace(",", "")).group(0))
                            curr_val = float(current_price)
                            if orig_val > curr_val:
                                discount = ((orig_val - curr_val) / orig_val) * 100
                                product_data["discount_information"] = f"{discount:.2f}% off"
                        except (ValueError, AttributeError):
                            pass
            
            # Extract brand
            if 'brand_name' in self.fields:
                brand_elem = product_soup.select_one("div.ux-labels-values__labels:-soup-contains('Brand')")
                if brand_elem:
                    brand_name = self.retry_extraction(
                        lambda: brand_elem.find_next_sibling("div").select_one("span.ux-textspans").get_text(strip=True),
                        default=""
                    )
                    product_data["brand_name"] = brand_name
            
        except Exception as e:
            logging.error(f"Error scraping product page {product_data['url']}: {str(e)}")
    
    def scrape(self):
        """Main scraping logic"""
        try:
            self.init_browser()
            
            # Calculate how many pages we need
            items_per_page = 50  # eBay typically shows ~50 items per page
            max_pages = min(10, (self.max_items // items_per_page) + 1)
            
            self.send_progress(0, self.max_items)
            
            scraped_urls = set()
            
            for page_num in range(1, max_pages + 1):
                if self.scraped_count >= self.max_items:
                    break
                
                logging.info(f"Scraping page {page_num}")
                products = self.scrape_product_list_page(page_num)
                
                for product in products:
                    if self.scraped_count >= self.max_items:
                        break
                    
                    # Skip duplicates
                    if product.get('url') in scraped_urls:
                        continue
                    
                    scraped_urls.add(product.get('url'))
                    
                    # Send item to backend
                    self.send_item(product, product.get('url', ''), self.scraped_count)
                    self.scraped_count += 1
                    self.send_progress(self.scraped_count, self.max_items)
                
                # Delay between pages
                time.sleep(random.uniform(2, 4))
            
            logging.info(f"Scraping completed. Total items: {self.scraped_count}")
            
        except Exception as e:
            raise Exception(f"Fatal error during scraping: {str(e)}")
        finally:
            if self.browser:
                self.browser.quit()
    
    def run(self):
        """Execute scraping with error handling"""
        try:
            self.scrape()
            return 0
        except Exception as e:
            self.send_error(str(e))
            return 1


def main():
    """Parse arguments and run scraper"""
    parser = argparse.ArgumentParser(description='eBay Scraper')
    parser.add_argument('--query', required=True, help='Search query')
    parser.add_argument('--fields', required=True, help='Comma-separated list of fields to scrape')
    parser.add_argument('--max-items', type=int, default=100, help='Maximum items to scrape')
    parser.add_argument('--job-id', required=True, help='Job ID from database')
    
    args = parser.parse_args()
    
    fields = args.fields.split(',')
    
    scraper = EbayScraper(
        query=args.query,
        fields=fields,
        max_items=args.max_items,
        job_id=args.job_id
    )
    
    return scraper.run()


if __name__ == '__main__':
    sys.exit(main())