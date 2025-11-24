"""
Payments Endpoints - Stripe Integration
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
import stripe
import logging

from ....core.dependencies import get_current_user, UserInDB
from ....core.config import settings
from ....core.constants import get_plan_by_id
from ....core.exceptions import NotFoundException, PaymentException
from ....infrastructure.database.mongodb import get_db
from ...schemas.plan import CheckoutRequest, CheckoutResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/stripe/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    checkout_req: CheckoutRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Create Stripe checkout session for plan upgrade
    
    - Creates Stripe Price object
    - Applies first-month discount if applicable
    - Returns checkout URL
    """
    if not settings.STRIPE_SECRET_KEY:
        raise PaymentException(detail="Payment system not configured")
    
    # Get plan details
    plan = get_plan_by_id(checkout_req.plan_id)
    if not plan:
        raise NotFoundException(detail="Plan not found")
    
    # Get organization plan
    org_plan = await db.organization_plans.find_one(
        {"organization_id": current_user.organization_id}
    )
    
    if not org_plan:
        raise NotFoundException(detail="Organization plan not found")
    
    is_first_month = org_plan.get("is_first_month", True)
    price_monthly = plan.get("price_monthly", 0)
    
    if price_monthly <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trial plan cannot be purchased"
        )
    
    try:
        # Create Stripe Price (normal price)
        price_kurus = int(price_monthly * 100)
        
        stripe_price = stripe.Price.create(
            currency='try',
            unit_amount=price_kurus,
            recurring={'interval': 'month'},
            product_data={
                'name': f'PLANN {plan.get("name", "Plan")} Plan'
            }
        )
        
        # Create discount coupon for first month
        coupon_id = None
        if is_first_month:
            try:
                coupon = stripe.Coupon.create(
                    percent_off=25,
                    duration='once',
                    name='İlk Ay %25 İndirim',
                    id=f'first_month_{current_user.organization_id}_{int(datetime.now(timezone.utc).timestamp())}'
                )
                coupon_id = coupon.id
                logger.info(f"✅ First-month coupon created: {coupon_id}")
            except stripe.error.StripeError as e:
                logger.warning(f"Coupon creation failed: {e}")
                coupon_id = None
        
        # Create checkout session
        session_params = {
            'payment_method_types': ['card'],
            'mode': 'subscription',
            'line_items': [{
                'price': stripe_price.id,
                'quantity': 1,
            }],
            'customer_email': current_user.username,
            'metadata': {
                'user_id': current_user.organization_id,
                'plan_id': checkout_req.plan_id,
                'organization_id': current_user.organization_id,
                'is_first_month': str(is_first_month)
            },
            'success_url': settings.PAYMENT_SUCCESS_URL + f'?session_id={{CHECKOUT_SESSION_ID}}',
            'cancel_url': settings.PAYMENT_CANCEL_URL,
            'billing_address_collection': 'required',
        }
        
        # Apply coupon if exists
        if coupon_id:
            session_params['discounts'] = [{'coupon': coupon_id}]
            logger.info(f"🎁 First-month discount applied: {price_monthly * 0.75} TL")
        else:
            session_params['allow_promotion_codes'] = True
        
        session = stripe.checkout.Session.create(**session_params)
        
        # Create payment log
        actual_amount = price_monthly * 0.75 if is_first_month else price_monthly
        await db.payment_logs.insert_one({
            "session_id": session.id,
            "organization_id": current_user.organization_id,
            "user_id": current_user.username,
            "plan_id": checkout_req.plan_id,
            "status": "pending",
            "amount": actual_amount,
            "original_amount": price_monthly,
            "currency": "TRY",
            "is_first_month": is_first_month,
            "discount_applied": is_first_month,
            "payment_provider": "stripe",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"✅ Stripe checkout created: {session.id} for plan {checkout_req.plan_id}")
        
        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id
        )
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise PaymentException(detail=f"Payment processing failed: {str(e)}")


@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Stripe webhook handler
    
    Handles:
    - checkout.session.completed
    - Updates payment logs
    - Activates subscription
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured"
        )
    
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid payload")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    
    # Handle event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        logger.info(f"✅ Checkout completed: {session['id']}")
        
        # Get metadata
        metadata = session.get('metadata', {})
        org_id = metadata.get('organization_id')
        plan_id = metadata.get('plan_id')
        
        if org_id and plan_id:
            # Update payment log
            await db.payment_logs.update_one(
                {"session_id": session['id']},
                {"$set": {
                    "status": "completed",
                    "stripe_subscription_id": session.get('subscription'),
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # Update organization plan
            await db.organization_plans.update_one(
                {"organization_id": org_id},
                {"$set": {
                    "plan_id": plan_id,
                    "is_first_month": False,
                    "stripe_subscription_id": session.get('subscription'),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            logger.info(f"✅ Plan activated: {plan_id} for org {org_id}")
        else:
            logger.warning(f"Missing metadata in session: {session['id']}")
    
    return {"status": "success"}
