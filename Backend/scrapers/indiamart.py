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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, StaleElementReferenceException
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote

# Setup logging to file and stderr (no stdout to avoid JSON parsing issues)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('indiamart_scraper.log'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Supported fields
SUPPORTED_FIELDS = [
    'url', 'title', 'currency', 'exact_price', 'description', 'min_order',
    'supplier', 'origin', 'feedback', 'image_url', 'images', 'videos',
    'dimensions', 'website_name', 'discount_information', 'brand_name'
]

# Map frontend field names to backend field names
FIELD_MAPPING = {
    'image_url': 'images',
    'video_url': 'videos'
}

# Parse command-line arguments
logger.info(f"Received command-line arguments: {sys.argv}")
if len(sys.argv) < 5 and sys.argv[1] != "--validate-captcha":
    error_msg = "Usage: python indiamart.py <keyword> <page_count> <retries> <fields>"
    logger.error(error_msg)
    print(json.dumps({"status": "error", "message": error_msg}))
    sys.exit(1)

if sys.argv[1] == "--validate-captcha":
    if len(sys.argv) != 4:
        error_msg = "Invalid arguments for CAPTCHA validation. Usage: python indiamart.py --validate-captcha <captcha_input> <session_id>"
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
    
    output_file = f"products_{keyword.replace(' ', '_')}_indiamart.json"
    logger.info(f"Output file will be saved as: {output_file}")

def setup_driver():
    """Configure and return a Selenium WebDriver instance."""
    logger.info("Initializing Selenium WebDriver")
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
        driver = webdriver.Chrome(
            service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
            options=options
        )
        driver.set_page_load_timeout(30)
        driver.maximize_window()
        logger.info("Chrome WebDriver initialized successfully")
        return driver
    except WebDriverException as e:
        logger.warning(f"Primary WebDriver initialization failed: {str(e)}. Trying with specified Chrome binary")
        try:
            options.binary_location = "C:/Program Files/Google/Chrome/Application/chrome.exe"
            driver = webdriver.Chrome(
                service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                options=options
            )
            driver.set_page_load_timeout(30)
            driver.maximize_window()
            logger.info("Chrome WebDriver initialized with specified binary")
            return driver
        except WebDriverException as e2:
            error_msg = f"Error initializing Chrome browser: {str(e2)}"
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
        captcha_indicators = ['captcha', 'verify you are not a robot', 'recaptcha', 'please verify']
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
        
        # Mock CAPTCHA validation (IndiaMart-specific CAPTCHA handling would go here)
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
    """Clean text by removing extra whitespace and HTML tags."""
    if not text:
        return None
    text = re.sub(r'<[^>]+>', '', text)
    return ' '.join(text.strip().split())

def clean_title(title, keyword):
    """Clean up malformed titles by removing duplicates, redundant brands, and normalizing."""
    if not title:
        return None
    title = clean_text(title)
    title = re.sub(r'[^\w\s,()&-]', '', title)
    # Split title into parts and remove duplicates
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
    # Remove redundant words and brands
    words = title.split()
    common_brands = ["rolex", "omega", "tag heuer", "cartier", "patek philippe", "audemars piguet", "tissot", "seiko", "citizen"]
    brand_count = {brand: 0 for brand in common_brands}
    cleaned_words = []
    seen_words = set()
    for word in words:
        word_lower = word.lower()
        skip = False
        for brand in common_brands:
            if brand in word_lower:
                if brand_count[brand] > 0:
                    skip = True
                    break
                brand_count[brand] += 1
        if not skip and word_lower not in seen_words and word_lower not in ["watch", "timepiece", "used"]:
            cleaned_words.append(word)
            seen_words.add(word_lower)
    cleaned_title = " ".join(cleaned_words).strip()
    # Append keyword parts only if missing
    keyword_parts = keyword.lower().split()
    missing_parts = [part for part in keyword_parts if part not in cleaned_title.lower()]
    if missing_parts:
        cleaned_title += " " + " ".join(missing_parts).capitalize()
    if len(cleaned_title) > 100:
        cleaned_title = cleaned_title[:97] + "..."
    return cleaned_title

def parse_price(price_text):
    """Parse price from text."""
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

