"""
Controlled enumerations for the REVIVE payment simulator.
"""

from enum import Enum


class CustomerProfile(str, Enum):
    RELIABLE = "PROFILE_A_RELIABLE"
    OCCASIONAL_FAILURE = "PROFILE_B_OCCASIONAL_FAILURE"
    HIGH_FAILURE = "PROFILE_C_HIGH_FAILURE"
    NEW_CUSTOMER = "PROFILE_D_NEW_CUSTOMER"
    SUBSCRIPTION = "PROFILE_E_SUBSCRIPTION"
    HIGH_VALUE = "PROFILE_F_HIGH_VALUE"


class CustomerSegment(str, Enum):
    CONSUMER_RETAIL = "CONSUMER_RETAIL"
    CONSUMER_PRO = "CONSUMER_PRO"
    SMB = "SMB"
    ENTERPRISE = "ENTERPRISE"


class PaymentMethod(str, Enum):
    UPI = "UPI"
    CARD = "CARD"
    NETBANKING = "NETBANKING"
    WALLET = "WALLET"


class PaymentMethodType(str, Enum):
    UPI_COLLECT = "upi_collect"
    UPI_INTENT = "upi_intent"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    NETBANKING_RETAIL = "netbanking_retail"
    NETBANKING_CORP = "netbanking_corp"
    PREPAID_WALLET = "prepaid_wallet"


class PaymentStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


class ErrorSource(str, Enum):
    GATEWAY = "gateway"
    BANK = "bank"
    CUSTOMER = "customer"
    INTERNAL = "internal"
    NETWORK = "network"


class ErrorStep(str, Enum):
    PAYMENT_AUTHENTICATION = "payment_authentication"
    PAYMENT_AUTHORIZATION = "payment_authorization"
    PAYMENT_PROCESSING = "payment_processing"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    CHECKOUT = "checkout"


class ErrorReason(str, Enum):
    TIMEOUT = "timeout"
    PAYMENT_FAILED = "payment_failed"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    AUTHENTICATION_FAILED = "authentication_failed"
    PAYMENT_METHOD_FAILED = "payment_method_failed"
    USER_ABANDONED = "user_abandoned"
    RISK_DETECTED = "risk_detected"


class FailureCategory(str, Enum):
    TRANSIENT_GATEWAY_FAILURE = "TRANSIENT_GATEWAY_FAILURE"
    BANK_DECLINE = "BANK_DECLINE"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    PAYMENT_METHOD_FAILURE = "PAYMENT_METHOD_FAILURE"
    USER_ABANDONMENT = "USER_ABANDONMENT"
    HARD_FAILURE = "HARD_FAILURE"
    HIGH_RISK = "HIGH_RISK"


class CheckoutStage(str, Enum):
    CHECKOUT_STARTED = "CHECKOUT_STARTED"
    PAYMENT_METHOD_SELECTED = "PAYMENT_METHOD_SELECTED"
    AUTHENTICATION_STARTED = "AUTHENTICATION_STARTED"
    OTP_STAGE = "OTP_STAGE"
    PAYMENT_SUBMISSION = "PAYMENT_SUBMISSION"


class RecoveryAction(str, Enum):
    RETRY = "RETRY"
    PAYMENT_LINK = "PAYMENT_LINK"
    REMINDER = "REMINDER"
    DO_NOTHING = "DO_NOTHING"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class RecoveryOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    NO_RESPONSE = "NO_RESPONSE"
    ALREADY_RESOLVED = "ALREADY_RESOLVED"
