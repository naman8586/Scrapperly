import time
import json
import os
import sys
import pickle
import logging
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# Configure logging to a file for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('madeinchina_scraper.log'),
    ]
)

# Supported fields for user selection
SUPPORTED_FIELDS = [
    'url', 'title', 'currency', 'exact_price', 'min_order', 'supplier',
    'origin', 'feedback', 'specifications', 'images', 'videos',
    'website_name', 'discount_information', 'brand_name'
]

# Map frontend field names to backend field names
FIELD_MAPPING = {
    'image_url': 'images',
    'video_url': 'videos'
}

# Get command-line arguments
if len(sys.argv) < 5 and sys.argv[1] != "--validate-captcha":
    print(json.dumps({
        "status": "error",
        "message": "Usage: python madeinchina.py <search_keyword> <page_count> <retries> <fields>"
    }))
    sys.exit(1)

# Parse arguments
if sys.argv[1] == "--validate-captcha":
    captcha_input = sys.argv[2]
    session_id = sys.argv[3]
else:
    search_keyword = sys.argv[1]
    try:
        search_page = int(sys.argv[2])
        retries = int(sys.argv[3])
    except ValueError:
        print(json.dumps({
            "status": "error",
            "message": "Error: page_count and retries must be integers"
        }))
        sys.exit(1)
    
    # Parse fields (comma-separated)
    input_fields = sys.argv[4].split(',')
    
    # Map frontend field names to backend field names
    mapped_fields = []
    for field in input_fields:
        field = field.strip()
        mapped_field = FIELD_MAPPING.get(field, field)
        mapped_fields.append(mapped_field)
    
    # Always include 'url' and 'website_name' for context and deduplication
    desired_fields = list(set(['url', 'website_name'] + mapped_fields))
    
    # Validate fields
    invalid_fields = [f for f in mapped_fields if f not in SUPPORTED_FIELDS]
    if invalid_fields:
        print(json.dumps({
            "status": "error",
            "message": f"Error: Invalid fields: {', '.join(invalid_fields)}. Supported fields: {', '.join(SUPPORTED_FIELDS)}"
        }))
        sys.exit(1)
        
    # Setup output file
    output_file = f"products_{search_keyword}_madeinchina.json"

# Setup Selenium configurations
options = webdriver.FirefoxOptions()
options.add_argument("--headless")
options.add_argument("--ignore-certificate-errors")
options.add_argument("--log-level=3")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

try:
    browser = webdriver.Firefox(options=options)
except Exception as e:
    print(json.dumps({
        "status": "error",
        "message": f"Error initializing Firefox browser: {str(e)}"
    }))
    sys.exit(1)

def save_session(session_id, url, cookies):
    """Save browser session (cookies and URL) to resume after CAPTCHA."""
    session_data = {'url': url, 'cookies': cookies}
    session_file = f"session_{session_id}.pkl"
    with open(session_file, 'wb') as f:
        pickle.dump(session_data, f)
    logging.info(f"Saved session {session_id}")

def load_session(session_id):
    """Load browser session for resuming scraping."""
    session_file = f"session_{session_id}.pkl"
    if os.path.exists(session_file):
        with open(session_file, 'rb') as f:
            return pickle.load(f)
    return None

def detect_captcha():
    """Detect CAPTCHA by checking for common CAPTCHA elements or redirects."""
    try:
        page_source = browser.page_source
        if any(keyword in page_source.lower() for keyword in ['h-captcha', 'recaptcha', 'please verify you are not a robot']):
            return True
        soup = BeautifulSoup(page_source, 'html.parser')
        captcha_div = soup.find('div', class_='captcha-container')
        if captcha_div:
            return True
        if 'captcha' in browser.current_url.lower():
            return True
        return False
    except Exception as e:
        logging.error(f"Error detecting CAPTCHA: {str(e)}")
        return False

def get_captcha_details():
    """Extract CAPTCHA details (type, URL, or HTML)."""
    try:
        page_source = browser.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        captcha_img = soup.find('img', class_='captcha-image')
        captcha_url = captcha_img['src'] if captcha_img and 'src' in captcha_img.attrs else None
        captcha_type = 'image' if captcha_url else 'interactive'
        
        return {
            'type': captcha_type,
            'url': captcha_url or browser.current_url,
            'html': None
        }
    except Exception as e:
        logging.error(f"Error extracting CAPTCHA details: {str(e)}")
        return {'type': 'image', 'url': 'https://example.com/captcha.jpg', 'html': None}

