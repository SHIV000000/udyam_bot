# udyam\automate_form.py


import os
import re
import time
import logging
from datetime import datetime, timezone
from io import BytesIO


from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    ElementClickInterceptedException,
)
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from database import RegistrationStage, get_db_session, UdyamRegistration


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


driver = None

def update_registration_stage(registration_id, stage, details=None, error=None):
    session = get_db_session()
    try:
        registration = session.query(UdyamRegistration).filter_by(id=registration_id).first()
        if registration:
            registration.current_stage = stage
            if details:
                registration.stage_details[stage.value] = details
            if error:
                registration.error_message = error
            registration.last_updated = datetime.now(timezone.utc)
            session.commit()
    except Exception as e:
        session.rollback()
        logging.error(f"Error updating registration stage: {str(e)}")
    finally:
        session.close()

def get_driver():
    global driver
    if driver is None:
        chrome_options = Options()
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument('--ignore-certificate-errors')

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


"""
def get_driver():
    global driver
    if driver is None:
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        #  Uncomment the line below if you want to run Chrome in headless mode
        chrome_options.add_argument("--headless")
        service = Service(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service)
        driver = webdriver.Chrome(options=chrome_options)
    return driver
"""


def close_driver():
    global driver
    if driver:
        driver.quit()
    driver = None


def initiate_adhar(adhar, name, registration_id):
    driver = get_driver()
    try:
        driver.get("https://udyamregistration.gov.in/UdyamRegistration.aspx")

        print("DONEDONE")

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located(
                (By.NAME, "ctl00$ContentPlaceHolder1$txtadharno")
            )
        )

        driver.find_element(By.NAME, "ctl00$ContentPlaceHolder1$txtadharno").send_keys(
            adhar
        )
        driver.find_element(
            By.NAME, "ctl00$ContentPlaceHolder1$txtownername"
        ).send_keys(name)

        driver.find_element(
            By.NAME, "ctl00$ContentPlaceHolder1$btnValidateAadhaar"
        ).click()

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.NAME, "ctl00$ContentPlaceHolder1$txtOtp1")
            )
        )

        return "OTP page ready"
    except Exception as e:
        # close_driver()
        return f"Error in initiate_adhar: {str(e)}"


def submit_otp(otp, registration_id):
    driver = get_driver()
    try:
        driver.find_element(By.NAME, "ctl00$ContentPlaceHolder1$txtOtp1").send_keys(otp)
        driver.find_element(By.NAME, "ctl00$ContentPlaceHolder1$btnValidate").click()

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located(
                (By.ID, "ctl00_ContentPlaceHolder1_ddlTypeofOrg")
            )
        )

        return "OTP submitted successfully"
    except Exception as e:
        # close_driver()
        return f"Error in submit_otp: {str(e)}"


