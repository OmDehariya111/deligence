import os
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
import stripe

from api.database import get_db
from api.models import User, PaymentEvent, Tier
from api.auth_routes import get_current_user

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

class CheckoutRequest(BaseModel):
    tier: str # PRO or ENTERPRISE

@router.post("/checkout")
def create_checkout_session(
    request: CheckoutRequest, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout Session."""
    
    if request.tier not in {"PRO", "ENTERPRISE"}:
        raise HTTPException(status_code=400, detail="Invalid tier")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")

    if not stripe.api_key:
        # Development mode should complete the same user-visible flow as Stripe,
        # rather than redirecting to a URL that does not update the account.
        if request.tier == "PRO":
            current_user.tier = Tier.PRO
            current_user.credits += 50
        else:
            current_user.tier = Tier.ENTERPRISE
            current_user.credits += 500
        db.commit()
        return {"url": f"{frontend_url}/pricing?{urlencode({'success': '1', 'tier': request.tier, 'mode': 'mock'})}"}
        
    try:
        price_id = ""
        if request.tier == "PRO":
            price_id = os.getenv("STRIPE_PRO_PRICE_ID", "price_pro_placeholder")
        else:
            price_id = os.getenv("STRIPE_ENTERPRISE_PRICE_ID", "price_enterprise_placeholder")
            
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f'{frontend_url}/pricing?success=1&session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{frontend_url}/pricing?canceled=1',
            client_reference_id=str(current_user.id),
            customer_email=current_user.email,
            metadata={"tier": request.tier},
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe Webhooks securely."""
    payload = await request.body()
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        # For mock local testing, we might want to allow raw events or just ignore if keys aren't set
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    # Idempotency check: Have we processed this event before?
    existing_event = db.query(PaymentEvent).filter(PaymentEvent.stripe_event_id == event['id']).first()
    if existing_event:
        return {"status": "already processed"}

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        user_id = session.get('client_reference_id')
        if user_id:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                purchased_tier = session.get('metadata', {}).get('tier')
                if purchased_tier == "ENTERPRISE":
                    user.tier = Tier.ENTERPRISE
                    user.credits += 500
                else:
                    user.tier = Tier.PRO
                    user.credits += 50
                
                # Record the event to prevent double-processing
                new_event = PaymentEvent(stripe_event_id=event['id'], user_id=user.id)
                db.add(new_event)
                db.commit()

    return {"status": "success"}

@router.post("/mock-success")
def mock_payment_success(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """A testing endpoint to simulate a successful payment when Stripe keys are missing."""
    if request.tier == "PRO":
        current_user.tier = Tier.PRO
        current_user.credits += 50
    elif request.tier == "ENTERPRISE":
        current_user.tier = Tier.ENTERPRISE
        current_user.credits += 500
        
    db.commit()
    db.refresh(current_user)
    return {"status": "success", "credits": current_user.credits, "tier": current_user.tier.value}