def extract_product_data(card, browser, desired_fields, keyword):
    """Extract product data from a card element."""
    product = {
        "url": None,
        "title": None,
        "currency": None,
        "exact_price": None,
        "description": None,
        "min_order": None,
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
        if 'title' in desired_fields:
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
                raw_title = retry_extraction(
                    lambda: clean_text(title_el.get_text(strip=True))
                )
                product['title'] = clean_title(raw_title, keyword) if raw_title else None
                logger.info(f"Title: {product['title']}")
            if not product['title']:
                logger.warning("No title found for product")
                return None

        # URL
        if 'url' in desired_fields:
            url_selectors = [
                'div.titleAskPriceImageNavigation a',
                'a.product-title',
                'a.cardlinks',
                'a[href]'
            ]
            for selector in url_selectors:
                a_tag = soup.select_one(selector)
                if a_tag:
                    href = retry_extraction(
                        lambda: a_tag.get('href', None)
                    )
                    if href and ("indiamart.com" in href or href.startswith('/')):
                        product['url'] = href if href.startswith('http') else f"https://www.indiamart.com{href}"
                        if product['url'] and '?' in product['url']:
                            product['url'] = product['url'].split('?')[0]
                        logger.info(f"URL: {product['url']}")
                        break
            if not product['url']:
                logger.warning(f"No URL found for {product['title']}")
                return None

        # Relaxed keyword filter to include products with partial matches
        if product['title']:
            keyword_parts = keyword.lower().split()
            if not any(part in product['title'].lower() for part in keyword_parts if len(part) > 3):
                logger.info(f"Skipping non-matching product: {product['title']}")
                return None

        # Price
        if 'currency' in desired_fields or 'exact_price' in desired_fields:
            price_selectors = [
                'p.price',
                'div.price',
                'span.price',
                'p[class*="price"]',
                'div[class*="price"]',
                'span[class*="price"]',
                '*[class*="price"]',
                'div.mprice',
                'span.mrp'
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
            else:
                logger.warning(f"No price element found for {product['title']}. Saving card HTML for debugging.")
                with open(f"no_price_{product['url'].split('/')[-1]}.html", "w", encoding="utf-8") as f:
                    f.write(str(soup))
                product['currency'] = None
                product['exact_price'] = None

        # Description
        if 'description' in desired_fields:
            desc_selectors = [
                'div.description',
                'p.description',
                'div.prod-desc',
                'p[class*="desc"]'
            ]
            desc_el = None
            for selector in desc_selectors:
                desc_el = soup.select_one(selector)
                if desc_el:
                    break
            product['description'] = retry_extraction(
                lambda: clean_text(desc_el.get_text(strip=True)),
                default=None
            )
            logger.info(f"Description: {product['description'][:100] if product['description'] else 'None'}...")

        # Min Order
        if 'min_order' in desired_fields:
            moq_selectors = [
                'span.unit',
                'div.moq',
                '*[class*="moq"]',
                '*[class*="min-order"]'
            ]
            moq_el = None
            for selector in moq_selectors:
                moq_el = soup.select_one(selector)
                if moq_el:
                    break
            if moq_el:
                text = retry_extraction(
                    lambda: clean_text(moq_el.get_text(strip=True))
                )
                qty_pattern = r'(\d+)'
                qty_match = re.search(qty_pattern, text) if text else None
                qty = qty_match.group(1) if qty_match else None
                unit_pattern = r'([A-Za-z]+)'
                unit_match = re.search(unit_pattern, text) if text else None
                unit = unit_match.group(1) if unit_match else None
                product['min_order'] = f"{qty} {unit}" if qty and unit else None
                logger.info(f"Min Order: {product['min_order']}")
            else:
                product['min_order'] = "1 unit"
                logger.info(f"Min Order: {product['min_order']} (default)")

        # Supplier
        if 'supplier' in desired_fields:
            supplier_selectors = [
                'div.companyname a',
                'div.companyname',
                'p.company-name',
                '*[class*="company"]'
            ]
            supplier_el = None
            for selector in supplier_selectors:
                supplier_el = soup.select_one(selector)
                if supplier_el:
                    break
            product['supplier'] = retry_extraction(
                lambda: clean_text(supplier_el.get_text(strip=True)),
                default=None
            )
            logger.info(f"Supplier: {product['supplier']}")

        # Origin
        if 'origin' in desired_fields:
            origin_selectors = [
                'span.origin',
                'div[class*="origin"]',
                'p[class*="origin"]'
            ]
            origin_el = None
            for selector in origin_selectors:
                origin_el = soup.select_one(selector)
                if origin_el:
                    break
            product['origin'] = retry_extraction(
                lambda: clean_text(origin_el.get_text(strip=True)),
                default=None
            )
            logger.info(f"Origin: {product['origin']}")

        # Feedback
        if 'feedback' in desired_fields:
            rating_selectors = [
                'div.rating',
                'span.rating',
                '*[class*="rating"]'
            ]
            review_selectors = [
                'span:contains("(")',
                'span.reviews',
                '*[class*="review"]'
            ]
            for selector in rating_selectors:
                rating_el = soup.select_one(selector)
                if rating_el:
                    rating_text = retry_extraction(
                        lambda: rating_el.get_text(strip=True)
                    )
                    rating_match = re.search(r'([\d.]+)', rating_text) if rating_text else None
                    product['feedback']['rating'] = rating_match.group(1) if rating_match else None
                    logger.info(f"Rating: {product['feedback']['rating']}")
                    break
            for selector in review_selectors:
                review_el = soup.select_one(selector)
                if review_el:
                    review_text = retry_extraction(
                        lambda: review_el.get_text(strip=True)
                    )
                    review_match = re.search(r'\((\d+)\)', review_text) if review_text else None
                    product['feedback']['review'] = review_match.group(1) if review_match else None
                    logger.info(f"Reviews: {product['feedback']['review']}")
                    break

        # Images and Dimensions
        if 'images' in desired_fields or 'image_url' in desired_fields or 'dimensions' in desired_fields:
            img_selectors = [
                'img[class*="product-img"]',
                'img[class*="image"]',
                'img[src*="product"]',
                'img[src]',
                'img'
            ]
            images = []
            image_url = None
            dimensions = None
            for selector in img_selectors:
                img_elements = soup.select(selector)
                if img_elements:
                    for idx, img in enumerate(img_elements):
                        src = retry_extraction(
                            lambda: img.get('src', '') or img.get('data-src', ''),
                            default=''
                        )
                        if not src or src.endswith(('placeholder.png', 'default.jpg', 'noimage.jpg')):
                            continue
                        if src and not src.startswith('data:'):
                            if idx == 0:
                                image_url = src
                                try:
                                    img_elem = card.find_element(By.CSS_SELECTOR, selector)
                                    width = retry_extraction(
                                        lambda: browser.execute_script("return arguments[0].naturalWidth", img_elem),
                                        default=img.get('width', 'Unknown')
                                    )
                                    height = retry_extraction(
                                        lambda: browser.execute_script("return arguments[0].naturalHeight", img_elem),
                                        default=img.get('height', 'Unknown')
                                    )
                                    dimensions = f"{width}x{height}"
                                except Exception as e:
                                    logger.debug(f"Error getting image dimensions for {product['title']}: {e}")
                                    dimensions = f"{img.get('width', 'Unknown')}x{img.get('height', 'Unknown')}"
                            images.append(src)
                    break
            product['image_url'] = image_url
            product['images'] = images if images else []
            product['dimensions'] = dimensions
            logger.info(f"Images: {product['images']}, Dimensions: {product['dimensions']}")

        # Videos
        if 'videos' in desired_fields:
            video_selectors = [
                'video source',
                'video[src]'
            ]
            video_els = []
            for selector in video_selectors:
                video_els = soup.select(selector)
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

        # Discount
        if 'discount_information' in desired_fields:
            discount_selectors = [
                'span.discount',
                'div[class*="discount"]',
                'p[class*="discount"]'
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

        # Brand Name
        if 'brand_name' in desired_fields:
            common_brands = ["rolex", "omega", "tag heuer", "cartier", "patek philippe", "audemars piguet", "tissot", "seiko", "citizen"]
            brand_name = None
            if product['title']:
                title_lower = product['title'].lower()
                for brand in common_brands:
                    if re.search(r'\b' + brand + r'\b', title_lower):
                        brand_name = brand.capitalize()
                        break
            product['brand_name'] = brand_name
            logger.info(f"Brand Name: {product['brand_name']}")

        return product
    except StaleElementReferenceException:
        logger.warning(f"Stale element for product {product.get('title', 'Unknown')}")
        return None
    except Exception as e:
        logger.error(f"Error extracting product data for {product.get('title', 'Unknown')}: {e}")
        return None

def scrape_indiamart(keyword, page_count, retries, desired_fields):
    """Main scraping function."""
    logger.info("Starting IndiaMart scraping")
    browser = setup_driver()
    products = {}
    messages = []
    session_id = f"indiamart_{int(time.time())}"
    skipped_products = []
    
    try:
        for page in range(1, page_count + 1):
            url = f"https://dir.indiamart.com/search.mp?ss={quote(keyword.replace(' ', '+'))}&page={page}"
            logger.info(f"Scraping page {page}/{page_count}: {url}")
            for attempt in range(retries):
                try:
                    browser.get(url)
                    WebDriverWait(browser, 20).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
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
                    previous_product_count = 0
                    max_scroll_attempts = 5
                    scroll_attempts = 0
                    while scroll_attempts < max_scroll_attempts:
                        cards = browser.find_elements(By.CSS_SELECTOR, 'div.card, div.product-card, div.listing')
                        current_count = len(cards)
                        logger.info(f"Scroll attempt {scroll_attempts + 1}: Found {current_count} products")
                        if current_count == previous_product_count:
                            break
                        previous_product_count = current_count
                        browser.execute_script(
                            "window.scrollTo(0, Math.min(document.body.scrollHeight, window.scrollY + 800));"
                        )
                        time.sleep(random.uniform(1, 2))
                        scroll_attempts += 1

                    # Try multiple product card selectors
                    product_cards_selectors = [
                        'div.card',
                        'div.product-card',
                        'div.listing',
                        'div[class*="product"]',
                        'li.listing-item'
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
                        with open(f"debug_page_{page}.html", "w", encoding="utf-8") as f:
                            f.write(browser.page_source)
                        break
                    
                    logger.info(f"Found {len(product_cards)} products on page {page}")
                    for index, card in enumerate(product_cards):
                        product = extract_product_data(card, browser, desired_fields, keyword)
                        if product and product['url']:
                            if product['url'] not in products:
                                filtered_product = filter_product_data(product)
                                products[product['url']] = filtered_product
                                logger.info(f"Product {index + 1} scraped successfully")
                            else:
                                logger.info(f"Skipping duplicate product: {product['title']}")
                        elif product and not product['url']:
                            skipped_products.append({
                                "title": product.get('title', 'Unknown'),
                                "reason": "Missing URL"
                            })
                        elif product is None:
                            skipped_products.append({
                                "title": "Unknown",
                                "reason": "Extraction failed or non-matching product"
                            })
                        
                        time.sleep(random.uniform(0.5, 1.5))
                    
                    break
                except TimeoutException as e:
                    logger.error(f"Attempt {attempt + 1}/{retries} failed for page {page}: Timeout - {str(e)}")
                    if attempt == retries - 1:
                        message = f"Failed to scrape page {page} after {retries} attempts"
                        logger.warning(message)
                        messages.append(message)
                        with open(f"debug_page_{page}.html", "w", encoding="utf-8") as f:
                            f.write(browser.page_source)
                        break
                    time.sleep(5 * (attempt + 1))
                except Exception as e:
                    logger.error(f"Attempt {attempt + 1}/{retries} failed for page {page}: {str(e)}")
                    if attempt == retries - 1:
                        message = f"Failed to scrape page {page} after {retries} attempts"
                        logger.warning(message)
                        messages.append(message)
                        break
                    time.sleep(5 * (attempt + 1))
            
            time.sleep(random.uniform(2, 5))
        
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

            # Save skipped products for debugging
            if skipped_products:
                skipped_file = f"skipped_{keyword.replace(' ', '_')}_indiamart.json"
                with open(skipped_file, 'w', encoding='utf-8') as f:
                    json.dump(skipped_products, f, ensure_ascii=False, indent=4)
                logger.info(f"Skipped products saved to {skipped_file}")

            # Save products to output file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result["products"], f, ensure_ascii=False, indent=4)
            logger.info(f"Scraping completed and saved to {output_file}. Total products: {len(products)}")

            # Print JSON result exactly once
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
        scrape_indiamart(keyword, page_count, retries, desired_fields)

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