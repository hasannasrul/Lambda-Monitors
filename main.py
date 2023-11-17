from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from tempfile import mkdtemp

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


def handler(event, context):
    # Extract URL from the event
    url = event.get('url')

    # Check if the URL is provided
    if not url:
        return {
            'statusCode': 400,
            'body': 'Error: Missing URL in the event'
        }

    try:
        # Open the provided URL in the browser
        driver.get(url)

        # Fetch all links on the page
        links = driver.find_elements(by=By.TAG_NAME, value="a")
        link_texts = [link.get_attribute('href') for link in links if link.get_attribute('href').strip()]
        
        return {
            'site-available': True,
            'body': link_texts
        }

    finally:
        # Close the browser
        driver.quit()