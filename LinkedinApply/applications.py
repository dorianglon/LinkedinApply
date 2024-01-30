import os
import pickle
import random
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import Select
import json
import openai
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options

COOKIES_FILE_PATH = 'linkedin_cookies.pkl'
JSON_FILE_PATH = 'application_info.json'
submitted_applications = 0


def human_like_typing(element, text):
    for character in text:
        element.send_keys(character)
        time.sleep(random.uniform(0.1, 0.3))


def save_cookies(driver, path):
    with open(path, "wb") as file:
        pickle.dump(driver.get_cookies(), file)


def load_cookies(driver, path):
    with open(path, "rb") as file:
        cookies = pickle.load(file)
        for cookie in cookies:
            driver.add_cookie(cookie)


def login(driver, url, username, password):
    driver.get(url)
    time.sleep(2)
    username_input = driver.find_element(By.ID, 'username')
    human_like_typing(username_input, username)
    time.sleep(2)
    password_input = driver.find_element(By.ID, 'password')
    human_like_typing(password_input, password)
    time.sleep(2)
    sign_in_button = driver.find_element(By.CLASS_NAME, 'btn__primary--large.from__button--floating')
    sign_in_button.click()
    time.sleep(5)


def get_jobs_list(driver, job_title, entry_level):
    try:
        # Construct an XPath targeting the button with a specific icon and text
        xpath = "//button[contains(@class, 'msg-overlay-bubble-header__control') and .//li-icon[@type='chevron-down']]"
        # Wait for the button to be present and clickable
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        # Find the button using XPath and click it
        overlay_button = driver.find_element(By.XPATH, xpath)
        overlay_button.click()
    except Exception as e:
        print(f"An error occurred while trying to close the messaging overlay: {e}")
    time.sleep(5)

    # Construct an XPath to find the link with the specific class and href attributes
    xpath = "//a[contains(@class, 'global-nav__primary-link') and contains(@href, 'linkedin.com/jobs')]"
    # Wait for the element to be present
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath)))
    # Find the "Jobs" link using the XPath and click it
    jobs_link = driver.find_element(By.XPATH, xpath)
    jobs_link.click()
    time.sleep(5)

    # Construct an XPath using class and aria-label to find the input element
    xpath = "//input[contains(@class, 'jobs-search-box__text-input') " \
            "and contains(@aria-label, 'Search by title, skill, or company')]"
    # Wait for the element to be present
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath)))
    # Find the input field using the XPath and type the job title
    search_input = driver.find_element(By.XPATH, xpath)
    search_input.clear()
    search_input.send_keys(job_title)
    search_input.send_keys(Keys.RETURN)
    time.sleep(5)

    if entry_level:
        # Construct an XPath using class and aria-label to find the button
        xpath = "//button[contains(@class, 'artdeco-pill') and contains(@aria-label, 'Experience level filter')]"
        # Wait for the element to be present
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath)))
        # Find the button using the XPath and click it
        experience_button = driver.find_element(By.XPATH, xpath)
        experience_button.click()
        time.sleep(5)

        # Locate the label associated with the checkbox
        label_for_checkbox_xpath = "//label[@for='experience-2']"
        # Wait for the label to be present and clickable
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, label_for_checkbox_xpath)))
        # Find the label and click it
        label_for_checkbox = driver.find_element(By.XPATH, label_for_checkbox_xpath)
        label_for_checkbox.click()
        time.sleep(5)

        try:
            # Same XPath targeting
            xpath = "//button[@data-test-reusables-filter-apply-button='true' and " \
                    "@data-control-name='filter_show_results'] "
            # Wait for the element to be present in the DOM
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, xpath)))
            # Find the button and use JavaScript to click it
            show_results_button = driver.find_element(By.XPATH, xpath)
            driver.execute_script("arguments[0].click();", show_results_button)
        except Exception as e:
            print(f"An error occurred: {e}")
        time.sleep(5)

        experience_button.click()
        time.sleep(2)
        experience_button.click()
        time.sleep(5)

    try:
        # CSS Selector using the class name
        css_selector = ".artdeco-pill--choice[aria-label='Easy Apply filter.']"
        # Wait for the button to be clickable
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector)))
        # Find the button using CSS Selector and click it
        easy_apply_button = driver.find_element(By.CSS_SELECTOR, css_selector)
        easy_apply_button.click()
    except Exception as e:
        print(f"An error occurred: {e}")
    time.sleep(5)