def validate_captcha(captcha_input, session_id):
    """Validate CAPTCHA input."""
    try:
        session_data = load_session(session_id)
        if not session_data:
            captcha_result = {
                "valid": False,
                "message": f"Session {session_id} not found"
            }
            print(json.dumps(captcha_result))
            return False
        
        browser.get(session_data['url'])
        for cookie in session_data['cookies']:
            browser.add_cookie(cookie)
        
        # For demonstration/testing purposes
        if captcha_input == "mock123":
            captcha_result = {
                "valid": True,
                "message": "CAPTCHA validated successfully"
            }
            print(json.dumps(captcha_result))
            save_session(session_id, browser.current_url, browser.get_cookies())
            return True
        else:
            captcha_result = {
                "valid": False,
                "message": "Invalid CAPTCHA input"
            }
            print(json.dumps(captcha_result))
            return False
    except Exception as e:
        captcha_result = {
            "valid": False,
            "message": f"Error validating CAPTCHA: {str(e)}"
        }
        print(json.dumps(captcha_result))
        return False

def retry_extraction(func, attempts=3, delay=1, default=""):
    """Retry a function with specified attempts and delay."""
    for i in range(attempts):
        try:
            result = func()
            if result:
                return result
        except Exception as e:
            logging.warning(f"Retry {i+1}/{attempts} failed: {str(e)}")
            time.sleep(delay)
    return default

def filter_product_data(product_data, desired_fields):
    """Filter product data to include only desired fields."""
    filtered_data = {}
    for field in desired_fields:
        if field in product_data:
            filtered_data[field] = product_data[field]
    return filtered_data

