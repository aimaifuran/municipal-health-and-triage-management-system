"""Application-specific exceptions."""

from rest_framework.exceptions import APIException


class BusinessRuleViolation(APIException):
    status_code = 400
    default_detail = "Business rule violation."
    default_code = "business_rule_violation"


class AntiIDORViolation(APIException):
    status_code = 403
    default_detail = "You do not have permission to access this resource."
    default_code = "anti_idor_violation"
