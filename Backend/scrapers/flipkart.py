import re
import time
import json
import sys
import logging
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging to a file and console for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('flipkart_scraper.log'),
        logging.StreamHandler()  # Also log to console for immediate feedback
    ]
)

# Supported fields for user selection
SUPPORTED_FIELDS = [
    'url', 'title', 'currency', 'exact_price', 'description', 'min_order',
    'supplier', 'feedback', 'image_url', 'images', 'videos', 'specifications',
    'website_name', 'discount_information'
]

# Get command-line arguments
logging.info(f"Received command-line arguments: {sys.argv}")
if len(sys.argv) != 5:
    error_msg = "Usage: python flipkart.py <search_keyword> <page_count> <retries> <fields>"
    logging.error(error_msg)
    print(json.dumps({
        "status": "error",
        "message": error_msg
    }))
    sys.exit(1)

search_keyword = sys.argv[1]
try:
    search_page = int(sys.argv[2])
    retries = int(sys.argv[3])
except ValueError:
    error_msg = "Error: page_count and retries must be integers"
    logging.error(error_msg)
    print(json.dumps({
        "status": "error",
        "message": error_msg
    }))
    sys.exit(1)

# Parse fields (comma-separated)
fields = sys.argv[4].split(',')
# Always include 'url' and 'website_name' for context and deduplication
desired_fields = list(set(['url', 'website_name'] + [f.strip() for f in fields if f.strip() in SUPPORTED_FIELDS]))
# Validate fields
invalid_fields = [f for f in fields if f.strip() not in SUPPORTED_FIELDS]
if invalid_fields:
    error_msg = f"Error: Invalid fields: {', '.join(invalid_fields)}. Supported fields: {', '.join(SUPPORTED_FIELDS)}"
    logging.error(error_msg)
    print(json.dumps({
        "status": "error",
        "message": error_msg
    }))
    sys.exit(1)

# Setup output file
output_file = f"products_{search_keyword.replace(' ', '_')}_flipkart.json"
logging.info(f"Output file will be saved as: {output_file}")

def selenium_config():
    """Configure and return a Selenium WebDriver instance."""
    logging.info("Initializing Selenium WebDriver")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")
    
    # Fallback for Chrome binary if not found
    try:
        browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        browser.maximize_window()
        logging.info("Chrome WebDriver initialized successfully")
        return browser
    except WebDriverException as e:
        logging.error(f"Primary WebDriver initialization failed: {str(e)}")
        # Try specifying Chrome binary location (common issue on Windows)
        try:
            options.binary_location = "C:/Program Files/Google/Chrome/Application/chrome.exe"
            browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            browser.maximize_window()
            logging.info("WebDriver initialized with specified Chrome binary")
            return browser
        except WebDriverException as e2:
            error_msg = f"Error initializing Chrome browser: {str(e2)}"
            logging.error(error_msg)
            print(json.dumps({
                "status": "error",
                "message": error_msg
            }))
            sys.exit(1)

def retry_extraction(func, attempts=3, delay=2, default="N/A"):
    """Retries an extraction function up to 'attempts' times."""
    for i in range(attempts):
        try:
            result = func()
            if result:
                return result
        except Exception as e:
            logging.warning(f"Retry {i+1}/{attempts} failed: {str(e)}")
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

def detect_captcha(browser):
    """Detect CAPTCHA by checking for common CAPTCHA elements or redirects."""
    try:
        page_source = browser.page_source.lower()
        captcha_indicators = ['captcha', 'verify you are not a robot', 'recaptcha', 'please verify']
        if any(indicator in page_source for indicator in captcha_indicators):
            logging.warning("CAPTCHA detected in page source")
            return True
        soup = BeautifulSoup(page_source, 'html.parser')
        if soup.find('div', class_='g-recaptcha') or soup.find('form', id='challenge-form'):
            logging.warning("CAPTCHA element found in HTML")
            return True
        if 'captcha' in browser.current_url.lower():
            logging.warning("CAPTCHA detected in URL")
            return True
        return False
    except Exception as e:
        logging.error(f"Error detecting CAPTCHA: {str(e)}")
        return False

