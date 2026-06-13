import frappe
import json
from datetime import datetime
# import os
# import socketserver
# import requests
# from dotenv import load_dotenv


# load_dotenv()

# QBS_URL = os.getenv("QBS_URL")
# QBS_API_KEY = os.getenv("QBS_API_KEY")
# QBS_API_SECRET = os.getenv("QBS_API_SECRET")

# LISTENER_HOST = os.getenv("LISTENER_HOST", "0.0.0.0")
# LISTENER_PORT = int(os.getenv("LISTENER_PORT", "5001"))


# HEADERS = {
#    "Authorization": f"token {QBS_API_KEY}:{QBS_API_SECRET}",
#    "Content-Type": "application/json"
# }


def clean_hl7_message(raw_message):
    """
    Remove HL7 wrapper characters if present
    """
    return (
        raw_message
        .replace("\x0b", "")
        .replace("\x1c", "")
        .replace("\x0d", "\r")
        .strip()
    )


def parse_hl7_message(message):
    """
    Parse HL7 message and extract required fields
    """

    parsed = {
        "received_at": datetime.now().isoformat(),
        "message_type": None,
        "patient_id": None,
        "patient_name": None,
        "sample_id": None,
        "order_id": None,
        "results": []
    }

    segments = message.replace("\n", "\r").split("\r")

    for segment in segments:

        if not segment.strip():
            continue

        fields = segment.split("|")

        if not fields:
            continue

        segment_type = fields[0]

        # MSH
        if segment_type == "MSH":

            if len(fields) > 8:
                parsed["message_type"] = fields[8]

        # PID
        elif segment_type == "PID":

            if len(fields) > 3:
                parsed["patient_id"] = fields[3]

            if len(fields) > 5:
                parsed["patient_name"] = fields[5].replace("^", " ")

        # OBR
        elif segment_type == "OBR":

            if len(fields) > 2:
                parsed["order_id"] = fields[2]

            if len(fields) > 3:
                parsed["sample_id"] = fields[3]

        # OBX
        elif segment_type == "OBX":

            result = {}

            if len(fields) > 3:

                test_parts = fields[3].split("^")

                result["analyzer_test_code"] = test_parts[0]

                result["test_name"] = (
                    test_parts[1]
                    if len(test_parts) > 1
                    else test_parts[0]
                )

            result["result_value"] = (
                fields[5]
                if len(fields) > 5
                else None
            )

            result["uom"] = (
                fields[6]
                if len(fields) > 6
                else None
            )

            result["reference_range"] = (
                fields[7]
                if len(fields) > 7
                else None
            )

            result["abnormal_flag"] = (
                fields[8]
                if len(fields) > 8
                else None
            )

            parsed["results"].append(result)

    return parsed

# def post_to_qbs(parsed_data, raw_message):
#    """
#    Posts received message into QBS.
#    Recommended custom DocType:
#    Instrument Message Log
#    """

#    payload = {
#        "doctype": "Instrument Message Log",
#        "instrument_protocol": "HL7",
#        "received_at": parsed_data.get("received_at"),
#        "message_type": parsed_data.get("message_type"),
#        "patient_id": parsed_data.get("patient_id"),
#        "patient_name": parsed_data.get("patient_name"),
#        "sample_id": parsed_data.get("sample_id"),
#        "order_id": parsed_data.get("order_id"),
#        "raw_message": raw_message,
#        "parsed_json": str(parsed_data),
#        "status": "Received"
#    }

#    response = requests.post(
#        f"{QBS_URL}/api/resource/Instrument Message Log",
#        headers=HEADERS,
#        json=payload,
#        timeout=20
#    )

#    response.raise_for_status()
#    return response.json()


# def post_results_to_qbs(parsed_data):
#    """
#    Optional: Creates one Instrument Result Queue entry per OBX.
#    Recommended custom DocType:
#    Instrument Result Queue
#    """

#    for result in parsed_data.get("results", []):
#        payload = {
#            "doctype": "Instrument Result Queue",
#            "sample_id": parsed_data.get("sample_id"),
#            "order_id": parsed_data.get("order_id"),
#            "patient_id": parsed_data.get("patient_id"),
#            "patient_name": parsed_data.get("patient_name"),
#            "analyzer_test_code": result.get("analyzer_test_code"),
#            "test_name": result.get("test_name"),
#            "result_value": result.get("result_value"),
#            "uom": result.get("uom"),
#            "reference_range": result.get("reference_range"),
#            "abnormal_flag": result.get("abnormal_flag"),
#            "status": "Pending Validation"
#        }

