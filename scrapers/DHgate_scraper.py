import re
import time
import json
import os
import random
import uuid
from tqdm import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

retries = 2
search_page = 1
search_keyword = "Christian dior perfume"

output_file = os.path.join(os.path.dirname(__file__), "dhgate_rolex.json")
os.makedirs(os.path.dirname(output_file), exist_ok=True)
with open(output_file, "w", encoding="utf-8") as f:
    json.dump([], f)

options = webdriver.ChromeOptions()
options.add_argument("--ignore-certificate-errors")
options.add_argument("--log-level=3")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")
service = Service(ChromeDriverManager().install())
browser = webdriver.Chrome(service=service, options=options)
browser.maximize_window()

def retry_extraction(func, attempts=3, delay=1, default=""):
    for i in range(attempts):
        try:
            result = func()
            if result:
                return result
        except Exception:
            time.sleep(delay)
    return default

def scroll_to_element(driver, css_selector):
    try:
        element = driver.find_element(By.CSS_SELECTOR, css_selector)
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(random.uniform(0.5, 1))
        return element
    except Exception as e:
        print(f"Error scrolling to {css_selector}: {e}")
        return None

def clean_text(text):
    return ' '.join(text.strip().split()) if text else ''

def append_product_to_json(product):
    try:
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except Exception:
                    data = []
        else:
            data = []
        data.append(product)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error appending product to JSON file: {e}")

def extract_specifications(browser, product_page_html, product_json_data):
    try:
        if 'specifications' not in product_json_data:
            product_json_data['specifications'] = {}
        spec_regex = r'\b\d+(\.\d+)?\s*(?:x|X)\s*\d+(\.\d+)?\s*(?:x|X)\s*\d+(\.\d+)?\s*(cm|in|inches|centimeters|mm|kg|g)\b|' + \
                     r'\b\d+\s*-\s*\d+\s*(millimeters|mm|cm|in|inches|centimeters|kg|g)\b|' + \
                     r'\b\d+(\.\d+)?\s*(cm|in|inches|centimeters|mm|kg|g)\b|' + \
                     r'\b\d+\s*(UK|US|EU|CM)\b'
        specs_container = retry_extraction(
            lambda: product_page_html.find("div", {"class": "prodSpecifications_showLayer__15RQA"}),
            attempts=3, delay=1, default=None
        )
        if specs_container:
            specs_list = specs_container.find("ul", {"class": "prodSpecifications_showUl__fmY8y"})
            if specs_list:
                for li in specs_list.find_all("li"):
                    key_span = li.find("span")
                    value_div = li.find("div", {"class": "prodSpecifications_deswrap___Z092"})
                    if key_span and value_div:
                        key = clean_text(key_span.get_text(strip=True).replace(":", ""))
                        value = clean_text(value_div.get_text(strip=True))
                        if key and value:
                            if re.match(spec_regex, value, re.IGNORECASE) or key.lower() in ["dial diameter", "waterproof deepness", "band width", "band length"]:
                                product_json_data['specifications'][key] = value
                            else:
                                product_json_data['specifications'][key] = value
                print(f"Specifications (showLayer): {product_json_data['specifications']}")
        if not product_json_data['specifications']:
            scroll_to_element(browser, "table.product-spec")
            specs_table = retry_extraction(
                lambda: product_page_html.find("table", {"class": "product-spec"}),
                attempts=3, delay=1, default=None
            )
            if specs_table:
                for row in specs_table.find_all("tr"):
                    th = row.find("th")
                    td = row.find("td")
                    if th and td:
                        key = clean_text(th.get_text(strip=True))
                        value = clean_text(td.get_text(strip=True))
                        if key and value:
                            if re.match(spec_regex, value, re.IGNORECASE):
                                product_json_data['specifications'][key] = value
                            else:
                                product_json_data['specifications'][key] = value
                print(f"Specifications (table): {product_json_data['specifications']}")
        if not product_json_data['specifications']:
            description = product_json_data.get("description", "")
            spec_matches = re.findall(spec_regex, description, re.IGNORECASE)
            if spec_matches:
                for match in spec_matches:
                    spec_value = clean_text(match[0])
                    if spec_value:
                        product_json_data['specifications']['Dimensions'] = spec_value
                print(f"Specifications (description): {product_json_data['specifications']}")
        if not product_json_data['specifications']:
            print(f"No specifications found for product: {product_json_data['url']}")
            html_file = f"product_{product_json_data['url'].split('/')[-1]}_source_{uuid.uuid4().hex}.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(browser.page_source)
            print(f"Saved product page HTML to {html_file}")
    except Exception as e:
        print(f"Error extracting specifications: {e}")
        product_json_data['specifications'] = {}
    return product_json_data