def submit_pan(pan_data, registration_id):
    driver = get_driver()
    logging.info(f"Starting PAN submission for registration ID: {registration_id}")
    
    try:
        # Initial stage - PAN Data Filling
        update_registration_stage(registration_id, RegistrationStage.PAN_DATA_FILLING, pan_data)
        logging.info("Starting PAN data filling")

        # Wait for the dropdown to be present
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlTypeofOrg"))
        )
        logging.info("Organization type dropdown found")

        # Select 'Proprietary' using JavaScript
        script = """
        var select = document.getElementById('ctl00_ContentPlaceHolder1_ddlTypeofOrg');
        for(var i=0; i<select.options.length; i++) {
            if(select.options[i].text.includes('Proprietary')) {
                select.selectedIndex = i;
                select.dispatchEvent(new Event('change'));
                break;
            }
        }
        """
        driver.execute_script(script)
        update_registration_stage(registration_id, RegistrationStage.PAN_SELECT_BOX_DONE, 
                                {"org_type": "Proprietary"})
        logging.info("Organization type selected")

        # Wait for form elements to be ready
        time.sleep(5)

        try:
            # PAN Number
            pan_input = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtPan"))
            )
            pan_input.send_keys(pan_data["pan"])
            update_registration_stage(registration_id, RegistrationStage.PAN_NUMBER_ADDED, 
                                    {"pan": pan_data["pan"]})
            logging.info("PAN number entered")

            # PAN Name
            pan_name_input = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtPanName"))
            )
            pan_name_input.send_keys(pan_data["pan_name"])
            update_registration_stage(registration_id, RegistrationStage.PAN_NAME_ADDED, 
                                    {"pan_name": pan_data["pan_name"]})
            logging.info("PAN name entered")

            # Date of Birth
            dob = datetime.strptime(pan_data["dob"], "%Y-%m-%d").strftime("%d/%m/%Y")
            dob_input = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_txtdob"))
            )
            dob_input.send_keys(dob)
            update_registration_stage(registration_id, RegistrationStage.PAN_DATE_ADDED, 
                                    {"dob": dob})
            logging.info("Date of birth entered")

            # Wait for preloader to disappear
            WebDriverWait(driver, 30).until(
                EC.invisibility_of_element_located((By.ID, "preloader"))
            )

            # Declaration checkbox
            try:
                checkbox = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_chkDecarationP"))
                )
                checkbox.click()
            except ElementClickInterceptedException:
                driver.execute_script(
                    "document.getElementById('ctl00_ContentPlaceHolder1_chkDecarationP').click();"
                )
            update_registration_stage(registration_id, RegistrationStage.PAN_CHECKBOX_CHECKED)
            logging.info("Declaration checkbox checked")

            time.sleep(5)

            # PAN Validation
            try:
                validate_button = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_btnValidatePan"))
                )
                validate_button.click()
            except ElementClickInterceptedException:
                driver.execute_script(
                    "document.getElementById('ctl00_ContentPlaceHolder1_btnValidatePan').click();"
                )
            update_registration_stage(registration_id, RegistrationStage.PAN_BUTTON_CLICKED)
            logging.info("PAN validation button clicked")

            time.sleep(10)

            # Get PAN Data
            try:
                get_pan_data_button = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_btnGetPanData"))
                )
                get_pan_data_button.click()
            except ElementClickInterceptedException:
                driver.execute_script(
                    "document.getElementById('ctl00_ContentPlaceHolder1_btnGetPanData').click();"
                )
            logging.info("Get PAN Data button clicked")

            # GSTIN Selection
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_rblWhetherGstn"))
            )
            logging.info("GSTIN radio buttons found")

            gstin_option = pan_data.get("have_gstin", "Exempted")
            gstin_value = "1" if gstin_option == "Yes" else "3"
            gstin_id = f"ctl00_ContentPlaceHolder1_rblWhetherGstn_{int(gstin_value) - 1}"
            
            try:
                gstin_radio = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, gstin_id))
                )
                gstin_radio.click()
            except Exception as e:
                logging.warning(f"Failed to click GSTIN radio button normally: {str(e)}")
                driver.execute_script(f"document.getElementById('{gstin_id}').click();")
            
            update_registration_stage(registration_id, RegistrationStage.GST_BTN_CLICKABLE, 
                                    {"gstin_option": gstin_option})
            logging.info(f"GSTIN option selected: {gstin_option}")

            # Wait for mobile input field
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtmobile"))
            )
            logging.info("Mobile input field found")

            # Final PAN submission stage
            update_registration_stage(registration_id, RegistrationStage.PAN_SUBMITTED, 
                                    {"status": "success"})
            
            return "PAN and GSTIN details submitted successfully"

        except TimeoutException as e:
            error_msg = f"Timeout waiting for element: {str(e)}"
            logging.error(error_msg)
            update_registration_stage(registration_id, RegistrationStage.ERROR, 
                                    error=error_msg)
            return f"Error in submit_pan: {error_msg}"

    except Exception as e:
        error_msg = f"Error in PAN submission: {str(e)}"
        logging.error(error_msg)
        update_registration_stage(registration_id, RegistrationStage.ERROR, 
                                error=error_msg)
        return f"Error in submit_pan: {error_msg}"



