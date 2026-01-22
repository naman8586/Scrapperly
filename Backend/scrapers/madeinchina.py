#!/usr/bin/env python3
"""
MadeinChina Scraper - Integrated with Node.js Backend
Modified to work with the backend scraper executor
"""

import time
import json
import os
import sys
import pickle
import logging
import argparse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('madeinchina_scraper.log'),
    ]
)

# Supported fields
SUPPORTED_FIELDS = [
    'url', 'title', 'currency', 'exact_price', 'min_order', 'supplier',
    'origin', 'feedback', 'specifications', 'images', 'videos',
    'website_name', 'discount_information', 'brand_name'
]

# Field mapping
FIELD_MAPPING = {
    'image_url': 'images',
    'video_url': 'videos'
}

class MadeinChinaScraper:
    def __init__(self, query, fields, max_items, job_id):
        self.query = query
        self.fields = self._map_fields(fields)
        self.max_items = max_items
        self.job_id = job_id
        self.scraped_count = 0
        self.browser = None
        self.session_id = f"madeinchina_{job_id}_{int(time.time())}"
        
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
        options = webdriver.FirefoxOptions()
        options.add_argument("--headless")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--log-level=3")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            self.browser = webdriver.Firefox(options=options)
            logging.info("Browser initialized successfully")
        except Exception as e:
            raise Exception(f"Error initializing Firefox browser: {str(e)}")
    
    def detect_captcha(self):
        """Detect CAPTCHA on the page"""
        try:
            page_source = self.browser.page_source
            if any(keyword in page_source.lower() for keyword in ['h-captcha', 'recaptcha', 'please verify']):
                return True
            soup = BeautifulSoup(page_source, 'html.parser')
            if soup.find('div', class_='captcha-container'):
                return True
            if 'captcha' in self.browser.current_url.lower():
                return True
            return False
        except Exception as e:
            logging.error(f"Error detecting CAPTCHA: {str(e)}")
            return False
    
    def filter_product_data(self, product_data):
        """Filter product data to include only desired fields"""
        filtered_data = {}
        for field in self.fields:
            if field in product_data:
                filtered_data[field] = product_data[field]
        return filtered_data
    
    def scrape_product_list_page(self, page_num):
        """Scrape a single search results page"""
        products = []
        
        try:
            search_url = f'https://www.made-in-china.com/multi-search/{self.query}/F1/{page_num}.html'
            self.browser.get(search_url)
            WebDriverWait(self.browser, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Check for CAPTCHA
            if self.detect_captcha():
                self.send_error("CAPTCHA detected - manual intervention required")
                return products
            
            # Find product container
            product_cards_container = None
            selectors = [
                '.sr-srpList',
                '.prod-list',
                '.search-result-list',
                'div[data-component="ProductList"]'
            ]
            
            for selector in selectors:
                try:
                    product_cards_container = self.browser.find_element(By.CSS_SELECTOR, selector)
                    logging.info(f"Found product container with selector: {selector}")
                    break
                except NoSuchElementException:
                    continue
            
            if not product_cards_container:
                logging.warning(f"No product container found on page {page_num}")
                return products
            
            # Parse product cards
            product_cards_html = BeautifulSoup(
                product_cards_container.get_attribute("outerHTML"),
                "html.parser"
            )
            product_cards = product_cards_html.find_all(
                "div",
                {"class": ["sr-srpItem", "prod-info", "item"]}
            )
            
            if not product_cards:
                logging.warning(f"No product cards found on page {page_num}")
                return products
            
            for product in product_cards:
                if self.scraped_count >= self.max_items:
                    break
                    
                product_data = self.scrape_product_card(product)
                if product_data:
                    products.append(product_data)
            
            return products
            
        except Exception as e:
            logging.error(f"Error scraping page {page_num}: {str(e)}")
            return products
    
    def scrape_product_card(self, product):
        """Extract data from a product card"""
        product_json_data = {
            "url": "",
            "title": "",
            "currency": "",
            "exact_price": "",
            "min_order": "",
            "supplier": "",
            "origin": "",
            "feedback": {"rating": "", "star_count": ""},
            "specifications": {},
            "images": [],
            "videos": [],
            "website_name": "MadeinChina",
            "discount_information": "N/A",
            "brand_name": "N/A"
        }
        
        try:
            # Extract product URL
            if 'url' in self.fields:
                product_link = product.select_one('a[href*="made-in-china.com"]')
                if product_link:
                    product_url = product_link.get('href')
                    product_url = 'https:' + product_url if product_url.startswith('//') else product_url
                    product_json_data["url"] = product_url
            
            if not product_json_data["url"]:
                return None
            
            # Extract product title
            if 'title' in self.fields:
                title_elem = product.select_one('.product-name, .sr-srpItem-title, .title')
                if title_elem:
                    product_json_data["title"] = title_elem.get_text(strip=True)
            
            # Extract currency and price
            if 'currency' in self.fields or 'exact_price' in self.fields:
                price_elem = product.select_one('.price, .price-info, .sr-srpItem-price')
                if price_elem:
                    currency_price_text = price_elem.get_text(strip=True)
                    currency = ''.join([c for c in currency_price_text if not c.isdigit() and c not in ['.', '-', ' ']]).strip()
                    product_json_data["currency"] = currency
                    price_range = currency_price_text.replace(currency, '').strip()
                    product_json_data["exact_price"] = price_range
            
            # Extract minimum order
            if 'min_order' in self.fields:
                min_order_elem = product.find('div', string=lambda t: t and '(MOQ)' in t)
                if min_order_elem:
                    min_order_text = min_order_elem.get_text(strip=True)
                    product_json_data["min_order"] = min_order_text.replace('(MOQ)', '').strip()
            
            # Extract supplier
            if 'supplier' in self.fields:
                supplier_elem = product.select_one('.company-name, .supplier-name, .compnay-name span')
                if supplier_elem:
                    product_json_data["supplier"] = supplier_elem.get_text(strip=True)
            
            # Scrape product page details if needed
            if any(field in self.fields for field in ['origin', 'feedback', 'specifications', 'images', 'videos']):
                self.scrape_product_page_details(product_json_data)
            
            return self.filter_product_data(product_json_data)
            
        except Exception as e:
            logging.error(f"Error scraping product card: {str(e)}")
            return None
    
    def scrape_product_page_details(self, product_data):
        """Visit product page and extract detailed information"""
        try:
            self.browser.get(product_data["url"])
            WebDriverWait(self.browser, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            if self.detect_captcha():
                self.send_error("CAPTCHA detected on product page")
                return
            
            self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            product_page_html = BeautifulSoup(self.browser.page_source, "html.parser")
            
            # Extract origin
            if 'origin' in self.fields:
                try:
                    origin_elem = product_page_html.select_one('.basic-info-list .bsc-item .bac-item-value')
                    if origin_elem:
                        product_data["origin"] = origin_elem.get_text(strip=True)
                except Exception as e:
                    logging.error(f"Error extracting origin: {str(e)}")
            
            # Extract feedback
            if 'feedback' in self.fields:
                try:
                    rating_elem = self.browser.find_element(By.CSS_SELECTOR, "a.J-company-review .review-score")
                    product_data["feedback"]["rating"] = rating_elem.text if rating_elem else "No rating"
                    
                    star_elems = self.browser.find_elements(By.CSS_SELECTOR, "a.J-company-review .review-rate i")
                    product_data["feedback"]["star_count"] = str(len(star_elems))
                except Exception:
                    product_data["feedback"]["rating"] = "No rating"
                    product_data["feedback"]["star_count"] = "0"
            
            # Extract specifications
            if 'specifications' in self.fields:
                specs = {}
                try:
                    rows = self.browser.find_elements(By.XPATH, "//div[@class='basic-info-list']/div[@class='bsc-item cf']")
                    for row in rows:
                        try:
                            label_div = row.find_element(By.XPATH, ".//div[contains(@class,'bac-item-label')]")
                            value_div = row.find_element(By.XPATH, ".//div[contains(@class,'bac-item-value')]")
                            label = label_div.text.strip()
                            value = value_div.text.strip()
                            if label and value:
                                specs[label] = value
                        except Exception:
                            continue
                    product_data["specifications"] = specs
                except Exception as e:
                    logging.error(f"Error extracting specifications: {str(e)}")
            
            # Extract images and videos
            if 'images' in self.fields or 'videos' in self.fields:
                try:
                    swiper = product_page_html.find("div", {"class": ["sr-proMainInfo-slide-container", "product-media"]})
                    if swiper:
                        wrapper = swiper.find("div", {"class": "swiper-wrapper"})
                        if wrapper:
                            media_blocks = wrapper.find_all("div", {"class": ["sr-prMainInfo-slide-inner", "media-item"]})
                            for media in media_blocks:
                                if 'videos' in self.fields:
                                    videos = media.find_all("script", {"type": "text/data-video"})
                                    for vid in videos:
                                        try:
                                            video_data = json.loads(vid.get_text(strip=True))
                                            video_url = video_data.get("videoUrl")
                                            if video_url:
                                                product_data["videos"].append(video_url)
                                        except:
                                            continue
                                
                                if 'images' in self.fields:
                                    images = media.find_all("img")
                                    for img in images:
                                        src = img.get("src", "")
                                        if src.startswith("//"):
                                            src = "https:" + src
                                        if src:
                                            product_data["images"].append(src)
                except Exception as e:
                    logging.error(f"Error extracting media: {str(e)}")
                    
        except Exception as e:
            logging.error(f"Error scraping product page {product_data['url']}: {str(e)}")
    
    def scrape(self):
        """Main scraping logic"""
        try:
            self.init_browser()
            
            # Calculate how many pages we need to scrape
            items_per_page = 20  # Approximate
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
                
                # Small delay between pages
                time.sleep(2)
            
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
    parser = argparse.ArgumentParser(description='MadeinChina Scraper')
    parser.add_argument('--query', required=True, help='Search query')
    parser.add_argument('--fields', required=True, help='Comma-separated list of fields to scrape')
    parser.add_argument('--max-items', type=int, default=100, help='Maximum items to scrape')
    parser.add_argument('--job-id', required=True, help='Job ID from database')
    
    args = parser.parse_args()
    
    fields = args.fields.split(',')
    
    scraper = MadeinChinaScraper(
        query=args.query,
        fields=fields,
        max_items=args.max_items,
        job_id=args.job_id
    )
    
    return scraper.run()

if __name__ == '__main__':
    sys.exit(main())