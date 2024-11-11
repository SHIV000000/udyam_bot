# Udyam Registration Automation

This project automates the process of Udyam Registration using Selenium WebDriver and Flask. It provides a RESTful API to interact with the Udyam Registration website, allowing users to submit their registration details programmatically.

## Features

- **Aadhaar verification**
- **OTP submission**
- **PAN details submission**
- **Business details submission**
- **Automated form filling**
- **Submit OTP and CAPTCHA**

## Requirements

- **Python 3.7+**
- **Flask**
- **Selenium WebDriver**
- **Chrome WebDriver**

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://gitlab.com/digicians/udyambot_web.git
   ```

### For windows installation:

Create virtual environement
```bash
python3 -m venv env
```
Activate Virtual environement
```bash
env\Scripts\activate
```

### For MacOS/Ubuntu installation:

Create virtual environement

```bash
  python3 -m venv env
```
Activate Virtual environement
```bash
  source env/bin/activate
```



2. **Install dependencies:**

   ```bash
   python3 -m pip install -r requirements.txt
   ```

3. **Set up Chrome WebDriver:**
   - Download the appropriate version of Chrome WebDriver for your system.
   - Place the WebDriver executable in your system PATH or update the `get_driver()` function in `automate_form.py` with the correct path.

Get Chrom Driver https://googlechromelabs.github.io/chrome-for-testing/#stable

## Running the Application

Start the Flask application:

```bash
python3 app.py
```

The API will be available at `http://localhost:5000`.

## API Endpoints

### Vendor Management

- **`POST /api/vendor/register`**: Register a new vendor
- **`POST /api/vendor/login`**: Vendor login
- **`POST /api/vendor/refresh_api_key`**: Refresh vendor's API key

### Udyam Registration

- **`POST /api/udyam/register`**: Initiate Udyam registration
- **`POST /api/udyam/submit_otp`**: Submit OTP for verification
- **`GET /api/udyam/status/<registration_id>`**: Check registration status
- **`POST /api/udyam/retry`**: Retry a failed registration
- **`GET /api/udyam/fetch_captcha`**: Fetch CAPTCHA for final submission
- **`POST /api/udyam/submit_otp_and_captcha`**: Submit OTP and CAPTCHA and complete registration

### Vendor Registrations

- **`GET /api/vendor/registrations`**: Get vendor's registration list

## Postman Collection