def select_option_by_regex(dropdown_element, user_input):
    # Create a Select object for the dropdown
    select = Select(dropdown_element)

    # Normalize the user's input to uppercase for matching
    user_input = user_input.upper()

    # Iterate through the options in the dropdown to find a regex match
    for option in select.options:
        option_text = option.text.upper()

        # Extract the district name from the option text
        district_name = option_text.split('.')[-1].strip()

        # Use regex to match the user's input with the district name
        if re.search(rf"\b{re.escape(user_input)}\b", district_name):
            select.select_by_visible_text(option.text)
            return

    # If no match is found, try a more lenient search
    for option in select.options:
        option_text = option.text.upper()
        if user_input in option_text:
            select.select_by_visible_text(option.text)
            return

    # Raise an error if no match is found
    raise ValueError(f"Could not locate element with matching text for: {user_input}")


def submit_form(form_data, registration_id):
    driver = get_driver()
    try:
        # Wait for the form to load
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtmobile"))
        )
        logging.info("Form loaded successfully")

        # Fill in form fields
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtmobile").send_keys(form_data.get("mobile", ""))
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtemail"))
        )
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtemail").send_keys(form_data.get("email", ""))
        logging.info("Mobile and email filled")

        # Social Category
        social_category_map = {"General": "0", "SC": "1", "ST": "2", "OBC": "3"}
        social_category_id = f"ctl00_ContentPlaceHolder1_rdbcategory_{social_category_map.get(form_data.get('social_category', 'General'), '0')}"
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, social_category_id))).click()
        logging.info("Social category selected")

        # Gender
        gender_map = {"M": "0", "F": "1", "O": "2"}
        gender_id = f"ctl00_ContentPlaceHolder1_rbtGender_{gender_map.get(form_data.get('gender', 'M'), '0')}"
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, gender_id))).click()
        logging.info("Gender selected")

        # Specially Abled
        specially_abled_map = {"Y": "0", "N": "1"}
        specially_abled_id = f"ctl00_ContentPlaceHolder1_rbtPh_{specially_abled_map.get(form_data.get('specially_abled', 'N'), '1')}"
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, specially_abled_id))).click()
        logging.info("Specially abled option selected")

        # Fill in the form fields
        enterprise_name = form_data.get("enterprise_name") or form_data.get("pan_name", "")
        unit_name = form_data.get("unit_name") or form_data.get("pan_name", "")

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtenterprisename"))
        )

        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtenterprisename").send_keys(enterprise_name)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtUnitName"))
        )
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtUnitName").send_keys(unit_name)
        logging.info("Enterprise and unit name filled")

        # Click the "Add Unit" button
        add_unit_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_btnAddUnit"))
        )
        add_unit_button.click()
        logging.info("Add Unit button clicked")

        # Wait for 2 seconds
        time.sleep(2)

        # Create a Select object and choose the first option
        dropdown_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlUnitName"))
        )
        select = Select(dropdown_element)
        select.select_by_index(1)
        logging.info("Unit selected from dropdown")

        # Fill address details
        address_fields = [
            ("ctl00_ContentPlaceHolder1_txtPFlat", "premises_number"),
            ("ctl00_ContentPlaceHolder1_txtPBuilding", "building_name"),
            ("ctl00_ContentPlaceHolder1_txtPVillageTown", "village_town"),
            ("ctl00_ContentPlaceHolder1_txtPBlock", "block"),
            ("ctl00_ContentPlaceHolder1_txtPRoadStreetLane", "road_street_lane"),
            ("ctl00_ContentPlaceHolder1_txtPCity", "city"),
            ("ctl00_ContentPlaceHolder1_txtPpin", "pincode")
        ]

        for field_id, data_key in address_fields:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, field_id))
            ).send_keys(form_data.get(data_key, ""))
        logging.info("Address details filled")

        # Select state
        state_dropdown = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlPState"))
        )
        select_option_by_regex(state_dropdown, form_data.get("state", ""))
        logging.info("State selected")

        # Wait for the district dropdown to load options
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#ctl00_ContentPlaceHolder1_ddlPDistrict option:not([value='0'])"))
        )

        # Select district
        district_dropdown = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlPDistrict")
        select_option_by_regex(district_dropdown, form_data.get("district", ""))
        logging.info("District selected")

        # Click the "Add Plant" button
        add_plant_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_BtnPAdd"))
        )
        add_plant_button.click()

        # Wait for 4 seconds
        time.sleep(4)

        # Official address of the enterprise (same as plant address)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtOffFlatNo"))
        )

        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtOffFlatNo").send_keys(form_data["premises_number"])
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtOffBuilding"))
        )

        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtOffBuilding").send_keys(form_data["building_name"])
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtOffVillageTown"))
        )
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtOffVillageTown").send_keys(form_data["village_town"])
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtOffBlock"))
        )
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtOffBlock").send_keys(form_data["block"])
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtOffRoadStreetLane"))
        )
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtOffRoadStreetLane").send_keys(
            form_data["road_street_lane"])
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtOffCity"))
        )
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtOffCity").send_keys(form_data["city"])
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtOffPin"))
        )
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtOffPin").send_keys(form_data["pincode"])

        # Select state (same as plant address)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlstate"))
        )
        state_dropdown = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlstate")
        select_option_by_regex(state_dropdown, form_data["state"])

        # Wait for the district dropdown to load options
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#ctl00_ContentPlaceHolder1_ddlDistrict option:not([value='0'])"))
        )

        # Select district (same as plant address)
        district_dropdown = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlDistrict")
        select_option_by_regex(district_dropdown, form_data["district"])

        # Click the "Get Latitude & Longitude" button
        get_lat_long_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_Button1"))
        )
        get_lat_long_button.click()

        # Store the current window handle (parent window)
        parent_window = driver.current_window_handle

        # Wait for the new window to open and switch to it
        WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
        all_windows = driver.window_handles
        new_window = [window for window in all_windows if window != parent_window][0]
        driver.switch_to.window(new_window)

        # Wait for the map to load
        wait = WebDriverWait(driver, 40)

        # Wait for the map div to be present
        map_div = wait.until(EC.presence_of_element_located((By.ID, 'mapDiv')))
        print("Map div found")

        # Wait for SVG to load
        svg = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'svg')))
        print("SVG element found")

        # Implement a retry mechanism for finding path elements
        max_retries = 5
        for attempt in range(max_retries):
            paths = driver.find_elements(By.CSS_SELECTOR, 'path')
            if paths:
                print(f"Found {len(paths)} path elements")
                district_path = paths[0]
                actions = ActionChains(driver)

                # Scroll the element into view
                driver.execute_script("arguments[0].scrollIntoView();", district_path)

                # Click the path
                actions.move_to_element(district_path).click().perform()
                print("Clicked on a path element")
                time.sleep(2)  # Wait for 2 seconds after clicking
                break
            else:
                print(f"No path elements found. Attempt {attempt + 1} of {max_retries}")
                time.sleep(2)  # Wait for 2 seconds before retrying
        else:
            print("Failed to find path elements after all attempts")

        # Wait for latitude and longitude fields to be visible
        latitude = wait.until(EC.visibility_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_txtlatitude1')))
        longitude = wait.until(EC.visibility_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_txtlongitude1')))

        latitude_value = latitude.get_attribute('value')
        longitude_value = longitude.get_attribute('value')

        print(f'Latitude: {latitude_value}')
        print(f'Longitude: {longitude_value}')

        # Click the OK button
        ok_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.btn.btn-primary[onclick="f2();"]')))
        ok_button.click()
        print("Clicked the OK button")
        time.sleep(2)

        # Switch back to the original window
        driver.switch_to.window(parent_window)

        # Date of incorporation (convert to DD/MM/YYYY format)
        incorporation_date = datetime.strptime(form_data["date_of_incorporation"], "%Y-%m-%d").strftime("%d/%m/%Y")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtdateIncorporation"))
        )
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtdateIncorporation").send_keys(incorporation_date)

        # Date of Commencement (use incorporation date if not provided)
        commencement_date = form_data.get("date_of_commencement", form_data["date_of_incorporation"])
        commencement_date = datetime.strptime(commencement_date, "%Y-%m-%d").strftime("%d/%m/%Y")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtcommencedate"))
        )
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtcommencedate").send_keys(commencement_date)

        # Bank Details

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtBankName"))
        )
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtBankName").send_keys(form_data["bank_name"])

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtaccountno"))
        )
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtaccountno").send_keys(form_data["account_number"])

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtifsccode"))
        )
        driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtifsccode").send_keys(form_data["ifsc_code"])

        major_activity = form_data.get("major_activity", "Manufacturing")
        if major_activity == "Manufacturing":
            activity_id = "ctl00_ContentPlaceHolder1_rdbCatgg_0"
        else:  # Services
            activity_id = "ctl00_ContentPlaceHolder1_rdbCatgg_1"

        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, activity_id))
        ).click()
        logging.info(f"Selected Major Activity: {major_activity}")

        # If Services is selected, handle the sub-category
        if major_activity == "Services":
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_divsubcatg"))
            )

            sub_activity = form_data.get("sub_activity", "Non-Trading")
            if sub_activity == "Non-Trading":
                sub_activity_id = "ctl00_ContentPlaceHolder1_rdbSubCategg_0"
            else:  # Trading
                sub_activity_id = "ctl00_ContentPlaceHolder1_rdbSubCategg_1"

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, sub_activity_id))
            ).click()
            logging.info(f"Selected Sub-Activity: {sub_activity}")

        time.sleep(7)

        return "Form submitted successfully"
    except Exception as e:
        return f"Error submitting form: {str(e)}"



