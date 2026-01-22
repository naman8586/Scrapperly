#!/usr/bin/env python3
"""
Flipkart Scraper - Integrated with Node.js Backend
Modified to work with the backend scraper executor
"""

import re
import time
import json
import sys
import logging
import argparse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('flipkart_scraper.log'),
    ]
)
logger = logging.getLogger(__name__)

# Supported fields
SUPPORTED_FIELDS = [
    'url', 'title', 'currency', 'exact_price', 'description', 'min_order',
    'supplier', 'feedback', 'image_url', 'images', 'videos', 'specifications',
    'website_name', 'discount_information'
]

# Field mapping
FIELD_MAPPING = {
    'price': 'exact_price',
    'seller': 'supplier',
    'rating': 'feedback',
    'specs': 'specifications'
}


class FlipkartScraper:
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
            "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
        )
        
        try:
            self.browser = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
            self.browser.maximize_window()
            logger.info("Chrome browser initialized successfully")
        except WebDriverException as e:
            raise Exception(f"Error initializing Chrome browser: {str(e)}")
    
    def detect_captcha(self):
        """Detect CAPTCHA on the page"""
        try:
            page_source = self.browser.page_source.lower()
            captcha_indicators = ['captcha', 'verify you are not a robot', 'recaptcha', 'please verify']
            if any(indicator in page_source for indicator in captcha_indicators):
                return True
            soup = BeautifulSoup(page_source, 'html.parser')
            if soup.find('div', class_='g-recaptcha') or soup.find('form', id='challenge-form'):
                return True
            if 'captcha' in self.browser.current_url.lower():
                return True
            return False
        except Exception as e:
            logger.error(f"Error detecting CAPTCHA: {str(e)}")
            return False
    
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
            "description": None,
            "min_order": "1 unit",
            "supplier": None,
            "feedback": {"rating": None, "review": None},
            "image_url": None,
            "images": [],
            "videos": [],
            "specifications": {},
            "website_name": "Flipkart",
            "discount_information": None
        }
        
        try:
            # URL
            if 'url' in self.fields:
                try:
                    url_tag = card.find_element(By.CSS_SELECTOR, "a[href*='flipkart.com']")
                    product["url"] = url_tag.get_attribute("href")
                except Exception as e:
                    logger.error(f"Error extracting URL: {str(e)}")
                    return None
            
            if not product["url"]:
                return None
            
            # Title
            if 'title' in self.fields:
                product["title"] = self.retry_extraction(
                    lambda: card.find_element(By.CSS_SELECTOR, "div._4rR01T, div.KzDlHZ, a.wjcEIp").text.strip()
                )
            
            # Price and currency
            if 'currency' in self.fields or 'exact_price' in self.fields:
                price_text = self.retry_extraction(
                    lambda: card.find_element(By.CSS_SELECTOR, "div._30jeq3, div.Nx9bqj").text.strip()
                )
                if price_text:
                    match = re.match(r'([^0-9]+)([0-9,]+)', price_text)
                    if match:
                        product["currency"] = match.group(1).strip()
                        product["exact_price"] = match.group(2).replace(",", "")
            
            # Primary image
            if 'image_url' in self.fields:
                product["image_url"] = self.retry_extraction(
                    lambda: card.find_element(By.CSS_SELECTOR, "img._396cs4, img.DByuf4").get_attribute("src")
                )
            
            return product
            
        except Exception as e:
            logger.error(f"Error extracting product card {index}: {str(e)}")
            return None
    
    def scrape_product_page_details(self, product):
        """Visit product page and extract detailed information"""
        try:
            logger.info(f"Navigating to product page: {product['url']}")
            self.browser.get(product["url"])
            WebDriverWait(self.browser, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Check for CAPTCHA
            if self.detect_captcha():
                self.send_error("CAPTCHA detected on product page")
                return
            
            product_page_html = BeautifulSoup(self.browser.page_source, "html.parser")
            
            # Description
            if 'description' in self.fields:
                product["description"] = self.retry_extraction(
                    lambda: product_page_html.select_one("div._1mXcCf, div.yN_+oW p").get_text(strip=True)[:500]
                )
            
            # Supplier (seller)
            if 'supplier' in self.fields:
                product["supplier"] = self.retry_extraction(
                    lambda: self.browser.find_element(By.CSS_SELECTOR, "div._2VRS5M, div.cvCpHS").text.strip()
                )
            
            # Feedback (rating and reviews)
            if 'feedback' in self.fields:
                product["feedback"]["rating"] = self.retry_extraction(
                    lambda: self.browser.find_element(By.CSS_SELECTOR, "div._3LWZlK, div.XQDdHH").text.strip()
                )
                product["feedback"]["review"] = self.retry_extraction(
                    lambda: self.browser.find_element(By.CSS_SELECTOR, "span._2_R_DZ, span.Wphh3N").text.strip()
                )
            
            # Discount
            if 'discount_information' in self.fields:
                product["discount_information"] = self.retry_extraction(
                    lambda: self.browser.find_element(By.CSS_SELECTOR, "div._3Ay6Sb, div.UkUFwK").text.strip()
                )
            
            # Images
            if 'images' in self.fields:
                try:
                    images = product_page_html.select("div._2r_T1I img, div.qOPjUY img")
                    for img in images:
                        src = img.get("src", "")
                        if src and src not in product["images"]:
                            product["images"].append(src)
                    if product["images"] and 'image_url' in self.fields:
                        product["image_url"] = product["images"][0]
                except Exception as e:
                    logger.error(f"Error extracting images: {str(e)}")
            
            # Specifications
            if 'specifications' in self.fields:
                try:
                    # Click "Product Details" if present
                    try:
                        product_details = WebDriverWait(self.browser, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Product Details')]"))
                        )
                        self.browser.execute_script("arguments[0].scrollIntoView(true);", product_details)
                        self.browser.execute_script("arguments[0].click();", product_details)
                        time.sleep(1)
                    except TimeoutException:
                        pass
                    
                    # Extract specifications
                    table = WebDriverWait(self.browser, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div._1UhVsV, div.GNDEQ-"))
                    )
                    soup = BeautifulSoup(table.get_attribute("innerHTML"), "html.parser")
                    rows = soup.select("div.WJdYP6, li._7eSDEz")
                    product["specifications"] = {}
                    for row in rows:
                        try:
                            label = row.select_one("div.col-3-12, td._0vPCLL").get_text(strip=True)
                            value = row.select_one("div.col-9-12, td.BGjvC- li").get_text(strip=True)
                            if label and value:
                                product["specifications"][label] = value
                        except Exception:
                            continue
                except Exception as e:
                    logger.error(f"Error extracting specifications: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error scraping product page {product['url']}: {str(e)}")
    
    def scrape_product_list_page(self, page_num):
        """Scrape a single search results page"""
        products = []
        
        try:
            search_url = f"https://www.flipkart.com/search?q={self.query.replace(' ', '+')}&page={page_num}"
            logger.info(f"Scraping page {page_num}: {search_url}")
            
            self.browser.get(search_url)
            WebDriverWait(self.browser, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Check for CAPTCHA
            if self.detect_captcha():
                self.send_error("CAPTCHA detected on search page")
                return products
            
            # Scroll to load content
            self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Find product cards
            product_cards_selectors = [
                'div._2kHMtA',
                'div.tUxRFH',
                'div._1AtVbE',
                'div[data-id]'
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
                    'description', 'supplier', 'feedback', 'images', 'specifications', 'discount_information'
                ]):
                    self.scrape_product_page_details(product)
                
                products.append(self.filter_product_data(product))
            
            return products
            
        except Exception as e:
            logger.error(f"Error scraping page {page_num}: {str(e)}")
            return products
    
    def scrape(self):
        """Main scraping logic"""
        try:
            self.init_browser()
            
            # Calculate pages needed
            items_per_page = 24  # Flipkart shows ~24 items per page
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
                time.sleep(2)
            
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
    parser = argparse.ArgumentParser(description='Flipkart Scraper')
    parser.add_argument('--query', required=True, help='Search query')
    parser.add_argument('--fields', required=True, help='Comma-separated list of fields to scrape')
    parser.add_argument('--max-items', type=int, default=100, help='Maximum items to scrape')
    parser.add_argument('--job-id', required=True, help='Job ID from database')
    
    args = parser.parse_args()
    
    fields = args.fields.split(',')
    
    scraper = FlipkartScraper(
        query=args.query,
        fields=fields,
        max_items=args.max_items,
        job_id=args.job_id
    )
    
    return scraper.run()


if __name__ == '__main__':
    sys.exit(main())