from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os, stat, time
import wget
import zipfile36 as zipfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import uvicorn

app = FastAPI(title="Instagram Session Extractor", version="1.0.0")

# Instagram credentials
INSTAGRAM_USERNAME = "dummarodum280"
INSTAGRAM_PASSWORD = "Aman@123"

def download_and_extract_chromedriver():
    try:
        # For Linux systems (like Render)
        download_url = "https://storage.googleapis.com/chrome-for-testing-public/137.0.7151.70/linux64/chromedriver-linux64.zip"
        
        # For local Windows development
        if os.name == 'nt':
            download_url = "https://storage.googleapis.com/chrome-for-testing-public/137.0.7151.70/win64/chromedriver-win64.zip"

        latest_driver_zip = wget.download(download_url, 'chromedriver.zip')

        def set_executable_permissions(file_path):
            st = os.stat(file_path)
            os.chmod(file_path, st.st_mode | stat.S_IEXEC)

        extracted_dir = os.getcwd()
        with zipfile.ZipFile(latest_driver_zip, 'r') as zip_ref:
            zip_ref.extractall(extracted_dir)
            
            # Handle different extracted paths based on OS
            if os.name == 'nt':  # Windows
                extracted_path = os.path.join(extracted_dir, 'chromedriver-win64', 'chromedriver.exe')
            else:  # Linux/Mac
                extracted_path = os.path.join(extracted_dir, 'chromedriver-linux64', 'chromedriver')
                
            set_executable_permissions(extracted_path)

        os.remove(latest_driver_zip)
        return extracted_path
    except Exception as e:
        print(f"Error downloading or extracting ChromeDriver: {e}")
        return None

def setup_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")

    # On Render, ChromeDriver is already installed at this path
    if os.getenv('RENDER'):
        driver = webdriver.Chrome(options=chrome_options)
    else:
        # Local development
        driver_path = download_and_extract_chromedriver()
        if not driver_path or not os.path.exists(driver_path):
            raise FileNotFoundError(f"ChromeDriver not found at path: {driver_path}")
        service = ChromeService(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def wait_and_click(driver, by, value, timeout=10):
    try:
        element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))
        element.click()
        return True
    except TimeoutException:
        return False

def handle_login_modals(driver):
    time.sleep(3)
    try:
        not_now_xpath = "//button[contains(text(), 'Not now') or contains(text(), 'Not Now')]"
        wait_and_click(driver, By.XPATH, not_now_xpath, 5)
        time.sleep(2)
    except:
        pass
    
    try:
        not_now_xpath = "//button[contains(text(), 'Not now') or contains(text(), 'Not Now')]"
        wait_and_click(driver, By.XPATH, not_now_xpath, 5)
    except:
        pass

def extract_session_cookies(driver):
    cookies = driver.get_cookies()
    session_id = None
    csrf_token = None
    for cookie in cookies:
        if cookie['name'] == 'sessionid':
            session_id = cookie['value']
        elif cookie['name'] == 'csrftoken':
            csrf_token = cookie['value']
    return session_id, csrf_token

def instagram_login(driver):
    try:
        print("🌐 Navigating to Instagram login page...")
        driver.get("https://www.instagram.com/accounts/login/")
        time.sleep(5)

        # Check if already logged in
        if "instagram.com" in driver.current_url and "/accounts/login/" not in driver.current_url:
            print("✅ Already logged in!")
            return True

        print("⏳ Waiting for login form...")
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "username")))
        
        print("📝 Entering credentials...")
        username_input = driver.find_element(By.NAME, "username")
        username_input.clear()
        username_input.send_keys(INSTAGRAM_USERNAME)
        time.sleep(1)

        password_input = driver.find_element(By.NAME, "password")
        password_input.clear()
        password_input.send_keys(INSTAGRAM_PASSWORD)
        time.sleep(1)

        print("🚀 Clicking login button...")
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()

        print("⏳ Waiting for login to complete...")
        WebDriverWait(driver, 20).until(lambda d: (
            d.find_elements(By.XPATH, "//nav") or
            d.find_elements(By.XPATH, "//a[@href='/']") or
            d.find_elements(By.XPATH, "//button[contains(text(), 'Not now')]") or
            d.find_elements(By.XPATH, "//*[contains(text(), 'incorrect') or contains(text(), 'error')]")
        ))

        # Check for login errors
        error_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'incorrect') or contains(text(), 'Sorry') or contains(text(), 'error')]")
        if error_elements:
            print(f"❌ Login error: {error_elements[0].text}")
            return False

        print("🔧 Handling post-login modals...")
        handle_login_modals(driver)
        
        print("🏠 Navigating to home page...")
        driver.get("https://www.instagram.com/")
        WebDriverWait(driver, 15).until(EC.any_of(
            EC.presence_of_element_located((By.XPATH, "//nav")),
            EC.presence_of_element_located((By.XPATH, "//header"))
        ))

        print("✅ Login successful!")
        return True
    except Exception as e:
        print(f"❌ Login failed: {str(e)}")
        return False

# API Endpoints
@app.get("/")
def root():
    """Health check endpoint"""
    return {"status": "running", "message": "Instagram Session Extractor API"}

@app.get("/get_session_id")
def get_session_id():
    """Extract Instagram session ID"""
    print("🚀 Starting session extraction...")
    driver = None
    
    try:
        print("🔧 Setting up Chrome driver...")
        driver = setup_chrome_driver()
        
        # Try login with retries
        max_retries = 3
        for attempt in range(max_retries):
            print(f"📱 Login attempt {attempt + 1} of {max_retries}")
            
            if instagram_login(driver):
                print("🍪 Extracting session cookies...")
                session_id, csrf_token = extract_session_cookies(driver)
                
                if session_id:
                    print("🎉 SUCCESS! Session ID extracted")
                    response_data = {
                        "success": True,
                        "session_id": session_id,
                        "csrf_token": csrf_token,
                        "username": INSTAGRAM_USERNAME,
                        "message": "Session extracted successfully",
                        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # Save to file for backup
                    with open("session_backup.txt", "w") as f:
                        f.write(f"Session ID: {session_id}\n")
                        f.write(f"CSRF Token: {csrf_token}\n")
                        f.write(f"Username: {INSTAGRAM_USERNAME}\n")
                        f.write(f"Extracted at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    
                    return JSONResponse(content=response_data)
                else:
                    print("❌ Login successful but session ID not found")
            
            if attempt < max_retries - 1:
                print("⏳ Waiting before retry...")
                time.sleep(5)
        
        print("❌ All login attempts failed")
        return JSONResponse(
            status_code=401, 
            content={
                "success": False,
                "error": "Login failed after multiple attempts or session ID not found",
                "message": "Please check credentials or try again later"
            }
        )
        
    except Exception as e:
        print(f"💥 Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=500, 
            content={
                "success": False,
                "error": f"Internal server error: {str(e)}",
                "message": "An unexpected error occurred during session extraction"
            }
        )
    finally:
        if driver:
            print("🔚 Closing browser...")
            driver.quit()
            print("✅ Cleanup complete!")

if __name__ == "__main__":
    print("🚀 Starting Instagram Session Extractor API...")
    print("📡 Server will be available at: http://localhost:8000")
    print("📚 API documentation at: http://localhost:8000/docs")
    print("🔍 GET endpoint: http://localhost:8000/get_session_id")
    print("\n" + "="*50 + "\n")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        log_level="info"
    )