def extract_application_popup_text(driver):
    try:
        popup_element = driver.find_element(By.CLASS_NAME, 'jobs-easy-apply-modal')
        popup_text_raw = popup_element.text

        # Splitting by any whitespace and rejoining with space to clean up
        popup_text_cleaned = ' '.join(popup_text_raw.split())

        return popup_text_cleaned
    except NoSuchElementException:
        print("Application popup element not found.")
        return ""
    except Exception as e:
        print(f"Error extracting text from application popup: {e}")
        return ""


def get_job_details(driver):
    try:
        # Extract job details
        job_details_element = driver.find_element(By.CLASS_NAME, 'scaffold-layout__detail')
        job_details_raw_text = job_details_element.text
        job_details_lines = job_details_raw_text.split('\n')
        job_details_cleaned = "\n".join(line.strip() for line in job_details_lines if line.strip())
        return job_details_cleaned

    except NoSuchElementException:
        print("Job details element not found.")
        return
    except Exception as e:
        print(f"Error extracting job details or applying: {e}")
        return


def handle_inputs(driver):
    with open(JSON_FILE_PATH, 'r') as file:
        application_data = json.load(file)

    inputs = driver.find_elements(By.XPATH, "//input[contains(@id, 'formElement') and not(@type='hidden') and not("
                                            "@type='radio')]")
    if not inputs:
        print('No inputs found.')
        return

    for input_element in inputs:
        # Scroll to the input element
        driver.execute_script("arguments[0].scrollIntoView(true);", input_element)
        time.sleep(2)  # Allow time for scrolling and potential re-layout

        label_for = input_element.get_attribute('id')
        label = driver.find_element(By.XPATH, f"//label[@for='{label_for}']")
        label_text = label.text.strip()

        if label_text not in application_data["input"]:
            input_element.clear()  # Clear existing text
            user_input = input(f"Please enter your input for '{label_text}': ")
            input_element.send_keys(user_input)
            application_data["input"][label_text] = user_input
            with open(JSON_FILE_PATH, 'w') as file:
                json.dump(application_data, file, indent=4)
        else:
            input_element.clear()
            input_element.send_keys(application_data["input"][label_text])

        time.sleep(1)


def handle_dropdowns(driver):
    with open(JSON_FILE_PATH, 'r') as file:
        application_data = json.load(file)

    dropdowns = driver.find_elements(By.CSS_SELECTOR, 'select[data-test-text-entity-list-form-select]')
    if not dropdowns:
        print("No dropdowns found.")
        return

    for dropdown in dropdowns:
        driver.execute_script("arguments[0].scrollIntoView(true);", dropdown)
        time.sleep(2)

        label_text = None
        label_for = dropdown.get_attribute('id')

        # First, try to find the direct label association
        labels = driver.find_elements(By.XPATH, f"//label[@for='{label_for}']")
        if labels:
            label_text = labels[0].text.strip().split('\n')[0]
        else:
            # If no direct label is found, try finding the nearest preceding span
            try:
                label = dropdown.find_element(By.XPATH, "./preceding::span[contains(@class, 't-14')][1]")
                label_text = label.text.strip().split('\n')[0]
            except NoSuchElementException:
                print("No label found for dropdown.")
                continue  # Skip this dropdown if no label is found

        select = Select(dropdown)

        if label_text in application_data["dropdown"]:
            user_choice = application_data["dropdown"][label_text]
            try:
                select.select_by_visible_text(user_choice)
            except Exception as e:
                print(f"Error selecting dropdown option for '{label_text}': {e}")
        else:
            print(f"Label found for dropdown: {label_text}")
            options = [option.text.strip() for option in select.options if option.text.strip()]
            print(f"Options for '{label_text}': {', '.join(options)}")

            user_choice = input(f"Please enter your choice for '{label_text}': ")
            try:
                select.select_by_visible_text(user_choice)
                application_data["dropdown"][label_text] = user_choice
                with open(JSON_FILE_PATH, 'w') as file:
                    json.dump(application_data, file, indent=4)
            except Exception as e:
                print(f"Error selecting dropdown option for '{label_text}': {e}")

        time.sleep(1)


