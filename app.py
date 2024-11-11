# udyam\app.py

import os
import re
import json
import uuid
import logging
import time
import threading
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, request, jsonify, abort, url_for
from werkzeug.exceptions import HTTPException

from automate_form import (
    initiate_adhar,
    submit_otp,
    submit_pan,
    submit_form,
    automate_form_next,
    submit_otp_and_captcha,
    get_captcha_screenshot
)
from database import (
    UdyamRegistration,
    get_db_session,
    Vendor,
    FormStatus,
    Gender,
    SocialCategory,
    RegistrationStage
)

app = Flask(__name__, static_folder='static', static_url_path='/static')

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "7X9Y2Z4A1B8C3D6E5F")

logging.basicConfig(level=logging.DEBUG)
DEBUG_MODE = os.environ.get("DEBUG_MODE", "False").lower() == "true"

def validate_aadhaar(aadhaar):
    return bool(re.match(r"^\d{12}$", aadhaar))

def validate_name(name):
    return bool(re.match(r"^[a-zA-Z\s]{1,100}$", name))

def validate_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({"status": "error", "message": "Missing API key"}), 401
        
        db_session = get_db_session()
        try:
            vendor = db_session.query(Vendor).filter_by(api_key=api_key).first()
            if not vendor:
                return jsonify({"status": "error", "message": "Invalid API key"}), 401
            
            # Convert both datetimes to UTC for comparison
            current_time = datetime.now(timezone.utc)
            expiry_time = vendor.api_key_expires_at
            if expiry_time.tzinfo is None:
                expiry_time = expiry_time.replace(tzinfo=timezone.utc)
            
            if expiry_time < current_time:
                return jsonify({"status": "error", "message": "API key has expired"}), 401
            
            request.vendor_id = vendor.id
            return f(*args, **kwargs)
        finally:
            db_session.close()
    
    return decorated_function


class InvalidAPIUsage(Exception):
    status_code = 400

    def _init_(self, message, status_code=None, payload=None):
        super()._init_()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

@app.errorhandler(InvalidAPIUsage)
def invalid_api_usage(e):
    return jsonify(e.to_dict()), e.status_code

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        response = e.get_response()
        response.data = json.dumps({
            "code": e.code,
            "name": e.name,
            "description": e.description,
        })
        response.content_type = "application/json"
    else:
        response = jsonify({
            "code": 500,
            "name": "Internal Server Error",
            "description": str(e),
        })
        response.status_code = 500
    return response