def automate_form_next(registration_id, major_activity, second_form_section, nic_codes, employee_counts, investment_data, turnover_data,
                       district):
    driver = get_driver()  # Get the WebDriver instance
    if not driver:
        return {"status": "error", "message": "Failed to initialize WebDriver"}

    def safe_find_element(by, value, timeout=15):
        try:
            return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
        except TimeoutException:
            logging.warning(f"Element not found: {value}")
            return None

    def safe_click(element):
        try:
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(element))
            element.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", element)
        except Exception as e:
            logging.error(f"Error clicking element: {e}")

    def select_option_by_text(select_element, text):
        try:
            select = Select(select_element)
            select.select_by_visible_text(text)
            return True
        except Exception as e:
            logging.error(f"Error selecting option {text}: {e}")
            return False

    def get_options_count(select_element):
        try:
            select = Select(select_element)
            options = select.options
            return len(options)
        except Exception as e:
            logging.error(f"Error getting options count: {e}")
            return 0

    def reselect_previous_dropdown(previous_dropdown_element, previous_text, new_dropdown_element, new_text):
        # Reselect previous dropdown option
        if select_option_by_text(previous_dropdown_element, previous_text):
            logging.info(f"Reselected previous dropdown option: {previous_text}")
            # Select the current dropdown option again
            if select_option_by_text(new_dropdown_element, new_text):
                logging.info(f"Selected option from current dropdown: {new_text}")
                return True
        return False

    try:
        # Major Activity of Unit
        activity_map = {"Mfg": "1", "Service": "2", "Trading": "2"}
        major_activity_id = f'ctl00_ContentPlaceHolder1_rdbCatgg_{activity_map.get(major_activity, "1")}'
        radio_button_script = f"document.getElementById('{major_activity_id}').click();"

        # Major Activity Under Services (if applicable)
        if major_activity == "2":  # Services
            second_form_section_id = f'ctl00_ContentPlaceHolder1_rdbSubCategg_{int(second_form_section) - 1}'
            safe_click(safe_find_element(By.ID, second_form_section_id))
            logging.info(f"Selected second form section: {second_form_section}")

        # NIC Code Selection
        category_radios = {
            "Manufacturing": "//table[@id='ctl00_ContentPlaceHolder1_rdbCatggMultiple']//label[contains(text(),'Manufacturing')]",
            "Services": "//table[@id='ctl00_ContentPlaceHolder1_rdbCatggMultiple']//label[contains(text(),'Services')]",
            "Trading": "//table[@id='ctl00_ContentPlaceHolder1_rdbCatggMultiple']//label[contains(text(),'Trading')]"
        }

        category_element = safe_find_element(By.XPATH, category_radios[nic_codes[0]['category']])
        if category_element:
            safe_click(category_element)
            logging.info(f"Selected category: {nic_codes[0]['category']}")
        else:
            logging.warning(f"Category element not found for: {nic_codes[0]['category']}")

        time.sleep(3)  # Wait for the page to load

        print("NIC CODES >>>> ", nic_codes)
        for nic_code in nic_codes:
            print("NIC CODE >>>>>>>> ", nic_code)

            two_digit = safe_find_element(By.XPATH, "//select[@name='ctl00$ContentPlaceHolder1$ddl2NicCode']")
            select_option_by_regex(two_digit, nic_code['2_digit'])
            print("TWO DIGIT >>>>> ", two_digit)

            print("WAITING")

            if two_digit:
                logging.info(f"Selected 2-digit NIC code: {nic_code['2_digit']}")

                print("DONE 2")

                time.sleep(5)

                four_digit = safe_find_element(By.XPATH, "//select[@name='ctl00$ContentPlaceHolder1$ddl4NicCode']")
                print("four digit")
                if four_digit:
                    print("if passed four digit")
                    print("option count>>>>> ", get_options_count(four_digit))

                    if get_options_count(four_digit) > 1:
                        # Continue if there are more than one option
                        select_option_by_regex(four_digit, nic_code['4_digit'])
                        logging.info(f"Selected 4-digit NIC code: {nic_code['4_digit']}")
                        print("second selected")
                        time.sleep(6)
                    else:
                        print("---------------------else second")
                        # Reselect the previous 2-digit option and try again
                        logging.info(
                            "Only one option in 4-digit dropdown, reselecting 2-digit option and trying again.")
                        reselect_previous_dropdown(two_digit, nic_code['2_digit'], four_digit, nic_code['4_digit'])

                    # Now select the 5-digit NIC code
                    print("second done")
                    five_digit = safe_find_element(By.XPATH, "//select[@name='ctl00$ContentPlaceHolder1$ddl5NicCode']")
                    print("FIVE DIGIT >>", five_digit)
                    if five_digit:
                        print("If passed five <<<<<<<<<<<")
                        print("option count five ::::::::: ", get_options_count(five_digit))
                        if get_options_count(five_digit) > 1:
                            print("DONE   MSKDM")
                            # Continue if there are more than one option
                            select_option_by_regex(five_digit, nic_code['5_digit'])
                            print("selected")
                            print("DONE LAST")
                            logging.info(f"Selected 5-digit NIC code: {nic_code['5_digit']}")
                        else:
                            print("Else ------------------------- five")
                            # Reselect the previous 4-digit option and try again
                            logging.info(
                                "Only one option in 5-digit dropdown, reselecting 4-digit option and trying again.")
                            reselect_previous_dropdown(four_digit, nic_code['4_digit'], five_digit, nic_code['5_digit'])

            time.sleep(10)
            print("DONE")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//input[@name='ctl00$ContentPlaceHolder1$btnAddMore'][@value='Add Activity']"))
            )
            add_activity = safe_find_element(By.XPATH,
                                             "//input[@name='ctl00$ContentPlaceHolder1$btnAddMore'][@value='Add Activity']")
            if add_activity:
                safe_click(add_activity)
                logging.info("Added activity")
            else:
                logging.warning("Add Activity button not found")

            time.sleep(5)  # Wait for the page to load

        # Number of persons employed
        try:
            print("Waiting for male employee input field")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtNoofpersonMale"))
            )
            print("Found male employee input field")
            driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtNoofpersonMale").send_keys(
                str(employee_counts.get("male", 0)))
            print("Entered male employee count:", employee_counts.get("male", 0))
        except:
            pass

        try:
            print("Waiting for female employee input field")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtNoofpersonFemale"))
            )
            print("Found female employee input field")
            driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtNoofpersonFemale").send_keys(
                str(employee_counts.get("female", 0)))
            print("Entered female employee count:", employee_counts.get("female", 0))

        except:
            pass


        try:
            print("Waiting for others employee input field")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtNoofpersonOthers"))
            )
            print("Found others employee input field")
            driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtNoofpersonOthers").send_keys(
                str(employee_counts.get("others", 0)))
            print("Entered others employee count:", employee_counts.get("others", 0))
        except:
            pass
        

        try:
            # Investment in Plant and Machinery or Equipment
            print("Checking Written Down Value (WDV) input field")
            wdv_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtDepCost"))
            )
            print("Found Written Down Value (WDV) input field")
        except:
            pass

        if wdv_field.is_enabled():
            print("WDV field is enabled")
            wdv_field.clear()
            wdv_field.send_keys(str(investment_data.get("wdv", 5000000)))
            print("Entered Written Down Value (WDV):", investment_data.get("wdv", 5000000))
        else:
            print("WDV field is disabled. Skipping input.")
            logging.info("WDV field is disabled. Value not entered.")
        
        try:
            print("Waiting for exclusion cost input field")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtExCost"))
            )
            print("Found exclusion cost input field")
            driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtExCost").send_keys(
                str(investment_data.get("exclusion_cost", 200000)))
            print("Entered exclusion cost:", investment_data.get("exclusion_cost", 200000))
        except:
            pass


        try:
            # Turnover
            print("Waiting for total turnover input field")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_txtTotalTurnoverA"))
            )
            print("Found total turnover input field")
            driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtTotalTurnoverA").send_keys(
                str(turnover_data.get("total_turnover", 0)))
            print("Entered total turnover:", turnover_data.get("total_turnover", 0))

        except Exception as e:
            pass

        # Additional registrations (all set to "No")
        no_buttons = [
            '#ctl00_ContentPlaceHolder1_rblGeM_1',
            '#ctl00_ContentPlaceHolder1_rblTReDS_1',
            '#ctl00_ContentPlaceHolder1_rblNCS_1',
            '#ctl00_ContentPlaceHolder1_rblnsic_1',
            '#ctl00_ContentPlaceHolder1_rblnixi_1',
            '#ctl00_ContentPlaceHolder1_rblsid_1'
        ]

        print("Clicking 'No' buttons for additional registrations")
        for button_id in no_buttons:
            print(f"Clicking 'No' button for {button_id}")
            try:
                no_button = driver.find_element(By.CSS_SELECTOR, button_id)
                driver.execute_script("arguments[0].click();", no_button)
                logging.info(f"Clicked 'No' button: {button_id}")
                print(f"Clicked 'No' button: {button_id}")
            except Exception as e:
                logging.error(f'Error selecting "No" button with ID {button_id}: {str(e)}')
                print(f'Error selecting "No" button with ID {button_id}: {str(e)}')

        # District Industries Centre
        print("Selecting district from dropdown")
        district_dropdown = safe_find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlDIC")
        if district_dropdown:
            if select_option_by_text(district_dropdown, district):
                logging.info(f"Selected district: {district}")
                print(f"Selected district: {district}")
            else:
                logging.warning(f"Failed to select district: {district}")
                print(f"Failed to select district: {district}")
        else:
            logging.warning("District dropdown not found")
            print("District dropdown not found")

        # Final submission
        print("Looking for submit button")
        submit_button = safe_find_element(By.ID, "ctl00_ContentPlaceHolder1_btnsubmit")
        if submit_button:
            safe_click(submit_button)
            logging.info("Clicked initial submit button")
            print("Clicked initial submit button")
        else:
            logging.error("Initial submit button not found")
            print("Initial submit button not found")
            return {"status": "error", "message": "Initial submit button not found"}

        try:
            # Wait for the alert to be present
            WebDriverWait(driver, 20).until(EC.alert_is_present())

            # Switch to the alert
            alert = Alert(driver)

            # Print alert text (for debugging purposes)
            print(f"Alert says: {alert.text}")

            # Accept the alert to click OK
            alert.accept()
            print("Alert accepted successfully.")

        except Exception as e:
            print(f"Error handling alert: {e}")

        # Wait for 5 seconds
        print("Waiting for 5 seconds before CAPTCHA")
        time.sleep(50)

        # Wait for the CAPTCHA image to load
        print("Waiting for CAPTCHA image to load")
        captcha_element = safe_find_element(By.ID, "ctl00_ContentPlaceHolder1_imgCaptcha", timeout=30)
        if not captcha_element:
            logging.error("CAPTCHA image not found")
            return {"status": "error", "message": "CAPTCHA image not found"}

        # Get the CAPTCHA image URL
        captcha_url = captcha_element.get_attribute("src")
        print("CAPTCHA image URL:", captcha_url)

        return {"status": "success", "message": "OTP and CAPTCHA required", "captcha_url": captcha_url}

    except Exception as e:
        logging.error(f"Unexpected error in form submission: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        pass


def safe_find_element(by, value, timeout=15):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
    except TimeoutException:
        logging.warning(f"Element not found: {value}")
        return None


def safe_click(element):
    try:
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(element))
        element.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", element)
    except Exception as e:
        logging.error(f"Error clicking element: {e}")


