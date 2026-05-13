import json
import os
from chainlit import user_session as session
from chainlit.context import context
from chainlit.types import ToastType
from asyncio import run
import re

script_dir = os.path.dirname(__file__)
db_path = os.path.join(script_dir, 'database.json')

def send_toast(message: str, type: ToastType = "success"):
    run(context.emitter.emit("toast", {"message": message, "type": type}))


transfer_agent_def = {
    "name": "transfer_agent",
    "description": "Transfers the conversation to another agent (Car rental support agent or Airline assistant support agent). Before calling this tool, the assistant should briefly warn the user that he/she will be transferred to another agent. After the agent transfer, the new agent must be introduced to the user.",
    "parameters": {
        "type": "object",
        "properties": {
            "context": {
                "type": "string",
                "description": "Conversation context including user name and authentication status if possible."
            },
            "language": {
                "type": "string",
                "enum": [
                    "en",
                    "es"
                ],
                "description": "Language the user is speaking. e.g. 'en' or 'es'"
            },
            "target_agent": {
                "type": "string",
                "enum": [
                    "airline",
                    "car_rental"
                ],
                "description": "Key of the agent to transfer to: 'airline' or 'car_rental'.",
                "default": "car_rental"
            }
        },
        "required": ["context", "language", "target_agent"]
    }
}

authenticate_user_id_def = {
    "name": "user_auth",
    "description": "Authenticate the user's indentity using the user's id (e.g. 47239P).",
    "parameters": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "User id",
            }
        },
        "required": ["user_id"],
    }
}

authenticate_user_access_key_def = {
    "name": "user_access_key_auth",
    "description": "Authenticate the user's access key.",
    "parameters": {
        "type": "object",
        "properties": {
            "access_key": {
                "type": "string",
                "description": "User access key",
            }
        },
        "required": ["access_key"],
    }
}

check_flight_status_def = {
    "name": "check_user_flight_status",
    "description": "Retrieves the current status (e.g., Confirmed, Delayed) for a specific flight number associated with a verified user ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "flight_number": {
                "type": "string",
                "description": "The specific flight number to check the status",
            }
        },
        "required": ["flight_number"], 
    }
}

make_flight_reservation_def = {
    "name": "make_flight_reservation",
    "description": "Makes a flight reservation for a specific user, adding the flight to their bookings if available.",
    "parameters": {
        "type": "object",
        "properties": {
            "flight_number": {
                "type": "string",
                "description": "The specific flight number to reserve.",
            }
        },
        "required": ["flight_number"], 
    }
}


cancel_flight_reservation_def = {
    "name": "cancel_flight_reservation",
    "description": "Cancels an existing flight reservation for a specific user, removing the flight from their bookings.",
    "parameters": {
        "type": "object",
        "properties": {
            "flight_number": {
                "type": "string",
                "description": "The specific flight number of the reservation to cancel.",
            }
        },
        "required": ["flight_number"], 
    }
}

check_available_flights_def = {
    "name": "check_available_flights",
    "description": "Changes an existing flight reservation to one of the available flight selections.",
    "parameters": {
        "type": "object",
        "properties": {
            "flight_number": {
                "type": "string",
                "description": "The specific flight number of the reservation to change.",
            },
        },
        "required": ["flight_number", "new_flight_number"], 
    }
}

change_flight_reservation_def = {
    "name": "change_flight_reservation",
    "description": "Changes an existing flight reservation to one of the available flight selections.",
    "parameters": {
        "type": "object",
        "properties": {
            "actual_flight_number": {
                "type": "string",
                "description": "The specific flight number of the reservation to change.",
            },
            "new_flight_number": {
                "type": "string",
                "description": "The flight number specific to the new flight.",
            },
        },
        "required": ["actual_flight_number", "new_flight_number"], 
    } 
}

check_available_cars_def = {
    "name": "check_available_cars",
    "description": "Checks available cars to rent",
    "parameters":{}
}