#        response = requests.post(
#            f"{QBS_URL}/api/resource/Instrument Result Queue",
#            headers=HEADERS,
#            json=payload,
#            timeout=20
#        )

#        response.raise_for_status()


def save_message_log(parsed_data, raw_message):
    """
    Save complete message to Instrument Message Log
    """

    doc = frappe.get_doc({
        "doctype": "Instrument Message Log",
        "received_at": parsed_data.get("received_at"),
        "message_type": parsed_data.get("message_type"),
        "patient_id": parsed_data.get("patient_id"),
        "patient_name": parsed_data.get("patient_name"),
        "sample_id": parsed_data.get("sample_id"),
        "order_id": parsed_data.get("order_id"),
        "raw_message": raw_message,
        "parsed_json": json.dumps(parsed_data, indent=4),
        "status": "Received"
    })

    doc.insert(ignore_permissions=True)

    return doc.name


def save_result_queue(parsed_data):
    """
    Save each OBX result as separate record
    """

    created_records = []

    for result in parsed_data.get("results", []):

        doc = frappe.get_doc({
            "doctype": "Instrument Result Queue",
            "sample_id": parsed_data.get("sample_id"),
            "order_id": parsed_data.get("order_id"),
            "patient_id": parsed_data.get("patient_id"),
            "patient_name": parsed_data.get("patient_name"),
            "analyzer_test_code": result.get("analyzer_test_code"),
            "test_name": result.get("test_name"),
            "result_value": result.get("result_value"),
            "uom": result.get("uom"),
            "reference_range": result.get("reference_range"),
            "abnormal_flag": result.get("abnormal_flag"),
            "status": "Pending Validation"
        })

        doc.insert(ignore_permissions=True)

        created_records.append(doc.name)

    return created_records


def create_hl7_ack():
    """
    Generate HL7 ACK
    """

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    ack = (
        f"MSH|^~\\&|QBS|Q10|ANALYZER|LAB|{timestamp}||ACK|1|P|2.3\r"
        f"MSA|AA|1\r"
    )

    return ack
    # return f"\x0b{ack}\x1c\x0d"

# class HL7TCPHandler(socketserver.BaseRequestHandler):

#    def handle(self):
#        raw_bytes = self.request.recv(65535)
#        raw_message = raw_bytes.decode("utf-8", errors="ignore")

#        cleaned_message = clean_hl7_message(raw_message)

#        print("\n--- HL7 MESSAGE RECEIVED ---")
#        print(cleaned_message)

#        try:
#            parsed_data = parse_hl7_message(cleaned_message)

#            post_to_qbs(parsed_data, cleaned_message)
#            post_results_to_qbs(parsed_data)

#            ack = create_hl7_ack()
#            self.request.sendall(ack.encode("utf-8"))

#            print("--- MESSAGE POSTED TO QBS SUCCESSFULLY ---")

#        except Exception as e:
#            print(f"ERROR: {e}")


# def start_listener():
#    server = socketserver.ThreadingTCPServer(
#        (LISTENER_HOST, LISTENER_PORT),
#        HL7TCPHandler
#    )

#    print(f"HL7 Listener started on {LISTENER_HOST}:{LISTENER_PORT}")
#    server.serve_forever()


# if __name__ == "__main__":
#    start_listener()


@frappe.whitelist()
def test_hl7():
    """
    POC Function
    Uses hardcoded HL7 message
    """

    sample_message = """
MSH|^~\\&|ROCHE|LAB|QBS|HOSPITAL|20260605100000||OUL^R22|12345|P|2.5
PID|1||P001||John^Doe
OBR|1|ORD001|S123
OBX|1|NM|HB^Hemoglobin||13.5|g/dL|12-16|N
OBX|2|NM|WBC^White Blood Cells||7000|cells/uL|4000-11000|N
"""

    cleaned_message = clean_hl7_message(sample_message)

    parsed_data = parse_hl7_message(cleaned_message)

    message_log = save_message_log(
        parsed_data,
        cleaned_message
    )

    result_records = save_result_queue(
        parsed_data
    )

    ack = create_hl7_ack()

    frappe.db.commit()

    return {
        "message_log": message_log,
        "result_records": result_records,
        "ack": ack,
        "parsed_data": parsed_data
    }