def ensure_timezone_aware(dt):
    """Convert naive datetime to timezone-aware UTC datetime"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def update_registration_stage(registration_id, stage, details=None, error=None):
    session = get_db_session()
    try:
        registration = session.query(UdyamRegistration).filter_by(id=registration_id).first()
        if registration:
            if not isinstance(stage, RegistrationStage):
                logging.error(f"Invalid stage type: {type(stage)}. Expected RegistrationStage")
                return
            
            registration.current_stage = stage
            if details:
                registration.stage_details[stage.value] = details
            if error:
                registration.error_message = error
            
            # Ensure timezone awareness
            registration.last_updated = ensure_timezone_aware(datetime.now())
            session.commit()
            logging.info(f"Updated registration {registration_id} to stage: {stage.value}")
    except Exception as e:
        session.rollback()
        logging.error(f"Error updating registration stage: {str(e)}")
    finally:
        session.close()



def process_registration(registration_id):
    session = get_db_session()
    try:
        registration = session.query(UdyamRegistration).filter_by(id=registration_id).first()
        if not registration:
            app.logger.error(f"Registration not found for ID: {registration_id}")
            return

        # Step 1: Initiate Aadhaar
        result = initiate_adhar(registration.aadhaar, registration.name, registration_id)
        if "Error" in result:
            raise Exception(result)
        
        update_registration_stage(registration_id, RegistrationStage.AADHAAR_SUBMITTED, 
                                  {"aadhaar": registration.aadhaar, "name": registration.name})
        
        registration.form_status = FormStatus.AWAITING_OTP
        session.commit()

        # Wait for OTP submission (this will be handled by a separate API endpoint)
        app.logger.info(f"Waiting for OTP submission for registration ID: {registration_id}")
        return

    except Exception as e:
        update_registration_stage(registration_id, RegistrationStage.ERROR, 
                                  error=f"Error processing registration: {str(e)}")
        registration.form_status = FormStatus.ERROR
        session.commit()
        app.logger.error(f"Error processing registration {registration_id}: {str(e)}")
    finally:
        session.close()


def continue_registration_after_otp(registration_id):
    session = get_db_session()
    logging.info(f"Starting post-OTP registration process for ID: {registration_id}")
    
    try:
        registration = session.query(UdyamRegistration).filter_by(id=registration_id).first()
        if not registration:
            error_msg = f"Registration not found for ID: {registration_id}"
            logging.error(error_msg)
            raise ValueError(error_msg)

        try:
            # Step 2: Submit PAN
            logging.info("Starting PAN submission process")
            pan_data = {
                "pan": registration.pan,
                "pan_name": registration.pan_name,
                "dob": registration.dob,
                "have_gstin": registration.have_gstin
            }
            
            result = submit_pan(pan_data, registration_id)
            if isinstance(result, str) and "Error" in result:
                raise Exception(f"PAN submission failed: {result}")
            
            update_registration_stage(registration_id, RegistrationStage.PAN_SUBMITTED, 
                                    {"pan_data": pan_data, "submission_result": result})
            logging.info("PAN submission completed successfully")

            # Step 3: Submit Basic Form Details
            logging.info("Starting basic form submission")
            form_data = {
                # Personal Details
                "mobile": registration.mobile,
                "email": registration.email,
                "social_category": registration.social_category.value,
                "gender": registration.gender.value,
                "specially_abled": "Y" if registration.specially_abled else "N",
                
                # Enterprise Details
                "enterprise_name": registration.enterprise_name,
                "unit_name": registration.unit_name,
                
                # Plant Address
                "premises_number": registration.premises_number,
                "building_name": registration.building_name,
                "village_town": registration.village_town,
                "block": registration.block,
                "road_street_lane": registration.road_street_lane,
                "city": registration.city,
                "state": registration.state,
                "district": registration.district,
                "pincode": registration.pincode,
                
                # Official Address
                "official_premises_number": registration.official_premises_number,
                "official_address": registration.official_address,
                "official_town": registration.official_town,
                "official_block": registration.official_block,
                "official_lane": registration.official_lane,
                "official_city": registration.official_city,
                "official_state": registration.official_state,
                "official_district": registration.official_district,
                "official_pincode": registration.official_pincode,
                
                # Business Details
                "date_of_incorporation": registration.date_of_incorporation,
                "date_of_commencement": registration.date_of_commencement,
                "bank_name": registration.bank_name,
                "account_number": registration.account_number,
                "ifsc_code": registration.ifsc_code
            }
            
            result = submit_form(form_data, registration_id)
            if isinstance(result, str) and "Error" in result:
                raise Exception(f"Form submission failed: {result}")
            
            update_registration_stage(registration_id, RegistrationStage.BASIC_DETAILS_FILLED, 
                                    {"form_data": form_data, "submission_result": result})
            logging.info("Basic form details submitted successfully")

            # Step 4: Submit Additional Details
            logging.info("Starting additional details submission")
            additional_data = {
                "major_activity": registration.major_activity,
                "second_form_section": registration.second_form_section,
                "nic_codes": registration.nic_codes,
                "employee_counts": {
                    "male": registration.male_employees,
                    "female": registration.female_employees,
                    "others": registration.other_employees
                },
                "investment_data": {
                    "wdv": registration.investment_wdv,
                    "exclusion_cost": registration.investment_exclusion_cost
                },
                "turnover_data": {
                    "total_turnover": registration.total_turnover,
                    "export_turnover": registration.export_turnover
                },
                "district": registration.district
            }
            
            result = automate_form_next(registration_id, **additional_data)
            if isinstance(result, dict) and result.get('status') == 'error':
                raise Exception(f"Additional details submission failed: {result.get('message')}")
            
            update_registration_stage(registration_id, RegistrationStage.ADDITIONAL_DETAILS_FILLED, 
                                    {"additional_data": additional_data, "submission_result": result})
            logging.info("Additional details submitted successfully")

            # Update final status
            registration.form_status = FormStatus.COMPLETED
            registration.current_stage = RegistrationStage.COMPLETED
            session.commit()
            logging.info(f"Registration {registration_id} completed successfully")

        except Exception as process_error:
            error_msg = f"Process error: {str(process_error)}"
            logging.error(error_msg)
            update_registration_stage(registration_id, RegistrationStage.ERROR, error=error_msg)
            registration.form_status = FormStatus.ERROR
            session.commit()
            raise Exception(error_msg)

    except Exception as e:
        error_msg = f"Error continuing registration {registration_id}: {str(e)}"
        logging.error(error_msg)
        try:
            update_registration_stage(registration_id, RegistrationStage.ERROR, error=error_msg)
            if registration:
                registration.form_status = FormStatus.ERROR
                session.commit()
        except Exception as commit_error:
            logging.error(f"Failed to record error state: {str(commit_error)}")
        raise Exception(error_msg)

    finally:
        try:
            session.close()
            logging.info(f"Session closed for registration {registration_id}")
        except Exception as session_error:
            logging.error(f"Error closing session: {str(session_error)}")


@app.route("/api/udyam/register", methods=["POST"])
@validate_api_key
def register_udyam():
    data = request.json
    if not isinstance(data, list):
        data = [data]  # Convert single registration to list
    
    session = get_db_session()
    registration_ids = []
    
    try:
        for registration_data in data:
            registration_id = str(uuid.uuid4())
            registration_data['id'] = registration_id
            registration_data['vendor_id'] = request.vendor_id
            
            # Convert gender to enum
            registration_data['gender'] = Gender(registration_data['gender'])
            
            # Convert social_category to enum
            registration_data['social_category'] = SocialCategory(registration_data['social_category'])
            
            # Convert specially_abled to boolean
            if isinstance(registration_data['specially_abled'], bool):
                registration_data['specially_abled'] = registration_data['specially_abled']
            elif isinstance(registration_data['specially_abled'], str):
                registration_data['specially_abled'] = registration_data['specially_abled'].lower() == 'true'
            else:
                registration_data['specially_abled'] = False
            
            new_registration = UdyamRegistration(**registration_data)
            session.add(new_registration)
            registration_ids.append(registration_id)
        
        session.commit()
        
        # Start the registration process for each registration in separate threads
        for reg_id in registration_ids:
            update_registration_stage(reg_id, RegistrationStage.INITIATED)
            threading.Thread(target=process_registration, args=(reg_id,)).start()
        
        return jsonify({
            "status": "success", 
            "message": f"{len(registration_ids)} registrations initiated successfully",
            "registration_ids": registration_ids
        }), 202
    except Exception as e:
        session.rollback()
        app.logger.error(f"Error in register_udyam: {str(e)}")
        raise InvalidAPIUsage(str(e), status_code=400)
    finally:
        session.close()

@app.route("/api/udyam/submit_otp", methods=["POST"])
@validate_api_key
def submit_otp_route():
    data = request.json
    if 'otp' not in data or 'registration_id' not in data:
        raise InvalidAPIUsage("OTP and registration ID are required", status_code=400)
    
    registration_id = data['registration_id']
    db_session = get_db_session()
    try:
        registration = db_session.query(UdyamRegistration).filter_by(id=registration_id, vendor_id=request.vendor_id).first()
        if not registration:
            raise InvalidAPIUsage("Registration not found", status_code=404)
        
        if registration.form_status != FormStatus.AWAITING_OTP:
            raise InvalidAPIUsage("Registration is not awaiting OTP", status_code=400)
        
        result = submit_otp(data['otp'], registration_id)
        if "Error" in result:
            raise InvalidAPIUsage(result, status_code=500)
        
        update_registration_stage(registration_id, RegistrationStage.OTP_VERIFIED, {"otp": data['otp']})
        registration.form_status = FormStatus.OTP_VERIFIED
        db_session.commit()
        
        # Continue with the rest of the registration process
        threading.Thread(target=continue_registration_after_otp, args=(registration_id,)).start()
        
        return jsonify({"status": "success", "message": "OTP verified, continuing registration"})
    except Exception as e:
        db_session.rollback()
        raise InvalidAPIUsage(str(e), status_code=500)
    finally:
        db_session.close()

@app.route("/api/udyam/status/<registration_id>", methods=["GET"])
@validate_api_key
def get_registration_status(registration_id):
    session = get_db_session()
    try:
        registration = session.query(UdyamRegistration).filter_by(id=registration_id, vendor_id=request.vendor_id).first()
        if not registration:
            raise InvalidAPIUsage("Registration not found", status_code=404)
        
        # Get all stages in order
        all_stages = list(RegistrationStage)
        current_stage_index = all_stages.index(registration.current_stage)
        
        # Create a list of all stages with their status
        stages_status = []
        for stage in all_stages:
            stage_info = {
                "stage": stage.value,
                "completed": all_stages.index(stage) <= current_stage_index,
                "details": registration.stage_details.get(stage.value, {})
            }
            stages_status.append(stage_info)
        
        status_info = {
            "status": "success",
            "registration_id": registration_id,
            "form_status": registration.form_status.value,
            "current_stage": registration.current_stage.value,
            "stages": stages_status,
            "last_updated": registration.last_updated.isoformat(),
            "error_message": registration.error_message
        }

        return jsonify(status_info)
    except Exception as e:
        raise InvalidAPIUsage(str(e), status_code=400)
    finally:
        session.close()


@app.route("/api/udyam/retry", methods=["POST"])
@validate_api_key
def retry_registration():
    data = request.json
    if 'registration_id' not in data:
        raise InvalidAPIUsage("Registration ID is required", status_code=400)
    
    registration_id = data['registration_id']
    db_session = get_db_session()
    try:
        registration = db_session.query(UdyamRegistration).filter_by(id=registration_id, vendor_id=request.vendor_id).first()
        if not registration:
            raise InvalidAPIUsage("Registration not found", status_code=404)
        
        if registration.form_status != FormStatus.ERROR:
            raise InvalidAPIUsage("Only failed registrations can be retried", status_code=400)
        
        # Reset the status and start the process again
        registration.form_status = FormStatus.INITIATED
        registration.current_stage = RegistrationStage.INITIATED
        registration.stage_details = {}
        registration.error_message = None
        db_session.commit()
        
        # Start the registration process in a separate thread
        threading.Thread(target=process_registration, args=(registration_id,)).start()
        
        return jsonify({
            "status": "success", 
            "message": "Registration retry initiated successfully",
            "registration_id": registration_id
        }), 202
    except Exception as e:
        db_session.rollback()
        raise InvalidAPIUsage(str(e), status_code=500)
    finally:
        db_session.close()

@app.route("/api/udyam/fetch_captcha", methods=["GET"])
@validate_api_key
def fetch_captcha():
    registration_id = request.args.get('registration_id')
    if not registration_id:
        raise InvalidAPIUsage("Registration ID is required", status_code=400)

    db_session = get_db_session()
    try:
        registration = db_session.query(UdyamRegistration).filter_by(id=registration_id, vendor_id=request.vendor_id).first()
        if not registration:
            raise InvalidAPIUsage("Registration not found", status_code=404)

        captcha_path = get_captcha_screenshot(registration_id)
        if captcha_path:
            # Get the filename from the full path
            captcha_filename = os.path.basename(captcha_path)
            
            # Construct the URL for the captcha image
            captcha_url = url_for('static', filename=f'captcha_images/{captcha_filename}', _external=True)
            
            update_registration_stage(registration_id, RegistrationStage.CAPTCHA_REQUIRED, {"captcha_url": captcha_url})
            
            return jsonify({
                "status": "success", 
                "message": "CAPTCHA screenshot saved successfully",
                "captcha_url": captcha_url
            })
        else:
            raise InvalidAPIUsage("Failed to capture CAPTCHA screenshot", status_code=500)
    except Exception as e:
        raise InvalidAPIUsage(str(e), status_code=500)
    finally:
        db_session.close()

@app.route("/api/udyam/submit_otp_and_captcha", methods=["POST"])
@validate_api_key
def submit_otp_and_captcha_route():
    data = request.json
    if 'otp' not in data or 'captcha' not in data or 'registration_id' not in data:
        raise InvalidAPIUsage("OTP, CAPTCHA, and registration ID are required", status_code=400)
    
    registration_id = data['registration_id']
    db_session = get_db_session()
    try:
        registration = db_session.query(UdyamRegistration).filter_by(id=registration_id, vendor_id=request.vendor_id).first()
        if not registration:
            raise InvalidAPIUsage("Registration not found", status_code=404)
        
        result = submit_otp_and_captcha(data['otp'], data['captcha'], registration_id)
        
        if result['status'] == 'success':
            update_registration_stage(registration_id, RegistrationStage.COMPLETED, 
                                      {"otp": data['otp'], "captcha": data['captcha']})
            registration.form_status = FormStatus.COMPLETED
        elif result['status'] == 'error':
            update_registration_stage(registration_id, RegistrationStage.ERROR, 
                                      error=result['message'])
            registration.form_status = FormStatus.ERROR
        
        db_session.commit()
        
        return jsonify(result)
    except Exception as e:
        db_session.rollback()
        raise InvalidAPIUsage(str(e), status_code=500)
    finally:
        db_session.close()

@app.route("/api/vendor/register", methods=["POST"])
def register_vendor():
    data = request.json
    if 'name' not in data or 'email' not in data:
        raise InvalidAPIUsage("Vendor name and email are required", status_code=400)
    
    db_session = get_db_session()
    try:
        new_vendor = Vendor(name=data['name'], email=data['email'])
        new_vendor.generate_api_key()
        db_session.add(new_vendor)
        db_session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Vendor registered successfully",
            "vendor_id": new_vendor.id,
            "api_key": new_vendor.api_key
        }), 201
    except Exception as e:
        db_session.rollback()
        raise InvalidAPIUsage(str(e), status_code=400)
    finally:
        db_session.close()

@app.route("/api/vendor/refresh_api_key", methods=["POST"])
@validate_api_key
def refresh_api_key():
    db_session = get_db_session()
    try:
        vendor = db_session.query(Vendor).filter_by(id=request.vendor_id).first()
        if not vendor:
            raise InvalidAPIUsage("Vendor not found", status_code=404)
        
        vendor.generate_api_key()
        db_session.commit()
        
        return jsonify({
            "status": "success",
            "message": "API key refreshed successfully",
            "new_api_key": vendor.api_key
        })
    except Exception as e:
        db_session.rollback()
        raise InvalidAPIUsage(str(e), status_code=400)
    finally:
        db_session.close()

@app.route("/api/vendor/registrations", methods=["GET"])
@validate_api_key
def get_vendor_registrations():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    db_session = get_db_session()
    try:
        registrations = db_session.query(UdyamRegistration).filter_by(vendor_id=request.vendor_id)\
            .order_by(UdyamRegistration.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        registration_list = [{
            "id": reg.id,
            "aadhaar": reg.aadhaar,
            "name": reg.name,
            "form_status": reg.form_status.value,
            "current_stage": reg.current_stage.value,
            "created_at": reg.created_at.isoformat(),
            "last_updated": reg.last_updated.isoformat()
        } for reg in registrations.items]
        
        return jsonify({
            "status": "success",
            "registrations": registration_list,
            "total": registrations.total,
            "pages": registrations.pages,
            "current_page": page
        })
    except Exception as e:
        raise InvalidAPIUsage(str(e), status_code=400)
    finally:
        db_session.close()

@app.route("/api/vendor/login", methods=["POST"])
def vendor_login():
    data = request.json
    if 'email' not in data or 'api_key' not in data:
        raise InvalidAPIUsage("Email and API key are required", status_code=400)
    
    db_session = get_db_session()
    try:
        vendor = db_session.query(Vendor).filter_by(email=data['email'], api_key=data['api_key']).first()
        if not vendor:
            raise InvalidAPIUsage("Invalid credentials", status_code=401)
        
        return jsonify({
            "status": "success",
            "message": "Login successful",
            "vendor_id": vendor.id
        })
    except Exception as e:
        raise InvalidAPIUsage(str(e), status_code=400)
    finally:
        db_session.close()

def process_registration_with_retry(registration_id, max_retries=3):
    for attempt in range(max_retries):
        try:
            process_registration(registration_id)
            break
        except Exception as e:
            logging.error(f"Error processing registration {registration_id} (Attempt {attempt + 1}): {str(e)}")
            if attempt == max_retries - 1:
                update_registration_stage(registration_id, RegistrationStage.ERROR, 
                                          error=f"Failed after {max_retries} attempts: {str(e)}")
            else:
                time.sleep(5 * (attempt + 1))  # Exponential backoff

@app.route("/api/udyam/bulk_status", methods=["POST"])
@validate_api_key
def get_bulk_registration_status():
    data = request.json
    if 'registration_ids' not in data or not isinstance(data['registration_ids'], list):
        raise InvalidAPIUsage("List of registration IDs is required", status_code=400)
    
    db_session = get_db_session()
    try:
        registrations = db_session.query(UdyamRegistration).filter(
            UdyamRegistration.id.in_(data['registration_ids']),
            UdyamRegistration.vendor_id == request.vendor_id
        ).all()
        
        status_info = [{
            "registration_id": reg.id,
            "form_status": reg.form_status.value,
            "current_stage": reg.current_stage.value,
            "last_updated": reg.last_updated.isoformat(),
            "error_message": reg.error_message
        } for reg in registrations]
        
        return jsonify({
            "status": "success",
            "registrations": status_info
        })
    except Exception as e:
        raise InvalidAPIUsage(str(e), status_code=400)
    finally:
        db_session.close()

@app.route("/api/udyam/statistics", methods=["GET"])
@validate_api_key
def get_registration_statistics():
    db_session = get_db_session()
    try:
        total_registrations = db_session.query(UdyamRegistration).filter_by(vendor_id=request.vendor_id).count()
        completed_registrations = db_session.query(UdyamRegistration).filter_by(
            vendor_id=request.vendor_id, 
            form_status=FormStatus.COMPLETED
        ).count()
        error_registrations = db_session.query(UdyamRegistration).filter_by(
            vendor_id=request.vendor_id, 
            form_status=FormStatus.ERROR
        ).count()
        
        from sqlalchemy import func
        stage_counts = db_session.query(
            UdyamRegistration.current_stage, 
            func.count(UdyamRegistration.id)
        ).filter_by(vendor_id=request.vendor_id).group_by(UdyamRegistration.current_stage).all()
        
        stage_statistics = {stage.value: count for stage, count in stage_counts}
        
        return jsonify({
            "status": "success",
            "total_registrations": total_registrations,
            "completed_registrations": completed_registrations,
            "error_registrations": error_registrations,
            "stage_statistics": stage_statistics
        })
    except Exception as e:
        raise InvalidAPIUsage(str(e), status_code=400)
    finally:
        db_session.close()


@app.route("/api/udyam/export", methods=["GET"])
@validate_api_key
def export_registrations():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        raise InvalidAPIUsage("Start date and end date are required", status_code=400)
    
    try:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise InvalidAPIUsage("Invalid date format. Use YYYY-MM-DD", status_code=400)
    
    db_session = get_db_session()
    try:
        registrations = db_session.query(UdyamRegistration).filter(
            UdyamRegistration.vendor_id == request.vendor_id,
            UdyamRegistration.created_at >= start_date,
            UdyamRegistration.created_at <= end_date
        ).all()
        
        export_data = [{
            "id": reg.id,
            "aadhaar": reg.aadhaar,
            "name": reg.name,
            "pan": reg.pan,
            "form_status": reg.form_status.value,
            "current_stage": reg.current_stage.value,
            "created_at": reg.created_at.isoformat(),
            "last_updated": reg.last_updated.isoformat(),
            "error_message": reg.error_message
        } for reg in registrations]
        
        return jsonify({
            "status": "success",
            "export_data": export_data
        })
    except Exception as e:
        raise InvalidAPIUsage(str(e), status_code=400)
    finally:
        db_session.close()

if __name__ == '__main__':
    app.run(debug=DEBUG_MODE, port=2000)