rent_car_def = {
    "name": "rent_car",
    "description": "Rents a car",
    "parameters": {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": "The specific model the user wants to rent.",
            }
        },
        "required": ["model"], 
    } 
}

calculate_price_def = {
    "name": "calculate_price",
    "description": "Calculate the total price of the car renting, taking into account the numbers of the days of the travel and the percentage of the car insurance.",
    "parameters": {
        "type": "object",
        "properties": {
            "car_price": {
                "type": "integer",
                "description": "The price of the car per day.",
            },
            "days": {
                "type": "integer",
                "description": "Number of days the user is renting the car",
            },
            "insurance_price": {
                "type": "integer",
                "description": "The percentage of the chosen insurance per day. For example, if the percentage of the insurance is 20%, should be 20.",
            },
        },
        "required": ["car_price", "days", "insurance_price"],
    }
}

def transfer_agent(context: str, language: str, target_agent: str = "car_rental"):
    send_toast("Your call is being transferred soon", "success")
    print(f'CONTEXTO: {context} \nIDIOMA: {language}')
    return {
        "context": context,
        "language": language,
        "target_agent": target_agent,
        "auth_state": "User is authenticated" if session.get("user_auth", False) else "User is not authenticated"
    }

def authenticate_user_id(user_id: str):
    global db_path
    try:
        with open(db_path, "r", encoding='utf-8') as file:
            data = json.load(file)

        airline_users = data.get("airline_dataset", [])

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        error_message = f"Internal error processing user data: {type(e).__name__}"
        print(error_message)
        return {"status": "error", "message": error_message}
    except Exception as e: 
        error_message = f"Unexpected internal error: {type(e).__name__}"
        print(error_message)
        return {"status": "error", "message": error_message}

    provided_id_norm = re.sub(r'[\s\.-]', '', user_id).lower() # ID normalized

    for user in airline_users:
        if isinstance(user, dict):
            found_user_id = user.get("id")
            print("PROVIDED ID:", provided_id_norm)
            print("FOUND_ID:", found_user_id)
            if str(found_user_id).strip().lower() == provided_id_norm.lower():
                name = user.get("name", "User") # Default value "User"
                surname = user.get("surname", "")   # Default value ""
                full_name = f"{name} {surname}".strip()
                session.set("user_id", provided_id_norm) 
                send_toast(f"Your id was received correctly {found_user_id}", "success")
                return {
                    "status": "In progress",
                    "message": f"User id found in database. Access key required.",
                    "user_details": {
                        "id": found_user_id, # The original ID from the record
                    }
                }

    send_toast(f"User not found for id: {provided_id_norm}", "error")
    return {"status": "error", "message": "User not found. Please check your ID."}

def authenticate_user_access_key(access_key: str):
    global db_path
    user_id = session.get("user_id")
    print("USER ID AUTH KEY: ",user_id)
    try:
        with open(db_path, "r", encoding='utf-8') as file:
            data = json.load(file)

        airline_users = data.get("airline_dataset", [])

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        error_message = f"Internal error processing user data: {type(e).__name__}"
        print(error_message)
        return {"status": "error", "message": error_message}
    except Exception as e: 
        error_message = f"Unexpected internal error: {type(e).__name__}"
        print(error_message)
        return {"status": "error", "message": error_message}

    provided_access_key_norm = re.sub(r'[\s\.-]', '', access_key).lower()
    print("PROVIDED ACCESS_KEY", access_key)

    for user in airline_users:
        found_user_id = user.get("id")
        found_user_access_key = user.get("access_key")
        print("FOUND_ACCESS_KEY:", found_user_access_key)
        if str(found_user_id).strip().lower() == user_id and str(found_user_access_key).strip().lower() == provided_access_key_norm.lower():
            name = user.get("name", "User") # Default value "User"
            surname = user.get("surname", "")   # Default value ""
            full_name = f"{name} {surname}".strip()
            session.set("user_auth", True) 
            send_toast(f"User: {full_name} authenticated")
            return {
                "status": "success",
                "message": f"User access key authenticated: {full_name}. The user is properly authenticated.",
                "user_details": {
                    "id": found_user_id, # The original ID from the record
                    "name": name,
                    "surname": surname,
                }
            }
        session.set("user_auth", False) 
        send_toast(f"User access key could not be authenticated, received access key: {provided_access_key_norm}", "error")
        return {
                "status": "denied",
                "message": f"User access key could not be authenticated",
                "user_details": {
                    "id": found_user_id, # The original ID from the record
                }
            }
            