def submit_otp_and_captcha(otp, captcha_code, registration_id):
    driver = get_driver()
    try:
        # Enter OTP
        otp_input = safe_find_element(By.ID, "ctl00_ContentPlaceHolder1_txtOtp")
        if otp_input:
            otp_input.clear()
            otp_input.send_keys(otp)
            logging.info("Entered OTP")
        else:
            logging.error("OTP input field not found")
            return {"status": "error", "message": "OTP input field not found"}

        # Enter CAPTCHA
        captcha_input = safe_find_element(By.ID, "ctl00_ContentPlaceHolder1_txtCaptcha")
        if captcha_input:
            captcha_input.clear()
            captcha_input.send_keys(captcha_code)
            logging.info("Entered CAPTCHA code")
        else:
            logging.error("CAPTCHA input field not found")
            return {"status": "error", "message": "CAPTCHA input field not found"}

        # Click the final submit button
        final_submit_button = safe_find_element(By.ID, "ctl00_ContentPlaceHolder1_btn_finalsubmit")
        if final_submit_button:
            safe_click(final_submit_button)
            logging.info("Clicked final submit button")
        else:
            logging.error("Final submit button not found")
            return {"status": "error", "message": "Final submit button not found"}

        # Wait for the submission to complete
        success_message_element = safe_find_element(By.ID, "ctl00_ContentPlaceHolder1_lblMssgg", timeout=30)
        if success_message_element:
            success_message = success_message_element.text
            if "successfully" in success_message.lower():
                logging.info("Form submitted successfully!")
                return {"status": "success", "message": success_message}
            else:
                logging.warning(f"Form submission may have failed. Message: {success_message}")
                return {"status": "warning", "message": success_message}
        else:
            logging.error("Success message element not found")
            return {"status": "error", "message": "Success message element not found"}

    except Exception as e:
        logging.error(f"Unexpected error in OTP and CAPTCHA submission: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        close_driver()


def get_captcha_screenshot(registration_id):
    driver = get_driver()
    try:
        captcha_element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_imgCaptcha"))
        )
        
        element_location = captcha_element.location
        element_size = captcha_element.size
        
        viewport_height = driver.execute_script("return window.innerHeight;")
        
        scroll_y = element_location['y'] - (viewport_height / 2) + (element_size['height'] / 2)
        
        driver.execute_script(f"window.scrollTo(0, {scroll_y});")
        
        time.sleep(2)
        
        captcha_screenshot = captcha_element.screenshot_as_png
        captcha_image = Image.open(BytesIO(captcha_screenshot))
        
        captcha_dir = os.path.join(os.getcwd(), 'static', 'captcha_images')
        os.makedirs(captcha_dir, exist_ok=True)
        
        captcha_path = os.path.join(captcha_dir, f'captcha_{registration_id}.png')
        captcha_image.save(captcha_path)
        
        if captcha_image.getbbox():
            logging.info(f"CAPTCHA image saved successfully: {captcha_path}")
            return captcha_path
        else:
            logging.error("Captured CAPTCHA image is empty")
            return None
        
    except Exception as e:
        logging.error(f"Error getting CAPTCHA screenshot: {str(e)}")
        return None



