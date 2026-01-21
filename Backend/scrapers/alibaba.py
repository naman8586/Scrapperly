import time
import json
import re
import logging
import os
import random
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, urljoin
from typing import List, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, WebDriverException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Logging setup
log_folder = Path("logs")
log_folder.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
logging.basicConfig(
    filename=f"logs/alibaba_scraper_{timestamp}.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Supported fields for user selection
SUPPORTED_FIELDS = [
    'url', 'title', 'currency', 'exact_price', 'description', 'min_order',
    'supplier', 'origin', 'feedback', 'image_url', 'images', 'videos',
    'specifications', 'website_name', 'discount_information', 'brand_name'
]

# Get command-line arguments
if len(sys.argv) != 5:
    print("Usage: python alibaba.py <search_keyword> <page_count> <retries> <fields>")
    logger.error("Invalid arguments. Usage: python alibaba.py <search_keyword> <page_count> <retries> <fields>")
    sys.exit(1)

search_keyword = sys.argv[1]
try:
    max_pages = int(sys.argv[2])
    retries = int(sys.argv[3])
except ValueError:
    print("Error: page_count and retries must be integers")
    logger.error("page_count and retries must be integers")
    sys.exit(1)

# Parse fields (comma-separated)
fields = sys.argv[4].split(',')
# Always include 'url' and 'website_name' for context and deduplication
desired_fields = ['url', 'website_name'] + [f.strip() for f in fields if f.strip() in SUPPORTED_FIELDS]
# Validate fields
invalid_fields = [f for f in fields if f.strip() not in SUPPORTED_FIELDS]
if invalid_fields:
    print(f"Error: Invalid fields: {', '.join(invalid_fields)}. Supported fields: {', '.join(SUPPORTED_FIELDS)}")
    logger.error(f"Invalid fields: {', '.join(invalid_fields)}. Supported fields: {', '.join(SUPPORTED_FIELDS)}")
    sys.exit(1)

# Setup output file
output_file = f"products_{search_keyword.replace(' ', '_')}_alibaba.json"

class AlibabaScraper:
    def __init__(self, search_keyword: str, max_pages: int = 10, headless: bool = False, chrome_binary: Optional[str] = None, min_products: int = 100):
        """Initialize the Alibaba scraper."""
        if not search_keyword or not search_keyword.strip():
            raise ValueError("Search keyword cannot be empty")
        self.search_keyword = re.sub(r'[^\w\s]', '', search_keyword.strip()).lower()
        self.max_pages = max(1, max_pages)
        self.min_products = max(0, min_products)
        self.headless = headless
        self.chrome_binary = chrome_binary
        self.scraped_data = []
        self.skipped_products = []
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0"
        ]
        self.output_dir = Path("data")
        self.output_dir.mkdir(exist_ok=True)
        self.driver = None
        self.wait = None
        self.base_url = "https://www.alibaba.com"
        self.selectors = {
            "product_card": ".m-gallery-product-item-v2, .m-gallery-product-item-wrap, .search-card, .list-outter, .organic-gallery-offer-outter, .offer-item, .product-card, [data-content='item'], div[data-spm]",
            "product_link": "a.elements-title-normal, a.organic-gallery-title__link, a[href*='product-detail'], a[class*='card-main'], a",
            "next_page": "a.next, a[class*='next'], [class*='pagination-next'], [aria-label*='next'], a[rel='next'], button[class*='next']",
            "title": "h2.elements-title-normal__content, a.organic-gallery-title__link, h2, a[class*='title'], div[class*='title'], [class*='title']",
            "price": ".m-gallery-product-item-price, .price-main, span.elements-offer-price-normal__price, div[class*='price'], span[class*='price'], [class*='amount']",
            "description": "div.product-detail-description, div.product-desc, div[class*='desc'], div[class*='text']",
            "detail_description": "table tbody tr:first-child td:nth-child(2) div.magic-3, div.ife-detail-decorate-table div.magic-3, div[class*='description'], div[class*='detail-content']",
            "supplier": ".m-gallery-product-item-supplier, .company-name, div.supplier-name, div[class*='company-name'], [class*='supplier'], [class*='seller']",
            "origin": "span.origin, *[class*='origin'], *[class*='location']",
            "feedback": ".rating, .rating-value, div[class*='rating'], span[class*='rating'], [class*='review']",
            "discount": "span.discount, span[class*='discount'], div[class*='discount'], [class*='promo'], [class*='sale']",
            "image": "img.m-gallery-product-item-img, img[src*='product'], img[class*='image'], img[src], img[data-src], img[data-lazy-src]",
            "detail_images": ".detail-gallery img, .thumb-list img, [class*='thumbnail'] img, img[src*='product'], .main-image img",
            "detail_specs": ".spec-table, table[class*='spec'], div[class*='specification'], .product-props, .attribute-list, ul.product-feature",
            "video": "video, video[src], *[class*='video']",
            "captcha": "div[class*='captcha'], iframe[src*='captcha'], [id*='captcha'], div[class*='verify']"
        }
        self._setup_driver()

    def _setup_driver(self):
        """Set up Selenium WebDriver with Chrome."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument(f"--window-size={random.randint(1600, 1920)},{random.randint(900, 1080)}")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        if self.chrome_binary and os.path.isfile(self.chrome_binary):
            chrome_options.binary_location = self.chrome_binary
            logger.info(f"Using Chrome binary: {self.chrome_binary}")
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.navigator.chrome = { runtime: {} };
                    Object.defineProperty(window, 'chrome', { get: () => ({ runtime: {} }) });
                    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                """
            })
            self.wait = WebDriverWait(self.driver, 20)
            logger.info("WebDriver initialized")
        except WebDriverException as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def rotate_user_agent(self):
        """Rotate user agent to avoid detection."""
        try:
            user_agent = random.choice(self.user_agents)
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
            logger.debug(f"Rotated user agent to: {user_agent}")
        except Exception as e:
            logger.warning(f"Failed to rotate user agent: {e}")

    def clean_title(self, title: str) -> Optional[str]:
        """Clean and normalize product title."""
        if not title:
            return None
        title = re.sub(r'<[^>]+>', '', title)
        title = re.sub(r'[^\w\s,()&-]', ' ', title)
        parts = re.split(r'[,|/]', title)
        parts = [part.strip() for part in parts if part.strip()]
        seen = set()
        cleaned_parts = []
        for part in parts:
            part_lower = part.lower()
            if part_lower not in seen:
                seen.add(part_lower)
                cleaned_parts.append(part)
        title = " ".join(cleaned_parts)
        words = title.split()
        common_brands = ["louis vuitton", "gucci", "prada", "chanel", "dior", "hermes", "burberry"]
        brand_count = {brand: 0 for brand in common_brands}
        cleaned_words = []
        for word in words:
            word_lower = word.lower()
            skip = False
            for brand in common_brands:
                if brand in word_lower:
                    if brand_count[brand] > 0:
                        skip = True
                        break
                    brand_count[brand] += 1
            if not skip and word_lower not in ["bag", "handbag", "purse", "used"]:
                cleaned_words.append(word)
        cleaned_title = " ".join(cleaned_words).strip()
        if self.search_keyword.lower() not in cleaned_title.lower():
            cleaned_title += f" {self.search_keyword.capitalize()}"
        if len(cleaned_title) > 100:
            cleaned_title = cleaned_title[:97] + "..."
        return cleaned_title

    def extract_price(self, soup: BeautifulSoup, title: str) -> Dict[str, Optional[str]]:
        """Extract currency and exact price."""
        try:
            for selector in self.selectors["price"].split(", "):
                if price_el := soup.select_one(selector):
                    raw_price = price_el.get_text(strip=True)
                    if "Contact Supplier" in raw_price or "Negotiable" in raw_price:
                        return {"currency": None, "exact_price": "Ask Price"}
                    currency = None
                    currency_symbols = ["$", "€", "¥", "£", "US$", "CNY", "₹"]
                    for symbol in currency_symbols:
                        if symbol in raw_price:
                            currency = symbol
                            break
                    price_pattern = r'[\d,]+(?:\.\d+)?'
                    price_matches = re.findall(price_pattern, raw_price)
                    price_values = [re.sub(r'[^\d.]', '', p) for p in price_matches]
                    if price_values:
                        return {"currency": currency, "exact_price": price_values[0]}
                    break
            logger.warning(f"No price found for {title}")
            return {"currency": None, "exact_price": None}
        except Exception as e:
            logger.error(f"Error extracting price for {title}: {e}")
            return {"currency": None, "exact_price": None}

    def extract_images(self, soup: BeautifulSoup, card_elem, title: str) -> Dict[str, Optional[any]]:
        """Extract image_url, images, and dimensions."""
        try:
            images = []
            image_url = None
            dimensions = None
            for selector in self.selectors["image"].split(", "):
                img_elements = soup.select(selector)
                if not img_elements:
                    continue
                for idx, img in enumerate(img_elements):
                    src = img.get("src", "") or img.get("data-src", "") or img.get("data-lazy-src", "")
                    if not src or any(x in src.lower() for x in ['placeholder', 'default', '.svg', 'noimage']):
                        continue
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif not src.startswith(('http://', 'https://')):
                        src = urljoin(self.base_url, src)
                    if idx == 0:
                        image_url = src
                        width = height = "Unknown"
                        try:
                            img_elem = card_elem.find_element(By.CSS_SELECTOR, selector)
                            width = self.driver.execute_script("return arguments[0].naturalWidth", img_elem) or img.get("width", "Unknown")
                            height = self.driver.execute_script("return arguments[0].naturalHeight", img_elem) or img.get("height", "Unknown")
                            dimensions = f"{width}x{height}"
                        except Exception as e:
                            logger.debug(f"Error getting image dimensions for {title}: {e}")
                            dimensions = f"{img.get('width', 'Unknown')}x{img.get('height', 'Unknown')}"
                    images.append(src)
                if images:
                    break
            if images:
                logger.info(f"Found {len(images)} images for {title}")
                return {"image_url": image_url, "images": images[:5], "dimensions": dimensions}
            logger.warning(f"No images found for {title}")
            return {"image_url": None, "images": None, "dimensions": None}
        except Exception as e:
            logger.error(f"Error extracting images for {title}: {e}")
            return {"image_url": None, "images": None, "dimensions": None}

    def extract_description(self, soup: BeautifulSoup, title: str) -> Optional[str]:
        """Extract product description."""
        try:
            for selector in self.selectors["detail_description"].split(", "):
                if desc := soup.select_one(selector):
                    return desc.get_text(strip=True)
            return None
        except Exception as e:
            logger.error(f"Error extracting description for {title}: {e}")
            return None

    def extract_min_order(self, soup: BeautifulSoup, title: str) -> Optional[str]:
        """Extract minimum order quantity and unit."""
        try:
            for selector in self.selectors["discount"].split(", "):
                if moq_el := soup.select_one(selector):
                    text = moq_el.get_text(strip=True)
                    qty_pattern = r'(\d+)'
                    qty_match = re.search(qty_pattern, text)
                    qty = qty_match.group(1) if qty_match else None
                    unit_pattern = r'([A-Za-z]+)'
                    unit_match = re.search(unit_pattern, text)
                    unit = unit_match.group(1) if unit_match else None
                    if qty and unit:
                        return f"{qty} {unit}"
                    return None
            return None
        except Exception as e:
            logger.error(f"Error extracting min order for {title}: {e}")
            return None

    def extract_supplier(self, soup: BeautifulSoup, title: str) -> Optional[str]:
        """Extract supplier name."""
        try:
            for selector in self.selectors["supplier"].split(", "):
                if elem := soup.select_one(selector):
                    return elem.get_text(strip=True)
            return None
        except Exception as e:
            logger.error(f"Error extracting supplier for {title}: {e}")
            return None

    def extract_origin(self, soup: BeautifulSoup, title: str) -> Optional[str]:
        """Extract product origin."""
        try:
            for selector in self.selectors["origin"].split(", "):
                if origin_el := soup.select_one(selector):
                    return origin_el.get_text(strip=True)
            return None
        except Exception as e:
            logger.error(f"Error extracting origin for {title}: {e}")
            return None

    def extract_feedback(self, soup: BeautifulSoup, title: str) -> Dict[str, Optional[str]]:
        """Extract rating and review count."""
        feedback = {"rating": None, "review": None}
        try:
            for selector in self.selectors["feedback"].split(", "):
                if rating_el := soup.select_one(selector):
                    rating_text = rating_el.get_text(strip=True)
                    rating_match = re.search(r'([\d.]+)', rating_text)
                    if rating_match:
                        feedback["rating"] = rating_match.group(1)
                        break
            for selector in self.selectors["feedback"].split(", "):
                if review_el := soup.select_one(selector):
                    review_text = review_el.get_text(strip=True)
                    review_match = re.search(r'\((\d+)\)', review_text)
                    if review_match:
                        feedback["review"] = review_match.group(1)
                        break
            return feedback
        except Exception as e:
            logger.error(f"Error extracting feedback for {title}: {e}")
            return {"rating": None, "review": None}

    def extract_brand(self, title: str) -> Optional[str]:
        """Extract brand from title."""
        try:
            title_lower = title.lower()
            common_brands = ["louis vuitton", "gucci", "prada", "chanel", "dior", "hermes", "burberry"]
            for brand in common_brands:
                if re.search(r'\b' + re.escape(brand) + r'\b', title_lower):
                    return brand.title()
            return None
        except Exception as e:
            logger.error(f"Error extracting brand: {e}")
            return None

    def extract_discount(self, soup: BeautifulSoup, title: str) -> Optional[str]:
        """Extract discount information."""
        try:
            for selector in self.selectors["discount"].split(", "):
                if discount_el := soup.select_one(selector):
                    return discount_el.get_text(strip=True)
            return None
        except Exception as e:
            logger.error(f"Error extracting discount for {title}: {e}")
            return None

    def extract_videos(self, soup: BeautifulSoup, title: str) -> Optional[List[str]]:
        """Extract video URLs."""
        try:
            videos = []
            for selector in self.selectors["video"].split(", "):
                for video_el in soup.find_all("video"):
                    if src := video_el.get("src"):
                        videos.append(src)
            return videos if videos else None
        except Exception as e:
            logger.error(f"Error extracting videos for {title}: {e}")
            return None

    def extract_specifications(self, soup: BeautifulSoup, title: str) -> Dict[str, str]:
        """Extract product specifications."""
        specs = {}
        try:
            for selector in self.selectors["detail_specs"].split(", "):
                for spec_elem in soup.select(selector):
                    if selector == ".attribute-list":
                        for item in spec_elem.select(".attribute-item"):
                            key_elem = item.select_one(".left")
                            value_elem = item.select_one(".right span")
                            if key_elem and value_elem:
                                key = key_elem.get_text(strip=True)
                                value = value_elem.get_text(strip=True)
                                if key and value and len(key) < 100 and len(value) < 500:
                                    specs[key] = value
                    else:
                        for row in spec_elem.select("tr, li, div.do-entry-item"):
                            cells = row.select("th, td, span.attr-name, span.attr-value")
                            if len(cells) >= 2:
                                key = cells[0].get_text(strip=True)
                                value = cells[1].get_text(strip=True)
                                if key and value and len(key) < 100 and len(value) < 500:
                                    specs[key] = value
                    if specs:
                        break
                if specs:
                    break
            return specs
        except Exception as e:
            logger.error(f"Error extracting specifications for {title}: {e}")
            return {}

    def handle_anti_bot_checks(self) -> bool:
        """Detect and handle anti-bot measures."""
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.selectors["captcha"])))
            logger.warning("Captcha detected! Retrying...")
            return False
        except TimeoutException:
            return True
        except Exception as e:
            logger.error(f"Error handling anti-bot checks: {e}")
            return False

    def extract_detail_page(self, url: str, title: str) -> Dict[str, any]:
        """Extract data from product detail page."""
        detail_data = {
            "description": None,
            "videos": None,
            "specifications": {},
            "images": [],
            "origin": None
        }
        try:
            self.driver.get(url)
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            if not self.handle_anti_bot_checks():
                logger.error(f"Failed anti-bot checks on detail page: {url}")
                return detail_data
            for i in range(2):
                self.driver.execute_script(f"window.scrollTo(0, {i * 500});")
                time.sleep(0.5)
            detail_html = self.driver.page_source
            detail_soup = BeautifulSoup(detail_html, "html.parser")
            detail_data["description"] = self.extract_description(detail_soup, title)
            detail_data["videos"] = self.extract_videos(detail_soup, title)
            detail_data["specifications"] = self.extract_specifications(detail_soup, title)
            detail_data["origin"] = self.extract_origin(detail_soup, title)
            valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')
            for selector in self.selectors["detail_images"].split(", "):
                for img in detail_soup.select(selector):
                    src = img.get("src", "") or img.get("data-src", "") or img.get("data-lazy-src", "")
                    if not src or any(x in src.lower() for x in ['placeholder', 'default', '.svg', 'noimage']):
                        continue
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif not src.startswith(('http://', 'https://')):
                        src = urljoin(self.base_url, src)
                    if src.lower().endswith(valid_extensions):
                        src = src.replace("_.webp", "")
                        if src not in detail_data["images"]:
                            detail_data["images"].append(src)
                if detail_data["images"]:
                    break
            detail_data["images"] = detail_data["images"][:5]
            logger.info(f"Extracted detail page data for: {title}")
        except Exception as e:
            logger.error(f"Error extracting detail page {url}: {e}")
        return detail_data

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def scrape_products(self) -> List[Dict]:
        """Main scraping logic."""
        try:
            for page in range(1, self.max_pages + 1):
                if len(self.scraped_data) >= self.min_products:
                    logger.info(f"Reached target of {self.min_products} products")
                    break
                url = f"{self.base_url}/trade/search?SearchText={quote(self.search_keyword)}&page={page}"
                logger.info(f"Scraping page {page}/{self.max_pages}: {url}")
                self.rotate_user_agent()
                self.driver.get(url)
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(random.uniform(2, 4))
                if not self.handle_anti_bot_checks():
                    logger.error(f"Failed anti-bot checks on page {page}")
                    continue
                working_selector = None
                for selector in self.selectors["product_card"].split(", "):
                    try:
                        self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
                        working_selector = selector
                        logger.info(f"Using product selector: {selector}")
                        break
                    except TimeoutException:
                        continue
                if not working_selector:
                    logger.error(f"No products found on page {page}")
                    continue
                previous_count = 0
                for _ in range(3):
                    cards = self.driver.find_elements(By.CSS_SELECTOR, working_selector)
                    if len(cards) == previous_count:
                        break
                    previous_count = len(cards)
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(random.uniform(1, 2))
                product_list = []
                idx = 0
                while True:
                    if len(self.scraped_data) + len(product_list) >= self.min_products:
                        break
                    cards = self.driver.find_elements(By.CSS_SELECTOR, working_selector)
                    if idx >= len(cards):
                        break
                    retries = 3
                    card_elem = None
                    while retries > 0:
                        try:
                            card_elem = cards[idx]
                            break
                        except (StaleElementReferenceException, IndexError):
                            retries -= 1
                            time.sleep(1)
                            cards = self.driver.find_elements(By.CSS_SELECTOR, working_selector)
                    if not card_elem:
                        logger.warning(f"Failed to retrieve card {idx} after retries")
                        self.skipped_products.append({"idx": idx + 1, "page": page, "reason": "Stale element after retries"})
                        idx += 1
                        continue
                    product_data = {
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
                        "images": None,
                        "videos": None,
                        "dimensions": None,
                        "website_name": "Alibaba.com",
                        "discount_information": None,
                        "brand_name": None,
                        "specifications": {}
                    }
                    try:
                        card_html = card_elem.get_attribute("outerHTML")
                        card_soup = BeautifulSoup(card_html, "html.parser")
                    except StaleElementReferenceException:
                        logger.warning(f"Stale element for card {idx}. Skipping.")
                        self.skipped_products.append({"idx": idx + 1, "page": page, "reason": "Stale element during HTML retrieval"})
                        idx += 1
                        continue
                    title = None
                    for selector in self.selectors["title"].split(", "):
                        if title_el := card_soup.select_one(selector):
                            title = title_el.get_text(strip=True)
                            break
                    if not title:
                        logger.warning(f"No title found for card {idx}")
                        self.skipped_products.append({"idx": idx + 1, "page": page, "reason": "No title"})
                        idx += 1
                        continue
                    product_data["title"] = self.clean_title(title)
                    if self.search_keyword.lower() not in product_data["title"].lower():
                        logger.info(f"Skipping non-matching product: {product_data['title']}")
                        self.skipped_products.append({
                            "idx": idx + 1,
                            "page": page,
                            "title": product_data["title"],
                            "reason": f"Does not match search keyword: {self.search_keyword}"
                        })
                        idx += 1
                        continue
                    product_url = None
                    for selector in self.selectors["product_link"].split(", "):
                        if a_tag := card_soup.select_one(selector):
                            product_url = a_tag.get("href", None)
                            break
                    if not product_url:
                        logger.warning(f"No URL found for {product_data['title']}")
                        self.skipped_products.append({
                            "idx": idx + 1,
                            "page": page,
                            "title": product_data["title"],
                            "reason": "No URL"
                        })
                        idx += 1
                        continue
                    if product_url.startswith('//'):
                        product_url = f"https:{product_url}"
                    elif not product_url.startswith(('http://', 'https://')):
                        product_url = urljoin(self.base_url, product_url)
                    if "?" in product_url:
                        product_url = product_url.split("?")[0]
                    product_data["url"] = product_url
                    product_data.update(self.extract_price(card_soup, product_data["title"]))
                    product_data["min_order"] = self.extract_min_order(card_soup, product_data["title"])
                    product_data["supplier"] = self.extract_supplier(card_soup, product_data["title"])
                    product_data["feedback"] = self.extract_feedback(card_soup, product_data["title"])
                    product_data["discount_information"] = self.extract_discount(card_soup, product_data["title"])
                    product_data["brand_name"] = self.extract_brand(product_data["title"])
                    image_data = self.extract_images(card_soup, card_elem, product_data["title"])
                    product_data.update(image_data)
                    if image_data["dimensions"]:
                        product_data["specifications"]["Dimensions"] = image_data["dimensions"]
                    product_data["dimensions"] = None  # Remove separate dimensions field
                    product_list.append(product_data)
                    logger.info(f"Collected listing data for product {idx + 1}/{len(cards)} on page {page}: {product_data['title']}")
                    idx += 1
                for product_data in product_list:
                    if len(self.scraped_data) >= self.min_products:
                        break
                    try:
                        detail_data = self.extract_detail_page(product_data["url"], product_data["title"])
                        product_data["description"] = detail_data["description"]
                        product_data["videos"] = detail_data["videos"]
                        product_data["specifications"].update(detail_data["specifications"])
                        product_data["origin"] = detail_data["origin"]
                        if detail_data["images"]:
                            product_data["images"] = list(set((product_data["images"] or []) + detail_data["images"]))[:5]
                            if not product_data["image_url"] and product_data["images"]:
                                product_data["image_url"] = product_data["images"][0]
                        if product_data["title"] and product_data["url"]:
                            self.scraped_data.append(product_data)
                            logger.info(f"Scraped product on page {page}: {product_data['title']}")
                        else:
                            self.skipped_products.append({
                                "page": page,
                                "title": product_data.get("title", "Unknown"),
                                "reason": "Missing title or URL after detail page"
                            })
                    except Exception as e:
                        logger.error(f"Failed to extract detail page for {product_data['title']}: {e}")
                        self.skipped_products.append({
                            "page": page,
                            "title": product_data["title"],
                            "reason": f"Detail page error: {str(e)}"
                        })
                    self.driver.get(url)
                    self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    time.sleep(random.uniform(1, 2))
                try:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)
                    next_button = None
                    for selector in self.selectors["next_page"].split(", "):
                        try:
                            next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if next_button.is_displayed() and next_button.is_enabled():
                                break
                            next_button = None
                        except NoSuchElementException:
                            continue
                    if not next_button:
                        logger.info("Next page button not found or disabled, stopping pagination")
                        break
                    self.driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(random.uniform(3, 5))
                except Exception as e:
                    logger.info(f"Error finding next page button: {e}")
                    break
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Scraping error: {e}")
        finally:
            self.save_results()
            self.close()
        return self.scraped_data