def scrape_dhgate_products():
    scraped_products = {}
    for page in tqdm(range(search_page), desc="Scraping pages", unit="page"):
        for attempt in range(retries):
            try:
                search_url = f'https://www.dhgate.com/wholesale/search.do?act=search&searchkey={search_keyword}&pageNum={page+1}'
                browser.get(search_url)
                WebDriverWait(browser, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                time.sleep(random.uniform(2, 3))
                try:
                    captcha = browser.find_element(By.XPATH, '//form[contains(@action, "captcha")]')
                    print(f"CAPTCHA detected on page {page+1}! Please solve it manually.")
                    browser.save_screenshot(f"captcha_page_{page+1}_attempt_{attempt+1}.png")
                    break
                except NoSuchElementException:
                    print(f"No CAPTCHA detected on page {page+1}, proceeding...")
                browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1, 2))
                product_cards = WebDriverWait(browser, 10).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "gallery-main"))
                )
                if not product_cards:
                    print(f"No products found on page {page+1}")
                    browser.save_screenshot(f"no_products_page_{page+1}_attempt_{attempt+1}.png")
                    break
                for product in tqdm(product_cards, desc=f"Scraping products on page {page+1}", leave=False):
                    product_json_data = {
                        "url": "",
                        "title": "",
                        "currency": "",
                        "min_price": "",
                        "max_price": "",
                        "description": "",
                        "min_order":"1 unit",
                        "supplier": "",
                        "feedback": {"rating": "", "review": ""},
                        "image_url": "",
                        "images": [],
                        "videos": [],
                        "dimensions": "",
                        "specifications": {},
                        "website_name": "DHgate.com",
                        "discount_information": "",
                        "brand_name": ""
                    }
                    try:
                        product_html = BeautifulSoup(product.get_attribute('outerHTML'), "html.parser")
                    except Exception as e:
                        print(f"Error parsing product HTML: {e}")
                        continue
                    try:
                        title_div = retry_extraction(
                            lambda: product_html.find('div', {"class": "gallery-pro-name"}),
                            attempts=3, delay=1, default=None
                        )
                        if title_div:
                            a_tag = retry_extraction(
                                lambda: title_div.find("a"),
                                attempts=3, delay=1, default=None
                            )
                            if a_tag:
                                product_json_data["title"] = a_tag.get("title", "").strip()
                                product_url = a_tag.get("href", "").strip()
                                if product_url and not product_url.startswith("http"):
                                    product_url = f"https://www.dhgate.com{product_url}"
                                product_json_data["url"] = product_url
                                print(f"Product URL: {product_url}")
                    except Exception as e:
                        print(f"Error extracting product URL and title: {e}")
                    if product_json_data["url"] in scraped_products:
                        continue
                    try:
                        price_element = retry_extraction(
                            lambda: product.find_element(By.CSS_SELECTOR, "[class*='price'], .gallery-pro-price"),
                            attempts=3, delay=1, default=None
                        )
                        if price_element:
                            price_text = price_element.text.strip()
                            print(f"Extracted price text: '{price_text}'")
                            prices = []
                            for line in price_text.split('\n'):
                                match = re.match(r'Rs\.([\d,]+(?:\.[\d]+)?)\s*-\s*([\d,]+(?:\.[\d]+)?)', line)
                                if match:
                                    min_p = match.group(1).replace(',', '')
                                    max_p = match.group(2).replace(',', '')
                                    prices.extend([float(min_p), float(max_p)])
                            if prices:
                                product_json_data["currency"] = "$"
                                product_json_data["min_price"] = str(min(prices))
                                product_json_data["max_price"] = str(max(prices))
                                print(f"Currency: {product_json_data['currency']}")
                                print(f"Minimum Price: {product_json_data['min_price']}")
                                print(f"Maximum Price: {product_json_data['max_price']}")
                            else:
                                print(f"Price format not recognized: '{price_text}'")
                                product_json_data["currency"] = ""
                                product_json_data["min_price"] = ""
                                product_json_data["max_price"] = ""
                        else:
                            print(f"Price element not found for product: {product_json_data['url']}")
                            html_file = f"price_missing_{product_json_data['url'].split('/')[-1]}_source_{uuid.uuid4().hex}.html"
                            with open(html_file, "w", encoding="utf-8") as f:
                                f.write(product.get_attribute('outerHTML'))
                            print(f"Saved product HTML to {html_file}")
                            product_json_data["currency"] = ""
                            product_json_data["min_price"] = ""
                            product_json_data["max_price"] = ""
                    except Exception as e:
                        print(f"Error extracting price: {e}")
                        product_json_data["currency"] = ""
                        product_json_data["min_price"] = ""
                        product_json_data["max_price"] = ""
                    if product_json_data["url"]:
                        try:
                            browser.execute_script("window.open('');")
                            browser.switch_to.window(browser.window_handles[-1])
                            browser.get(product_json_data["url"])
                            WebDriverWait(browser, 10).until(
                                lambda d: d.execute_script("return document.readyState") == "complete"
                            )
                            time.sleep(random.uniform(1, 2))
                            browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(random.uniform(1, 2))
                            product_page_html = BeautifulSoup(browser.page_source, "html.parser")
                            try:
                                description_elements = retry_extraction(
                                    lambda: product_page_html.find("div", {"class": "product-description-detail"}).find_all("p"),
                                    attempts=3, delay=1, default=[]
                                )
                                if description_elements:
                                    description = " ".join([elem.get_text(strip=True) for elem in description_elements])
                                    product_json_data["description"] = description
                                    print(f"Description (product-description-detail): {description[:100]}...")
                                else:
                                    info_section = retry_extraction(
                                        lambda: product_page_html.find("div", {"class": "product-info"}),
                                        attempts=3, delay=1, default=None
                                    )
                                    if info_section:
                                        description = info_section.get_text(strip=True)
                                        product_json_data["description"] = description
                                        print(f"Description (product-info): {description[:100]}...")
                                    else:
                                        h1_title = retry_extraction(
                                            lambda: product_page_html.find("h1").get_text(strip=True),
                                            attempts=3, delay=1, default=""
                                        )
                                        if h1_title:
                                            product_json_data["description"] = h1_title
                                            print(f"Description (h1 title): {h1_title[:100]}...")
                            except Exception as e:
                                print(f"Error extracting description: {e}")
                            try:
                                review_text = retry_extraction(
                                    lambda: product_page_html.find("span", {"class": "productSellerMsg_reviewsCount__HJ3MJ"}).get_text(strip=True),
                                    attempts=3, delay=1, default=""
                                )
                                if review_text:
                                    review_match = re.search(r'\d+', review_text)
                                    if review_match:
                                        product_json_data["feedback"]["review"] = review_match.group(0)
                                        print(f"Review count: {product_json_data['feedback']['review']}")
                                else:
                                    alt_reviews = retry_extraction(
                                        lambda: product_page_html.find("span", {"class": "review-count"}).get_text(strip=True),
                                        attempts=3, delay=1, default=""
                                    )
                                    if alt_reviews:
                                        review_match = re.search(r'\d+', alt_reviews)
                                        if review_match:
                                            product_json_data["feedback"]["review"] = review_match.group(0)
                                            print(f"Review count (fallback): {product_json_data['feedback']['review']}")
                            except Exception as e:
                                print(f"Error extracting product reviews: {e}")
                            try:
                                rating = retry_extraction(
                                    lambda: product_page_html.find("div", {"class": "productSellerMsg_starWarp__WeIw2"}).find("span", string=re.compile(r'^\d+\.\d+$')),
                                    attempts=3, delay=1, default=""
                                )
                                if rating:
                                    product_json_data["feedback"]["rating"] = rating.get_text(strip=True)
                                    print(f"Rating: {product_json_data['feedback']['rating']}")
                                else:
                                    alt_rating = retry_extraction(
                                        lambda: product_page_html.find("span", {"class": "star-rating"}).get_text(strip=True),
                                        attempts=3, delay=1, default=""
                                    )
                                    if alt_rating and re.match(r'^\d+\.\d+$', alt_rating):
                                        product_json_data["feedback"]["rating"] = alt_rating
                                        print(f"Rating (fallback): {product_json_data['feedback']['rating']}")
                            except Exception as e:
                                print(f"Error extracting product rating: {e}")
                            try:
                                supplier_name = retry_extraction(
                                    lambda: product_page_html.find("a", {"class": "store-name"}).get_text(strip=True),
                                    attempts=3, delay=1, default=""
                                )
                                if supplier_name:
                                    product_json_data["supplier"] = supplier_name
                                    print(f"Supplier: {supplier_name}")
                                else:
                                    store_link = retry_extraction(
                                        lambda: product_page_html.find("a", href=re.compile(r'https://www\.dhgate\.com/store/')).get_text(strip=True),
                                        attempts=3, delay=1, default=""
                                    )
                                    if store_link:
                                        product_json_data["supplier"] = store_link
                                        print(f"Supplier (fallback from store link): {store_link}")
                            except Exception as e:
                                print(f"Error extracting product supplier: {e}")
                            try:
                                main_image_elem = retry_extraction(
                                    lambda: product_page_html.find("div", {"class": "masterMap_bigMapWarp__2Jzw2"}).find("img"),
                                    attempts=3, delay=1, default=None
                                )
                                if main_image_elem:
                                    main_image = main_image_elem.get("data-zoom-image") or main_image_elem.get("src", "")
                                    if main_image and not main_image.startswith("http"):
                                        main_image = f"https:{main_image}"
                                    if "100x100" not in main_image and main_image:
                                        product_json_data["image_url"] = main_image
                                        print(f"Primary image URL: {main_image}")
                                if not product_json_data["image_url"]:
                                    alt_image_elem = retry_extraction(
                                        lambda: product_page_html.find("img", {"class": "main-image"}),
                                        attempts=3, delay=1, default=None
                                    )
                                    if alt_image_elem:
                                        alt_image = alt_image_elem.get("data-zoom-image") or alt_image_elem.get("src", "")
                                        if alt_image and not alt_image.startswith("http"):
                                            alt_image = f"https:{alt_image}"
                                        if "100x100" not in alt_image and alt_image:
                                            product_json_data["image_url"] = alt_image
                                        print(f"Primary image URL (fallback main-image): {alt_image}")
                                if not product_json_data["image_url"]:
                                    thumb_image = retry_extraction(
                                        lambda: product_page_html.find("ul", {"class": "masterMap_smallMapList__JTkBX"}).find("img").get("data-zoom-image") or 
                                                product_page_html.find("ul", {"class": "masterMap_smallMapList__JTkBX"}).find("img").get("src"),
                                        attempts=3, delay=1, default=""
                                    )
                                    if thumb_image and not thumb_image.startswith("http"):
                                        thumb_image = f"https:{thumb_image}"
                                    if "100x100" not in thumb_image and thumb_image:
                                        product_json_data["image_url"] = thumb_image
                                        print(f"Primary image URL (thumbnail fallback): {thumb_image}")
                            except Exception as e:
                                print(f"Error extracting primary image URL: {e}")
                            try:
                                scroll_to_element(browser, "ul.masterMap_smallMapList__JTkBX")
                                thumbnails = retry_extraction(
                                    lambda: browser.find_elements(By.CSS_SELECTOR, "ul.masterMap_smallMapList__JTkBX li"),
                                    attempts=3, delay=1, default=[]
                                )
                                media_images = set([product_json_data["image_url"]]) if product_json_data["image_url"] else set()
                                media_videos = set()
                                for thumb in thumbnails:
                                    try:
                                        ActionChains(browser).move_to_element(thumb).click().perform()
                                        time.sleep(random.uniform(0.5, 1))
                                        media_soup = BeautifulSoup(browser.page_source, "html.parser")
                                        big_map_div = media_soup.find("div", {"class": "masterMap_bigMapWarp__2Jzw2"})
                                        if big_map_div:
                                            video_tag = big_map_div.find("video")
                                            if video_tag and video_tag.get("src"):
                                                video_src = video_tag.get("src")
                                                if not video_src.startswith("http"):
                                                    video_src = f"https:{video_src}"
                                                media_videos.add(video_src)
                                            else:
                                                image_tag = big_map_div.find("img")
                                                if image_tag:
                                                    img_src = image_tag.get("data-zoom-image") or image_tag.get("src", "")
                                                    if img_src and not img_src.startswith("http"):
                                                        img_src = f"https:{img_src}"
                                                    if "100x100" not in img_src and img_src:
                                                        media_images.add(img_src)
                                    except Exception as e:
                                        print(f"Error extracting media for a thumbnail: {e}")
                                product_json_data["images"] = list(media_images)
                                product_json_data["videos"] = list(media_videos)
                                print(f"Images: {product_json_data['images']}")
                                print(f"Videos: {product_json_data['videos']}")
                            except Exception as e:
                                print(f"Error extracting additional images and videos: {e}")
                            try:
                                dim_regex = r'\b\d+(\.\d+)?\s*(?:x|X)\s*\d+(\.\d+)?\s*(?:x|X)\s*\d+(\.\d+)?\s*(cm|in|inches|centimeters|mm)\b|' + \
                                            r'\b\d+\s*-\s*\d+\s*(millimeters|mm|cm|in|inches|centimeters)\b|' + \
                                            r'\b\d+(\.\d+)?\s*(cm|in|inches|centimeters|mm)\b'
                                dimension_keys = ["Band length", "Dial Diameter", "Band Width", "Waterproof Deepness", "Case Size", "Dimensions"]
                                specs_list = retry_extraction(
                                    lambda: product_page_html.find("ul", {"class": "prodSpecifications_showUl__fmY8y"}),
                                    attempts=3, delay=1, default=None
                                )
                                dimensions = []
                                if specs_list:
                                    for li in specs_list.find_all("li"):
                                        key_elem = li.find("span")
                                        value_elem = li.find("div", {"class": "prodSpecifications_deswrap___Z092"})
                                        if key_elem and value_elem:
                                            key = key_elem.get_text(strip=True).replace(":", "").strip()
                                            value = value_elem.get_text(strip=True)
                                            if key in dimension_keys and re.match(dim_regex, value, re.IGNORECASE):
                                                dimensions.append(f"{key}: {value}")
                                    if dimensions:
                                        product_json_data["dimensions"] = "; ".join(dimensions)
                                        print(f"Dimensions (specifications): {product_json_data['dimensions']}")
                                if not product_json_data["dimensions"]:
                                    description = product_json_data.get("description", "")
                                    dimension_matches = re.findall(dim_regex, description, re.IGNORECASE)
                                    if dimension_matches:
                                        dimensions = "; ".join([match[0] for match in dimension_matches if match[0]])
                                        product_json_data["dimensions"] = dimensions
                                        print(f"Dimensions (description): {dimensions}")
                                if not product_json_data["dimensions"]:
                                    print(f"No dimensions found for product: {product_json_data['url']}")
                                    html_file = f"product_{product_json_data['url'].split('/')[-1]}_source_{uuid.uuid4().hex}.html"
                                    with open(html_file, "w", encoding="utf-8") as f:
                                        f.write(browser.page_source)
                                    print(f"Saved product page HTML to {html_file}")
                            except Exception as e:
                                print(f"Error extracting dimensions: {e}")
                            product_json_data = extract_specifications(browser, product_page_html, product_json_data)
                            try:
                                discount_element = retry_extraction(
                                    lambda: product_page_html.find("span", {"class": "productPrice_discount__dMPyI"}),
                                    attempts=3, delay=1, default=None
                                )
                                if discount_element:
                                    discount_text = discount_element.get_text(strip=True)
                                    if re.match(r'\d+%\s*(off)?', discount_text, re.IGNORECASE):
                                        product_json_data["discount_information"] = discount_text
                                        print(f"Discount information: {discount_text}")
                                else:
                                    discount_element = retry_extraction(
                                        lambda: product_page_html.find("span", {"class": "discount-label"}),
                                        attempts=3, delay=1, default=None
                                    )
                                    if discount_element:
                                        discount_text = discount_element.get_text(strip=True)
                                        if re.match(r'\d+%\s*(off)?', discount_text, re.IGNORECASE):
                                            product_json_data["discount_information"] = discount_text
                                            print(f"Discount information (discount-label): {discount_text}")
                                    else:
                                        promo_tag = retry_extraction(
                                            lambda: product_page_html.find("span", {"class": "promo-label"}).get_text(strip=True),
                                            attempts=3, delay=1, default=""
                                        )
                                        if promo_tag and re.match(r'\d+%\s*off', promo_tag, re.IGNORECASE):
                                            product_json_data["discount_information"] = promo_tag
                                            print(f"Discount (promo tag): {promo_tag}")
                                if not product_json_data["discount_information"]:
                                    print("No discount information found.")
                            except Exception as e:
                                print(f"Error extracting discount information: {e}")
                            try:
                                brand_name = None
                                if 'specifications' in product_json_data and product_json_data['specifications']:
                                    for key, value in product_json_data['specifications'].items():
                                        if key.lower() in ["brand", "product brand"]:
                                            brand_name = value
                                            product_json_data["brand_name"] = brand_name
                                            print(f"Brand name (specifications): {brand_name}")
                                            break
                                if not brand_name:
                                    brand_element = retry_extraction(
                                        lambda: product_page_html.find("span", {"class": "brand-name"}),
                                        attempts=3, delay=1, default=None
                                    )
                                    if brand_element:
                                        brand_name = brand_element.get_text(strip=True)
                                        brand_name = re.sub(r'^Brand:\s*', '', brand_name, flags=re.IGNORECASE)
                                        product_json_data["brand_name"] = brand_name
                                        print(f"Brand name (page): {brand_name}")
                                    else:
                                        title = product_json_data.get("title", "").lower()
                                        if "rolex" in title:
                                            product_json_data["brand_name"] = "Rolex"
                                            print("Brand name (title): Rolex")
                            except Exception as e:
                                print(f"Error extracting brand name: {e}")
                            print(f"Website name: {product_json_data['website_name']}")
                        except Exception as e:
                            print(f"Error processing product page: {e}")
                            browser.save_screenshot(f"product_error_{product_json_data['url'].split('/')[-1]}.png")
                        finally:
                            browser.close()
                            browser.switch_to.window(browser.window_handles[0])
                    scraped_products[product_json_data["url"]] = product_json_data
                    append_product_to_json(product_json_data)
                break
            except Exception as e:
                print(f"Attempt {attempt+1}/{retries}: Error scraping page {page+1}: {e}")
                browser.save_screenshot(f"error_page_{page+1}_attempt_{attempt+1}.png")
                time.sleep(random.uniform(1, 2))
        else:
            print(f"Failed to scrape page {page+1} after {retries} attempts.")
            browser.save_screenshot(f"final_error_page_{page+1}.png")
    try:
        json_data = list(scraped_products.values())
        print(f"Number of products scraped: {len(json_data)}")
        if not json_data:
            print("No products scraped.")
            return
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        print(f"Scraping completed and saved to {output_file}")
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            print("JSON file verified.")
        else:
            print("Warning: JSON file is empty or was not created.")
    except Exception as e:
        print(f"Error saving final JSON file: {e}")
    finally:
        try:
            browser.quit()
        except Exception as e:
            print(f"Error closing browser: {e}")

if __name__ == "__main__":
    scrape_dhgate_products()