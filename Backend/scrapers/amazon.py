#!/usr/bin/env python3
"""
Amazon Scraper - Integrated with Node.js Backend
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
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('amazon_scraper.log'),
    ]
)
logger = logging.getLogger(__name__)

# Supported fields
SUPPORTED_FIELDS = [
    'url', 'title', 'currency', 'exact_price', 'description', 'min_order',
    'supplier', 'feedback', 'image_url', 'images', 'videos', 'specifications',
    'website_name', 'discount_information', 'brand_name'
]

# Field mapping
FIELD_MAPPING = {
    'price': 'exact_price',
    'seller': 'supplier',
    'rating': 'feedback',
    'specs': 'specifications',
    'brand': 'brand_name'
}


class AmazonScraper:
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
            logger.info("Chrome browser initialized successfully")
        except Exception as e:
            raise Exception(f"Error initializing Chrome browser: {str(e)}")
    
    def clean_text(self, text):
        """Clean text by removing extra whitespace and special characters"""
        if not text:
            return ""
        cleaned = re.sub(r'[\u2000-\u200F\u2028-\u202F]+', '', text)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = re.sub(r'\[U\+[0-9A-Fa-f]+\]', '', cleaned)
        return cleaned.strip()
    
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
            "website_name": "Amazon",
            "discount_information": None,
            "brand_name": None
        }
        
        try:
            # URL
            if 'url' in self.fields:
                product_link = self.retry_extraction(
                    lambda: card.find("a", {"class": "a-link-normal s-line-clamp-2 s-link-style a-text-normal"})
                )
                if product_link and product_link.get("href"):
                    href = product_link["href"]
                    product["url"] = href if href.startswith("https://www.amazon") else f"https://www.amazon.in{href}"
                else:
                    return None
            
            if not product["url"]:
                return None
            
            # Title
            if 'title' in self.fields:
                title_elem = self.retry_extraction(
                    lambda: card.find("a", {"class": "a-link-normal s-line-clamp-2 s-link-style a-text-normal"})
                )
                if title_elem:
                    product["title"] = self.clean_text(title_elem.get_text(strip=True))
            
            # Currency
            if 'currency' in self.fields:
                currency_elem = self.retry_extraction(
                    lambda: card.find("span", {"class": "a-price-symbol"})
                )
                if currency_elem:
                    product["currency"] = self.clean_text(currency_elem.get_text(strip=True))
            
            # Price
            if 'exact_price' in self.fields:
                price_elem = self.retry_extraction(
                    lambda: card.find("span", {"class": "a-price-whole"})
                )
                if price_elem:
                    product["exact_price"] = self.clean_text(price_elem.get_text(strip=True)).replace(",", "")
            
            return product
            
        except Exception as e:
            logger.error(f"Error extracting product card {index}: {str(e)}")
            return None
    
    def scrape_product_page_details(self, product):
        """Visit product page and extract detailed information"""
        try:
            logger.info(f"Navigating to product page: {product['url']}")
            self.browser.get(product["url"])
            WebDriverWait(self.browser, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            product_page_html = BeautifulSoup(self.browser.page_source, "html.parser")
            
            # Description
            if 'description' in self.fields:
                description_elements = self.retry_extraction(
                    lambda: product_page_html.find("div", {"id": "feature-bullets"}).find_all("li", {"class": "a-spacing-mini"}),
                    default=[]
                )
                if description_elements:
                    description = " ".join([self.clean_text(elem.get_text(strip=True)) for elem in description_elements])
                    product["description"] = description[:500]  # Limit length
            
            # Discount information
            if 'discount_information' in self.fields:
                discount_elem = self.retry_extraction(
                    lambda: product_page_html.select_one("span.savingsPercentage")
                )
                if discount_elem:
                    product["discount_information"] = self.clean_text(discount_elem.get_text(strip=True))
                else:
                    # Calculate from MRP
                    mrp_elem = self.retry_extraction(
                        lambda: product_page_html.select_one("span.a-price.a-text-price span.a-offscreen")
                    )
                    if mrp_elem and product["exact_price"]:
                        mrp_text = self.clean_text(mrp_elem.get_text(strip=True))
                        mrp_value = re.sub(r'[^\d.]', '', mrp_text)
                        current_price = re.sub(r'[^\d.]', '', product["exact_price"])
                        if mrp_value and current_price:
                            try:
                                mrp_value = float(mrp_value)
                                current_price = float(current_price)
                                if mrp_value > current_price:
                                    discount = ((mrp_value - current_price) / mrp_value) * 100
                                    product["discount_information"] = f"{discount:.2f}% off"
                            except ValueError:
                                pass
            
            # Specifications
            if 'specifications' in self.fields:
                specs = {}
                # Try bullet list
                detail_lists = product_page_html.select("ul.detail-bullet-list > li")
                for li in detail_lists:
                    label_tag = li.select_one("span.a-text-bold")
                    value_tag = label_tag.find_next_sibling("span") if label_tag else None
                    if label_tag and value_tag:
                        label = self.clean_text(label_tag.get_text(strip=True).replace(":", ""))
                        value = self.clean_text(value_tag.get_text(" ", strip=True))
                        if label and value:
                            specs[label] = value
                
                # Try table format
                if not specs:
                    details_table = product_page_html.select_one("table#productDetails_detailBullets_sections1")
                    if details_table:
                        for row in details_table.find_all("tr"):
                            label = row.find("th", {"class": "a-color-secondary a-size-base prodDetSectionEntry"})
                            value = row.find("td", {"class": "a-size-base prodDetAttrValue"})
                            if label and value:
                                label_text = self.clean_text(label.get_text(strip=True).replace(":", ""))
                                value_text = self.clean_text(value.get_text(" ", strip=True))
                                if label_text and value_text:
                                    specs[label_text] = value_text
                
                product["specifications"] = specs
            
            # Feedback (reviews count)
            if 'feedback' in self.fields:
                review_elem = self.retry_extraction(
                    lambda: product_page_html.find("span", {"id": "acrCustomerReviewText"})
                )
                if review_elem:
                    review_text = self.clean_text(review_elem.get_text(strip=True))
                    numeric_match = re.search(r"(\d+)", review_text)
                    if numeric_match:
                        product["feedback"]["review"] = numeric_match.group(1)
                
                # Rating
                rating_elem = self.retry_extraction(
                    lambda: product_page_html.find(
                        lambda tag: tag.name == "span" and tag.get("id") == "acrPopover"
                    )
                )
                if rating_elem:
                    rating_span = rating_elem.find("span", {"class": "a-size-base a-color-base"})
                    if rating_span:
                        product["feedback"]["rating"] = self.clean_text(rating_span.get_text(strip=True))
            
            # Supplier
            if 'supplier' in self.fields:
                supplier_elem = product_page_html.find("a", {"id": "sellerProfileTriggerId"})
                if not supplier_elem:
                    supplier_elem = product_page_html.find("span", {"class": "tabular-buybox-text"})
                if supplier_elem:
                    product["supplier"] = self.clean_text(supplier_elem.get_text(strip=True))
            
            # Images
            if 'image_url' in self.fields or 'images' in self.fields:
                try:
                    altImages = WebDriverWait(self.browser, 5).until(
                        EC.presence_of_element_located((By.ID, "altImages"))
                    )
                    imgButtons = altImages.find_elements(By.CSS_SELECTOR, "li.imageThumbnail")
                    image_urls = set()
                    for imgButton in imgButtons[:5]:  # Limit to first 5 images
                        try:
                            WebDriverWait(self.browser, 2).until(EC.element_to_be_clickable(imgButton))
                            imgButton.click()
                            time.sleep(0.5)
                            product_image = self.browser.find_element(By.CSS_SELECTOR, "img.a-dynamic-image")
                            image_url = product_image.get_attribute('src')
                            if image_url:
                                image_urls.add(image_url)
                        except:
                            continue
                    
                    product["images"] = list(image_urls)
                    if product["images"] and 'image_url' in self.fields:
                        product["image_url"] = product["images"][0]
                except Exception as e:
                    logger.error(f"Error extracting images: {str(e)}")
            
            # Brand name
            if 'brand_name' in self.fields:
                brand_elem = product_page_html.find("a", {"id": "bylineInfo"})
                if brand_elem:
                    product["brand_name"] = self.clean_text(brand_elem.get_text(strip=True))
            
        except Exception as e:
            logger.error(f"Error scraping product page {product['url']}: {str(e)}")
    
    def scrape_product_list_page(self, page_num):
        """Scrape a single search results page"""
        products = []
        
        try:
            search_url = f"https://www.amazon.in/s?k={self.query.replace(' ', '+')}&page={page_num}"
            logger.info(f"Scraping page {page_num}: {search_url}")
            
            self.browser.get(search_url)
            WebDriverWait(self.browser, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Find product container
            try:
                product_cards_container = self.browser.find_element(By.XPATH, '//span[@data-component-type="s-search-results"]')
            except Exception:
                logger.warning(f"No product container found on page {page_num}")
                return products
            
            product_cards_html = BeautifulSoup(product_cards_container.get_attribute("outerHTML"), "html.parser")
            product_cards = product_cards_html.find_all("div", {"role": "listitem"})
            
            if not product_cards:
                logger.warning(f"No product cards found on page {page_num}")
                return products
            
            logger.info(f"Found {len(product_cards)} products on page {page_num}")
            
            for index, card in enumerate(product_cards):
                if self.scraped_count >= self.max_items:
                    break
                
                product = self.extract_product_card(card, index)
                if not product:
                    continue
                
                # Visit product page if detailed fields needed
                if any(field in self.fields for field in [
                    'description', 'supplier', 'feedback', 'image_url', 'images',
                    'specifications', 'discount_information', 'brand_name'
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
            items_per_page = 16  # Amazon shows ~16 items per page
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
    parser = argparse.ArgumentParser(description='Amazon Scraper')
    parser.add_argument('--query', required=True, help='Search query')
    parser.add_argument('--fields', required=True, help='Comma-separated list of fields to scrape')
    parser.add_argument('--max-items', type=int, default=100, help='Maximum items to scrape')
    parser.add_argument('--job-id', required=True, help='Job ID from database')
    
    args = parser.parse_args()
    
    fields = args.fields.split(',')
    
    scraper = AmazonScraper(
        query=args.query,
        fields=fields,
        max_items=args.max_items,
        job_id=args.job_id
    )
    
    return scraper.run()


if __name__ == '__main__':
    sys.exit(main())