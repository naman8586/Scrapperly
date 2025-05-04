import re
import time
import json
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from lxml import html

# Global scraping configurations
retries = 3
search_page = 1  # Adjust to desired number of pages
search_keyword = "Rolex watches"

# Setup Selenium configurations for Chrome
def initialize_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--log-level=3")
    # Comment out headless mode for debugging; uncomment for production
    # options.add_argument("--headless")
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        print("Chrome WebDriver initialized successfully.")
        return driver
    except WebDriverException as e:
        print(f"Error initializing Chrome WebDriver: {e}")
        print("Ensure ChromeDriver is installed and matches your Chrome version.")
        print("Download from https://chromedriver.chromium.org/downloads")
        exit(1)
    except Exception as e:
        print(f"Unexpected error initializing Chrome WebDriver: {e}")
        exit(1)

browser = initialize_driver()

def retry_extraction(func, attempts=3, delay=1, default=""):
    """
    Helper function that retries an extraction function up to 'attempts' times.
    Returns the result if successful, otherwise returns 'default'.
    """
    for i in range(attempts):
        try:
            result = func()
            if result:
                return result
        except Exception:
            time.sleep(delay)
    return default

def scroll_to_element(driver, css_selector):
    """
    Scroll to an element to ensure it's loaded in the DOM.
    """
    try:
        element = driver.find_element(By.CSS_SELECTOR, css_selector)
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(1)  # Wait for content to load
        return element
    except Exception as e:
        print(f"Error scrolling to element {css_selector}: {e}")
        return None

