import sys
import json
import os
import pickle
import logging
import time
import re
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote

# Setup logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dhgate_scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Supported fields
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

# Parse command-line arguments
logger.info(f"Received command-line arguments: {sys.argv}")
if len(sys.argv) < 5 and sys.argv[1] != "--validate-captcha":
    error_msg = "Usage: python dhgate.py <keyword> <page_count> <retries> <fields>"
    logger.error(error_msg)
    print(json.dumps({"status": "error", "message": error_msg}))
    sys.exit(1)

if sys.argv[1] == "--validate-captcha":
    if len(sys.argv) != 4:
        error_msg = "Invalid arguments for CAPTCHA validation. Usage: python dhgate.py --validate-captcha <captcha_input> <session_id>"
        logger.error(error_msg)
        print(json.dumps({"status": "error", "message": error_msg}))
        sys.exit(1)
    captcha_input = sys.argv[2]
    session_id = sys.argv[3]
else:
    keyword = sys.argv[1]
    try:
        page_count = int(sys.argv[2])
        retries = int(sys.argv[3])
    except ValueError:
        error_msg = "page_count and retries must be integers"
        logger.error(error_msg)
        print(json.dumps({"status": "error", "message": error_msg}))
        sys.exit(1)
    
    input_fields = sys.argv[4].split(',')
    mapped_fields = [FIELD_MAPPING.get(field.strip(), field.strip()) for field in input_fields]
    desired_fields = list(set(['url', 'website_name'] + mapped_fields))
    
    invalid_fields = [f for f in mapped_fields if f not in SUPPORTED_FIELDS]
    if invalid_fields:
        error_msg = f"Invalid fields: {', '.join(invalid_fields)}. Supported fields: {', '.join(SUPPORTED_FIELDS)}"
        logger.error(error_msg)
        print(json.dumps({"status": "error", "message": error_msg}))
        sys.exit(1)
    
    output_file = f"products_{keyword.replace(' ', '_')}_dhgate.json"
    logger.info(f"Output file will be saved as: {output_file}")

