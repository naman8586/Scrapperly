import re
import time
import json
import sys
import logging
import webbrowser
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(filename="amazon_scraper.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Supported fields for user selection
SUPPORTED_FIELDS = [
    'url', 'title', 'currency', 'exact_price', 'description', 'min_order',
    'supplier', 'feedback', 'image_url', 'images', 'videos', 'specifications',
    'website_name', 'discount_information', 'brand_name'
]

# Get command-line arguments
if len(sys.argv) != 5:
    print("Usage: python amazon.py <search_keyword> <page_count> <retries> <fields>")
    logging.error("Invalid arguments. Usage: python amazon.py <search_keyword> <page_count> <retries> <fields>")
    sys.exit(1)

search_keyword = sys.argv[1]
try:
    search_page = int(sys.argv[2])
    retries = int(sys.argv[3])
except ValueError:
    print("Error: page_count and retries must be integers")
    logging.error("page_count and retries must be integers")
    sys.exit(1)

# Parse fields (comma-separated)
fields = sys.argv[4].split(',')
# Always include 'url' and 'website_name' for context and deduplication
desired_fields = ['url', 'website_name'] + [f.strip() for f in fields if f.strip() in SUPPORTED_FIELDS]
# Validate fields
invalid_fields = [f for f in fields if f.strip() not in SUPPORTED_FIELDS]
if invalid_fields:
    print(f"Error: Invalid fields: {', '.join(invalid_fields)}. Supported fields: {', '.join(SUPPORTED_FIELDS)}")
    logging.error(f"Invalid fields: {', '.join(invalid_fields)}. Supported fields: {', '.join(SUPPORTED_FIELDS)}")
    sys.exit(1)

# Setup output file
output_file = f"products_{search_keyword.replace(' ', '_')}_amazon.json"

def initialize_driver():
    """Configure and return a Selenium WebDriver instance"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        return driver
    except Exception as e:
        print(f"Error initializing Chrome browser: {e}")
        logging.error(f"Error initializing Chrome browser: {e}")
        sys.exit(1)

def retry_extraction(func, attempts=3, delay=1, default=""):
    """Retries an extraction function up to 'attempts' times."""
    for i in range(attempts):
        try:
            result = func()
            if result:
                return result
        except Exception as e:
            logging.warning(f"Retry {i+1}/{attempts} failed: {e}")
            if i < attempts - 1:
                time.sleep(delay)
    return default

def clean_text(text):
    """Clean text by removing extra whitespace, newlines, control characters, and special Unicode characters."""
    if not text:
        return ""
    cleaned = re.sub(r'[\u2000-\u200F\u2028-\u202F]+', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'\[U\+[0-9A-Fa-f]+\]', '', cleaned)
    return cleaned.strip()

def filter_product_data(product_data):
    """Filter product data to include only desired fields."""
    filtered_data = {}
    for field in desired_fields:
        if field in product_data:
            filtered_data[field] = product_data[field]
    return filtered_data

def scrape_amazon_products():
    """Main scraping function"""
    browser = initialize_driver()
    scraped_products = {}
    try:
        for page in range(1, search_page + 1):
            for attempt in range(retries):
                try:
                    search_url = f"https://www.amazon.in/s?k={search_keyword.replace(' ', '+')}&page={page}"
                    print(f"Scraping page {page}, attempt {attempt + 1}/{retries}: {search_url}")
                    logging.info(f"Scraping page {page}, attempt {attempt + 1}/{retries}: {search_url}")
                    browser.get(search_url)
                    WebDriverWait(browser, 10).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )

                    # Select product cards container
                    try:
                        product_cards_container = browser.find_element(By.XPATH, '//span[@data-component-type="s-search-results"]')
                    except Exception:
                        print(f"No product container found on page {page}")
                        logging.warning(f"No product container found on page {page}")
                        break

                    product_cards_html = BeautifulSoup(product_cards_container.get_attribute("outerHTML"), "html.parser")
                    product_cards = product_cards_html.find_all("div", {"role": "listitem"})
                    if not product_cards:
                        print(f"No product cards found on page {page}")
                        logging.warning(f"No product cards found on page {page}")
                        break

                    print(f"Found {len(product_cards)} products on page {page}")
                    for index, product in enumerate(product_cards, 1):
                        product_json_data = {
                            "url": "",
                            "title": "",
                            "currency": "",
                            "exact_price": "",
                            "description": "",
                            "min_order": "1 unit",
                            "supplier": "",
                            "feedback": {"rating": "", "review": ""},
                            "image_url": "",
                            "images": [],
                            "videos": [],
                            "specifications": {},
                            "website_name": "Amazon",
                            "discount_information": "",
                            "brand_name": ""
                        }

                        # Extract product URL
                        if 'url' in desired_fields:
                            try:
                                product_link = retry_extraction(
                                    lambda: product.find("a", {"class": "a-link-normal s-line-clamp-2 s-link-style a-text-normal"})["href"]
                                )
                                if product_link:
                                    product_url = product_link if product_link.startswith("https://www.amazon.in") else f"https://www.amazon.in{product_link}"
                                    product_json_data["url"] = product_url
                                    print(f"Product {index} URL: {product_url}")
                                    logging.info(f"Product {index} URL: {product_url}")
                            except Exception as e:
                                print(f"Error extracting product URL: {e}")
                                logging.warning(f"Error extracting product URL: {e}")
                                continue

                        # Avoid duplicates
                        if product_json_data["url"] in scraped_products:
                            print(f"Skipping duplicate product: {product_json_data['url']}")
                            logging.info(f"Skipping duplicate product: {product_json_data['url']}")
                            continue

                        # Extract product title
                        if 'title' in desired_fields:
                            try:
                                title_elem = retry_extraction(
                                    lambda: product.find("a", {"class": "a-link-normal s-line-clamp-2 s-link-style a-text-normal"})
                                )
                                if title_elem:
                                    product_json_data["title"] = clean_text(title_elem.get_text(strip=True))
                                    print(f"Product title: {product_json_data['title']}")
                                    logging.info(f"Product title: {product_json_data['title']}")
                            except Exception as e:
                                print(f"Error extracting product title: {e}")
                                logging.warning(f"Error extracting product title: {e}")

                        # Extract product currency
                        if 'currency' in desired_fields:
                            try:
                                product_currency_element = retry_extraction(
                                    lambda: product.find("span", {"class": "a-price-symbol"})
                                )
                                if product_currency_element:
                                    product_json_data["currency"] = clean_text(product_currency_element.get_text(strip=True))
                                    print(f"Product currency: {product_json_data['currency']}")
                                    logging.info(f"Product currency: {product_json_data['currency']}")
                            except Exception as e:
                                print(f"Error extracting product currency: {e}")
                                logging.warning(f"Error extracting product currency: {e}")

                        # Extract product price
                        if 'exact_price' in desired_fields:
                            try:
                                product_price_element = retry_extraction(
                                    lambda: product.find("span", {"class": "a-price-whole"})
                                )
                                if product_price_element:
                                    product_json_data["exact_price"] = clean_text(product_price_element.get_text(strip=True)).replace(",", "")
                                    print(f"Product exact_price: {product_json_data['exact_price']}")
                                    logging.info(f"Product exact_price: {product_json_data['exact_price']}")
                            except Exception as e:
                                print(f"Error extracting product price: {e}")
                                logging.warning(f"Error extracting product price: {e}")

                        # Open product page for additional details
                        if product_json_data["url"] and any(field in desired_fields for field in [
                            'description', 'supplier', 'feedback', 'image_url', 'images', 'videos',
                            'specifications', 'discount_information', 'brand_name'
                        ]):
                            try:
                                browser.get(product_json_data["url"])
                                WebDriverWait(browser, 10).until(
                                    lambda d: d.execute_script("return document.readyState") == "complete"
                                )
                                product_page_html = BeautifulSoup(browser.page_source, "html.parser")

                                # Extract description
                                if 'description' in desired_fields:
                                    try:
                                        description_elements = retry_extraction(
                                            lambda: product_page_html.find("div", {"id": "feature-bullets"}).find_all("li", {"class": "a-spacing-mini"}),
                                            default=[]
                                        )
                                        if description_elements:
                                            description = " ".join([clean_text(elem.get_text(strip=True)) for elem in description_elements])
                                            product_json_data["description"] = description
                                            print(f"Description: {description[:100]}...")
                                            logging.info(f"Description: {description[:100]}...")
                                        else:
                                            container = retry_extraction(
                                                lambda: product_page_html.find("ul", {"class": "a-unordered-list a-vertical a-spacing-small"})
                                            )
                                            if container:
                                                description = " ".join([clean_text(li.get_text(strip=True)) for li in container.find_all("li")])
                                                product_json_data["description"] = description
                                                print(f"Description (fallback): {description[:100]}...")
                                                logging.info(f"Description (fallback): {description[:100]}...")
                                    except Exception as e:
                                        print(f"Error extracting description: {e}")
                                        logging.warning(f"Error extracting description: {e}")

                                # Extract discount information
                                if 'discount_information' in desired_fields:
                                    try:
                                        discount_elem = retry_extraction(
                                            lambda: product_page_html.select_one("span.savingsPercentage")
                                        )
                                        if discount_elem:
                                            product_json_data["discount_information"] = clean_text(discount_elem.get_text(strip=True))
                                            print(f"Discount: {product_json_data['discount_information']}")
                                            logging.info(f"Discount: {product_json_data['discount_information']}")
                                        else:
                                            mrp_element = retry_extraction(
                                                lambda: product_page_html.select_one("span.a-price.a-text-price span.a-offscreen")
                                            )
                                            if mrp_element and product_json_data["exact_price"]:
                                                mrp_text = clean_text(mrp_element.get_text(strip=True))
                                                mrp_value = re.sub(r'[^\d.]', '', mrp_text)
                                                current_price = re.sub(r'[^\d.]', '', product_json_data["exact_price"])
                                                if mrp_value and current_price:
                                                    mrp_value = float(mrp_value)
                                                    current_price = float(current_price)
                                                    if mrp_value > current_price:
                                                        discount_percentage = ((mrp_value - current_price) / mrp_value) * 100
                                                        product_json_data["discount_information"] = f"{discount_percentage:.2f}% off"
                                                        print(f"Calculated discount: {product_json_data['discount_information']}")
                                                        logging.info(f"Calculated discount: {product_json_data['discount_information']}")
                                    except Exception as e:
                                        print(f"Error extracting discount: {e}")
                                        logging.warning(f"Error extracting discount: {e}")

                                # Extract specifications
                                if 'specifications' in desired_fields:
                                    try:
                                        product_details = {}
                                        detail_lists = product_page_html.select("ul.detail-bullet-list > li")
                                        for li in detail_lists:
                                            label_tag = li.select_one("span.a-text-bold")
                                            value_tag = label_tag.find_next_sibling("span") if label_tag else None
                                            if label_tag and value_tag:
                                                label = clean_text(label_tag.get_text(strip=True).replace(":", ""))
                                                value = clean_text(value_tag.get_text(" ", strip=True))
                                                if label and value:
                                                    product_details[label] = value
                                        if not product_details:
                                            details_table = product_page_html.select_one("table#productDetails_detailBullets_sections1")
                                            if details_table:
                                                for row in details_table.find_all("tr"):
                                                    label = row.find("th", {"class": "a-color-secondary a-size-base prodDetSectionEntry"})
                                                    value = row.find("td", {"class": "a-size-base prodDetAttrValue"})
                                                    if label and value:
                                                        label_text = clean_text(label.get_text(strip=True).replace(":", ""))
                                                        value_text = clean_text(value.get_text(" ", strip=True))
                                                        if label_text and value_text:
                                                            product_details[label_text] = value_text
                                        tech_specs_table = product_page_html.find("table", {"class": "aplus-tech-spec-table"})
                                        if tech_specs_table:
                                            for row in tech_specs_table.find_all("tr"):
                                                cells = row.find_all("td")
                                                if len(cells) == 2:
                                                    key = clean_text(cells[0].get_text(strip=True))
                                                    value = clean_text(cells[1].get_text(strip=True))
                                                    if key and value:
                                                        product_details[key] = value
                                        product_json_data["specifications"] = product_details
                                        print(f"Specifications: {product_details}")
                                        logging.info(f"Specifications: {product_details}")
                                    except Exception as e:
                                        print(f"Error extracting specifications: {e}")
                                        logging.warning(f"Error extracting specifications: {e}")

                                # Extract product reviews
                                if 'feedback' in desired_fields:
                                    try:
                                        product_review_element = retry_extraction(
                                            lambda: product_page_html.find("span", {"id": "acrCustomerReviewText"})
                                        )
                                        if product_review_element:
                                            product_review_text = clean_text(product_review_element.get_text(strip=True))
                                            numeric_match = re.search(r"(\d+)", product_review_text)
                                            if numeric_match:
                                                product_json_data["feedback"]["review"] = numeric_match.group(1)
                                                print(f"Reviews: {product_json_data['feedback']['review']}")
                                                logging.info(f"Reviews: {product_json_data['feedback']['review']}")
                                    except Exception as e:
                                        print(f"Error extracting product reviews: {e}")
                                        logging.warning(f"Error extracting product reviews: {e}")

                                # Extract product rating
                                if 'feedback' in desired_fields:
                                    try:
                                        product_rating_element = retry_extraction(
                                            lambda: product_page_html.find(
                                                lambda tag: tag.name == "span" and tag.get("id") == "acrPopover" and "reviewCountTextLinkedHistogram" in tag.get("class", []) and tag.has_attr("title")
                                            )
                                        )
                                        if product_rating_element:
                                            rating_span = product_rating_element.find("span", {"class": "a-size-base a-color-base"})
                                            if rating_span:
                                                product_json_data["feedback"]["rating"] = clean_text(rating_span.get_text(strip=True))
                                                print(f"Rating: {product_json_data['feedback']['rating']}")
                                                logging.info(f"Rating: {product_json_data['feedback']['rating']}")
                                    except Exception as e:
                                        print(f"Error extracting product rating: {e}")
                                        logging.warning(f"Error extracting product rating: {e}")

                                # Extract product supplier
                                if 'supplier' in desired_fields:
                                    try:
                                        product_supplier_element = product_page_html.find("a", {"id": "sellerProfileTriggerId"})
                                        if not product_supplier_element:
                                            product_supplier_element = product_page_html.find("span", {"class": "tabular-buybox-text"})
                                        if product_supplier_element:
                                            product_json_data["supplier"] = clean_text(product_supplier_element.get_text(strip=True))
                                            print(f"Supplier: {product_json_data['supplier']}")
                                            logging.info(f"Supplier: {product_json_data['supplier']}")
                                    except Exception as e:
                                        print(f"Error extracting product supplier: {e}")
                                        logging.warning(f"Error extracting product supplier: {e}")

                                # Extract product images
                                if 'image_url' in desired_fields or 'images' in desired_fields:
                                    try:
                                        altImages = WebDriverWait(browser, 5).until(
                                            EC.presence_of_element_located((By.ID, "altImages"))
                                        )
                                        imgButtons = altImages.find_elements(By.CSS_SELECTOR, "li.imageThumbnail")
                                        image_urls = set()
                                        for imgButton in imgButtons:
                                            WebDriverWait(browser, 2).until(EC.element_to_be_clickable(imgButton))
                                            imgButton.click()
                                            product_image_wrapper = WebDriverWait(browser, 2).until(
                                                EC.presence_of_element_located((By.CSS_SELECTOR, "ul.a-unordered-list.a-nostyle.a-horizontal.list.maintain-height"))
                                            )
                                            product_image_list = product_image_wrapper.find_element(By.CSS_SELECTOR, "li.selected")
                                            product_image = product_image_list.find_element(By.CSS_SELECTOR, "img.a-dynamic-image")
                                            image_url = product_image.get_attribute('src')
                                            if image_url:
                                                image_urls.add(image_url)
                                        product_json_data["images"] = list(image_urls)
                                        if product_json_data["images"] and 'image_url' in desired_fields:
                                            product_json_data["image_url"] = product_json_data["images"][0]
                                        print(f"Images: {product_json_data['images']}")
                                        print(f"Image URL: {product_json_data['image_url']}")
                                        logging.info(f"Images: {product_json_data['images']}")
                                        logging.info(f"Image URL: {product_json_data['image_url']}")
                                    except Exception as e:
                                        print(f"Error extracting product images: {e}")
                                        logging.warning(f"Error extracting product images: {e}")

                                # Extract brand name
                                if 'brand_name' in desired_fields:
                                    try:
                                        brand_elem = product_page_html.find("a", {"id": "bylineInfo"})
                                        if brand_elem:
                                            product_json_data["brand_name"] = clean_text(brand_elem.get_text(strip=True))
                                            print(f"Brand: {product_json_data['brand_name']}")
                                            logging.info(f"Brand: {product_json_data['brand_name']}")
                                        else:
                                            title = product_json_data.get("title", "").lower()
                                            if "louis vuitton" in title:
                                                product_json_data["brand_name"] = "Louis Vuitton"
                                                print("Brand from title: Louis Vuitton")
                                                logging.info("Brand from title: Louis Vuitton")
                                    except Exception as e:
                                        print(f"Error extracting brand name: {e}")
                                        logging.warning(f"Error extracting brand name: {e}")

                            except Exception as e:
                                print(f"Error processing product page {product_json_data['url']}: {e}")
                                logging.error(f"Error processing product page {product_json_data['url']}: {e}")

                        # Filter and save product
                        filtered_product = filter_product_data(product_json_data)
                        scraped_products[product_json_data["url"]] = filtered_product
                        print(f"✅ Product {index} scraped successfully")

                except Exception as e:
                    print(f"Attempt {attempt + 1}/{retries}: Error scraping page {page}: {e}")
                    logging.error(f"Attempt {attempt + 1}/{retries}: Error scraping page {page}: {e}")
                    time.sleep(5)
                else:
                    break
            else:
                print(f"Failed to scrape page {page} after {retries} attempts")
                logging.error(f"Failed to scrape page {page} after {retries} attempts")

        # Save to JSON
        try:
            print(f"Total products scraped: {len(scraped_products)}")
            logging.info(f"Total products scraped: {len(scraped_products)}")
            if not scraped_products:
                print("No products scraped. JSON file will not be created.")
                logging.warning("No products scraped. JSON file will not be created.")
                return
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(list(scraped_products.values()), f, ensure_ascii=False, indent=4)
            print(f"Scraping completed and saved to {output_file}")
            logging.info(f"Scraping completed and saved to {output_file}")
        except Exception as e:
            print(f"Error saving JSON file: {e}")
            logging.error(f"Error saving JSON file: {e}")

    finally:
        try:
            browser.quit()
        except Exception as e:
            print(f"Error closing browser: {e}")
            logging.error(f"Error closing browser: {e}")

if __name__ == "__main__":
    try:
        scrape_amazon_products()
    except Exception as e:
        print(f"Script terminated with error: {e}")
        logging.error(f"Script terminated with error: {e}")
        webbrowser.quit()