def check_flight_status(flight_number: str):
    global db_path
    user_id = session.get("user_id")

    try:
        with open(db_path, "r", encoding='utf-8') as file:
            data = json.load(file)

        airline_users = data.get("airline_dataset", [])
        if not isinstance(airline_users, list):
            raise ValueError("Unexpected format for airline_dataset, expected a list.")

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        error_message = f"Internal error processing flight data: {type(e).__name__}"
        return {"status": "error", "message": error_message}
    except Exception as e:
        error_message = f"Unexpected internal error: {type(e).__name__}"
        return {"status": "error", "message": error_message}

    if not session.get("user_auth"):
        send_toast(f"Called check_flight_status before user was authenticated", "error")
        return {
            "status": "denied",
            "message": f"User access key must be authenticated."
        }

    user_id_norm = user_id
    provided_flight_norm = re.sub(r'[\s\.-]', '', flight_number).lower()
    # print("PROVIDED FLIGHT_ID:", provided_flight_norm)

    user_record = None
    for user in airline_users:
        if isinstance(user, dict):
            record_id = user.get("id")
            if record_id and str(record_id).strip().lower() == user_id_norm:
                user_record = user
                break

    if user_record is None:
        return {
            "status": "user_not_found",
            "message": f"User ID {user_id} not found in our records."
        }

    fly_status_info = user_record.get("fly_status", {})
    found_flight_number = fly_status_info.get("flight_number")
    print("FOUND FLIGHT_ID:", found_flight_number)
    flight_to_check = provided_flight_norm
    if provided_flight_norm:
        flight_to_check = provided_flight_norm

    if str(found_flight_number).strip().lower() == flight_to_check:
        record_status = fly_status_info.get("status", "Status unknown")
        name = user_record.get("name", "User")
        surname = user_record.get("surname", "")
        full_name = f"{name} {surname}".strip()

        send_toast(f"Status for flight {found_flight_number} for user {full_name} (ID: {user_id}) is: {record_status}.", "success")
        return {
            "status": "success",
            "message": f"Status for flight {found_flight_number} for user {full_name} (ID: {user_id}) is: {record_status}.",
            "flight_details": {
                "user_id": user_id,
                "flight_number": found_flight_number,
                "current_status": record_status
            }
        }
    else:
        actual_flight = found_flight_number if found_flight_number else "no specific flight listed"
        send_toast(f"User {user_id} found, but they are not associated with flight {provided_flight_norm} in this record. Found flight associated: {actual_flight}.", "error")
        return {
            "status": "flight_mismatch",
            "message": f"User {user_id} found, but they are not associated with flight {provided_flight_norm} in this record. Found flight associated: {actual_flight}."
        }