def handle_multiple_choice(driver):
    with open(JSON_FILE_PATH, 'r') as file:
        application_data = json.load(file)

    fieldsets = driver.find_elements(By.XPATH,
                                     "//fieldset[@data-test-form-builder-radio-button-form-component='true']")
    if not fieldsets:
        print('No multiple choices found.')
        return

    for fieldset in fieldsets:
        driver.execute_script("arguments[0].scrollIntoView(true);", fieldset)
        time.sleep(2)

        question = fieldset.find_element(By.TAG_NAME, "legend").text.strip()

        # Get all radio button options within the fieldset
        radio_buttons = fieldset.find_elements(By.XPATH, ".//input[@type='radio']")
        labels = [driver.find_element(By.XPATH, f"//label[@for='{radio.get_attribute('id')}']") for radio in
                  radio_buttons]

        if question in application_data["multiple choice"]:
            user_choice = application_data["multiple choice"][question]
            # Click the radio button corresponding to the saved user's choice
            for label in labels:
                if label.text.strip() == user_choice.strip():
                    driver.execute_script("arguments[0].click();", label)
                    break
        else:
            print(f"Question: {question}")
            for label in labels:
                print(f"Option: {label.text}")

            user_choice = input("Please enter your choice: ")
            # Click the radio button corresponding to the user's choice
            for label in labels:
                if label.text.strip() == user_choice.strip():
                    driver.execute_script("arguments[0].click();", label)
                    break

            application_data["multiple choice"][question] = user_choice
            with open(JSON_FILE_PATH, 'w') as file:
                json.dump(application_data, file, indent=4)

        time.sleep(1)


def handle_final_submission(driver):
    try:
        # Wait for the pop-up to be visible
        pop_up = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, 'jobs-easy-apply'
                                                                                                  '-modal')))
        pop_up.click()
        time.sleep(1)

        # Scroll to the bottom of the pop-up
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", pop_up)
        time.sleep(3)

        # Uncheck 'Follow Company' checkbox if present and selected
        # follow_company_checkbox_elements = driver.find_elements(By.ID, "follow-company-checkbox")
        # if follow_company_checkbox_elements:
        #     follow_company_label = driver.find_element(By.XPATH, "//label[@for='follow-company-checkbox']")
        #     follow_company_label.click()
        #     time.sleep(2)

        # Click the submit button
        submit_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[.//span[text("
                                                                                              ")='Submit "
                                                                                              "application']]")))
        driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
        driver.execute_script("arguments[0].click();", submit_button)
        print("Application submitted.")
        time.sleep(2)

        # Close the confirmation pop-up
        close_confirmation_popup(driver)
    except Exception as e:
        print(f"Error during final submission step: {e}")


def close_confirmation_popup(driver):
    try:
        # Wait for a few seconds for the pop-up to appear
        time.sleep(3)
        dismiss_button = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//button["
                                                                                                   "contains(@class, "
                                                                                                   "'artdeco"
                                                                                                   "-modal__dismiss')]")))
        driver.execute_script("arguments[0].click();", dismiss_button)
        print("Confirmation pop-up closed.")
    except Exception as e:
        print(f"Error closing confirmation pop-up: {e}")


