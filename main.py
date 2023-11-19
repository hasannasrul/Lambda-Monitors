from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from tempfile import mkdtemp
from concurrent.futures import ThreadPoolExecutor, as_completed


class Monitor():
    def __init__(self, driver):
        self.driver = driver

    def get_page_load_time(self):
        navigation_start = self.driver.execute_script("return window.performance.timing.navigationStart;")
        load_event_end = self.driver.execute_script("return window.performance.timing.loadEventEnd;")
        page_load_time = (load_event_end - navigation_start) / 1000.0  # Convert to seconds
        return page_load_time

    def check_console_errors(self):
        console_errors = self.driver.get_log("browser")
        return console_errors

    def check_url(self, url, timeout=10):
        try:
            self.driver.set_page_load_timeout(timeout)
            self.driver.get(url)
            # Check the HTTP status code
            status_code = self.driver.execute_script("return window.performance.getEntries()[0].response.status")
            if status_code == 200 or status_code == 403:
                return None  # Website is up
            else:
                return { url : status_code }
        except TimeoutException:
            return { url : "Timeout" }  # Timeout occurred, URL might be down or slow to respond
        except Exception as e:
            return { url : str(e) }  # Other exceptions, URL is likely broken

    def check_urls(self, urls, timeout=10):
        with ThreadPoolExecutor() as executor:
            # Create a list of futures for each URL
            futures = [executor.submit(self.check_url, url, timeout) for url in urls]
            # Collect broken URLs
            broken_urls = [future.result() for future in as_completed(futures) if future.result() is not None]
            return broken_urls

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

        # create a monitor class instance
        monitor = Monitor(driver)

        # 1. Open the provided URL in the browser
        driver.get(url)

        # 2. Check Page Load Time
        page_load_time = monitor.get_page_load_time()
        
        # 3. Check for console errors
        console_errors = monitor.check_console_errors()

        # 4. Fetch all links on the page to Check external links for being broken
        links = driver.find_elements(by=By.TAG_NAME, value="a")
        link_texts = [link.get_attribute('href') for link in links if link.get_attribute('href').strip()]

        broken_links = monitor.check_urls(link_texts)

        return {
            'site-available': True,
            'page-load-time': page_load_time,
            'console-errors': console_errors,
            'broken-links': broken_links,
            'links-texts': link_texts
            
        }

    finally:
        # Close the browser in the finally block to ensure cleanup
        if driver:
            driver.quit()