def scrape_madeinchina_products():
    # Handle validate-captcha mode
    if sys.argv[1] == "--validate-captcha":
        validate_captcha(sys.argv[2], sys.argv[3])
        sys.exit(0)

    scraped_products = {}
    session_id = f"madeinchina_{int(time.time())}"
    messages = []  # Collect messages for final output
    
    try:
        for page in range(1, search_page + 1):
            for attempt in range(retries):
                try:
                    # Simplified search URL, removing potentially unnecessary parameters
                    search_url = f'https://www.made-in-china.com/multi-search/{search_keyword}/F1/{page}.html'
                    browser.get(search_url)
                    WebDriverWait(browser, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
                    
                    # Check for CAPTCHA
                    if detect_captcha():
                        captcha_details = get_captcha_details()
                        save_session(session_id, browser.current_url, browser.get_cookies())
                        print(json.dumps({
                            "status": "captcha_required",
                            "captcha": captcha_details,
                            "sessionId": session_id
                        }))
                        sys.exit(0)

                    # Try multiple selectors to find product list
                    product_cards_container = None
                    selectors = [
                        '.sr-srpList',  # Common class for search result list
                        '.prod-list',   # Original selector
                        '.search-result-list',  # Alternative
                        'div[data-component="ProductList"]'  # Data attribute selector
                    ]
                    for selector in selectors:
                        try:
                            product_cards_container = browser.find_element(By.CSS_SELECTOR, selector)
                            logging.info(f"Found product container with selector: {selector}")
                            break
                        except NoSuchElementException:
                            continue

                    if not product_cards_container:
                        message = f"No product container found on page {page}"
                        logging.warning(message)
                        messages.append(message)
                        break

                    # Parse product cards
                    product_cards_html = BeautifulSoup(product_cards_container.get_attribute("outerHTML"), "html.parser")
                    product_cards = product_cards_html.find_all("div", {"class": ["sr-srpItem", "prod-info", "item"]})

                    if not product_cards:
                        message = f"No product cards found on page {page}"
                        logging.warning(message)
                        messages.append(message)
                        break

                    for product in product_cards:
                        product_json_data = {
                            "url": "",
                            "title": "",
                            "currency": "",
                            "exact_price": "",
                            "min_order": "",
                            "supplier": "",
                            "origin": "",
                            "feedback": {
                                "rating": "",
                                "star_count": ""
                            },
                            "specifications": {},
                            "images": [],
                            "videos": [],
                            "website_name": "MadeinChina",
                            "discount_information": "N/A",
                            "brand_name": "N/A"
                        }

                        # Extract product URL
                        if 'url' in desired_fields:
                            try:
                                product_link = product.select_one('a[href*="made-in-china.com"]')
                                if product_link:
                                    product_url = product_link.get('href')
                                    product_url = 'https:' + product_url if product_url.startswith('//') else product_url
                                    product_json_data["url"] = product_url
                            except Exception as e:
                                logging.error(f"Error extracting product URL: {str(e)}")

                        # Skip if product URL already scraped or empty
                        if not product_json_data["url"] or product_json_data["url"] in scraped_products:
                            continue

                        # Extract product title
                        if 'title' in desired_fields:
                            try:
                                title_elem = product.select_one('.product-name, .sr-srpItem-title, .title')
                                if title_elem:
                                    product_json_data["title"] = title_elem.get_text(strip=True)
                            except Exception as e:
                                logging.error(f"Error extracting product title: {str(e)}")

                        # Extract currency and price
                        if 'currency' in desired_fields or 'exact_price' in desired_fields:
                            try:
                                price_elem = product.select_one('.price, .price-info, .sr-srpItem-price')
                                if price_elem:
                                    currency_price_text = price_elem.get_text(strip=True)
                                    currency = ''.join([c for c in currency_price_text if not c.isdigit() and c not in ['.', '-', ' ']]).strip()
                                    product_json_data["currency"] = currency
                                    price_range = currency_price_text.replace(currency, '').strip()
                                    product_json_data["exact_price"] = price_range
                            except Exception as e:
                                logging.error(f"Error extracting product currency and price: {str(e)}")

                        # Extract minimum order
                        if 'min_order' in desired_fields:
                            try:
                                min_order_elem = product.find('div', string=lambda t: t and '(MOQ)' in t)
                                if min_order_elem:
                                    min_order_text = min_order_elem.get_text(strip=True)
                                    min_order = min_order_text.replace('(MOQ)', '').strip()
                                    product_json_data["min_order"] = min_order
                            except Exception as e:
                                logging.error(f"Error extracting product minimum order: {str(e)}")

                        # Extract supplier name
                        if 'supplier' in desired_fields:
                            try:
                                supplier_elem = product.select_one('.company-name, .supplier-name, .compnay-name span')
                                if supplier_elem:
                                    product_json_data["supplier"] = supplier_elem.get_text(strip=True)
                            except Exception as e:
                                logging.error(f"Error extracting supplier name: {str(e)}")

                        # Scrape product page details if needed
                        if any(field in desired_fields for field in ['origin', 'feedback', 'specifications', 'images', 'videos']):
                            if product_json_data["url"]:
                                try:
                                    browser.get(product_json_data["url"])
                                    WebDriverWait(browser, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
                                    if detect_captcha():
                                        captcha_details = get_captcha_details()
                                        save_session(session_id, browser.current_url, browser.get_cookies())
                                        print(json.dumps({
                                            "status": "captcha_required",
                                            "captcha": captcha_details,
                                            "sessionId": session_id
                                        }))
                                        sys.exit(0)
                                    
                                    browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                                    WebDriverWait(browser, 2).until(lambda d: True)
                                    product_page_html = BeautifulSoup(browser.page_source, "html.parser")

                                    # Extract origin
                                    if 'origin' in desired_fields:
                                        try:
                                            origin_elem = product_page_html.select_one('.basic-info-list .bsc-item .bac-item-value')
                                            if origin_elem:
                                                product_json_data["origin"] = origin_elem.get_text(strip=True)
                                        except Exception as e:
                                            logging.error(f"Error extracting origin: {str(e)}")

                                    # Extract feedback
                                    if 'feedback' in desired_fields:
                                        try:
                                            rating_elem = browser.find_element(By.CSS_SELECTOR, "a.J-company-review .review-score, .review-rating")
                                            rating_text = rating_elem.text if rating_elem else "No rating available"
                                            star_elems = browser.find_elements(By.CSS_SELECTOR, "a.J-company-review .review-rate i, .review-stars i")
                                            star_count = len(star_elems)
                                            product_json_data["feedback"]["rating"] = rating_text
                                            product_json_data["feedback"]["star_count"] = str(star_count)
                                        except (NoSuchElementException, TimeoutException):
                                            product_json_data["feedback"]["rating"] = "No rating available"
                                            product_json_data["feedback"]["star_count"] = "0"
                                        except Exception as e:
                                            logging.error(f"Unexpected error extracting reviews: {str(e)}")

                                    # Extract specifications
                                    if 'specifications' in desired_fields:
                                        specifications = {}
                                        try:
                                            rows = browser.find_elements(By.XPATH, "//div[@class='basic-info-list']/div[@class='bsc-item cf']")
                                            for row in rows:
                                                try:
                                                    label_div = row.find_element(By.XPATH, ".//div[contains(@class,'bac-item-label')]")
                                                    value_div = row.find_element(By.XPATH, ".//div[contains(@class,'bac-item-value')]")
                                                    label = label_div.text.strip()
                                                    value = value_div.text.strip()
                                                    if label and value:
                                                        specifications[label] = value
                                                except Exception as e:
                                                    logging.error(f"Error processing specification row: {str(e)}")
                                            product_json_data["specifications"] = specifications
                                        except Exception as e:
                                            logging.error(f"Error extracting specifications: {str(e)}")

                                    # Extract images and videos
                                    if 'images' in desired_fields or 'videos' in desired_fields:
                                        try:
                                            swiper = product_page_html.find("div", {"class": ["sr-proMainInfo-slide-container", "product-media"]})
                                            if swiper:
                                                wrapper = swiper.find("div", {"class": "swiper-wrapper"})
                                                if wrapper:
                                                    media_blocks = wrapper.find_all("div", {"class": ["sr-prMainInfo-slide-inner", "media-item"]})
                                                    for media in media_blocks:
                                                        if 'videos' in desired_fields:
                                                            videos = media.find_all("script", {"type": "text/data-video"})
                                                            for vid in videos:
                                                                video_data = json.loads(vid.get_text(strip=True))
                                                                video_url = video_data.get("videoUrl")
                                                                product_json_data["videos"].append(video_url)
                                                        if 'images' in desired_fields:
                                                            images = media.find_all("img")
                                                            for img in images:
                                                                src = img.get("src", "")
                                                                if src.startswith("//"):
                                                                    src = "https:" + src
                                                                product_json_data["images"].append(src)
                                        except Exception as e:
                                            logging.error(f"Error extracting media: {str(e)}")

                                except Exception as e:
                                    logging.error(f"Error processing product page {product_json_data['url']}: {str(e)}")

                        # Filter and store product data
                        filtered_product = filter_product_data(product_json_data, desired_fields)
                        scraped_products[product_json_data["url"]] = filtered_product

                    break  # Exit retry loop on success
                except Exception as e:
                    logging.error(f"Attempt {attempt + 1}/{retries}: Error scraping page {page}: {str(e)}")
                    time.sleep(5)
                if attempt == retries - 1:  # If all retries failed
                    message = f"Failed to scrape page {page} after {retries} attempts"
                    logging.warning(message)
                    messages.append(message)
                    break  # Exit retry loop and move to next page

        # Log if no products were scraped
        if not scraped_products:
            message = "No products were scraped across all pages"
            logging.info(message)
            messages.append(message)

        # Write final output to file
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(list(scraped_products.values()), f, ensure_ascii=False, indent=4)
        
        # Return final JSON result
        result = {
            "status": "completed",
            "products": list(scraped_products.values())
        }
        if messages:
            result["messages"] = messages
        print(json.dumps(result))

    except Exception as e:
        logging.error(f"Fatal error in scrape_madeinchina_products: {str(e)}")
        print(json.dumps({
            "status": "error",
            "message": f"Fatal error: {str(e)}"
        }))
    finally:
        browser.quit()
        session_file = f"session_{session_id}.pkl"
        if os.path.exists(session_file):
            os.remove(session_file)

if __name__ == "__main__":
    scrape_madeinchina_products()