def cancel_flight_reservation(flight_number: str):
    global db_path
    user_id = session.get("user_id")
    print("USER ID CANCELACION: ",user_id)
    try:
        with open(db_path, "r", encoding='utf-8') as file:
            data = json.load(file)

        airline_users = data.get("airline_dataset", [])
        if not isinstance(airline_users, list):
            raise ValueError("Unexpected format for airline_dataset, expected a list.")

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        error_message = f"Internal error processing flight data: {type(e).__name__}"
        return {"status": "error", "message": error_message}
    except Exception as e:
        error_message = f"Unexpected internal error: {type(e).__name__}"
        return {"status": "error", "message": error_message}

    if not session.get("user_auth"):
        send_toast("Called cancel_flight_reservation before user was authenticated", "error")
        return {
            "status": "denied",
            "message": f"User access key must be authenticated."
        }
        
    user_id_norm = user_id
    provided_flight_norm = flight_number.strip().lower()
    # print("PROVIDED FLIGHT_ID:", provided_flight_norm)

    user_record = None
    for user in airline_users:
        if isinstance(user, dict):
            record_id = user.get("id")
            if record_id and str(record_id).strip().lower() == user_id_norm:
                user_record = user
                break

    if user_record is None:
        return {
            "status": "user_not_found",
            "message": f"User ID {user_id} not found in our records."
        }

    fly_status_info = user_record.get("fly_status", {})
    found_flight_number = fly_status_info.get("flight_number")
    print("FOUND FLIGHT_ID:", found_flight_number)

    flight_to_check = provided_flight_norm
    if provided_flight_norm:
        flight_to_check = provided_flight_norm.strip().lower()

    if str(found_flight_number).strip().lower() == flight_to_check:
        send_toast(f"Flight {found_flight_number} successfully cancelled for user {user_id}.", "success")
        return {
            "status": "success",
            "message": f"Flight {found_flight_number} successfully cancelled for user {user_id}.",
        }

    send_toast(f"Flight {found_flight_number} could not be found successfully for user {user_id}.", "error")
    return {
        "status": "flight_not_found",
        "message": f"Flight {found_flight_number} could not be found successfully for user {user_id}.",
    }

def check_available_flights(flight_number: str):
    global db_path
    user_id = session.get("user_id")
    try:
        with open(db_path, "r", encoding='utf-8') as file:
            data = json.load(file)

        airline_users = data.get("airline_dataset", [])
        if not isinstance(airline_users, list):
            raise ValueError("Unexpected format for airline_dataset, expected a list.")

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        error_message = f"Internal error processing flight data: {type(e).__name__}"
        return {"status": "error", "message": error_message}
    except Exception as e:
        error_message = f"Unexpected internal error: {type(e).__name__}"
        return {"status": "error", "message": error_message}

    if not session.get("user_auth"):
        send_toast(f"Called check_available_flights before user was authenticated", "error")
        return {
            "status": "denied",
            "message": f"User access key must be authenticated."
        }

    provided_user_id_norm = user_id
    provided_flight_norm = flight_number.strip().lower()
    # print("PROVIDED FLIGHT_ID:", provided_flight_norm)

    user_record = None
    for user in airline_users:
        if isinstance(user, dict):
            record_id = user.get("id")
            if record_id and str(record_id).strip().lower() == provided_user_id_norm:
                user_record = user # Found the matching user record
                break # Stop searching once the user is found

    if user_record is None:
        return {
            "status": "user_not_found",
            "message": f"User ID {user_id} not found in our records."
        }

    fly_status_info = user_record.get("fly_status", {})
    found_flight_number = fly_status_info.get("flight_number")
    print("FOUND FLIGHT_ID:", found_flight_number)

    if str(found_flight_number).strip().lower() == provided_flight_norm.lower():
        # Get origin and destination of the user's flight
        origin = fly_status_info.get("origin")
        destination = fly_status_info.get("destination")

        available_flights = []
        flights_data = data.get("fights_dataset", [])[0]
        
        for flight_id, flight_details in flights_data.items():
            if (flight_details.get("origin") == origin and 
                flight_details.get("destination") == destination and
                flight_id != found_flight_number):
                flight_details["flight_number"] = flight_id
                available_flights.append(flight_details)
        
        send_toast(f"Succesfully found available flights from {origin} to {destination}", "success")
        return {
            "status": "success",
            "message": f"Available flights from {origin} to {destination}",
            "current_flight": found_flight_number,
            "available_flights": available_flights
        }
    
    send_toast(f"Flight number {provided_flight_norm} is not associated with user ID {user_id}.", "error")
    return {
        "status": "flight_not_found",
        "message": f"Flight number {provided_flight_norm} is not associated with user ID {user_id}."
    }

