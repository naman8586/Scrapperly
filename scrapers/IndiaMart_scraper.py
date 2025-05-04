import time
import json
import re
import logging
import random
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, WebDriverException
from bs4 import BeautifulSoup

# Enhanced logging setup
log_folder = Path("logs")
log_folder.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
logging.basicConfig(
    filename=f"logs/scraper_{timestamp}.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(console_handler)

class IndiaMartScraper:
    def __init__(self, search_keyword, max_pages=10):
        self.search_keyword = search_keyword
        self.max_pages = max_pages
        self.retries = 3
        self.max_scroll_attempts = 5
        self.scraped_data = []
        self.skipped_products = []
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36"
        ]
        self.browser = self._setup_browser()

    def _setup_browser(self):
        """Configure and return a Selenium WebDriver instance"""
        options = webdriver.ChromeOptions()
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--start-maximized")
        options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        try:
            driver = webdriver.Chrome(options=options)
            return driver
        except WebDriverException as e:
            logging.error(f"Failed to initialize WebDriver: {e}")
            raise

    def rotate_user_agent(self):
        """Change the user agent to avoid detection"""
        try:
            user_agent = random.choice(self.user_agents)
            self.browser.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": user_agent
            })
            logging.info(f"Rotated user agent to: {user_agent}")
        except Exception as e:
            logging.warning(f"Failed to rotate user agent: {e}")

    def clean_title(self, title):
        """Clean up malformed titles by removing duplicates, redundant brands, and normalizing."""
        if not title:
            return None
        title = re.sub(r'<[^>]+>', '', title)
        title = re.sub(r'[^\w\s,()&-]', '', title)
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
        common_brands = ["rolex", "omega", "tag heuer", "cartier", "patek philippe", "audemars piguet", "tissot", "seiko", "citizen"]
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
            if not skip and word_lower not in ["watch", "timepiece", "used"]:
                cleaned_words.append(word)
        cleaned_title = " ".join(cleaned_words).strip()
        if self.search_keyword.lower() not in cleaned_title.lower():
            cleaned_title += f" {self.search_keyword.capitalize()}"
        if len(cleaned_title) > 100:
            cleaned_title = cleaned_title[:97] + "..."
        return cleaned_title

    def extract_price(self, card_soup, title):
        """Extract currency and exact price from card."""
        try:
            price_selectors = [
                "p.price", "div.price", "span.price", "p[class*='price']",
                "div[class*='price']", "span[class*='price']", "*[class*='price']"
            ]
            for selector in price_selectors:
                if price_el := card_soup.select_one(selector):
                    raw_price = price_el.get_text(strip=True)
                    if "Ask Price" in raw_price or "Call" in raw_price:
                        return {"currency": None, "exact_price": "Ask Price"}
                    currency = None
                    currency_symbols = ["₹", "$", "€", "¥", "£", "Rs"]
                    for symbol in currency_symbols:
                        if symbol in raw_price:
                            currency = symbol
                            break
                    if not currency and "rs" in raw_price.lower():
                        currency = "₹"
                    price_pattern = r'[\d,]+(?:\.\d+)?'
                    price_matches = re.findall(price_pattern, raw_price)
                    price_values = [re.sub(r'[^\d.]', '', p) for p in price_matches]
                    if len(price_values) >= 1:
                        return {"currency": currency, "exact_price": price_values[0]}
                    break
            logging.warning(f"No price element found for {title}")
            return {"currency": None, "exact_price": None}
        except Exception as e:
            logging.error(f"Error extracting price for {title}: {e}")
            return {"currency": None, "exact_price": None}

    def extract_images(self, card_soup, card_elem, title):
        """Extract image_url, images, and dimensions from card."""
        try:
            img_selectors = [
                "img[class*='product-img']", "img[class*='image']",
                "img[src*='product']", "img[src]", "img"
            ]
            images = []
            image_url = None
            dimensions = None
            for selector in img_selectors:
                img_elements = card_soup.select(selector)
                if not img_elements:
                    continue
                for idx, img in enumerate(img_elements):
                    src = img.get("src", "")
                    data_src = img.get("data-src", "")
                    if not src or src.endswith(('placeholder.png', 'default.jpg', 'noimage.jpg')):
                        if data_src and not data_src.endswith(('placeholder.png', 'default.jpg', 'noimage.jpg')):
                            src = data_src
                        else:
                            continue
                    if src and not src.startswith('data:'):
                        if idx == 0:
                            image_url = src
                            width = height = "Unknown"
                            try:
                                img_elem = card_elem.find_element(By.CSS_SELECTOR, selector)
                                width = self.browser.execute_script("return arguments[0].naturalWidth", img_elem) or img.get("width", "Unknown")
                                height = self.browser.execute_script("return arguments[0].naturalHeight", img_elem) or img.get("height", "Unknown")
                                dimensions = f"{width}x{height}"
                            except Exception as e:
                                logging.debug(f"Error getting image dimensions for {title}: {e}")
                                dimensions = f"{img.get('width', 'Unknown')}x{img.get('height', 'Unknown')}"
                        images.append(src)
                if images:
                    break
            if images:
                logging.info(f"Found {len(images)} images for {title}")
                return {"image_url": image_url, "images": images, "dimensions": dimensions}
            else:
                logging.warning(f"No images found for {title}")
                return {"image_url": None, "images": None, "dimensions": None}
        except Exception as e:
            logging.error(f"Error extracting images for {title}: {e}")
            return {"image_url": None, "images": None, "dimensions": None}

    def extract_description(self, card_soup, title):
        """Extract product description."""
        try:
            desc_selectors = ["div.description", "p.description", "div.prod-desc"]
            for selector in desc_selectors:
                if desc := card_soup.select_one(selector):
                    return desc.get_text(strip=True)
            return None
        except Exception as e:
            logging.error(f"Error extracting description for {title}: {e}")
            return None

    def extract_min_order(self, card_soup, title):
        """Extract minimum order quantity and unit."""
        try:
            min_order_selectors = ["span.unit", "div.moq", "*[class*='moq']", "*[class*='min-order']"]
            for selector in min_order_selectors:
                if min_order_el := card_soup.select_one(selector):
                    text = min_order_el.get_text(strip=True)
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
            logging.error(f"Error extracting min order for {title}: {e}")
            return None

    def extract_supplier(self, card_soup, title):
        """Extract supplier name."""
        try:
            name_selectors = ["div.companyname a", "div.companyname", "p.company-name", "*[class*='company']"]
            for selector in name_selectors:
                if elem := card_soup.select_one(selector):
                    return elem.get_text(strip=True)
            return None
        except Exception as e:
            logging.error(f"Error extracting supplier for {title}: {e}")
            return None

    def extract_origin(self, card_soup, title):
        """Extract product origin."""
        try:
            if origin_el := card_soup.find("span", {"class": "origin"}):
                return origin_el.get_text(strip=True)
            return None
        except Exception as e:
            logging.error(f"Error extracting origin for {title}: {e}")
            return None

    def extract_feedback(self, card_soup, title):
        """Extract rating and review count."""
        feedback = {"rating": None, "review": None}
        try:
            rating_selectors = ["div.rating", "span.rating", "*[class*='rating']"]
            review_selectors = ["span:contains('(')", "span.reviews", "*[class*='review']"]
            for selector in rating_selectors:
                if rating_el := card_soup.select_one(selector):
                    rating_text = rating_el.get_text(strip=True)
                    rating_match = re.search(r'([\d.]+)', rating_text)
                    if rating_match:
                        feedback["rating"] = rating_match.group(1)
                        break
            for selector in review_selectors:
                if review_el := card_soup.select(selector):
                    for el in review_el:
                        review_text = el.get_text(strip=True)
                        review_match = re.search(r'\((\d+)\)', review_text)
                        if review_match:
                            feedback["review"] = review_match.group(1)
                            break
            return feedback
        except Exception as e:
            logging.error(f"Error extracting feedback for {title}: {e}")
            return {"rating": None, "review": None}

    def extract_brand(self, title):
        """Extract brand from title."""
        try:
            title_text = title.lower()
            common_brands = [
                "rolex", "omega", "tag heuer", "cartier", "patek philippe",
                "audemars piguet", "tissot", "seiko", "citizen"
            ]
            for brand in common_brands:
                if re.search(r'\b' + brand + r'\b', title_text):
                    return brand.capitalize()
            return None
        except Exception as e:
            logging.error(f"Error extracting brand: {e}")
            return None

    def extract_discount(self, card_soup, title):
        """Extract discount information."""
        try:
            if discount_el := card_soup.find("span", {"class": "discount"}):
                return discount_el.get_text(strip=True)
            return None
        except Exception as e:
            logging.error(f"Error extracting discount for {title}: {e}")
            return None

    def extract_videos(self, card_soup, title):
        """Extract video URLs."""
        try:
            videos = []
            if video_el := card_soup.find("video"):
                if src := video_el.get("src"):
                    videos.append(src)
            return videos if videos else None
        except Exception as e:
            logging.error(f"Error extracting videos for {title}: {e}")
            return None

    def scrape_products(self):
        """Main scraping function"""
        try:
            for page in range(1, self.max_pages + 1):
                url = f"https://dir.indiamart.com/search.mp?ss={self.search_keyword.replace(' ', '+')}&page={page}"
                logging.info(f"Scraping page {page}/{self.max_pages}: {url}")
                for attempt in range(self.retries):
                    try:
                        self.rotate_user_agent()
                        self.browser.get(url)
                        WebDriverWait(self.browser, 20).until(
                            lambda d: d.execute_script("return document.readyState") == "complete"
                        )
                        WebDriverWait(self.browser, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.card"))
                        )
                        previous_product_count = 0
                        scroll_attempts = 0
                        while scroll_attempts < self.max_scroll_attempts:
                            cards = self.browser.find_elements(By.CSS_SELECTOR, "div.card")
                            current_count = len(cards)
                            logging.info(f"Scroll attempt {scroll_attempts + 1}: Found {current_count} products")
                            if current_count == previous_product_count:
                                break
                            previous_product_count = current_count
                            self.browser.execute_script(
                                "window.scrollTo(0, Math.min(document.body.scrollHeight, window.scrollY + 800));"
                            )
                            time.sleep(random.uniform(1, 2))
                            scroll_attempts += 1
                        cards = self.browser.find_elements(By.CSS_SELECTOR, "div.card")
                        if not cards:
                            logging.error("No products found on page. Saving page source for debugging.")
                            with open(f"debug_page_{page}.html", "w", encoding="utf-8") as f:
                                f.write(self.browser.page_source)
                            break
                        logging.info(f"Found {len(cards)} product cards on page {page}")
                        for card_idx, card_elem in enumerate(cards):
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
                                "website_name": "IndiaMart",
                                "discount_information": None,
                                "brand_name": None
                            }
                            try:
                                card_html = card_elem.get_attribute("outerHTML")
                                card_soup = BeautifulSoup(card_html, "html.parser")
                            except StaleElementReferenceException:
                                logging.warning(f"Stale element for card {card_idx}. Skipping.")
                                self.skipped_products.append({"card_idx": card_idx, "reason": "Stale element"})
                                continue
                            except Exception as e:
                                logging.error(f"Error retrieving card HTML for card {card_idx}: {e}")
                                self.skipped_products.append({"card_idx": card_idx, "reason": f"HTML retrieval error: {str(e)}"})
                                continue
                            if prod_name := card_soup.find("div", {"class": "producttitle"}):
                                raw_title = prod_name.get_text(strip=True)
                                product_data["title"] = self.clean_title(raw_title)
                                if self.search_keyword.lower() not in product_data["title"].lower():
                                    logging.info(f"Skipping non-matching product: {product_data['title']}")
                                    self.skipped_products.append({
                                        "title": product_data["title"],
                                        "reason": f"Does not match search keyword: {self.search_keyword}"
                                    })
                                    continue
                            else:
                                logging.warning(f"No title found for card {card_idx}")
                                self.skipped_products.append({"card_idx": card_idx, "reason": "No title"})
                                continue
                            if prod_url_el := card_soup.find("div", {"class": "titleAskPriceImageNavigation"}):
                                if a_tag := prod_url_el.find("a"):
                                    product_data["url"] = a_tag.get("href", None)
                            if not product_data["url"]:
                                for url_selector in ["a.product-title", "a.cardlinks", "a[href]"]:
                                    if a_tag := card_soup.select_one(url_selector):
                                        href = a_tag.get("href", None)
                                        if href and ("indiamart.com" in href or href.startswith("/")):
                                            product_data["url"] = href
                                            break
                            if not product_data["url"]:
                                logging.warning(f"No URL found for {product_data['title']}")
                                self.skipped_products.append({
                                    "title": product_data["title"],
                                    "reason": "No URL"
                                })
                                continue
                            if product_data["url"].startswith("/"):
                                product_data["url"] = f"https://www.indiamart.com{product_data['url']}"
                            # Clean URL by removing query parameters
                            if product_data["url"] and "?" in product_data["url"]:
                                product_data["url"] = product_data["url"].split("?")[0]
                            price_data = self.extract_price(card_soup, product_data["title"])
                            product_data.update(price_data)
                            product_data["description"] = self.extract_description(card_soup, product_data["title"])
                            product_data["min_order"] = self.extract_min_order(card_soup, product_data["title"])
                            product_data["supplier"] = self.extract_supplier(card_soup, product_data["title"])
                            product_data["origin"] = self.extract_origin(card_soup, product_data["title"])
                            product_data["feedback"] = self.extract_feedback(card_soup, product_data["title"])
                            product_data["brand_name"] = self.extract_brand(product_data["title"])
                            product_data["discount_information"] = self.extract_discount(card_soup, product_data["title"])
                            product_data["videos"] = self.extract_videos(card_soup, product_data["title"])
                            image_data = self.extract_images(card_soup, card_elem, product_data["title"])
                            product_data.update(image_data)
                            if product_data["title"] and product_data["url"]:
                                self.scraped_data.append(product_data)
                                logging.info(f"Successfully scraped product: {product_data['title']}")
                            else:
                                self.skipped_products.append({
                                    "title": product_data.get("title", "Unknown"),
                                    "reason": "Missing title or URL"
                                })
                        break
                    except TimeoutException:
                        logging.error(f"Timeout on page {page}, attempt {attempt + 1}")
                        time.sleep(5 * (attempt + 1))
                    except Exception as e:
                        logging.error(f"Attempt {attempt + 1} failed for page {page}: {e}")
                        time.sleep(5 * (attempt + 1))
                time.sleep(random.uniform(2, 5))
        except KeyboardInterrupt:
            logging.info("Script interrupted by user")
        except Exception as e:
            logging.error(f"Unexpected error during scraping: {e}")
        finally:
            try:
                self.browser.quit()
            except Exception as e:
                logging.warning(f"Error closing browser: {e}")
        return self.scraped_data

    def save_results(self):
        """Save scraped data and statistics to files"""
        output_folder = Path("data")
        output_folder.mkdir(exist_ok=True)
        try:
            output_file = output_folder / f"{self.search_keyword.replace(' ', '_')}_products_{timestamp}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(self.scraped_data, f, ensure_ascii=False, indent=2)
            logging.info(f"Data saved to {output_file}")
            if self.skipped_products:
                skipped_file = output_folder / f"{self.search_keyword.replace(' ', '_')}_skipped_{timestamp}.json"
                with open(skipped_file, "w", encoding="utf-8") as f:
                    json.dump(self.skipped_products, f, indent=2)
                logging.info(f"Skipped products data saved to {skipped_file}")
            return str(output_file)
        except Exception as e:
            logging.error(f"Error saving data: {e}")
            return None

def main():
    """Main function to run the scraper"""
    try:
        search_keyword = input("Enter search keyword (default: watch): ") or "watch"
        try:
            max_pages = int(input("Enter number of pages to scrape (default: 10): ") or "10")
        except ValueError:
            max_pages = 10
            print("Invalid input. Using default: 10 pages")
        print(f"\nStarting IndiaMART scraper for '{search_keyword}'")
        print(f"Scraping {max_pages} pages in visible mode")
        scraper = IndiaMartScraper(search_keyword, max_pages)
        products = scraper.scrape_products()
        output_file = scraper.save_results()
        print("\n===== SCRAPING SUMMARY =====")
        print(f"Total products scraped: {len(products)}")
        print(f"Skipped products: {len(scraper.skipped_products)}")
        if output_file:
            print(f"Results saved to: {output_file}")
        else:
            print("Failed to save results.")
    except Exception as e:
        logging.error(f"Error in main function: {e}")
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()