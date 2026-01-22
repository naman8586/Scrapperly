#!/usr/bin/env python3
"""
DHgate Scraper - Integrated with Node.js Backend
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dhgate_scraper.log'),
    ]
)
logger = logging.getLogger(__name__)

# Supported fields
SUPPORTED_FIELDS = [
    'url', 'title', 'currency', 'exact_price', 'min_order', 'supplier',
    'origin', 'feedback', 'specifications', 'images', 'videos',
    'website_name', 'discount_information', 'brand_name'
]

# Field mapping
FIELD_MAPPING = {
    'price': 'exact_price',
    'moq': 'min_order',
    'seller': 'supplier',
    'location': 'origin',
    'rating': 'feedback'
}


class DHgateScraper:
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
        """Initialize Selenium browser (try Firefox first, fallback to Chrome)"""
        # Try Firefox first
        firefox_options = webdriver.FirefoxOptions()
        firefox_options.add_argument("--headless")
        firefox_options.add_argument("--ignore-certificate-errors")
        firefox_options.add_argument("--log-level=3")
        firefox_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        try:
            self.browser = webdriver.Firefox(
                service=webdriver.firefox.service.Service(GeckoDriverManager().install()),
                options=firefox_options
            )
            self.browser.set_page_load_timeout(30)
            self.browser.maximize_window()
            logger.info("Firefox browser initialized successfully")
            return
        except WebDriverException:
            logger.warning("Firefox init failed, trying Chrome...")
        
        # Fallback to Chrome
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        try:
            self.browser = webdriver.Chrome(
                service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            self.browser.set_page_load_timeout(30)
            self.browser.maximize_window()
            logger.info("Chrome browser initialized successfully")
        except WebDriverException as e:
            raise Exception(f"Error initializing browser (Firefox and Chrome failed): {str(e)}")
    
    def clean_text(self, text):
        """Clean text by removing extra whitespace"""
        return ' '.join(text.strip().split()) if text else None
    
    def parse_price(self, price_text):
        """Parse price from text"""
        if not price_text:
            return {'currency': None, 'exact_price': None}
        
        currency = next((s for s in ["$", "€", "£", "¥", "USD", "EUR", "GBP", "CNY"] if s in price_text), None)
        if not currency and "usd" in price_text.lower():
            currency = "USD"
        
        clean_text = re.sub(r'[^\d.,]', '', price_text)
        range_match = re.search(r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*-\s*(\d+(?:,\d{3})*(?:\.\d+)?)', clean_text)
        if range_match:
            return {
                'currency': currency,
                'exact_price': range_match.group(1).replace(',', '')
            }
        
        single_match = re.search(r'(\d+(?:,\d{3})*(?:\.\d+)?)', clean_text)
        if single_match:
            return {
                'currency': currency,
                'exact_price': single_match.group(1).replace(',', '')
            }
        
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
    
    def extract_product_card(self, card, index):
        """Extract data from a product card on search page"""
        product = {
            "url": None,
            "title": None,
            "currency": None,
            "exact_price": None,
            "min_order": "1 unit",
            "supplier": None,
            "origin": None,
            "feedback": {"rating": None, "review": None},
            "specifications": {},
            "images": [],
            "videos": [],
            "website_name": "DHgate",
            "discount_information": None,
            "brand_name": None
        }
        
        try:
            soup = BeautifulSoup(card.get_attribute('outerHTML'), 'html.parser')
            
            # Title and URL
            title_selectors = [
                'div.gallery-pro-name a',
                'a.title',
                'div.item-title a',
                'a[href*="/product/"]'
            ]
            title_el = None
            for selector in title_selectors:
                title_el = soup.select_one(selector)
                if title_el:
                    break
            
            if title_el:
                if 'title' in self.fields:
                    product['title'] = self.retry_extraction(
                        lambda: self.clean_text(title_el.get('title') or title_el.get_text(strip=True))
                    )
                if 'url' in self.fields:
                    href = title_el.get('href', '')
                    product['url'] = href if href.startswith('http') else f"https://www.dhgate.com{href}"
            
            if not product['url']:
                return None
            
            # Price
            if 'currency' in self.fields or 'exact_price' in self.fields:
                price_selectors = [
                    '.gallery-pro-price',
                    '[class*="price"]',
                    'span.price',
                    'div.item-price'
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
            
            # Discount
            if 'discount_information' in self.fields:
                discount_selectors = ['.discount', '.promo-info', 'span[class*="discount"]']
                discount_el = None
                for selector in discount_selectors:
                    discount_el = soup.select_one(selector)
                    if discount_el:
                        break
                product['discount_information'] = self.retry_extraction(
                    lambda: self.clean_text(discount_el.get_text(strip=True)),
                    default=None
                )
            
            return product
            
        except Exception as e:
            logger.error(f"Error extracting product card {index}: {str(e)}")
            return None
    
    def scrape_product_page_details(self, product):
        """Visit product page and extract detailed information"""
        try:
            logger.info(f"Navigating to product page: {product['url']}")
            self.browser.get(product['url'])
            WebDriverWait(self.browser, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.product-info, .product-detail, div.prodSpecifications_showLayer'))
            )
            
            page_soup = BeautifulSoup(self.browser.page_source, 'html.parser')
            
            # Min Order
            if 'min_order' in self.fields:
                moq_selectors = ['span.moq', 'div.moq', '[class*="min-order"]']
                moq_el = None
                for selector in moq_selectors:
                    moq_el = page_soup.select_one(selector)
                    if moq_el:
                        break
                product['min_order'] = self.retry_extraction(
                    lambda: self.clean_text(moq_el.get_text(strip=True)),
                    default="1 unit"
                )
            
            # Supplier
            if 'supplier' in self.fields:
                supplier_selectors = [
                    'a.store-name',
                    'a[href*="/store/"]',
                    'div.seller-info a',
                    'span.seller-name'
                ]
                supplier_el = None
                for selector in supplier_selectors:
                    supplier_el = page_soup.select_one(selector)
                    if supplier_el:
                        break
                product['supplier'] = self.retry_extraction(
                    lambda: self.clean_text(supplier_el.get_text(strip=True)),
                    default=None
                )
            
            # Origin
            if 'origin' in self.fields:
                specs_container = page_soup.find('div', class_=re.compile(r'prodSpecifications_showLayer'))
                if specs_container:
                    for li in specs_container.select('ul li'):
                        key_text = self.retry_extraction(
                            lambda: self.clean_text(li.find('span').get_text(strip=True) if li.find('span') else ''),
                            default=''
                        )
                        if key_text and 'origin' in key_text.lower():
                            value_div = li.find('div', class_=re.compile(r'prodSpecifications_deswrap'))
                            product['origin'] = self.retry_extraction(
                                lambda: self.clean_text(value_div.get_text(strip=True)),
                                default=None
                            )
                            break
            
            # Feedback
            if 'feedback' in self.fields:
                review_selectors = ['span[class*="reviewsCount"]', 'span.review-count']
                review_el = None
                for selector in review_selectors:
                    review_el = page_soup.select_one(selector)
                    if review_el:
                        break
                if review_el:
                    review_text = self.retry_extraction(lambda: review_el.get_text(strip=True))
                    review_match = re.search(r'\d+', review_text)
                    product['feedback']['review'] = review_match.group(0) if review_match else None
                
                rating_selectors = ['div[class*="starWarp"]', 'span.star-rating']
                rating_el = None
                for selector in rating_selectors:
                    rating_el = page_soup.select_one(selector)
                    if rating_el:
                        break
                if rating_el:
                    rating_text = self.retry_extraction(lambda: rating_el.get_text(strip=True))
                    if re.match(r'^\d+\.\d+', rating_text):
                        product['feedback']['rating'] = rating_text
            
            # Specifications
            if 'specifications' in self.fields:
                specs = {}
                specs_container = page_soup.find('div', class_=re.compile(r'prodSpecifications_showLayer'))
                if specs_container:
                    for li in specs_container.select('ul li'):
                        key_span = li.find('span')
                        value_div = li.find('div', class_=re.compile(r'prodSpecifications_deswrap'))
                        if key_span and value_div:
                            key = self.retry_extraction(
                                lambda: self.clean_text(key_span.get_text(strip=True).replace(':', '')),
                                default=None
                            )
                            value = self.retry_extraction(
                                lambda: self.clean_text(value_div.get_text(strip=True)),
                                default=None
                            )
                            if key and value:
                                specs[key] = value
                product['specifications'] = specs
            
            # Images
            if 'images' in self.fields:
                img_selectors = [
                    'ul[class*="smallMapList"] img',
                    '.product-image img',
                    'div.image-gallery img'
                ]
                img_els = []
                for selector in img_selectors:
                    img_els = page_soup.select(selector)
                    if img_els:
                        break
                product['images'] = [
                    self.retry_extraction(
                        lambda: (img.get('data-zoom-image') or img.get('src', '')).replace('100x100', ''),
                        default=''
                    )
                    for img in img_els
                    if '100x100' not in (img.get('data-zoom-image') or img.get('src', ''))
                ]
                product['images'] = [
                    img if img.startswith('http') else f"https:{img}"
                    for img in product['images']
                    if img
                ]
            
            # Videos
            if 'videos' in self.fields:
                video_els = page_soup.select('video source, [class*="video"] source')
                product['videos'] = [
                    video.get('src', '')
                    for video in video_els
                    if video.get('src')
                ]
            
            # Brand Name
            if 'brand_name' in self.fields:
                brand_name = next(
                    (value for key, value in product['specifications'].items()
                     if key.lower() in ['brand', 'product brand']),
                    None
                )
                if not brand_name and product['title']:
                    title_lower = product['title'].lower()
                    brands = ["dior", "nike", "adidas", "rolex", "gucci", "prada"]
                    for brand in brands:
                        if re.search(r'\b' + brand + r'\b', title_lower):
                            brand_name = brand.capitalize()
                            break
                product['brand_name'] = brand_name
            
        except (TimeoutException, NoSuchElementException) as e:
            logger.warning(f"Error loading product page {product['url']}: {str(e)}")
    
    def scrape_product_list_page(self, page_num):
        """Scrape a single search results page"""
        products = []
        
        try:
            url = f"https://www.dhgate.com/wholesale/search.do?act=search&searchkey={quote(self.query)}&pageNo={page_num}"
            logger.info(f"Scraping page {page_num}: {url}")
            
            self.browser.get(url)
            WebDriverWait(self.browser, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.gallery-pro, .item-box, .product-item'))
            )
            
            # Scroll to load content
            self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Find product cards
            product_cards_selectors = [
                '.gallery-pro',
                '.item-box',
                '.product-item',
                'div[class*="product-list"] > div'
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
            
            for index, card in enumerate(product_cards):
                if self.scraped_count >= self.max_items:
                    break
                
                product = self.extract_product_card(card, index)
                if not product:
                    continue
                
                # Visit product page if detailed fields needed
                if any(field in self.fields for field in [
                    'min_order', 'supplier', 'origin', 'feedback', 'specifications', 'images', 'videos', 'brand_name'
                ]):
                    self.scrape_product_page_details(product)
                
                products.append(self.filter_product_data(product))
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
            items_per_page = 48  # DHgate typically shows ~48 items per page
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
    parser = argparse.ArgumentParser(description='DHgate Scraper')
    parser.add_argument('--query', required=True, help='Search query')
    parser.add_argument('--fields', required=True, help='Comma-separated list of fields to scrape')
    parser.add_argument('--max-items', type=int, default=100, help='Maximum items to scrape')
    parser.add_argument('--job-id', required=True, help='Job ID from database')
    
    args = parser.parse_args()
    
    fields = args.fields.split(',')
    
    scraper = DHgateScraper(
        query=args.query,
        fields=fields,
        max_items=args.max_items,
        job_id=args.job_id
    )
    
    return scraper.run()


if __name__ == '__main__':
    sys.exit(main())