def scrape_flipkart_products(browser):
    """Main scraping function."""
    logging.info("Starting Flipkart scraping")
    scraped_products = {}
    messages = []  # Collect messages for final output

    for page in range(1, search_page + 1):
        for attempt in range(retries):
            try:
                search_url = f"https://www.flipkart.com/search?q={search_keyword.replace(' ', '+')}&page={page}"
                logging.info(f"Scraping page {page}, attempt {attempt + 1}/{retries}: {search_url}")
                browser.get(search_url)
                WebDriverWait(browser, 15).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )

                # Check for CAPTCHA
                if detect_captcha(browser):
                    message = f"CAPTCHA detected on page {page}"
                    logging.warning(message)
                    messages.append(message)
                    time.sleep(5)
                    continue

                # Scroll to ensure all products load
                browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)  # Wait for lazy-loaded content

                # Try multiple product card selectors
                product_cards_selectors = [
                    'div._2kHMtA',  # Grid layout
                    'div.tUxRFH',  # List layout
                    'div._1AtVbE',  # Container
                    'div[data-id]',  # Fallback
                ]
                product_cards = None
                for selector in product_cards_selectors:
                    try:
                        product_cards = WebDriverWait(browser, 10).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                        )
                        if product_cards:
                            logging.info(f"Found product cards with selector: {selector}")
                            break
                    except TimeoutException:
                        logging.info(f"Selector {selector} failed")
                        continue

                if not product_cards:
                    message = f"No products found on page {page}"
                    logging.warning(message)
                    messages.append(message)
                    break

                logging.info(f"Found {len(product_cards)} products on page {page}")
                for index, product_card in enumerate(product_cards):
                    product_json_data = {
                        "url": "N/A",
                        "title": "N/A",
                        "currency": "N/A",
                        "exact_price": "N/A",
                        "description": "N/A",
                        "min_order": "1 unit",
                        "supplier": "N/A",
                        "feedback": {"rating": "N/A", "review": "N/A"},
                        "image_url": "N/A",
                        "images": [],
                        "videos": [],
                        "specifications": {},
                        "website_name": "Flipkart",
                        "discount_information": "N/A"
                    }

                    # Extract product URL
                    if 'url' in desired_fields:
                        try:
                            product_url_tag = product_card.find_element(By.CSS_SELECTOR, "a[href*='flipkart.com']")
                            product_json_data["url"] = product_url_tag.get_attribute("href")
                            logging.info(f"Product {index + 1} URL: {product_json_data['url']}")
                        except Exception as e:
                            logging.error(f"Error extracting URL for product {index + 1}: {str(e)}")

                    # Skip duplicates
                    if product_json_data["url"] in scraped_products or product_json_data["url"] == "N/A":
                        continue

                    # Extract fields from search page
                    if any(field in desired_fields for field in ['title', 'exact_price', 'currency', 'image_url']):
                        try:
                            # Title
                            if 'title' in desired_fields:
                                product_json_data["title"] = retry_extraction(
                                    lambda: product_card.find_element(By.CSS_SELECTOR, "div._4rR01T, div.KzDlHZ, a.wjcEIp").text.strip()
                                )
                                logging.info(f"Title: {product_json_data['title']}")

                            # Price and currency
                            if 'currency' in desired_fields or 'exact_price' in desired_fields:
                                price_text = retry_extraction(
                                    lambda: product_card.find_element(By.CSS_SELECTOR, "div._30jeq3, div.Nx9bqj").text.strip()
                                )
                                match = re.match(r'([^0-9]+)([0-9,]+)', price_text)
                                if match:
                                    product_json_data["currency"] = match.group(1).strip()
                                    product_json_data["exact_price"] = match.group(2).replace(",", "")
                                logging.info(f"Price: {product_json_data['exact_price']}, Currency: {product_json_data['currency']}")

                            # Primary image
                            if 'image_url' in desired_fields:
                                product_json_data["image_url"] = retry_extraction(
                                    lambda: product_card.find_element(By.CSS_SELECTOR, "img._396cs4, img.DByuf4").get_attribute("src")
                                )
                                logging.info(f"Primary Image: {product_json_data['image_url']}")
                        except Exception as e:
                            logging.error(f"Error extracting search page data for product {index + 1}: {str(e)}")

                    # Open product page for detailed fields
                    if product_json_data["url"] != "N/A" and any(field in desired_fields for field in [
                        'description', 'supplier', 'feedback', 'images', 'videos', 'specifications', 'discount_information'
                    ]):
                        try:
                            logging.info(f"Navigating to product page: {product_json_data['url']}")
                            browser.get(product_json_data["url"])
                            WebDriverWait(browser, 15).until(
                                lambda d: d.execute_script("return document.readyState") == "complete"
                            )
                            browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(2)  # Wait for lazy-loaded content
                            product_page_html = BeautifulSoup(browser.page_source, "html.parser")

                            # Check for CAPTCHA
                            if detect_captcha(browser):
                                message = f"CAPTCHA detected on product page: {product_json_data['url']}"
                                logging.warning(message)
                                messages.append(message)
                                continue

                            # Product description
                            if 'description' in desired_fields:
                                product_json_data["description"] = retry_extraction(
                                    lambda: product_page_html.select_one("div._1mXcCf, div.yN_+oW p").get_text(strip=True)
                                )
                                logging.info(f"Description: {product_json_data['description'][:100]}...")

                            # Supplier (seller info)
                            if 'supplier' in desired_fields:
                                product_json_data["supplier"] = retry_extraction(
                                    lambda: browser.find_element(By.CSS_SELECTOR, "div._2VRS5M, div.cvCpHS").text.strip()
                                )
                                logging.info(f"Supplier: {product_json_data['supplier']}")

                            # Feedback (rating and reviews)
                            if 'feedback' in desired_fields:
                                product_json_data["feedback"]["rating"] = retry_extraction(
                                    lambda: browser.find_element(By.CSS_SELECTOR, "div._3LWZlK, div.XQDdHH").text.strip()
                                )
                                product_json_data["feedback"]["review"] = retry_extraction(
                                    lambda: browser.find_element(By.CSS_SELECTOR, "span._2_R_DZ, span.Wphh3N").text.strip()
                                )
                                logging.info(f"Rating: {product_json_data['feedback']['rating']}, Reviews: {product_json_data['feedback']['review']}")

                            # Discount information
                            if 'discount_information' in desired_fields:
                                product_json_data["discount_information"] = retry_extraction(
                                    lambda: browser.find_element(By.CSS_SELECTOR, "div._3Ay6Sb, div.UkUFwK").text.strip()
                                )
                                logging.info(f"Discount: {product_json_data['discount_information']}")

                            # Images
                            if 'images' in desired_fields:
                                try:
                                    images = product_page_html.select("div._2r_T1I img, div.qOPjUY img")
                                    for img in images:
                                        src = img.get("src", "")
                                        if src and src not in product_json_data["images"]:
                                            product_json_data["images"].append(src)
                                    if product_json_data["images"] and 'image_url' in desired_fields:
                                        product_json_data["image_url"] = product_json_data["images"][0]
                                    logging.info(f"Images: {product_json_data['images']}")
                                except Exception as e:
                                    logging.error(f"Error extracting images: {str(e)}")

                            # Specifications
                            if 'specifications' in desired_fields:
                                try:
                                    # Click "Product Details" if present
                                    try:
                                        product_details = WebDriverWait(browser, 5).until(
                                            EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Product Details')]"))
                                        )
                                        browser.execute_script("arguments[0].scrollIntoView(true);", product_details)
                                        browser.execute_script("arguments[0].click();", product_details)
                                        logging.info("Clicked 'Product Details'")
                                        time.sleep(1)
                                    except TimeoutException:
                                        logging.info("No 'Product Details' button found")

                                    # Click "Read More" if present
                                    try:
                                        read_more = WebDriverWait(browser, 5).until(
                                            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Read More')]"))
                                        )
                                        browser.execute_script("arguments[0].scrollIntoView(true);", read_more)
                                        browser.execute_script("arguments[0].click();", read_more)
                                        logging.info("Clicked 'Read More'")
                                        time.sleep(1)
                                    except TimeoutException:
                                        logging.info("No 'Read More' button found")

                                    # Extract specifications
                                    table = WebDriverWait(browser, 10).until(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, "div._1UhVsV, div.GNDEQ-"))
                                    )
                                    soup = BeautifulSoup(table.get_attribute("innerHTML"), "html.parser")
                                    rows = soup.select("div.WJdYP6, li._7eSDEz")
                                    product_json_data["specifications"] = {}
                                    for row in rows:
                                        try:
                                            label = row.select_one("div.col-3-12, td._0vPCLL").get_text(strip=True)
                                            value = row.select_one("div.col-9-12, td.BGjvC- li").get_text(strip=True)
                                            if label and value:
                                                product_json_data["specifications"][label] = value
                                                logging.info(f"Specification: {label}: {value}")
                                        except Exception:
                                            continue
                                except Exception as e:
                                    logging.error(f"Error extracting specifications: {str(e)}")

                        except Exception as e:
                            logging.error(f"Error processing product page {product_json_data['url']}: {str(e)}")
                            messages.append(f"Error processing product {index + 1} on page {page}")

                    # Filter and store product data
                    filtered_product = filter_product_data(product_json_data)
                    scraped_products[product_json_data["url"]] = filtered_product
                    logging.info(f"Product {index + 1} scraped successfully")

                break  # Exit retry loop on success
            except Exception as e:
                logging.error(f"Attempt {attempt + 1}/{retries}: Error scraping page {page}: {str(e)}")
                time.sleep(5)
                if attempt == retries - 1:
                    message = f"Failed to scrape page {page} after {retries} attempts"
                    logging.warning(message)
                    messages.append(message)
                    break

    # Save to JSON and return result
    try:
        result = {
            "status": "completed",
            "products": list(scraped_products.values())
        }
        if messages:
            result["messages"] = messages
        if not scraped_products:
            message = "No products were scraped across all pages"
            logging.info(message)
            result["messages"] = result.get("messages", []) + [message]

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result["products"], f, ensure_ascii=False, indent=4)
        logging.info(f"Scraping completed and saved to {output_file}. Total products: {len(scraped_products)}")
        print(json.dumps(result))
        return True
    except Exception as e:
        logging.error(f"Error saving JSON file: {str(e)}")
        print(json.dumps({
            "status": "error",
            "message": f"Error saving JSON file: {str(e)}"
        }))
        return False

if __name__ == "__main__":
    logging.info("Starting main execution")
    browser = None
    try:
        browser = selenium_config()
        scrape_flipkart_products(browser)
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        print(json.dumps({
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }))
        sys.exit(1)
    finally:
        if browser:
            try:
                browser.quit()
                logging.info("Browser closed successfully")
            except Exception as e:
                logging.error(f"Error closing browser: {str(e)}")