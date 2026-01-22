#!/usr/bin/env python3
"""
IndiaMART Scraper - Integrated with Node.js Backend
Modified to work with the backend scraper executor
"""

import sys
import json
import re
import time
import random
import logging
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, StaleElementReferenceException
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('indiamart_scraper.log'),
    ]
)
logger = logging.getLogger(__name__)

# Supported fields
SUPPORTED_FIELDS = [
    'url', 'title', 'currency', 'exact_price', 'description', 'min_order',
    'supplier', 'origin', 'feedback', 'image_url', 'images', 'videos',
    'dimensions', 'website_name', 'discount_information', 'brand_name'
]

# Field mapping
FIELD_MAPPING = {
    'price': 'exact_price',
    'company': 'supplier',
    'location': 'origin',
    'rating': 'feedback'
}


class IndiaMartScraper:
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
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        try:
            self.browser = webdriver.Chrome(
                service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                options=options
            )
            self.browser.set_page_load_timeout(30)
            self.browser.maximize_window()
            logger.info("Chrome browser initialized successfully")
        except WebDriverException as e:
            raise Exception(f"Error initializing Chrome browser: {str(e)}")
    
    def clean_text(self, text):
        """Clean text by removing extra whitespace"""
        if not text:
            return None
        text = re.sub(r'<[^>]+>', '', text)
        return ' '.join(text.strip().split())
    
    def clean_title(self, title):
        """Clean up product title"""
        if not title:
            return None
        title = self.clean_text(title)
        title = re.sub(r'[^\w\s,()&-]', '', title)
        
        # Remove duplicates
        parts = re.split(r'[,|/]', title)
        parts = [part.strip() for part in parts if part.strip()]
        seen_phrases = set()
        cleaned_parts = []
        for part in parts:
            part_lower = part.lower()
            if part_lower not in seen_phrases:
                seen_phrases.add(part_lower)
                cleaned_parts.append(part)
        
        title = " ".join(cleaned_parts)
        if len(title) > 100:
            title = title[:97] + "..."
        return title
    
    def parse_price(self, price_text):
        """Parse price from text"""
        if not price_text:
            return {'currency': None, 'exact_price': None}
        
        if "Ask Price" in price_text or "Call" in price_text:
            return {"currency": None, "exact_price": "Ask Price"}
        
        currency = None
        currency_symbols = ["₹", "$", "€", "¥", "£", "Rs"]
        for symbol in currency_symbols:
            if symbol in price_text:
                currency = symbol
                break
        if not currency and "rs" in price_text.lower():
            currency = "₹"
        
        clean_text = re.sub(r'[^\d.,]', '', price_text)
        price_pattern = r'(\d+(?:,\d{3})*(?:\.\d+)?)'
        price_matches = re.findall(price_pattern, clean_text)
        price_values = [re.sub(r'[^\d.]', '', p) for p in price_matches]
        
        if price_values:
            return {"currency": currency, "exact_price": price_values[0]}
        return {'currency': currency, 'exact_price': None}
    
    def retry_extraction(self, func, attempts=3, delay=1, default=None):
        """Retry extraction with attempts"""
        for i in range(attempts):
            try:
                result = func()
                if result:
                    return result
            except Exception as e:
                if i < attempts - 1:
                    time.sleep(delay)
        return default
    
    def filter_product_data(self, product_data):
        """Filter product data to include only desired fields"""
        return {field: product_data[field] for field in self.fields if field in product_data}
    
    def extract_product_data(self, card):
        """Extract product data from a card element"""
        product = {
            "url": None,
            "title": None,
            "currency": None,
            "exact_price": None,
            "description": None,
            "min_order": "1 unit",
            "supplier": None,
            "origin": None,
            "feedback": {"rating": None, "review": None},
            "image_url": None,
            "images": [],
            "videos": [],
            "dimensions": None,
            "website_name": "IndiaMart",
            "discount_information": None,
            "brand_name": None
        }
        
        try:
            soup = BeautifulSoup(card.get_attribute('outerHTML'), 'html.parser')
            
            # Title
            if 'title' in self.fields:
                title_selectors = [
                    'div.producttitle',
                    'div.titleAskPriceImageNavigation a',
                    'a.product-title',
                    'h2.product-name'
                ]
                title_el = None
                for selector in title_selectors:
                    title_el = soup.select_one(selector)
                    if title_el:
                        break
                if title_el:
                    raw_title = self.retry_extraction(
                        lambda: self.clean_text(title_el.get_text(strip=True))
                    )
                    product['title'] = self.clean_title(raw_title) if raw_title else None
                
                if not product['title']:
                    return None
            
            # URL
            if 'url' in self.fields:
                url_selectors = [
                    'div.titleAskPriceImageNavigation a',
                    'a.product-title',
                    'a.cardlinks',
                    'a[href]'
                ]
                for selector in url_selectors:
                    a_tag = soup.select_one(selector)
                    if a_tag:
                        href = self.retry_extraction(lambda: a_tag.get('href', None))
                        if href and ("indiamart.com" in href or href.startswith('/')):
                            product['url'] = href if href.startswith('http') else f"https://www.indiamart.com{href}"
                            if product['url'] and '?' in product['url']:
                                product['url'] = product['url'].split('?')[0]
                            break
                
                if not product['url']:
                    return None
            
            # Price
            if 'currency' in self.fields or 'exact_price' in self.fields:
                price_selectors = [
                    'p.price', 'div.price', 'span.price',
                    'div.mprice', 'span.mrp', '*[class*="price"]'
                ]
                price_el = None
                for selector in price_selectors:
                    price_el = soup.select_one(selector)
                    if price_el:
                        break
                if price_el:
                    price_text = self.retry_extraction(lambda: price_el.get_text(strip=True))
                    price_info = self.parse_price(price_text)
                    product.update(price_info)
            
            # Description
            if 'description' in self.fields:
                desc_selectors = ['div.description', 'p.description', 'div.prod-desc']
                desc_el = None
                for selector in desc_selectors:
                    desc_el = soup.select_one(selector)
                    if desc_el:
                        break
                product['description'] = self.retry_extraction(
                    lambda: self.clean_text(desc_el.get_text(strip=True))[:500],
                    default=None
                )
            
            # Min Order
            if 'min_order' in self.fields:
                moq_selectors = ['span.unit', 'div.moq', '*[class*="moq"]']
                moq_el = None
                for selector in moq_selectors:
                    moq_el = soup.select_one(selector)
                    if moq_el:
                        break
                if moq_el:
                    text = self.retry_extraction(lambda: self.clean_text(moq_el.get_text(strip=True)))
                    if text:
                        qty_match = re.search(r'(\d+)', text)
                        unit_match = re.search(r'([A-Za-z]+)', text)
                        qty = qty_match.group(1) if qty_match else None
                        unit = unit_match.group(1) if unit_match else None
                        product['min_order'] = f"{qty} {unit}" if qty and unit else "1 unit"
            
            # Supplier
            if 'supplier' in self.fields:
                supplier_selectors = ['div.companyname a', 'div.companyname', 'p.company-name']
                supplier_el = None
                for selector in supplier_selectors:
                    supplier_el = soup.select_one(selector)
                    if supplier_el:
                        break
                product['supplier'] = self.retry_extraction(
                    lambda: self.clean_text(supplier_el.get_text(strip=True)),
                    default=None
                )
            
            # Origin
            if 'origin' in self.fields:
                origin_selectors = ['span.origin', 'div[class*="origin"]']
                origin_el = None
                for selector in origin_selectors:
                    origin_el = soup.select_one(selector)
                    if origin_el:
                        break
                product['origin'] = self.retry_extraction(
                    lambda: self.clean_text(origin_el.get_text(strip=True)),
                    default=None
                )
            
            # Feedback
            if 'feedback' in self.fields:
                rating_el = soup.select_one('div.rating, span.rating, *[class*="rating"]')
                if rating_el:
                    rating_text = self.retry_extraction(lambda: rating_el.get_text(strip=True))
                    rating_match = re.search(r'([\d.]+)', rating_text) if rating_text else None
                    product['feedback']['rating'] = rating_match.group(1) if rating_match else None
            
            # Images
            if 'images' in self.fields or 'image_url' in self.fields:
                img_selectors = ['img[class*="product-img"]', 'img[src*="product"]', 'img[src]']
                images = []
                image_url = None
                for selector in img_selectors:
                    img_elements = soup.select(selector)
                    if img_elements:
                        for idx, img in enumerate(img_elements):
                            src = self.retry_extraction(
                                lambda: img.get('src', '') or img.get('data-src', ''),
                                default=''
                            )
                            if src and not src.startswith('data:') and not src.endswith(('placeholder.png', 'default.jpg')):
                                if idx == 0:
                                    image_url = src
                                images.append(src)
                        break
                product['image_url'] = image_url
                product['images'] = images if images else []
            
            return self.filter_product_data(product)
            
        except (StaleElementReferenceException, Exception) as e:
            logger.error(f"Error extracting product data: {str(e)}")
            return None
    
    def scrape_product_list_page(self, page_num):
        """Scrape a single search results page"""
        products = []
        
        try:
            url = f"https://dir.indiamart.com/search.mp?ss={quote(self.query.replace(' ', '+'))}&page={page_num}"
            logger.info(f"Scraping page {page_num}: {url}")
            
            self.browser.get(url)
            WebDriverWait(self.browser, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Scroll to load products
            for _ in range(3):
                self.browser.execute_script(
                    "window.scrollTo(0, Math.min(document.body.scrollHeight, window.scrollY + 800));"
                )
                time.sleep(random.uniform(0.5, 1))
            
            # Find product cards
            product_cards_selectors = [
                'div.card',
                'div.product-card',
                'div.listing',
                'div[class*="product"]'
            ]
            product_cards = None
            for selector in product_cards_selectors:
                try:
                    product_cards = WebDriverWait(self.browser, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                    )
                    if product_cards:
                        logger.info(f"Found {len(product_cards)} products with selector: {selector}")
                        break
                except TimeoutException:
                    continue
            
            if not product_cards:
                logger.warning(f"No products found on page {page_num}")
                return products
            
            for card in product_cards:
                if self.scraped_count >= self.max_items:
                    break
                
                product = self.extract_product_data(card)
                if product:
                    products.append(product)
                
                time.sleep(random.uniform(0.3, 0.7))
            
            return products
            
        except Exception as e:
            logger.error(f"Error scraping page {page_num}: {str(e)}")
            return products
    
    def scrape(self):
        """Main scraping logic"""
        try:
            self.init_browser()
            
            # Calculate pages needed
            items_per_page = 30
            max_pages = min(10, (self.max_items // items_per_page) + 1)
            
            self.send_progress(0, self.max_items)
            
            scraped_urls = set()
            
            for page_num in range(1, max_pages + 1):
                if self.scraped_count >= self.max_items:
                    break
                
                logger.info(f"Scraping page {page_num}")
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
            
            logger.info(f"Scraping completed. Total items: {self.scraped_count}")
            
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
    parser = argparse.ArgumentParser(description='IndiaMART Scraper')
    parser.add_argument('--query', required=True, help='Search query')
    parser.add_argument('--fields', required=True, help='Comma-separated list of fields to scrape')
    parser.add_argument('--max-items', type=int, default=100, help='Maximum items to scrape')
    parser.add_argument('--job-id', required=True, help='Job ID from database')
    
    args = parser.parse_args()
    
    fields = args.fields.split(',')
    
    scraper = IndiaMartScraper(
        query=args.query,
        fields=fields,
        max_items=args.max_items,
        job_id=args.job_id
    )
    
    return scraper.run()


if __name__ == '__main__':
    sys.exit(main())