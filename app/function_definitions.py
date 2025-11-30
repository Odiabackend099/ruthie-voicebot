"""
Function Definitions for Deepgram Agent API - PRODUCTION READY
Rewritten with user-intent focus to prevent false positive function calls.

CRITICAL CHANGES (2025-11-30):
- Removed imperative language ("Call this FIRST") that LLM was speaking out loud
- Added explicit trigger examples and negative cases
- Removed implementation details ("stores", "tells you")
- Focus on WHEN to use, not HOW it works internally
"""

# =============================================================================
# BOOKING APPOINTMENT FLOW (8 steps)
# Sequence: initiate → name → email → phone → company → date → time → service → purpose → confirm
# =============================================================================

BOOKING_FUNCTIONS = [
    {
        "name": "initiate_booking",
        "description": "Use ONLY when user explicitly requests to book/schedule an appointment (e.g., 'I want to book', 'Schedule an appointment', 'Book a call'). Do NOT use for general inquiries, greetings, or questions about services.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_intent": {
                    "type": "string",
                    "description": "The exact phrase the user said that indicates they want to book (e.g., 'I want to book an appointment')"
                }
            },
            "required": ["user_intent"]
        }
    },
    {
        "name": "collect_client_name",
        "description": "Use when the user has provided their full name during the booking process. Extract the name from their message.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_name": {
                    "type": "string",
                    "description": "The customer's full name as they provided it"
                }
            },
            "required": ["client_name"]
        }
    },
    {
        "name": "collect_client_email",
        "description": "Use when the user has provided their email address during booking. Extract the email from their message.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_email": {
                    "type": "string",
                    "description": "Email address in format user@domain.com"
                }
            },
            "required": ["client_email"]
        }
    },
    {
        "name": "collect_client_phone",
        "description": "Use when the user has provided their phone number during booking. Extract the phone number from their message.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_phone": {
                    "type": "string",
                    "description": "Phone number with country code in E.164 format (e.g., +2348141995397)"
                }
            },
            "required": ["client_phone"]
        }
    },
    {
        "name": "collect_company_name",
        "description": "Use when the user has provided their company name during booking. Extract the company name from their message.",
        "parameters": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "The name of the customer's company or organization"
                }
            },
            "required": ["company_name"]
        }
    },
    {
        "name": "collect_booking_date",
        "description": "Use when the user has provided their preferred appointment date. Convert natural language dates to YYYY-MM-DD format.",
        "parameters": {
            "type": "object",
            "properties": {
                "booking_date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (e.g., 2024-12-15). Convert natural language dates like 'next Tuesday' to this format."
                }
            },
            "required": ["booking_date"]
        }
    },
    {
        "name": "collect_booking_time",
        "description": "Use when the user has provided their preferred appointment time. Convert to 24-hour format.",
        "parameters": {
            "type": "object",
            "properties": {
                "booking_time": {
                    "type": "string",
                    "description": "Time in HH:MM format (24-hour, e.g., 14:30 for 2:30 PM)"
                }
            },
            "required": ["booking_time"]
        }
    },
    {
        "name": "collect_service_type",
        "description": "Use when the user has specified what type of service they need (e.g., consultation, demo, support).",
        "parameters": {
            "type": "object",
            "properties": {
                "service_type": {
                    "type": "string",
                    "description": "Type of service (e.g., consultation, demo, follow-up, support)"
                }
            },
            "required": ["service_type"]
        }
    },
    {
        "name": "collect_purpose",
        "description": "Use when the user has described the purpose or reason for the appointment.",
        "parameters": {
            "type": "object",
            "properties": {
                "purpose": {
                    "type": "string",
                    "description": "Brief description of the appointment's purpose"
                }
            },
            "required": ["purpose"]
        }
    },
    {
        "name": "confirm_and_book",
        "description": "Use ONLY after user explicitly confirms all booking details are correct (e.g., user says 'yes', 'that's correct', 'looks good'). This creates the actual booking. NEVER use until user confirms.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string"},
                "client_email": {"type": "string"},
                "client_phone": {"type": "string"},
                "company_name": {"type": "string"},
                "booking_date": {"type": "string"},
                "booking_time": {"type": "string"},
                "service_type": {"type": "string"},
                "purpose": {"type": "string"}
            },
            "required": ["client_name", "client_email", "client_phone", "company_name", "booking_date", "booking_time", "service_type", "purpose"]
        }
    },
]

# =============================================================================
# RESCHEDULE APPOINTMENT FLOW (4 steps)
# Sequence: initiate → email → new_date → new_time → confirm
# =============================================================================

