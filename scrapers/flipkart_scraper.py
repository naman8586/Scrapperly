import re
import time
import json
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Global scraping configurations
retries = 3
search_page = 3  # Number of pages to scrape
search_keyword = "rolex watches"  # Change to "iphone" or other keyword as needed
output_file = os.path.expanduser("~/Desktop/flipkart_products.json")

# Setup Selenium configurations
def selenium_config():
    options = webdriver.ChromeOptions()
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-blink-features=AutomationControlled")  # Avoid bot detection
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")
    # options.add_argument("--headless=new")  # Uncomment for headless mode
    browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    browser.maximize_window()
    return browser

def retry_extraction(func, attempts=3, delay=2, default="N/A"):
    """
    Retries an extraction function up to 'attempts' times.
    Returns the result if successful, otherwise returns 'default'.
    """
    for i in range(attempts):
        try:
            result = func()
            if result:
                return result
        except Exception as e:
            if i < attempts - 1:
                time.sleep(delay)
    return default

def scrape_flipkart_products(browser):
    scraped_products = {}
    for page in range(1, search_page + 1):
        for attempt in range(retries):
            try:
                search_url = f"https://www.flipkart.com/search?q={search_keyword}&page={page}"
                print(f"Scraping page {page}, attempt {attempt + 1}/{retries}: {search_url}")
                browser.get(search_url)
                WebDriverWait(browser, 15).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                time.sleep(3)  # Allow dynamic content to load

                # Check for CAPTCHA
                if "captcha" in browser.current_url.lower() or "verify" in browser.page_source.lower():
                    print("CAPTCHA detected. Please solve it manually and press Enter to continue...")
                    input()
                    browser.get(search_url)
                    WebDriverWait(browser, 15).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                    time.sleep(3)

                # Try multiple product card selectors
                product_cards_selectors = ["div.tUxRFH", "div._1sdMkc.LFEi7Z"]
                product_cards = None
                for selector in product_cards_selectors:
                    try:
                        product_cards = WebDriverWait(browser, 10).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                        )
                        if product_cards:
                            break
                    except TimeoutException:
                        continue

                if not product_cards:
                    print(f"No products found on page {page}")
                    break

                print(f"Found {len(product_cards)} products on page {page}")
                for index, product_card in enumerate(product_cards):
                    product_json_data = {
                        "url": "N/A",
                        "title": "N/A",
                        "currency": "N/A",
                        "exact_price": "N/A",
                        "description": "N/A",
                        "min_order": "1 unit",
                        "supplier": "N/A",
                        "origin": "N/A",
                        "feedback": {"rating": "N/A", "review": "N/A"},
                        "image_url": "N/A",
                        "images": [],
                        "videos": [],
                        "specifications": {},
                        "website_name": "Flipkart",
                        "discount_information": "N/A",
                        "brand_name": "N/A"
                    }

                    # Extract product URL
                    try:
                        product_url_tag = product_card.find_element(By.TAG_NAME, "a")
                        product_json_data["url"] = product_url_tag.get_attribute("href")
                    except Exception as e:
                        print(f"Error extracting URL for product {index + 1}: {e}")

                    # Skip duplicates
                    if product_json_data["url"] in scraped_products:
                        continue

                    # Open product page
                    if product_json_data["url"] != "N/A":
                        try:
                            browser.execute_script("window.open('');")
                            browser.switch_to.window(browser.window_handles[-1])
                            browser.get(product_json_data["url"])
                            WebDriverWait(browser, 15).until(
                                lambda d: d.execute_script("return document.readyState") == "complete"
                            )
                            time.sleep(2)
                            product_page_html = BeautifulSoup(browser.page_source, "html.parser")

                            # Product title
                            product_json_data["title"] = retry_extraction(
                                lambda: browser.find_element(By.CSS_SELECTOR, "span.VU-ZEz").text.strip()
                            )
                            print(f"Title: {product_json_data['title']}")

                            # Product price and currency
                            product_json_data["exact_price"] = retry_extraction(
                                lambda: browser.find_element(By.CSS_SELECTOR, "div.Nx9bqj.CxhGGd").text.strip()
                            )
                            match = re.match(r'([^0-9]+)([0-9,]+)', product_json_data["exact_price"])
                            if match:
                                product_json_data["currency"] = match.group(1)
                                product_json_data["exact_price"] = match.group(2).replace(",", "")
                            print(f"Exact Price: {product_json_data['exact_price']}, Currency: {product_json_data['currency']}")

                            # Product description
                            product_json_data["description"] = retry_extraction(
                                lambda: " ".join([e.text.strip() for e in browser.find_elements(By.CSS_SELECTOR, "span.VU-ZEz") if e.text.strip()])
                            )
                            print(f"Description: {product_json_data['description'][:100]}...")

                            # Supplier (seller info)
                            product_json_data["supplier"] = retry_extraction(
                                lambda: browser.find_element(By.CSS_SELECTOR, "div.cvCpHS").text.strip()
                            )
                            print(f"Supplier: {product_json_data['supplier']}")

                            # Feedback (rating and reviews)
                            product_json_data["feedback"]["rating"] = retry_extraction(
                                lambda: browser.find_element(By.CSS_SELECTOR, "div.XQDdHH._1Quie7").text.split()[0]
                            )
                            product_json_data["feedback"]["review"] = retry_extraction(
                                lambda: browser.find_element(By.CSS_SELECTOR, "span.Wphh3N span").text.strip()
                            )
                            print(f"Rating: {product_json_data['feedback']['rating']}, Reviews: {product_json_data['feedback']['review']}")

                            # Brand name
                            product_json_data["brand_name"] = retry_extraction(
                                lambda: browser.find_element(By.CSS_SELECTOR, "span.mEh187").text.strip()
                            )
                            print(f"Brand Name: {product_json_data['brand_name']}")

                            # Discount information
                            product_json_data["discount_information"] = retry_extraction(
                                lambda: browser.find_element(By.CSS_SELECTOR, "div.UkUFwK.WW8yVX.dB67CR").text.strip()
                            )
                            print(f"Discount: {product_json_data['discount_information']}")

                            # Product images and primary image
                            try:
                                images_elem = WebDriverWait(browser, 10).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.qOPjUY"))
                                )
                                img_buttons = images_elem.find_elements(By.CSS_SELECTOR, "li.YGoYIP")
                                for i, img_button in enumerate(img_buttons):
                                    try:
                                        browser.execute_script("arguments[0].scrollIntoView(true);", img_button)
                                        img_button.click()
                                        time.sleep(1)
                                        wrapper = images_elem.find_element(By.CSS_SELECTOR, "div.vU5WPQ")
                                        img_tag = wrapper.find_element(By.TAG_NAME, "img")
                                        image_url = img_tag.get_attribute("src")
                                        if i == 0:  # First image is primary
                                            product_json_data["image_url"] = image_url
                                        if image_url not in product_json_data["images"]:
                                            product_json_data["images"].append(image_url)
                                            print(f"Image {'(primary)' if i == 0 else ''}: {image_url}")
                                    except Exception:
                                        continue
                            except Exception as e:
                                print(f"Error extracting images: {e}")

                            # Specifications (all fields from the table)
                            try:
                                # Click the div to reveal product details
                                try:
                                    product_details = WebDriverWait(browser, 5).until(
                                        EC.element_to_be_clickable((By.CSS_SELECTOR, "div.col.col-1-12.cWwIYq"))
                                    )
                                    browser.execute_script("arguments[0].scrollIntoView(true);", product_details)
                                    browser.execute_script("arguments[0].click();", product_details)
                                    time.sleep(1)
                                    print("Clicked Product Details section (cWwIYq)")
                                except Exception as e:
                                    print(f"Product Details section (cWwIYq) not clickable or not found: {e}")

                                # Click "Read More" button
                                try:
                                    read_more = WebDriverWait(browser, 5).until(
                                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.QqFHMw.n4gy8q"))
                                    )
                                    browser.execute_script("arguments[0].scrollIntoView(true);", read_more)
                                    browser.execute_script("arguments[0].click();", read_more)
                                    time.sleep(2)  # Allow content to load after clicking
                                    print("Clicked Read More button")
                                except Exception as e:
                                    print(f"Read More button not found or not clickable: {e}")

                                # Extract specification table
                                table = WebDriverWait(browser, 10).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.Cnl9Jt"))
                                )
                                rows = table.find_elements(By.CLASS_NAME, "row")
                                print(f"Found {len(rows)} specification rows")
                                for row in rows:
                                    try:
                                        label = row.find_element(By.CSS_SELECTOR, "div.col.col-3-12._9NUIO9").text.strip()
                                        value = row.find_element(By.CSS_SELECTOR, "div.col.col-9-12.-gXFvC").text.strip()
                                        if label:  # Only add non-empty labels
                                            product_json_data["specifications"][label] = value
                                            print(f"Specification: {label}: {value}")
                                    except Exception:
                                        continue

                                # Extract additional description if available
                                try:
                                    extra_desc = retry_extraction(
                                        lambda: table.find_element(By.CSS_SELECTOR, "div._4aGEkW").text.strip()
                                    )
                                    if extra_desc != "N/A":
                                        product_json_data["specifications"]["Additional Description"] = extra_desc
                                        print(f"Additional Description: {extra_desc}")
                                except Exception:
                                    pass

                            except Exception as e:
                                print(f"Error extracting specifications: {e}")

                        except Exception as e:
                            print(f"Error processing product page {product_json_data['url']}: {e}")
                        finally:
                            if len(browser.window_handles) > 1:
                                try:
                                    browser.close()
                                    browser.switch_to.window(browser.window_handles[0])
                                except Exception as e:
                                    print(f"Error switching windows: {e}")

                    scraped_products[product_json_data["url"]] = product_json_data
                    print(f"✅ Product {index + 1} scraped successfully")

                break  # Successful page scrape
            except Exception as e:
                print(f"Attempt {attempt + 1}/{retries}: Error scraping page {page}: {e}")
                time.sleep(2)
        else:
            print(f"Failed to scrape page {page} after {retries} attempts.")

    # Save to JSON
    try:
        print(f"Total products scraped: {len(scraped_products)}")
        if not scraped_products:
            print("No products scraped. JSON file will not be created.")
            return False

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(list(scraped_products.values()), f, ensure_ascii=False, indent=4)
        print(f"Scraping completed and saved to {output_file}")
        return True
    except Exception as e:
        print(f"Error saving JSON file: {e}")
        return False

if __name__ == "__main__":
    browser = None
    try:
        browser = selenium_config()
        retry_extraction(lambda: scrape_flipkart_products(browser))
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        if browser:
            try:
                browser.quit()
            except Exception as e:
                print(f"Error closing browser: {e}")