def apply_to_job(driver):
    global submitted_applications
    last_form_elements = {'dropdowns': None, 'inputs': None, 'multiple_choice': None}
    current_form_elements = {}
    stuck_count = 0
    MAX_STUCK_COUNT = 2  # Adjust this count based on your observations

    while True:
        review_button_elements = driver.find_elements(By.XPATH, "//button[@aria-label='Review your application']")
        review_button = review_button_elements[0] if review_button_elements else None

        next_button = None
        if not review_button:
            next_button_elements = driver.find_elements(By.XPATH, "//button[@aria-label='Continue to next step' and "
                                                                  "@data-easy-apply-next-button]")
            next_button = next_button_elements[0] if next_button_elements else None

        if not next_button and not review_button:
            handle_final_submission(driver)
            submitted_applications += 1
            update_application_count()
            break

        # Capture current form element labels
        current_form_elements['dropdowns'] = get_form_element_labels(driver, 'dropdowns')
        current_form_elements['inputs'] = get_form_element_labels(driver, 'inputs')
        current_form_elements['multiple_choice'] = get_form_element_labels(driver, 'multiple_choice')

        # Check if stuck in a loop
        if current_form_elements == last_form_elements:
            stuck_count += 1
            if stuck_count >= MAX_STUCK_COUNT:
                trigger_failsafe(driver)
                break
        else:
            stuck_count = 0  # Reset stuck count if progress is made

        # Update last form elements
        last_form_elements = current_form_elements.copy()

        handle_dropdowns(driver)
        handle_inputs(driver)
        handle_multiple_choice(driver)

        # Click 'Next' or 'Review'
        if next_button:
            driver.execute_script("arguments[0].click();", next_button)
        elif review_button:
            driver.execute_script("arguments[0].click();", review_button)

        time.sleep(2)


def get_form_element_labels(driver, element_type):
    labels = []
    if element_type == 'dropdowns':
        dropdowns = driver.find_elements(By.CSS_SELECTOR, 'select[data-test-text-entity-list-form-select]')
        for dropdown in dropdowns:
            labels.append(dropdown.get_attribute('aria-label'))
    elif element_type == 'inputs':
        inputs = driver.find_elements(By.XPATH,
                                      "//input[contains(@id, 'formElement') and not(@type='hidden') and not(@type='radio')]")
        for input_element in inputs:
            labels.append(input_element.get_attribute('aria-label'))
    elif element_type == 'multiple_choice':
        fieldsets = driver.find_elements(By.XPATH,
                                         "//fieldset[@data-test-form-builder-radio-button-form-component='true']")
        for fieldset in fieldsets:
            legend = fieldset.find_element(By.TAG_NAME, "legend")
            labels.append(legend.text.strip())
    return labels


def trigger_failsafe(driver):
    print("Triggering fail-safe to exit application process.")
    try:
        dismiss_button = driver.find_element(By.XPATH, "//button[@data-test-modal-close-btn]")
        driver.execute_script("arguments[0].click();", dismiss_button)
        time.sleep(2)

        discard_button = driver.find_element(By.XPATH, "//button[@data-control-name='discard_application_confirm_btn']")
        driver.execute_script("arguments[0].click();", discard_button)
        print("Application process exited. Moving to next job.")
        time.sleep(2)
    except Exception as e:
        print(f"Failed to exit application process: {e}")


def update_application_count():
    with open('application_count.json', 'r+') as file:
        data = json.load(file)
        data['submitted_applications'] = submitted_applications
        file.seek(0)  # Reset file position to the beginning
        json.dump(data, file, indent=4)
        file.truncate()  # Remove remaining part of the old data


def generate_personalized_message(job_details, job_title, recruiter_name):
    # OPTIONAL FUNCTION FOR MESSAGING JOB RECRUITER AFTER YOU'VE APPLIED
    openai.api_key = "INSERT API KEY"
    # Prepare the prompt for GPT
    resume = "INSERT THE TEXT FROM YOUR RESUME"

    prompt = "INSERT YOUR PROMPT HERE, I HAD MINE INCLUDE MY RESUME TO CATER MESSAGE"

    try:
        # Generate the completion using GPT-3
        completion = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            max_tokens=1000
        )

        # Extract the response
        response_content = completion.choices[0].text.strip()

    except openai.error.OpenAIError as e:
        print(f"An error occurred while querying GPT-3: {e}")
        return None

    return response_content