def scrape_ebay_products():
    scraped_products = {}  # Using URL as key to avoid duplicates
    output_file = os.path.join(os.path.dirname(__file__), "ebay_rolex_watches.json")

    try:
        for page in range(1, search_page + 1):
            for attempt in range(retries):
                try:
                    search_url = f'https://www.ebay.com/sch/i.html?_nkw={search_keyword}&_sacat=0&_from=R40&_pgn={page}'
                    browser.get(search_url)
                    WebDriverWait(browser, 10).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                    time.sleep(2)  # Allow dynamic content to load

                    # Select product cards container
                    try:
                        product_cards_container = browser.find_element(By.CSS_SELECTOR, 'ul.srp-results.srp-list, ul.srp-results.srp-grid')
                    except Exception:
                        print(f"No product container found on page {page}")
                        break

                    product_cards_html = BeautifulSoup(product_cards_container.get_attribute("outerHTML"), "html.parser")
                    product_cards = product_cards_html.find_all("div", {"class": "s-item__wrapper"})
                    if not product_cards:
                        print(f"No product cards found on page {page}")
                        break

                    for product in product_cards:
                        product_json_data = {
                            "url": "",
                            "title": "",
                            "currency": "",
                            "exact_price": "",
                            "description": "",
                            "min_order": "1 unit",
                            "supplier": "",
                            "feedback": {
                                "rating": "",
                                "review": ""
                            },
                            "image_url": "",
                            "images": [],
                            "videos": [],
                            "dimensions": "",
                            "website_name": "eBay.com",
                            "discount_information": "",
                            "brand_name": "",
                        }

                        # Extracting product url and title
                        try:
                            product_title_url_container = product.find("a", {"class": "s-item__link"})
                            if product_title_url_container:
                                product_title = retry_extraction(
                                    lambda: product_title_url_container.find("span", {"role": "heading"}).get_text(strip=True)
                                )
                                if product_title:
                                    product_json_data["title"] = product_title
                                product_url = product_title_url_container["href"]
                                if product_url:
                                    product_json_data["url"] = product_url.split('?')[0]
                                    print(f"Product URL: {product_json_data['url']}")
                        except Exception as e:
                            print(f"Error extracting product title and url: {e}")
                            continue

                        # Avoid duplicate products by URL
                        if product_json_data["url"] in scraped_products:
                            continue

                        # Extracting currency and exact price from search page
                        try:
                            price_element = retry_extraction(
                                lambda: product.find("span", {"class": "s-item__price"}).get_text(strip=True),
                                attempts=3,
                                delay=1,
                                default=""
                            )
                            if price_element:
                                # Extract currency and price using regex
                                currency_match = re.match(r"([A-Z\s$]+)", price_element.strip())
                                price_match = re.search(r'\d+(?:,\d+)?(?:\.\d+)?', price_element)
                                
                                if currency_match:
                                    product_json_data["currency"] = currency_match.group(0).strip()
                                    print(f"Currency: {product_json_data['currency']}")
                                else:
                                    product_json_data["currency"] = ""
                                    print("No currency found.")
                                
                                if price_match:
                                    exact_price = price_match.group(0).replace(",", "")
                                    product_json_data["exact_price"] = exact_price
                                    print(f"Exact price: {exact_price}")
                                else:
                                    product_json_data["exact_price"] = ""
                                    print("No price found.")
                            else:
                                product_json_data["currency"] = ""
                                product_json_data["exact_price"] = ""
                                print("Price element not found.")
                        except Exception as e:
                            print(f"Error extracting currency and price: {e}")
                            product_json_data["currency"] = ""
                            product_json_data["exact_price"] = ""

                        # Extracting product origin
                        try:
                            product_origin_text = product.find("span", {"class": "s-item__location"}).get_text(strip=True)
                            if product_origin_text and product_origin_text.startswith("from "):
                                product_json_data["origin"] = product_origin_text[5:].strip()
                                print(f"Origin: {product_json_data['origin']}")
                        except Exception as e:
                            print(f"Error extracting product origin: {e}")

                        # Open product page to extract additional details
                        if product_json_data["url"]:
                            try:
                                browser.execute_script("window.open('');")
                                browser.switch_to.window(browser.window_handles[-1])
                                browser.get(product_json_data["url"])
                                WebDriverWait(browser, 10).until(
                                    lambda d: d.execute_script("return document.readyState") == "complete"
                                )
                                time.sleep(2)

                                # Scroll to specification table for dimensions
                                scroll_to_element(browser, 'div.ux-layout-section-evo')

                                # Refresh page HTML after scrolling
                                product_page_html = BeautifulSoup(browser.page_source, "html.parser")

                                # Re-extract currency and exact price from product page (more reliable)
                                try:
                                    price_element = retry_extraction(
                                        lambda: product_page_html.find("div", {"class": "x-price-primary"}).find("span", {"class": "ux-textspans"}).get_text(strip=True),
                                        attempts=3,
                                        delay=1,
                                        default=""
                                    )
                                    if price_element:
                                        currency_match = re.match(r"([A-Z\s$]+)", price_element.strip())
                                        price_match = re.search(r'\d+(?:,\d+)?(?:\.\d+)?', price_element)
                                        
                                        if currency_match:
                                            product_json_data["currency"] = currency_match.group(0).strip()
                                            print(f"Currency (product page): {product_json_data['currency']}")
                                        else:
                                            print("No currency found on product page.")
                                        
                                        if price_match:
                                            exact_price = price_match.group(0).replace(",", "")
                                            product_json_data["exact_price"] = exact_price
                                            print(f"Exact price (product page): {exact_price}")
                                        else:
                                            print("No price found on product page.")
                                    else:
                                        print("Price element not found on product page.")
                                except Exception as e:
                                    print(f"Error extracting currency and price from product page: {e}")

                                # Extracting description
                                try:
                                    description_container = product_page_html.find("div", {"id": "viTabs_0_is"})
                                    if description_container:
                                        description = description_container.get_text(strip=True)
                                        product_json_data["description"] = description
                                        print(f"Description: {description[:100]}...")
                                except Exception as e:
                                    print(f"Error extracting description: {e}")

                               # Extracting supplier details
                                try:
                                    # Primary method: Find <a> within x-sellercard-atf__info__about-seller with href matching eBay store pattern
                                    supplier_name_element = retry_extraction(
                                        lambda: product_page_html.find("div", {"class": "x-sellercard-atf__info__about-seller"})
                                            .find("a", href=re.compile(r'https://www\.ebay\.com/str/'))
                                            .find("span", {"class": "ux-textspans ux-textspans--BOLD"}).get_text(strip=True),
                                        attempts=3,
                                        delay=1,
                                        default=""
                                    )
                                    # Fallback: Extract from data-clientpresentationmetadata attribute
                                    if not supplier_name_element:
                                        supplier_name_element = retry_extraction(
                                            lambda: next(
                                                (json.loads(a.get("data-clientpresentationmetadata")).get("_ssn", "")
                                                 for a in product_page_html.find_all("a", href=re.compile(r'https://www\.ebay\.com/str/'))
                                                 if a.get("data-clientpresentationmetadata") and json.loads(a.get("data-clientpresentationmetadata")).get("_ssn")),
                                                ""
                                            ),
                                            attempts=3,
                                            delay=1,
                                            default=""
                                        )
                                    if supplier_name_element:
                                        product_json_data["supplier"] = supplier_name_element
                                        print(f"Supplier: {supplier_name_element}")
                                    else:
                                        print("No supplier name found.")
                                except Exception as e:
                                    print(f"Error extracting supplier name: {e}")

                                # Extracting feedback details
                                try:
                                    feedback_container = product_page_html.find("div", {"class": "ux-seller-card"})
                                    if feedback_container:
                                        review_text = retry_extraction(
                                            lambda: feedback_container.find("span", {"class": "SECONDARY"}).get_text(strip=True),
                                            attempts=3,
                                            delay=1,
                                            default=""
                                        )
                                        review_match = re.search(r'\((\d+(?:,\d+)*)\)', review_text)
                                        if review_match:
                                            product_json_data["feedback"]["review"] = review_match.group(1).replace(",", "")
                                        positive_feedback = retry_extraction(
                                            lambda: feedback_container.find("span", {"class": "ux-textspans ux-textspans--PSEUDOLINK"}).get_text(strip=True),
                                            attempts=3,
                                            delay=1,
                                            default=""
                                        )
                                        feedback_match = re.search(r"(\d+(?:\.\d+)?)%", positive_feedback)
                                        if feedback_match:
                                            positive_feedback = float(feedback_match.group(1))
                                            rating = round(1 + 4 * (positive_feedback / 100), 1)
                                            product_json_data["feedback"]["rating"] = str(rating)
                                            print(f"Rating: {rating}, Reviews: {product_json_data['feedback']['review']}")
                                        else:
                                            print("No positive feedback percentage found.")
                                    else:
                                        print("No feedback container found.")
                                except Exception as e:
                                    print(f"Error extracting feedback: {e}")

                                # Extracting primary image URL and additional images
                                try:
                                    product_json_data["image_url"] = ""
                                    product_json_data["images"] = []
                                    carousel_items = product_page_html.find_all("div", {"class": "ux-image-carousel-item"})
                                    image_urls = set()
                                    for item in carousel_items:
                                        img_tag = item.find("img")
                                        if img_tag:
                                            src = retry_extraction(lambda: img_tag.get("src"), attempts=3, delay=1, default="")
                                            if src:
                                                image_urls.add(src)
                                            zoom_src = retry_extraction(lambda: img_tag.get("data-zoom-src"), attempts=3, delay=1, default="")
                                            if zoom_src:
                                                image_urls.add(zoom_src)
                                            srcset = retry_extraction(lambda: img_tag.get("srcset"), attempts=3, delay=1, default="")
                                            if srcset:
                                                srcset_urls = [url.split(" ")[0] for url in srcset.split(",") if url.strip()]
                                                image_urls.update(srcset_urls)
                                    image_urls = sorted(list(image_urls), key=lambda x: int(re.search(r's-l(\d+)', x).group(1)) if re.search(r's-l(\d+)', x) else 0, reverse=True)
                                    if image_urls:
                                        product_json_data["image_url"] = image_urls[0]
                                        product_json_data["images"] = image_urls
                                        print(f"Primary image URL: {product_json_data['image_url']}")
                                        for i, url in enumerate(product_json_data["images"], 1):
                                            print(f"Image {i}: {url}")
                                    else:
                                        print("No images found.")
                                except Exception as e:
                                    print(f"Error extracting images: {e}")

                                # Extracting dimensions with scrolling
                                try:
                                    dim_regex = r'\b(?:About\s*)?\d+(\.\d+)?\s*(cm|in|inches|centimeters|mm)\b|' + \
                                                r'\b\d+(\.\d+)?\s*\(\d+(\.\d+)?\s*(inch|in)\)'
                                    dimensions = []
                                    spec_table = product_page_html.find("div", {"class": "ux-layout-section-evo"})
                                    if spec_table:
                                        labels = spec_table.find_all("div", {"class": "ux-labels-values__labels"})
                                        for label in labels:
                                            label_text = label.get_text(strip=True).lower()
                                            if "case size" in label_text:
                                                value_container = label.find_parent().find_next_sibling("div", {"class": "ux-labels-values__values"})
                                                if value_container:
                                                    span = value_container.find("span", {"class": "ux-textspans"})
                                                    if span:
                                                        dim_text = retry_extraction(
                                                            lambda: span.get_text(strip=True),
                                                            attempts=3,
                                                            delay=1,
                                                            default=""
                                                        )
                                                        if dim_text:
                                                            matches = re.finditer(dim_regex, dim_text, re.IGNORECASE)
                                                            for match in matches:
                                                                dim_value = match.group(0)
                                                                dimensions.append({"context": f"{label_text}: {dim_text}", "dimension": dim_value})
                                                                print(f"Dimensions from specs: {dim_text} ({dim_value})")
                                    if dimensions:
                                        product_json_data["dimensions"] = "; ".join([f"{dim['context']} ({dim['dimension']})" for dim in dimensions])
                                        print(f"Dimensions: {product_json_data['dimensions']}")
                                    else:
                                        product_json_data["dimensions"] = ""
                                        print("No case size found.")
                                except Exception as e:
                                    print(f"Error extracting dimensions: {e}")

                                # Extracting discount information
                                try:
                                    original_price_elem = product_page_html.find("span", {"class": "ux-textspans--STRIKETHROUGH"})
                                    if original_price_elem:
                                        original_price = original_price_elem.get_text(strip=True)
                                        current_price = product_json_data.get("exact_price", "")
                                        if original_price and current_price:
                                            try:
                                                original_val = float(original_price.replace(product_json_data["currency"], "").replace(",", "").strip())
                                                current_val = float(current_price.replace(",", ""))
                                                if original_val > current_val:
                                                    discount_percentage = ((original_val - current_val) / original_val) * 100
                                                    product_json_data["discount_information"] = f"{discount_percentage:.2f}% off"
                                                    print(f"Discount: {product_json_data['discount_information']}")
                                            except ValueError as e:
                                                print(f"Error calculating discount: {e}")
                                    else:
                                        discount_elem = product_page_html.find("span", {"class": "ux-textspans ux-textspans--EMPHASIS"})
                                        if discount_elem:
                                            discount_text = discount_elem.get_text(strip=True).strip('()')
                                            product_json_data["discount_information"] = discount_text
                                            print(f"Discount: {product_json_data['discount_information']}")
                                except Exception as e:
                                    print(f"Error extracting discount information: {e}")

                                # Extracting brand name
                                try:
                                    brand_elem = product_page_html.find("div", {"class": "ux-labels-values__labels"}, string=re.compile("Brand", re.IGNORECASE))
                                    if brand_elem:
                                        brand_name = brand_elem.find_next_sibling("div", {"class": "ux-labels-values__values"}).find("span", {"class": "ux-textspans"}).get_text(strip=True)
                                        product_json_data["brand_name"] = brand_name
                                        print(f"Brand: {brand_name}")
                                    else:
                                        title = product_json_data.get("title", "").lower()
                                        if "rolex" in title:
                                            product_json_data["brand_name"] = "Rolex"
                                            print("Brand from title: Rolex")
                                except Exception as e:
                                    print(f"Error extracting brand name: {e}")

                            except Exception as e:
                                print(f"Error processing product page {product_json_data['url']}: {e}")
                            finally:
                                browser.close()
                                browser.switch_to.window(browser.window_handles[0])

                        # Save unique product
                        scraped_products[product_json_data["url"]] = product_json_data

                    break
                except Exception as e:
                    print(f"Attempt {attempt+1}/{retries}: Error scraping page {page}: {e}")
                    time.sleep(2)
            else:
                print(f"Failed to scrape page {page} after {retries} attempts.")

        # Save all unique scraped products to a JSON file
        try:
            print(f"Number of products scraped: {len(scraped_products)}")
            if not scraped_products:
                print("No products scraped. JSON file will not be created.")
                return

            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            print(f"Saving scraped products to: {output_file}")
            json_data = list(scraped_products.values())
            for attempt in range(3):
                try:
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(json_data, f, ensure_ascii=False, indent=4)
                        f.flush()
                    print(f"Scraping completed and saved to {output_file}")
                    break
                except (PermissionError, OSError) as e:
                    print(f"Attempt {attempt+1}/3: Failed to write file: {e}")
                    time.sleep(1)
            else:
                print(f"Failed to write file after 3 attempts.")

            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                print("JSON file verified: File exists and contains data.")
            else:
                print("Warning: JSON file is empty or was not created.")
        except Exception as e:
            print(f"Error saving JSON file: {e}")

    finally:
        try:
            browser.quit()
        except Exception as e:
            print(f"Error closing browser: {e}")

if __name__ == "__main__":
    scrape_ebay_products()