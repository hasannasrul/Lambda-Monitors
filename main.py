from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from tempfile import mkdtemp
import requests

def get_page_load_time(driver):
    navigation_start = driver.execute_script("return window.performance.timing.navigationStart;")
    load_event_end = driver.execute_script("return window.performance.timing.loadEventEnd;")
    page_load_time = (load_event_end - navigation_start) / 1000.0  # Convert to seconds
    return page_load_time

def check_console_errors(driver):
    console_errors = driver.get_log("browser")
    return console_errors

# def check_external_links(driver):
#     links = driver.find_elements(by=By.TAG_NAME, value="a")
#     external_links = [link.get_attribute('href') for link in links if link.get_attribute('href') and 'example.com' not in link.get_attribute('href')]

#     broken_links = []

#     for link in external_links:
#         try:
#             response = requests.head(link, allow_redirects=True, timeout=5)
#             if response.status_code != 200:
#                 broken_links.append(link)
#         except Exception as e:
#             print(f"Error checking link {link}: {e}")
#             broken_links.append(link)

#     return broken_links

def handler(event, context):
    # Extract URL from the event
    url = event.get('url')

    # Check if the URL is provided
    if not url:
        return {
            'statusCode': 400,
            'body': 'Error: Missing URL in the event'
        }

    driver = None  # Initialize the driver variable

    try:
        # Set up Chrome WebDriver
        options = webdriver.ChromeOptions()
        service = webdriver.ChromeService("/opt/chromedriver")

        options.binary_location = '/opt/chrome/chrome'
        options.add_argument("--headless")
        options.add_argument('--no-sandbox')
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280x1696")
        options.add_argument("--single-process")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-dev-tools")
        options.add_argument("--no-zygote")
        options.add_argument(f"--user-data-dir={mkdtemp()}")
        options.add_argument(f"--data-path={mkdtemp()}")
        options.add_argument(f"--disk-cache-dir={mkdtemp()}")
        options.add_argument("--remote-debugging-port=9222")

        driver = webdriver.Chrome(options=options, service=service)

        # Open the provided URL in the browser
        driver.get(url)
        page_load_time = get_page_load_time(driver)

        # Fetch all links on the page
        links = driver.find_elements(by=By.TAG_NAME, value="a")
        link_texts = [link.get_attribute('href') for link in links if link.get_attribute('href').strip()]
        
        # Check for console errors
        console_errors = check_console_errors(driver)

        # # Check external links for being broken
        # broken_links = check_external_links(driver)

        return {
            'site-available': True,
            'page-load-time': page_load_time,
            'console-errors': console_errors,
            'body': {
                'links-texts': link_texts,
                # 'broken-links': broken_links
            }
        }

    finally:
        # Close the browser in the finally block to ensure cleanup
        if driver:
            driver.quit()