def craft_message(driver, details):
    try:
        # Extract the job title
        job_title_element = driver.find_element(By.XPATH,
                                                "//h2[contains(@class, 'job-details-jobs-unified-top-card__job-title')]")
        job_title = job_title_element.text.strip()
        print("Job Title:", job_title)

        # Try a different approach to locate the recruiter's name
        recruiter_section = driver.find_element(By.XPATH, "//div[contains(@class, 'hirer-card__container')]")
        recruiter_name = recruiter_section.find_element(By.TAG_NAME, 'strong').text.strip()
        print("Recruiter Name:", recruiter_name)

        # Generate personalized message using GPT
        personalized_message = generate_personalized_message(details, job_title, recruiter_name)
        print("Personalized Message:", personalized_message)

        # Craft the subject line
        subject = f"Interest in {job_title}"

        # Locate and click the Message button
        message_button = driver.find_element(By.XPATH, "//button[.//span[text()='Message']]")
        message_button.click()
        time.sleep(2)  # Wait for the message dialog to open

        # Fill out the subject line
        subject_input = driver.find_element(By.XPATH, "//input[@placeholder='Subject (optional)']")
        subject_input.send_keys(subject)
        time.sleep(2)

        # Fill out the message body
        message_text_area = driver.find_element(By.XPATH, "//div[@contenteditable='true']")
        message_text_area.send_keys(personalized_message)
        time.sleep(2)

        # Locate and click the Send button
        send_button = driver.find_element(By.XPATH,
                                          "//button[@class='msg-form__send-button artdeco-button artdeco-button--1']")
        send_button.click()
        print("Message sent successfully.")
        time.sleep(2)

    except NoSuchElementException:
        print("Unable to locate message elements.")
    except Exception as e:
        print(f"An error occurred while sending the message: {e}")

    time.sleep(1)


def check_if_job_description_matches(details, job_title):
    # OPTIONAL FUNCTION FOR WHEN MESSAGING IS TURNED ON, CHECKS WHETHER IT'S WORTH IT TO MESSAGE
    openai.api_key = "INSERT API KEY"

    prompt = f"I am looking for: {job_title} jobs. Please make sure that this job relates to it. Here is text " \
             f"containing the job description: {details}. If this job does not seem to be in line with what I am " \
             f"looking for simply output the string 'False', if it does seem in line with the type of job I am " \
             f"looking for then simply return the string 'True'. Make sure that your output is only one of those " \
             f"two values and nothing else. Thank you."

    try:
        # Generate the completion using GPT-3
        completion = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            max_tokens=1000
        )

        # Extract the response
        response_content = completion.choices[0].text.strip()

    except openai.error.OpenAIError as e:
        print(f"An error occurred while querying GPT-3: {e}")
        return False

    return response_content


