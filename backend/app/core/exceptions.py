"""
Custom Exceptions
"""
from fastapi import HTTPException, status


class QuotaExceededException(HTTPException):
    """Raised when monthly appointment quota is exceeded"""
    def __init__(self, detail: str = "Monthly appointment quota exceeded"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class TrialExpiredException(HTTPException):
    """Raised when trial period has expired"""
    def __init__(self, detail: str = "Trial period has expired. Please upgrade to continue."):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail
        )


class UnauthorizedException(HTTPException):
    """Raised when user doesn't have permission"""
    def __init__(self, detail: str = "You don't have permission to perform this action"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class NotFoundException(HTTPException):
    """Raised when resource is not found"""
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class BadRequestException(HTTPException):
    """Raised for bad requests"""
    def __init__(self, detail: str = "Bad request"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


class ConflictException(HTTPException):
    """Raised when there's a conflict (e.g., duplicate entry)"""
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )


class AIServiceException(HTTPException):
    """Raised when AI service fails"""
    def __init__(self, detail: str = "AI service error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


class PaymentException(HTTPException):
    """Raised when payment processing fails"""
    def __init__(self, detail: str = "Payment processing failed"):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail
        )