def change_flight_reservation(actual_flight_number: str, new_flight_number: str):

    if not session.get("user_auth"):
        send_toast(f"Called change_flight_reservation before user was authenticated", "error")
        return {
            "status": "denied",
            "message": f"User access key must be authenticated."
        }

    send_toast(f"Flight successfully changed to {new_flight_number}", "success")
    return {
        "status": "success",
        "message": f"Flight successfully changed to {new_flight_number}.",
    } 

def check_available_cars():
    try:
        with open(db_path, "r", encoding='utf-8') as file:
            data = json.load(file)

        cars_dataset = data.get("cars_dataset", [])
        if not isinstance(cars_dataset, list):
            raise ValueError("Unexpected format for cars_dataset, expected a list.")

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        error_message = f"Internal error processing flight data: {type(e).__name__}"
        return {"status": "error", "message": error_message}
    except Exception as e:
        error_message = f"Unexpected internal error: {type(e).__name__}"
        return {"status": "error", "message": error_message}

    send_toast(f"Checked available cars", "success")
    return cars_dataset

def rent_car(model: str):
    print("AUTHENTICATION STATUS: ", session.get("user_auth"))
    if not session.get("user_auth"):
        send_toast(f"Called rent_car before user was authenticated", "error")
        return {
            "status": "denied",
            "message": f"User must be authenticated first."
        }
    try:
        with open(db_path, "r", encoding='utf-8') as file:
            data = json.load(file)

        car_rental_dataset = data.get("car_rental_dataset", {})
        if not isinstance(car_rental_dataset, dict):
            raise ValueError("Unexpected format for car_rental_dataset, expected a list.")

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        error_message = f"Internal error processing flight data: {type(e).__name__}"
        return {"status": "error", "message": error_message}
    except Exception as e:
        error_message = f"Unexpected internal error: {type(e).__name__}"
        return {"status": "error", "message": error_message}
    
    send_toast(f"Rented {model} successfully", "success")
    return f'Success: rented {model}'

def calculate_price(car_price: int, days: int, insurance_price: int):
    total_price = car_price*days + insurance_price/100*car_price*days
    return total_price

transfer_agent_tool = (transfer_agent_def, transfer_agent)
authenticate_user_id_tool = (authenticate_user_id_def, authenticate_user_id)
authenticate_user_access_key_tool = (authenticate_user_access_key_def,authenticate_user_access_key)
check_flight_status_tool = (check_flight_status_def, check_flight_status)
cancel_flight_reservation_tool = (cancel_flight_reservation_def, cancel_flight_reservation)
check_available_flights_tool = (check_available_flights_def, check_available_flights)
change_flight_reservation_tool = (change_flight_reservation_def, change_flight_reservation)
calculate_price_tool = (calculate_price_def, calculate_price)

airline_agent_tools = [
    transfer_agent_tool,
    authenticate_user_id_tool,
    authenticate_user_access_key_tool,
    check_flight_status_tool,
    cancel_flight_reservation_tool,
    check_available_flights_tool,
    change_flight_reservation_tool,
]

check_available_cars_tool = (check_available_cars_def, check_available_cars)
rent_car_tool = (rent_car_def, rent_car)

car_agent_tools = [
    check_available_cars_tool,
    rent_car_tool,
    transfer_agent_tool,
    authenticate_user_id_tool,
    authenticate_user_access_key_tool,
    calculate_price_tool,
]

tools = [
    transfer_agent_tool, 
    authenticate_user_id_tool,
    authenticate_user_access_key_tool, 
    check_flight_status_tool, 
    cancel_flight_reservation_tool,
    check_available_flights_tool,
    change_flight_reservation_tool,
]