def go_through_jobs(driver, job_title, messages, skip_pages_count=0):
    current_page = 1
    job_index = 0  # Initialize job index

    # Function to click on the ellipsis button
    def click_ellipsis():
        ellipsis_buttons = driver.find_elements(By.XPATH,
                                                "//li[contains(@class, 'artdeco-pagination__indicator')]/button["
                                                ".//span[text()='…']]")
        if ellipsis_buttons:
            # Click on the last ellipsis button (to move forward)
            ellipsis_buttons[-1].click()
            time.sleep(2)  # Wait for the page numbers to update

    # Skip pages if required
    for _ in range(skip_pages_count):
        click_ellipsis()
        current_page += 3 if current_page >= 9 else 8  # Update current page count accordingly

    while True:
        print(current_page)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'scaffold-layout__list-container')))

        while True:
            job_list_container = driver.find_element(By.CLASS_NAME, 'scaffold-layout__list-container')
            job_links = job_list_container.find_elements(By.XPATH,
                                                         ".//li[contains(@class, "
                                                         "'jobs-search-results__list-item')]//a[contains(@class, "
                                                         "'job-card-container__link')]")

            if job_index >= len(job_links):
                break  # Break the inner loop to move to the next page

            try:
                # Scroll into view
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", job_links[job_index])
                time.sleep(2)
                job_links[job_index].click()
                time.sleep(0.2)
                driver.execute_script("arguments[0].click();", job_links[job_index])
                time.sleep(0.2)
                job_links[job_index].click()
                time.sleep(0.2)
                driver.execute_script("arguments[0].click();", job_links[job_index])
                time.sleep(0.2)
                action_chains = ActionChains(driver)
                action_chains.click(job_links[job_index]).perform()
                time.sleep(5)

                # Check for Easy Apply button's presence
                easy_apply_button_xpath = "//button[contains(@class, 'jobs-apply-button') and contains(@aria-label, " \
                                          "'Easy Apply')] "
                if not driver.find_elements(By.XPATH, easy_apply_button_xpath):
                    print("No Easy Apply button, possibly already applied. Moving to next job.")
                    job_index += 1
                    continue

                if messages:
                    details = get_job_details(driver)
                    job_match = check_if_job_description_matches(details, job_title)
                    if job_match == 'True':
                        easy_apply_button = driver.find_element(By.XPATH, easy_apply_button_xpath)
                        easy_apply_button.click()
                        time.sleep(5)
                        apply_to_job(driver)
                        message_box_xpath = "//div[contains(@class, 'hirer-card__message-container')]//button[" \
                                            "contains(@class, 'artdeco-button') and .//span[text()='Message']] "
                        if driver.find_elements(By.XPATH, message_box_xpath):
                            message_button = driver.find_element(By.XPATH, message_box_xpath)
                            ActionChains(driver).move_to_element(message_button).perform()
                            craft_message(driver, details)
                        else:
                            print("Message option not available for this job.")
                else:
                    easy_apply_button = driver.find_element(By.XPATH, easy_apply_button_xpath)
                    easy_apply_button.click()
                    time.sleep(0.2)
                    driver.execute_script("arguments[0].click();", easy_apply_button)
                    time.sleep(0.2)
                    action_chains = ActionChains(driver)
                    action_chains.click(easy_apply_button).perform()
                    time.sleep(5)
                    apply_to_job(driver)

                job_index += 1
                time.sleep(5)
            except Exception as e:
                print(f"Error processing job item: {e}")
                job_index += 1

        try:
            # Handling pagination
            next_page_button_xpath = f"//li[@data-test-pagination-page-btn='{current_page + 1}']/button"
            next_page_button_elements = driver.find_elements(By.XPATH, next_page_button_xpath)

            if next_page_button_elements:
                next_page_button = next_page_button_elements[0]
                next_page_button.click()
                current_page += 1
                job_index = 0

            else:
                click_ellipsis()  # Click on the forward ellipsis button
                current_page += 1  # Update current page number

            time.sleep(5)
        except TimeoutException:
            print(f"Reached the last page or cannot click page {current_page}.")
            break
        except Exception as e:
            print(f"Error navigating to next page: {e}")
            break
    time.sleep(5)


def main():
    global submitted_applications
    # Read the current count from the file
    with open('application_count.json', 'r') as file:
        data = json.load(file)
        submitted_applications = data.get('submitted_applications', 0)

    url = 'https://www.linkedin.com/login'
    your_username = "example@gmail.com"
    your_password = "example password"
    job_title = 'data scientist' # FILL WITH WHAT YOU WANT TO APPLY TO
    entry_level = False
    messages = False

    # Initialize the Chrome WebDriver
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run Chrome in headless mode
    driver = webdriver.Chrome(options=chrome_options)

    # Maximize the browser window
    driver.maximize_window()

    # Load cookies if they exist, else perform login and save cookies
    if os.path.exists(COOKIES_FILE_PATH):
        driver.get(url)
        load_cookies(driver, COOKIES_FILE_PATH)
        driver.refresh()  # Refresh after loading cookies
        time.sleep(5)
    else:
        login(driver, url, your_username, your_password)
        save_cookies(driver, COOKIES_FILE_PATH)
        time.sleep(5)

    get_jobs_list(driver, job_title, entry_level)
    go_through_jobs(driver, job_title, messages, skip_pages_count=0)


if __name__ == '__main__':
    main()