```json
{
  "info": {
    "_postman_id": "your-postman-id-here",
    "name": "Udyam Registration Automation",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:5000",
      "type": "string"
    },
    {
      "key": "api_key",
      "value": "your_api_key_here",
      "type": "string"
    }
  ],
  "item": [
    {
      "name": "Vendor Management",
      "item": [
        {
          "name": "Register Vendor",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n    \"name\": \"Test Vendor\",\n    \"email\": \"vendor@example.com\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/api/vendor/register",
              "host": ["{{base_url}}"],
              "path": ["api", "vendor", "register"]
            }
          }
        },
        {
          "name": "Vendor Login",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n    \"email\": \"vendor@example.com\",\n    \"api_key\": \"{{api_key}}\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/api/vendor/login",
              "host": ["{{base_url}}"],
              "path": ["api", "vendor", "login"]
            }
          }
        },
        {
          "name": "Refresh API Key",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "X-API-Key",
                "value": "{{api_key}}"
              }
            ],
            "url": {
              "raw": "{{base_url}}/api/vendor/refresh_api_key",
              "host": ["{{base_url}}"],
              "path": ["api", "vendor", "refresh_api_key"]
            }
          }
        }
      ]
    },
    {
      "name": "Udyam Registration",
      "item": [
        {
          "name": "Register Udyam",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "X-API-Key",
                "value": "{{api_key}}"
              },
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n    \"aadhaar\": \"123456789012\",\n    \"name\": \"John Doe\",\n    \"pan\": \"ABCDE1234F\",\n    \"pan_name\": \"John Doe\",\n    \"dob\": \"1990-01-01\",\n    \"mobile\": \"9876543210\",\n    \"email\": \"john@example.com\",\n    \"social_category\": \"General\",\n    \"gender\": \"M\",\n    \"specially_abled\": false,\n    \"enterprise_name\": \"John's Enterprise\",\n    \"unit_name\": \"Main Unit\",\n    \"premises_number\": \"123\",\n    \"building_name\": \"Business Tower\",\n    \"village_town\": \"Sample Town\",\n    \"block\": \"Block A\",\n    \"road_street_lane\": \"Main Street\",\n    \"city\": \"Sample City\",\n    \"state\": \"Sample State\",\n    \"district\": \"Sample District\",\n    \"pincode\": \"123456\",\n    \"official_premises_number\": \"123\",\n    \"official_address\": \"123 Business Tower, Main Street\",\n    \"official_town\": \"Sample Town\",\n    \"official_block\": \"Block A\",\n    \"official_lane\": \"Main Street\",\n    \"official_city\": \"Sample City\",\n    \"official_state\": \"Sample State\",\n    \"official_district\": \"Sample District\",\n    \"official_pincode\": \"123456\",\n    \"date_of_incorporation\": \"2022-01-01\",\n    \"date_of_commencement\": \"2022-01-01\",\n    \"bank_name\": \"Sample Bank\",\n    \"account_number\": \"1234567890\",\n    \"ifsc_code\": \"SBIN0123456\",\n    \"major_activity\": \"Manufacturing\",\n    \"nic_codes\": [\n        {\n            \"category\": \"Manufacturing\",\n            \"2_digit\": \"10\",\n            \"4_digit\": \"1010\",\n            \"5_digit\": \"10101\"\n        }\n    ],\n    \"male_employees\": 5,\n    \"female_employees\": 3,\n    \"other_employees\": 0,\n    \"investment_wdv\": 500000,\n    \"investment_exclusion_cost\": 200000,\n    \"total_turnover\": 1000000,\n    \"export_turnover\": 200000,\n    \"have_gstin\": \"No\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/api/udyam/register",
              "host": ["{{base_url}}"],
              "path": ["api", "udyam", "register"]
            }
          }
        },
        {
          "name": "Submit OTP",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "X-API-Key",
                "value": "{{api_key}}"
              },
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n    \"registration_id\": \"your_registration_id_here\",\n    \"otp\": \"123456\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/api/udyam/submit_otp",
              "host": ["{{base_url}}"],
              "path": ["api", "udyam", "submit_otp"]
            }
          }
        },
        {
          "name": "Check Registration Status",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "X-API-Key",
                "value": "{{api_key}}"
              }
            ],
            "url": {
              "raw": "{{base_url}}/api/udyam/status/your_registration_id_here",
              "host": ["{{base_url}}"],
              "path": ["api", "udyam", "status", "your_registration_id_here"]
            }
          }
        },
        {
          "name": "Retry Registration",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "X-API-Key",
                "value": "{{api_key}}"
              },
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n    \"registration_id\": \"your_registration_id_here\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/api/udyam/retry",
              "host": ["{{base_url}}"],
              "path": ["api", "udyam", "retry"]
            }
          }
        },
        {
          "name": "Fetch CAPTCHA",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "X-API-Key",
                "value": "{{api_key}}"
              }
            ],
            "url": {
              "raw": "{{base_url}}/api/udyam/fetch_captcha?registration_id=your_registration_id_here",
              "host": ["{{base_url}}"],
              "path": ["api", "udyam", "fetch_captcha"],
              "query": [
                {
                  "key": "registration_id",
                  "value": "your_registration_id_here"
                }
              ]
            }
          }
        },
        {
          "name": "Submit OTP and CAPTCHA",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "X-API-Key",
                "value": "{{api_key}}"
              },
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n    \"registration_id\": \"your_registration_id_here\",\n   \"otp\": \"123456\",\n  \"captcha\": \"ABCD123\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/api/udyam/submit_otp_and_captcha",
              "host": ["{{base_url}}"],
              "path": ["api", "udyam", "submit_otp_and_captcha"]
            }
          }
        }
      ]
    },
    {
      "name": "Vendor Registrations",
      "item": [
        {
          "name": "Get Vendor Registrations",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "X-API-Key",
                "value": "{{api_key}}"
              }
            ],
            "url": {
              "raw": "{{base_url}}/api/vendor/registrations?page=1&per_page=10",
              "host": ["{{base_url}}"],
              "path": ["api", "vendor", "registrations"],
              "query": [
                {
                  "key": "page",
                  "value": "1"
                },
                {
                  "key": "per_page",
                  "value": "10"
                }
              ]
            }
          }
        }
      ]
    }
  ]
}
```

To use this Postman collection:

1. Open Postman and click on "Import" in the top left corner.
2. Copy and paste the entire JSON content above into the "Raw text" tab.
3. Click "Import" to add the collection to your Postman workspace.

### Before using the collection:

- Set the `base_url` variable to your API's base URL (e.g., `http://localhost:5000` for local development).
- After registering a vendor and receiving an API key, set the `api_key` variable to the received API key.

### Here's a brief explanation of each request in the collection:

#### Vendor Management
- **Register Vendor**: Create a new vendor account
- **Vendor Login**: Authenticate a vendor
- **Refresh API Key**: Get a new API key for a vendor

#### Udyam Registration
- **Register Udyam**: Start a new Udyam registration process
- **Submit OTP**: Verify the OTP sent during registration
- **Check Registration Status**: Get the current status of a registration
- **Retry Registration**: Attempt to retry a failed registration
- **Fetch CAPTCHA**: Get the CAPTCHA image URL for final submission
- **Submit OTP and CAPTCHA**: Submit the OTP and CAPTCHA and complete the registration

#### Vendor Registrations
- **Get Vendor Registrations**: Retrieve a list of registrations for the authenticated vendor