def setup_driver():
    """Configure and return a Selenium WebDriver instance."""
    logger.info("Initializing Selenium WebDriver")
    
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
        driver = webdriver.Firefox(
            service=webdriver.firefox.service.Service(GeckoDriverManager().install()),
            options=firefox_options
        )
        driver.set_page_load_timeout(30)
        driver.maximize_window()
        logger.info("Firefox WebDriver initialized successfully")
        return driver
    except WebDriverException as e:
        logger.warning(f"Firefox WebDriver initialization failed: {str(e)}. Falling back to Chrome")
    
    # Fallback to Chrome
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    try:
        driver = webdriver.Chrome(
            service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        driver.set_page_load_timeout(30)
        driver.maximize_window()
        logger.info("Chrome WebDriver initialized successfully")
        return driver
    except WebDriverException as e:
        # Try specifying Chrome binary as a last resort
        try:
            chrome_options.binary_location = "C:/Program Files/Google/Chrome/Application/chrome.exe"
            driver = webdriver.Chrome(
                service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            driver.set_page_load_timeout(30)
            driver.maximize_window()
            logger.info("Chrome WebDriver initialized with specified binary")
            return driver
        except WebDriverException as e2:
            error_msg = f"Error initializing browser (Firefox and Chrome failed): {str(e2)}"
            logger.error(error_msg)
            print(json.dumps({"status": "error", "message": error_msg}))
            sys.exit(1)

def save_session(session_id, url, cookies):
    """Save browser session for CAPTCHA handling."""
    session_data = {'url': url, 'cookies': cookies}
    session_file = f"session_{session_id}.pkl"
    try:
        with open(session_file, 'wb') as f:
            pickle.dump(session_data, f)
        logger.info(f"Saved session to {session_file}")
    except Exception as e:
        logger.error(f"Error saving session: {e}")

def load_session(session_id):
    """Load browser session."""
    session_file = f"session_{session_id}.pkl"
    if os.path.exists(session_file):
        try:
            with open(session_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Error loading session: {e}")
            return None
    logger.warning(f"Session file {session_file} not found")
    return None

def detect_captcha(page_source, browser):
    """Detect CAPTCHA presence."""
    try:
        page_source_lower = page_source.lower()
        captcha_indicators = ['h-captcha', 'recaptcha', 'verify you are not a robot', 'please verify', 'captcha']
        if any(indicator in page_source_lower for indicator in captcha_indicators):
            logger.warning("CAPTCHA detected in page source")
            return True
        soup = BeautifulSoup(page_source, 'html.parser')
        captcha_div = (
            soup.find('div', class_='captcha-container') or
            soup.find('div', id='captcha') or
            soup.find('div', class_='g-recaptcha') or
            soup.find('form', id='challenge-form')
        )
        if captcha_div:
            logger.warning("CAPTCHA element found in HTML")
            return True
        if 'captcha' in browser.current_url.lower():
            logger.warning("CAPTCHA detected in URL")
            return True
        return False
    except Exception as e:
        logger.error(f"Error detecting CAPTCHA: {e}")
        return False

def get_captcha_details(browser):
    """Extract CAPTCHA details."""
    try:
        page_source = browser.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        captcha_img = (
            soup.find('img', class_='captcha-image') or
            soup.find('img', id='captcha') or
            soup.find('img', class_=re.compile(r'captcha'))
        )
        captcha_url = captcha_img['src'] if captcha_img and 'src' in captcha_img.attrs else None
        captcha_type = 'image' if captcha_url else 'interactive'
        return {
            'type': captcha_type,
            'url': captcha_url or browser.current_url,
            'html': None
        }
    except Exception as e:
        logger.error(f"Error extracting CAPTCHA details: {e}")
        return {'type': 'unknown', 'url': browser.current_url, 'html': None}

def validate_captcha(captcha_input, session_id):
    """Validate CAPTCHA input."""
    browser = setup_driver()
    try:
        session_data = load_session(session_id)
        if not session_data:
            result = {"valid": False, "message": f"Session {session_id} not found"}
            logger.error(result["message"])
            print(json.dumps(result))
            return
        
        browser.get(session_data['url'])
        for cookie in session_data['cookies']:
            browser.add_cookie(cookie)
        
        # Mock CAPTCHA validation (DHgate-specific CAPTCHA handling would go here)
        if captcha_input == "mock123":
            save_session(session_id, browser.current_url, browser.get_cookies())
            result = {"valid": True, "message": "CAPTCHA validated successfully"}
            logger.info(result["message"])
            print(json.dumps(result))
        else:
            result = {"valid": False, "message": "Invalid CAPTCHA input"}
            logger.error(result["message"])
            print(json.dumps(result))
    except Exception as e:
        result = {"valid": False, "message": f"Error validating CAPTCHA: {str(e)}"}
        logger.error(result["message"])
        print(json.dumps(result))
    finally:
        try:
            browser.quit()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error quitting browser: {e}")

def clean_text(text):
    """Clean text by removing extra whitespace."""
    return ' '.join(text.strip().split()) if text else None

def parse_price(price_text):
    """Parse price from text."""
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

def retry_extraction(func, attempts=3, delay=2, default=None):
    """Retries an extraction function up to 'attempts' times."""
    for i in range(attempts):
        try:
            result = func()
            if result:
                return result
        except Exception as e:
            logger.warning(f"Retry {i+1}/{attempts} failed: {str(e)}")
            if i < attempts - 1:
                time.sleep(delay)
    return default

def filter_product_data(product_data):
    """Filter product data to include only desired fields."""
    filtered_data = {}
    for field in desired_fields:
        if field in product_data:
            filtered_data[field] = product_data[field]
    return filtered_data

def extract_product_data(card, browser, desired_fields):
    """Extract product data from a card element."""
    product = {
        "url": None,
        "title": None,
        "currency": None,
        "exact_price": None,
        "min_order": None,
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
        if 'title' in desired_fields or 'url' in desired_fields:
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
                if 'title' in desired_fields:
                    product['title'] = retry_extraction(
                        lambda: clean_text(title_el.get('title') or title_el.get_text(strip=True))
                    )
                if 'url' in desired_fields:
                    href = title_el.get('href', '')
                    product['url'] = href if href.startswith('http') else f"https://www.dhgate.com{href}"
                    logger.info(f"Product URL: {product['url']}")

        if not product['url']:
            logger.warning("No valid URL found for product")
            return None

        # Price
        if 'currency' in desired_fields or 'exact_price' in desired_fields:
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
                price_text = retry_extraction(
                    lambda: price_el.get_text(strip=True)
                )
                price_info = parse_price(price_text)
                product.update(price_info)
                logger.info(f"Price: {product['exact_price']}, Currency: {product['currency']}")

        # Discount
        if 'discount_information' in desired_fields:
            discount_selectors = [
                '.discount',
                '.promo-info',
                'span[class*="discount"]',
                'div.sale-info'
            ]
            discount_el = None
            for selector in discount_selectors:
                discount_el = soup.select_one(selector)
                if discount_el:
                    break
            product['discount_information'] = retry_extraction(
                lambda: clean_text(discount_el.get_text(strip=True)),
                default=None
            )
            logger.info(f"Discount: {product['discount_information']}")

        # Navigate to product page for detailed fields
        if any(field in desired_fields for field in ['min_order', 'supplier', 'origin', 'feedback', 'specifications', 'images', 'videos', 'brand_name']):
            try:
                logger.info(f"Navigating to product page: {product['url']}")
                browser.get(product['url'])
                WebDriverWait(browser, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.product-info, .product-detail, div.prodSpecifications_showLayer'))
                )
                
                # Check for CAPTCHA
                if detect_captcha(browser.page_source, browser):
                    session_id = f"dhgate_{int(time.time())}"
                    captcha_details = get_captcha_details(browser)
                    save_session(session_id, browser.current_url, browser.get_cookies())
                    result = {
                        "status": "captcha_required",
                        "captcha": captcha_details,
                        "sessionId": session_id
                    }
                    logger.info(f"CAPTCHA detected on product page: {json.dumps(result)}")
                    print(json.dumps(result))
                    sys.exit(0)  # Exit to trigger CAPTCHA handling in Node.js
                
                page_soup = BeautifulSoup(browser.page_source, 'html.parser')

                # Min Order
                if 'min_order' in desired_fields:
                    moq_selectors = [
                        'span.moq',
                        'div.moq',
                        '[class*="min-order"]',
                        'div.min-order-quantity'
                    ]
                    moq_el = None
                    for selector in moq_selectors:
                        moq_el = page_soup.select_one(selector)
                        if moq_el:
                            break
                    product['min_order'] = retry_extraction(
                        lambda: clean_text(moq_el.get_text(strip=True)),
                        default="1 unit"
                    )
                    logger.info(f"Min Order: {product['min_order']}")

                # Supplier
                if 'supplier' in desired_fields:
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
                    product['supplier'] = retry_extraction(
                        lambda: clean_text(supplier_el.get_text(strip=True)),
                        default=None
                    )
                    logger.info(f"Supplier: {product['supplier']}")

                # Origin
                if 'origin' in desired_fields:
                    specs_container = page_soup.find('div', class_=re.compile(r'prodSpecifications_showLayer'))
                    if specs_container:
                        for li in specs_container.select('ul li'):
                            key_text = retry_extraction(
                                lambda: clean_text(li.find('span').get_text(strip=True) if li.find('span') else ''),
                                default=''
                            )
                            if key_text and 'origin' in key_text.lower():
                                value_div = li.find('div', class_=re.compile(r'prodSpecifications_deswrap'))
                                product['origin'] = retry_extraction(
                                    lambda: clean_text(value_div.get_text(strip=True)),
                                    default=None
                                )
                                logger.info(f"Origin: {product['origin']}")
                                break

                # Feedback
                if 'feedback' in desired_fields:
                    review_selectors = [
                        'span[class*="reviewsCount"]',
                        'span.review-count',
                        'div.review-info span'
                    ]
                    review_el = None
                    for selector in review_selectors:
                        review_el = page_soup.select_one(selector)
                        if review_el:
                            break
                    if review_el:
                        review_text = retry_extraction(
                            lambda: review_el.get_text(strip=True)
                        )
                        review_match = re.search(r'\d+', review_text)
                        product['feedback']['review'] = review_match.group(0) if review_match else None
                        logger.info(f"Reviews: {product['feedback']['review']}")
                    
                    rating_selectors = [
                        'div[class*="starWarp"]',
                        'span.star-rating',
                        'div.rating-score'
                    ]
                    rating_el = None
                    for selector in rating_selectors:
                        rating_el = page_soup.select_one(selector)
                        if rating_el:
                            break
                    if rating_el:
                        rating_text = retry_extraction(
                            lambda: rating_el.get_text(strip=True)
                        )
                        if re.match(r'^\d+\.\d+', rating_text):
                            product['feedback']['rating'] = rating_text
                            logger.info(f"Rating: {product['feedback']['rating']}")

                # Specifications
                if 'specifications' in desired_fields:
                    specs = {}
                    specs_container = page_soup.find('div', class_=re.compile(r'prodSpecifications_showLayer'))
                    if specs_container:
                        for li in specs_container.select('ul li'):
                            key_span = li.find('span')
                            value_div = li.find('div', class_=re.compile(r'prodSpecifications_deswrap'))
                            if key_span and value_div:
                                key = retry_extraction(
                                    lambda: clean_text(key_span.get_text(strip=True).replace(':', '')),
                                    default=None
                                )
                                value = retry_extraction(
                                    lambda: clean_text(value_div.get_text(strip=True)),
                                    default=None
                                )
                                if key and value:
                                    specs[key] = value
                                    logger.info(f"Specification: {key}: {value}")
                    product['specifications'] = specs

                # Images
                if 'images' in desired_fields:
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
                        retry_extraction(
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
                    logger.info(f"Images: {product['images']}")

                # Videos
                if 'videos' in desired_fields:
                    video_selectors = [
                        'video source',
                        '[class*="video"] source',
                        'div.video-player source'
                    ]
                    video_els = []
                    for selector in video_selectors:
                        video_els = page_soup.select(selector)
                        if video_els:
                            break
                    product['videos'] = [
                        retry_extraction(
                            lambda: video.get('src', ''),
                            default=''
                        )
                        for video in video_els
                        if video.get('src')
                    ]
                    logger.info(f"Videos: {product['videos']}")

                # Brand Name
                if 'brand_name' in desired_fields:
                    brand_name = next(
                        (value for key, value in product['specifications'].items()
                         if key.lower() in ['brand', 'product brand']),
                        None
                    )
                    if not brand_name:
                        brand_selectors = [
                            'span[class*="brand"]',
                            'div.brand-info span',
                            'span.brand-name'
                        ]
                        brand_el = None
                        for selector in brand_selectors:
                            brand_el = page_soup.select_one(selector)
                            if brand_el:
                                break
                        if brand_el:
                            brand_name = retry_extraction(
                                lambda: clean_text(re.sub(r'^Brand:\s*', '', brand_el.get_text(strip=True), flags=re.IGNORECASE)),
                                default=None
                            )
                    
                    if not brand_name and product['title']:
                        title_lower = product['title'].lower()
                        brands = ["dior", "nike", "adidas", "rolex", "gucci", "prada"]
                        for brand in brands:
                            if re.search(r'\b' + brand + r'\b', title_lower):
                                brand_name = brand.capitalize()
                                break
                    product['brand_name'] = brand_name
                    logger.info(f"Brand Name: {product['brand_name']}")

            except (TimeoutException, NoSuchElementException) as e:
                logger.warning(f"Error loading product page {product['url']}: {e}")

        return product
    except Exception as e:
        logger.error(f"Error extracting product data: {e}")
        return product

def scrape_dhgate(keyword, page_count, retries, desired_fields):
    """Main scraping function."""
    logger.info("Starting DHgate scraping")
    browser = setup_driver()
    products = {}
    messages = []  # Collect messages for final output
    session_id = f"dhgate_{int(time.time())}"
    
    try:
        for page in range(1, page_count + 1):
            url = f"https://www.dhgate.com/wholesale/search.do?act=search&searchkey={quote(keyword)}&pageNo={page}"
            logger.info(f"Scraping page {page}: {url}")
            for attempt in range(retries):
                try:
                    browser.get(url)
                    WebDriverWait(browser, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '.gallery-pro, .item-box, .product-item'))
                    )
                    
                    # Check for CAPTCHA
                    if detect_captcha(browser.page_source, browser):
                        captcha_details = get_captcha_details(browser)
                        save_session(session_id, browser.current_url, browser.get_cookies())
                        result = {
                            "status": "captcha_required",
                            "captcha": captcha_details,
                            "sessionId": session_id
                        }
                        messages.append("CAPTCHA detected")
                        logger.info(f"CAPTCHA detected: {json.dumps(result)}")
                        print(json.dumps(result))
                        return result
                    
                    # Scroll to load all products
                    browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)  # Wait for lazy-loaded content

                    # Try multiple product card selectors
                    product_cards_selectors = [
                        '.gallery-pro',
                        '.item-box',
                        '.product-item',
                        'div[class*="product-list"] > div',
                        'li.item'
                    ]
                    product_cards = None
                    for selector in product_cards_selectors:
                        try:
                            product_cards = WebDriverWait(browser, 10).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                            )
                            if product_cards:
                                logger.info(f"Found product cards with selector: {selector}")
                                break
                        except TimeoutException:
                            logger.info(f"Selector {selector} failed")
                            continue

                    if not product_cards:
                        message = f"No products found on page {page}"
                        logger.warning(message)
                        messages.append(message)
                        break
                    
                    logger.info(f"Found {len(product_cards)} products on page {page}")
                    for index, card in enumerate(product_cards):
                        product = extract_product_data(card, browser, desired_fields)
                        if product and product['url'] and product['url'] not in products:
                            filtered_product = filter_product_data(product)
                            products[product['url']] = filtered_product
                            logger.info(f"Product {index + 1} scraped successfully")
                        
                        # Random delay to mimic human behavior
                        time.sleep(random.uniform(0.5, 1.5))
                    
                    break
                except (TimeoutException, NoSuchElementException) as e:
                    logger.error(f"Attempt {attempt + 1}/{retries} failed for page {page}: {str(e)}")
                    if attempt == retries - 1:
                        message = f"Failed to scrape page {page} after {retries} attempts"
                        logger.warning(message)
                        messages.append(message)
                        break
                    time.sleep(5)
        
        # Save to JSON and return result
        try:
            result = {
                "status": "completed",
                "products": list(products.values())
            }
            if messages:
                result["messages"] = messages
            if not products:
                message = "No products were scraped across all pages"
                logger.info(message)
                result["messages"] = result.get("messages", []) + [message]

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result["products"], f, ensure_ascii=False, indent=4)
            logger.info(f"Scraping completed and saved to {output_file}. Total products: {len(products)}")
            print(json.dumps(result))
            return result
        
        except Exception as e:
            logger.error(f"Error saving JSON file: {e}")
            result = {"status": "error", "message": f"Error saving JSON file: {str(e)}"}
            print(json.dumps(result))
            return result
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        result = {"status": "error", "message": str(e)}
        print(json.dumps(result))
        return result
    finally:
        try:
            browser.quit()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error quitting browser: {e}")
        session_file = f"session_{session_id}.pkl"
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                logger.info(f"Removed session file: {session_file}")
            except Exception as e:
                logger.error(f"Error removing session file: {e}")

def main():
    """Main entry point."""
    logger.info("Starting main execution")
    if sys.argv[1] == "--validate-captcha":
        validate_captcha(captcha_input, session_id)
    else:
        result = scrape_dhgate(keyword, page_count, retries, desired_fields)
        print(json.dumps(result))

if __name__ == "__main__":
    browser = None
    try:
        main()
    except Exception as e:
        logger.error(f"Main error: {str(e)}")
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)
    finally:
        if browser:
            try:
                browser.quit()
                logger.info("Browser closed successfully")
            except Exception as e:
                logger.error(f"Error quitting browser: {e}")