RESCHEDULE_FUNCTIONS = [
    {
        "name": "initiate_reschedule",
        "description": "Use ONLY when user explicitly requests to reschedule/change an existing appointment (e.g., 'Reschedule my appointment', 'Change my booking', 'Move my appointment'). Do NOT use for new bookings or general questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_intent": {
                    "type": "string",
                    "description": "The exact phrase indicating they want to reschedule"
                }
            },
            "required": ["user_intent"]
        }
    },
    {
        "name": "collect_reschedule_email",
        "description": "Use when user provides the email address associated with their existing booking.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_email": {
                    "type": "string",
                    "description": "The email address associated with the booking"
                }
            },
            "required": ["client_email"]
        }
    },
    {
        "name": "collect_new_date",
        "description": "Use when user provides their new preferred date for the rescheduled appointment.",
        "parameters": {
            "type": "object",
            "properties": {
                "new_date": {
                    "type": "string",
                    "description": "New date in YYYY-MM-DD format"
                }
            },
            "required": ["new_date"]
        }
    },
    {
        "name": "collect_new_time",
        "description": "Use when user provides their new preferred time for the rescheduled appointment.",
        "parameters": {
            "type": "object",
            "properties": {
                "new_time": {
                    "type": "string",
                    "description": "New time in HH:MM format (24-hour)"
                }
            },
            "required": ["new_time"]
        }
    },
    {
        "name": "confirm_and_reschedule",
        "description": "Use ONLY after user confirms the new date/time are correct. This actually updates the booking.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_email": {"type": "string"},
                "new_date": {"type": "string"},
                "new_time": {"type": "string"}
            },
            "required": ["client_email", "new_date", "new_time"]
        }
    },
]

# =============================================================================
# CANCEL APPOINTMENT FLOW (2 steps)
# Sequence: initiate → email → confirm
# =============================================================================

CANCEL_FUNCTIONS = [
    {
        "name": "initiate_cancel",
        "description": "Use ONLY when user explicitly requests to cancel an existing appointment (e.g., 'Cancel my appointment', 'I need to cancel', 'Delete my booking'). Do NOT use for rescheduling.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_intent": {
                    "type": "string",
                    "description": "The exact phrase indicating they want to cancel"
                }
            },
            "required": ["user_intent"]
        }
    },
    {
        "name": "collect_cancel_email",
        "description": "Use when user provides the email address associated with the booking they want to cancel.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_email": {
                    "type": "string",
                    "description": "Email address associated with the booking to cancel"
                }
            },
            "required": ["client_email"]
        }
    },
    {
        "name": "confirm_and_cancel",
        "description": "Use ONLY after user confirms they want to cancel (not reschedule). This permanently cancels the booking.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_email": {"type": "string"}
            },
            "required": ["client_email"]
        }
    },
]

# =============================================================================
# EMAIL FLOW (4 steps)
# Sequence: initiate → recipient → subject → message → confirm
# =============================================================================

EMAIL_FUNCTIONS = [
    {
        "name": "initiate_email",
        "description": "Use ONLY when user explicitly requests to send an email (e.g., 'Send an email to...', 'Email john@example.com'). Do NOT use for booking confirmations (those are automatic).",
        "parameters": {
            "type": "object",
            "properties": {
                "user_intent": {
                    "type": "string",
                    "description": "The exact phrase indicating they want to send an email"
                }
            },
            "required": ["user_intent"]
        }
    },
    {
        "name": "collect_email_recipient",
        "description": "Use when user provides the recipient's email address.",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient_email": {
                    "type": "string",
                    "description": "Recipient's email address"
                }
            },
            "required": ["recipient_email"]
        }
    },
    {
        "name": "collect_email_subject",
        "description": "Use when user provides the email subject line.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Email subject line"
                }
            },
            "required": ["subject"]
        }
    },
    {
        "name": "collect_email_message",
        "description": "Use when user provides the email message body/content.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Email message body"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "confirm_and_send_email",
        "description": "Use ONLY after user confirms the email details are correct. This actually sends the email.",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient_email": {"type": "string"},
                "subject": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["recipient_email", "subject", "message"]
        }
    },
]

# =============================================================================
# SMS FLOW (3 steps)
# Sequence: initiate → phone → message → confirm
# =============================================================================

SMS_FUNCTIONS = [
    {
        "name": "initiate_sms",
        "description": "Use ONLY when user explicitly requests to send an SMS/text message (e.g., 'Text me at...', 'Send an SMS to...'). Do NOT use for booking confirmations.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_intent": {
                    "type": "string",
                    "description": "The exact phrase indicating they want to send SMS"
                }
            },
            "required": ["user_intent"]
        }
    },
    {
        "name": "collect_sms_phone",
        "description": "Use when user provides the phone number to send SMS to.",
        "parameters": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "Phone number with country code (E.164 format)"
                }
            },
            "required": ["phone_number"]
        }
    },
    {
        "name": "collect_sms_message",
        "description": "Use when user provides the SMS message content.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "SMS message text"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "confirm_and_send_sms",
        "description": "Use ONLY after user confirms the SMS details. This actually sends the text message.",
        "parameters": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["phone_number", "message"]
        }
    },
]

# =============================================================================
# WHATSAPP FLOW (3 steps)
# Sequence: initiate → phone → message → confirm
# =============================================================================

WHATSAPP_FUNCTIONS = [
    {
        "name": "initiate_whatsapp",
        "description": "Use ONLY when user explicitly requests to send a WhatsApp message (e.g., 'WhatsApp me at...', 'Send via WhatsApp'). Do NOT use for SMS or booking confirmations.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_intent": {
                    "type": "string",
                    "description": "The exact phrase indicating they want WhatsApp"
                }
            },
            "required": ["user_intent"]
        }
    },
    {
        "name": "collect_whatsapp_phone",
        "description": "Use when user provides the WhatsApp phone number.",
        "parameters": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "WhatsApp phone number with country code"
                }
            },
            "required": ["phone_number"]
        }
    },
    {
        "name": "collect_whatsapp_message",
        "description": "Use when user provides the WhatsApp message content.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "WhatsApp message text"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "confirm_and_send_whatsapp",
        "description": "Use ONLY after user confirms the WhatsApp details. This actually sends the message.",
        "parameters": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["phone_number", "message"]
        }
    },
]

# =============================================================================
# SIMPLE ACTION FUNCTIONS (No sequential flow)
# =============================================================================

SIMPLE_FUNCTIONS = [
    {
        "name": "continue_conversation",
        "description": "Use for general conversation, greetings, or answering questions when NO other specific action (booking, email, etc.) is needed. This allows you to chat naturally with the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "response_text": {
                    "type": "string",
                    "description": "The text you want to say to the user"
                }
            },
            "required": ["response_text"]
        }
    },
    {
        "name": "search_web",
        "description": "Use when user asks a question that requires current/real-time information you don't have (e.g., 'What's the weather?', 'Latest news about...'). Do NOT use for questions about Callwaiting AI services.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query based on user's question"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_current_datetime",
        "description": "Use when user asks for current date, time, or day of week (e.g., 'What's today's date?', 'What time is it?').",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_location_info",
        "description": "Use when user asks about location-specific information (e.g., 'Where are you located?', 'What's your office address?').",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
]

# =============================================================================
# FUNCTION FLOWS MAPPING
# Maps function names to their flow type for session management
# =============================================================================

FUNCTION_FLOWS = {
    # Booking flow
    "initiate_booking": "booking",
    "collect_client_name": "booking",
    "collect_client_email": "booking",
    "collect_client_phone": "booking",
    "collect_company_name": "booking",
    "collect_booking_date": "booking",
    "collect_booking_time": "booking",
    "collect_service_type": "booking",
    "collect_purpose": "booking",
    "confirm_and_book": "booking",
    
    # Reschedule flow
    "initiate_reschedule": "reschedule",
    "collect_reschedule_email": "reschedule",
    "collect_new_date": "reschedule",
    "collect_new_time": "reschedule",
    "confirm_and_reschedule": "reschedule",
    
    # Cancel flow
    "initiate_cancel": "cancel",
    "collect_cancel_email": "cancel",
    "confirm_and_cancel": "cancel",
    
    # Email flow
    "initiate_email": "email",
    "collect_email_recipient": "email",
    "collect_email_subject": "email",
    "collect_email_message": "email",
    "confirm_and_send_email": "email",
    
    # SMS flow
    "initiate_sms": "sms",
    "collect_sms_phone": "sms",
    "collect_sms_message": "sms",
    "confirm_and_send_sms": "sms",
    
    # WhatsApp flow
    "initiate_whatsapp": "whatsapp",
    "collect_whatsapp_phone": "whatsapp",
    "collect_whatsapp_message": "whatsapp",
    "confirm_and_send_whatsapp": "whatsapp",
    
    # Simple actions (no flow)
    "continue_conversation": "simple",
    "search_web": "simple",
    "get_current_datetime": "simple",
    "get_location_info": "simple",
}

# Combine all functions for Deepgram Agent API
FUNCTION_DEFINITIONS = (
    BOOKING_FUNCTIONS +
    RESCHEDULE_FUNCTIONS +
    CANCEL_FUNCTIONS +
    EMAIL_FUNCTIONS +
    SMS_FUNCTIONS +
    WHATSAPP_FUNCTIONS +
    SIMPLE_FUNCTIONS
)
